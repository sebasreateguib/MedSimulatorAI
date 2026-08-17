"""
Módulo de búsqueda híbrida que combina BM25 (léxica), pgvector (semántica) y reranking.
"""

import json
import logging
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from sqlalchemy import select

from medsimulator.db.models import Chunk
from medsimulator.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)

# Qué claves de `Chunk.metadatos` suben al nivel del resultado. La página es la
# que importa: sin ella una cita dice "según la guía" y no "según la guía, p. 42",
# que es la diferencia entre una referencia y una referencia verificable.
CLAVES_PROMOVIDAS = ("pagina", "paginas", "titulo", "url", "doi", "pmid")


def _metadatos_de(chunk: Chunk) -> Dict[str, Any]:
    """
    Lee `Chunk.metadatos` —que es Text con JSON adentro, no JSONB— y devuelve
    las claves que el resto del sistema espera al ras del resultado.

    Un chunk viejo, mal serializado o sin metadatos no puede tumbar la búsqueda
    entera: se registra y se sigue sin ellos.
    """
    crudo = getattr(chunk, "metadatos", None)
    if not crudo:
        return {}

    try:
        datos = json.loads(crudo)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Chunk %s tiene metadatos ilegibles; se ignoran.", chunk.id)
        return {}

    if not isinstance(datos, dict):
        return {}

    promovidas = {c: datos[c] for c in CLAVES_PROMOVIDAS if datos.get(c) is not None}
    # El resto viaja agrupado: no se pierde, pero tampoco pisa claves propias
    # del resultado como `texto` o `score_semantico`.
    return {**promovidas, "metadatos": datos}


class BuscadorHibrido:
    """
    Buscador híbrido que integra búsqueda léxica y vectorial, 
    seguida de un paso de reranking con BAAI/bge-reranker-v2-m3.
    """
    
    def __init__(self, session_factory, embedding_service: EmbeddingService):
        """
        `session_factory` es el `async_sessionmaker` de `medsimulator.db`: la
        consulta vectorial se hace sobre el mismo engine asíncrono que usa la
        API, no sobre una sesión sincrónica aparte.
        """
        self.session_factory = session_factory
        self.embedding_service = embedding_service
        self._reranker = None
        logger.info("Inicializando BuscadorHibrido")
        
    @property
    def reranker(self):
        if self._reranker is None:
            logger.info("Cargando modelo de reranking BAAI/bge-reranker-v2-m3")
            from FlagEmbedding import FlagReranker
            self._reranker = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)
        return self._reranker

    async def buscar(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        logger.info(f"Ejecutando búsqueda híbrida para: '{query}' (top_k={top_k})")
        
        # 1. Generar embedding de la query
        query_embedding = self.embedding_service.generar_embedding_query(query)
        
        # 2. Búsqueda semántica (top_k amplio para recall)
        semantic_results = await self._busqueda_semantica(query_embedding, top_k=top_k*4)
        
        # 3. Búsqueda léxica (BM25) sobre el mismo corpus o uno general
        # Para RRF, idealmente evaluamos todos los chunks candidatos
        lexical_results = self._busqueda_lexica(query, semantic_results, top_k=top_k*4)
        
        # 4. Fusión de resultados (RRF)
        fusionados = self._fusionar_rrf(semantic_results, lexical_results)
        
        # 5. Reranking con cross-encoder
        resultados_finales = self._reranquear(query, fusionados, top_k)
        
        return resultados_finales

    async def _busqueda_semantica(self, query_embedding: List[float], top_k: int) -> List[Dict[str, Any]]:
        """Búsqueda vectorial en la BD usando pgvector."""
        # La distancia se pide como columna y no solo en el ORDER BY: así el
        # score que se propaga al RRF es el real y no un 1.0 fijo para todos.
        distancia = Chunk.embedding.cosine_distance(query_embedding).label("distancia")
        stmt = select(Chunk, distancia).order_by(distancia).limit(top_k)

        resultados = []
        async with self.session_factory() as session:
            for chunk, dist in (await session.execute(stmt)).all():
                fila = {
                    "id": chunk.id,
                    "texto": chunk.texto,
                    "fuente": chunk.documento_origen,
                    "seccion": chunk.seccion,
                    # cosine_distance ∈ [0, 2]; la similitud es su complemento.
                    "score_semantico": 1.0 - dist,
                }
                fila.update(_metadatos_de(chunk))
                resultados.append(fila)
        return resultados

    def _busqueda_lexica(self, query: str, corpus: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        """Búsqueda BM25 sobre los documentos candidatos."""
        if not corpus:
            return []
        tokenized_corpus = [doc["texto"].lower().split() for doc in corpus]
        bm25 = BM25Okapi(tokenized_corpus)
        tokenized_query = query.lower().split()
        doc_scores = bm25.get_scores(tokenized_query)
        
        resultados = []
        for i, doc in enumerate(corpus):
            doc_copy = doc.copy()
            doc_copy["score_lexico"] = doc_scores[i]
            resultados.append(doc_copy)
            
        resultados.sort(key=lambda x: x["score_lexico"], reverse=True)
        return resultados[:top_k]

    def _fusionar_rrf(self, semantic_results: List[Dict], lexical_results: List[Dict], k: int = 60) -> List[Dict]:
        """Fusión Reciprocal Rank Fusion."""
        rankings = {}
        
        for rank, doc in enumerate(semantic_results):
            doc_id = doc["id"]
            if doc_id not in rankings:
                rankings[doc_id] = {"doc": doc, "score": 0}
            rankings[doc_id]["score"] += 1.0 / (k + rank + 1)
            
        for rank, doc in enumerate(lexical_results):
            doc_id = doc["id"]
            if doc_id not in rankings:
                rankings[doc_id] = {"doc": doc, "score": 0}
            rankings[doc_id]["score"] += 1.0 / (k + rank + 1)
            
        fusionados = [item["doc"] for item in sorted(rankings.values(), key=lambda x: x["score"], reverse=True)]
        return fusionados

    def _reranquear(self, query: str, results: List[Dict], top_k: int) -> List[Dict]:
        """
        Reranking avanzado usando modelo cross-encoder.

        Si el reranker no se puede usar, se devuelve el orden de la fusión RRF
        en lugar de propagar el error: el cross-encoder mejora el orden de los
        candidatos, no los produce. Quedarse sin él degrada la precisión; que
        tumbe la búsqueda entera deja al sistema sin recuperación ninguna, que
        es bastante peor.
        """
        if not results:
            return []

        pairs = [[query, doc["texto"]] for doc in results]
        try:
            scores = self.reranker.compute_score(pairs)
        except Exception as e:
            logger.warning(
                "Reranker no disponible (%s); se usa el orden de la fusión RRF.", e
            )
            return results[:top_k]

        # En caso de devolver un solo score cuando len(pairs)==1
        if isinstance(scores, float):
            scores = [scores]
            
        for doc, score in zip(results, scores):
            doc["score_rerank"] = score
            
        results.sort(key=lambda x: x["score_rerank"], reverse=True)
        return results[:top_k]
