"""
Paquete de base de datos para MedSimulator.
Configuración de SQLAlchemy y async engine.
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from medsimulator.app.config import settings

logger = logging.getLogger(__name__)

# Configuración del engine asíncrono
engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    """
    Dependencia de FastAPI para obtener la sesión de base de datos asíncrona.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    """
    Inicializa las tablas de la base de datos y configura la extensión vector.
    """
    from medsimulator.db.models import Base
    import sqlalchemy as sa
    
    async with engine.begin() as conn:
        # Crea la extensión vector si no existe (requerido para pgvector)
        await conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Crea las tablas
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Base de datos inicializada correctamente.")
