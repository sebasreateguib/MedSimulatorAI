"""
Router de estudio: chat fundamentado en el material del usuario y flashcards.

El chat es sin estado del lado del servidor —el frontend manda los turnos
previos que quiere conservar— para que abrir la sección no obligue a arrastrar
una tabla de conversaciones. Lo que sí se persiste son los mazos: se generan
una vez y se repasan muchas.
"""

import datetime
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from medsimulator.agents.estudio import AgenteEstudio
from medsimulator.app.api.biblioteca import obtener_buscador
from medsimulator.app.dependencias import usuario_actual
from medsimulator.app.sse import evento
from medsimulator.db import get_db
from medsimulator.db.models import ChunkDocumento, Documento, Flashcard, Mazo, Usuario
from medsimulator.llm.schemas import MazoGenerado

logger = logging.getLogger(__name__)

router = APIRouter()

# El agente abre clientes HTTP hacia el proveedor del modelo: uno por proceso.
_agente: Optional[AgenteEstudio] = None

# Tope de fragmentos que alimentan la generación de un mazo. Más contexto no
# mejora las tarjetas y sí empuja el pedido fuera de la ventana del modelo.
MAX_FRAGMENTOS_MAZO = 20


def obtener_agente() -> AgenteEstudio:
    global _agente
    if _agente is None:
        _agente = AgenteEstudio()
    return _agente


# ── Modelos de request ───────────────────────────────────────────────

class TurnoChat(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    mensaje: str
    historial: List[TurnoChat] = Field(default_factory=list)
    # Vacío = buscar en toda la biblioteca del usuario.
    documento_ids: List[int] = Field(default_factory=list)


class MazoRequest(BaseModel):
    documento_ids: List[int] = Field(default_factory=list)
    tema: Optional[str] = None
    cantidad: int = Field(default=10, ge=1, le=30)


class RepasoRequest(BaseModel):
    resultado: str  # 'bien' | 'mal'


# ── Serialización ────────────────────────────────────────────────────

def flashcard_a_dict(ficha: Flashcard) -> Dict[str, Any]:
    return {
        "id": ficha.id,
        "anverso": ficha.anverso,
        "reverso": ficha.reverso,
        "fuente": ficha.fuente,
        "pagina": ficha.pagina,
        "aciertos": ficha.aciertos or 0,
        "fallos": ficha.fallos or 0,
        "ultima_revision": ficha.ultima_revision.isoformat() if ficha.ultima_revision else None,
    }


def mazo_a_dict(mazo: Mazo, flashcards: Optional[List[Flashcard]] = None) -> Dict[str, Any]:
    fichas = mazo.flashcards if flashcards is None else flashcards
    return {
        "id": mazo.id,
        "titulo": mazo.titulo,
        "tema": mazo.tema,
        "documento_ids": mazo.documento_ids or [],
        "created_at": mazo.created_at.isoformat() if mazo.created_at else None,
        "total": len(fichas),
        "flashcards": [flashcard_a_dict(f) for f in fichas],
    }


# ── Chat ─────────────────────────────────────────────────────────────

# El empaquetado vive en app/sse.py: lo comparten los dos streams de la app.
_evento = evento


@router.post("/chat")
async def chat_con_material(
    peticion: ChatRequest,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Responde la pregunta del estudiante usando su propio material, en streaming.

    El stream termina con dos eventos de control: `[CITAS]{...}` con los
    fragmentos que sostienen la respuesta y `[DONE]`.
    """
    mensaje = peticion.mensaje.strip()
    if not mensaje:
        raise HTTPException(status_code=400, detail="El mensaje está vacío.")

    fragmentos = await obtener_buscador().buscar(
        db,
        usuario_id=usuario.id,
        consulta=mensaje,
        top_k=6,
        documento_ids=peticion.documento_ids or None,
    )

    citas = [
        {
            "n": i,
            "documento_id": f["documento_id"],
            "fuente": f["fuente"],
            "pagina": f["pagina"],
            "seccion": f["seccion"],
            "extracto": f["texto"][:400],
        }
        for i, f in enumerate(fragmentos, start=1)
    ]

    historial = [t.model_dump() for t in peticion.historial]

    async def generador() -> AsyncGenerator[str, None]:
        try:
            async for token in obtener_agente().responder_stream(mensaje, historial, fragmentos):
                yield _evento(token)
            yield _evento("[CITAS]" + json.dumps({"citas": citas}, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error en /estudio/chat: {e}", exc_info=True)
            yield _evento("[ERROR] No se pudo completar la respuesta.")
        finally:
            yield _evento("[DONE]")

    return StreamingResponse(
        generador(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Flashcards ───────────────────────────────────────────────────────

async def _fragmentos_para_mazo(
    db: AsyncSession,
    usuario: Usuario,
    peticion: MazoRequest,
) -> List[Dict[str, Any]]:
    """
    Con tema, recupera por relevancia. Sin tema, toma una muestra repartida a lo
    largo de los documentos: agarrar los primeros N chunks daría un mazo entero
    sobre la portada y el índice.
    """
    if peticion.tema and peticion.tema.strip():
        return await obtener_buscador().buscar(
            db,
            usuario_id=usuario.id,
            consulta=peticion.tema,
            top_k=MAX_FRAGMENTOS_MAZO,
            documento_ids=peticion.documento_ids or None,
        )

    stmt = (
        select(ChunkDocumento, Documento.nombre)
        .join(Documento, Documento.id == ChunkDocumento.documento_id)
        .where(ChunkDocumento.usuario_id == usuario.id)
        .order_by(ChunkDocumento.documento_id, ChunkDocumento.id)
    )
    if peticion.documento_ids:
        stmt = stmt.where(ChunkDocumento.documento_id.in_(peticion.documento_ids))

    filas = (await db.execute(stmt)).all()
    if not filas:
        return []

    paso = max(1, len(filas) // MAX_FRAGMENTOS_MAZO)
    muestra = filas[::paso][:MAX_FRAGMENTOS_MAZO]

    return [
        {
            "documento_id": chunk.documento_id,
            "texto": chunk.texto,
            "seccion": chunk.seccion,
            "pagina": chunk.pagina,
            "fuente": nombre,
        }
        for chunk, nombre in muestra
    ]


@router.post("/mazos", status_code=201)
async def generar_mazo(
    peticion: MazoRequest,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """Genera un mazo de flashcards a partir del material y lo persiste."""
    fragmentos = await _fragmentos_para_mazo(db, usuario, peticion)
    if not fragmentos:
        raise HTTPException(
            status_code=400,
            detail="No hay material indexado para generar tarjetas. "
                   "Subí un documento y esperá a que termine de procesarse.",
        )

    try:
        generado: MazoGenerado = await obtener_agente().generar_flashcards(
            fragmentos, cantidad=peticion.cantidad, tema=peticion.tema
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Error generando el mazo: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail="El modelo no pudo generar el mazo.")

    # Los ids se guardan tal como se pidieron; si el pedido era "toda la
    # biblioteca", se registran los documentos que efectivamente aportaron.
    documento_ids = peticion.documento_ids or sorted(
        {f["documento_id"] for f in fragmentos if f.get("documento_id")}
    )

    mazo = Mazo(
        usuario_id=usuario.id,
        titulo=generado.titulo.strip() or "Mazo de repaso",
        tema=peticion.tema,
        documento_ids=documento_ids,
    )
    mazo.flashcards = [
        Flashcard(
            anverso=f.anverso.strip(),
            reverso=f.reverso.strip(),
            fuente=f.fuente,
            pagina=f.pagina,
        )
        for f in generado.flashcards
    ]

    db.add(mazo)
    await db.commit()
    await db.refresh(mazo, attribute_names=["flashcards"])

    logger.info(f"Mazo {mazo.id} generado con {len(mazo.flashcards)} tarjetas.")
    return mazo_a_dict(mazo)


@router.get("/mazos")
async def listar_mazos(
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Mazos del usuario con su cantidad de tarjetas. No trae las tarjetas: la
    lista solo necesita el conteo y traerlas todas sería cargar cada mazo entero.
    """
    resultado = await db.execute(
        select(Mazo, func.count(Flashcard.id))
        .outerjoin(Flashcard, Flashcard.mazo_id == Mazo.id)
        .where(Mazo.usuario_id == usuario.id)
        .group_by(Mazo.id)
        .order_by(Mazo.created_at.desc(), Mazo.id.desc())
    )
    return [
        {
            "id": mazo.id,
            "titulo": mazo.titulo,
            "tema": mazo.tema,
            "documento_ids": mazo.documento_ids or [],
            "created_at": mazo.created_at.isoformat() if mazo.created_at else None,
            "total": total,
            "flashcards": [],
        }
        for mazo, total in resultado.all()
    ]


async def _mazo_del_usuario(mazo_id: int, usuario: Usuario, db: AsyncSession) -> Mazo:
    resultado = await db.execute(
        select(Mazo).options(selectinload(Mazo.flashcards)).where(Mazo.id == mazo_id)
    )
    mazo = resultado.scalar_one_or_none()
    if mazo is None or mazo.usuario_id != usuario.id:
        raise HTTPException(status_code=404, detail="Mazo no encontrado.")
    return mazo


@router.get("/mazos/{mazo_id}")
async def obtener_mazo(
    mazo_id: int,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    return mazo_a_dict(await _mazo_del_usuario(mazo_id, usuario, db))


@router.delete("/mazos/{mazo_id}", status_code=204)
async def eliminar_mazo(
    mazo_id: int,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    mazo = await _mazo_del_usuario(mazo_id, usuario, db)
    await db.delete(mazo)  # cascade borra las tarjetas
    await db.commit()
    return None


@router.post("/flashcards/{flashcard_id}/repaso")
async def registrar_repaso(
    flashcard_id: int,
    peticion: RepasoRequest,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Anota si el estudiante se acordó de la tarjeta. Con esto el modo repaso
    puede volver a mostrar primero lo que peor se sabe.
    """
    if peticion.resultado not in ("bien", "mal"):
        raise HTTPException(status_code=400, detail="El resultado debe ser 'bien' o 'mal'.")

    resultado = await db.execute(
        select(Flashcard, Mazo.usuario_id)
        .join(Mazo, Mazo.id == Flashcard.mazo_id)
        .where(Flashcard.id == flashcard_id)
    )
    fila = resultado.first()
    if fila is None or fila[1] != usuario.id:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada.")

    ficha = fila[0]
    if peticion.resultado == "bien":
        ficha.aciertos = (ficha.aciertos or 0) + 1
    else:
        ficha.fallos = (ficha.fallos or 0) + 1
    ficha.ultima_revision = datetime.datetime.utcnow()

    await db.commit()
    await db.refresh(ficha)
    return flashcard_a_dict(ficha)
