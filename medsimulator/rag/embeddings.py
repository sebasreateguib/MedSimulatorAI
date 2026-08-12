"""
Módulo para la generación de embeddings utilizando modelos locales.
Emplea sentence-transformers con el modelo BAAI/bge-m3 para embeddings multilingües.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    Servicio para generar embeddings usando el modelo BAAI/bge-m3.
    La carga del modelo es perezosa (lazy) para evitar demoras innecesarias.
    """
    
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self._model = None
        
    @property
    def model(self):
        """Carga perezosa del modelo."""
        if self._model is None:
            logger.info(f"Cargando modelo de embeddings: {self.model_name}")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def generar_embedding(self, texto: str) -> List[float]:
        """
        Genera el embedding para un único texto de documento.
        """
        texto_formateado = f"passage: {texto}"
        embedding = self.model.encode(texto_formateado, normalize_embeddings=True)
        return embedding.tolist()
        
    def generar_embedding_query(self, query: str) -> List[float]:
        """
        Genera el embedding para una consulta.
        """
        query_formateada = f"query: {query}"
        embedding = self.model.encode(query_formateada, normalize_embeddings=True)
        return embedding.tolist()
        
    def generar_embeddings_batch(self, textos: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Genera embeddings para una lista de textos (procesamiento por lotes).
        """
        textos_formateados = [f"passage: {t}" for t in textos]
        embeddings = self.model.encode(
            textos_formateados,
            batch_size=batch_size,
            normalize_embeddings=True
        )
        return embeddings.tolist()
