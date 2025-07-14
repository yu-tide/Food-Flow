"""add_analysis_mode_to_food_records

Revision ID: a2b3c4d5e6f7
Revises: 9a1b2c3d4e5f
Create Date: 2026-05-16 10:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '9a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('food_records', sa.Column('analysis_mode', sa.String(length=20), nullable=False, server_default="whole_dish"))


def downgrade() -> None:
    op.drop_column('food_records', 'analysis_mode')
