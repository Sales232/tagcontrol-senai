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
| `app/instance/models.py` | Entidades, relacionamentos, expansão recursiva de conjuntos e cálculo de progresso de pedido. |
| `app/routers/pecas.py` | Páginas e operações de gestão de peças. |
| `app/routers/conjunto.py` | Páginas e operações de conjuntos, peças/subconjuntos e prevenção de ciclos. |
| `app/routers/pedidos.py` | Páginas e operações de pedidos, itens, aplicação de composição, scanner, progresso agregado, conferência final e validação JSON. |
| `app/templates/` | Apresentação HTML renderizada com Jinja2. |
| `app/static/` | CSS, JavaScript do scanner e biblioteca local de leitura de QR Code. |
| `migrations/` | Configuração e histórico de versões do schema via Alembic. |
| `tests/test_app.py` | Testes de fábrica, modelos, CRUD, scanner e seed com o cliente de teste Flask. |

## Fluxos principais

### Gestão HTML

O navegador envia `GET` para obter listas, formulários ou detalhes. Operações de escrita são enviadas por `POST`; as rotas validam os dados, alteram os modelos via sessão SQLAlchemy, fazem commit/rollback e retornam mensagens flash e redirecionamentos ou re-renderizam o formulário com erro.

### Leitura do scanner

O JavaScript inicia a câmera usando `html5-qrcode`, decodifica QR Codes e envia o conteúdo lido para `POST /pedidos/{pedido_id}/scanner/validar`. Pedidos sem itens não abrem o scanner e a rota também rejeita a validação sem criar leitura. Para os demais pedidos, a rota encontra a peça, verifica sua presença e quantidade, grava o resultado aplicável e retorna status, progresso total e progresso por peça em JSON. O cliente atualiza a interface e oferece acesso à conferência quando as quantidades são concluídas. A listagem resume progresso sem substituir o estágio persistido do fluxo.

### Conferência final

Quando o progresso operacional do pedido atinge 100%, a tela de detalhe oferece um checklist manual por peça. A rota `GET/POST /pedidos/{pedido_id}/conferencia` valida o nome do conferente, as quantidades encontradas e os motivos das divergências, persistindo uma tentativa e snapshots por item. A aprovação muda o fluxo para liberado; a reprovação salva quantidades reconciliadas e marcos das leituras existentes para que apenas novas leituras contem na separação complementar. A reabertura explícita de um pedido liberado inicia nova separação sem apagar eventos históricos.

### Composição de pedidos

Conjuntos podem referenciar peças e subconjuntos. A inclusão valida que a hierarquia não forme ciclos. Antes das leituras e conferências, o operador pode aplicar uma quantidade de conjuntos ao pedido; o modelo expande a árvore, multiplica quantidades por nível e agrega peças repetidas. As quantidades resultantes são somadas aos `PedidoItem` existentes e a origem selecionada é persistida em `PedidoConjunto`, sem dependência de recálculo futuro do catálogo.

### Migrações e demonstração

As versões de schema estão em `migrations/versions/` e são aplicadas via Flask-Migrate. O comando `seed-demo` invoca o seed de demonstração; esse seed chama `db.create_all()` e faz upsert dos registros de demonstração que administra.

## Limites arquiteturais observados

- Lógica de apresentação, validação de formulário e parte da orquestração de negócio residem nas funções de rota.
- Não há camada de serviço separada registrada nem interface versionada de API REST.
- O banco SQLite e a ausência de autenticação são configurações/limites atuais, não uma afirmação de adequação para deploy multiusuário.
- Não existe documentação de infraestrutura, topologia de produção ou monitoramento neste repositório.
