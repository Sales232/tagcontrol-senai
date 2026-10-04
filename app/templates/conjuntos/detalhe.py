{% extends "base.html" %}
{% block title %}Conjunto {{ conjunto.codigo }}{% endblock %}
{% block content %}
<h1>Conjunto {{ conjunto.codigo }} — {{ conjunto.descricao }}</h1>

<h2>Peças neste conjunto</h2>
<table>
    <thead>
        <tr><th>Código</th><th>Descrição</th><th>Quantidade</th><th></th></tr>
    </thead>
    <tbody>
    {% for assoc in conjunto.pecas_assoc %}
        <tr>
            <td>{{ assoc.peca.codigo }}</td>
            <td>{{ assoc.peca.descricao }}</td>
            <td>
                <form method="post" action="{{ url_for('conjuntos.editar_peca', conjunto_id=conjunto.id, assoc_id=assoc.id) }}" style="display:inline">
                    <input type="number" name="quantidade" value="{{ assoc.quantidade }}" min="1" style="width:4em">
                    <button type="submit">Atualizar</button>
                </form>
            </td>
            <td>
                <form method="post" action="{{ url_for('conjuntos.remover_peca', conjunto_id=conjunto.id, assoc_id=assoc.id) }}" style="display:inline"
                      onsubmit="return confirm('Remover essa peça do conjunto?');">
                    <button type="submit">Remover</button>
                </form>
            </td>
        </tr>
    {% else %}
        <tr><td colspan="4">Nenhuma peça associada ainda.</td></tr>
    {% endfor %}
    </tbody>
</table>

<h2>Adicionar peça ao conjunto</h2>
{% if pecas_disponiveis %}
<form method="post" action="{{ url_for('conjuntos.adicionar_peca', conjunto_id=conjunto.id) }}">
    <label>Peça
        <select name="peca_id" required>
            {% for peca in pecas_disponiveis %}
                <option value="{{ peca.id }}">{{ peca.codigo }} — {{ peca.descricao }}</option>
            {% endfor %}
        </select>
    </label>
    <label>Quantidade
        <input type="number" name="quantidade" min="1" value="1" required>
    </label>
    <button type="submit">Adicionar</button>
</form>
{% else %}
<p>Todas as peças cadastradas já estão neste conjunto (ou não há peças cadastradas ainda).</p>
{% endif %}
{% endblock %}