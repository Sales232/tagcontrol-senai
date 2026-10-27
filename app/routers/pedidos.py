import uuid

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app import db
from app.instance.models import (
    Conferencia,
    ConferenciaItem,
    Conjunto,
    Leitura,
    Pedido,
    PedidoConjunto,
    PedidoItem,
    Peca,
    StatusLeitura,
)

pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")


@pedidos_bp.route("/", methods=["GET"], endpoint="listar")
def listar():
    pedidos = (
        Pedido.query.options(
            selectinload(Pedido.itens),
            selectinload(Pedido.leituras),
        )
        .order_by(Pedido.codigo)
        .all()
    )
    progresso_por_pedido = {pedido.id: pedido.progresso() for pedido in pedidos}
    return render_template(
        "pedidos/listar.html",
        pedidos=pedidos,
        progresso_por_pedido=progresso_por_pedido,
    )


@pedidos_bp.route("/novo", methods=["GET", "POST"], endpoint="novo")
def novo():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        if not codigo:
            flash("Código do pedido é obrigatório.", "error")
            return render_template("pedidos/form.html", pedido=Pedido(codigo=codigo))

        pedido = Pedido(codigo=codigo)
        db.session.add(pedido)
        try:
            db.session.commit()
            flash("Pedido adicionado com sucesso!", "success")
            return redirect(url_for("pedidos.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um pedido com esse código.", "error")

    return render_template("pedidos/form.html", pedido=None)


@pedidos_bp.route("/editar/<int:pedido_id>", methods=["GET", "POST"], endpoint="editar")
def editar(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        if not codigo:
            flash("Código do pedido é obrigatório.", "error")
            return render_template("pedidos/form.html", pedido=Pedido(id=pedido.id, codigo=codigo))

        pedido.codigo = codigo
        try:
            db.session.commit()
            flash("Pedido atualizado com sucesso!", "success")
            return redirect(url_for("pedidos.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um pedido com esse código.", "error")
            return render_template("pedidos/form.html", pedido=Pedido(id=pedido_id, codigo=codigo))

    return render_template("pedidos/form.html", pedido=pedido)


@pedidos_bp.route("/apagar/<int:pedido_id>", methods=["POST"], endpoint="apagar")
def apagar(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.leituras:
        flash("Não é possível apagar um pedido que possui leituras registradas.", "error")
        return redirect(url_for("pedidos.listar"))

    db.session.delete(pedido)
    try:
        db.session.commit()
        flash("Pedido excluído com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível excluir o pedido por causa de registros relacionados.", "error")

    return redirect(url_for("pedidos.listar"))


@pedidos_bp.route("/<int:pedido_id>/detalhe", methods=["GET"], endpoint="detalhe")
def detalhe(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    pecas_disponiveis = Peca.query.order_by(Peca.codigo).all()
    conjuntos_disponiveis = Conjunto.query.order_by(Conjunto.codigo).all()
    return render_template(
        "pedidos/detalhe.html",
        pedido=pedido,
        pecas_disponiveis=pecas_disponiveis,
        conjuntos_disponiveis=conjuntos_disponiveis,
        composicoes_pedido=pedido.composicoes,
        progresso=pedido.progresso(),
        progresso_por_item=pedido.progresso_por_item(),
        ultima_conferencia=pedido.conferencias[-1] if pedido.conferencias else None,
    )


@pedidos_bp.route("/<int:pedido_id>/scanner", methods=["GET"], endpoint="scanner")
def scanner(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if not pedido.itens:
        flash("Adicione peças ou aplique um conjunto antes de iniciar a separação.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if pedido.status_fluxo == "liberado":
        flash("O pedido já foi liberado. Reabra-o para iniciar uma nova separação.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    return render_template(
        "pedidos/scanner.html",
        pedido=pedido,
        progresso=pedido.progresso(),
        progresso_por_item=pedido.progresso_por_item(),
    )

@pedidos_bp.route("/<int:pedido_id>/scanner/validar", methods=["POST"], endpoint="validar_codigo")
def validar_codigo(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    payload = request.get_json(silent=True) if request.is_json else {}
    if not isinstance(payload, dict):
        payload = {}
    if not payload:
        payload = request.form.to_dict()

    codigo = str(payload.get("codigo") or payload.get("codigo_qr") or "").strip()
    if not codigo:
        return jsonify({
            "status": "erro",
            "message": "Código QR não informado.",
            "progress": pedido.progresso(),
        }), 400

    raw_idempotency_key = payload.get("idempotency_key")
    idempotency_key = None
    if raw_idempotency_key is not None:
        try:
            idempotency_key = str(uuid.UUID(str(raw_idempotency_key)))
        except (ValueError, AttributeError):
            return jsonify({
                "status": "erro",
                "message": "Chave de leitura inválida.",
                "progress": pedido.progresso(),
            }), 400

    def read_response(status, message, peca=None, *, replayed=False, response_status=200):
        response_payload = {
            "status": status.value if isinstance(status, StatusLeitura) else status,
            "message": message,
            "progress": pedido.progresso(),
            "progress_by_item": [
                {
                    "peca": {
                        "id": item["peca"].id,
                        "codigo": item["peca"].codigo,
                        "descricao": item["peca"].descricao,
                    },
                    "quantidade_necessaria": item["quantidade_necessaria"],
                    "quantidade_validada": item["quantidade_validada"],
                    "percentual": item["percentual"],
                }
                for item in pedido.progresso_por_item()
            ],
        }
        if peca is not None:
            response_payload["peca"] = {
                "id": peca.id,
                "codigo": peca.codigo,
                "descricao": peca.descricao,
            }
        if replayed:
            response_payload["replayed"] = True
        return jsonify(response_payload), response_status

    def replay_response(leitura):
        peca_lida = leitura.peca
        if codigo not in (peca_lida.codigo, peca_lida.codigo_qr):
            return read_response(
                "erro",
                "A chave de leitura já foi usada para outro código.",
                response_status=409,
            )
        replay_messages = {
            StatusLeitura.SUCESSO: f"Peça {peca_lida.codigo} validada com sucesso para o pedido.",
            StatusLeitura.DUPLICADA: f"A peça {peca_lida.codigo} já foi separada na quantidade necessária para este pedido.",
            StatusLeitura.FORA_DO_PEDIDO: f"A peça {peca_lida.codigo} não pertence a este pedido.",
        }
        return read_response(
            leitura.status,
            replay_messages[leitura.status],
            peca_lida,
            replayed=True,
        )

    if idempotency_key:
        previous_read = Leitura.query.filter_by(
            pedido_id=pedido.id,
            idempotency_key=idempotency_key,
        ).first()
        if previous_read is not None:
            return replay_response(previous_read)

    if pedido.status_fluxo == "liberado":
        return read_response(
            "erro",
            "O pedido já foi liberado. Reabra-o antes de registrar novas leituras.",
            response_status=409,
        )
    if not pedido.itens:
        return read_response(
            "pedido_sem_itens",
            "Adicione peças ou aplique um conjunto antes de iniciar a separação.",
            response_status=409,
        )

    peca = Peca.query.filter((Peca.codigo_qr == codigo) | (Peca.codigo == codigo)).first()
    if peca is None:
        return read_response(
            "nao_cadastrado",
            "O conteúdo do QR Code não corresponde a nenhuma peça cadastrada.",
        )

    item = PedidoItem.query.filter_by(pedido_id=pedido.id, peca_id=peca.id).first()
    if item is None:
        leitura = Leitura(
            pedido=pedido,
            peca=peca,
            status=StatusLeitura.FORA_DO_PEDIDO,
            idempotency_key=idempotency_key,
        )
        db.session.add(leitura)
        message = f"A peça {peca.codigo} não pertence a este pedido."
        status = StatusLeitura.FORA_DO_PEDIDO
    else:
        leituras_sucesso = Leitura.query.filter_by(
            pedido_id=pedido.id,
            peca_id=peca.id,
            status=StatusLeitura.SUCESSO,
        ).count()
        quantidade_validada = min(
            item.quantidade_reconciliada
            + max(leituras_sucesso - item.leituras_referencia_reconciliacao, 0),
            item.quantidade_necessaria,
        )

        if quantidade_validada >= item.quantidade_necessaria:
            status = StatusLeitura.DUPLICADA
            message = f"A peça {peca.codigo} já foi separada na quantidade necessária para este pedido."
        else:
            status = StatusLeitura.SUCESSO
            message = f"Peça {peca.codigo} validada com sucesso para o pedido."

        leitura = Leitura(
            pedido=pedido,
            peca=peca,
            status=status,
            idempotency_key=idempotency_key,
        )
        db.session.add(leitura)

    try:
        db.session.flush()
        if status == StatusLeitura.SUCESSO and pedido.progresso()["status"] == "finalizado":
            pedido.status_fluxo = "aguardando_conferencia"
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if idempotency_key:
            previous_read = Leitura.query.filter_by(
                pedido_id=pedido.id,
                idempotency_key=idempotency_key,
            ).first()
            if previous_read is not None:
                return replay_response(previous_read)
        raise

    return read_response(status, message, peca)


def _pedido_liberado(pedido):
    if pedido.status_fluxo == "liberado":
        flash("O pedido está liberado. Reabra-o antes de alterar os itens.", "error")
        return True
    return False


def _atualizar_estado_separacao(pedido):
    if pedido.progresso()["status"] == "finalizado":
        pedido.status_fluxo = "aguardando_conferencia"
    else:
        pedido.status_fluxo = "separacao"


@pedidos_bp.route("/<int:pedido_id>/conferencia", methods=["GET", "POST"], endpoint="conferencia")
def conferencia(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.status_fluxo == "liberado":
        flash("Este pedido já está liberado para expedição.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if pedido.progresso()["status"] != "finalizado":
        flash("A conferência só pode ser feita quando todas as quantidades estiverem separadas.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    if pedido.status_fluxo not in ("aguardando_conferencia", "correcao"):
        flash("O pedido ainda não está disponível para conferência.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    if request.method == "GET":
        return render_template(
            "pedidos/conferencia.html",
            pedido=pedido,
            progresso_por_item=pedido.progresso_por_item(),
        )

    conferente = request.form.get("conferente", "").strip()
    if not conferente or len(conferente) > 100:
        flash("Informe o nome do conferente (até 100 caracteres).", "error")
        return render_template(
            "pedidos/conferencia.html",
            pedido=pedido,
            progresso_por_item=pedido.progresso_por_item(),
        )

    resultados = []
    divergencias = False
    for item in pedido.itens:
        try:
            quantidade_encontrada = int(request.form.get(f"quantidade_{item.id}", ""))
        except ValueError:
            flash(f"Informe a quantidade física encontrada para a peça {item.peca.codigo}.", "error")
            return render_template(
                "pedidos/conferencia.html",
                pedido=pedido,
                progresso_por_item=pedido.progresso_por_item(),
            )
        if quantidade_encontrada < 0:
            flash("A quantidade encontrada não pode ser negativa.", "error")
            return render_template(
                "pedidos/conferencia.html",
                pedido=pedido,
                progresso_por_item=pedido.progresso_por_item(),
            )

        motivo = request.form.get(f"motivo_{item.id}", "").strip()
        diverge = quantidade_encontrada != item.quantidade_necessaria
        if diverge and not motivo:
            flash(f"Informe o motivo da divergência da peça {item.peca.codigo}.", "error")
            return render_template(
                "pedidos/conferencia.html",
                pedido=pedido,
                progresso_por_item=pedido.progresso_por_item(),
            )
        if len(motivo) > 500:
            flash("O motivo da divergência deve ter no máximo 500 caracteres.", "error")
            return render_template(
                "pedidos/conferencia.html",
                pedido=pedido,
                progresso_por_item=pedido.progresso_por_item(),
            )

        divergencias = divergencias or diverge
        resultados.append((item, quantidade_encontrada, motivo or None))

    tentativa = Conferencia(
        pedido_id=pedido.id,
        conferente=conferente,
        resultado="reprovada" if divergencias else "aprovada",
    )
    db.session.add(tentativa)
    db.session.flush()

    for item, quantidade_encontrada, motivo in resultados:
        db.session.add(
            ConferenciaItem(
                conferencia_id=tentativa.id,
                pedido_item_id=item.id,
                codigo_peca=item.peca.codigo,
                descricao_peca=item.peca.descricao,
                quantidade_necessaria=item.quantidade_necessaria,
                quantidade_encontrada=quantidade_encontrada,
                motivo_divergencia=motivo,
            )
        )
        if divergencias:
            item.quantidade_reconciliada = min(quantidade_encontrada, item.quantidade_necessaria)
            item.leituras_referencia_reconciliacao = Leitura.query.filter_by(
                pedido_id=pedido.id,
                peca_id=item.peca_id,
                status=StatusLeitura.SUCESSO,
            ).count()

    pedido.status_fluxo = "correcao" if divergencias else "liberado"
    db.session.commit()

    if divergencias:
        flash("Conferência reprovada. Corrija as divergências e faça uma nova conferência.", "error")
    else:
        flash("Conferência aprovada. Pedido liberado para expedição.", "success")
    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/reabrir", methods=["POST"], endpoint="reabrir")
def reabrir(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.status_fluxo != "liberado":
        flash("Somente pedidos liberados podem ser reabertos.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    for item in pedido.itens:
        item.quantidade_reconciliada = 0
        item.leituras_referencia_reconciliacao = Leitura.query.filter_by(
            pedido_id=pedido.id,
            peca_id=item.peca_id,
            status=StatusLeitura.SUCESSO,
        ).count()
    pedido.status_fluxo = "separacao"
    db.session.commit()
    flash("Pedido reaberto. Será necessário refazer a separação e a conferência.", "success")
    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route(
    "/<int:pedido_id>/conjuntos/adicionar",
    methods=["POST"],
    endpoint="adicionar_conjunto",
)
def adicionar_conjunto(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.status_fluxo != "separacao" or pedido.leituras or pedido.conferencias:
        flash("Conjuntos só podem ser aplicados antes de qualquer leitura ou conferência.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    try:
        conjunto_id = int(request.form.get("conjunto_id", ""))
        quantidade = int(request.form.get("quantidade", "1"))
    except ValueError:
        flash("Selecione um conjunto e informe uma quantidade inteira positiva.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if quantidade < 1:
        flash("A quantidade deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    conjunto = Conjunto.query.get_or_404(conjunto_id)
    try:
        itens_expandidos = conjunto.expandir_pecas(quantidade)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if not itens_expandidos:
        flash(f"O conjunto {conjunto.codigo} não possui peças para adicionar ao pedido.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    db.session.add(
        PedidoConjunto(
            pedido_id=pedido.id,
            conjunto_id=conjunto.id,
            codigo_conjunto=conjunto.codigo,
            descricao_conjunto=conjunto.descricao,
            quantidade=quantidade,
        )
    )
    for peca_id, quantidade_peca in itens_expandidos.items():
        item = PedidoItem.query.filter_by(pedido_id=pedido.id, peca_id=peca_id).first()
        if item:
            item.quantidade_necessaria += quantidade_peca
        else:
            db.session.add(
                PedidoItem(
                    pedido_id=pedido.id,
                    peca_id=peca_id,
                    quantidade_necessaria=quantidade_peca,
                )
            )

    try:
        db.session.commit()
        flash(
            f"Composição de {quantidade} unidade(s) do conjunto {conjunto.codigo} aplicada ao pedido.",
            "success",
        )
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível aplicar a composição do conjunto ao pedido.", "error")
    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/itens/adicionar", methods=["POST"], endpoint="adicionar_item")
def adicionar_item(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if _pedido_liberado(pedido):
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    try:
        peca_id = int(request.form.get("peca_id", ""))
        quantidade = int(request.form.get("quantidade_necessaria", "1"))
    except ValueError:
        flash("Selecione uma peça e informe uma quantidade inteira positiva.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    if peca_id < 1:
        flash("Selecione uma peça para adicionar ao pedido.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if quantidade < 1:
        flash("A quantidade deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    peca = Peca.query.get_or_404(peca_id)
    item = PedidoItem.query.filter_by(pedido_id=pedido.id, peca_id=peca.id).first()
    if item:
        item.quantidade_necessaria += quantidade
    else:
        db.session.add(PedidoItem(pedido_id=pedido.id, peca_id=peca.id, quantidade_necessaria=quantidade))

    try:
        db.session.flush()
        _atualizar_estado_separacao(pedido)
        db.session.commit()
        flash("Item adicionado ao pedido com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao adicionar item ao pedido.", "error")

    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/itens/editar/<int:item_id>", methods=["POST"], endpoint="editar_item")
def editar_item(pedido_id, item_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if _pedido_liberado(pedido):
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    item = PedidoItem.query.filter_by(id=item_id, pedido_id=pedido.id).first_or_404()
    try:
        quantidade = int(request.form.get("quantidade_necessaria", ""))
    except ValueError:
        flash("A quantidade deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if quantidade < 1:
        flash("A quantidade deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    item.quantidade_necessaria = quantidade
    try:
        db.session.flush()
        _atualizar_estado_separacao(pedido)
        db.session.commit()
        flash("Quantidade atualizada com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao atualizar quantidade.", "error")

    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/itens/remover/<int:item_id>", methods=["POST"], endpoint="remover_item")
def remover_item(pedido_id, item_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if _pedido_liberado(pedido):
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    item = PedidoItem.query.filter_by(id=item_id, pedido_id=pedido.id).first_or_404()
    db.session.delete(item)
    try:
        db.session.flush()
        _atualizar_estado_separacao(pedido)
        db.session.commit()
        flash("Item removido do pedido com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao remover item do pedido.", "error")

    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


listar_pedidos = listar
adicionar_pedido = novo
editar_pedido = editar
excluir_pedido = apagar
detalhes_pedido = detalhe
listar_pecas_pedido = detalhe
adicionar_item_pedido = adicionar_item
