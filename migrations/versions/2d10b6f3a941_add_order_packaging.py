"""add order packaging

Revision ID: 2d10b6f3a941
Revises: 7a99af667db9
Create Date: 2026-11-01 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2d10b6f3a941"
down_revision = "7a99af667db9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "embalagem",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("ciclo", sa.Integer(), nullable=False),
        sa.Column("responsavel", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("observacao", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedido.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pedido_id", "ciclo", name="uq_embalagem_pedido_ciclo"),
    )
    op.create_table(
        "embalagem_volume",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("embalagem_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["embalagem_id"], ["embalagem.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("embalagem_id", "numero", name="uq_embalagem_volume_numero"),
    )
    op.create_table(
        "embalagem_volume_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("volume_id", sa.Integer(), nullable=False),
        sa.Column("pedido_item_id", sa.Integer(), nullable=True),
        sa.Column("codigo_peca", sa.String(length=50), nullable=False),
        sa.Column("descricao_peca", sa.String(length=200), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantidade > 0", name="ck_embalagem_volume_item_quantidade_positiva"),
        sa.ForeignKeyConstraint(["pedido_item_id"], ["pedido_item.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["volume_id"], ["embalagem_volume.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("volume_id", "pedido_item_id", name="uq_embalagem_volume_item"),
    )


def downgrade():
    op.drop_table("embalagem_volume_item")
    op.drop_table("embalagem_volume")
    op.drop_table("embalagem")
