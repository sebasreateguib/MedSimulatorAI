"""
Router para los endpoints de simulación médica.

Conecta los endpoints HTTP con el Orchestrator real que coordina
paciente, router, especialista y tutor.

Todas las rutas exigen un JWT válido: el usuario sale del token, nunca del
cuerpo del request, y cada sesión se verifica contra su dueño.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from medsimulator.app.casos import CasoNoEncontrado, caso_publico, catalogo_publico
from medsimulator.app.dependencias import sesion_del_usuario, usuario_actual
from medsimulator.app.sse import evento
from medsimulator.db import async_session_factory, get_db
from medsimulator.db.models import Sesion, Evaluacion, Transcripcion, Usuario
from medsimulator.agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()

# Caché en memoria de orquestadores activos por sesión. Es solo un atajo para
# no releer la conversación en cada turno: la fuente de verdad es la tabla
# `transcripciones`, así que perder este dict —reinicio, otro worker— ya no
# pierde la sesión. Ver `_orquestador_de`.
_orchestrators: dict[int, Orchestrator] = {}

# Con este prefijo guarda el orquestador lo que dice el especialista. El
# historial solo distingue system/user/assistant, así que es lo único que
# permite devolverle su burbuja propia a la interfaz al retomar una sesión.
PREFIJO_ESPECIALISTA = "[Especialista]: "


# ── Persistencia de la conversación ──────────────────────────────────

def _filas_de(sesion_id: int, entradas: list[dict]) -> list[Transcripcion]:
    """Convierte entradas del historial del orquestador en filas de la tabla."""
    return [
        Transcripcion(
            sesion_id=sesion_id,
            rol=entrada.get("role", "system"),
            contenido=entrada.get("content", ""),
        )
        for entrada in entradas
    ]


async def _guardar_turnos(sesion_id: int, entradas: list[dict]) -> None:
    """
    Persiste los mensajes nuevos de un turno.

    Abre su propia sesión de base de datos a propósito: esto corre dentro del
    generador del StreamingResponse, y para entonces FastAPI ya cerró la
    sesión que inyectó como dependencia del request.
    """
    if not entradas:
        return
    async with async_session_factory() as db:
        db.add_all(_filas_de(sesion_id, entradas))
        await db.commit()


async def _historial_de(db: AsyncSession, sesion_id: int) -> list[dict]:
    """La conversación de una sesión, en el formato que consume el orquestador."""
    result = await db.execute(
        select(Transcripcion)
        .where(Transcripcion.sesion_id == sesion_id)
        .order_by(Transcripcion.id)
    )
    return [{"role": t.rol, "content": t.contenido} for t in result.scalars().all()]


async def _orquestador_de(sesion: Sesion, db: AsyncSession) -> Orchestrator:
    """
    Devuelve el orquestador de una sesión, rehidratándolo desde la base si no
    está en memoria.

    Antes, cuando faltaba, se lo recreaba con `iniciar_sesion()` —o sea, con el
    historial en blanco— y el paciente seguía atendiendo como si nada pero sin
    recordar nada de la consulta. Ahora la conversación se relee de
    `transcripciones` y el caso sale del snapshot de la sesión.
    """
    orchestrator = _orchestrators.get(sesion.id)
    if orchestrator is not None:
        return orchestrator

    orchestrator = Orchestrator()
    orchestrator.restaurar(sesion.caso_data or {}, await _historial_de(db, sesion.id))
    _orchestrators[sesion.id] = orchestrator
    return orchestrator


def _mensaje_publico(entrada: dict) -> dict:
    """
    Traduce un mensaje del historial al rol con el que lo dibuja la interfaz.

    El historial guarda roles de LLM (system/user/assistant); el frontend
    habla de estudiante, paciente, especialista y sistema.
    """
    contenido = entrada.get("content", "")
    rol = entrada.get("role", "system")

    if rol == "user":
        return {"rol": "estudiante", "contenido": contenido}
    if rol == "assistant":
        if contenido.startswith(PREFIJO_ESPECIALISTA):
            return {"rol": "especialista", "contenido": contenido[len(PREFIJO_ESPECIALISTA):]}
        return {"rol": "paciente", "contenido": contenido}
    return {"rol": "sistema", "contenido": contenido}


# ── Modelos de request ──────────────────────────────────────────────

class IniciarSesionRequest(BaseModel):
    caso_id: str

class TurnoRequest(BaseModel):
    sesion_id: int
    mensaje_estudiante: str

class FinalizarRequest(BaseModel):
    sesion_id: int


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/casos")
async def listar_casos(usuario: Usuario = Depends(usuario_actual)):
    """
    Casos disponibles para simular.

    Es el catálogo que el frontend ya intentaba consultar y que, al no existir,
    lo dejaba cayendo a una copia local escrita a mano; esa copia fue la que se
    desincronizó de los YAML. Devuelve solo lo que el estudiante puede ver antes
    de empezar: ni historia oculta, ni laboratorios, ni diagnóstico.
    """
    return catalogo_publico()


@router.post("/iniciar")
async def iniciar_sesion(
    request: IniciarSesionRequest,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Inicia una nueva sesión de simulación con un caso clínico específico.
    Crea el Orchestrator, carga el caso y registra la sesión en la base de datos.
    """
    # Crear orquestador e iniciar sesión con el caso
    orchestrator = Orchestrator()
    try:
        info_sesion = await orchestrator.iniciar_sesion(request.caso_id)
    except (CasoNoEncontrado, FileNotFoundError) as e:
        # El detalle trae los ids que sí existen: el error anterior solo decía
        # que el pedido no estaba, sin pista de cuál era el bueno.
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error iniciando sesión: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error interno al cargar el caso.")

    # Persistir sesión en BD, siempre a nombre del usuario autenticado
    nueva_sesion = Sesion(
        usuario_id=usuario.id,
        estado="activa",
        caso_data=orchestrator.caso,
    )
    db.add(nueva_sesion)
    await db.commit()
    await db.refresh(nueva_sesion)

    # El mensaje de apertura ya es parte de la conversación: sin persistirlo,
    # una sesión retomada empezaría sin saber quién entró al consultorio.
    db.add_all(_filas_de(nueva_sesion.id, orchestrator.historial))
    await db.commit()

    # Guardar orquestador en memoria
    _orchestrators[nueva_sesion.id] = orchestrator
    logger.info(
        f"Sesión {nueva_sesion.id} iniciada para caso '{request.caso_id}' "
        f"(usuario {usuario.id})"
    )

    return {
        "mensaje": "Sesión iniciada correctamente",
        "sesion_id": nueva_sesion.id,
        "caso_nombre": orchestrator.caso.get("titulo", "Desconocido"),
        "mensaje_inicial": info_sesion.get("mensaje_inicial", ""),
    }


@router.post("/turno")
async def procesar_turno(
    request: TurnoRequest,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Procesa el turno de un estudiante y devuelve la respuesta
    en formato SSE (Server-Sent Events) token por token.
    """
    sesion = await sesion_del_usuario(request.sesion_id, usuario, db)

    if sesion.estado != "activa":
        raise HTTPException(status_code=400, detail="La sesión no está activa.")

    orchestrator = await _orquestador_de(sesion, db)

    # Dónde termina lo ya persistido: todo lo que el orquestador agregue de acá
    # en adelante es lo que este turno tiene que guardar.
    marca = len(orchestrator.historial)

    async def generador_sse():
        try:
            async for token in orchestrator.procesar_turno(request.mensaje_estudiante):
                # `evento()` y no un f-string: un token con salto de línea
                # —el separador entre el resultado de un estudio y la reacción
                # del paciente— cortaba el evento y se perdía en el camino.
                yield evento(token)
        except Exception as e:
            logger.error(
                f"Error en turno de sesión {request.sesion_id}: {e}",
                exc_info=True,
            )
            yield evento("[ERROR] Ocurrió un problema procesando el turno.")
        finally:
            # Se guarda antes del [DONE] y dentro del finally a propósito: si
            # el estudiante corta el turno a la mitad, lo que el paciente
            # alcanzó a decir igual es parte de la consulta.
            try:
                await _guardar_turnos(request.sesion_id, orchestrator.historial[marca:])
            except Exception:
                logger.error(
                    f"No se pudo persistir el turno de la sesión {request.sesion_id}",
                    exc_info=True,
                )
            yield evento("[DONE]")

    return StreamingResponse(
        generador_sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/finalizar")
async def finalizar_sesion(
    request: FinalizarRequest,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Finaliza la sesión de simulación y desencadena la evaluación del tutor.
    """
    sesion = await sesion_del_usuario(request.sesion_id, usuario, db)

    if sesion.estado == "finalizada":
        raise HTTPException(status_code=400, detail="La sesión ya se encuentra finalizada.")

    # Se rehidrata si hace falta. Antes esto era un 400: una sesión que había
    # sobrevivido a un reinicio del servidor no se podía cerrar nunca y quedaba
    # "activa" para siempre en el historial.
    orchestrator = await _orquestador_de(sesion, db)

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


@router.get("/sesion/{sesion_id}")
async def obtener_sesion(
    sesion_id: int,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Todo lo necesario para retomar una sesión: la ficha del caso y la
    conversación tal como quedó.

    Del caso viaja solo la vista pública —quién consulta y por qué—: la
    historia oculta, los laboratorios y el diagnóstico se quedan en el
    servidor, igual que al elegir el caso por primera vez.
    """
    sesion = await sesion_del_usuario(sesion_id, usuario, db)

    caso_data = sesion.caso_data or {}
    if not caso_data.get("id"):
        # Una sesión sin snapshot del caso no se puede reconstruir: no hay
        # paciente al que volver.
        raise HTTPException(
            status_code=409,
            detail="Esta sesión no guardó los datos del caso y no se puede retomar.",
        )

    return {
        "sesion_id": sesion.id,
        "estado": sesion.estado,
        "caso": caso_publico(caso_data),
        "mensajes": [_mensaje_publico(e) for e in await _historial_de(db, sesion_id)],
    }


@router.get("/historial")
async def obtener_historial(
    limite: int | None = Query(
        None,
        ge=1,
        le=100,
        description="Cuántas sesiones traer. Sin este parámetro vuelven todas.",
    ),
    desplazamiento: int = Query(0, ge=0, description="Cuántas saltear antes de empezar."),
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Lista las sesiones pasadas del usuario autenticado junto con el puntaje de
    su evaluación (si ya fue finalizada), de más reciente a más antigua.

    `total` viaja siempre, aunque la página venga recortada: sin él, el que
    pagina no puede saber cuántas páginas hay ni cuándo se quedó sin sesiones.
    Los tableros de métricas piden sin `limite` porque calculan agregados sobre
    el historial completo.
    """
    total = await db.scalar(
        select(func.count(Sesion.id)).where(Sesion.usuario_id == usuario.id)
    )

    consulta = (
        select(Sesion, Evaluacion)
        .outerjoin(Evaluacion, Evaluacion.sesion_id == Sesion.id)
        .where(Sesion.usuario_id == usuario.id)
        .order_by(Sesion.created_at.desc())
    )
    if limite is not None:
        consulta = consulta.offset(desplazamiento).limit(limite)

    result = await db.execute(consulta)

    return {
        "total": total or 0,
        "sesiones": [
            {
                "sesion_id": sesion.id,
                "caso_id": (sesion.caso_data or {}).get("id"),
                "caso_titulo": (sesion.caso_data or {}).get("titulo", "Caso sin título"),
                "paciente_nombre": (sesion.caso_data or {}).get("paciente", {}).get("nombre"),
                "estado": sesion.estado,
                "puntaje": evaluacion.puntaje if evaluacion else None,
                "created_at": sesion.created_at.isoformat(),
            }
            for sesion, evaluacion in result.all()
        ],
    }
