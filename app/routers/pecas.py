import io

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.instance.models import Peca

pecas_bp = Blueprint("pecas", __name__, url_prefix="/pecas")


def _codigo_valido(codigo):
    return (
        bool(codigo)
        and len(codigo) <= 50
        and codigo == codigo.strip()
        and not any(ord(character) < 32 or ord(character) == 127 for character in codigo)
    )


@pecas_bp.route("/", methods=["GET"], endpoint="listar")
def listar():
    pecas = Peca.query.order_by(Peca.codigo).all()
    return render_template("pecas/listar.html", pecas=pecas)


@pecas_bp.route("/novo", methods=["GET", "POST"], endpoint="novo")
def novo():
    if request.method == "POST":
        codigo = request.form.get("codigo", "")
        descricao = request.form.get("descricao", "").strip()
        codigo_normalizado = codigo.strip()
        peca = Peca(codigo=codigo_normalizado, descricao=descricao)

        if not _codigo_valido(codigo) or not descricao:
            flash("Informe um código interno válido (até 50 caracteres) e a descrição.", "error")
            return render_template("pecas/form.html", peca=peca, is_new_piece=True)

        db.session.add(peca)
        try:
            db.session.commit()
            flash("Peça adicionada com sucesso!", "success")
            return redirect(url_for("pecas.etiqueta", peca_id=peca.id))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma peça com esse código interno.", "error")
            return render_template("pecas/form.html", peca=peca, is_new_piece=True)

    return render_template("pecas/form.html", peca=None, is_new_piece=True)


@pecas_bp.route("/editar/<int:peca_id>", methods=["GET", "POST"], endpoint="editar")
def editar(peca_id):
    peca = Peca.query.get_or_404(peca_id)

    if request.method == "POST":
        codigo_anterior = peca.codigo
        codigo = request.form.get("codigo", "")
        descricao = request.form.get("descricao", "").strip()
        codigo_normalizado = codigo.strip()
        if not _codigo_valido(codigo) or not descricao:
            flash("Informe um código interno válido (até 50 caracteres) e a descrição.", "error")
            return render_template(
                "pecas/form.html",
                peca=Peca(id=peca.id, codigo=codigo_normalizado, descricao=descricao),
                is_new_piece=False,
            )

        peca.codigo = codigo_normalizado
        peca.descricao = descricao

        try:
            db.session.commit()
            flash("Peça atualizada com sucesso!", "success")
            if codigo_normalizado != codigo_anterior:
                flash("O código interno mudou; reimprima a etiqueta para atualizar o QR Code.", "warning")
            return redirect(url_for("pecas.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe uma peça com esse código interno.", "error")
            return render_template(
                "pecas/form.html",
                peca=Peca(id=peca_id, codigo=codigo_normalizado, descricao=descricao),
                is_new_piece=False,
            )

    return render_template("pecas/form.html", peca=peca, is_new_piece=False)


@pecas_bp.route("/<int:peca_id>/etiqueta", methods=["GET"], endpoint="etiqueta")
def etiqueta(peca_id):
    peca = Peca.query.get_or_404(peca_id)
    return render_template("pecas/etiqueta.html", peca=peca)


@pecas_bp.route("/<int:peca_id>/qr.svg", methods=["GET"], endpoint="qr_svg")
def qr_svg(peca_id):
    import qrcode
    import qrcode.image.svg

    peca = Peca.query.get_or_404(peca_id)
    qr = qrcode.QRCode(version=None, box_size=8, border=4)
    qr.add_data(peca.codigo)
    qr.make(fit=True)
    image = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    output = io.BytesIO()
    image.save(output)
    response = Response(output.getvalue(), mimetype="image/svg+xml")
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


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