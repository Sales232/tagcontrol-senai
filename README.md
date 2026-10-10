# Tagcontrol

Aplicação web Flask para cadastrar peças, organizar conjuntos e acompanhar a separação de itens de pedidos por leitura de código de barras.

## Funcionalidades disponíveis

- Cadastro, edição, consulta e exclusão de peças, conjuntos e pedidos.
- Composição de conjuntos por peças e quantidades.
- Composição de pedidos por itens e quantidades necessárias.
- Validação de códigos de barras na separação, registro de leituras e cálculo do progresso do pedido.
- Scanner de câmera no navegador móvel, com a biblioteca `html5-qrcode` armazenada localmente.
- Dados de demonstração por meio do comando `flask seed-demo`.

O projeto não implementa autenticação de usuários nem uma API REST pública. As páginas operacionais usam formulários HTML; o scanner usa uma rota JSON descrita em [docs/api.md](./docs/api.md). O uso do scanner com câmera física e códigos reais depende de validação no dispositivo de destino.

## Tecnologias

- Python 3
- Flask e SQLAlchemy
- Flask-Migrate/Alembic
- SQLite (banco padrão configurado pela aplicação)
- HTML, CSS e JavaScript
- `unittest` para testes

## Preparação local

Requisitos: Python 3 e Git. No PowerShell:

```powershell
git clone https://github.com/Sales232/tagcontrol.git
cd tagcontrol
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
```

`SECRET_KEY` é obrigatória para criar a aplicação e deve ser configurada no ambiente antes de iniciar o servidor ou executar comandos Flask. Use uma chave própria em cada ambiente; não a versione nem a compartilhe.

## Executar

Com o ambiente virtual ativo e `SECRET_KEY` configurada:

```powershell
flask --app app run --debug
```

Acesse `http://127.0.0.1:5000`. O modo debug é apropriado apenas para desenvolvimento local.

## Banco, demonstração e testes

O repositório contém o histórico de migrações. Para aplicar as migrações existentes:

```powershell
flask --app app db upgrade
```

Para popular ou atualizar os registros de demonstração:

```powershell
flask --app app seed-demo
```

O seed é idempotente para os registros que administra e cria as tabelas ausentes usando o metadata SQLAlchemy.

Execute os testes automatizados com:

```powershell
python -m unittest discover -s tests -v
```

## Documentação técnica

- [Requisitos e escopo atual](./docs/requisitos.md)
- [Arquitetura da aplicação](./docs/arquitetura.md)
- [Modelo de dados e regras](./docs/modelo-de-dados.md)
- [Rotas e contrato do scanner](./docs/api.md)
- [Operação e contribuição](./docs/operacao-e-contribuicao.md)

## Estado e limites conhecidos

A especificação `DES_Expedicao_Silos.md` é citada em materiais existentes, mas não está disponível no repositório. Portanto, a documentação funcional descreve somente o comportamento verificável no código e nos testes; não substitui a validação com os requisitos oficiais do produto.

O acesso à câmera depende de permissão do navegador e contexto seguro (`localhost` ou HTTPS). Para acessar a câmera de outro dispositivo, a aplicação precisa estar servida por HTTPS. A biblioteca do scanner é local; não é baixada de uma CDN em tempo de execução.
