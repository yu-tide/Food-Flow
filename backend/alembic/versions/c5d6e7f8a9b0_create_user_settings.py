"""create_user_settings

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-05-17 08:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_settings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False, index=True),
        sa.Column('gender', sa.String(10), nullable=True, server_default='unknown'),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('height_cm', sa.Integer(), nullable=True),
        sa.Column('weight_kg', sa.Integer(), nullable=True),
        sa.Column('activity_level', sa.String(20), nullable=True, server_default='light'),
        sa.Column('target_weight_kg', sa.Integer(), nullable=True),
        sa.Column('target_calories', sa.Integer(), server_default='2000'),
        sa.Column('target_protein', sa.Integer(), nullable=True),
        sa.Column('target_carbs', sa.Integer(), nullable=True),
        sa.Column('target_fat', sa.Integer(), nullable=True),
        sa.Column('goal_type', sa.String(20), server_default='maintain'),
        sa.Column('nutrition_goal_mode', sa.String(20), server_default='agent_recommended'),
        sa.Column('diet_style', sa.String(20), nullable=True, server_default='normal'),
        sa.Column('taste_preference', sa.String(10), nullable=True, server_default='normal'),
        sa.Column('avoid_foods', sa.Text(), nullable=True),
        sa.Column('allergens', sa.Text(), nullable=True),
        sa.Column('cuisines', JSONB, nullable=True, server_default='[]'),
        sa.Column('ai_recognition_mode', sa.String(20), server_default='standard'),
        sa.Column('ai_estimate_mode', sa.String(20), server_default='standard'),
        sa.Column('ai_low_confidence_confirm', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('ai_show_components', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('ai_show_summary', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('ai_confirm_similar_dish', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('breakfast_reminder_enabled', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('breakfast_reminder_time', sa.String(5), nullable=True, server_default='08:30'),
        sa.Column('lunch_reminder_enabled', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('lunch_reminder_time', sa.String(5), nullable=True, server_default='12:00'),
        sa.Column('dinner_reminder_enabled', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('dinner_reminder_time', sa.String(5), nullable=True, server_default='18:30'),
        sa.Column('daily_summary_enabled', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('daily_summary_time', sa.String(5), nullable=True, server_default='21:30'),
        sa.Column('weekly_report_enabled', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('weekly_report_day', sa.Integer(), nullable=True, server_default='7'),
        sa.Column('weekly_report_time', sa.String(5), nullable=True, server_default='10:00'),
        sa.Column('inactivity_reminder_enabled', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('image_retention_policy', sa.String(20), server_default='keep_history'),
        sa.Column('allow_anonymous_ai_training', sa.Boolean(), server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('user_settings')
