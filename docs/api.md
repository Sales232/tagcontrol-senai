# Rotas e contrato do scanner

As rotas abaixo são derivadas dos blueprints em `app/routers/`. As rotas de peças, conjuntos e pedidos servem HTML ou recebem formulários (`application/x-www-form-urlencoded` ou formulário equivalente), não são endpoints REST JSON. Escritas de formulário usam `POST`; os resultados de sucesso normalmente usam mensagens flash e redirecionamento.

`{peca_id}`, `{conjunto_id}`, `{pedido_id}`, `{assoc_id}` e `{item_id}` são identificadores inteiros. Identificadores que não existem retornam 404 pelo helper `get_or_404`/`first_or_404`.

## Peças (`/pecas`)

| Método | Caminho | Comportamento |
| --- | --- | --- |
| GET | `/pecas/` | Lista peças ordenadas por código. |
| GET, POST | `/pecas/novo` | Exibe formulário ou cria peça; código interno e descrição são obrigatórios. O código interno é único e também é o conteúdo do QR Code. Após salvar, redireciona à etiqueta imprimível. |
| GET, POST | `/pecas/editar/{peca_id}` | Exibe formulário ou atualiza a peça. |
| GET | `/pecas/{peca_id}/etiqueta` | Exibe etiqueta sob demanda, com QR, código interno, descrição e ação de impressão. |
| GET | `/pecas/{peca_id}/qr.svg` | Gera o QR Code em SVG a partir do código interno. |
| POST | `/pecas/apagar/{peca_id}` | Exclui a peça se não tiver associações ou leituras. |

## Conjuntos (`/conjuntos`)

| Método | Caminho | Comportamento |
| --- | --- | --- |
| GET | `/conjuntos/` | Lista conjuntos ordenados por código. |
| GET, POST | `/conjuntos/novo` | Exibe formulário ou cria conjunto. |
| GET, POST | `/conjuntos/editar/{conjunto_id}` | Exibe formulário ou atualiza conjunto. |
| POST | `/conjuntos/apagar/{conjunto_id}` | Exclui conjunto e seus componentes; bloqueia conjuntos usados como subconjunto ou registrados na composição de um pedido. |
| GET | `/conjuntos/{conjunto_id}/detalhe` | Exibe peças e subconjuntos associados, além de componentes que ainda podem ser adicionados. |
| POST | `/conjuntos/{conjunto_id}/pecas/adicionar` | Adiciona peça com `peca_id` e `quantidade`; quantidade deve ser inteira positiva; se já existir no conjunto, soma a quantidade. |
| POST | `/conjuntos/{conjunto_id}/subconjuntos/adicionar` | Adiciona subconjunto com `subconjunto_id` e `quantidade` positiva; rejeita associações circulares e soma a quantidade quando já associado. |
| POST | `/conjuntos/{conjunto_id}/pecas/editar/{assoc_id}` | Define a nova quantidade positiva de uma peça ou subconjunto associado. |
| POST | `/conjuntos/{conjunto_id}/pecas/remover/{assoc_id}` | Remove uma peça ou subconjunto associado. |

## Pedidos (`/pedidos`)

| Método | Caminho | Comportamento |
| --- | --- | --- |
| GET | `/pedidos/` | Lista pedidos ordenados por código. |
| GET, POST | `/pedidos/novo` | Exibe formulário ou cria pedido. |
| GET, POST | `/pedidos/editar/{pedido_id}` | Exibe formulário ou atualiza pedido. |
| POST | `/pedidos/apagar/{pedido_id}` | Exclui pedido sem leituras; a aplicação bloqueia exclusão quando há histórico de leitura. |
| GET | `/pedidos/{pedido_id}/detalhe` | Exibe itens, progresso total e progresso por item. |
| GET | `/pedidos/{pedido_id}/historico` | Exibe a linha do tempo de leituras, conferências, divergências e reaberturas, ordenada por data/hora UTC. Eventos antigos sem ciclo são mostrados como histórico legado não classificado. |
| GET | `/pedidos/{pedido_id}/scanner` | Exibe interface do scanner e progresso atual; redireciona ao detalhe se o pedido não tiver itens ou já tiver concluído a separação/conferência. |
| POST | `/pedidos/{pedido_id}/itens/adicionar` | Recebe `peca_id` e `quantidade_necessaria` positiva; soma à quantidade existente para a mesma peça. |
| POST | `/pedidos/{pedido_id}/conjuntos/adicionar` | Recebe `conjunto_id` e `quantidade` positiva; expande recursivamente peças e subconjuntos, soma quantidades repetidas aos itens existentes e registra um snapshot da composição selecionada. Disponível apenas antes de qualquer leitura ou conferência. |
| POST | `/pedidos/{pedido_id}/itens/editar/{item_id}` | Define nova `quantidade_necessaria` positiva. |
| POST | `/pedidos/{pedido_id}/itens/remover/{item_id}` | Remove item do pedido. |
| POST | `/pedidos/{pedido_id}/scanner/validar` | Valida o código interno lido do QR Code e retorna JSON conforme contrato abaixo. |
| GET, POST | `/pedidos/{pedido_id}/conferencia` | Exibe e registra checklist final, disponível com todas as quantidades separadas; exige nome do conferente e quantidade física por item. Divergências exigem motivo. |
| GET, POST | `/pedidos/{pedido_id}/embalagem` | Exibe e registra embalagem depois da conferência aprovada no ciclo atual; recebe responsável, observação opcional, volumes e quantidade por item em cada volume. |
| GET | `/pedidos/{pedido_id}/carregamento` | Exibe os volumes da embalagem do ciclo atual e o respectivo estado de carregamento/saída. |
| POST | `/pedidos/{pedido_id}/carregamento/volumes/{volume_id}` | Marca um volume da embalagem atual como carregado; no primeiro carregamento exige placa, motorista/transportadora e responsável. |
| POST | `/pedidos/{pedido_id}/carregamento/volumes/{volume_id}/reverter` | Reverte uma marcação de carregamento antes da saída, exigindo responsável; preserva o evento anterior no histórico. |
| POST | `/pedidos/{pedido_id}/expedir` | Registra a saída separadamente, exigindo que todos os volumes estejam carregados e nome do responsável. |
| POST | `/pedidos/{pedido_id}/reabrir` | Reabre pedidos liberados, embalados ou em carregamento antes da saída, registra início do próximo ciclo e preserva eventos anteriores; pedidos expedidos não podem ser reabertos. |
| GET | `/indicadores/` | Exibe indicadores agregados; aceita `inicio` e `fim` no formato ISO `YYYY-MM-DD` e `estado` opcional com um estado atual válido. Datas inválidas ou invertidas retornam 400. |
| GET | `/` | Exibe o painel inicial com contagens de peças, conjuntos e pedidos, além de atalhos para os fluxos principais. |

## Importação e exportação CSV

`GET /dados/exportar.csv` gera um CSV de formato 3, sem campo QR independente: peças exportam código interno e descrição, e o código interno é usado como conteúdo do QR. `POST /dados/importar` importa esse formato e também aceita CSV de formato 2, descartando o QR legado e preservando o código interno. A importação rejeita códigos internos inválidos ou duplicados.

Itens de pedidos liberados, embalados, em carregamento, carregados ou expedidos não podem ser adicionados, editados ou removidos. A listagem de pedidos mostra quantidade validada/necessária e percentual, independentemente da etapa do fluxo. A conferência aprovada libera a embalagem; depois da embalagem completa, o sistema acompanha o carregamento por volume e a confirmação de saída.

### Composição dos pedidos

Conjuntos podem conter peças e outros conjuntos. Ao aplicar um conjunto ao pedido, a expansão multiplica as quantidades ao longo da hierarquia e consolida todas as ocorrências da mesma peça em uma única linha de item. A quantidade manual que já existir para essa peça também é somada. A composição selecionada guarda código, descrição e quantidade de conjuntos como snapshot; os itens materializados no pedido não são recalculados quando o catálogo muda.

### Conferência final

O formulário recebe `conferente`, `quantidade_{item_id}` para cada item e, quando houver divergência, `motivo_{item_id}`. Quantidades encontradas devem ser inteiros não negativos; o motivo é limitado a 500 caracteres. Uma tentativa é aprovada apenas quando cada quantidade física coincide com a quantidade necessária.

Tentativas aprovadas ou reprovadas e suas linhas são persistidas como histórico com snapshots de código, descrição e quantidades. Em caso de reprovação, a quantidade encontrada é reconciliada como base operacional (limitada à quantidade necessária para o progresso), e somente leituras bem-sucedidas posteriores ao marco da tentativa contam como separação complementar. Leituras antigas não são apagadas. Quando as quantidades voltam a estar completas, é necessário registrar nova conferência de todo o pedido.

O nome do conferente é digitado manualmente; não há autenticação. Reabrir explicitamente um pedido liberado invalida o resultado e zera o progresso operacional, mantendo leituras e conferências anteriores como histórico.

### Histórico do pedido

A página `GET /pedidos/{pedido_id}/historico` reúne eventos persistidos sem duplicar os registros operacionais: leituras de sucesso, duplicadas e fora do pedido; tentativas de conferência; linhas divergentes com snapshots da peça, quantidades, conferente e motivo; reaberturas; embalagens; eventos de carregamento/reversão e saídas. Os eventos são exibidos em ordem cronológica, com desempate determinístico, e a data/hora é rotulada como UTC. Leituras e conferências novas são associadas ao ciclo atual; cada reabertura inicia o próximo ciclo.

Registros anteriores à implantação do acompanhamento de ciclos permanecem com o ciclo vazio e são agrupados visualmente como “Histórico legado — ciclo não identificado”. O sistema não infere a qual ciclo esses eventos pertencem. Tentativas de códigos não cadastrados não aparecem porque não são persistidas.

### Embalagem, carregamento e saída

`GET/POST /pedidos/{pedido_id}/embalagem` só está disponível para pedido liberado por uma conferência aprovada no ciclo atual e sem embalagem já registrada. O formulário recebe `responsavel`, `observacao` opcional e uma lista repetida `volume_id`. Para cada volume e item do pedido, recebe `volume_{volume_id}_item_{item_id}` como inteiro não negativo. Cada volume deve conter ao menos uma peça e a soma por peça entre todos os volumes deve coincidir exatamente com a quantidade necessária do pedido. A operação grava embalagem, volumes, conteúdo e estado `embalado` na mesma transação.

O carregamento só pode usar volumes da embalagem completa do ciclo atual. Cada `POST /pedidos/{pedido_id}/carregamento/volumes/{volume_id}` recebe `responsavel` e `observacao` opcional; a primeira confirmação também exige `placa_veiculo` e `motorista_transportadora`, armazenados para aquela expedição/ciclo. Cada ação gera evento com horário UTC. O último evento de cada volume determina se ele está carregado. A reversão exige `responsavel`, aceita `observacao` opcional e é bloqueada depois da saída.

`POST /pedidos/{pedido_id}/expedir` recebe `responsavel` e `observacao` opcional. Só registra a saída quando todos os volumes estão carregados; em caso de sucesso o estado passa a `expedido` e as alterações e reaberturas são bloqueadas. Erros de validação dos campos de carregamento, reversão e saída reapresentam os valores enviados no formulário. Antes da saída, reabrir diretamente preserva a embalagem e os eventos de carregamento no ciclo anterior; o novo ciclo exige nova conferência e embalagem. A linha do tempo apresenta esses eventos em UTC.

## Validação JSON do scanner

### Requisição

`POST /pedidos/{pedido_id}/scanner/validar` aceita JSON ou campos de formulário. O código interno lido pode ser enviado nas chaves `codigo` ou `codigo_qr` (compatibilidade de nome com clientes antigos); `responsavel` é obrigatório para registrar qualquer leitura e aceita até 100 caracteres. A peça é localizada somente pelo código interno, que é o conteúdo do QR Code.

Exemplo JSON:

```json
{
  "codigo": "PEC-001",
  "responsavel": "Operador"
}
```

### Resposta

O payload inclui `status`, `message`, `progress` e `progress_by_item`. Quando o código identifica uma peça cadastrada, inclui também `peca` com `id`, `codigo` e `descricao`.

`progress` tem os campos `total_necessario`, `quantidade_validada`, `percentual` e `status` (veja [modelo-de-dados.md](./modelo-de-dados.md#cálculo-do-progresso)).

`progress_by_item` é uma lista de objetos com a peça (`id`, `codigo`, `descricao`), `quantidade_necessaria`, `quantidade_validada` e `percentual`. Leituras fora do pedido e duplicadas atualizam a resposta sem incrementar as quantidades válidas.

| HTTP | `status` | Condição e efeito |
| --- | --- | --- |
| 400 | `erro` | Código interno ausente/vazio ou responsável vazio/inválido; não registra leitura. |
| 409 | `pedido_sem_itens` | Pedido não possui itens; não registra leitura e orienta a adicionar peças ou aplicar um conjunto. |
| 409 | `erro` | Pedido liberado; não registra leitura. |
| 200 | `nao_cadastrado` | Código interno não corresponde a uma peça; não registra leitura. |
| 200 | `fora_do_pedido` | Peça cadastrada, mas não incluída no pedido; registra a leitura como fora do pedido. |
| 200 | `sucesso` | Peça incluída no pedido ainda tem unidades necessárias a separar; cria leitura de sucesso. |
| 200 | `duplicada` | A quantidade necessária da peça já foi validada; registra a leitura duplicada sem aumentar o progresso. |

Exemplo simplificado de resposta de sucesso:

```json
{
  "status": "sucesso",
  "message": "Peça P-1 validada com sucesso para o pedido.",
  "peca": {
    "id": 1,
    "codigo": "P-1",
    "descricao": "Peça de exemplo"
  },
  "progress": {
    "total_necessario": 1,
    "quantidade_validada": 1,
    "percentual": 100.0,
    "status": "finalizado"
  },
  "progress_by_item": [
    {
      "peca": {"id": 1, "codigo": "P-1", "descricao": "Peça de exemplo"},
      "quantidade_necessaria": 1,
      "quantidade_validada": 1,
      "percentual": 100.0
    }
  ]
}
```

Para pedido inexistente, a rota devolve 404 antes de validar o payload. Não há autenticação, versionamento de API, esquema formal (OpenAPI) nem contratos JSON gerais documentados no projeto.

## Scanner no navegador

Pedidos sem itens não podem abrir o scanner; a tela orienta a adicionar peças ou aplicar uma composição. Cada leitura aceita conta uma unidade do tipo de peça; a etiqueta não identifica uma unidade física individual. No scanner, o progresso global e por peça é atualizado a cada resposta e a conclusão oferece acesso à conferência. Leituras excedentes continuam sendo registradas como duplicadas sem aumentar o progresso.

O scanner de pedidos usa `html5-qrcode` servido localmente e a inicialização/captura compartilhada em `app/static/js/qr-scanner-config.js`. A configuração aceita somente QR Code, processa 10 quadros por segundo, limita a análise a uma área central retangular que se ajusta ao visor e solicita resolução preferencial de 1280 × 720, sujeita ao suporte do dispositivo. Mantenha o QR Code inteiro dentro do retângulo exibido. O cadastro não lê um QR pré-existente: após salvar, gera a etiqueta a partir do código interno. A câmera do scanner requer permissão e contexto seguro (`localhost` ou HTTPS); foco, reflexos e movimento ainda podem afetar a leitura. Teste com a câmera física e QR Codes reais no dispositivo-alvo.

## Macro 7 — indicadores e auditoria

Pedidos aceitam `prazo_entrega` opcional (`YYYY-MM-DD`) no cadastro/edição. O painel `/indicadores/` usa `inicio`, `fim` e `estado` como filtros. Os agregados incluem pedidos filtrados por estado atual, prazos vencidos/entregues, duração média dos ciclos completos, transições, resultado das leituras, divergências de conferência, quantidades embaladas e eventos de carregamento/reversão.

Cada leitura nova requer `responsavel`; transições de estado são registradas com responsável manual, estado anterior/novo, timestamp UTC e ciclo. Conferências, embalagem, carregamento, reversão, saída e reabertura reutilizam os responsáveis já informados nas ações. O painel não exibe ranking ou nomes de operadores. Dados legados sem data de criação ou transições mensuráveis não são reconstruídos.