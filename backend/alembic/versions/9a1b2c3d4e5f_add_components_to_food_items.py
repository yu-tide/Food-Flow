"""add_components_to_food_items

Revision ID: 9a1b2c3d4e5f
Revises: f18ce15061ee
Create Date: 2026-05-16 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = '9a1b2c3d4e5f'
down_revision: Union[str, None] = 'f18ce15061ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('food_items', sa.Column('components', JSONB, nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column('food_items', 'components')
