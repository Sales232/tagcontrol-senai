from __future__ import annotations

from app import db
from app.instance.models import Leitura, Pedido, PedidoItem, Peca, StatusLeitura


DEMO_PECAS = (
    {
        "codigo": "232323",
        "descricao": "Parafuso M8 x 30",
    },
    {
        "codigo": "232021",
        "descricao": "Porca M8",
    },
    {
        "codigo": "232102",
        "descricao": "Arruela M8",
    },
    {
        "codigo": "210211",
        "descricao": "Terminal elétrico",
    },
)

DEMO_PEDIDOS = (
    {
        "codigo": "PED-1001",
        "itens": (
            {"peca_codigo": "PEC-001", "quantidade_necessaria": 2},
            {"peca_codigo": "PEC-002", "quantidade_necessaria": 1},
            {"peca_codigo": "PEC-003", "quantidade_necessaria": 3},
        ),
        "leituras": (
            {"peca_codigo": "PEC-001", "status": StatusLeitura.SUCESSO},
            {"peca_codigo": "PEC-001", "status": StatusLeitura.DUPLICADA},
            {"peca_codigo": "PEC-004", "status": StatusLeitura.FORA_DO_PEDIDO},
        ),
    },
)


def _get_or_create_peca(codigo: str, descricao: str) -> Peca:
    peca = Peca.query.filter_by(codigo=codigo).first()
    if peca is None:
        peca = Peca(codigo=codigo, descricao=descricao)
        db.session.add(peca)
        db.session.flush()
    else:
        peca.descricao = descricao
    return peca


def _get_or_create_pedido(codigo: str) -> Pedido:
    pedido = Pedido.query.filter_by(codigo=codigo).first()
    if pedido is None:
        pedido = Pedido(codigo=codigo)
        db.session.add(pedido)
        db.session.flush()
    return pedido


def _get_or_create_item(pedido: Pedido, peca: Peca, quantidade_necessaria: int) -> PedidoItem:
    item = PedidoItem.query.filter_by(pedido_id=pedido.id, peca_id=peca.id).first()
    if item is None:
        item = PedidoItem(
            pedido_id=pedido.id,
            peca_id=peca.id,
            quantidade_necessaria=quantidade_necessaria,
        )
        db.session.add(item)
        db.session.flush()
    else:
        item.quantidade_necessaria = quantidade_necessaria
    return item


def seed_demo_data() -> dict[str, object]:
    """Create a reusable demo dataset for the MVP and keep it idempotent."""

    pecas: dict[str, Peca] = {}
    for dados in DEMO_PECAS:
        peca = _get_or_create_peca(
            codigo=dados["codigo"],
            descricao=dados["descricao"],
        )
        pecas[dados["codigo"]] = peca

    pedidos: dict[str, Pedido] = {}
    for dados in DEMO_PEDIDOS:
        pedido = _get_or_create_pedido(dados["codigo"])
        pedidos[dados["codigo"]] = pedido

        for item in dados["itens"]:
            peca = pecas[item["peca_codigo"]]
            _get_or_create_item(
                pedido=pedido,
                peca=peca,
                quantidade_necessaria=item["quantidade_necessaria"],
            )

        for leitura in dados["leituras"]:
            peca = pecas[leitura["peca_codigo"]]
            leitura_existente = Leitura.query.filter_by(
                pedido_id=pedido.id,
                peca_id=peca.id,
                status=leitura["status"],
            ).first()
            if leitura_existente is None:
                db.session.add(
                    Leitura(
                        pedido_id=pedido.id,
                        peca_id=peca.id,
                        status=leitura["status"],
                    )
                )

    db.session.commit()

    return {
        "pecas": pecas,
        "pedidos": pedidos,
    }