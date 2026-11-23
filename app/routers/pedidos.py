import uuid
from datetime import date, datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import selectinload

from app import db
from app.instance.models import (
    Conferencia,
    ConferenciaItem,
    Conjunto,
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

pedidos_bp = Blueprint("pedidos", __name__, url_prefix="/pedidos")


def _set_estado_fluxo(pedido, estado_novo, responsavel, *, ciclo=None):
    if pedido.status_fluxo == estado_novo:
        return
    timestamp = datetime.utcnow()
    db.session.add(
        PedidoEstadoEvento(
            pedido_id=pedido.id,
            ciclo=ciclo or pedido.ciclo_atual,
            estado_anterior=pedido.status_fluxo,
            estado_novo=estado_novo,
            responsavel=responsavel,
            timestamp=timestamp,
        )
    )
    pedido.status_fluxo = estado_novo


def _validar_responsavel(responsavel):
    return bool(responsavel) and len(responsavel) <= 100


def _parse_prazo(value):
    if not value:
        return None
    return date.fromisoformat(value)


def _render_carregamento(pedido, form_values=None):
    embalagem_atual = next(
        (embalagem for embalagem in pedido.embalagens if embalagem.ciclo == pedido.ciclo_atual),
        None,
    )
    expedicao_atual = next(
        (expedicao for expedicao in pedido.expedicoes if expedicao.ciclo == pedido.ciclo_atual),
        None,
    )
    volumes_carregados = expedicao_atual.volumes_carregados() if expedicao_atual else set()
    return render_template(
        "pedidos/carregamento.html",
        pedido=pedido,
        embalagem=embalagem_atual,
        expedicao=expedicao_atual,
        volumes_carregados=volumes_carregados,
        form_values=form_values or {},
    )


@pedidos_bp.route("/", methods=["GET"], endpoint="listar")
def listar():
    pedidos = (
        Pedido.query.options(
            selectinload(Pedido.itens),
            selectinload(Pedido.leituras),
        )
        .order_by(Pedido.codigo)
        .all()
    )
    progresso_por_pedido = {pedido.id: pedido.progresso() for pedido in pedidos}
    return render_template(
        "pedidos/listar.html",
        pedidos=pedidos,
        progresso_por_pedido=progresso_por_pedido,
    )


@pedidos_bp.route("/novo", methods=["GET", "POST"], endpoint="novo")
def novo():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        raw_deadline = request.form.get("prazo_entrega", "").strip()
        try:
            prazo_entrega = _parse_prazo(raw_deadline)
        except ValueError:
            flash("Informe um prazo de entrega válido.", "error")
            return render_template(
                "pedidos/form.html",
                pedido=Pedido(codigo=codigo),
                prazo_entrega=raw_deadline,
            )
        if not codigo:
            flash("Código do pedido é obrigatório.", "error")
            return render_template(
                "pedidos/form.html",
                pedido=Pedido(codigo=codigo),
                prazo_entrega=raw_deadline,
            )
        pedido = Pedido(codigo=codigo, prazo_entrega=prazo_entrega)
        db.session.add(pedido)
        try:
            db.session.commit()
            flash("Pedido adicionado com sucesso!", "success")
            return redirect(url_for("pedidos.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um pedido com esse código.", "error")

    return render_template("pedidos/form.html", pedido=None, prazo_entrega="")


@pedidos_bp.route("/editar/<int:pedido_id>", methods=["GET", "POST"], endpoint="editar")
def editar(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.status_fluxo in ("liberado", "embalado", "carregando", "carregado", "expedido"):
        flash("O código do pedido não pode ser alterado após a conferência ou a expedição.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        raw_deadline = request.form.get("prazo_entrega", "").strip()
        try:
            prazo_entrega = _parse_prazo(raw_deadline)
        except ValueError:
            flash("Informe um prazo de entrega válido.", "error")
            return render_template(
                "pedidos/form.html",
                pedido=Pedido(id=pedido.id, codigo=codigo),
                prazo_entrega=raw_deadline,
            )
        if not codigo:
            flash("Código do pedido é obrigatório.", "error")
            return render_template(
                "pedidos/form.html",
                pedido=Pedido(id=pedido.id, codigo=codigo),
                prazo_entrega=raw_deadline,
            )
        pedido.codigo = codigo
        pedido.prazo_entrega = prazo_entrega
        try:
            db.session.commit()
            flash("Pedido atualizado com sucesso!", "success")
            return redirect(url_for("pedidos.listar"))
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um pedido com esse código.", "error")
            return render_template(
                "pedidos/form.html",
                pedido=Pedido(id=pedido_id, codigo=codigo),
                prazo_entrega=raw_deadline,
            )

    return render_template("pedidos/form.html", pedido=pedido)


@pedidos_bp.route("/apagar/<int:pedido_id>", methods=["POST"], endpoint="apagar")
def apagar(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.leituras:
        flash("Não é possível apagar um pedido que possui leituras registradas.", "error")
        return redirect(url_for("pedidos.listar"))
    if pedido.embalagens:
        flash("Não é possível apagar um pedido que possui embalagens registradas.", "error")
        return redirect(url_for("pedidos.listar"))
    if pedido.expedicoes:
        flash("Não é possível apagar um pedido que possui carregamentos registrados.", "error")
        return redirect(url_for("pedidos.listar"))

    db.session.delete(pedido)
    try:
        db.session.commit()
        flash("Pedido excluído com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível excluir o pedido por causa de registros relacionados.", "error")

    return redirect(url_for("pedidos.listar"))


@pedidos_bp.route("/<int:pedido_id>/detalhe", methods=["GET"], endpoint="detalhe")
def detalhe(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    pecas_disponiveis = Peca.query.order_by(Peca.codigo).all()
    conjuntos_disponiveis = Conjunto.query.order_by(Conjunto.codigo).all()
    return render_template(
        "pedidos/detalhe.html",
        pedido=pedido,
        pecas_disponiveis=pecas_disponiveis,
        conjuntos_disponiveis=conjuntos_disponiveis,
        composicoes_pedido=pedido.composicoes,
        progresso=pedido.progresso(),
        progresso_por_item=pedido.progresso_por_item(),
        ultima_conferencia=pedido.conferencias[-1] if pedido.conferencias else None,
        embalagem_atual=next(
            (embalagem for embalagem in pedido.embalagens if embalagem.ciclo == pedido.ciclo_atual),
            None,
        ),
        expedicao_atual=next(
            (expedicao for expedicao in pedido.expedicoes if expedicao.ciclo == pedido.ciclo_atual),
            None,
        ),
    )


@pedidos_bp.route("/<int:pedido_id>/historico", methods=["GET"], endpoint="historico")
def historico(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    return render_template(
        "pedidos/historico.html",
        pedido=pedido,
        eventos=pedido.historico(),
        ciclo_atual=pedido.ciclo_atual,
    )


@pedidos_bp.route("/<int:pedido_id>/scanner", methods=["GET"], endpoint="scanner")
def scanner(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if not pedido.itens:
        flash("Adicione peças ou aplique um conjunto antes de iniciar a separação.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if pedido.status_fluxo in ("liberado", "embalado", "carregando", "carregado", "expedido"):
        flash("O pedido já concluiu a separação. Reabra-o para iniciar um novo ciclo.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    return render_template(
        "pedidos/scanner.html",
        pedido=pedido,
        progresso=pedido.progresso(),
        progresso_por_item=pedido.progresso_por_item(),
    )

@pedidos_bp.route("/<int:pedido_id>/scanner/validar", methods=["POST"], endpoint="validar_codigo")
def validar_codigo(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    payload = request.get_json(silent=True) if request.is_json else {}
    if not isinstance(payload, dict):
        payload = {}
    if not payload:
        payload = request.form.to_dict()

    codigo = str(payload.get("codigo") or payload.get("codigo_qr") or "").strip()
    responsavel = str(payload.get("responsavel") or "").strip()
    if not _validar_responsavel(responsavel):
        return jsonify({
            "status": "erro",
            "message": "Informe o responsável pela leitura (até 100 caracteres).",
            "progress": pedido.progresso(),
        }), 400
    if not codigo:
        return jsonify({
            "status": "erro",
            "message": "Código QR não informado.",
            "progress": pedido.progresso(),
        }), 400

    raw_idempotency_key = payload.get("idempotency_key")
    idempotency_key = None
    if raw_idempotency_key is not None:
        try:
            idempotency_key = str(uuid.UUID(str(raw_idempotency_key)))
        except (ValueError, AttributeError):
            return jsonify({
                "status": "erro",
                "message": "Chave de leitura inválida.",
                "progress": pedido.progresso(),
            }), 400

    def read_response(status, message, peca=None, *, replayed=False, response_status=200):
        response_payload = {
            "status": status.value if isinstance(status, StatusLeitura) else status,
            "message": message,
            "progress": pedido.progresso(),
            "progress_by_item": [
                {
                    "peca": {
                        "id": item["peca"].id,
                        "codigo": item["peca"].codigo,
                        "descricao": item["peca"].descricao,
                    },
                    "quantidade_necessaria": item["quantidade_necessaria"],
                    "quantidade_validada": item["quantidade_validada"],
                    "percentual": item["percentual"],
                }
                for item in pedido.progresso_por_item()
            ],
        }
        if peca is not None:
            response_payload["peca"] = {
                "id": peca.id,
                "codigo": peca.codigo,
                "descricao": peca.descricao,
            }
        if replayed:
            response_payload["replayed"] = True
        return jsonify(response_payload), response_status

    def replay_response(leitura):
        peca_lida = leitura.peca
        if codigo != peca_lida.codigo:
            return read_response(
                "erro",
                "A chave de leitura já foi usada para outro código.",
                response_status=409,
            )
        replay_messages = {
            StatusLeitura.SUCESSO: f"Peça {peca_lida.codigo} validada com sucesso para o pedido.",
            StatusLeitura.DUPLICADA: f"A peça {peca_lida.codigo} já foi separada na quantidade necessária para este pedido.",
            StatusLeitura.FORA_DO_PEDIDO: f"A peça {peca_lida.codigo} não pertence a este pedido.",
        }
        return read_response(
            leitura.status,
            replay_messages[leitura.status],
            peca_lida,
            replayed=True,
        )

    if idempotency_key:
        previous_read = Leitura.query.filter_by(
            pedido_id=pedido.id,
            idempotency_key=idempotency_key,
        ).first()
        if previous_read is not None:
            return replay_response(previous_read)

    if pedido.status_fluxo in ("liberado", "embalado", "carregando", "carregado", "expedido"):
        return read_response(
            "erro",
            "O pedido já concluiu a separação. Reabra-o antes de registrar novas leituras.",
            response_status=409,
        )
    if not pedido.itens:
        return read_response(
            "pedido_sem_itens",
            "Adicione peças ou aplique um conjunto antes de iniciar a separação.",
            response_status=409,
        )

    peca = Peca.query.filter_by(codigo=codigo).first()
    if peca is None:
        return read_response(
            "nao_cadastrado",
            "O código interno não corresponde a nenhuma peça cadastrada.",
        )

    item = PedidoItem.query.filter_by(pedido_id=pedido.id, peca_id=peca.id).first()
    if item is None:
        leitura = Leitura(
            pedido=pedido,
            peca=peca,
            status=StatusLeitura.FORA_DO_PEDIDO,
            ciclo=pedido.ciclo_atual,
            responsavel=responsavel,
            idempotency_key=idempotency_key,
        )
        db.session.add(leitura)
        message = f"A peça {peca.codigo} não pertence a este pedido."
        status = StatusLeitura.FORA_DO_PEDIDO
    else:
        leituras_sucesso = Leitura.query.filter_by(
            pedido_id=pedido.id,
            peca_id=peca.id,
            status=StatusLeitura.SUCESSO,
        ).count()
        quantidade_validada = min(
            item.quantidade_reconciliada
            + max(leituras_sucesso - item.leituras_referencia_reconciliacao, 0),
            item.quantidade_necessaria,
        )

        if quantidade_validada >= item.quantidade_necessaria:
            status = StatusLeitura.DUPLICADA
            message = f"A peça {peca.codigo} já foi separada na quantidade necessária para este pedido."
        else:
            status = StatusLeitura.SUCESSO
            message = f"Peça {peca.codigo} validada com sucesso para o pedido."

        leitura = Leitura(
            pedido=pedido,
            peca=peca,
            status=status,
            ciclo=pedido.ciclo_atual,
            responsavel=responsavel,
            idempotency_key=idempotency_key,
        )
        db.session.add(leitura)

    try:
        db.session.flush()
        if status == StatusLeitura.SUCESSO and pedido.progresso()["status"] == "finalizado":
            _set_estado_fluxo(pedido, "aguardando_conferencia", responsavel)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if idempotency_key:
            previous_read = Leitura.query.filter_by(
                pedido_id=pedido.id,
                idempotency_key=idempotency_key,
            ).first()
            if previous_read is not None:
                return replay_response(previous_read)
        raise

    return read_response(status, message, peca)


def _pedido_liberado(pedido):
    if pedido.status_fluxo in ("liberado", "embalado", "carregando", "carregado", "expedido"):
        flash("O pedido já concluiu a separação. Reabra-o antes de alterar os itens.", "error")
        return True
    return False


def _atualizar_estado_separacao(pedido, responsavel):
    if pedido.progresso()["status"] == "finalizado":
        _set_estado_fluxo(pedido, "aguardando_conferencia", responsavel)
    else:
        _set_estado_fluxo(pedido, "separacao", responsavel)


@pedidos_bp.route("/<int:pedido_id>/conferencia", methods=["GET", "POST"], endpoint="conferencia")
def conferencia(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.status_fluxo == "liberado":
        flash("Este pedido já está liberado para expedição.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if pedido.progresso()["status"] != "finalizado":
        flash("A conferência só pode ser feita quando todas as quantidades estiverem separadas.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    if pedido.status_fluxo not in ("aguardando_conferencia", "correcao"):
        flash("O pedido ainda não está disponível para conferência.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    if request.method == "GET":
        return render_template(
            "pedidos/conferencia.html",
            pedido=pedido,
            progresso_por_item=pedido.progresso_por_item(),
        )

    conferente = request.form.get("conferente", "").strip()
    if not conferente or len(conferente) > 100:
        flash("Informe o nome do conferente (até 100 caracteres).", "error")
        return render_template(
            "pedidos/conferencia.html",
            pedido=pedido,
            progresso_por_item=pedido.progresso_por_item(),
        )

    resultados = []
    divergencias = False
    for item in pedido.itens:
        try:
            quantidade_encontrada = int(request.form.get(f"quantidade_{item.id}", ""))
        except ValueError:
            flash(f"Informe a quantidade física encontrada para a peça {item.peca.codigo}.", "error")
            return render_template(
                "pedidos/conferencia.html",
                pedido=pedido,
                progresso_por_item=pedido.progresso_por_item(),
            )
        if quantidade_encontrada < 0:
            flash("A quantidade encontrada não pode ser negativa.", "error")
            return render_template(
                "pedidos/conferencia.html",
                pedido=pedido,
                progresso_por_item=pedido.progresso_por_item(),
            )

        motivo = request.form.get(f"motivo_{item.id}", "").strip()
        diverge = quantidade_encontrada != item.quantidade_necessaria
        if diverge and not motivo:
            flash(f"Informe o motivo da divergência da peça {item.peca.codigo}.", "error")
            return render_template(
                "pedidos/conferencia.html",
                pedido=pedido,
                progresso_por_item=pedido.progresso_por_item(),
            )
        if len(motivo) > 500:
            flash("O motivo da divergência deve ter no máximo 500 caracteres.", "error")
            return render_template(
                "pedidos/conferencia.html",
                pedido=pedido,
                progresso_por_item=pedido.progresso_por_item(),
            )

        divergencias = divergencias or diverge
        resultados.append((item, quantidade_encontrada, motivo or None))

    tentativa = Conferencia(
        pedido_id=pedido.id,
        ciclo=pedido.ciclo_atual,
        conferente=conferente,
        resultado="reprovada" if divergencias else "aprovada",
    )
    db.session.add(tentativa)
    db.session.flush()

    for item, quantidade_encontrada, motivo in resultados:
        db.session.add(
            ConferenciaItem(
                conferencia_id=tentativa.id,
                pedido_item_id=item.id,
                codigo_peca=item.peca.codigo,
                descricao_peca=item.peca.descricao,
                quantidade_necessaria=item.quantidade_necessaria,
                quantidade_encontrada=quantidade_encontrada,
                motivo_divergencia=motivo,
            )
        )
        if divergencias:
            item.quantidade_reconciliada = min(quantidade_encontrada, item.quantidade_necessaria)
            item.leituras_referencia_reconciliacao = Leitura.query.filter_by(
                pedido_id=pedido.id,
                peca_id=item.peca_id,
                status=StatusLeitura.SUCESSO,
            ).count()

    _set_estado_fluxo(pedido, "correcao" if divergencias else "liberado", conferente)
    db.session.commit()

    if divergencias:
        flash("Conferência reprovada. Corrija as divergências e faça uma nova conferência.", "error")
    else:
        flash("Conferência aprovada. Pedido liberado para expedição.", "success")
    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/embalagem", methods=["GET", "POST"], endpoint="embalagem")
def embalagem(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)

    def render_form(volume_ids):
        volumes = [
            {
                "id": volume_id,
                "quantidades": {
                    item.id: request.form.get(f"volume_{volume_id}_item_{item.id}", "0")
                    for item in pedido.itens
                },
            }
            for volume_id in volume_ids
        ]
        return render_template(
            "pedidos/embalagem.html",
            pedido=pedido,
            volumes=volumes,
            responsavel=request.form.get("responsavel", ""),
            observacao=request.form.get("observacao", ""),
        )

    if pedido.status_fluxo != "liberado":
        flash("A embalagem só pode ser registrada após a conferência aprovada.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    conferencia_aprovada = Conferencia.query.filter_by(
        pedido_id=pedido.id,
        ciclo=pedido.ciclo_atual,
        resultado="aprovada",
    ).order_by(Conferencia.id.desc()).first()
    if conferencia_aprovada is None:
        flash("Não há conferência aprovada no ciclo atual para liberar a embalagem.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    if any(embalagem.ciclo == pedido.ciclo_atual for embalagem in pedido.embalagens):
        flash("Este pedido já possui uma embalagem registrada no ciclo atual.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    if request.method == "GET":
        return render_form([1])

    responsavel = request.form.get("responsavel", "").strip()
    observacao = request.form.get("observacao", "").strip()
    if not responsavel or len(responsavel) > 100:
        flash("Informe o responsável pela embalagem (até 100 caracteres).", "error")
        return render_form(request.form.getlist("volume_id") or [1])
    if len(observacao) > 500:
        flash("A observação deve ter no máximo 500 caracteres.", "error")
        return render_form(request.form.getlist("volume_id") or [1])

    raw_volume_ids = request.form.getlist("volume_id")
    try:
        volume_ids = [int(value) for value in raw_volume_ids]
    except ValueError:
        flash("A lista de volumes é inválida.", "error")
        return render_form([1])
    if not volume_ids or any(volume_id < 1 for volume_id in volume_ids):
        flash("Adicione ao menos um volume válido.", "error")
        return render_form(volume_ids or [1])
    if len(volume_ids) != len(set(volume_ids)):
        flash("Os números dos volumes devem ser únicos.", "error")
        return render_form(volume_ids)

    quantities_by_volume = {}
    totals_by_item = {item.id: 0 for item in pedido.itens}
    for volume_id in volume_ids:
        quantities = {}
        for item in pedido.itens:
            field_name = f"volume_{volume_id}_item_{item.id}"
            try:
                quantity = int(request.form.get(field_name, "0"))
            except ValueError:
                flash(f"Informe uma quantidade inteira para a peça {item.peca.codigo}.", "error")
                return render_form(volume_ids)
            if quantity < 0:
                flash("As quantidades por volume não podem ser negativas.", "error")
                return render_form(volume_ids)
            quantities[item.id] = quantity
            totals_by_item[item.id] += quantity
        if not any(quantities.values()):
            flash(f"Informe ao menos uma peça no volume {volume_id}.", "error")
            return render_form(volume_ids)
        quantities_by_volume[volume_id] = quantities

    for item in pedido.itens:
        if totals_by_item[item.id] != item.quantidade_necessaria:
            flash(
                f"A soma da peça {item.peca.codigo} nos volumes deve ser "
                f"{item.quantidade_necessaria}; recebido: {totals_by_item[item.id]}.",
                "error",
            )
            return render_form(volume_ids)

    nova_embalagem = Embalagem(
        pedido_id=pedido.id,
        ciclo=pedido.ciclo_atual,
        responsavel=responsavel,
        observacao=observacao or None,
    )
    db.session.add(nova_embalagem)
    for numero, volume_id in enumerate(volume_ids, start=1):
        volume = EmbalagemVolume(numero=numero)
        nova_embalagem.volumes.append(volume)
        for item in pedido.itens:
            quantidade = quantities_by_volume[volume_id][item.id]
            if quantidade:
                volume.itens.append(
                    EmbalagemVolumeItem(
                        pedido_item_id=item.id,
                        codigo_peca=item.peca.codigo,
                        descricao_peca=item.peca.descricao,
                        quantidade=quantidade,
                    )
                )

    _set_estado_fluxo(pedido, "embalado", responsavel)
    try:
        db.session.commit()
        flash("Embalagem registrada. Pedido pronto para carregamento.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Falha ao registrar embalagem do pedido %s.", pedido.id)
        flash("Não foi possível registrar a embalagem do pedido.", "error")
        return render_form(volume_ids)
    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/carregamento", methods=["GET"], endpoint="carregamento")
def carregamento(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    embalagem_atual = next(
        (embalagem for embalagem in pedido.embalagens if embalagem.ciclo == pedido.ciclo_atual),
        None,
    )
    if embalagem_atual is None:
        flash("O carregamento só pode começar após a embalagem completa do ciclo atual.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if pedido.status_fluxo not in ("embalado", "carregando", "carregado", "expedido"):
        flash("Este pedido não está disponível para carregamento.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    return _render_carregamento(pedido)


@pedidos_bp.route(
    "/<int:pedido_id>/carregamento/volumes/<int:volume_id>",
    methods=["POST"],
    endpoint="carregar_volume",
)
def carregar_volume(pedido_id, volume_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    embalagem_atual = next(
        (embalagem for embalagem in pedido.embalagens if embalagem.ciclo == pedido.ciclo_atual),
        None,
    )
    if embalagem_atual is None or pedido.status_fluxo not in ("embalado", "carregando", "carregado"):
        flash("O pedido não possui uma embalagem disponível para carregamento neste ciclo.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    volume = next((volume for volume in embalagem_atual.volumes if volume.id == volume_id), None)
    if volume is None:
        abort(404)

    expedicao_atual = next(
        (expedicao for expedicao in pedido.expedicoes if expedicao.ciclo == pedido.ciclo_atual),
        None,
    )
    if expedicao_atual and expedicao_atual.saida is not None:
        flash("A saída já foi registrada; o carregamento não pode ser alterado.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    responsavel = request.form.get("responsavel", "").strip()
    observacao = request.form.get("observacao", "").strip()
    if not responsavel or len(responsavel) > 100:
        flash("Informe o responsável pelo carregamento (até 100 caracteres).", "error")
        return _render_carregamento(
            pedido,
            {**request.form.to_dict(), "_acao": "carregar", "_volume_id": str(volume.id)},
        )
    if len(observacao) > 500:
        flash("A observação deve ter no máximo 500 caracteres.", "error")
        return _render_carregamento(
            pedido,
            {**request.form.to_dict(), "_acao": "carregar", "_volume_id": str(volume.id)},
        )

    if expedicao_atual is None:
        placa_veiculo = request.form.get("placa_veiculo", "").strip().upper()
        motorista_transportadora = request.form.get("motorista_transportadora", "").strip()
        if not placa_veiculo or len(placa_veiculo) > 20:
            flash("Informe a placa do veículo (até 20 caracteres).", "error")
            return _render_carregamento(
                pedido,
                {**request.form.to_dict(), "_acao": "carregar", "_volume_id": str(volume.id)},
            )
        if not motorista_transportadora or len(motorista_transportadora) > 120:
            flash("Informe o motorista ou a transportadora (até 120 caracteres).", "error")
            return _render_carregamento(
                pedido,
                {**request.form.to_dict(), "_acao": "carregar", "_volume_id": str(volume.id)},
            )
        expedicao_atual = Expedicao(
            pedido_id=pedido.id,
            embalagem_id=embalagem_atual.id,
            ciclo=pedido.ciclo_atual,
            placa_veiculo=placa_veiculo,
            motorista_transportadora=motorista_transportadora,
        )
        db.session.add(expedicao_atual)

    if volume.id in expedicao_atual.volumes_carregados():
        flash(f"O volume {volume.numero} já está marcado como carregado.", "error")
        return redirect(url_for("pedidos.carregamento", pedido_id=pedido.id))

    expedicao_atual.eventos_carga.append(
        ExpedicaoVolumeEvento(
            volume=volume,
            acao="carregado",
            responsavel=responsavel,
            observacao=observacao or None,
        )
    )
    volumes_carregados = expedicao_atual.volumes_carregados()
    volumes_ids = {volume_item.id for volume_item in embalagem_atual.volumes}
    _set_estado_fluxo(
        pedido,
        "carregado" if volumes_carregados == volumes_ids else "carregando",
        responsavel,
    )
    try:
        db.session.commit()
        flash(f"Volume {volume.numero} marcado como carregado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível registrar o carregamento do volume.", "error")
        return _render_carregamento(
            Pedido.query.get_or_404(pedido_id),
            {**request.form.to_dict(), "_acao": "carregar", "_volume_id": str(volume_id)},
        )
    return redirect(url_for("pedidos.carregamento", pedido_id=pedido.id))


@pedidos_bp.route(
    "/<int:pedido_id>/carregamento/volumes/<int:volume_id>/reverter",
    methods=["POST"],
    endpoint="reverter_carregamento",
)
def reverter_carregamento(pedido_id, volume_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    embalagem_atual = next(
        (embalagem for embalagem in pedido.embalagens if embalagem.ciclo == pedido.ciclo_atual),
        None,
    )
    expedicao_atual = next(
        (expedicao for expedicao in pedido.expedicoes if expedicao.ciclo == pedido.ciclo_atual),
        None,
    )
    if (
        embalagem_atual is None
        or expedicao_atual is None
        or pedido.status_fluxo not in ("carregando", "carregado")
    ):
        flash("Não há carregamento ativo para reverter neste ciclo.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if expedicao_atual.saida is not None:
        flash("A saída já foi registrada; o carregamento não pode ser revertido.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    volume = next((volume for volume in embalagem_atual.volumes if volume.id == volume_id), None)
    if volume is None:
        abort(404)
    if volume.id not in expedicao_atual.volumes_carregados():
        flash(f"O volume {volume.numero} não está marcado como carregado.", "error")
        return redirect(url_for("pedidos.carregamento", pedido_id=pedido.id))

    responsavel = request.form.get("responsavel", "").strip()
    observacao = request.form.get("observacao", "").strip()
    if not responsavel or len(responsavel) > 100:
        flash("Informe o responsável pela reversão (até 100 caracteres).", "error")
        return _render_carregamento(
            pedido,
            {**request.form.to_dict(), "_acao": "reverter", "_volume_id": str(volume.id)},
        )
    if len(observacao) > 500:
        flash("A observação deve ter no máximo 500 caracteres.", "error")
        return _render_carregamento(
            pedido,
            {**request.form.to_dict(), "_acao": "reverter", "_volume_id": str(volume.id)},
        )

    expedicao_atual.eventos_carga.append(
        ExpedicaoVolumeEvento(
            volume=volume,
            acao="revertido",
            responsavel=responsavel,
            observacao=observacao or None,
        )
    )
    _set_estado_fluxo(
        pedido,
        "carregando" if expedicao_atual.volumes_carregados() else "embalado",
        responsavel,
    )
    try:
        db.session.commit()
        flash(f"Carregamento do volume {volume.numero} revertido e registrado no histórico.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível reverter o carregamento do volume.", "error")
        return _render_carregamento(
            Pedido.query.get_or_404(pedido_id),
            {**request.form.to_dict(), "_acao": "reverter", "_volume_id": str(volume_id)},
        )
    return redirect(url_for("pedidos.carregamento", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/expedir", methods=["POST"], endpoint="expedir")
def expedir(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    embalagem_atual = next(
        (embalagem for embalagem in pedido.embalagens if embalagem.ciclo == pedido.ciclo_atual),
        None,
    )
    expedicao_atual = next(
        (expedicao for expedicao in pedido.expedicoes if expedicao.ciclo == pedido.ciclo_atual),
        None,
    )
    if (
        pedido.status_fluxo != "carregado"
        or embalagem_atual is None
        or expedicao_atual is None
        or expedicao_atual.saida is not None
    ):
        flash("A saída só pode ser registrada depois que todos os volumes forem carregados.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    volumes_ids = {volume.id for volume in embalagem_atual.volumes}
    if expedicao_atual.volumes_carregados() != volumes_ids:
        flash("O carregamento está incompleto. Confira todos os volumes antes da saída.", "error")
        return redirect(url_for("pedidos.carregamento", pedido_id=pedido.id))

    responsavel = request.form.get("responsavel", "").strip()
    observacao = request.form.get("observacao", "").strip()
    if not responsavel or len(responsavel) > 100:
        flash("Informe o responsável pela saída (até 100 caracteres).", "error")
        return _render_carregamento(
            pedido,
            {**request.form.to_dict(), "_acao": "saida"},
        )
    if len(observacao) > 500:
        flash("A observação deve ter no máximo 500 caracteres.", "error")
        return _render_carregamento(
            pedido,
            {**request.form.to_dict(), "_acao": "saida"},
        )

    expedicao_atual.saida = ExpedicaoSaida(
        responsavel=responsavel,
        observacao=observacao or None,
    )
    _set_estado_fluxo(pedido, "expedido", responsavel)
    try:
        db.session.commit()
        flash("Saída registrada. Pedido expedido e encerrado.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível registrar a saída do pedido.", "error")
        return _render_carregamento(
            Pedido.query.get_or_404(pedido_id),
            {**request.form.to_dict(), "_acao": "saida"},
        )
    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/reabrir", methods=["POST"], endpoint="reabrir")
def reabrir(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.status_fluxo not in ("liberado", "embalado", "carregando", "carregado"):
        flash("Somente pedidos ainda não expedidos podem ser reabertos.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    responsavel = request.form.get("responsavel", "").strip()
    if not _validar_responsavel(responsavel):
        flash("Informe o responsável pela reabertura (até 100 caracteres).", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    novo_ciclo = pedido.ciclo_atual + 1
    db.session.add(
        PedidoReabertura(
            pedido_id=pedido.id,
            ciclo=novo_ciclo,
        )
    )
    for item in pedido.itens:
        item.quantidade_reconciliada = 0
        item.leituras_referencia_reconciliacao = Leitura.query.filter_by(
            pedido_id=pedido.id,
            peca_id=item.peca_id,
            status=StatusLeitura.SUCESSO,
        ).count()
    _set_estado_fluxo(pedido, "separacao", responsavel, ciclo=novo_ciclo)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Falha ao reabrir pedido %s.", pedido_id)
        flash("Não foi possível reabrir o pedido. Nenhuma alteração foi aplicada.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido_id))
    flash("Pedido reaberto. Será necessário refazer a separação e a conferência.", "success")
    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route(
    "/<int:pedido_id>/conjuntos/adicionar",
    methods=["POST"],
    endpoint="adicionar_conjunto",
)
def adicionar_conjunto(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if pedido.status_fluxo != "separacao" or pedido.leituras or pedido.conferencias:
        flash("Conjuntos só podem ser aplicados antes de qualquer leitura ou conferência.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    try:
        conjunto_id = int(request.form.get("conjunto_id", ""))
        quantidade = int(request.form.get("quantidade", "1"))
    except ValueError:
        flash("Selecione um conjunto e informe uma quantidade inteira positiva.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if quantidade < 1:
        flash("A quantidade deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    conjunto = Conjunto.query.get_or_404(conjunto_id)
    try:
        itens_expandidos = conjunto.expandir_pecas(quantidade)
    except ValueError as error:
        flash(str(error), "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if not itens_expandidos:
        flash(f"O conjunto {conjunto.codigo} não possui peças para adicionar ao pedido.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    db.session.add(
        PedidoConjunto(
            pedido_id=pedido.id,
            conjunto_id=conjunto.id,
            codigo_conjunto=conjunto.codigo,
            descricao_conjunto=conjunto.descricao,
            quantidade=quantidade,
        )
    )
    for peca_id, quantidade_peca in itens_expandidos.items():
        item = PedidoItem.query.filter_by(pedido_id=pedido.id, peca_id=peca_id).first()
        if item:
            item.quantidade_necessaria += quantidade_peca
        else:
            db.session.add(
                PedidoItem(
                    pedido_id=pedido.id,
                    peca_id=peca_id,
                    quantidade_necessaria=quantidade_peca,
                )
            )

    try:
        db.session.commit()
        flash(
            f"Composição de {quantidade} unidade(s) do conjunto {conjunto.codigo} aplicada ao pedido.",
            "success",
        )
    except IntegrityError:
        db.session.rollback()
        flash("Não foi possível aplicar a composição do conjunto ao pedido.", "error")
    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/itens/adicionar", methods=["POST"], endpoint="adicionar_item")
def adicionar_item(pedido_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if _pedido_liberado(pedido):
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    try:
        peca_id = int(request.form.get("peca_id", ""))
        quantidade = int(request.form.get("quantidade_necessaria", "1"))
    except ValueError:
        flash("Selecione uma peça e informe uma quantidade inteira positiva.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    if peca_id < 1:
        flash("Selecione uma peça para adicionar ao pedido.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if quantidade < 1:
        flash("A quantidade deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    responsavel = request.form.get("responsavel", "").strip()
    if not _validar_responsavel(responsavel):
        flash("Informe o responsável pela alteração (até 100 caracteres).", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    peca = Peca.query.get_or_404(peca_id)
    item = PedidoItem.query.filter_by(pedido_id=pedido.id, peca_id=peca.id).first()
    if item:
        item.quantidade_necessaria += quantidade
    else:
        db.session.add(PedidoItem(pedido_id=pedido.id, peca_id=peca.id, quantidade_necessaria=quantidade))

    try:
        db.session.flush()
        _atualizar_estado_separacao(pedido, responsavel)
        db.session.commit()
        flash("Item adicionado ao pedido com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao adicionar item ao pedido.", "error")

    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/itens/editar/<int:item_id>", methods=["POST"], endpoint="editar_item")
def editar_item(pedido_id, item_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if _pedido_liberado(pedido):
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    item = PedidoItem.query.filter_by(id=item_id, pedido_id=pedido.id).first_or_404()
    try:
        quantidade = int(request.form.get("quantidade_necessaria", ""))
    except ValueError:
        flash("A quantidade deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    if quantidade < 1:
        flash("A quantidade deve ser um número inteiro maior que zero.", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    responsavel = request.form.get("responsavel", "").strip()
    if not _validar_responsavel(responsavel):
        flash("Informe o responsável pela alteração (até 100 caracteres).", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))

    item.quantidade_necessaria = quantidade
    try:
        db.session.flush()
        _atualizar_estado_separacao(pedido, responsavel)
        db.session.commit()
        flash("Quantidade atualizada com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao atualizar quantidade.", "error")

    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


@pedidos_bp.route("/<int:pedido_id>/itens/remover/<int:item_id>", methods=["POST"], endpoint="remover_item")
def remover_item(pedido_id, item_id):
    pedido = Pedido.query.get_or_404(pedido_id)
    if _pedido_liberado(pedido):
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    responsavel = request.form.get("responsavel", "").strip()
    if not _validar_responsavel(responsavel):
        flash("Informe o responsável pela alteração (até 100 caracteres).", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    item = PedidoItem.query.filter_by(id=item_id, pedido_id=pedido.id).first_or_404()
    responsavel = request.form.get("responsavel", "").strip()
    if not _validar_responsavel(responsavel):
        flash("Informe o responsável pela alteração (até 100 caracteres).", "error")
        return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))
    db.session.delete(item)
    try:
        db.session.flush()
        _atualizar_estado_separacao(pedido, responsavel)
        db.session.commit()
        flash("Item removido do pedido com sucesso!", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Erro ao remover item do pedido.", "error")

    return redirect(url_for("pedidos.detalhe", pedido_id=pedido.id))


listar_pedidos = listar
adicionar_pedido = novo
editar_pedido = editar
excluir_pedido = apagar
detalhes_pedido = detalhe
listar_pecas_pedido = detalhe
adicionar_item_pedido = adicionar_item