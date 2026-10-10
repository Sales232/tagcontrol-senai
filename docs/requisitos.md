# Requisitos e escopo atual

Este documento registra o comportamento verificável na aplicação e nos testes. Não é uma especificação aprovada do produto e não substitui a especificação operacional externa citada no README.

## Objetivo

Dar suporte ao cadastro de peças e conjuntos e à separação de pedidos, validando as peças lidas e exibindo o progresso da separação.

## Requisitos funcionais implementados

| ID | Requisito observado |
| --- | --- |
| RF-01 | Listar, cadastrar e editar peças com código, descrição e código de barras. |
| RF-02 | Impedir códigos e códigos de barras duplicados entre peças. |
| RF-03 | Impedir a exclusão de peça associada a conjunto, pedido ou leitura. |
| RF-04 | Listar, cadastrar e editar conjuntos e associar peças com quantidade positiva. |
| RF-05 | Listar, cadastrar e editar pedidos e adicionar, editar ou remover seus itens e quantidades necessárias. |
| RF-06 | Abrir a página de scanner de um pedido e validar códigos informados pelo scanner ou pela rota JSON. |
| RF-07 | Registrar leituras como sucesso, duplicada ou fora do pedido quando a peça cadastrada não pertence ao pedido. |
| RF-08 | Calcular progresso global e por item contando apenas leituras bem-sucedidas, limitadas à quantidade necessária. |
| RF-09 | Carregar os dados de demonstração pelo comando `seed-demo`. |

## Regras de negócio observadas

- Código de peça, código de barras, código de conjunto e código de pedido são únicos nos respectivos registros.
- Campos textuais obrigatórios são validados pelas rotas de formulário.
- Quantidades em itens de conjuntos e pedidos devem ser inteiros positivos segundo a validação das rotas.
- Adicionar novamente peça que já está no conjunto ou pedido soma a quantidade ao item existente.
- Leituras de peças que não fazem parte do pedido são armazenadas como `fora_do_pedido`; um código não cadastrado é respondido como fora do pedido, mas não gera uma linha de leitura.
- Leituras que ultrapassam a quantidade necessária são registradas como `duplicada` e não aumentam o progresso.
- O pedido tem status calculado `sem_itens`, `em_andamento` ou `finalizado`; o status não é armazenado como uma coluna.
- Um pedido com leituras registradas não pode ser excluído pelas rotas da aplicação. Peças relacionadas também não podem ser excluídas.

## Requisitos não funcionais e restrições verificáveis

- A aplicação é construída com Flask e SQLAlchemy, usa SQLite como banco padrão e Flask-Migrate/Alembic para migrações.
- `SECRET_KEY` precisa existir no ambiente para inicializar a fábrica da aplicação.
- O scanner usa `html5-qrcode` servido como arquivo estático local e requer acesso à câmera no navegador.
- Os testes automatizados usam `unittest` e banco SQLite em memória.
- A documentação não confirma requisitos de capacidade, desempenho, disponibilidade, retenção, recuperação de desastres, conformidade ou compatibilidade entre navegadores.

## Fora do escopo confirmado

- Não há login, autenticação, autorização ou perfis de usuário implementados nas rotas documentadas.
- Não há API REST geral: as rotas de cadastro e gestão servem páginas HTML e processam formulários. Apenas a validação do scanner oferece resposta JSON.
- Não há configuração de deploy ou garantia de prontidão para produção documentada no repositório.
- A especificação `DES_Expedicao_Silos.md` não está versionada neste repositório; requisitos que dependam dela precisam ser confirmados com a fonte responsável.
