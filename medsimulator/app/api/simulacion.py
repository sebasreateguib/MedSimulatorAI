"""
Router para los endpoints de simulación médica.

Conecta los endpoints HTTP con el Orchestrator real que coordina
paciente, router, especialista y tutor.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from medsimulator.db import get_db
from medsimulator.db.models import Sesion, Evaluacion, Usuario
from medsimulator.agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()

# Almacén en memoria de orquestadores activos por sesión.
# En producción se usaría Redis o similar para persistencia entre workers.
_orchestrators: dict[int, Orchestrator] = {}


# ── Modelos de request ──────────────────────────────────────────────

class IniciarSesionRequest(BaseModel):
    caso_id: str
    usuario_id: int

class TurnoRequest(BaseModel):
    sesion_id: int
    mensaje_estudiante: str

class FinalizarRequest(BaseModel):
    sesion_id: int


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/iniciar")
async def iniciar_sesion(request: IniciarSesionRequest, db: AsyncSession = Depends(get_db)):
    """
    Inicia una nueva sesión de simulación con un caso clínico específico.
    Crea el Orchestrator, carga el caso y registra la sesión en la base de datos.
    """
    # Verificar o crear usuario
    usuario_result = await db.execute(select(Usuario).where(Usuario.id == request.usuario_id))
    usuario = usuario_result.scalar_one_or_none()

    if not usuario:
        usuario = Usuario(
            id=request.usuario_id,
            username=f"user_{request.usuario_id}",
            email=f"user{request.usuario_id}@test.com",
        )
        db.add(usuario)
        await db.flush()

    # Crear orquestador e iniciar sesión con el caso
    orchestrator = Orchestrator()
    try:
        info_sesion = await orchestrator.iniciar_sesion(request.caso_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Caso clínico '{request.caso_id}' no encontrado.",
        )
    except Exception as e:
        logger.error(f"Error iniciando sesión: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al cargar el caso.")

    # Persistir sesión en BD
    nueva_sesion = Sesion(
        usuario_id=usuario.id,
        estado="activa",
        caso_data=orchestrator.caso,
    )
    db.add(nueva_sesion)
    await db.commit()
    await db.refresh(nueva_sesion)

    # Guardar orquestador en memoria
    _orchestrators[nueva_sesion.id] = orchestrator
    logger.info(f"Sesión {nueva_sesion.id} iniciada para caso '{request.caso_id}'")

    return {
        "mensaje": "Sesión iniciada correctamente",
        "sesion_id": nueva_sesion.id,
        "caso_nombre": orchestrator.caso.get("nombre", "Desconocido"),
        "mensaje_inicial": info_sesion.get("mensaje_inicial", ""),
    }


@router.post("/turno")
async def procesar_turno(request: TurnoRequest, db: AsyncSession = Depends(get_db)):
    """
    Procesa el turno de un estudiante y devuelve la respuesta
    en formato SSE (Server-Sent Events) token por token.
    """
    # Validar sesión en BD
    sesion_result = await db.execute(select(Sesion).where(Sesion.id == request.sesion_id))
    sesion = sesion_result.scalar_one_or_none()

    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    if sesion.estado != "activa":
        raise HTTPException(status_code=400, detail="La sesión no está activa.")

    # Recuperar o recrear orquestador
    orchestrator = _orchestrators.get(request.sesion_id)
    if orchestrator is None:
        # Recrear si se perdió (reinicio del servidor, etc.)
        orchestrator = Orchestrator()
        await orchestrator.iniciar_sesion(sesion.caso_data.get("id", "desconocido"))
        _orchestrators[request.sesion_id] = orchestrator

    async def generador_sse():
        try:
            async for token in orchestrator.procesar_turno(request.mensaje_estudiante):
                yield f"data: {token}\n\n"
        except Exception as e:
            logger.error(
                f"Error en turno de sesión {request.sesion_id}: {e}",
                exc_info=True,
            )
            yield f"data: [ERROR] Ocurrió un problema procesando el turno.\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(generador_sse(), media_type="text/event-stream")


@router.post("/finalizar")
async def finalizar_sesion(request: FinalizarRequest, db: AsyncSession = Depends(get_db)):
    """
    Finaliza la sesión de simulación y desencadena la evaluación del tutor.
    """
    sesion_result = await db.execute(select(Sesion).where(Sesion.id == request.sesion_id))
    sesion = sesion_result.scalar_one_or_none()

    if not sesion:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    if sesion.estado == "finalizada":
        raise HTTPException(status_code=400, detail="La sesión ya se encuentra finalizada.")

    orchestrator = _orchestrators.get(request.sesion_id)
    if orchestrator is None:
        raise HTTPException(
            status_code=400,
            detail="No se encontró el orquestador para esta sesión. Inicie una nueva.",
        )

    # Evaluación final del tutor
    evaluacion_obj = await orchestrator.finalizar_sesion()

    # Persistir evaluación
    sesion.estado = "finalizada"
    nueva_evaluacion = Evaluacion(
        sesion_id=sesion.id,
        puntaje=evaluacion_obj.puntaje_total,
        evaluacion_clinica=evaluacion_obj.model_dump(),
        feedback=evaluacion_obj.retroalimentacion,
    )
    db.add(nueva_evaluacion)
    await db.commit()

    # Limpiar orquestador de memoria
    _orchestrators.pop(request.sesion_id, None)
    logger.info(f"Sesión {request.sesion_id} finalizada y evaluada.")

    return {
        "mensaje": "Sesión finalizada. Puede consultar la evaluación.",
        "sesion_id": request.sesion_id,
        "evaluacion": evaluacion_obj.model_dump(),
    }
