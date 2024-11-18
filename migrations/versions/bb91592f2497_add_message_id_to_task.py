from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bb91592f2497'
down_revision = '8cbf07976843'
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем столбец с временным значением NULL
    op.add_column('tasks', sa.Column('message_id', sa.Integer(), nullable=True))

    # Устанавливаем значение по умолчанию для существующих записей
    op.execute('UPDATE tasks SET message_id = 0')

    # Меняем столбец на NOT NULL
    op.alter_column('tasks', 'message_id', nullable=False)


def downgrade():
    op.drop_column('tasks', 'message_id')