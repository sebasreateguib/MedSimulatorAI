"""
Módulo de búsqueda híbrida que combina BM25 (léxica), pgvector (semántica) y reranking.
"""

import logging
from typing import List, Dict, Any
from rank_bm25 import BM25Okapi
from medsimulator.rag.embeddings import EmbeddingService
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class BuscadorHibrido:
    """
    Buscador híbrido que integra búsqueda léxica y vectorial, 
    seguida de un paso de reranking con BAAI/bge-reranker-v2-m3.
    """
    
    def __init__(self, session_factory, embedding_service: EmbeddingService):
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
        try:
            from medsimulator.db.models import Chunk
        except ImportError:
            logger.warning("No se pudo importar Chunk de medsimulator.db.models")
            return []
            
        resultados = []
        with self.session_factory() as session:
            stmt = select(Chunk).order_by(Chunk.vector.cosine_distance(query_embedding)).limit(top_k)
            for chunk in session.execute(stmt).scalars():
                resultados.append({
                    "id": chunk.id,
                    "texto": chunk.texto,
                    "fuente": chunk.fuente,
                    "pagina": getattr(chunk, 'pagina', None),
                    "score_semantico": 1.0 # pgvector devuelve distancia, simplificado aquí
                })
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
        """Reranking avanzado usando modelo cross-encoder."""
        if not results:
            return []
            
        pairs = [[query, doc["texto"]] for doc in results]
        scores = self.reranker.compute_score(pairs)
        
        # En caso de devolver un solo score cuando len(pairs)==1
        if isinstance(scores, float):
            scores = [scores]
            
        for doc, score in zip(results, scores):
            doc["score_rerank"] = score
            
        results.sort(key=lambda x: x["score_rerank"], reverse=True)
        return results[:top_k]
