"""chunks: etiqueta de casos para acotar la búsqueda del validador

Revision ID: b3d1c7a92f40
Revises: 9f7a4ff1e4b6
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b3d1c7a92f40'
down_revision: Union[str, Sequence[str], None] = '9f7a4ff1e4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agrega `chunks.casos` y su índice GIN."""
    # Nullable a propósito: un corpus ya ingerido queda con la columna en NULL y
    # el buscador lo trata como "sirve a cualquier caso". Así la migración no
    # obliga a reingerir para que el sistema siga funcionando.
    op.add_column("chunks", sa.Column("casos", postgresql.ARRAY(sa.String()), nullable=True))
    op.create_index("ix_chunks_casos", "chunks", ["casos"], unique=False, postgresql_using="gin")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_chunks_casos", table_name="chunks", postgresql_using="gin")
    op.drop_column("chunks", "casos")
