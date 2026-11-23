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
    criado_em: db.Mapped[datetime.datetime | None] = db.mapped_column(
        default=datetime.datetime.utcnow,
        nullable=True,
    )
    prazo_entrega: db.Mapped[datetime.date | None] = db.mapped_column(db.Date, nullable=True)

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
    embalagens: db.Mapped[list["Embalagem"]] = db.relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="Embalagem.ciclo",
    )
    expedicoes: db.Mapped[list["Expedicao"]] = db.relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="Expedicao.ciclo",
    )
    composicoes: db.Mapped[list["PedidoConjunto"]] = db.relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="PedidoConjunto.id",
    )
    eventos_estado: db.Mapped[list["PedidoEstadoEvento"]] = db.relationship(
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="PedidoEstadoEvento.timestamp, PedidoEstadoEvento.id",
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

    @property
    def ciclo_atual(self) -> int:
        return max((reabertura.ciclo for reabertura in self.reaberturas), default=1)

    def historico(self) -> list[dict[str, object]]:
        eventos: list[tuple[datetime.datetime, int, int, dict[str, object]]] = []

        leitura_labels = {
            StatusLeitura.SUCESSO: ("Leitura validada", "Sucesso"),
            StatusLeitura.DUPLICADA: ("Leitura duplicada", "Duplicada"),
            StatusLeitura.FORA_DO_PEDIDO: ("Peça fora do pedido", "Fora do pedido"),
        }
        for leitura in self.leituras:
            titulo, resultado = leitura_labels[leitura.status]
            eventos.append(
                (
                    leitura.timestamp,
                    1,
                    leitura.id,
                    {
                        "timestamp": leitura.timestamp,
                        "ciclo": leitura.ciclo,
                        "tipo": "Leitura",
                        "evento": titulo,
                        "codigo_peca": leitura.peca.codigo,
                        "descricao_peca": leitura.peca.descricao,
                        "resultado": resultado,
                        "conferente": None,
                        "responsavel": leitura.responsavel,
                        "motivo": None,
                    },
                )
            )

        for conferencia in self.conferencias:
            eventos.append(
                (
                    conferencia.timestamp,
                    2,
                    conferencia.id,
                    {
                        "timestamp": conferencia.timestamp,
                        "ciclo": conferencia.ciclo,
                        "tipo": "Conferência",
                        "evento": "Tentativa de conferência",
                        "codigo_peca": None,
                        "descricao_peca": None,
                        "resultado": "Aprovada" if conferencia.resultado == "aprovada" else "Reprovada",
                        "conferente": conferencia.conferente,
                        "motivo": None,
                    },
                )
            )
            for item in conferencia.itens:
                if item.quantidade_encontrada == item.quantidade_necessaria:
                    continue
                eventos.append(
                    (
                        conferencia.timestamp,
                        3,
                        item.id,
                        {
                            "timestamp": conferencia.timestamp,
                            "ciclo": conferencia.ciclo,
                            "tipo": "Divergência",
                            "evento": "Divergência na conferência",
                            "codigo_peca": item.codigo_peca,
                            "descricao_peca": item.descricao_peca,
                            "resultado": (
                                f"{item.quantidade_encontrada} encontrada(s) "
                                f"de {item.quantidade_necessaria}"
                            ),
                            "conferente": conferencia.conferente,
                            "motivo": item.motivo_divergencia,
                        },
                    )
                )

        for reabertura in self.reaberturas:
            eventos.append(
                (
                    reabertura.timestamp,
                    4,
                    reabertura.id,
                    {
                        "timestamp": reabertura.timestamp,
                        "ciclo": reabertura.ciclo,
                        "tipo": "Reabertura",
                        "evento": "Pedido reaberto",
                        "codigo_peca": None,
                        "descricao_peca": None,
                        "resultado": f"Ciclo {reabertura.ciclo} iniciado",
                        "conferente": None,
                        "motivo": None,
                    },
                )
            )

        for evento_estado in self.eventos_estado:
            eventos.append(
                (
                    evento_estado.timestamp,
                    0,
                    evento_estado.id,
                    {
                        "timestamp": evento_estado.timestamp,
                        "ciclo": evento_estado.ciclo,
                        "tipo": "Transição",
                        "evento": "Estado do pedido alterado",
                        "codigo_peca": None,
                        "descricao_peca": None,
                        "resultado": (
                            f"{evento_estado.estado_anterior or 'Novo'} → "
                            f"{evento_estado.estado_novo}"
                        ),
                        "conferente": None,
                        "responsavel": evento_estado.responsavel,
                        "motivo": None,
                    },
                )
            )

        for embalagem in self.embalagens:
            resumo = ", ".join(
                f"{item.codigo_peca}: {item.quantidade}"
                for volume in embalagem.volumes
                for item in volume.itens
            )
            eventos.append(
                (
                    embalagem.timestamp,
                    5,
                    embalagem.id,
                    {
                        "timestamp": embalagem.timestamp,
                        "ciclo": embalagem.ciclo,
                        "tipo": "Embalagem",
                        "evento": "Pedido embalado",
                        "codigo_peca": None,
                        "descricao_peca": None,
                        "resultado": f"{len(embalagem.volumes)} volume(s)",
                        "conferente": embalagem.responsavel,
                        "responsavel": embalagem.responsavel,
                        "motivo": embalagem.observacao or resumo or None,
                    },
                )
            )

        for expedicao in self.expedicoes:
            for evento_carga in expedicao.eventos_carga:
                eventos.append(
                    (
                        evento_carga.timestamp,
                        6,
                        evento_carga.id,
                        {
                            "timestamp": evento_carga.timestamp,
                            "ciclo": expedicao.ciclo,
                            "tipo": "Carregamento",
                            "evento": (
                                f"Volume {evento_carga.volume.numero} "
                                f"{'carregado' if evento_carga.acao == 'carregado' else 'descarregado'}"
                            ),
                            "codigo_peca": None,
                            "descricao_peca": None,
                            "resultado": evento_carga.acao.capitalize(),
                            "conferente": evento_carga.responsavel,
                            "responsavel": evento_carga.responsavel,
                            "motivo": evento_carga.observacao,
                            "veiculo": expedicao.placa_veiculo,
                            "motorista": expedicao.motorista_transportadora,
                        },
                    )
                )
            if expedicao.saida is not None:
                eventos.append(
                    (
                        expedicao.saida.timestamp,
                        7,
                        expedicao.saida.id,
                        {
                            "timestamp": expedicao.saida.timestamp,
                            "ciclo": expedicao.ciclo,
                            "tipo": "Saída",
                            "evento": "Pedido expedido",
                            "codigo_peca": None,
                            "descricao_peca": None,
                            "resultado": "Saída confirmada",
                            "conferente": expedicao.saida.responsavel,
                            "responsavel": expedicao.saida.responsavel,
                            "motivo": expedicao.saida.observacao,
                            "veiculo": expedicao.placa_veiculo,
                            "motorista": expedicao.motorista_transportadora,
                        },
                    )
                )

        eventos.sort(key=lambda evento: (evento[0], evento[1], evento[2]))
        return [evento[3] for evento in eventos]


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


class Embalagem(db.Model):
    __tablename__ = "embalagem"
    __table_args__ = (
        db.UniqueConstraint("pedido_id", "ciclo", name="uq_embalagem_pedido_ciclo"),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"), nullable=False)
    ciclo: db.Mapped[int] = db.mapped_column(nullable=False)
    responsavel: db.Mapped[str] = db.mapped_column(db.String(100), nullable=False)
    timestamp: db.Mapped[datetime.datetime] = db.mapped_column(default=datetime.datetime.utcnow)
    observacao: db.Mapped[str | None] = db.mapped_column(db.String(500), nullable=True)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="embalagens")
    volumes: db.Mapped[list["EmbalagemVolume"]] = db.relationship(
        back_populates="embalagem",
        cascade="all, delete-orphan",
        order_by="EmbalagemVolume.numero",
    )


class EmbalagemVolume(db.Model):
    __tablename__ = "embalagem_volume"
    __table_args__ = (
        db.UniqueConstraint("embalagem_id", "numero", name="uq_embalagem_volume_numero"),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    embalagem_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("embalagem.id"), nullable=False)
    numero: db.Mapped[int] = db.mapped_column(nullable=False)

    embalagem: db.Mapped["Embalagem"] = db.relationship(back_populates="volumes")
    itens: db.Mapped[list["EmbalagemVolumeItem"]] = db.relationship(
        back_populates="volume",
        cascade="all, delete-orphan",
        order_by="EmbalagemVolumeItem.id",
    )


class EmbalagemVolumeItem(db.Model):
    __tablename__ = "embalagem_volume_item"
    __table_args__ = (
        db.UniqueConstraint("volume_id", "pedido_item_id", name="uq_embalagem_volume_item"),
        db.CheckConstraint("quantidade > 0", name="ck_embalagem_volume_item_quantidade_positiva"),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    volume_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("embalagem_volume.id"), nullable=False)
    pedido_item_id: db.Mapped[int | None] = db.mapped_column(
        db.ForeignKey("pedido_item.id", ondelete="SET NULL"),
        nullable=True,
    )
    codigo_peca: db.Mapped[str] = db.mapped_column(db.String(50), nullable=False)
    descricao_peca: db.Mapped[str] = db.mapped_column(db.String(200), nullable=False)
    quantidade: db.Mapped[int] = db.mapped_column(nullable=False)

    volume: db.Mapped["EmbalagemVolume"] = db.relationship(back_populates="itens")


class Expedicao(db.Model):
    __tablename__ = "expedicao"
    __table_args__ = (
        db.UniqueConstraint("pedido_id", "ciclo", name="uq_expedicao_pedido_ciclo"),
        db.UniqueConstraint("embalagem_id", name="uq_expedicao_embalagem"),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"), nullable=False)
    embalagem_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("embalagem.id"), nullable=False)
    ciclo: db.Mapped[int] = db.mapped_column(nullable=False)
    placa_veiculo: db.Mapped[str] = db.mapped_column(db.String(20), nullable=False)
    motorista_transportadora: db.Mapped[str] = db.mapped_column(db.String(120), nullable=False)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="expedicoes")
    embalagem: db.Mapped["Embalagem"] = db.relationship()
    eventos_carga: db.Mapped[list["ExpedicaoVolumeEvento"]] = db.relationship(
        back_populates="expedicao",
        cascade="all, delete-orphan",
        order_by="ExpedicaoVolumeEvento.id",
    )
    saida: db.Mapped["ExpedicaoSaida | None"] = db.relationship(
        back_populates="expedicao",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def volumes_carregados(self) -> set[int]:
        estado_por_volume = {}
        for evento in self.eventos_carga:
            volume_id = evento.embalagem_volume_id or evento.volume.id
            estado_por_volume[volume_id] = evento.acao == "carregado"
        return {
            volume_id
            for volume_id, carregado in estado_por_volume.items()
            if carregado
        }


class ExpedicaoVolumeEvento(db.Model):
    __tablename__ = "expedicao_volume_evento"
    __table_args__ = (
        db.CheckConstraint(
            "acao IN ('carregado', 'revertido')",
            name="ck_expedicao_volume_evento_acao",
        ),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    expedicao_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("expedicao.id"), nullable=False)
    embalagem_volume_id: db.Mapped[int] = db.mapped_column(
        db.ForeignKey("embalagem_volume.id"),
        nullable=False,
    )
    acao: db.Mapped[str] = db.mapped_column(db.String(20), nullable=False)
    responsavel: db.Mapped[str] = db.mapped_column(db.String(100), nullable=False)
    timestamp: db.Mapped[datetime.datetime] = db.mapped_column(default=datetime.datetime.utcnow)
    observacao: db.Mapped[str | None] = db.mapped_column(db.String(500), nullable=True)

    expedicao: db.Mapped["Expedicao"] = db.relationship(back_populates="eventos_carga")
    volume: db.Mapped["EmbalagemVolume"] = db.relationship()


class ExpedicaoSaida(db.Model):
    __tablename__ = "expedicao_saida"

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    expedicao_id: db.Mapped[int] = db.mapped_column(
        db.ForeignKey("expedicao.id"),
        nullable=False,
        unique=True,
    )
    responsavel: db.Mapped[str] = db.mapped_column(db.String(100), nullable=False)
    timestamp: db.Mapped[datetime.datetime] = db.mapped_column(default=datetime.datetime.utcnow)
    observacao: db.Mapped[str | None] = db.mapped_column(db.String(500), nullable=True)

    expedicao: db.Mapped["Expedicao"] = db.relationship(back_populates="saida")


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
    responsavel: db.Mapped[str | None] = db.mapped_column(db.String(100), nullable=True)
    idempotency_key: db.Mapped[str] = db.mapped_column(db.String(36), nullable=True)
    timestamp: db.Mapped[datetime.datetime] = db.mapped_column(default=datetime.datetime.utcnow)

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="leituras")
    peca: db.Mapped["Peca"] = db.relationship(back_populates="leituras")


class PedidoEstadoEvento(db.Model):
    __tablename__ = "pedido_estado_evento"
    __table_args__ = (
        db.Index(
            "ix_pedido_estado_evento_pedido_ciclo_timestamp",
            "pedido_id",
            "ciclo",
            "timestamp",
        ),
    )

    id: db.Mapped[int] = db.mapped_column(primary_key=True)
    pedido_id: db.Mapped[int] = db.mapped_column(db.ForeignKey("pedido.id"), nullable=False)
    ciclo: db.Mapped[int] = db.mapped_column(nullable=False)
    estado_anterior: db.Mapped[str | None] = db.mapped_column(db.String(30), nullable=True)
    estado_novo: db.Mapped[str] = db.mapped_column(db.String(30), nullable=False)
    responsavel: db.Mapped[str] = db.mapped_column(db.String(100), nullable=False)
    timestamp: db.Mapped[datetime.datetime] = db.mapped_column(
        default=datetime.datetime.utcnow,
        nullable=False,
    )

    pedido: db.Mapped["Pedido"] = db.relationship(back_populates="eventos_estado")