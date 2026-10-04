from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.instance.models import Pedido, PedidoItem, Peca

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
            return render_template("pedidos/form.html", pedido=None)

        pedido = Pedido(codigo=codigo)
        db.session.add(pedido)
        try:
            db.session.commit()
            flash("Pedido adicionado com sucesso!", "success")
            return redirect(url_for("pedidos.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Erro ao adicionar pedido.", "error")

    return render_template("pedidos/form.html", pedido=None)


@pedidos_bp.route("/editar/<int:pedido_id>", methods=["GET", "POST"], endpoint="editar")
def editar(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    if request.method == "POST":
        pedido.codigo = request.form.get("codigo", "").strip()
        try:
            db.session.commit()
            flash("Pedido atualizado com sucesso!", "success")
            return redirect(url_for("pedidos.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Erro ao atualizar pedido.", "error")

    return render_template("pedidos/form.html", pedido=pedido)


@pedidos_bp.route("/apagar/<int:pedido_id>", methods=["POST"], endpoint="apagar")
def apagar(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    db.session.delete(pedido)
    try:
        db.session.commit()
        flash("Pedido excluído com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao excluir pedido.", "error")

    return redirect(url_for("pedidos.listar"))


@pedidos_bp.route("/<int:pedido_id>/detalhe", methods=["GET"], endpoint="detalhe")
def detalhe(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    pecas_disponiveis = Peca.query.order_by(Peca.codigo).all()
    return render_template("pedidos/detalhe.html", pedido=pedido, pecas_disponiveis=pecas_disponiveis)


@pedidos_bp.route("/<int:pedido_id>/itens/adicionar", methods=["POST"], endpoint="adicionar_item")
def adicionar_item(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    peca_id = request.form.get("peca_id")
    if not peca_id:
        flash("Selecione uma peça para adicionar ao pedido.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    quantidade = int(request.form.get("quantidade_necessaria", "1") or 1)
    if quantidade < 1:
        quantidade = 1

    peca = Peca.query.get_or_404(int(peca_id))
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
    quantidade = int(request.form.get("quantidade_necessaria", item.quantidade_necessaria) or item.quantidade_necessaria)
    if quantidade < 1:
        quantidade = 1

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

