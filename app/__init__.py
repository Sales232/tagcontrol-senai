import os

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
migrate = Migrate()


def create_app(config=None):
    app = Flask(__name__)
    secret_key = os.environ.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("A variável de ambiente SECRET_KEY deve estar definida.")

    app.config.from_mapping(
        SECRET_KEY=secret_key,
        SQLALCHEMY_DATABASE_URI="sqlite:///tagcontrol.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Populate the SQLite database with a reusable mock dataset for demo sessions."""
        from app.instance.seed import seed_demo_data

        seed_demo_data()
        print("Dados de demonstração criados com sucesso.")

    with app.app_context():
        from app.instance import models  # noqa: F401
        from app.routers.conjunto import conjuntos_bp
        from app.routers.pecas import pecas_bp
        from app.routers.pedidos import pedidos_bp

        app.register_blueprint(conjuntos_bp)
        app.register_blueprint(pecas_bp)
        app.register_blueprint(pedidos_bp)

    return app
