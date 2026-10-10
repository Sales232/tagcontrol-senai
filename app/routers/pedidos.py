from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.instance.models import Leitura, Pedido, PedidoItem, Peca, StatusLeitura

pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")


@pedidos_bp.route("/", methods=["GET"], endpoint="listar")
def listar():
    pedidos = Pedido.query.order_by(Pedido.codigo).all()
    return render_template("pedidos/listar.html", pedidos=pedidos)


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
    return render_template(
        "pedidos/detalhe.html",
        pedido=pedido,
        pecas_disponiveis=pecas_disponiveis,
        progresso=pedido.progresso(),
        progresso_por_item=pedido.progresso_por_item(),
    )


@pedidos_bp.route("/<int:pedido_id>/scanner", methods=["GET"], endpoint="scanner")
def scanner(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template("pedidos/scanner.html", pedido=pedido, progresso=pedido.progresso())


@pedidos_bp.route("/<int:pedido_id>/scanner/validar", methods=["POST"], endpoint="validar_codigo")
def validar_codigo(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    payload = request.get_json(silent=True) if request.is_json else {}
    if not payload:
        payload = request.form.to_dict()

    codigo = str(payload.get("codigo") or payload.get("codigo_barras") or payload.get("barcode") or "").strip()
    if not codigo:
        return jsonify({
            "status": "erro",
            "message": "Código de barras não informado.",
            "progress": pedido.progresso(),
        }), 400

    peca = Peca.query.filter((Peca.codigo_barras == codigo) | (Peca.codigo == codigo)).first()
    if peca is None:
        return jsonify({
            "status": "fora_do_pedido",
            "message": "Código não corresponde a nenhuma peça cadastrada.",
            "progress": pedido.progresso(),
        })

    item = PedidoItem.query.filter_by(pedido_id=pedido.id, peca_id=peca.id).first()
    if item is None:
        leitura = Leitura(
            pedido_id=pedido.id,
            peca_id=peca.id,
            status=StatusLeitura.FORA_DO_PEDIDO,
        )
        db.session.add(leitura)
        db.session.commit()
        return jsonify({
            "status": StatusLeitura.FORA_DO_PEDIDO.value,
            "message": f"A peça {peca.codigo} não pertence a este pedido.",
            "peca": {"id": peca.id, "codigo": peca.codigo, "descricao": peca.descricao},
            "progress": pedido.progresso(),
        })

    leituras_sucesso = Leitura.query.filter_by(
        pedido_id=pedido.id,
        peca_id=peca.id,
        status=StatusLeitura.SUCESSO,
    ).count()

    if leituras_sucesso >= item.quantidade_necessaria:
        status = StatusLeitura.DUPLICADA
        message = f"A peça {peca.codigo} já foi separada na quantidade necessária para este pedido."
    else:
        status = StatusLeitura.SUCESSO
        message = f"Peça {peca.codigo} validada com sucesso para o pedido."

    leitura = Leitura(
        pedido_id=pedido.id,
        peca_id=peca.id,
        status=status,
    )
    db.session.add(leitura)
    db.session.commit()

    return jsonify({
        "status": status.value,
        "message": message,
        "peca": {"id": peca.id, "codigo": peca.codigo, "descricao": peca.descricao},
        "progress": pedido.progresso(),
    })


@pedidos_bp.route("/<int:pedido_id>/itens/adicionar", methods=["POST"], endpoint="adicionar_item")
def adicionar_item(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
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
        db.session.commit()
        flash("Item adicionado ao pedido com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao adicionar item ao pedido.", "error")

    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/itens/editar/<int:item_id>", methods=["POST"], endpoint="editar_item")
def editar_item(pedido_id, item_id):
    pedido = Pedido.query.get_or_404(pedido_id)
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
        db.session.commit()
        flash("Quantidade atualizada com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao atualizar quantidade.", "error")

    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/itens/remover/<int:item_id>", methods=["POST"], endpoint="remover_item")
def remover_item(pedido_id, item_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    item = PedidoItem.query.filter_by(id=item_id, pedido_id=pedido.id).first_or_404()
    db.session.delete(item)
    try:
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
