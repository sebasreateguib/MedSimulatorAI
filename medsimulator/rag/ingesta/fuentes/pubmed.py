"""
Módulo para la extracción de artículos desde PubMed usando la API de E-utilities.
"""

import logging
import httpx
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
import asyncio

from medsimulator.rag.ingesta.chunking import ChunkerClinico

logger = logging.getLogger(__name__)

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Los abstracts estructurados etiquetan cada bloque en inglés. Se traducen para
# que `seccion` sea homogénea con el resto del corpus, que está en español.
# Lo que no esté acá entra tal cual: es una etiqueta válida, solo desconocida.
ETIQUETAS = {
    "BACKGROUND": "Antecedentes",
    "INTRODUCTION": "Introducción",
    "IMPORTANCE": "Relevancia",
    "OBJECTIVE": "Objetivo",
    "OBJECTIVES": "Objetivo",
    "PURPOSE": "Objetivo",
    "AIM": "Objetivo",
    "AIMS": "Objetivo",
    "METHODS": "Métodos",
    "MATERIALS AND METHODS": "Métodos",
    "DESIGN": "Diseño",
    "RESULTS": "Resultados",
    "FINDINGS": "Resultados",
    "DISCUSSION": "Discusión",
    "CONCLUSION": "Conclusiones",
    "CONCLUSIONS": "Conclusiones",
}

# Cuántos autores entran en los metadatos antes de cortar con "et al.". Un
# artículo de consorcio trae 40+; la cita necesita el primero, no la lista.
MAX_AUTORES = 3


def _texto_de(elemento) -> str:
    """
    Aplana un elemento con marcado adentro.

    `ArticleTitle` y `AbstractText` pueden traer `<i>`, `<sub>` o `<b>`, y
    `findtext` devuelve solo el texto anterior al primer hijo: un título con
    una cursiva a la mitad se trunca ahí en silencio.
    """
    if elemento is None:
        return ""
    return "".join(elemento.itertext()).strip()


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
    """
    Obtiene los detalles de un artículo de PubMed dado su PMID.

    Todos los paths van acotados desde la raíz del artículo en vez de con
    `.//`: el XML de PubMed incluye la lista de referencias, y cada referencia
    trae su propio `ArticleIdList`. Con `.//ArticleId` este artículo devuelve
    63 identificadores —los suyos y los de sus 60 referencias— y el DOI que se
    guardaba como propio podía ser el de un trabajo citado.
    """
    logger.info(f"Obteniendo artículo PubMed: {pmid}")
    vacio = {"pmid": pmid, "titulo": "", "abstract": "", "secciones": []}
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
                return vacio

            titulo = _texto_de(articulo.find("MedlineCitation/Article/ArticleTitle"))

            # Un abstract estructurado ya viene partido por el autor en
            # BACKGROUND/METHODS/RESULTS/CONCLUSIONS. Respetar ese corte es
            # gratis y mejor que cualquier heurística nuestra.
            secciones = []
            for elem in articulo.findall("MedlineCitation/Article/Abstract/AbstractText"):
                texto = _texto_de(elem)
                if not texto:
                    continue
                etiqueta = (elem.get("Label") or "").strip().upper()
                secciones.append({
                    "etiqueta": ETIQUETAS.get(etiqueta, etiqueta.capitalize()) if etiqueta else "Resumen",
                    "texto": texto,
                })

            journal = articulo.findtext("MedlineCitation/Article/Journal/Title", default="")

            autores = []
            for autor in articulo.findall("MedlineCitation/Article/AuthorList/Author"):
                last_name = autor.findtext("LastName", default="")
                fore_name = autor.findtext("ForeName", default="")
                if last_name:
                    autores.append(f"{last_name} {fore_name}".strip())

            fecha = articulo.findtext("MedlineCitation/Article/Journal/JournalIssue/PubDate/Year", default="")

            ids = {
                e.get("IdType"): e.text
                for e in articulo.findall("PubmedData/ArticleIdList/ArticleId")
            }

            return {
                "pmid": pmid,
                "titulo": titulo,
                # Se mantiene el abstract entero para quien lo quiera leer de
                # corrido; los chunks salen de `secciones`.
                "abstract": " ".join(s["texto"] for s in secciones),
                "secciones": secciones,
                "autores": autores,
                "journal": journal,
                "fecha": fecha,
                "doi": ids.get("doi", ""),
                "pmcid": ids.get("pmc", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
    except Exception as e:
        logger.error(f"Error obteniendo artículo {pmid}: {e}")
        return vacio

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


def _cita_corta(articulo: Dict[str, Any]) -> str:
    """Referencia legible: 'Pérez J et al., Circulation (2024)'."""
    autores = articulo.get("autores") or []
    firma = autores[0] if autores else ""
    if len(autores) > 1:
        firma = f"{firma} et al."
    partes = [p for p in (firma, articulo.get("journal", "")) if p]
    referencia = ", ".join(partes)
    fecha = articulo.get("fecha")
    return f"{referencia} ({fecha})" if referencia and fecha else referencia


def chunkear_articulo(articulo: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convierte un artículo de PubMed en chunks, uno por sección del abstract.

    Mismo tratamiento que las etiquetas de openFDA, por los mismos dos motivos.
    El abstract entero como chunk único mezcla método y conclusión en un solo
    vector, y el validador —que pide evidencia para una afirmación concreta—
    recibe el diseño del estudio cuando preguntó por el resultado. Y los
    metadatos ya no cargan el abstract duplicado: se guardaba el dict completo
    del artículo, así que cada fila de resultado traía el texto dos veces.
    """
    secciones = articulo.get("secciones") or []
    if not secciones:
        return []

    chunker = ChunkerClinico()
    titulo = articulo.get("titulo") or f"PMID {articulo['pmid']}"
    cita = _cita_corta(articulo)
    encabezado = f"{titulo} — {cita}" if cita else titulo
    fuente = f"PubMed:{articulo['pmid']}"
    chunks: List[Dict[str, Any]] = []

    for seccion in secciones:
        fragmentos = chunker.partir_texto(seccion["texto"])
        for i, fragmento in enumerate(fragmentos, start=1):
            sufijo = f" [{i}/{len(fragmentos)}]" if len(fragmentos) > 1 else ""
            chunks.append({
                "texto": f"{encabezado}\n{seccion['etiqueta']}{sufijo}\n\n{fragmento}",
                "fuente": fuente,
                "seccion": seccion["etiqueta"],
                # Solo lo que identifica y permite volver a la fuente. `pmid`,
                # `doi`, `url` y `titulo` son claves que `BuscadorHibrido`
                # promueve al ras del resultado para armar la cita.
                "metadata": {
                    "fuente_api": "PubMed",
                    "pmid": articulo["pmid"],
                    "titulo": titulo,
                    "doi": articulo.get("doi", ""),
                    "url": articulo.get("url", ""),
                    "journal": articulo.get("journal", ""),
                    "fecha": articulo.get("fecha", ""),
                    "autores": (articulo.get("autores") or [])[:MAX_AUTORES],
                },
            })

    return chunks


def chunkear_articulos(articulos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Aplana los chunks de varios artículos, salteando los que no traen abstract."""
    chunks: List[Dict[str, Any]] = []
    sin_abstract = 0
    for articulo in articulos:
        del_articulo = chunkear_articulo(articulo)
        if not del_articulo:
            sin_abstract += 1
        chunks.extend(del_articulo)

    if sin_abstract:
        logger.warning("%d artículo(s) sin abstract: no entran al corpus.", sin_abstract)
    return chunks
