"""add order tracking and indicator events

Revision ID: c8d42f6a1e90
Revises: 91f0cae7b604
Create Date: 2026-11-02 15:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c8d42f6a1e90"
down_revision = "91f0cae7b604"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("pedido") as batch_op:
        batch_op.add_column(sa.Column("criado_em", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("prazo_entrega", sa.Date(), nullable=True))

    with op.batch_alter_table("leitura") as batch_op:
        batch_op.add_column(sa.Column("responsavel", sa.String(length=100), nullable=True))

    op.create_table(
        "pedido_estado_evento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("ciclo", sa.Integer(), nullable=False),
        sa.Column("estado_anterior", sa.String(length=30), nullable=True),
        sa.Column("estado_novo", sa.String(length=30), nullable=False),
        sa.Column("responsavel", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedido.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pedido_estado_evento_pedido_ciclo_timestamp",
        "pedido_estado_evento",
        ["pedido_id", "ciclo", "timestamp"],
    )


def downgrade():
    op.drop_index(
        "ix_pedido_estado_evento_pedido_ciclo_timestamp",
        table_name="pedido_estado_evento",
    )
    op.drop_table("pedido_estado_evento")
    with op.batch_alter_table("leitura") as batch_op:
        batch_op.drop_column("responsavel")
    with op.batch_alter_table("pedido") as batch_op:
        batch_op.drop_column("prazo_entrega")
        batch_op.drop_column("criado_em")
