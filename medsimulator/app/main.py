"""
Punto de entrada principal para la aplicación FastAPI.
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medsimulator.app.config import settings
from medsimulator.app.api import auth, biblioteca, estudio, simulacion, evaluacion
from medsimulator.db import init_db, engine

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manejador de ciclo de vida de la aplicación.
    Se ejecuta al iniciar y detener la app.
    """
    logger.info("Iniciando aplicación y conectando a base de datos...")
    # Inicializar la base de datos (crear tablas, extensión de vectores)
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Error inicializando la base de datos: {e}")

    # Carga de los modelos de ingesta (layout, OCR, embeddings). Va como tarea
    # de fondo y no con await: tarda minutos la primera vez, y bloquear el
    # arranque haría fallar el health check de cualquier despliegue.
    tarea_precalentado = asyncio.create_task(biblioteca.precalentar_modelos())

    # Opcional: Inicializar Langfuse (requerido solo si se configura)
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        try:
            from langfuse import Langfuse
            # Mantener referencia global o inyectarla donde sea necesario
            app.state.langfuse = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST
            )
            logger.info("Langfuse inicializado correctamente.")
        except ImportError:
            logger.warning("Langfuse no está instalado. Ejecute `pip install langfuse` para habilitar la observabilidad.")
        except Exception as e:
            logger.warning(f"No se pudo inicializar Langfuse: {e}")

    yield

    logger.info("Deteniendo aplicación y cerrando conexiones...")
    # Si la precarga sigue corriendo al apagar, se corta acá: sin esto asyncio
    # avisa de una tarea pendiente destruida en cada reinicio del dev server.
    tarea_precalentado.cancel()
    # Cerrar el pool de conexiones de la base de datos
    await engine.dispose()
    logger.info("Conexiones de base de datos cerradas.")

app = FastAPI(
    title="MedSimulator AI",
    description="Simulador médico impulsado por IA para entrenamiento de estudiantes.",
    version="0.1.0",
    lifespan=lifespan,
)

# Configuración de CORS.
# Con autenticación por token no se puede dejar allow_origins=["*"]: habilitaría
# a cualquier sitio a llamar la API desde el navegador de un usuario logueado.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_lista,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(auth.router, prefix="/auth", tags=["Autenticación"])
app.include_router(simulacion.router, prefix="/simulacion", tags=["Simulación"])
app.include_router(evaluacion.router, prefix="/evaluacion", tags=["Evaluación"])
app.include_router(biblioteca.router, prefix="/biblioteca", tags=["Biblioteca"])
app.include_router(estudio.router, prefix="/estudio", tags=["Estudio"])

@app.get("/health")
async def health_check():
    """
    Endpoint de comprobación de estado (health check).
    """
    return {"status": "ok"}
