import csv

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.instance.csv_exchange import CsvExchangeError, MAX_CSV_BYTES, export_csv, import_csv


dados_bp = Blueprint("dados", __name__, url_prefix="/dados")


@dados_bp.route("/", methods=["GET"], endpoint="index")
def index():
    return render_template("dados/index.html", max_upload_mb=MAX_CSV_BYTES // (1024 * 1024))


@dados_bp.route("/exportar.csv", methods=["GET"], endpoint="exportar")
def exportar():
    response = Response(export_csv(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = 'attachment; filename="tagcontrol.csv"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@dados_bp.route("/importar", methods=["POST"], endpoint="importar")
def importar():
    upload = request.files.get("arquivo")
    if upload is None or not upload.filename:
        flash("Selecione um arquivo CSV para importar.", "error")
        return redirect(url_for("dados.index"))

    content = upload.stream.read(MAX_CSV_BYTES + 1)
    if len(content) > MAX_CSV_BYTES:
        flash("O arquivo CSV excede o limite de 10 MB.", "error")
        return redirect(url_for("dados.index"))

    try:
        record_count = import_csv(content)
    except CsvExchangeError as error:
        db.session.rollback()
        flash(str(error), "error")
        return redirect(url_for("dados.index"))
    except csv.Error:
        db.session.rollback()
        flash("O arquivo CSV possui estrutura inválida.", "error")
        return redirect(url_for("dados.index"))
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Falha ao importar registros do arquivo CSV.")
        flash("Não foi possível concluir a importação; nenhum registro foi mantido.", "error")
        return redirect(url_for("dados.index"))

    flash(f"Importação concluída: {record_count} registro(s) carregado(s).", "success")
    return redirect(url_for("dados.index"))
