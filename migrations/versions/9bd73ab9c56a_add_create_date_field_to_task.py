"""add create_date field to Task

Revision ID: 9bd73ab9c56a
Revises: 28e5a84f797b
Create Date: 2024-10-17 00:26:44.804609

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bd73ab9c56a'
down_revision: Union[str, None] = '28e5a84f797b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Добавляем столбец с временным значением по умолчанию
    op.add_column('tasks', sa.Column('create_date', sa.DateTime(), nullable=False, server_default=sa.func.now()))

    # После создания столбца, удаляем временное значение по умолчанию, если оно больше не нужно
    op.alter_column('tasks', 'create_date', server_default=None)

def downgrade():
    # Удаляем столбец при откате миграции
    op.drop_column('tasks', 'create_date')
