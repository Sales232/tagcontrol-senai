from collections import defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app import db
from app.instance.models import (
    Conferencia,
    Embalagem,
    Expedicao,
    ExpedicaoVolumeEvento,
    Leitura,
    Pedido,
    PedidoEstadoEvento,
    StatusLeitura,
)


FLOW_STATUSES = (
    "separacao",
    "aguardando_conferencia",
    "correcao",
    "liberado",
    "embalado",
    "carregando",
    "carregado",
    "expedido",
)


def calculate_indicators(
    start_date: date,
    end_date: date,
    status: str | None = None,
    *,
    today: date | None = None,
) -> dict[str, object]:
    if start_date > end_date:
        raise ValueError("A data inicial deve ser anterior ou igual à data final.")
    if status and status not in FLOW_STATUSES:
        raise ValueError("Estado de pedido inválido.")

    start = datetime.combine(start_date, time.min)
    end_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)
    selected_orders = select(Pedido).where(
        Pedido.criado_em.is_not(None),
        Pedido.criado_em >= start,
        Pedido.criado_em < end_exclusive,
    )
    if status:
        selected_orders = selected_orders.where(Pedido.status_fluxo == status)
    orders = db.session.scalars(selected_orders.order_by(Pedido.codigo)).all()
    order_ids = [order.id for order in orders]
    current_day = today or datetime.utcnow().date()

    reads = []
    conferences = []
    packages = []
    if order_ids:
        reads = db.session.scalars(
            select(Leitura).where(
                Leitura.pedido_id.in_(order_ids),
                Leitura.timestamp >= start,
                Leitura.timestamp < end_exclusive,
            )
        ).all()
        conferences = db.session.scalars(
            select(Conferencia).where(
                Conferencia.pedido_id.in_(order_ids),
                Conferencia.timestamp >= start,
                Conferencia.timestamp < end_exclusive,
            )
        ).all()
        packages = db.session.scalars(
            select(Embalagem).where(
                Embalagem.pedido_id.in_(order_ids),
                Embalagem.timestamp >= start,
                Embalagem.timestamp < end_exclusive,
            )
        ).all()

    events = []
    loaded_events = []
    loaded_events_as_of_end = []
    if order_ids:
        events = db.session.scalars(
            select(PedidoEstadoEvento)
            .where(
                PedidoEstadoEvento.pedido_id.in_(order_ids),
                PedidoEstadoEvento.timestamp < end_exclusive,
            )
            .order_by(PedidoEstadoEvento.pedido_id, PedidoEstadoEvento.ciclo, PedidoEstadoEvento.timestamp)
        ).all()
        loaded_events = db.session.scalars(
            select(ExpedicaoVolumeEvento)
            .join(Expedicao, ExpedicaoVolumeEvento.expedicao_id == Expedicao.id)
            .where(
                ExpedicaoVolumeEvento.timestamp >= start,
                ExpedicaoVolumeEvento.timestamp < end_exclusive,
                Expedicao.pedido_id.in_(order_ids),
            )
        ).all()
        loaded_events_as_of_end = db.session.scalars(
            select(ExpedicaoVolumeEvento)
            .join(Expedicao, ExpedicaoVolumeEvento.expedicao_id == Expedicao.id)
            .where(
                ExpedicaoVolumeEvento.timestamp < end_exclusive,
                Expedicao.pedido_id.in_(order_ids),
            )
        ).all()

    reading_counts = {status.value: 0 for status in StatusLeitura}
    for read in reads:
        reading_counts[read.status.value] += 1

    conference_items = [item for conference in conferences for item in conference.itens]
    divergent_items = sum(
        item.quantidade_encontrada != item.quantidade_necessaria
        for item in conference_items
    )
    packaged_quantity = 0
    packaged_volume_count = 0
    for package in packages:
        packaged_volume_count += len(package.volumes)
        packaged_quantity += sum(
            item.quantidade
            for volume in package.volumes
            for item in volume.itens
        )

    loaded_volume_state: dict[tuple[int, int], bool] = {}
    for event in sorted(loaded_events_as_of_end, key=lambda value: (value.timestamp, value.id)):
        loaded_volume_state[(event.expedicao_id, event.embalagem_volume_id)] = (
            event.acao == "carregado"
        )

    events_by_cycle: dict[tuple[int, int], list[PedidoEstadoEvento]] = defaultdict(list)
    for event in events:
        if event.pedido_id in order_ids:
            events_by_cycle[(event.pedido_id, event.ciclo)].append(event)
    completed_durations = []
    completed_on_time = 0
    completed_late = 0
    overdue_orders = 0
    for order in orders:
        if order.prazo_entrega and order.prazo_entrega < current_day and order.status_fluxo != "expedido":
            overdue_orders += 1
        for (event_order_id, cycle), cycle_events in events_by_cycle.items():
            if event_order_id != order.id:
                continue
            start_at = order.criado_em if cycle == 1 else next(
                (
                    event.timestamp
                    for event in cycle_events
                    if event.estado_novo == "separacao"
                ),
                None,
            )
            finish = next(
                (
                    event
                    for event in reversed(cycle_events)
                    if event.estado_novo == "expedido"
                    and start <= event.timestamp < end_exclusive
                ),
                None,
            )
            if start_at is None or finish is None:
                continue
            duration_minutes = (finish.timestamp - start_at).total_seconds() / 60
            if duration_minutes >= 0:
                completed_durations.append(duration_minutes)
            if order.prazo_entrega:
                if finish.timestamp.date() <= order.prazo_entrega:
                    completed_on_time += 1
                else:
                    completed_late += 1

    events_in_period = [
        event
        for event in events
        if start <= event.timestamp < end_exclusive
    ]
    return {
        "order_count": len(orders),
        "orders_by_status": {
            flow_status: sum(order.status_fluxo == flow_status for order in orders)
            for flow_status in FLOW_STATUSES
        },
        "overdue_order_count": overdue_orders,
        "completed_on_time_count": completed_on_time,
        "completed_late_count": completed_late,
        "average_cycle_minutes": (
            round(sum(completed_durations) / len(completed_durations), 2)
            if completed_durations
            else None
        ),
        "measured_cycle_count": len(completed_durations),
        "reading_counts": reading_counts,
        "conference_count": len(conferences),
        "conference_divergence_rate": (
            round(divergent_items / len(conference_items) * 100, 2)
            if conference_items
            else None
        ),
        "conference_item_count": len(conference_items),
        "divergent_item_count": divergent_items,
        "packaged_volume_count": packaged_volume_count,
        "packaged_quantity": packaged_quantity,
        "loaded_volume_event_count": sum(event.acao == "carregado" for event in loaded_events),
        "reverted_volume_event_count": sum(event.acao == "revertido" for event in loaded_events),
        "currently_loaded_volume_count": sum(loaded_volume_state.values()),
        "state_transition_count": len(events_in_period),
        "legacy_order_count": db.session.scalar(
            select(db.func.count()).select_from(Pedido).where(Pedido.criado_em.is_(None))
        )
        or 0,
    }
