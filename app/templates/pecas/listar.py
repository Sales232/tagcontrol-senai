{% extends "base.html" %}
{% block title %}Peças{% endblock %}
{% block content %}
<h1>Peças cadastradas</h1>
<a href="{{ url_for('pecas.novo') }}">+ Nova peça</a>
<table>
    <thead>
        <tr><th>Código</th><th>Descrição</th><th>Código de barras</th><th></th></tr>
    </thead>
    <tbody>
    {% for peca in pecas %}
        <tr>
            <td>{{ peca.codigo }}</td>
            <td>{{ peca.descricao }}</td>
            <td>{{ peca.codigo_barras }}</td>
            <td>
                <a href="{{ url_for('pecas.editar', peca_id=peca.id) }}">Editar</a>
                <form method="post" action="{{ url_for('pecas.apagar', peca_id=peca.id) }}" style="display:inline"
                      onsubmit="return confirm('Apagar peça {{ peca.codigo }}?');">
                    <button type="submit">Apagar</button>
                </form>
            </td>
        </tr>
    {% else %}
        <tr><td colspan="4">Nenhuma peça cadastrada.</td></tr>
    {% endfor %}
    </tbody>
</table>
{% endblock %}