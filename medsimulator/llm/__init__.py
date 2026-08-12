"""
Módulo LLM para interacciones con modelos de lenguaje.
"""
import logging
from .client import get_client, get_client_for_agent, get_providers
from .schemas import (
    EvaluacionClinica, 
    AfirmacionValidada, 
    MensajeChat, 
    RespuestaAgente,
    ConfigAgente,
    CasoClinico
)
from .cache import verificar_cache, build_system_message_with_cache, build_system_congelado

logger = logging.getLogger(__name__)

__all__ = [
    "get_client",
    "get_client_for_agent",
    "get_providers",
    "EvaluacionClinica",
    "AfirmacionValidada",
    "MensajeChat",
    "RespuestaAgente",
    "ConfigAgente",
    "CasoClinico",
    "verificar_cache",
    "build_system_message_with_cache",
    "build_system_congelado"
]
