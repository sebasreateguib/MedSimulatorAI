"""
Paquete RAG (Retrieval-Augmented Generation) para MedSimulator.
Maneja la ingesta, búsqueda vectorial, validación y generación fundamentada.
"""

from medsimulator.rag.embeddings import EmbeddingService
from medsimulator.rag.busqueda import BuscadorHibrido
from medsimulator.rag.validador_casero import ValidadorCasero
from medsimulator.rag.validador_nativo import ValidadorNativo

__all__ = [
    "EmbeddingService",
    "BuscadorHibrido",
    "ValidadorCasero",
    "ValidadorNativo",
]
