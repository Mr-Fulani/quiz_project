"""Add translation_group_id to tasks

Revision ID: 0f2e8226dd84
Revises: ec8319ff823c
Create Date: 2024-10-15 08:20:28.098916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f2e8226dd84'
down_revision: Union[str, None] = 'ec8319ff823c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Добавляем новое поле, но не делаем его сразу обязательным
    op.add_column('tasks', sa.Column('translation_group_id', sa.UUID(as_uuid=True), nullable=True))

    # Далее можно будет установить значения translation_group_id для существующих записей через SQL или Python-скрипт
    # После чего можно будет установить ограничение NOT NULL

def downgrade():
    op.drop_column('tasks', 'translation_group_id')
