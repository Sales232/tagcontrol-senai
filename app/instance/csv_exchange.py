import csv
import io
import json
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy import select

from app import db
from app.instance.models import (
    Conferencia,
    ConferenciaItem,
    Conjunto,
    ConjuntoPeca,
    Embalagem,
    EmbalagemVolume,
    EmbalagemVolumeItem,
    Expedicao,
    ExpedicaoSaida,
    ExpedicaoVolumeEvento,
    Leitura,
    Pedido,
    PedidoConjunto,
    PedidoEstadoEvento,
    PedidoItem,
    PedidoReabertura,
    Peca,
    StatusLeitura,
)


CSV_VERSION = "3"
LEGACY_CSV_VERSION = "2"
MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_CSV_RECORDS = 50000
CSV_FIELDS = (
    "format_version",
    "record_type",
    "record_key",
    "parent_key",
    "related_key",
    "code",
    "description",
    "flow_status",
    "previous_status",
    "created_at",
    "deadline",
    "cycle",
    "quantity",
    "quantity_required",
    "quantity_reconciled",
    "reconciliation_read_count",
    "quantity_found",
    "person",
    "result",
    "timestamp",
    "observation",
    "sequence",
    "piece_code",
    "piece_description",
    "reason",
    "vehicle_plate",
    "driver_carrier",
    "action",
    "idempotency_key",
)
LEGACY_CSV_FIELDS = (*CSV_FIELDS[:7], "qr_code", *CSV_FIELDS[7:])

ENTITY_FIELDS = {
    "peca": {"code", "description"},
    "conjunto": {"code", "description"},
    "pedido": {"code", "flow_status", "created_at", "deadline"},
    "conjunto_peca": {"quantity"},
    "pedido_item": {"quantity_required", "quantity_reconciled", "reconciliation_read_count"},
    "pedido_conjunto": {"code", "description", "quantity", "sequence"},
    "leitura": {"cycle", "result", "timestamp", "sequence", "idempotency_key", "person"},
    "pedido_estado_evento": {
        "cycle",
        "flow_status",
        "previous_status",
        "person",
        "timestamp",
        "sequence",
    },
    "conferencia": {"cycle", "person", "result", "timestamp", "sequence"},
    "conferencia_item": {
        "piece_code",
        "piece_description",
        "quantity_required",
        "quantity_found",
        "reason",
        "sequence",
    },
    "pedido_reabertura": {"cycle", "timestamp"},
    "embalagem": {"cycle", "person", "timestamp", "observation"},
    "embalagem_volume": {"sequence"},
    "embalagem_volume_item": {"piece_code", "piece_description", "quantity", "sequence"},
    "expedicao": {"cycle", "vehicle_plate", "driver_carrier"},
    "expedicao_volume_evento": {"action", "person", "timestamp", "observation", "sequence"},
    "expedicao_saida": {"person", "timestamp", "observation"},
}

RELATION_FIELDS = {
    "peca": (None, set()),
    "conjunto": (None, set()),
    "pedido": (None, set()),
    "conjunto_peca": ("conjunto", {"peca", "conjunto"}),
    "pedido_item": ("pedido", {"peca"}),
    "pedido_conjunto": ("pedido", {"conjunto"}),
    "leitura": ("pedido", {"peca"}),
    "pedido_estado_evento": ("pedido", set()),
    "conferencia": ("pedido", set()),
    "conferencia_item": ("conferencia", {"pedido_item"}),
    "pedido_reabertura": ("pedido", set()),
    "embalagem": ("pedido", set()),
    "embalagem_volume": ("embalagem", set()),
    "embalagem_volume_item": ("embalagem_volume", {"pedido_item"}),
    "expedicao": ("pedido", {"embalagem"}),
    "expedicao_volume_evento": ("expedicao", {"embalagem_volume"}),
    "expedicao_saida": ("expedicao", set()),
}

FLOW_STATUSES = {
    "separacao",
    "aguardando_conferencia",
    "correcao",
    "liberado",
    "embalado",
    "carregando",
    "carregado",
    "expedido",
}


class CsvExchangeError(ValueError):
    pass


def _key(*parts: object) -> str:
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def _record(record_type: str, record_key: str, parent_key="", related_key="", **fields):
    row = {field: "" for field in CSV_FIELDS}
    row.update(
        format_version=CSV_VERSION,
        record_type=record_type,
        record_key=record_key,
        parent_key=parent_key or "",
        related_key=related_key or "",
    )
    row.update({name: value for name, value in fields.items() if value is not None})
    for field in CSV_FIELDS:
        if row[field] is None:
            row[field] = ""
    return row


def _timestamp(value: datetime | None) -> str:
    return value.isoformat(timespec="microseconds") if value else ""


def _status(value) -> str:
    return value.value if isinstance(value, StatusLeitura) else str(value)


def _spreadsheet_safe(value: str) -> str:
    if value.startswith("'") or value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _restore_spreadsheet_value(value: str) -> str:
    if value.startswith("'") and value[1:2] in {"'", "=", "+", "-", "@", "\t", "\r"}:
        return value[1:]
    return value


def export_csv() -> str:
    rows = []
    piece_keys = {}
    set_keys = {}
    order_keys = {}
    item_keys = {}
    conference_keys = {}
    package_keys = {}
    volume_keys = {}
    expedition_keys = {}

    pieces = db.session.scalars(select(Peca).order_by(Peca.codigo)).all()
    for piece in pieces:
        piece_key = _key("peca", piece.codigo)
        piece_keys[piece.id] = piece_key
        rows.append(
            _record(
                "peca",
                piece_key,
                code=piece.codigo,
                description=piece.descricao,
            )
        )

    sets = db.session.scalars(select(Conjunto).order_by(Conjunto.codigo)).all()
    for item_set in sets:
        set_key = _key("conjunto", item_set.codigo)
        set_keys[item_set.id] = set_key
        rows.append(
            _record("conjunto", set_key, code=item_set.codigo, description=item_set.descricao)
        )

    orders = db.session.scalars(select(Pedido).order_by(Pedido.codigo)).all()
    for order in orders:
        order_key = _key("pedido", order.codigo)
        order_keys[order.id] = order_key
        rows.append(
            _record(
                "pedido",
                order_key,
                code=order.codigo,
                flow_status=order.status_fluxo,
                created_at=_timestamp(order.criado_em),
                deadline=order.prazo_entrega.isoformat() if order.prazo_entrega else None,
            )
        )

    components = db.session.scalars(
        select(ConjuntoPeca)
        .join(Conjunto, ConjuntoPeca.conjunto_id == Conjunto.id)
        .order_by(Conjunto.codigo, ConjuntoPeca.id)
    ).all()
    for component in components:
        parent_key = set_keys[component.conjunto_id]
        related_key = (
            piece_keys[component.peca_id]
            if component.peca_id is not None
            else set_keys[component.subconjunto_id]
        )
        rows.append(
            _record(
                "conjunto_peca",
                _key("conjunto_peca", parent_key, related_key),
                parent_key,
                related_key,
                quantity=component.quantidade,
            )
        )

    order_items = db.session.scalars(
        select(PedidoItem).join(Pedido).join(Peca).order_by(Pedido.codigo, Peca.codigo)
    ).all()
    for order_item in order_items:
        parent_key = order_keys[order_item.pedido_id]
        related_key = piece_keys[order_item.peca_id]
        item_key = _key("pedido_item", parent_key, related_key)
        item_keys[order_item.id] = item_key
        rows.append(
            _record(
                "pedido_item",
                item_key,
                parent_key,
                related_key,
                quantity_required=order_item.quantidade_necessaria,
                quantity_reconciled=order_item.quantidade_reconciliada,
                reconciliation_read_count=order_item.leituras_referencia_reconciliacao,
            )
        )

    for order in orders:
        parent_key = order_keys[order.id]
        sequence = 0
        for composition in sorted(order.composicoes, key=lambda value: value.id):
            sequence += 1
            related_key = _key("conjunto", composition.codigo_conjunto)
            rows.append(
                _record(
                    "pedido_conjunto",
                    _key("pedido_conjunto", parent_key, sequence),
                    parent_key,
                    related_key,
                    code=composition.codigo_conjunto,
                    description=composition.descricao_conjunto,
                    quantity=composition.quantidade,
                    sequence=sequence,
                )
            )

        reading_sequence = 0
        for reading in sorted(order.leituras, key=lambda value: value.id):
            reading_sequence += 1
            rows.append(
                _record(
                    "leitura",
                    _key("leitura", parent_key, reading_sequence),
                    parent_key,
                    piece_keys[reading.peca_id],
                    cycle=reading.ciclo,
                    result=_status(reading.status),
                    timestamp=_timestamp(reading.timestamp),
                    sequence=reading_sequence,
                    idempotency_key=reading.idempotency_key,
                    person=reading.responsavel,
                )
            )

        for event_sequence, event in enumerate(
            sorted(order.eventos_estado, key=lambda value: (value.ciclo, value.timestamp, value.id)),
            start=1,
        ):
            rows.append(
                _record(
                    "pedido_estado_evento",
                    _key("pedido_estado_evento", parent_key, event.ciclo, event_sequence),
                    parent_key,
                    cycle=event.ciclo,
                    previous_status=event.estado_anterior,
                    flow_status=event.estado_novo,
                    person=event.responsavel,
                    timestamp=_timestamp(event.timestamp),
                    sequence=event_sequence,
                )
            )

        conference_sequence_by_cycle = defaultdict(int)
        for conference in sorted(order.conferencias, key=lambda value: value.id):
            conference_sequence_by_cycle[conference.ciclo] += 1
            sequence = conference_sequence_by_cycle[conference.ciclo]
            conference_key = _key("conferencia", parent_key, conference.ciclo, sequence)
            conference_keys[conference.id] = conference_key
            rows.append(
                _record(
                    "conferencia",
                    conference_key,
                    parent_key,
                    cycle=conference.ciclo,
                    person=conference.conferente,
                    result=conference.resultado,
                    timestamp=_timestamp(conference.timestamp),
                    sequence=sequence,
                )
            )
            for item_sequence, conference_item in enumerate(
                sorted(conference.itens, key=lambda value: value.id), start=1
            ):
                rows.append(
                    _record(
                        "conferencia_item",
                        _key("conferencia_item", conference_key, item_sequence),
                        conference_key,
                        item_keys.get(conference_item.pedido_item_id),
                        piece_code=conference_item.codigo_peca,
                        piece_description=conference_item.descricao_peca,
                        quantity_required=conference_item.quantidade_necessaria,
                        quantity_found=conference_item.quantidade_encontrada,
                        reason=conference_item.motivo_divergencia,
                        sequence=item_sequence,
                    )
                )

        for reopening in order.reaberturas:
            rows.append(
                _record(
                    "pedido_reabertura",
                    _key("pedido_reabertura", parent_key, reopening.ciclo),
                    parent_key,
                    cycle=reopening.ciclo,
                    timestamp=_timestamp(reopening.timestamp),
                )
            )

        for package in order.embalagens:
            package_key = _key("embalagem", parent_key, package.ciclo)
            package_keys[package.id] = package_key
            rows.append(
                _record(
                    "embalagem",
                    package_key,
                    parent_key,
                    cycle=package.ciclo,
                    person=package.responsavel,
                    timestamp=_timestamp(package.timestamp),
                    observation=package.observacao,
                )
            )
            for volume in package.volumes:
                volume_key = _key("embalagem_volume", package_key, volume.numero)
                volume_keys[volume.id] = volume_key
                rows.append(
                    _record(
                        "embalagem_volume",
                        volume_key,
                        package_key,
                        sequence=volume.numero,
                    )
                )
                for item_sequence, volume_item in enumerate(
                    sorted(volume.itens, key=lambda value: value.id), start=1
                ):
                    rows.append(
                        _record(
                            "embalagem_volume_item",
                            _key("embalagem_volume_item", volume_key, item_sequence),
                            volume_key,
                            item_keys.get(volume_item.pedido_item_id),
                            piece_code=volume_item.codigo_peca,
                            piece_description=volume_item.descricao_peca,
                            quantity=volume_item.quantidade,
                            sequence=item_sequence,
                        )
                    )

        for dispatch in order.expedicoes:
            expedition_key = _key("expedicao", parent_key, dispatch.ciclo)
            expedition_keys[dispatch.id] = expedition_key
            rows.append(
                _record(
                    "expedicao",
                    expedition_key,
                    parent_key,
                    package_keys.get(dispatch.embalagem_id),
                    cycle=dispatch.ciclo,
                    vehicle_plate=dispatch.placa_veiculo,
                    driver_carrier=dispatch.motorista_transportadora,
                )
            )
            for event_sequence, event in enumerate(
                sorted(dispatch.eventos_carga, key=lambda value: value.id), start=1
            ):
                rows.append(
                    _record(
                        "expedicao_volume_evento",
                        _key("expedicao_volume_evento", expedition_key, event_sequence),
                        expedition_key,
                        volume_keys.get(event.embalagem_volume_id),
                        action=event.acao,
                        person=event.responsavel,
                        timestamp=_timestamp(event.timestamp),
                        observation=event.observacao,
                        sequence=event_sequence,
                    )
                )
            if dispatch.saida is not None:
                rows.append(
                    _record(
                        "expedicao_saida",
                        _key("expedicao_saida", expedition_key),
                        expedition_key,
                        person=dispatch.saida.responsavel,
                        timestamp=_timestamp(dispatch.saida.timestamp),
                        observation=dispatch.saida.observacao,
                    )
                )

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: _spreadsheet_safe(value) if isinstance(value, str) else value
                for field, value in row.items()
            }
        )
    return output.getvalue()


def _required(row, field, record_number):
    value = (row.get(field) or "").strip()
    if not value:
        raise CsvExchangeError(f"Linha {record_number}: o campo {field} é obrigatório.")
    return value


def _integer(row, field, record_number, *, minimum=None, nullable=False):
    value = (row.get(field) or "").strip()
    if nullable and not value:
        return None
    try:
        result = int(value)
    except ValueError as error:
        raise CsvExchangeError(
            f"Linha {record_number}: {field} deve ser um número inteiro."
        ) from error
    if minimum is not None and result < minimum:
        raise CsvExchangeError(
            f"Linha {record_number}: {field} deve ser maior ou igual a {minimum}."
        )
    return result


def _date(row, field, record_number):
    value = _required(row, field, record_number)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CsvExchangeError(f"Linha {record_number}: timestamp ISO inválido.") from error
    if parsed.utcoffset() is not None:
        parsed = parsed.astimezone(timezone.utc)
        parsed = parsed.replace(tzinfo=None)
    return parsed


def _deadline(row, field, record_number):
    value = (row.get(field) or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise CsvExchangeError(f"Linha {record_number}: prazo de entrega inválido.") from error


def _record_type(row, record_number):
    record_type = _required(row, "record_type", record_number)
    if record_type not in ENTITY_FIELDS:
        raise CsvExchangeError(f"Linha {record_number}: tipo de registro desconhecido.")
    return record_type


def _validate_csv(content: bytes):
    if not content:
        raise CsvExchangeError("O arquivo CSV está vazio.")
    if len(content) > MAX_CSV_BYTES:
        raise CsvExchangeError("O arquivo CSV excede o limite de 10 MB.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvExchangeError("O arquivo deve usar codificação UTF-8.") from error

    reader = csv.DictReader(io.StringIO(text, newline=""))
    headers = tuple(reader.fieldnames or ())
    if headers not in {CSV_FIELDS, LEGACY_CSV_FIELDS}:
        raise CsvExchangeError("Cabeçalho CSV inválido ou versão de formato incompatível.")
    legacy_format = headers == LEGACY_CSV_FIELDS

    rows = []
    keys = {}
    natural_values = defaultdict(set)
    for number, row in enumerate(reader, start=2):
        if None in row or any(value is None for value in row.values()):
            raise CsvExchangeError(f"Linha {number}: quantidade de colunas inválida.")
        row = {field: _restore_spreadsheet_value(value) for field, value in row.items()}
        expected_version = LEGACY_CSV_VERSION if legacy_format else CSV_VERSION
        if row["format_version"] != expected_version:
            raise CsvExchangeError(f"Linha {number}: versão de formato não suportada.")
        record_type = _record_type(row, number)
        record_key = _required(row, "record_key", number)
        if record_key in keys:
            raise CsvExchangeError(f"Linha {number}: chave de registro duplicada.")
        keys[record_key] = record_type

        allowed = {"format_version", "record_type", "record_key", "parent_key", "related_key"}
        allowed.update(ENTITY_FIELDS[record_type])
        if legacy_format and record_type == "peca":
            allowed.add("qr_code")
        for field in CSV_FIELDS:
            if field not in allowed and (row.get(field) or "").strip():
                raise CsvExchangeError(
                    f"Linha {number}: o campo {field} não se aplica a {record_type}."
                )

        parent_type, related_types = RELATION_FIELDS[record_type]
        parent_key = (row.get("parent_key") or "").strip()
        related_key = (row.get("related_key") or "").strip()
        if bool(parent_type) != bool(parent_key):
            raise CsvExchangeError(f"Linha {number}: referência parent_key inválida.")
        if parent_key and keys.get(parent_key) not in (None, parent_type):
            raise CsvExchangeError(f"Linha {number}: parent_key aponta para entidade incompatível.")
        if related_types and record_type not in {"conferencia_item", "embalagem_volume_item"} and not related_key:
            raise CsvExchangeError(f"Linha {number}: related_key é obrigatório.")
        if related_key and keys.get(related_key) not in (None, *related_types):
            raise CsvExchangeError(f"Linha {number}: related_key aponta para entidade incompatível.")
        if not related_types and related_key:
            raise CsvExchangeError(f"Linha {number}: related_key não se aplica a {record_type}.")

        try:
            key_parts = json.loads(record_key)
        except json.JSONDecodeError as error:
            raise CsvExchangeError(f"Linha {number}: record_key inválida.") from error
        if not isinstance(key_parts, list) or not key_parts or key_parts[0] != record_type:
            raise CsvExchangeError(f"Linha {number}: record_key incompatível com o tipo.")

        if record_type == "peca":
            code = _required(row, "code", number)
            description = _required(row, "description", number)
            if len(code) > 50 or len(description) > 200:
                raise CsvExchangeError(f"Linha {number}: dados da peça excedem os limites.")
            if code != code.strip() or any(
                ord(character) < 32 or ord(character) == 127 for character in code
            ):
                raise CsvExchangeError(f"Linha {number}: código interno inválido para o QR Code.")
            if code in natural_values["peca.codigo_seen"]:
                raise CsvExchangeError(f"Linha {number}: código de peça duplicado.")
            natural_values["peca.codigo_seen"].add(code)
        elif record_type in {"conjunto", "pedido"}:
            code = _required(row, "code", number)
            if len(code) > 50:
                raise CsvExchangeError(f"Linha {number}: código de {record_type} excede 50 caracteres.")
            if code in natural_values[f"{record_type}.codigo_seen"]:
                raise CsvExchangeError(f"Linha {number}: código de {record_type} duplicado.")
            natural_values[f"{record_type}.codigo_seen"].add(code)
            if record_type == "conjunto":
                if len(_required(row, "description", number)) > 200:
                    raise CsvExchangeError(f"Linha {number}: descrição de conjunto excede 200 caracteres.")
            else:
                if (row.get("flow_status") or "") not in FLOW_STATUSES:
                    raise CsvExchangeError(f"Linha {number}: estado de pedido inválido.")
                if row["created_at"]:
                    _date(row, "created_at", number)
                _deadline(row, "deadline", number)
        elif record_type == "conjunto_peca":
            _integer(row, "quantity", number, minimum=1)
            if not related_key.startswith('["peca",') and not related_key.startswith('["conjunto",'):
                raise CsvExchangeError(f"Linha {number}: componente deve ser uma peça ou conjunto.")
        elif record_type == "pedido_item":
            _integer(row, "quantity_required", number, minimum=1)
            _integer(row, "quantity_reconciled", number, minimum=0)
            _integer(row, "reconciliation_read_count", number, minimum=0)
        elif record_type == "pedido_conjunto":
            _required(row, "code", number)
            _required(row, "description", number)
            _integer(row, "quantity", number, minimum=1)
            _integer(row, "sequence", number, minimum=1)
        elif record_type == "leitura":
            _integer(row, "cycle", number, minimum=1, nullable=True)
            if (row.get("result") or "") not in {status.value for status in StatusLeitura}:
                raise CsvExchangeError(f"Linha {number}: resultado da leitura inválido.")
            if row["idempotency_key"]:
                identity = (parent_key, row["idempotency_key"])
                if identity in natural_values["leitura.idempotency"]:
                    raise CsvExchangeError(f"Linha {number}: chave de idempotência duplicada.")
                natural_values["leitura.idempotency"].add(identity)
            _date(row, "timestamp", number)
            _integer(row, "sequence", number, minimum=1)
            if len(row["person"] or "") > 100:
                raise CsvExchangeError(f"Linha {number}: responsável da leitura excede 100 caracteres.")
        elif record_type == "pedido_estado_evento":
            _integer(row, "cycle", number, minimum=1)
            if (row.get("flow_status") or "") not in FLOW_STATUSES:
                raise CsvExchangeError(f"Linha {number}: estado de transição inválido.")
            previous_status = row["previous_status"]
            if previous_status and previous_status not in FLOW_STATUSES:
                raise CsvExchangeError(f"Linha {number}: estado anterior inválido.")
            if not _required(row, "person", number) or len(row["person"]) > 100:
                raise CsvExchangeError(f"Linha {number}: responsável da transição inválido.")
            _date(row, "timestamp", number)
            _integer(row, "sequence", number, minimum=1)
        elif record_type == "conferencia":
            _integer(row, "cycle", number, minimum=1, nullable=True)
            _required(row, "person", number)
            if len(row["person"]) > 100 or row["result"] not in {"aprovada", "reprovada"}:
                raise CsvExchangeError(f"Linha {number}: conferência inválida.")
            _date(row, "timestamp", number)
            _integer(row, "sequence", number, minimum=1)
        elif record_type == "conferencia_item":
            _required(row, "piece_code", number)
            _required(row, "piece_description", number)
            _integer(row, "quantity_required", number, minimum=0)
            _integer(row, "quantity_found", number, minimum=0)
            if len(row["reason"] or "") > 500:
                raise CsvExchangeError(f"Linha {number}: motivo excede 500 caracteres.")
            _integer(row, "sequence", number, minimum=1)
        elif record_type == "pedido_reabertura":
            _integer(row, "cycle", number, minimum=2)
            _date(row, "timestamp", number)
        elif record_type == "embalagem":
            _integer(row, "cycle", number, minimum=1)
            if not _required(row, "person", number) or len(row["person"]) > 100:
                raise CsvExchangeError(f"Linha {number}: responsável de embalagem inválido.")
            if len(row["observation"] or "") > 500:
                raise CsvExchangeError(f"Linha {number}: observação excede 500 caracteres.")
            _date(row, "timestamp", number)
        elif record_type == "embalagem_volume":
            _integer(row, "sequence", number, minimum=1)
        elif record_type == "embalagem_volume_item":
            _required(row, "piece_code", number)
            _required(row, "piece_description", number)
            _integer(row, "quantity", number, minimum=1)
            _integer(row, "sequence", number, minimum=1)
        elif record_type == "expedicao":
            _integer(row, "cycle", number, minimum=1)
            if len(_required(row, "vehicle_plate", number)) > 20:
                raise CsvExchangeError(f"Linha {number}: placa excede 20 caracteres.")
            if len(_required(row, "driver_carrier", number)) > 120:
                raise CsvExchangeError(f"Linha {number}: motorista/transportadora excede 120 caracteres.")
        elif record_type == "expedicao_volume_evento":
            if row["action"] not in {"carregado", "revertido"}:
                raise CsvExchangeError(f"Linha {number}: ação de carregamento inválida.")
            if len(_required(row, "person", number)) > 100:
                raise CsvExchangeError(f"Linha {number}: responsável excede 100 caracteres.")
            if len(row["observation"] or "") > 500:
                raise CsvExchangeError(f"Linha {number}: observação excede 500 caracteres.")
            _date(row, "timestamp", number)
            _integer(row, "sequence", number, minimum=1)
        elif record_type == "expedicao_saida":
            if len(_required(row, "person", number)) > 100:
                raise CsvExchangeError(f"Linha {number}: responsável excede 100 caracteres.")
            if len(row["observation"] or "") > 500:
                raise CsvExchangeError(f"Linha {number}: observação excede 500 caracteres.")
            _date(row, "timestamp", number)

        rows.append((number, record_type, row))
        if len(rows) > MAX_CSV_RECORDS:
            raise CsvExchangeError("O arquivo excede o limite de 50.000 registros.")

    if not rows:
        raise CsvExchangeError("O arquivo CSV não contém registros.")
    for number, record_type, row in rows:
        parent_key = (row.get("parent_key") or "").strip()
        related_key = (row.get("related_key") or "").strip()
        parent_type, related_types = RELATION_FIELDS[record_type]
        if parent_key and keys.get(parent_key) != parent_type:
            raise CsvExchangeError(f"Linha {number}: parent_key não encontrado no arquivo.")
        if related_key and keys.get(related_key) not in related_types:
            raise CsvExchangeError(f"Linha {number}: related_key não encontrado no arquivo.")
    return rows


def _precheck_conflicts(rows):
    by_type = defaultdict(list)
    for _, record_type, row in rows:
        by_type[record_type].append(row)

    conflicts = []
    if by_type["peca"]:
        codes = [row["code"] for row in by_type["peca"]]
        if db.session.scalars(select(Peca.codigo).where(Peca.codigo.in_(codes))).first():
            conflicts.append("código de peça")
    if by_type["conjunto"]:
        codes = [row["code"] for row in by_type["conjunto"]]
        if db.session.scalars(select(Conjunto.codigo).where(Conjunto.codigo.in_(codes))).first():
            conflicts.append("código de conjunto")
    if by_type["pedido"]:
        codes = [row["code"] for row in by_type["pedido"]]
        if db.session.scalars(select(Pedido.codigo).where(Pedido.codigo.in_(codes))).first():
            conflicts.append("código de pedido")
    if conflicts:
        raise CsvExchangeError(
            "Importação cancelada: já existem registros com " + ", ".join(conflicts) + "."
        )


def import_csv(content: bytes) -> int:
    rows = _validate_csv(content)
    _precheck_conflicts(rows)
    grouped = defaultdict(list)
    for number, record_type, row in rows:
        grouped[record_type].append((number, row))

    records = {row["record_key"]: (record_type, row) for _, record_type, row in rows}
    imported = {}

    def get_record(key, expected_type, row_number):
        if not key:
            return None
        value = imported.get(key)
        if value is None:
            raise CsvExchangeError(f"Linha {row_number}: referência ainda não resolvida ({expected_type}).")
        return value

    for record_type, model, key_field, constructor in (
        ("peca", Peca, "code", lambda row: Peca(
            codigo=row["code"], descricao=row["description"]
        )),
        ("conjunto", Conjunto, "code", lambda row: Conjunto(
            codigo=row["code"], descricao=row["description"]
        )),
        ("pedido", Pedido, "code", lambda row: Pedido(
            codigo=row["code"],
            status_fluxo=row["flow_status"],
        )),
    ):
        for number, row in grouped[record_type]:
            item = constructor(row)
            if record_type == "pedido":
                item.criado_em = _date(row, "created_at", number) if row["created_at"] else None
                item.prazo_entrega = _deadline(row, "deadline", number)
            db.session.add(item)
            imported[row["record_key"]] = item
    db.session.flush()

    for number, row in grouped["conjunto_peca"]:
        parent = get_record(row["parent_key"], "conjunto", number)
        related_type, _ = records[row["related_key"]]
        related = get_record(row["related_key"], related_type, number)
        component = ConjuntoPeca(conjunto=parent, quantidade=int(row["quantity"]))
        if related_type == "peca":
            component.peca = related
        else:
            component.subconjunto = related
        db.session.add(component)

    for number, row in grouped["pedido_item"]:
        order = get_record(row["parent_key"], "pedido", number)
        piece = get_record(row["related_key"], "peca", number)
        item = PedidoItem(
            pedido=order,
            peca=piece,
            quantidade_necessaria=int(row["quantity_required"]),
            quantidade_reconciliada=int(row["quantity_reconciled"]),
            leituras_referencia_reconciliacao=int(row["reconciliation_read_count"]),
        )
        db.session.add(item)
        imported[row["record_key"]] = item

    for number, row in grouped["pedido_conjunto"]:
        order = get_record(row["parent_key"], "pedido", number)
        item_set = get_record(row["related_key"], "conjunto", number)
        db.session.add(
            PedidoConjunto(
                pedido=order,
                conjunto_id=item_set.id,
                codigo_conjunto=row["code"],
                descricao_conjunto=row["description"],
                quantidade=int(row["quantity"]),
            )
        )

    for number, row in grouped["leitura"]:
        order = get_record(row["parent_key"], "pedido", number)
        piece = get_record(row["related_key"], "peca", number)
        reading = Leitura(
            pedido=order,
            peca=piece,
            ciclo=_integer(row, "cycle", number, minimum=1, nullable=True),
            status=StatusLeitura(row["result"]),
            timestamp=_date(row, "timestamp", number),
            responsavel=row["person"] or None,
            idempotency_key=row["idempotency_key"] or None,
        )
        db.session.add(reading)

    for number, row in grouped["pedido_estado_evento"]:
        order = get_record(row["parent_key"], "pedido", number)
        db.session.add(
            PedidoEstadoEvento(
                pedido=order,
                ciclo=int(row["cycle"]),
                estado_anterior=row["previous_status"] or None,
                estado_novo=row["flow_status"],
                responsavel=row["person"],
                timestamp=_date(row, "timestamp", number),
            )
        )

    for number, row in grouped["conferencia"]:
        order = get_record(row["parent_key"], "pedido", number)
        conference = Conferencia(
            pedido=order,
            ciclo=_integer(row, "cycle", number, minimum=1, nullable=True),
            conferente=row["person"],
            resultado=row["result"],
            timestamp=_date(row, "timestamp", number),
        )
        db.session.add(conference)
        imported[row["record_key"]] = conference

    for number, row in grouped["pedido_reabertura"]:
        order = get_record(row["parent_key"], "pedido", number)
        db.session.add(
            PedidoReabertura(
                pedido=order,
                ciclo=int(row["cycle"]),
                timestamp=_date(row, "timestamp", number),
            )
        )

    for number, row in grouped["embalagem"]:
        order = get_record(row["parent_key"], "pedido", number)
        package = Embalagem(
            pedido=order,
            ciclo=int(row["cycle"]),
            responsavel=row["person"],
            timestamp=_date(row, "timestamp", number),
            observacao=row["observation"] or None,
        )
        db.session.add(package)
        imported[row["record_key"]] = package

    for number, row in grouped["expedicao"]:
        order = get_record(row["parent_key"], "pedido", number)
        package = get_record(row["related_key"], "embalagem", number)
        dispatch = Expedicao(
            pedido=order,
            embalagem=package,
            ciclo=int(row["cycle"]),
            placa_veiculo=row["vehicle_plate"],
            motorista_transportadora=row["driver_carrier"],
        )
        db.session.add(dispatch)
        imported[row["record_key"]] = dispatch

    db.session.flush()

    for number, row in grouped["conferencia_item"]:
        conference = get_record(row["parent_key"], "conferencia", number)
        order_item = get_record(row["related_key"], "pedido_item", number)
        db.session.add(
            ConferenciaItem(
                conferencia=conference,
                pedido_item_id=order_item.id if order_item is not None else None,
                codigo_peca=row["piece_code"],
                descricao_peca=row["piece_description"],
                quantidade_necessaria=int(row["quantity_required"]),
                quantidade_encontrada=int(row["quantity_found"]),
                motivo_divergencia=row["reason"] or None,
            )
        )

    for number, row in grouped["embalagem_volume"]:
        package = get_record(row["parent_key"], "embalagem", number)
        volume = EmbalagemVolume(embalagem=package, numero=int(row["sequence"]))
        db.session.add(volume)
        imported[row["record_key"]] = volume

    db.session.flush()

    for number, row in grouped["embalagem_volume_item"]:
        volume = get_record(row["parent_key"], "embalagem_volume", number)
        order_item = get_record(row["related_key"], "pedido_item", number)
        db.session.add(
            EmbalagemVolumeItem(
                volume=volume,
                pedido_item_id=order_item.id if order_item is not None else None,
                codigo_peca=row["piece_code"],
                descricao_peca=row["piece_description"],
                quantidade=int(row["quantity"]),
            )
        )

    for number, row in grouped["expedicao_volume_evento"]:
        dispatch = get_record(row["parent_key"], "expedicao", number)
        volume = get_record(row["related_key"], "embalagem_volume", number)
        if volume.embalagem_id != dispatch.embalagem_id:
            raise CsvExchangeError(f"Linha {number}: volume não pertence à embalagem da expedição.")
        db.session.add(
            ExpedicaoVolumeEvento(
                expedicao=dispatch,
                volume=volume,
                acao=row["action"],
                responsavel=row["person"],
                timestamp=_date(row, "timestamp", number),
                observacao=row["observation"] or None,
            )
        )

    for number, row in grouped["expedicao_saida"]:
        dispatch = get_record(row["parent_key"], "expedicao", number)
        db.session.add(
            ExpedicaoSaida(
                expedicao=dispatch,
                responsavel=row["person"],
                timestamp=_date(row, "timestamp", number),
                observacao=row["observation"] or None,
            )
        )

    db.session.flush()
    db.session.commit()
    return len(rows)
