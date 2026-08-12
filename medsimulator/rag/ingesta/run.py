"""
Script CLI (Punto de entrada) para ejecutar la ingesta de documentos en el sistema RAG.
"""

import argparse
import logging
import asyncio

from medsimulator.rag.ingesta.fuentes.gpc import ingestar_directorio
from medsimulator.rag.ingesta.fuentes.pubmed import buscar_pubmed, obtener_articulos_batch
from medsimulator.rag.ingesta.fuentes.openfda import buscar_medicamento
from medsimulator.rag.embeddings import EmbeddingService
from medsimulator.rag.ingesta.chunking import ChunkerClinico

logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description="Script de ingesta para el RAG de MedSimulator")
    parser.add_argument("--fuente", type=str, required=True, choices=["gpc", "pubmed", "openfda"])
    parser.add_argument("--path", type=str, help="Ruta al directorio de documentos locales")
    parser.add_argument("--query", type=str, help="Consulta para fuentes en línea")
    return parser.parse_args()

async def procesar_y_guardar(chunks: list, fuente_nombre: str):
    logger.info(f"Procesando y guardando {len(chunks)} chunks para {fuente_nombre}")
    if not chunks:
        return
        
    embedder = EmbeddingService()
    
    # Extraer textos para batch embedding
    textos = [c.get("texto", c.get("abstract", c.get("indicaciones", ""))) for c in chunks]
    embeddings = embedder.generar_embeddings_batch(textos)
    
    # TODO: Almacenar en la base de datos de pgvector
    # model Chunk con Vector(1024)
    logger.info(f"Se generaron {len(embeddings)} embeddings exitosamente.")

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    args = parse_args()
    
    logger.info(f"Iniciando ingesta para la fuente: {args.fuente}")
    
    if args.fuente == "gpc":
        if not args.path:
            logger.error("Se requiere --path para la fuente 'gpc'")
            return
        chunks = ingestar_directorio(args.path)
        await procesar_y_guardar(chunks, "GPC")
        
    elif args.fuente == "pubmed":
        if not args.query:
            logger.error("Se requiere --query para la fuente 'pubmed'")
            return
        pmids = await buscar_pubmed(args.query)
        articulos = await obtener_articulos_batch(pmids)
        # Convertir artículos a formato chunk
        chunks = [{"texto": f"{a['titulo']}\n{a['abstract']}", "fuente": f"PubMed:{a['pmid']}", "metadata": a} for a in articulos if a['abstract']]
        await procesar_y_guardar(chunks, "PubMed")
        
    elif args.fuente == "openfda":
        if not args.query:
            logger.error("Se requiere --query para la fuente 'openfda'")
            return
        info = await buscar_medicamento(args.query)
        if "error" not in info:
            chunks = [{"texto": f"Medicamento: {info['nombre']}\nIndicaciones: {info['indicaciones']}\nDosis: {info['dosis']}\nContraindicaciones: {info['contraindicaciones']}", "fuente": f"OpenFDA:{info['nombre']}", "metadata": info}]
            await procesar_y_guardar(chunks, "OpenFDA")
        else:
            logger.error(f"Error desde OpenFDA: {info['error']}")

if __name__ == "__main__":
    asyncio.run(main())
