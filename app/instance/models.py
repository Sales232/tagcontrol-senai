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
    codigo_qr: db.Mapped[str] = db.mapped_column(db.String(50), unique=True, index=True)

    conjuntos_assoc: db.Mapped[list["ConjuntoPeca"]] = db.relationship(
        back_populates="peca",
        foreign_keys="ConjuntoPeca.peca_id",
    )
    pedidos_assoc: db.Mapped[list["PedidoItem"]] = db.relationship(back_populates="peca")
    leituras: db.Mapped[list["Leitura"]] = db.relationship(back_populates="peca")


class Conjunto(db.Model):
    __tablename__ = "conjunto"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    codigo: db.Mapped[str] = db.mapped_column(db.String(50), unique=True, index=True)
    descricao: db.Mapped[str] = db.mapped_column(db.String(200))

    componentes: db.Mapped[list["ConjuntoPeca"]] = db.relationship(
        back_populates="conjunto",
        foreign_keys="ConjuntoPeca.conjunto_id",
        cascade="all, delete-orphan",
        order_by="ConjuntoPeca.id",
    )

    @property
    def pecas_assoc(self) -> list["ConjuntoPeca"]:
        return [componente for componente in self.componentes if componente.peca_id is not None]

    def expandir_pecas(self, quantidade: int = 1) -> dict[int, int]:
        if quantidade < 1:
            raise ValueError("A quantidade do conjunto deve ser positiva.")

        def expandir(conjunto: "Conjunto", fator: int, caminho: set[int]) -> dict[int, int]:
            if conjunto.id in caminho:
                raise ValueError("A estrutura contém uma referência circular.")

            proximo_caminho = caminho | {conjunto.id}
            resultado: dict[int, int] = {}
            for componente in conjunto.componentes:
                quantidade_componente = fator * componente.quantidade
                if componente.peca_id is not None:
                    resultado[componente.peca_id] = (
                        resultado.get(componente.peca_id, 0) + quantidade_componente
                    )
                elif componente.subconjunto_id is not None:
                    subconjunto = componente.subconjunto
                    for peca_id, quantidade_peca in expandir(
                        subconjunto,
                        quantidade_componente,
                        proximo_caminho,
                    ).items():
                        resultado[peca_id] = resultado.get(peca_id, 0) + quantidade_peca
                else:
                    raise ValueError("A composição possui um componente sem peça ou subconjunto.")
            return resultado

        return expandir(self, quantidade, set())

class ConjuntoPeca(db.Model):
    __tablename__ = "conjunto_peca"
    __table_args__ = (
        db.UniqueConstraint("conjunto_id", "peca_id", name="uq_conjunto_peca"),
        db.UniqueConstraint("conjunto_id", "subconjunto_id", name="uq_conjunto_subconjunto"),
        db.CheckConstraint(
            "(peca_id IS NOT NULL AND subconjunto_id IS NULL) OR "
            "(peca_id IS NULL AND subconjunto_id IS NOT NULL)",
            name="ck_conjunto_componente_tipo",
        ),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    conjunto_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("conjunto.id"))
    peca_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("peca.id"), nullable=True)
    subconjunto_id: db.Mapped[int] = db.mapped_column(
        db.ForeignKey("conjunto.id", ondelete="RESTRICT"),
        nullable=True,
    )
    quantidade: db.Mapped[int]

    conjunto: db.Mapped["Conjunto"] = db.relationship(
        back_populates="componentes",
        foreign_keys=[conjunto_id],
    )
    peca: db.Mapped["Peca"] = db.relationship(
        back_populates="conjuntos_assoc",
        foreign_keys=[peca_id],
    )
    subconjunto: db.Mapped["Conjunto"] = db.relationship(foreign_keys=[subconjunto_id])


class Pedido(db.Model):
    __tablename__ = "pedido"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    codigo: db.Mapped[str] = db.mapped_column(db.String(50), unique=True, index=True)
    status_fluxo: db.Mapped[str] = db.mapped_column(db.String(30), default="separacao", nullable=False)

    itens: db.Mapped[list["PedidoItem"]] = db.relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
    )
    leituras: db.Mapped[list["Leitura"]] = db.relationship(back_populates="pedido")
    conferencias: db.Mapped[list["Conferencia"]] = db.relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="Conferencia.id",
    )
    reaberturas: db.Mapped[list["PedidoReabertura"]] = db.relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="PedidoReabertura.ciclo",
    )
    composicoes: db.Mapped[list["PedidoConjunto"]] = db.relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="PedidoConjunto.id",
    )

    def quantidade_validada_item(self, item: "PedidoItem") -> int:
        leituras_sucesso = sum(
            1
            for leitura in self.leituras
            if leitura.peca_id == item.peca_id and leitura.status == StatusLeitura.SUCESSO
        )
        quantidade_atual = item.quantidade_reconciliada + max(
            leituras_sucesso - item.leituras_referencia_reconciliacao,
            0,
        )
        return min(quantidade_atual, item.quantidade_necessaria)

    def progresso(self) -> dict[str, int | float | str]:
        total_necessario = sum(item.quantidade_necessaria for item in self.itens)
        if total_necessario == 0:
            return {
                "total_necessario": 0,
                "quantidade_validada": 0,
                "percentual": 0.0,
                "status": "sem_itens",
            }

        quantidade_validada = sum(self.quantidade_validada_item(item) for item in self.itens)

        percentual = round((quantidade_validada / total_necessario) * 100, 2)
        return {
            "total_necessario": total_necessario,
            "quantidade_validada": quantidade_validada,
            "percentual": percentual,
            "status": "finalizado" if quantidade_validada == total_necessario else "em_andamento",
        }

    def progresso_por_item(self) -> list[dict[str, object]]:
        itens = []
        for item in self.itens:
            quantidade_validada = self.quantidade_validada_item(item)
            itens.append(
                {
                    "peca": item.peca,
                    "quantidade_necessaria": item.quantidade_necessaria,
                    "quantidade_validada": quantidade_validada,
                    "percentual": round((quantidade_validada / item.quantidade_necessaria) * 100, 2) if item.quantidade_necessaria else 0.0,
                }
            )
        return itens


class Conferencia(db.Model):
    __tablename__ = "conferencia"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"), nullable=False)
    ciclo: db.Mapped[int] = db.mapped_column(nullable=True)
    conferente: db.Mapped[str] = db.mapped_column(db.String(100), nullable=False)
    resultado: db.Mapped[str] = db.mapped_column(db.String(20), nullable=False)
    timestamp: db.Mapped[datetime.datetime] = db.mapped_column(default=datetime.datetime.utcnow)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="conferencias")
    itens: db.Mapped[list["ConferenciaItem"]] = db.relationship(
        back_populates="conferencia",
        cascade="all, delete-orphan",
        order_by="ConferenciaItem.id",
    )


class PedidoReabertura(db.Model):
    __tablename__ = "pedido_reabertura"
    __table_args__ = (
        db.UniqueConstraint("pedido_id", "ciclo", name="uq_pedido_reabertura_ciclo"),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"), nullable=False)
    ciclo: db.Mapped[int] = db.mapped_column(nullable=False)
    timestamp: db.Mapped[datetime.datetime] = db.mapped_column(default=datetime.datetime.utcnow)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="reaberturas")


class PedidoConjunto(db.Model):
    __tablename__ = "pedido_conjunto"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"), nullable=False)
    conjunto_id: db.Mapped[int] = db.mapped_column(
        db.ForeignKey("conjunto.id", ondelete="RESTRICT"),
        nullable=False,
    )
    codigo_conjunto: db.Mapped[str] = db.mapped_column(db.String(50), nullable=False)
    descricao_conjunto: db.Mapped[str] = db.mapped_column(db.String(200), nullable=False)
    quantidade: db.Mapped[int] = db.mapped_column(nullable=False)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="composicoes")


class ConferenciaItem(db.Model):
    __tablename__ = "conferencia_item"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    conferencia_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("conferencia.id"), nullable=False)
    pedido_item_id: db.Mapped[int] = db.mapped_column(
        db.ForeignKey("pedido_item.id", ondelete="SET NULL"),
        nullable=True,
    )
    codigo_peca: db.Mapped[str] = db.mapped_column(db.String(50), nullable=False)
    descricao_peca: db.Mapped[str] = db.mapped_column(db.String(200), nullable=False)
    quantidade_necessaria: db.Mapped[int] = db.mapped_column(nullable=False)
    quantidade_encontrada: db.Mapped[int] = db.mapped_column(nullable=False)
    motivo_divergencia: db.Mapped[str] = db.mapped_column(db.String(500), nullable=True)

    conferencia: db.Mapped["Conferencia"] = db.relationship(back_populates="itens")


class PedidoItem(db.Model):
    __tablename__ = "pedido_item"
    __table_args__ = (
        db.UniqueConstraint("pedido_id", "peca_id", name="uq_pedido_peca"),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"))
    peca_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("peca.id"))
    quantidade_necessaria: db.Mapped[int] = db.mapped_column(default=1)
    quantidade_reconciliada: db.Mapped[int] = db.mapped_column(default=0, nullable=False)
    leituras_referencia_reconciliacao: db.Mapped[int] = db.mapped_column(default=0, nullable=False)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="itens")
    peca: db.Mapped["Peca"] = db.relationship(back_populates="pedidos_assoc")


class Leitura(db.Model):
    __tablename__ = "leitura"
    __table_args__ = (
        db.UniqueConstraint(
            "pedido_id",
            "idempotency_key",
            name="uq_leitura_pedido_idempotency_key",
        ),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"))
    peca_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("peca.id"))
    ciclo: db.Mapped[int] = db.mapped_column(nullable=True)
    status: db.Mapped[StatusLeitura] = db.mapped_column(db.Enum(StatusLeitura))
    idempotency_key: db.Mapped[str] = db.mapped_column(db.String(36), nullable=True)
    timestamp: db.Mapped[datetime.datetime] = db.mapped_column(default=datetime.datetime.utcnow)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="leituras")
    peca: db.Mapped["Peca"] = db.relationship(back_populates="leituras")