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
        codigo_qr = request.form.get("codigo_qr", "").strip()
        peca = Peca(codigo=codigo, descricao=descricao, codigo_qr=codigo_qr)

        if not codigo or not descricao or not codigo_qr:
            flash("Todos os campos são obrigatórios.", "error")
            return render_template("pecas/form.html", peca=peca, is_new_piece=True)

        db.session.add(peca)
        try:
            db.session.commit()
            flash("Peça adicionada com sucesso!", "success")
            return redirect(url_for("pecas.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma peça com esse código ou QR Code.", "error")
            return render_template("pecas/form.html", peca=peca, is_new_piece=True)

    return render_template("pecas/form.html", peca=None, is_new_piece=True)


@pecas_bp.route("/editar/<int:peca_id>", methods=["GET", "POST"], endpoint="editar")
def editar(peca_id):
    peca = Peca.query.get_or_404(peca_id)

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        descricao = request.form.get("descricao", "").strip()
        codigo_qr = request.form.get("codigo_qr", "").strip()
        if not codigo or not descricao or not codigo_qr:
            flash("Todos os campos são obrigatórios.", "error")
            return render_template(
                "pecas/form.html",
                peca=Peca(id=peca.id, codigo=codigo, descricao=descricao, codigo_qr=codigo_qr),
                is_new_piece=False,
            )

        peca.codigo = codigo
        peca.descricao = descricao
        peca.codigo_qr = codigo_qr

        try:
            db.session.commit()
            flash("Peça atualizada com sucesso!", "success")
            return redirect(url_for("pecas.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma peça com esse código ou QR Code.", "error")
            return render_template(
                "pecas/form.html",
                peca=Peca(id=peca_id, codigo=codigo, descricao=descricao, codigo_qr=codigo_qr),
                is_new_piece=False,
            )

    return render_template("pecas/form.html", peca=peca, is_new_piece=False)


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
