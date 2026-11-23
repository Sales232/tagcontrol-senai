"""add loading and dispatch

Revision ID: 91f0cae7b604
Revises: 2d10b6f3a941
Create Date: 2026-11-01 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "91f0cae7b604"
down_revision = "2d10b6f3a941"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "expedicao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pedido_id", sa.Integer(), nullable=False),
        sa.Column("embalagem_id", sa.Integer(), nullable=False),
        sa.Column("ciclo", sa.Integer(), nullable=False),
        sa.Column("placa_veiculo", sa.String(length=20), nullable=False),
        sa.Column("motorista_transportadora", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(["embalagem_id"], ["embalagem.id"]),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedido.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("embalagem_id", name="uq_expedicao_embalagem"),
        sa.UniqueConstraint("pedido_id", "ciclo", name="uq_expedicao_pedido_ciclo"),
    )
    op.create_table(
        "expedicao_volume_evento",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("expedicao_id", sa.Integer(), nullable=False),
        sa.Column("embalagem_volume_id", sa.Integer(), nullable=False),
        sa.Column("acao", sa.String(length=20), nullable=False),
        sa.Column("responsavel", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("observacao", sa.String(length=500), nullable=True),
        sa.CheckConstraint("acao IN ('carregado', 'revertido')", name="ck_expedicao_volume_evento_acao"),
        sa.ForeignKeyConstraint(["embalagem_volume_id"], ["embalagem_volume.id"]),
        sa.ForeignKeyConstraint(["expedicao_id"], ["expedicao.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "expedicao_saida",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("expedicao_id", sa.Integer(), nullable=False),
        sa.Column("responsavel", sa.String(length=100), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("observacao", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["expedicao_id"], ["expedicao.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expedicao_id"),
    )


def downgrade():
    op.drop_table("expedicao_saida")
    op.drop_table("expedicao_volume_evento")
    op.drop_table("expedicao")
