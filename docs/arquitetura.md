# Arquitetura

## Visão geral

A aplicação segue uma estrutura Flask modular: a fábrica inicializa extensões e registra blueprints; os blueprints processam requisições e consultam modelos SQLAlchemy; templates Jinja2 renderizam as páginas HTML. JavaScript no cliente usa uma rota JSON do scanner para enviar leituras.

```mermaid
flowchart TD
    Browser[ navegador: templates e scanner.js ] -->|HTTP HTML/forms| Routers[blueprints pecas, conjuntos e pedidos]
    Browser -->|POST JSON do scanner| Scanner[rota de validação do pedido]
    Routers --> Models[modelos SQLAlchemy]
    Scanner --> Models
    Models --> DB[(SQLite padrão)]
    Factory[create_app] --> Extensions[SQLAlchemy e Flask-Migrate]
    Factory --> Routers
    CLI[comandos Flask] --> Factory
    CLI --> Seed[seed-demo]
```

## Inicialização e configuração

`app.create_app(config=None)` cria a instância Flask, exige `SECRET_KEY` no ambiente, define a URI SQLite padrão, inicializa `db` e `migrate`, importa os modelos e registra os blueprints. Uma configuração opcional pode sobrescrever valores Flask após a configuração padrão, mas a checagem da variável de ambiente ocorre antes dessa substituição.

Os modelos ficam em `app/instance/models.py`; as rotas de cada domínio ficam em `app/routers/`; os templates e arquivos do cliente ficam sob `app/templates/` e `app/static/`. A CLI registra `seed-demo`, cuja implementação fica em `app/instance/seed.py`.

## Responsabilidade dos módulos

| Local | Responsabilidade |
| --- | --- |
| `app/__init__.py` | Fábrica Flask, configuração de extensões, registro de blueprints e comando de seed. |
| `app/routers/home.py` | Painel inicial com resumos e atalhos para as áreas de operação. |
| `app/instance/models.py` | Entidades, relacionamentos, expansão recursiva de conjuntos, ciclo/histórico, embalagem, carregamento e cálculo de progresso. |
| `app/routers/pecas.py` | Páginas e operações de gestão de peças. |
| `app/routers/conjunto.py` | Páginas e operações de conjuntos, peças/subconjuntos e prevenção de ciclos. |
| `app/routers/pedidos.py` | Páginas e operações de pedidos, itens, aplicação de composição, scanner, histórico, conferência, embalagem, carregamento, saída e validação JSON. |
| `app/routers/indicadores.py` | Filtros de período/estado e renderização do painel agregado. |
| `app/instance/indicadores.py` | Cálculo de métricas sustentadas pelos registros, excluindo ciclos legados não mensuráveis. |
| `app/templates/` | Apresentação HTML renderizada com Jinja2. |
| `app/static/` | CSS, JavaScript do scanner e biblioteca local de leitura de QR Code. |
| `migrations/` | Configuração e histórico de versões do schema via Alembic. |
| `tests/test_app.py` | Testes de fábrica, modelos, CRUD, scanner e seed com o cliente de teste Flask. |

## Fluxos principais

### Gestão HTML

O navegador envia `GET` para obter listas, formulários ou detalhes. Operações de escrita são enviadas por `POST`; as rotas validam os dados, alteram os modelos via sessão SQLAlchemy, fazem commit/rollback e retornam mensagens flash e redirecionamentos ou re-renderizam o formulário com erro.

A rota `/` apresenta contagens operacionais e atalhos para pedidos, peças, conjuntos, indicadores e importação/exportação. A navegação global é compartilhada também pelas páginas de scanner.

### Leitura do scanner

O JavaScript inicia a câmera usando `html5-qrcode`, decodifica QR Codes e envia o conteúdo lido para `POST /pedidos/{pedido_id}/scanner/validar`. Pedidos sem itens não abrem o scanner e a rota também rejeita a validação sem criar leitura. Para os demais pedidos, a rota encontra a peça, verifica sua presença e quantidade, grava o resultado aplicável e retorna status, progresso total e progresso por peça em JSON. O cliente atualiza a interface e oferece acesso à conferência quando as quantidades são concluídas. A listagem resume progresso sem substituir o estágio persistido do fluxo.

As telas de scanner de pedido e cadastro compartilham a folha `scanner.css`, a navegação e os componentes visuais de câmera/resultado; mantêm scripts e campos específicos de cada fluxo.

### Conferência final

Quando o progresso operacional do pedido atinge 100%, a tela de detalhe oferece um checklist manual por peça. A rota `GET/POST /pedidos/{pedido_id}/conferencia` valida o nome do conferente, as quantidades encontradas e os motivos das divergências, persistindo uma tentativa e snapshots por item. A aprovação muda o fluxo para liberado; a reprovação salva quantidades reconciliadas e marcos das leituras existentes para que apenas novas leituras contem na separação complementar. A reabertura explícita de um pedido liberado inicia nova separação sem apagar eventos históricos.

### Histórico do pedido

A rota `GET /pedidos/{pedido_id}/historico` combina leituras, tentativas de conferência, divergências, reaberturas, embalagens e eventos de expedição em ordem cronológica. Reaberturas e ciclos são persistidos; novas leituras e conferências recebem o ciclo vigente. Eventos legados sem ciclo permanecem sem classificação, e a interface rotula os horários como UTC sem conversão local.

### Indicadores de fluxo e armazém

O painel `GET /indicadores/` recebe o período e o estado atual selecionados e consulta o serviço de agregação. A migração incremental registra prazo opcional, responsáveis por leituras e transições auditáveis com ciclo e timestamp UTC. O painel não apresenta ranking nominal; ciclos sem eventos suficientes e dados sem data de criação são excluídos dos indicadores dependentes e identificados como legado.

### Embalagem, carregamento e saída

Uma conferência aprovada libera a rota de embalagem. A rota valida que todos os itens e quantidades do pedido sejam distribuídos entre volumes não vazios e persiste o snapshot dos volumes/conteúdo, responsável, horário UTC e observação na mesma transação que muda o estado para `embalado`.

O carregamento consome os volumes da embalagem do ciclo vigente. Cada volume recebe eventos auditáveis de carregamento e, se necessário antes da saída, reversão. Placa e motorista/transportadora são registrados no início da expedição; responsáveis e timestamps UTC são associados às ações. A saída é uma rota própria e só conclui o pedido quando todos os volumes constam como carregados. A mudança para `expedido` bloqueia alterações e reaberturas. Uma reabertura anterior à saída inicia ciclo novo sem apagar os eventos do anterior.

### Composição de pedidos

Conjuntos podem referenciar peças e subconjuntos. A inclusão valida que a hierarquia não forme ciclos. Antes das leituras e conferências, o operador pode aplicar uma quantidade de conjuntos ao pedido; o modelo expande a árvore, multiplica quantidades por nível e agrega peças repetidas. As quantidades resultantes são somadas aos `PedidoItem` existentes e a origem selecionada é persistida em `PedidoConjunto`, sem dependência de recálculo futuro do catálogo.

### Migrações e demonstração

As versões de schema estão em `migrations/versions/` e são aplicadas via Flask-Migrate. O comando `seed-demo` invoca o seed de demonstração; esse seed chama `db.create_all()` e faz upsert dos registros de demonstração que administra.

## Limites arquiteturais observados

- Lógica de apresentação, validação de formulário e parte da orquestração de negócio residem nas funções de rota.
- Não há camada de serviço separada registrada nem interface versionada de API REST.
- O banco SQLite e a ausência de autenticação são configurações/limites atuais, não uma afirmação de adequação para deploy multiusuário.
- Não existe documentação de infraestrutura, topologia de produção ou monitoramento neste repositório.
