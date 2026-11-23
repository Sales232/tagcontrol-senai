# Requisitos e escopo atual

Este documento registra o comportamento verificável na aplicação e nos testes. Não é uma especificação aprovada do produto e não substitui a especificação operacional externa citada no README.

## Objetivo

Dar suporte ao cadastro de peças e conjuntos e à separação de pedidos, validando as peças lidas e exibindo o progresso da separação.

## Requisitos funcionais implementados

| ID | Requisito observado |
| --- | --- |
| RF-01 | Listar, cadastrar e editar peças com código interno e descrição; o código interno é o conteúdo do QR Code. |
| RF-02 | Impedir códigos internos duplicados entre peças. |
| RF-03 | Impedir a exclusão de peça associada a conjunto, pedido ou leitura. |
| RF-04 | Listar, cadastrar e editar conjuntos e associar peças com quantidade positiva. |
| RF-05 | Listar, cadastrar e editar pedidos e adicionar, editar ou remover seus itens e quantidades necessárias. |
| RF-06 | Abrir a página de scanner de um pedido e validar códigos internos lidos do QR Code ou informados pela rota JSON. |
| RF-07 | Registrar leituras como sucesso, duplicada ou fora do pedido quando a peça cadastrada não pertence ao pedido. |
| RF-08 | Calcular progresso global e por item contando apenas leituras bem-sucedidas, limitadas à quantidade necessária. |
| RF-09 | Carregar os dados de demonstração pelo comando `seed-demo`. |
| RF-10 | Após cadastrar uma peça, gerar sob demanda uma etiqueta com QR contendo o código interno, código e descrição, com opção de impressão; permitir reimpressão de peças existentes. |
| RF-11 | Permitir conferência final manual por item apenas quando todas as quantidades do pedido estiverem separadas. |
| RF-12 | Registrar nome do conferente, horário, quantidade física encontrada e motivo obrigatório para divergências; manter o histórico de tentativas. |
| RF-13 | Liberar o pedido somente quando todas as quantidades conferidas coincidirem com as necessárias; divergências retornam o pedido para correção e nova conferência. |
| RF-14 | Considerar a quantidade física reconciliada como base após reprovação e contar somente novas leituras para a separação complementar, sem apagar leituras antigas. |
| RF-15 | Impedir alterações de itens em pedidos liberados; reabertura explícita invalida a liberação e exige nova separação e conferência. |
| RF-16 | Permitir que conjuntos sejam compostos por peças e subconjuntos, cada componente com quantidade positiva; impedir ciclos na hierarquia. |
| RF-17 | Expandir recursivamente uma composição aplicada ao pedido, multiplicar quantidades por nível e consolidar repetições da mesma peça. |
| RF-18 | Somar as quantidades expandidas às linhas manuais já existentes e registrar o conjunto, código/descrição e quantidade selecionada como origem do pedido. |
| RF-19 | Bloquear a aplicação de composições após qualquer leitura ou conferência e manter os itens já materializados inalterados quando o catálogo mudar. |
| RF-20 | Impedir a abertura do scanner e rejeitar validações quando o pedido não possuir itens, sem registrar leituras; orientar a preparar o pedido. |
| RF-21 | Exibir progresso global e por peça durante a separação e mostrar quantidade validada/necessária e percentual na listagem de pedidos. |
| RF-22 | Ao concluir as quantidades, oferecer acesso à conferência sem redirecionamento automático; manter leituras excedentes como duplicadas sem aumentar o progresso. |
| RF-23 | Consultar uma linha do tempo cronológica do pedido contendo leituras, tentativas de conferência, divergências, reaberturas, embalagens e eventos de expedição, com detalhes aplicáveis. |
| RF-24 | Associar novas leituras e conferências ao ciclo atual e registrar cada reabertura como início de novo ciclo; manter eventos preexistentes sem classificação quando o ciclo não puder ser determinado. |
| RF-25 | Após a conferência aprovada, registrar a embalagem do ciclo com responsável, horário UTC, observação opcional, volumes e conteúdo por peça/quantidade; a soma deve corresponder ao pedido. |
| RF-26 | Após embalagem completa, registrar individualmente o carregamento de cada volume, com responsável e horário UTC; exigir placa e motorista/transportadora para iniciar a expedição. |
| RF-27 | Permitir reversão de carregamento antes da saída, preservando o evento; registrar a saída em ação própria somente quando todos os volumes estiverem carregados. |
| RF-28 | Após a saída, marcar o pedido como expedido e bloquear alterações e reabertura no MVP. |
| RF-29 | Permitir prazo de entrega opcional e registrar responsável manual em cada leitura e transição de estado do fluxo. |
| RF-30 | Exibir indicadores agregados do fluxo e do armazém filtrados por período e estado atual, sem ranking nominal de operadores. |

## Regras de negócio observadas

- Código interno de peça, código de conjunto e código de pedido são únicos nos respectivos registros; QR de peça contém exatamente o código interno.
- Códigos internos de peça têm até 50 caracteres e não aceitam espaço externo nem caracteres de controle, para que o scanner recupere o mesmo conteúdo.
- Campos textuais obrigatórios são validados pelas rotas de formulário.
- Quantidades em itens de conjuntos e pedidos devem ser inteiros positivos segundo a validação das rotas.
- Adicionar novamente peça que já está no conjunto ou pedido soma a quantidade ao item existente.
- Conjuntos podem conter subconjuntos; uma hierarquia circular é rejeitada.
- Ao aplicar um conjunto ao pedido, quantidades são multiplicadas recursivamente e agrupadas por peça antes de serem somadas aos itens existentes.
- A composição aplicada registra snapshots de origem; mudanças posteriores nas estruturas do catálogo não recalculam itens do pedido.
- A aplicação de composição é permitida somente antes de leituras e conferências.
- Um pedido sem itens não inicia separação; a tela e a rota de validação orientam a adicionar peças ou aplicar uma composição, sem criar leituras.
- O progresso de cada peça e do pedido é exibido na tela de scanner; a listagem resume quantidades validadas e percentual separadamente da etapa do fluxo.
- Ao completar as quantidades, o scanner oferece acesso à conferência. Leituras seguintes ainda podem ser registradas como duplicadas, sem alterar o progresso.
- Leituras de peças cadastradas que não fazem parte do pedido são armazenadas como `fora_do_pedido`; um código interno não cadastrado retorna `nao_cadastrado` e não gera uma linha de leitura.
- Leituras que ultrapassam a quantidade necessária são registradas como `duplicada` e não aumentam o progresso.
- Cada leitura aceita conta uma unidade do tipo de peça; o QR Code não é tratado como identificador único da unidade física.
- O pedido tem status calculado `sem_itens`, `em_andamento` ou `finalizado`; o status não é armazenado como uma coluna.
- O estado do fluxo de expedição é armazenado no pedido: separação, aguardando conferência, correção, liberado, embalado, carregando, carregado ou expedido.
- A conferência é manual, não faz nova leitura de QR Code e só pode ser registrada com a separação completa.
- Cada tentativa de conferência armazena o nome do conferente e snapshots dos itens e quantidades. A aprovação libera o pedido; a reprovação registra motivos e reconcilia as quantidades.
- Na reconciliação, leituras anteriores permanecem no histórico; o progresso operacional usa a quantidade física confirmada mais as leituras posteriores ao marco de reconciliação.
- Após a liberação, alterações de itens são bloqueadas. Reabrir o pedido reinicia o progresso operacional, preservando o histórico de leituras e conferências.
- O histórico do pedido combina leituras, conferências, divergências com snapshots e reaberturas em ordem cronológica; eventos simultâneos têm desempate estável.
- Leituras e conferências novas são associadas ao ciclo vigente; reaberturas persistem o início do ciclo seguinte.
- Eventos anteriores sem vínculo de ciclo são apresentados como legado não classificado; os horários são exibidos explicitamente em UTC.
- A embalagem só pode ser registrada após aprovação da conferência no ciclo atual. Cada peça/quantidade do pedido precisa ser distribuída integralmente entre volumes não vazios.
- Pedidos embalados permitem reabertura; a embalagem anterior permanece no ciclo antigo e não é considerada vigente no novo ciclo.
- O carregamento exige embalagem completa no ciclo atual e marca volumes individualmente. Cada ação registra o responsável e timestamp UTC; veículo e motorista/transportadora são informados na primeira marcação.
- Carregamentos podem ser revertidos antes da saída, gerando eventos históricos. A saída é uma confirmação separada, disponível somente quando todos os volumes estão carregados.
- A reabertura é permitida antes da saída, inclusive durante ou após o carregamento; os registros do ciclo anterior são preservados. Depois de expedido, o pedido não pode ser reaberto nem alterado.
- O painel de indicadores usa datas e eventos efetivamente registrados. Pedidos legados sem data/eventos são excluídos dos cálculos que dependem desses dados; históricos passados não são inferidos.
- Um pedido com leituras registradas não pode ser excluído pelas rotas da aplicação. Peças relacionadas também não podem ser excluídas.

## Requisitos não funcionais e restrições verificáveis

- A aplicação é construída com Flask e SQLAlchemy, usa SQLite como banco padrão e Flask-Migrate/Alembic para migrações.
- `SECRET_KEY` precisa existir no ambiente para inicializar a fábrica da aplicação.
- Os scanners de pedidos e cadastro usam `html5-qrcode` local e aceitam somente QR Code, a 10 quadros por segundo, com área de leitura retangular central e resolução de vídeo preferencial de 1280 × 720, sujeita ao suporte do dispositivo.
- Na criação de uma peça, a leitura da câmera não busca dados em catálogo externo; apenas o conteúdo do QR Code é preenchido.
- Os testes automatizados usam `unittest` e banco SQLite em memória.
- A documentação não confirma requisitos de capacidade, desempenho, disponibilidade, retenção, recuperação de desastres, conformidade ou compatibilidade entre navegadores.

## Fora do escopo confirmado

- Não há login, autenticação, autorização ou perfis de usuário implementados nas rotas documentadas.
- O nome do conferente é informado manualmente e não representa autenticação ou garantia de identidade.
- Não há API REST geral: as rotas de cadastro e gestão servem páginas HTML e processam formulários. Apenas a validação do scanner oferece resposta JSON.
- Não há configuração de deploy ou garantia de prontidão para produção documentada no repositório.
- A especificação `DES_Expedicao_Silos.md` não está versionada neste repositório; requisitos que dependam dela precisam ser confirmados com a fonte responsável.