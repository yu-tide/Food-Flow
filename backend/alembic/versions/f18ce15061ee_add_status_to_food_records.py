"""add_status_to_food_records

Revision ID: f18ce15061ee
Revises: 6fd986e8ac34
Create Date: 2026-05-15 20:30:21.472973
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f18ce15061ee'
down_revision: Union[str, None] = '6fd986e8ac34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('food_records', sa.Column('status', sa.String(length=20), nullable=True))
    op.add_column('food_records', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    # Backfill: existing records are treated as confirmed
    op.execute("UPDATE food_records SET status = 'confirmed'")
    op.alter_column('food_records', 'status', nullable=False)


def downgrade() -> None:
    op.drop_column('food_records', 'confirmed_at')
    op.drop_column('food_records', 'status')
