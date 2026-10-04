<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>{% block title %}Expedição de Silos{% endblock %}</title>
</head>
<body>
    <nav>
        <a href="{{ url_for('pecas.listar') }}">Peças</a>
    </nav>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            <ul class="flashes">
            {% for category, message in messages %}
                <li class="{{ category }}">{{ message }}</li>
            {% endfor %}
            </ul>
        {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
</body>
</html>