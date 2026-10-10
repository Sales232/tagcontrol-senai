# MVP_PLAN.md

## 1. Objetivo do MVP

Este MVP tem como objetivo validar o fluxo principal do sistema descrito no DES — Sistema de Expedição de Silos — em um protótipo funcional para demonstração em banca.

O foco do MVP é demonstrar, de forma funcional e com baixo custo, o seguinte fluxo:

1. Cadastrar peças e pedidos.
2. Associar itens ao pedido.
3. Ler um código de barras via câmera do celular.
4. Validar em tempo real se a peça lida pertence ao pedido em andamento.
5. Apresentar feedback imediato de sucesso, duplicidade ou peça fora do pedido.
6. Persistir o progresso da separação.
7. Exibir painel simples de acompanhamento do pedido.

O MVP não deve incluir autenticação, importação em massa, relatórios avançados ou rastreabilidade rígida de ID individual em nível de produção. Esses itens ficam fora de escopo da Fase 1, conforme o DES.

## 2. Estado atual do projeto

### 2.1 Estrutura atual

O repositório está organizado da seguinte forma:

- `app/` — aplicação principal em Flask
  - `__init__.py` — fábrica de aplicação (`create_app`)
  - `instance/models.py` — modelos do banco
  - `routers/` — blueprints e rotas da aplicação
  - `templates/` — páginas HTML renderizadas pelo Flask
- `migrations/` — histórico do banco via Alembic/Flask-Migrate
- `tests/` — testes automatizados iniciais
- `requirements.txt` — dependências do projeto
- `README.md` — guia provisório de setup

### 2.2 Stack utilizada

A stack atual do projeto é:

- Python 3
- Flask
- Flask-SQLAlchemy
- Flask-Migrate
- SQLite
- Jinja2
- Gunicorn
- unittest para testes automatizados

### 2.3 Arquitetura existente

A arquitetura atual é monolítica e server-rendered:

- Um único serviço Flask responde pela aplicação.
- Não há frontend em React/Next/Vue ou API separada.
- As páginas são renderizadas no servidor com Jinja2.
- A aplicação usa blueprints para organizar rotas por domínio.
- O banco é SQLite local em desenvolvimento e compatível com deploy simples.

Essa arquitetura está de acordo com o requisito RNF07 do DES: arquitetura monolítica simples para protótipo.

### 2.4 Banco de dados e modelos existentes

O esquema atual foi definido em `app/instance/models.py` e migrado em `migrations/versions/9aac0ccff198_initial_schema.py`.

Modelos existentes:

- `Peca`
  - `id`
  - `codigo`
  - `descricao`
  - `codigo_barras`
  - relacionamento com conjunto e pedido
- `Conjunto`
  - `id`
  - `codigo`
  - `descricao`
- `ConjuntoPeca`
  - associação entre conjunto e peça
  - campo `quantidade`
- `Pedido`
  - `id`
  - `codigo`
  - relacionamento com itens e leituras
- `PedidoItem`
  - `pedido_id`
  - `peca_id`
  - `quantidade_necessaria`
  - constraint de unicidade por pedido/peça
- `Leitura`
  - `pedido_id`
  - `peca_id`
  - `status`
  - `timestamp`

Enum existente:

- `StatusLeitura`
  - `SUCESSO`
  - `DUPLICADA`
  - `FORA_DO_PEDIDO`

Observação importante: a estrutura atual já define a persistência da leitura; porém ela ainda não está conectada ao fluxo real de scanner de código de barras nem ao painel de acompanhamento da expedição.

### 2.5 Rotas existentes

As rotas atuais estão em:

- `app/routers/pecas.py`
- `app/routers/conjunto.py`
- `app/routers/pedidos.py`

Rotas implementadas:

- Peças:
  - listagem
  - criação
  - edição
  - exclusão
- Conjuntos:
  - listagem
  - criação
  - edição
  - exclusão
  - associação de peças ao conjunto
- Pedidos:
  - listagem
  - criação
  - edição
  - exclusão
  - detalhe de pedido
  - adicionar item ao pedido
  - editar quantidade do item
  - remover item do pedido

### 2.6 Páginas e templates existentes

A aplicação usa templates server-side com Jinja2. Há páginas para:

- `app/templates/base.html`
- `app/templates/pecas/form.html`
- `app/templates/pecas/listar.html`
- `app/templates/conjuntos/*`
- `app/templates/pedidos/listar.html`
- `app/templates/pedidos/detalhe.html`

Esses templates cobrem a parte administrativa do cadastro, mas ainda não cobrem a tela de expedição por scanner móvel nem o painel de progresso do pedido.

### 2.7 Testes existentes

Arquivo atual:

- `tests/test_app.py`

Testes presentes:

- criação da app via factory
- registro de blueprints
- exigência de `SECRET_KEY`
- presença dos campos principais nos modelos `Peca`, `Conjunto` e `Pedido`

A cobertura atual é mínima e não valida o fluxo de expedição, o scanner e o progresso do pedido.

### 2.8 O que já está implementado

As partes do MVP já desenvolvidas atualmente são:

- estrutura principal da aplicação Flask
- factory da app
- modelos de domínio básicos
- banco SQLite com migração inicial
- rotas de CRUD para peças, conjuntos e pedidos
- templates administrativas para gerenciar entidades
- início do modelo de leitura (`Leitura`) com enum de status
- testes básicos de inicialização da aplicação

### 2.9 O que ainda precisa ser desenvolvido

As partes que ainda faltam para cumprir o DES no MVP são:

- leitura de código de barras via câmera do navegador
- decodificação do código de barras no lado do cliente
- seleção do pedido ativo para separação
- validação real da peça lida contra o pedido ativo
- regra de duplicidade
- feedback visual em tempo real
- persistência do progresso de separação por pedido
- página de acompanhamento do pedido
- massa de dados fictícia para demonstração da banca
- tela de expedição otimizada para mobile
- testes de fluxo principal de leitura/validação
- preparação de layout de apresentação para feira

## 3. Critérios de sucesso

O MVP será considerado concluído quando:

1. O operador consegue cadastrar peças e pedidos no sistema.
2. O sistema consegue associar itens necessários ao pedido.
3. O operador abre a tela de expedição no celular.
4. O navegador consegue acessar a câmera do dispositivo.
5. O sistema lê um código de barras do produto.
6. O sistema valida se a peça pertence ao pedido selecionado.
7. O sistema identifica duplicidade quando a peça já foi separada anteriormente.
8. O sistema exibe feedback visual claro e imediato.
9. O progresso do pedido é atualizado e persistido.
10. Há uma tela ou painel simples mostrando o status de separação do pedido.
11. O fluxo funciona em ambiente de demonstração sem dependência de leitor físico USB/Bluetooth.
12. A demonstração atende ao escopo do DES para a Feira do Empreendedor.

## 4. Escopo

### 4.1 Dentro do escopo do MVP

- Cadastro de peças
- Cadastro de conjuntos/subconjuntos
- Cadastro de pedidos e itens
- Leitura de código de barras via câmera de celular
- Validação em tempo real da peça lida
- Feedback visual de sucesso, duplicidade e fora do pedido
- Persistência do progresso da separação
- Painel simples de acompanhamento por pedido
- Dados fictícios para demonstração
- Arquitetura monolítica com Flask
- Uso de HTTPS em produção, conforme requisito do DES

### 4.2 Fora do escopo do MVP

- Autenticação e controle de acesso
- Importação em massa via CSV/planilha
- Relatórios de gestão e KPI
- Pré-alocação rígida de IDs individuais por pedido
- Testes em ambiente real de fábrica
- Infraestrutura complexa

## 5. Fluxo principal do sistema

O fluxo principal do MVP deve seguir o seguinte caminho:

1. O usuário acessa a aplicação pelo navegador em um celular.
2. O sistema seleciona ou exibe um pedido ativo.
3. O operador aponta a câmera para o código de barras de uma peça.
4. O navegador decodifica o código de barras no cliente.
5. O backend valida a peça contra o pedido em andamento.
6. O sistema compara o código lido com o cadastro de peças e o pedido.
7. O sistema verifica se a peça:
   - pertence ao pedido
   - já foi lida antes
   - está fora do pedido
8. O sistema persiste a leitura com status correspondente.
9. O sistema atualiza o progresso do pedido.
10. A interface mostra feedback visual imediato.
11. O painel de acompanhamento exibe o percentual concluído.

Este fluxo é o núcleo do valor do sistema descrito no DES e deve ser o objetivo principal da implementação.

## 6. Etapas de implementação

### Checkpoint funcional 1 — Base estrutural do MVP

Objetivo:

- Validar que o projeto está pronto para receber a lógica de expedição.

Atividades:

- Revisar e ajustar modelos já existentes conforme necessidade do DES
- Confirmar campos mínimos para leitura/controle de pedido
- Garantir que `Peca`, `Pedido`, `PedidoItem` e `Leitura` consigam suportar o fluxo de armazenagem e separação
- Verificar migração do banco
- Preparar dados fictícios para testes

Resultado esperado:

- Base de dados consistente para o fluxo de expedição
- Dados mockados prontos para simulação da banca

### Checkpoint funcional 2 — Cadastro e gestão do domínio

Objetivo:

- Garantir que a administração do sistema esteja funcional.

Atividades:

- Validar cadastro de peças
- Validar cadastro de conjuntos/subconjuntos
- Validar criação de pedidos
- Validar associação de itens ao pedido
- Validar edição e remoção

Resultado esperado:

- O administrador consegue montar o cenário da demonstração do pedido

### Checkpoint funcional 3 — Scanner de câmera no navegador

Objetivo:

- Implementar a leitura de código de barras via câmera do celular.

Atividades:

- Adicionar fluxo para acesso à câmera (`getUserMedia`)
- Integrar biblioteca de leitura de código de barras do lado do cliente
- Exibir preview da câmera em tela
- Capturar código lido
- Tratar erros de permissão e leitura inválida

Resultado esperado:

- A aplicação lê código de barras do navegador em mobile

### Checkpoint funcional 4 — Validação em tempo real

Objetivo:

- Transformar a leitura em regra de negócio do sistema.

Atividades:

- Identificar a peça a partir do código lido
- Validar se a peça pertence ao pedido ativo
- Verificar duplicidade
- Registrar `Leitura` com `status`
- Atualizar o progresso do pedido

Resultado esperado:

- O sistema decide corretamente se a peça é aceita ou rejeitada

### Checkpoint funcional 5 — Feedback visual e experiência do operador

Objetivo:

- Dar retorno imediato ao operador no processo de separação.

Atividades:

- Implementar tela de expedição mobile
- Exibir mensagem de sucesso
- Exibir mensagem de duplicidade
- Exibir mensagem de peça fora do pedido
- Manter experiência simples e direta

Resultado esperado:

- O operador entende rapidamente o resultado da leitura

### Checkpoint funcional 6 — Painel de acompanhamento de pedido

Objetivo:

- Mostrar ao público o progresso da separação.

Atividades:

- Calcular quantidade separada vs necessária
- Calcular percentual
- Agrupar por pedido
- Exibir status em página simples para banca

Resultado esperado:

- O painel demonstra o progresso do pedido de forma clara

### Checkpoint funcional 7 — Testes e validação final

Objetivo:

- Validar o MVP antes da apresentação.

Atividades:

- Testar cadastro de peças e pedidos
- Testar leitura com códigos válidos e inválidos
- Testar duplicidade e fora do pedido
- Testar progresso do pedido
- Verificar usabilidade em mobile
- Ajustar correções finais

Resultado esperado:

- Fluxo principal funcionando e pronto para demonstração

## 7. Cronograma para dois dias

### Dia 1 — Fundação e administração do MVP

#### 09:00–09:30 | Revisão do DES e alinhamento do MVP
- Confirmar escopo do protótipo
- Revisar RFs relevantes
- Definir critérios de aceite da apresentação

#### 09:30–10:30 | Revisão da estrutura atual e ajustes no modelo
- Validar `Peca`, `Pedido`, `PedidoItem`, `Leitura`
- Ajustar campos necessários para expedição
- Definir regras de consistência do banco

#### 10:30–12:00 | Dados fictícios e seed do cenário
- Criar peças reais para demo
- Criar pedidos com itens e quantidades
- Preparar base para leitura e validação

#### 13:00–15:00 | Finalizar cadastros e regras de negócio do domínio
- Validar peças e pedidos
- Ajustar endpoints e telas
- Corrigir inconsistências de dados

#### 15:00–17:00 | Preparar base para expedição
- Criação do pedido ativo
- Estrutura da página de leitura
- Preparar endpoints de validação

#### 17:00–18:00 | Checkpoint técnico
- Rodar testes existentes
- Corrigir erros preliminares
- Validar que o cenário básico funciona

### Dia 2 — Leitura, validação e apresentação

#### 09:00–11:00 | Implementar leitura de código de barras via câmera
- Acesso à câmera
- Biblioteca de leitura
- Captura do valor lido
- Tratamento de erro

#### 11:00–13:00 | Implementar validação em tempo real
- Verificação de pedido
- Regras de duplicidade
- Persistência do resultado
- Atualização de progresso

#### 13:00–15:00 | Implementar feedback visual do operador
- Tela de expedição
- Mensagens de sucesso/erro
- Estilo simples e legível em mobile

#### 15:00–16:30 | Implementar painel de acompanhamento
- Pedido ativo
- Percentual concluído
- Quantidade separada
- Visão para banca

#### 16:30–17:30 | Testes end-to-end da demonstração
- Fluxo completo em celular
- Fluxo de pedido em andamento
- Verificação de panel visual

#### 17:30–18:00 | Ajustes finais e preparação da apresentação
- Remover bugs óbvios
- Confirmar que o fluxo principal funciona
- Preparar roteiro de demo

## 8. Testes necessários

### 8.1 Testes de modelo e domínio

- Criar peça com código e código de barras
- Criar pedido com itens
- Adicionar peça ao pedido
- Editar quantidade do item
- Remover item do pedido
- Verificar integridade do banco

### 8.2 Testes de leitura de código de barras

- Ler código válido
- Ler código inexistente
- Ler código fora do pedido
- Ler código duplicado
- Ler código com permissão de câmera negada

### 8.3 Testes de validação da expedição

- Peça correta e não duplicada → sucesso
- Peça correta e já separada → duplicada
- Peça não pertencente ao pedido → fora do pedido
- Pedido sem itens restantes → finalizado

### 8.4 Testes de progresso

- Pedido com 0% concluído
- Pedido com parte concluída
- Pedido 100% concluído
- Atualização em tempo real após leitura

### 8.5 Testes de interface

- Página de expedição funciona em mobile
- Texto legível
- Botões acessíveis
- Feedback visual perceptível

### 8.6 Testes de apresentação

- Fluxo de operação em sequência lógica
- Tempo de uso aceitável
- Demonstração visual clara para banca

## 9. Critérios de aceite

O MVP será aceito quando:

- A aplicação funcionará em navegador mobile,
- A leitura via câmera decodifica o código de barras,
- O pedido ativo é validado automaticamente,
- O sistema identifica duplicidade e fora do pedido,
- O painel mostra progresso de separação,
- O usuário consegue concluir uma simulação realista de expedição,
- O sistema cumpre o escopo do DES para a Fase 1.

## 10. Checklist de progresso

### Estrutura da aplicação
- [x] Revisão da arquitetura atual
- [x] Ajuste do modelo de domínio para MVP
- [x] Verificação do banco e migração

### Cadastro e gestão
- [x] Peças cadastradas
- [x] Conjuntos cadastrados
- [x] Pedidos cadastrados
- [x] Itens associados ao pedido

### Scanner e leitura
- [ ] Acesso à câmera funcionando
- [ ] Leitura de código de barras funcionando
- [x] Tratamento de erro implementado

Nota: a tela, a biblioteca e os recursos do navegador foram verificados em localhost. A captura com câmera física e código de barras real ainda depende de validação em um celular.

### Validação de separação
- [x] Peça correta aceita
- [x] Peça duplicada rejeitada
- [x] Peça fora do pedido rejeitada
- [x] Progresso persistido

### Painel de acompanhamento
- [x] Progresso calculado
- [x] Página de acompanhamento criada
- [x] Visual simples para banca

### Testes finais
- [x] Testes de domínio
- [x] Testes de scanner (rota, arquivos locais e tratamento do backend)
- [x] Testes de validação
- [ ] Testes de apresentação

Nota: os testes automatizados cobrem ausência de código, código inexistente, peça do pedido, quantidade parcial/completa, duplicidade e peça fora do pedido. A validação física do scanner e a demonstração em celular continuam pendentes.

## 11. Regras para o próprio Copilot durante a implementação

Estas regras devem guiar o desenvolvimento do MVP e evitar desvios do escopo:

1. Manter a arquitetura monolítica atual.
   - Não criar frontend separado.
   - Não introduzir microserviços.

2. Preservar a fábrica de app em `app/__init__.py`.
   - O código deve continuar inicializando a aplicação via `create_app()`.

3. Trabalhar com os blueprints existentes.
   - `pecas`, `conjuntos`, `pedidos` continuam sendo o centro da organização.

4. Respeitar o escopo do DES para Fase 1.
   - Não implementar autenticação.
   - Não implementar relatórios complexos.
   - Não implementar importação em massa.

5. Priorizar o fluxo principal do sistema.
   - Cadastro → pedido → leitura → validação → progresso → painel.

6. Usar o navegador como ponto de leitura.
   - A coleta de código de barras deve acontecer no lado do cliente.
   - O backend apenas valida e persiste o resultado.

7. Não perder tempo com soluções de produção.
   - O objetivo é demonstrar funcionalidade para banca, não robustez industrial.

8. Preservar a estrutura de modelos e banco já existentes.
   - Ajustar conforme necessidade, mas sem reescrever o projeto do zero.

9. Adotar dados fictícios realistas.
   - O protótipo deve ser demonstrável sem depender de dados reais de fábrica.

10. Validar cada checkpoint funcional antes de avançar.
   - Não seguir para a próxima etapa sem funcionalidade mínima estável.

11. Manter foco em usabilidade mobile.
   - A operação principal deve funcionar bem em celular, pois é o dispositivo de leitura.

12. A implementação deve refletir o código existente nesta base.
   - Não criar stack alternativa nem refatoração ampla sem necessidade.

## Conclusão

Este plano foi desenhado para refletir o projeto real que já existe hoje: um Flask monolítico com models, blueprints, templates e migrações funcionando de forma básica, mas ainda sem o fluxo principal de expedição descrito no DES.

O objetivo deste MVP é transformar essa base em um protótipo funcional de leitura e validação de peças em expedição, com foco em demonstração, simplicidade e rapidez de implementação em dois dias.
