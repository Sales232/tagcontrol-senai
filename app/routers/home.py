from flask import Blueprint, render_template

from app.instance.models import Conjunto, Pedido, Peca


home_bp = Blueprint("home", __name__)


@home_bp.route("/", methods=["GET"], endpoint="index")
def index():
    return render_template(
        "home.html",
        piece_count=Peca.query.count(),
        set_count=Conjunto.query.count(),
        order_count=Pedido.query.count(),
        active_order_count=Pedido.query.filter(Pedido.status_fluxo != "expedido").count(),
    )
