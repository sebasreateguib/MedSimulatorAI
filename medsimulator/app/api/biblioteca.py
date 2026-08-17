"""
Router de la biblioteca: el material de estudio que sube cada usuario.

La ingesta (parseo con OCR + embeddings) no cabe en el tiempo de un request:
el POST guarda el archivo, deja el documento en estado 'procesando' y devuelve
enseguida. El frontend consulta el estado hasta que pasa a 'listo' o 'error'.

Todas las rutas exigen JWT y filtran por dueño: el material de un estudiante
no es visible para nadie más.
"""

import asyncio
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from medsimulator.app.config import settings
from medsimulator.app.dependencias import usuario_actual
from medsimulator.db import async_session_factory, get_db
from medsimulator.db.models import ChunkDocumento, Documento, Usuario
from medsimulator.rag.busqueda_material import BuscadorMaterial
from medsimulator.rag.ingesta.materiales import (
    EXTENSIONES,
    TAMANO_MAXIMO_BYTES,
    MaterialVacioError,
    ProcesadorMaterial,
    mime_de_archivo,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Singletons perezosos: cargar docling y bge-m3 cuesta segundos y cientos de MB,
# así que se pagan una sola vez por proceso y solo si alguien sube material.
_procesador: Optional[ProcesadorMaterial] = None
_buscador: Optional[BuscadorMaterial] = None

# La ingesta satura CPU (OCR + embeddings). Sin este candado, tres subidas
# simultáneas se pelean por los núcleos y las tres tardan el triple.
_candado_ingesta = asyncio.Semaphore(1)


def obtener_procesador() -> ProcesadorMaterial:
    global _procesador
    if _procesador is None:
        _procesador = ProcesadorMaterial()
    return _procesador


def obtener_buscador() -> BuscadorMaterial:
    """Comparte el EmbeddingService con el procesador: es el mismo modelo."""
    global _buscador
    if _buscador is None:
        _buscador = BuscadorMaterial(embedding_service=obtener_procesador().embedding_service)
    return _buscador


async def precalentar_modelos() -> None:
    """
    Deja listos los modelos de ingesta al arrancar la app.

    Se lanza como tarea de fondo desde el lifespan: bloquear el arranque un par
    de minutos haría fallar cualquier health check de despliegue.
    """
    if not settings.PRECARGAR_MODELOS:
        logger.info("PRECARGAR_MODELOS=false: los modelos se cargarán con la primera subida.")
        return
    try:
        await asyncio.to_thread(obtener_procesador().precalentar)
    except Exception as e:
        logger.warning(f"No se pudieron precalentar los modelos de ingesta: {e}")


# ── Serialización ────────────────────────────────────────────────────

def documento_a_dict(doc: Documento) -> Dict[str, Any]:
    return {
        "id": doc.id,
        "nombre": doc.nombre,
        "tipo": doc.tipo,
        "mime": doc.mime,
        "tamano_bytes": doc.tamano_bytes,
        "estado": doc.estado,
        "detalle_error": doc.detalle_error,
        "paginas": doc.paginas,
        "n_chunks": doc.n_chunks or 0,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


# ── Ingesta en segundo plano ─────────────────────────────────────────

async def _ingestar(documento_id: int) -> None:
    """
    Parsea, chunkea y vectoriza el documento, y lo marca 'listo' o 'error'.

    Abre su propia sesión de base: la del request ya se cerró cuando esto
    arranca. Nunca lanza — si algo falla, el estado del documento lo cuenta.
    """
    async with _candado_ingesta:
        async with async_session_factory() as db:
            documento = await db.get(Documento, documento_id)
            if documento is None:
                logger.warning(f"Ingesta cancelada: el documento {documento_id} ya no existe.")
                return

            ruta, nombre, tipo = documento.ruta, documento.nombre, documento.tipo
            usuario_id = documento.usuario_id

            try:
                resultado = await _extraer_con_tope(documento_id, ruta, nombre, tipo)
                await _guardar_chunks(db, documento_id, usuario_id, resultado)

            except asyncio.TimeoutError:
                await db.rollback()
                segundos = settings.TIMEOUT_INGESTA_SEGUNDOS
                plazo = f"{segundos // 60} minutos" if segundos >= 60 else f"{segundos} segundos"
                await _marcar_error(
                    db,
                    documento_id,
                    f"El procesamiento superó los {plazo} y se canceló. "
                    "Probá subiendo el documento partido en secciones.",
                )
            except MaterialVacioError as e:
                await db.rollback()
                await _marcar_error(db, documento_id, str(e))
            except Exception as e:
                await db.rollback()
                logger.error(f"Error ingiriendo el documento {documento_id}: {e}", exc_info=True)
                await _marcar_error(
                    db, documento_id, "No se pudo procesar el archivo. Probá con otro formato."
                )


async def _extraer_con_tope(
    documento_id: int, ruta: str, nombre: str, tipo: str
) -> Dict[str, Any]:
    """
    Corre la extracción con límite de tiempo y, para las imágenes de las que el
    OCR no saca nada, cae al modelo de visión.

    Sobre el timeout: `asyncio.to_thread` no puede matar el hilo, así que al
    vencer el plazo el trabajo sigue consumiendo CPU en segundo plano. Lo que sí
    logra es liberar el candado y marcar el documento como fallido, en vez de
    dejar la cola bloqueada para siempre por un solo archivo.
    """
    procesador = obtener_procesador()

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(procesador.procesar, ruta, nombre, tipo),
            timeout=settings.TIMEOUT_INGESTA_SEGUNDOS,
        )
    except MaterialVacioError:
        if tipo != "imagen" or not settings.VISION_PARA_IMAGENES:
            raise

    # Un ECG, una radiografía o un diagrama no tienen texto que extraer: la
    # única forma de que entren a un RAG textual es describirlos.
    logger.info(f"Documento {documento_id}: sin texto legible, pasando a visión.")
    from medsimulator.agents.vision import obtener_agente_vision

    try:
        descripcion = await asyncio.wait_for(
            obtener_agente_vision().describir_imagen(ruta, nombre),
            timeout=settings.TIMEOUT_INGESTA_SEGUNDOS,
        )
    except asyncio.TimeoutError:
        raise
    except Exception as e:
        logger.error(f"La descripción por visión de {nombre} falló: {e}", exc_info=True)
        # Se distingue el fallo de configuración del de contenido: culpar a la
        # foto cuando lo que falta es la API key manda a buscar donde no es.
        detalle = str(e).lower()
        if "authentication" in detalle or "api_key" in detalle or "api key" in detalle:
            raise MaterialVacioError(
                "La imagen no tiene texto legible y el modelo de visión no está "
                "configurado: falta la API key del proveedor indicado en "
                "config/agents.yaml (agente 'vision')."
            )
        raise MaterialVacioError(
            "No se pudo leer texto en la imagen ni describirla automáticamente. "
            "Probá con una foto más nítida."
        )

    return await asyncio.to_thread(
        procesador.procesar_texto_crudo, descripcion, nombre, "Descripción de la imagen"
    )


async def _guardar_chunks(
    db: AsyncSession, documento_id: int, usuario_id: int, resultado: Dict[str, Any]
) -> None:
    """
    Persiste los chunks y marca el documento como listo.

    Vuelve a buscar el documento porque la ingesta puede haber tardado minutos:
    si el usuario lo borró mientras tanto, insertar sus chunks violaría la clave
    foránea y dejaría huérfanos los vectores de un archivo que ya no existe.
    """
    documento = await db.get(Documento, documento_id)
    if documento is None:
        logger.info(f"El documento {documento_id} se borró durante la ingesta: se descarta.")
        return

    db.add_all([
        ChunkDocumento(
            documento_id=documento_id,
            usuario_id=usuario_id,
            texto=chunk["texto"],
            seccion=chunk.get("seccion"),
            pagina=chunk.get("pagina"),
            embedding=chunk["embedding"],
        )
        for chunk in resultado["chunks"]
    ])

    documento.estado = "listo"
    documento.paginas = resultado["paginas"]
    documento.n_chunks = len(resultado["chunks"])
    documento.detalle_error = None
    await db.commit()
    logger.info(f"Documento {documento_id} ingerido: {documento.n_chunks} chunks.")


async def _marcar_error(db: AsyncSession, documento_id: int, detalle: str) -> None:
    documento = await db.get(Documento, documento_id)
    if documento is None:
        return
    documento.estado = "error"
    documento.detalle_error = detalle
    await db.commit()


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/documentos", status_code=201)
async def subir_documento(
    tareas: BackgroundTasks,
    archivo: UploadFile = File(...),
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Recibe un PDF, una imagen o un archivo de texto y encola su ingesta.

    Devuelve el documento en estado 'procesando': el frontend consulta
    GET /biblioteca/documentos hasta que cambie.
    """
    nombre = os.path.basename(archivo.filename or "sin-nombre")
    _, extension = os.path.splitext(nombre.lower())
    tipo = EXTENSIONES.get(extension)

    if tipo is None:
        raise HTTPException(
            status_code=415,
            detail=f"Formato no soportado ({extension or 'sin extensión'}). "
                   f"Aceptamos: {', '.join(sorted(EXTENSIONES))}.",
        )

    carpeta = settings.material_dir_absoluto / str(usuario.id)
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / f"{uuid.uuid4().hex}{extension}"

    # Se escribe por partes y se corta al pasar el límite: leer el archivo
    # entero en memoria para recién ahí medirlo es justamente lo que un archivo
    # gigante necesita para tumbar el proceso.
    tamano = 0
    try:
        with open(ruta, "wb") as destino:
            while fragmento := await archivo.read(1024 * 1024):
                tamano += len(fragmento)
                if tamano > TAMANO_MAXIMO_BYTES:
                    destino.close()
                    ruta.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"El archivo supera el máximo de "
                               f"{TAMANO_MAXIMO_BYTES // (1024 * 1024)} MB.",
                    )
                destino.write(fragmento)
    except HTTPException:
        raise
    except OSError as e:
        logger.error(f"No se pudo guardar el material: {e}")
        raise HTTPException(status_code=500, detail="No se pudo guardar el archivo.")
    finally:
        await archivo.close()

    if tamano == 0:
        ruta.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="El archivo está vacío.")

    documento = Documento(
        usuario_id=usuario.id,
        nombre=nombre,
        tipo=tipo,
        # El mime se deriva de la extensión y no del que declara el navegador:
        # el visor lo usa para elegir cómo mostrar el archivo, y un cliente puede
        # mandar cualquier cosa (o nada) en content_type.
        mime=mime_de_archivo(nombre, tipo),
        tamano_bytes=tamano,
        ruta=str(ruta),
        estado="procesando",
    )
    db.add(documento)
    await db.commit()
    await db.refresh(documento)

    tareas.add_task(_ingestar, documento.id)
    logger.info(f"Material '{nombre}' recibido del usuario {usuario.id} (id={documento.id}).")

    return documento_a_dict(documento)


@router.get("/documentos")
async def listar_documentos(
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """Material del usuario, del más reciente al más viejo."""
    resultado = await db.execute(
        select(Documento)
        .where(Documento.usuario_id == usuario.id)
        .order_by(Documento.created_at.desc(), Documento.id.desc())
    )
    return [documento_a_dict(d) for d in resultado.scalars().all()]


async def _documento_del_usuario(
    documento_id: int, usuario: Usuario, db: AsyncSession
) -> Documento:
    """
    404 —y no 403— cuando el documento es de otro: confirmar su existencia
    permitiría enumerar el material ajeno por id.
    """
    documento = await db.get(Documento, documento_id)
    if documento is None or documento.usuario_id != usuario.id:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return documento


@router.get("/documentos/{documento_id}")
async def obtener_documento(
    documento_id: int,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    return documento_a_dict(await _documento_del_usuario(documento_id, usuario, db))


@router.post("/documentos/{documento_id}/reintentar")
async def reintentar_ingesta(
    documento_id: int,
    tareas: BackgroundTasks,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Vuelve a procesar un documento que quedó en error.

    Buena parte de los fallos son transitorios —el modelo de visión sin cupo, un
    timeout con la cola llena— y volver a subir el mismo archivo obligaba a
    borrarlo primero.
    """
    documento = await _documento_del_usuario(documento_id, usuario, db)

    if documento.estado == "procesando":
        raise HTTPException(status_code=409, detail="El documento ya se está procesando.")
    if not os.path.exists(documento.ruta):
        raise HTTPException(status_code=410, detail="El archivo ya no está en el servidor.")

    # Los chunks de un intento anterior a medio camino no pueden quedar mezclados
    # con los del nuevo.
    await db.execute(delete(ChunkDocumento).where(ChunkDocumento.documento_id == documento_id))
    documento.estado = "procesando"
    documento.detalle_error = None
    documento.n_chunks = 0
    await db.commit()
    await db.refresh(documento)

    tareas.add_task(_ingestar, documento_id)
    logger.info(f"Reintento de ingesta para el documento {documento_id}.")

    return documento_a_dict(documento)


@router.get("/documentos/{documento_id}/archivo")
async def descargar_documento(
    documento_id: int,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """Sirve el archivo original para previsualizarlo en el visor."""
    documento = await _documento_del_usuario(documento_id, usuario, db)
    if not os.path.exists(documento.ruta):
        raise HTTPException(status_code=404, detail="El archivo ya no está en el servidor.")

    return FileResponse(
        documento.ruta,
        media_type=documento.mime or "application/octet-stream",
        filename=documento.nombre,
        # inline: el visor lo muestra dentro de la app en lugar de descargarlo.
        content_disposition_type="inline",
    )


@router.delete("/documentos/{documento_id}", status_code=204)
async def eliminar_documento(
    documento_id: int,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """Borra el documento, sus chunks y el archivo en disco."""
    documento = await _documento_del_usuario(documento_id, usuario, db)
    ruta = documento.ruta

    # El ON DELETE CASCADE vive en la FK, pero este DELETE es explícito porque
    # las tablas ya creadas antes de esta migración pueden no tenerlo.
    await db.execute(delete(ChunkDocumento).where(ChunkDocumento.documento_id == documento_id))
    await db.delete(documento)
    await db.commit()

    try:
        os.remove(ruta)
    except OSError:
        logger.warning(f"No se pudo borrar el archivo {ruta} del documento {documento_id}.")

    return None


class FragmentoBuscado(BaseModel):
    consulta: str
    documento_ids: List[int] = []
    top_k: int = 6


@router.post("/buscar")
async def buscar_en_material(
    peticion: FragmentoBuscado,
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """
    Búsqueda directa sobre el material, sin pasar por el modelo. Sirve para
    encontrar de dónde salió algo sin gastar una llamada al LLM.
    """
    if not peticion.consulta.strip():
        raise HTTPException(status_code=400, detail="La consulta está vacía.")

    fragmentos = await obtener_buscador().buscar(
        db,
        usuario_id=usuario.id,
        consulta=peticion.consulta,
        top_k=max(1, min(peticion.top_k, 20)),
        documento_ids=peticion.documento_ids or None,
    )
    return [
        {
            "documento_id": f["documento_id"],
            "fuente": f["fuente"],
            "pagina": f["pagina"],
            "seccion": f["seccion"],
            "texto": f["texto"],
        }
        for f in fragmentos
    ]


@router.get("/resumen")
async def resumen_biblioteca(
    usuario: Usuario = Depends(usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    """Cuántos documentos y fragmentos tiene indexados el usuario."""
    documentos = await db.scalar(
        select(func.count(Documento.id)).where(Documento.usuario_id == usuario.id)
    )
    chunks = await db.scalar(
        select(func.count(ChunkDocumento.id)).where(ChunkDocumento.usuario_id == usuario.id)
    )
    return {"documentos": documentos or 0, "fragmentos": chunks or 0}
