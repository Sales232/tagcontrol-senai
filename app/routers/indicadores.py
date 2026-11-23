from datetime import date, datetime, timedelta

from flask import Blueprint, abort, render_template, request

from app.instance.indicadores import FLOW_STATUSES, calculate_indicators


indicadores_bp = Blueprint("indicadores", __name__, url_prefix="/indicadores")

STATUS_LABELS = {
    "separacao": "Em separação",
    "aguardando_conferencia": "Aguardando conferência",
    "correcao": "Em correção",
    "liberado": "Liberado",
    "embalado": "Embalado",
    "carregando": "Carregando",
    "carregado": "Carregado",
    "expedido": "Expedido",
}


@indicadores_bp.route("/", methods=["GET"], endpoint="index")
def index():
    today = datetime.utcnow().date()
    try:
        start_date = date.fromisoformat(request.args.get("inicio", "")) if "inicio" in request.args else today - timedelta(days=29)
        end_date = date.fromisoformat(request.args.get("fim", "")) if "fim" in request.args else today
    except ValueError:
        abort(400, description="Informe datas válidas para o período.")

    status = request.args.get("estado") or None
    if status not in (None, *FLOW_STATUSES):
        abort(400, description="Estado de pedido inválido.")
    if start_date > end_date:
        abort(400, description="A data inicial deve ser anterior ou igual à data final.")

    indicators = calculate_indicators(start_date, end_date, status)
    return render_template(
        "indicadores/index.html",
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        selected_status=status or "",
        statuses=STATUS_LABELS,
        indicators=indicators,
    )
