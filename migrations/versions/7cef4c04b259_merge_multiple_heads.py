"""Merge multiple heads

Revision ID: 7cef4c04b259
Revises: 111eb3871f20, 3af612b399db
Create Date: 2025-01-18 10:26:39.642686

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7cef4c04b259'
down_revision: Union[str, None] = ('111eb3871f20', '3af612b399db')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
