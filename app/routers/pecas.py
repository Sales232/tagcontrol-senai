from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.instance.models import Peca

pecas_bp = Blueprint("pecas", __name__, url_prefix="/pecas")


@pecas_bp.route("/", methods=["GET"], endpoint="listar")
def listar():
    pecas = Peca.query.order_by(Peca.codigo).all()
    return render_template("pecas/listar.html", pecas=pecas)


@pecas_bp.route("/novo", methods=["GET", "POST"], endpoint="novo")
def novo():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        codigo_barras = request.form.get("codigo_barras", "").strip()
        peca = Peca(codigo=codigo, descricao=descricao, codigo_barras=codigo_barras)

        if not codigo or not descricao or not codigo_barras:
            flash("Todos os campos são obrigatórios.", "error")
            return render_template("pecas/form.html", peca=peca)

        db.session.add(peca)
        try:
            db.session.commit()
            flash("Peça adicionada com sucesso!", "success")
            return redirect(url_for("pecas.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma peça com esse código ou código de barras.", "error")
            return render_template("pecas/form.html", peca=peca)

    return render_template("pecas/form.html", peca=None)


@pecas_bp.route("/editar/<int:peca_id>", methods=["GET", "POST"], endpoint="editar")
def editar(peca_id):
    peca = Peca.query.get_or_404(peca_id)

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        codigo_barras = request.form.get("codigo_barras", "").strip()
        if not codigo or not descricao or not codigo_barras:
            flash("Todos os campos são obrigatórios.", "error")
            return render_template(
                "pecas/form.html",
                peca=Peca(id=peca.id, codigo=codigo, descricao=descricao, codigo_barras=codigo_barras),
            )

        peca.codigo = codigo
        peca.descricao = descricao
        peca.codigo_barras = codigo_barras

        try:
            db.session.commit()
            flash("Peça atualizada com sucesso!", "success")
            return redirect(url_for("pecas.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma peça com esse código ou código de barras.", "error")
            return render_template(
                "pecas/form.html",
                peca=Peca(id=peca_id, codigo=codigo, descricao=descricao, codigo_barras=codigo_barras),
            )

    return render_template("pecas/form.html", peca=peca)


@pecas_bp.route("/apagar/<int:peca_id>", methods=["POST"], endpoint="apagar")
def apagar(peca_id):
    peca = Peca.query.get_or_404(peca_id)
    if peca.conjuntos_assoc or peca.pedidos_assoc or peca.leituras:
        flash("Não é possível apagar uma peça associada a conjuntos, pedidos ou leituras.", "error")
        return redirect(url_for("pecas.listar"))

    db.session.delete(peca)
    try:
        db.session.commit()
        flash("Peça excluída com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível excluir a peça por causa de registros relacionados.", "error")

    return redirect(url_for("pecas.listar"))


adicionar_peca = novo
excluir_peca = apagar
adicionar = novo
"""Compatibilidade com nomes antigos de funções já existentes no projeto."""
