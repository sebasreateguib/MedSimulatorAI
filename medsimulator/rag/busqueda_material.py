"""
Búsqueda sobre el material privado de un usuario (`chunks_documento`).

Es hermana de `BuscadorHibrido`, pero no es la misma: aquella consulta el
corpus común y remata con un cross-encoder (BAAI/bge-reranker-v2-m3), que son
2 GB de modelo y varios segundos por consulta. Acá el corpus es chico —los
apuntes de una persona— y la recuperación corre dentro de un chat interactivo,
así que se queda en vectorial + BM25 fusionados con RRF.

Toda consulta filtra por `usuario_id`: el material de un estudiante no puede
aparecer en el contexto de otro.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medsimulator.db.models import ChunkDocumento, Documento
from medsimulator.rag.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


class BuscadorMaterial:
    """Recupera los fragmentos del material del usuario más afines a una consulta."""

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.embedding_service = embedding_service or EmbeddingService()

    async def buscar(
        self,
        db: AsyncSession,
        usuario_id: int,
        consulta: str,
        top_k: int = 6,
        documento_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Devuelve hasta `top_k` fragmentos con su fuente y página.

        `documento_ids` restringe la búsqueda a los documentos que el usuario
        haya seleccionado en la biblioteca; si va vacío se busca en todo lo suyo.
        """
        # encode() de sentence-transformers es sincrónico y usa CPU/GPU a fondo:
        # dentro del event loop congelaría el resto de los requests.
        embedding = await asyncio.to_thread(
            self.embedding_service.generar_embedding_query, consulta
        )

        candidatos = await self._semanticos(
            db, usuario_id, embedding, top_k * 4, documento_ids
        )
        if not candidatos:
            return []

        lexicos = self._lexicos(consulta, candidatos)
        return self._fusionar_rrf(candidatos, lexicos)[:top_k]

    async def _semanticos(
        self,
        db: AsyncSession,
        usuario_id: int,
        embedding: List[float],
        limite: int,
        documento_ids: Optional[List[int]],
    ) -> List[Dict[str, Any]]:
        distancia = ChunkDocumento.embedding.cosine_distance(embedding).label("distancia")
        stmt = (
            select(ChunkDocumento, Documento.nombre, distancia)
            .join(Documento, Documento.id == ChunkDocumento.documento_id)
            .where(ChunkDocumento.usuario_id == usuario_id)
            .order_by(distancia)
            .limit(limite)
        )
        if documento_ids:
            stmt = stmt.where(ChunkDocumento.documento_id.in_(documento_ids))

        return [
            {
                "id": chunk.id,
                "documento_id": chunk.documento_id,
                "texto": chunk.texto,
                "seccion": chunk.seccion,
                "pagina": chunk.pagina,
                "fuente": nombre,
                # cosine_distance ∈ [0, 2]; la similitud es su complemento.
                "score_semantico": 1.0 - dist,
            }
            for chunk, nombre, dist in (await db.execute(stmt)).all()
        ]

    def _lexicos(self, consulta: str, corpus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        BM25 sobre los candidatos vectoriales. Rescata los aciertos textuales
        —una sigla, una dosis, un nombre comercial— que el embedding diluye.
        """
        bm25 = BM25Okapi([doc["texto"].lower().split() for doc in corpus])
        scores = bm25.get_scores(consulta.lower().split())

        ordenados = sorted(
            ({**doc, "score_lexico": score} for doc, score in zip(corpus, scores)),
            key=lambda d: d["score_lexico"],
            reverse=True,
        )
        return ordenados

    def _fusionar_rrf(
        self,
        semanticos: List[Dict[str, Any]],
        lexicos: List[Dict[str, Any]],
        k: int = 60,
    ) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion: combina por posición, no por score crudo."""
        rankings: Dict[int, Dict[str, Any]] = {}

        for lista in (semanticos, lexicos):
            for posicion, doc in enumerate(lista):
                entrada = rankings.setdefault(doc["id"], {"doc": doc, "score": 0.0})
                entrada["score"] += 1.0 / (k + posicion + 1)

        ordenados = sorted(rankings.values(), key=lambda e: e["score"], reverse=True)
        return [{**e["doc"], "score_rrf": e["score"]} for e in ordenados]
