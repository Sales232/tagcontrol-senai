from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.instance.models import Conjunto, ConjuntoPeca, Peca

conjuntos_bp = Blueprint("conjuntos", __name__, url_prefix="/conjuntos")


@conjuntos_bp.route("/", methods=["GET"], endpoint="listar")
def listar():
    conjuntos = Conjunto.query.order_by(Conjunto.codigo).all()
    return render_template("conjuntos/listar.html", conjuntos=conjuntos)


@conjuntos_bp.route("/novo", methods=["GET", "POST"], endpoint="novo")
def novo():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        descricao = request.form.get("descricao", "").strip()

        if not codigo or not descricao:
            flash("Código e descrição são obrigatórios.", "error")
            return render_template("conjuntos/form.html", conjunto=None)

        conjunto = Conjunto(codigo=codigo, descricao=descricao)
        db.session.add(conjunto)
        try:
            db.session.commit()
            flash("Conjunto adicionado com sucesso!", "success")
            return redirect(url_for("conjuntos.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Erro ao adicionar conjunto.", "error")

    return render_template("conjuntos/form.html", conjunto=None)


@conjuntos_bp.route("/editar/<int:conjunto_id>", methods=["GET", "POST"], endpoint="editar")
def editar(conjunto_id):
    conjunto = Conjunto.query.get_or_404(conjunto_id)

    if request.method == "POST":
        conjunto.codigo = request.form.get("codigo", "").strip()
        conjunto.descricao = request.form.get("descricao", "").strip()

        try:
            db.session.commit()
            flash("Conjunto atualizado com sucesso!", "success")
            return redirect(url_for("conjuntos.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Erro ao atualizar conjunto.", "error")

    return render_template("conjuntos/form.html", conjunto=conjunto)


@conjuntos_bp.route("/apagar/<int:conjunto_id>", methods=["POST"], endpoint="apagar")
def apagar(conjunto_id):
    conjunto = Conjunto.query.get_or_404(conjunto_id)
    db.session.delete(conjunto)
    try:
        db.session.commit()
        flash("Conjunto excluído com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao excluir conjunto.", "error")

    return redirect(url_for("conjuntos.listar"))


@conjuntos_bp.route("/<int:conjunto_id>/detalhe", methods=["GET"], endpoint="detalhe")
def detalhe(conjunto_id):
    conjunto = Conjunto.query.get_or_404(conjunto_id)
    pecas_disponiveis = Peca.query.filter(~Peca.id.in_([assoc.peca_id for assoc in conjunto.pecas_assoc])).all()
    return render_template("conjuntos/detalhe.html", conjunto=conjunto, pecas_disponiveis=pecas_disponiveis)


@conjuntos_bp.route("/<int:conjunto_id>/pecas/adicionar", methods=["POST"], endpoint="adicionar_peca")
def adicionar_peca(conjunto_id):
    conjunto = Conjunto.query.get_or_404(conjunto_id)
    peca_id = request.form.get("peca_id")
    if not peca_id:
        flash("Selecione uma peça válida.", "error")
        return redirect(url_for("conjuntos.detalhe", conjunto_id=conjunto.id))

    quantidade = int(request.form.get("quantidade", "1") or 1)
    if quantidade < 1:
        quantidade = 1

    peca = Peca.query.get_or_404(int(peca_id))
    assoc = ConjuntoPeca.query.filter_by(conjunto_id=conjunto.id, peca_id=peca.id).first()
    if assoc:
        assoc.quantidade += quantidade
    else:
        db.session.add(ConjuntoPeca(conjunto_id=conjunto.id, peca_id=peca.id, quantidade=quantidade))

    try:
        db.session.commit()
        flash("Peça adicionada ao conjunto com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao adicionar peça ao conjunto.", "error")

    return redirect(url_for("conjuntos.detalhe", conjunto_id=conjunto.id))


@conjuntos_bp.route("/<int:conjunto_id>/pecas/editar/<int:assoc_id>", methods=["POST"], endpoint="editar_peca")
def editar_peca(conjunto_id, assoc_id):
    conjunto = Conjunto.query.get_or_404(conjunto_id)
    assoc = ConjuntoPeca.query.get_or_404(assoc_id)
    quantidade = int(request.form.get("quantidade", assoc.quantidade) or assoc.quantidade)
    if quantidade < 1:
        quantidade = 1

    assoc.quantidade = quantidade
    try:
        db.session.commit()
        flash("Quantidade atualizada com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao atualizar quantidade.", "error")

    return redirect(url_for("conjuntos.detalhe", conjunto_id=conjunto.id))


@conjuntos_bp.route("/<int:conjunto_id>/pecas/remover/<int:assoc_id>", methods=["POST"], endpoint="remover_peca")
def remover_peca(conjunto_id, assoc_id):
    conjunto = Conjunto.query.get_or_404(conjunto_id)
    assoc = ConjuntoPeca.query.get_or_404(assoc_id)
    db.session.delete(assoc)
    try:
        db.session.commit()
        flash("Peça removida do conjunto com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao remover peça do conjunto.", "error")

    return redirect(url_for("conjuntos.detalhe", conjunto_id=conjunto.id))


listar_conjuntos = listar
adicionar_conjunto = novo
editar_conjunto = editar
excluir_conjunto = apagar
listar_pecas_conjunto = detalhe
adicionar_peca_conjunto = adicionar_peca
editar_peca_conjunto = editar_peca
excluir_peca_conjunto = remover_peca

