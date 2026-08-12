"""
Módulo para la ingesta de Guías de Práctica Clínica (GPC) desde archivos PDF locales.
"""

import logging
import os
from typing import List, Dict, Any
from medsimulator.rag.ingesta.docling_parser import DoclingParser
from medsimulator.rag.ingesta.chunking import ChunkerClinico

logger = logging.getLogger(__name__)

def ingestar_directorio(path: str) -> List[Dict[str, Any]]:
    """
    Recorre un directorio, procesa los PDFs de guías clínicas y genera chunks.
    """
    logger.info(f"Iniciando ingesta de GPC en el directorio: {path}")
    chunks_totales = []
    
    if not os.path.exists(path):
        logger.error(f"El directorio {path} no existe.")
        return chunks_totales
        
    parser = DoclingParser()
    chunker = ChunkerClinico()
    
    for filename in os.listdir(path):
        if filename.lower().endswith(".pdf"):
            filepath = os.path.join(path, filename)
            try:
                documento = parser.parsear_documento(filepath)
                chunks = chunker.chunkear(documento)
                chunks_totales.extend(chunks)
                logger.info(f"Extraídos {len(chunks)} chunks de {filename}")
            except Exception as e:
                logger.error(f"Error procesando {filename}: {e}")
                
    return chunks_totales
