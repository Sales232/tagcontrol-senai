"""use the internal piece code as the only QR identifier

Revision ID: 4f9c2a61d730
Revises: c8d42f6a1e90
Create Date: 2026-11-02 19:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = "4f9c2a61d730"
down_revision = "c8d42f6a1e90"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    piece = sa.table(
        "peca",
        sa.column("id", sa.Integer()),
        sa.column("codigo", sa.String(length=50)),
        sa.column("codigo_qr", sa.String(length=50)),
    )
    rows = bind.execute(
        sa.select(piece.c.id, piece.c.codigo, piece.c.codigo_qr).order_by(piece.c.id)
    ).all()

    invalid = []
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
            invalid.append(row.id)
        seen_codes.add(code)
        if row.codigo_qr != code:
            legacy_labels_to_replace += 1

    if invalid:
        sample_ids = ", ".join(str(piece_id) for piece_id in invalid[:10])
        raise RuntimeError(
            "Migração QR cancelada: códigos internos vazios, inválidos ou duplicados "
            f"nas peças {sample_ids}. Corrija os códigos antes de atualizar."
        )

    if legacy_labels_to_replace:
        op.get_context().config.print_stdout(
            "ATENÇÃO: %s etiqueta(s) antiga(s) usam QR diferente do código interno; "
            "será necessário reimprimi-las." % legacy_labels_to_replace
        )

    with op.batch_alter_table("peca") as batch_op:
        batch_op.drop_index("ix_peca_codigo_qr")
        batch_op.drop_column("codigo_qr")


def downgrade():
    with op.batch_alter_table("peca") as batch_op:
        batch_op.add_column(sa.Column("codigo_qr", sa.String(length=50), nullable=True))

    bind = op.get_bind()
    bind.execute(sa.text("UPDATE peca SET codigo_qr = codigo"))

    with op.batch_alter_table("peca") as batch_op:
        batch_op.alter_column(
            "codigo_qr",
            existing_type=sa.String(length=50),
            nullable=False,
        )
        batch_op.create_index("ix_peca_codigo_qr", ["codigo_qr"], unique=True)
