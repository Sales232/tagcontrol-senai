# tagcontrol

Guia provisório para começar a desenvolver o protótipo de controle de armazenamento e expedição.

## 1. Pré-requisitos

- Git instalado e acesso ao repositório no GitHub.
- Python 3 instalado. No Windows, confirme com `py --version`.
- VS Code (opcional, recomendado).

## 2. Clonar e preparar o ambiente

No PowerShell, execute:

```powershell
git clone https://github.com/Sales232/tagcontrol.git
cd tagcontrol
git switch -c feat/descricao-da-tarefa
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Se o PowerShell bloquear a ativação do ambiente, nesta janela execute `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` e tente ativar novamente. A alteração vale apenas para a sessão atual.

Confira se o ambiente está ativo e se as dependências foram instaladas:

```powershell
python --version
python -m pip list
git status --short --branch
```

Use sempre o ambiente `.venv` deste projeto. Não versione a pasta `.venv`, arquivos de banco de dados locais, caches ou credenciais.

## 3. Entender o estado atual

O repositório está no início da implementação: há dependências Flask/SQLAlchemy e um módulo de modelos em `app/instance/models.py`, mas ainda não há inicialização da aplicação, rotas, comando para iniciar o servidor ou suíte de testes. Portanto, `flask run` e testes funcionais ainda não estão disponíveis.

A especificação `DES_Expedicao_Silos.md` existe no workspace do líder, mas ainda não está versionada no GitHub. Peça acesso a ela ou confirme com o líder que foi publicada antes de começar uma tarefa que dependa dos requisitos.

## 4. Validar as alterações

Após editar arquivos Python, faça pelo menos a verificação de sintaxe:

```powershell
python -m compileall -q app
```

Ainda não há testes automatizados no repositório. Quando forem adicionados testes com `unittest`, execute:

```powershell
python -m unittest discover -v
```

Até existir uma aplicação inicializável e testes, a compilação verifica apenas sintaxe; ela não confirma o comportamento do sistema. Ao concluir uma tarefa, revise também o diff e valide manualmente o fluxo alterado assim que houver uma forma de executá-lo.

## 5. Fluxo de trabalho com Git

Antes de começar e antes de enviar suas alterações, confira o estado e atualize sua branch a partir da principal:

```powershell
git status
git fetch origin
git switch main
git pull --ff-only origin main
git switch feat/descricao-da-tarefa
git merge main
```

Faça alterações pequenas e relacionadas à tarefa. Depois das validações, revise o que será enviado:

```powershell
git status --short
git diff
```

Adicione apenas os arquivos da tarefa, evitando `git add .` para não incluir ambiente virtual ou arquivos locais por engano:

```powershell
git add caminho/do/arquivo.py
git diff --cached
git commit -m "feat: descreve a alteracao"
git push -u origin feat/descricao-da-tarefa
```

Abra um Pull Request no GitHub da branch da tarefa para `main`, descreva o que mudou e quais verificações executou. Aguarde a revisão antes de integrar. Se o Git solicitar autenticação, use a autenticação do GitHub/VS Code ou SSH configurado; não coloque tokens ou senhas na URL do repositório.

## 6. Combinados para pedir ajuda

Ao sinalizar que terminou ou pedir revisão, informe a tarefa, os arquivos alterados, os comandos de validação executados e qualquer bloqueio. Se uma validação falhar, compartilhe a mensagem de erro completa e não faça push até entender o problema.