# Rotas e contrato do scanner

As rotas abaixo são derivadas dos blueprints em `app/routers/`. As rotas de peças, conjuntos e pedidos servem HTML ou recebem formulários (`application/x-www-form-urlencoded` ou formulário equivalente), não são endpoints REST JSON. Escritas de formulário usam `POST`; os resultados de sucesso normalmente usam mensagens flash e redirecionamento.

`{peca_id}`, `{conjunto_id}`, `{pedido_id}`, `{assoc_id}` e `{item_id}` são identificadores inteiros. Identificadores que não existem retornam 404 pelo helper `get_or_404`/`first_or_404`.

## Peças (`/pecas`)

| Método | Caminho | Comportamento |
| --- | --- | --- |
| GET | `/pecas/` | Lista peças ordenadas por código. |
| GET, POST | `/pecas/novo` | Exibe formulário ou cria peça; código, descrição e código de barras são obrigatórios e únicos nos seus respectivos campos. |
| GET, POST | `/pecas/editar/{peca_id}` | Exibe formulário ou atualiza a peça. |
| POST | `/pecas/apagar/{peca_id}` | Exclui a peça se não tiver associações ou leituras. |

## Conjuntos (`/conjuntos`)

| Método | Caminho | Comportamento |
| --- | --- | --- |
| GET | `/conjuntos/` | Lista conjuntos ordenados por código. |
| GET, POST | `/conjuntos/novo` | Exibe formulário ou cria conjunto. |
| GET, POST | `/conjuntos/editar/{conjunto_id}` | Exibe formulário ou atualiza conjunto. |
| POST | `/conjuntos/apagar/{conjunto_id}` | Exclui conjunto; os itens associados são removidos pela cascata do modelo. |
| GET | `/conjuntos/{conjunto_id}/detalhe` | Exibe o conjunto e peças que ainda podem ser associadas. |
| POST | `/conjuntos/{conjunto_id}/pecas/adicionar` | Adiciona peça com `peca_id` e `quantidade`; quantidade deve ser inteira positiva; se já existir no conjunto, soma a quantidade. |
| POST | `/conjuntos/{conjunto_id}/pecas/editar/{assoc_id}` | Define nova `quantidade` positiva para a associação. |
| POST | `/conjuntos/{conjunto_id}/pecas/remover/{assoc_id}` | Remove a associação. |

## Pedidos (`/pedidos`)

| Método | Caminho | Comportamento |
| --- | --- | --- |
| GET | `/pedidos/` | Lista pedidos ordenados por código. |
| GET, POST | `/pedidos/novo` | Exibe formulário ou cria pedido. |
| GET, POST | `/pedidos/editar/{pedido_id}` | Exibe formulário ou atualiza pedido. |
| POST | `/pedidos/apagar/{pedido_id}` | Exclui pedido sem leituras; a aplicação bloqueia exclusão quando há histórico de leitura. |
| GET | `/pedidos/{pedido_id}/detalhe` | Exibe itens, progresso total e progresso por item. |
| GET | `/pedidos/{pedido_id}/scanner` | Exibe interface do scanner e progresso atual. |
| POST | `/pedidos/{pedido_id}/itens/adicionar` | Recebe `peca_id` e `quantidade_necessaria` positiva; soma à quantidade existente para a mesma peça. |
| POST | `/pedidos/{pedido_id}/itens/editar/{item_id}` | Define nova `quantidade_necessaria` positiva. |
| POST | `/pedidos/{pedido_id}/itens/remover/{item_id}` | Remove item do pedido. |
| POST | `/pedidos/{pedido_id}/scanner/validar` | Valida código e retorna JSON conforme contrato abaixo. |

## Validação JSON do scanner

### Requisição

`POST /pedidos/{pedido_id}/scanner/validar` aceita JSON ou campos de formulário. O valor pode ser enviado em qualquer uma destas chaves: `codigo`, `codigo_barras` ou `barcode`. A peça cadastrada é localizada pelo código de barras **ou** pelo código interno.

Exemplo JSON:

```json
{
  "codigo": "750000000001"
}
```

### Resposta

O payload inclui `status`, `message` e `progress`. Quando o código identifica uma peça cadastrada, inclui também `peca` com `id`, `codigo` e `descricao`.

`progress` tem os campos `total_necessario`, `quantidade_validada`, `percentual` e `status` (veja [modelo-de-dados.md](./modelo-de-dados.md#cálculo-do-progresso)).

| HTTP | `status` | Condição e efeito |
| --- | --- | --- |
| 400 | `erro` | Código ausente/vazio; não registra leitura. |
| 200 | `fora_do_pedido` | Código não cadastrado; não registra leitura. Também é retornado e registrado quando a peça existe mas não pertence ao pedido. |
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
  }
}
```

Para pedido inexistente, a rota devolve 404 antes de validar o payload. Não há autenticação, versionamento de API, esquema formal (OpenAPI) nem contratos JSON gerais documentados no projeto.

## Scanner no navegador

A página usa os ativos locais `html5-qrcode`, `app/static/js/scanner.js` e `app/static/css/scanner.css`. O cliente solicita acesso à câmera e envia um código decodificado por requisição `POST` JSON. O navegador deve permitir a câmera e executar em contexto seguro (`localhost` ou HTTPS). A leitura com câmera física e códigos reais deve ser testada no dispositivo-alvo.
