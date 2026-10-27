# Rotas e contrato do scanner

As rotas abaixo são derivadas dos blueprints em `app/routers/`. As rotas de peças, conjuntos e pedidos servem HTML ou recebem formulários (`application/x-www-form-urlencoded` ou formulário equivalente), não são endpoints REST JSON. Escritas de formulário usam `POST`; os resultados de sucesso normalmente usam mensagens flash e redirecionamento.

`{peca_id}`, `{conjunto_id}`, `{pedido_id}`, `{assoc_id}` e `{item_id}` são identificadores inteiros. Identificadores que não existem retornam 404 pelo helper `get_or_404`/`first_or_404`.

## Peças (`/pecas`)

| Método | Caminho | Comportamento |
| --- | --- | --- |
| GET | `/pecas/` | Lista peças ordenadas por código. |
| GET, POST | `/pecas/novo` | Exibe formulário ou cria peça; código, descrição e conteúdo do QR Code são obrigatórios e únicos nos seus respectivos campos. No formulário, a câmera pode preencher o conteúdo do QR Code; código interno e descrição são informados manualmente. |
| GET, POST | `/pecas/editar/{peca_id}` | Exibe formulário ou atualiza a peça. |
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
| GET | `/pedidos/{pedido_id}/scanner` | Exibe interface do scanner e progresso atual; redireciona ao detalhe se o pedido não tiver itens ou já estiver liberado. |
| POST | `/pedidos/{pedido_id}/itens/adicionar` | Recebe `peca_id` e `quantidade_necessaria` positiva; soma à quantidade existente para a mesma peça. |
| POST | `/pedidos/{pedido_id}/conjuntos/adicionar` | Recebe `conjunto_id` e `quantidade` positiva; expande recursivamente peças e subconjuntos, soma quantidades repetidas aos itens existentes e registra um snapshot da composição selecionada. Disponível apenas antes de qualquer leitura ou conferência. |
| POST | `/pedidos/{pedido_id}/itens/editar/{item_id}` | Define nova `quantidade_necessaria` positiva. |
| POST | `/pedidos/{pedido_id}/itens/remover/{item_id}` | Remove item do pedido. |
| POST | `/pedidos/{pedido_id}/scanner/validar` | Valida código e retorna JSON conforme contrato abaixo. |
| GET, POST | `/pedidos/{pedido_id}/conferencia` | Exibe e registra checklist final, disponível com todas as quantidades separadas; exige nome do conferente e quantidade física por item. Divergências exigem motivo. |
| POST | `/pedidos/{pedido_id}/reabrir` | Reabre pedido liberado, invalida a liberação e reinicia o progresso operacional para nova separação e conferência. |

Itens de pedidos liberados não podem ser adicionados, editados ou removidos. A listagem de pedidos mostra quantidade validada/necessária e percentual, independentemente da etapa do fluxo. A conferência aprovada libera o pedido para expedição; o sistema não controla embalagem ou carregamento.

### Composição dos pedidos

Conjuntos podem conter peças e outros conjuntos. Ao aplicar um conjunto ao pedido, a expansão multiplica as quantidades ao longo da hierarquia e consolida todas as ocorrências da mesma peça em uma única linha de item. A quantidade manual que já existir para essa peça também é somada. A composição selecionada guarda código, descrição e quantidade de conjuntos como snapshot; os itens materializados no pedido não são recalculados quando o catálogo muda.

### Conferência final

O formulário recebe `conferente`, `quantidade_{item_id}` para cada item e, quando houver divergência, `motivo_{item_id}`. Quantidades encontradas devem ser inteiros não negativos; o motivo é limitado a 500 caracteres. Uma tentativa é aprovada apenas quando cada quantidade física coincide com a quantidade necessária.

Tentativas aprovadas ou reprovadas e suas linhas são persistidas como histórico com snapshots de código, descrição e quantidades. Em caso de reprovação, a quantidade encontrada é reconciliada como base operacional (limitada à quantidade necessária para o progresso), e somente leituras bem-sucedidas posteriores ao marco da tentativa contam como separação complementar. Leituras antigas não são apagadas. Quando as quantidades voltam a estar completas, é necessário registrar nova conferência de todo o pedido.

O nome do conferente é digitado manualmente; não há autenticação. Reabrir explicitamente um pedido liberado invalida o resultado e zera o progresso operacional, mantendo leituras e conferências anteriores como histórico.

## Validação JSON do scanner

### Requisição

`POST /pedidos/{pedido_id}/scanner/validar` aceita JSON ou campos de formulário. O conteúdo lido pode ser enviado nas chaves `codigo` ou `codigo_qr`. A peça cadastrada é localizada pelo conteúdo do QR Code ou pelo código interno.

Exemplo JSON:

```json
{
  "codigo_qr": "750000000001"
}
```

### Resposta

O payload inclui `status`, `message`, `progress` e `progress_by_item`. Quando o código identifica uma peça cadastrada, inclui também `peca` com `id`, `codigo` e `descricao`.

`progress` tem os campos `total_necessario`, `quantidade_validada`, `percentual` e `status` (veja [modelo-de-dados.md](./modelo-de-dados.md#cálculo-do-progresso)).

`progress_by_item` é uma lista de objetos com a peça (`id`, `codigo`, `descricao`), `quantidade_necessaria`, `quantidade_validada` e `percentual`. Leituras fora do pedido e duplicadas atualizam a resposta sem incrementar as quantidades válidas.

| HTTP | `status` | Condição e efeito |
| --- | --- | --- |
| 400 | `erro` | Conteúdo do QR Code ausente/vazio; não registra leitura. |
| 409 | `pedido_sem_itens` | Pedido não possui itens; não registra leitura e orienta a adicionar peças ou aplicar um conjunto. |
| 409 | `erro` | Pedido liberado; não registra leitura. |
| 200 | `nao_cadastrado` | Conteúdo não corresponde a uma peça; não registra leitura. |
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

Os scanners de pedidos e cadastro usam `html5-qrcode` servido localmente e compartilham a inicialização/captura em `app/static/js/qr-scanner-config.js`. A configuração aceita somente QR Code, processa 10 quadros por segundo, limita a análise a uma área central retangular que se ajusta ao visor e solicita resolução preferencial de 1280 × 720, sujeita ao suporte do dispositivo. Mantenha o QR Code inteiro dentro do retângulo exibido. Cada tela mantém seu próprio callback: o pedido valida o conteúdo lido e atualiza o progresso; o cadastro preenche o campo de QR Code. A tela de cadastro informa quando nenhum QR Code é detectado após alguns segundos. Não há consulta a catálogo externo e os demais campos são preenchidos manualmente. A câmera requer permissão e contexto seguro (`localhost` ou HTTPS); foco, reflexos e movimento ainda podem afetar a leitura. Teste com a câmera física e QR Codes reais no dispositivo-alvo.
