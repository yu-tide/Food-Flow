"""add_dish_family_to_food_items

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-05-16 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('food_items', sa.Column('dish_family', sa.String(length=100), nullable=True))
    op.add_column('food_items', sa.Column('alternatives', JSONB, nullable=True))
    op.add_column('food_items', sa.Column('user_correction', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('food_items', 'user_correction')
    op.drop_column('food_items', 'alternatives')
    op.drop_column('food_items', 'dish_family')
