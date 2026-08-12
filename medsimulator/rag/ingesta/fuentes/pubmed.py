"""
Módulo para la extracción de artículos desde PubMed usando la API de E-utilities.
"""

import logging
import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import asyncio

logger = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

async def buscar_pubmed(query: str, max_results: int = 10) -> List[str]:
    """Busca artículos en PubMed y devuelve una lista de PMIDs."""
    logger.info(f"Buscando en PubMed: {query}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/esearch.fcgi",
                params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "xml"},
                timeout=10.0
            )
            response.raise_for_status()
            root = ET.fromstring(response.text)
            pmids = [id_elem.text for id_elem in root.findall(".//Id")]
            return pmids
    except Exception as e:
        logger.error(f"Error buscando en PubMed: {e}")
        return []

async def obtener_articulo(pmid: str) -> Dict[str, Any]:
    """Obtiene los detalles de un artículo de PubMed dado su PMID."""
    logger.info(f"Obteniendo artículo PubMed: {pmid}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/efetch.fcgi",
                params={"db": "pubmed", "id": pmid, "retmode": "xml"},
                timeout=10.0
            )
            response.raise_for_status()
            root = ET.fromstring(response.text)
            
            articulo = root.find(".//PubmedArticle")
            if articulo is None:
                return {"pmid": pmid, "titulo": "", "abstract": ""}
                
            titulo = articulo.findtext(".//ArticleTitle", default="")
            abstract_texts = articulo.findall(".//AbstractText")
            abstract = " ".join([elem.text for elem in abstract_texts if elem.text])
            
            journal = articulo.findtext(".//Title", default="")
            
            autores = []
            for autor in articulo.findall(".//Author"):
                last_name = autor.findtext("LastName", default="")
                fore_name = autor.findtext("ForeName", default="")
                if last_name:
                    autores.append(f"{last_name} {fore_name}".strip())
                    
            fecha = articulo.findtext(".//PubDate/Year", default="")
            
            return {
                "pmid": pmid,
                "titulo": titulo,
                "abstract": abstract,
                "autores": autores,
                "journal": journal,
                "fecha": fecha
            }
    except Exception as e:
        logger.error(f"Error obteniendo artículo {pmid}: {e}")
        return {"pmid": pmid, "titulo": "", "abstract": ""}

async def obtener_articulos_batch(pmids: List[str]) -> List[Dict[str, Any]]:
    """Obtiene múltiples artículos respetando el rate limit (3 req/sec sin API key)."""
    resultados = []
    for i in range(0, len(pmids), 3):
        lote = pmids[i:i+3]
        tareas = [obtener_articulo(pmid) for pmid in lote]
        res_lote = await asyncio.gather(*tareas)
        resultados.extend(res_lote)
        await asyncio.sleep(1.1)  # Respetar rate limit
    return resultados
