"""
Script CLI (Punto de entrada) para ejecutar la ingesta de documentos en el sistema RAG.
"""

import argparse
import json
import logging
import asyncio
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select

from medsimulator.db import async_session_factory
from medsimulator.db.models import Chunk
from medsimulator.rag.ingesta.fuentes.gpc import ingestar_directorio
from medsimulator.rag.ingesta.fuentes.pubmed import (
    buscar_pubmed,
    chunkear_articulos,
    obtener_articulos_batch,
)
from medsimulator.rag.ingesta.fuentes.openfda import buscar_medicamento, chunkear_medicamento
from medsimulator.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# Cuántas filas se acumulan antes de bajarlas a la base. Con un corpus grande,
# un solo `add_all` de todo mantiene decenas de miles de vectores de 1024
# dimensiones vivos en la sesión.
LOTE_INSERCION = 200

def parse_args():
    parser = argparse.ArgumentParser(description="Script de ingesta para el RAG de MedSimulator")
    parser.add_argument("--fuente", type=str, required=True, choices=["gpc", "pubmed", "openfda"])
    parser.add_argument("--path", type=str, help="Ruta al directorio de documentos locales")
    parser.add_argument("--query", type=str, help="Consulta para fuentes en línea")
    parser.add_argument(
        "--caso",
        action="append",
        dest="casos",
        metavar="CASO_ID",
        help="Id del caso clínico al que sirve este material; repetible. "
             "Sin esto el chunk queda sin etiqueta y solo lo ve una búsqueda sin filtro.",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        help="Crea la extensión vector y las tablas antes de ingestar (Alembic no está inicializado)",
    )
    return parser.parse_args()

def _documento_de(chunk: Dict[str, Any]) -> str:
    """
    Clave de reemplazo: identifica el PDF, el artículo o el fármaco del que
    salió el chunk. Los tres chunkers la escriben en `fuente`.
    """
    return chunk.get("fuente") or "desconocido"


def _a_modelo(chunk: Dict[str, Any], embedding: List[float], casos: Optional[List[str]] = None) -> Chunk:
    """
    Traduce la forma que emiten los chunkers a las columnas de la tabla.

    Los chunkers producen `{texto, fuente, pagina, paginas, seccion, metadata}`
    y la tabla tiene `{documento_origen, seccion, texto, metadatos, embedding}`.
    Lo que no tiene columna propia —página y metadatos de la fuente— se
    serializa junto en `metadatos`, que es Text y no JSON: hay que volcarlo a
    string a mano.
    """
    metadatos = dict(chunk.get("metadata") or {})
    if chunk.get("pagina") is not None:
        metadatos["pagina"] = chunk["pagina"]
    if chunk.get("paginas"):
        metadatos["paginas"] = chunk["paginas"]

    return Chunk(
        documento_origen=_documento_de(chunk),
        seccion=chunk.get("seccion"),
        texto=chunk["texto"].strip(),
        # ensure_ascii=False para que los acentos queden legibles en la columna.
        metadatos=json.dumps(metadatos, ensure_ascii=False) if metadatos else None,
        casos=sorted(casos) if casos else None,
        embedding=embedding,
    )


async def procesar_y_guardar(
    chunks: List[Dict[str, Any]],
    fuente_nombre: str,
    casos: Optional[List[str]] = None,
) -> None:
    """
    Genera los embeddings de los chunks y los persiste en pgvector.

    La reingesta es idempotente por documento: antes de insertar se borran los
    chunks previos de cada `documento_origen` del lote. Sin eso, correr la
    ingesta dos veces duplica el corpus entero y el reranker termina devolviendo
    el mismo pasaje repetido en los primeros puestos.

    `casos` son los ids de casos clínicos a los que sirve este material. Como el
    borrado previo se lleva puesta la etiqueta que el documento ya tenía, antes
    de borrar se leen las etiquetas vigentes y se unen con las nuevas: ingerir
    enoxaparina para la tromboembolia no puede dejar sin ella a la fibrilación
    auricular, que la había ingerido antes.
    """
    if not chunks:
        logger.warning("No se recibieron chunks de %s: nada que guardar.", fuente_nombre)
        return

    # Un chunk vacío igual produce vector, y ese vector compite en la búsqueda
    # sin aportar texto. Se descartan antes de embeber.
    utiles = [c for c in chunks if (c.get("texto") or "").strip()]
    if len(utiles) < len(chunks):
        logger.warning("Descartados %d chunks sin texto.", len(chunks) - len(utiles))
    if not utiles:
        return

    logger.info("Generando embeddings para %d chunks de %s…", len(utiles), fuente_nombre)
    embedder = EmbeddingService()
    embeddings = embedder.generar_embeddings_batch([c["texto"] for c in utiles])

    documentos = sorted({_documento_de(c) for c in utiles})

    async with async_session_factory() as session:
        # Las etiquetas que ya tenía cada documento, para no perderlas al borrar.
        previas: Dict[str, set] = {}
        filas = await session.execute(
            select(Chunk.documento_origen, Chunk.casos).where(
                Chunk.documento_origen.in_(documentos)
            )
        )
        for documento, etiquetas in filas:
            previas.setdefault(documento, set()).update(etiquetas or [])

        borrado = await session.execute(
            delete(Chunk).where(Chunk.documento_origen.in_(documentos))
        )
        if borrado.rowcount:
            logger.info(
                "Reemplazando %d chunks previos de %d documento(s).",
                borrado.rowcount,
                len(documentos),
            )

        nuevos = set(casos or [])
        for i in range(0, len(utiles), LOTE_INSERCION):
            lote = utiles[i : i + LOTE_INSERCION]
            vectores = embeddings[i : i + LOTE_INSERCION]
            session.add_all([
                _a_modelo(c, v, previas.get(_documento_de(c), set()) | nuevos)
                for c, v in zip(lote, vectores)
            ])
            await session.flush()

        await session.commit()

    logger.info(
        "Guardados %d chunks de %s en %d documento(s).",
        len(utiles),
        fuente_nombre,
        len(documentos),
    )

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    args = parse_args()

    if args.init_db:
        from medsimulator.db import init_db
        await init_db()

    logger.info(f"Iniciando ingesta para la fuente: {args.fuente}")
    
    if args.fuente == "gpc":
        if not args.path:
            logger.error("Se requiere --path para la fuente 'gpc'")
            return
        chunks = ingestar_directorio(args.path)
        await procesar_y_guardar(chunks, "GPC", args.casos)
        
    elif args.fuente == "pubmed":
        if not args.query:
            logger.error("Se requiere --query para la fuente 'pubmed'")
            return
        pmids = await buscar_pubmed(args.query)
        articulos = await obtener_articulos_batch(pmids)
        await procesar_y_guardar(chunkear_articulos(articulos), "PubMed", args.casos)
        
    elif args.fuente == "openfda":
        if not args.query:
            logger.error("Se requiere --query para la fuente 'openfda'")
            return
        info = await buscar_medicamento(args.query)
        if "error" in info:
            logger.error(f"Error desde OpenFDA: {info['error']}")
            return
        await procesar_y_guardar(chunkear_medicamento(info), "OpenFDA", args.casos)

if __name__ == "__main__":
    asyncio.run(main())
