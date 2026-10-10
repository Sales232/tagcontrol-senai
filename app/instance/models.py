import datetime
import enum

from app import db

class StatusLeitura(str, enum.Enum):
    """Usar Enum em vez de string livre: o banco recusa um valor
    fora dessas três opções, em vez de aceitar qualquer texto e o
    bug só aparecer quando alguém filtrar por um status errado."""
    SUCESSO = "sucesso"
    DUPLICADA = "duplicada"
    FORA_DO_PEDIDO = "fora_do_pedido"


class Peca(db.Model):
    __tablename__ = "peca"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    codigo: db.Mapped[str] = db.mapped_column(db.String(50), unique=True, index=True)
    descricao: db.Mapped[str] = db.mapped_column(db.String(200))
    codigo_barras: db.Mapped[str] = db.mapped_column(db.String(50), unique=True, index=True)

    conjuntos_assoc: db.Mapped[list["ConjuntoPeca"]] = db.relationship(back_populates="peca")
    pedidos_assoc: db.Mapped[list["PedidoItem"]] = db.relationship(back_populates="peca")
    leituras: db.Mapped[list["Leitura"]] = db.relationship(back_populates="peca")


class Conjunto(db.Model):
    __tablename__ = "conjunto"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    codigo: db.Mapped[str] = db.mapped_column(db.String(50), unique=True, index=True)
    descricao: db.Mapped[str] = db.mapped_column(db.String(200))

    pecas_assoc: db.Mapped[list["ConjuntoPeca"]] = db.relationship(
        back_populates="conjunto",
        cascade="all, delete-orphan",
    )


class ConjuntoPeca(db.Model):
    __tablename__ = "conjunto_peca"
    __table_args__ = (
        db.UniqueConstraint("conjunto_id", "peca_id", name="uq_conjunto_peca"),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    conjunto_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("conjunto.id"))
    peca_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("peca.id"))
    quantidade: db.Mapped[int]

    conjunto: db.Mapped["Conjunto"] = db.relationship(back_populates="pecas_assoc")
    peca: db.Mapped["Peca"] = db.relationship(back_populates="conjuntos_assoc")


class Pedido(db.Model):
    __tablename__ = "pedido"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    codigo: db.Mapped[str] = db.mapped_column(db.String(50), unique=True, index=True)

    itens: db.Mapped[list["PedidoItem"]] = db.relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
    )
    leituras: db.Mapped[list["Leitura"]] = db.relationship(back_populates="pedido")

    def progresso(self) -> dict[str, int | float | str]:
        total_necessario = sum(item.quantidade_necessaria for item in self.itens)
        if total_necessario == 0:
            return {
                "total_necessario": 0,
                "quantidade_validada": 0,
                "percentual": 0.0,
                "status": "sem_itens",
            }

        contagem_sucessos: dict[int, int] = {}
        for leitura in self.leituras:
            if leitura.status == StatusLeitura.SUCESSO:
                contagem_sucessos[leitura.peca_id] = contagem_sucessos.get(leitura.peca_id, 0) + 1

        quantidade_validada = 0
        for item in self.itens:
            quantidade_validada += min(contagem_sucessos.get(item.peca_id, 0), item.quantidade_necessaria)

        percentual = round((quantidade_validada / total_necessario) * 100, 2)
        return {
            "total_necessario": total_necessario,
            "quantidade_validada": quantidade_validada,
            "percentual": percentual,
            "status": "finalizado" if quantidade_validada == total_necessario else "em_andamento",
        }

    def progresso_por_item(self) -> list[dict[str, object]]:
        contagem_sucessos: dict[int, int] = {}
        for leitura in self.leituras:
            if leitura.status == StatusLeitura.SUCESSO:
                contagem_sucessos[leitura.peca_id] = contagem_sucessos.get(leitura.peca_id, 0) + 1

        itens = []
        for item in self.itens:
            quantidade_validada = min(contagem_sucessos.get(item.peca_id, 0), item.quantidade_necessaria)
            itens.append(
                {
                    "peca": item.peca,
                    "quantidade_necessaria": item.quantidade_necessaria,
                    "quantidade_validada": quantidade_validada,
                    "percentual": round((quantidade_validada / item.quantidade_necessaria) * 100, 2) if item.quantidade_necessaria else 0.0,
                }
            )
        return itens


class PedidoItem(db.Model):
    __tablename__ = "pedido_item"
    __table_args__ = (
        db.UniqueConstraint("pedido_id", "peca_id", name="uq_pedido_peca"),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"))
    peca_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("peca.id"))
    quantidade_necessaria: db.Mapped[int] = db.mapped_column(default=1)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="itens")
    peca: db.Mapped["Peca"] = db.relationship(back_populates="pedidos_assoc")


class Leitura(db.Model):
    __tablename__ = "leitura"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"))
    peca_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("peca.id"))
    status: db.Mapped[StatusLeitura] = db.mapped_column(db.Enum(StatusLeitura))
    timestamp: db.Mapped[datetime.datetime] = db.mapped_column(default=datetime.datetime.utcnow)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="leituras")
    peca: db.Mapped["Peca"] = db.relationship(back_populates="leituras")
