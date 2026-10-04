{% extends "base.html" %}
{% block title %}Conjuntos{% endblock %}
{% block content %}
<h1>Conjuntos cadastrados</h1>
<a href="{{ url_for('conjuntos.novo') }}">+ Novo conjunto</a>
<table>
    <thead>
        <tr><th>Código</th><th>Descrição</th><th>Peças</th><th></th></tr>
    </thead>
    <tbody>
    {% for conjunto in conjuntos %}
        <tr>
            <td>{{ conjunto.codigo }}</td>
            <td>{{ conjunto.descricao }}</td>
            <td>{{ conjunto.pecas_assoc|length }}</td>
            <td>
                <a href="{{ url_for('conjuntos.detalhe', conjunto_id=conjunto.id) }}">Ver/gerenciar peças</a>
                <a href="{{ url_for('conjuntos.editar', conjunto_id=conjunto.id) }}">Editar</a>
                <form method="post" action="{{ url_for('conjuntos.apagar', conjunto_id=conjunto.id) }}" style="display:inline"
                      onsubmit="return confirm('Apagar conjunto {{ conjunto.codigo }} e todas as suas associações de peça?');">
                    <button type="submit">Apagar</button>
                </form>
            </td>
        </tr>
    {% else %}
        <tr><td colspan="4">Nenhum conjunto cadastrado.</td></tr>
    {% endfor %}
    </tbody>
</table>
{% endblock %}