{% extends "base.html" %}
{% block title %}{{ "Editar" if pedido else "Novo" }} pedido{% endblock %}
{% block content %}
<h1>{{ "Editar" if pedido else "Novo" }} pedido</h1>
<form method="post">
    <label>Código
        <input type="text" name="codigo" value="{{ pedido.codigo if pedido else '' }}" required maxlength="50">
    </label>
    <label>Cor da etiqueta
        <input type="text" name="cor_etiqueta" value="{{ pedido.cor_etiqueta if pedido else '' }}" required maxlength="30">
    </label>
    <button type="submit">Salvar</button>
</form>
{% endblock %}