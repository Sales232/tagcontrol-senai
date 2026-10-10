# Operação e contribuição

## Ambiente de desenvolvimento

Pré-requisitos: Git e Python 3. No PowerShell, a partir da raiz do repositório:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
```

Se a política do PowerShell bloquear a ativação do ambiente, para a sessão atual pode-se usar:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Não versione `.venv`, bancos de dados locais, arquivos de ambiente nem credenciais. O `.gitignore` já contém padrões para esses itens. `SECRET_KEY` é obrigatória e precisa ser configurada na sessão do terminal antes dos comandos Flask:

```powershell
flask --app app run --debug
```

O servidor de desenvolvimento Flask é destinado a uso local; o repositório não fornece uma receita validada de deploy.

## Banco e migrações

O URI padrão usa SQLite. As migrações existentes ficam em `migrations/`; com o segredo configurado, aplique-as usando:

```powershell
flask --app app db upgrade
```

Ao alterar modelos, gere uma revisão, revise o arquivo criado e aplique a migração:

```powershell
flask --app app db migrate -m "descricao da alteracao"
flask --app app db upgrade
```

`flask db init` não é necessário no clone atual, pois a pasta de migrações já está versionada. Não use o banco de produção (se houver) para testar migrações sem um procedimento de backup e revisão.

## Dados de demonstração

```powershell
flask --app app seed-demo
```

O comando cria/atualiza os registros de demonstração descritos em `app/instance/seed.py`, chama `db.create_all()` e mantém os registros que administra idempotentes. Execute contra banco de desenvolvimento, não contra dados operacionais.

## Testes e verificações

Execute os testes automatizados:

```powershell
python -m unittest discover -s tests -v
```

Os testes cobrem fábrica da aplicação, CRUD e validações, seed, fluxo do scanner/progresso e disponibilidade dos ativos estáticos. Eles usam SQLite em memória e não substituem validação de câmera física, navegador real, deploy ou testes de integração com serviço externo.

Depois de uma mudança, revise os arquivos afetados e o diff:

```powershell
git status --short
git diff --check
git diff
```

## Contribuição

1. Atualize sua branch de trabalho a partir da branch principal conforme o fluxo adotado pelo repositório.
2. Mantenha mudanças pequenas e relacionadas; não inclua arquivos locais ou segredos.
3. Para mudanças de schema, inclua e revise a migração correspondente.
4. Execute os testes relevantes e valide manualmente o fluxo afetado quando aplicável.
5. Abra um Pull Request para revisão, informando objetivo, arquivos principais, validações executadas e limitações conhecidas.

O README existente recomenda commits com mensagens descritivas e Pull Requests para `main`. Confirme a branch principal e os procedimentos ativos do time antes de atualizar ou integrar alterações.

## Limitações operacionais

- O projeto configura SQLite como padrão; não há documentação verificada de outro banco.
- `gunicorn` aparece nas dependências, mas não há manifesto/configuração de deploy, configuração de produção ou procedimento operacional versionado.
- As rotas não apresentam autenticação ou controle de acesso. A aplicação não deve ser exposta como serviço para usuários sem uma avaliação e controles adicionais definidos pelo responsável pelo produto.
- A especificação funcional externa `DES_Expedicao_Silos.md` não está neste repositório; confirme requisitos com a fonte responsável antes de tratar esta documentação como requisito aprovado.
