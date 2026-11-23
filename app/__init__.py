import os

import click
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text


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

    @app.cli.command("preflight-qr-migration")
    def preflight_qr_migration_command():
        """Check legacy piece identifiers before removing the independent QR column."""
        inspector = inspect(db.engine)
        if not inspector.has_table("peca"):
            raise click.ClickException("A tabela peca não existe neste banco.")

        if not inspector.has_table("alembic_version"):
            raise click.ClickException(
                "A revisão Alembic do banco não foi encontrada; confirme com `flask db current`."
            )
        revisions = db.session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalars().all()
        columns = {column["name"] for column in inspector.get_columns("peca")}
        if not {"id", "codigo"}.issubset(columns):
            raise click.ClickException("A tabela peca não possui as colunas esperadas.")
        if revisions == ["4f9c2a61d730"] and "codigo_qr" not in columns:
            click.echo("A coluna QR legada já não existe; a migração QR já foi aplicada.")
            return
        if revisions != ["c8d42f6a1e90"]:
            revision_text = ", ".join(revisions) or "nenhuma"
            raise click.ClickException(
                "Revisão do banco incompatível com a migração QR: "
                f"{revision_text}. Esperada: c8d42f6a1e90. Confirme com `flask db current`."
            )
        if "codigo_qr" not in columns:
            raise click.ClickException(
                "A coluna QR legada não existe, mas a revisão registrada não corresponde "
                "à migração QR; verifique o schema e a revisão Alembic."
            )

        rows = db.session.execute(
            text("SELECT id, codigo, codigo_qr FROM peca ORDER BY id")
        ).all()
        invalid_ids = []
        seen_codes = set()
        legacy_labels_to_replace = 0
        for row in rows:
            code = row.codigo
            if (
                not code
                or len(code) > 50
                or code != code.strip()
                or any(ord(character) < 32 or ord(character) == 127 for character in code)
                or code in seen_codes
            ):
                invalid_ids.append(row.id)
            seen_codes.add(code)
            if row.codigo_qr != code:
                legacy_labels_to_replace += 1

        if invalid_ids:
            sample_ids = ", ".join(str(piece_id) for piece_id in invalid_ids[:10])
            raise click.ClickException(
                "Migração QR bloqueada: códigos internos vazios, inválidos ou duplicados "
                f"nas peças {sample_ids}. Corrija-os antes de continuar."
            )

        click.echo(
            "Pré-verificação aprovada. "
            f"{legacy_labels_to_replace} etiqueta(s) antiga(s) precisarão ser reimpressas."
        )

    with app.app_context():
        from app.instance import models  # noqa: F401
        from app.routers.home import home_bp
        from app.routers.indicadores import indicadores_bp
        from app.routers.conjunto import conjuntos_bp
        from app.routers.dados import dados_bp
        from app.routers.pecas import pecas_bp
        from app.routers.pedidos import pedidos_bp

        app.register_blueprint(home_bp)
        app.register_blueprint(conjuntos_bp)
        app.register_blueprint(indicadores_bp)
        app.register_blueprint(dados_bp)
        app.register_blueprint(pecas_bp)
        app.register_blueprint(pedidos_bp)

    return app
