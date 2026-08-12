"""
Cliente LLM Multi-proveedor para MedSimulator AI.
"""
import logging
from typing import Optional, Any, Dict
from openai import AsyncOpenAI
import anthropic

from medsimulator.app.config import settings

logger = logging.getLogger(__name__)

# Cache de configuración de agentes para evitar lecturas repetidas
_agents_config_cache: Optional[Dict[str, Any]] = None

def cargar_config_agentes() -> Dict[str, Any]:
    """Carga y cachea la configuración de agentes."""
    global _agents_config_cache
    if _agents_config_cache is None:
        _agents_config_cache = settings.cargar_config_agentes()
    return _agents_config_cache

# Función para cargar proveedores dinámicamente para no fallar en tiempo de importación si faltan keys
def get_providers() -> Dict[str, tuple[str, str]]:
    return {
        "groq": ("https://api.groq.com/openai/v1", settings.GROQ_API_KEY),
        "openrouter": ("https://openrouter.ai/api/v1", settings.OPENROUTER_API_KEY),
    }

def get_client(provider: str) -> Any:
    """
    Retorna el cliente asíncrono adecuado según el proveedor especificado.
    
    Args:
        provider: Nombre del proveedor ('groq', 'openrouter', 'anthropic').
        
    Returns:
        Cliente asíncrono configurado.
    """
    logger.debug(f"Obteniendo cliente LLM para el proveedor: {provider}")
    providers = get_providers()
    
    if provider in providers:
        base_url, api_key = providers[provider]
        if not api_key:
            logger.warning(f"API key para {provider} no configurada.")
            
        return AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
        )
    elif provider == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("API key para Anthropic no configurada.")
            
        return anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
        )
    else:
        raise ValueError(f"Proveedor no soportado: {provider}")

def get_client_for_agent(agent_name: str) -> tuple[Any, Dict[str, Any]]:
    """
    Obtiene el cliente y la configuración específica del modelo para un agente.
    
    Args:
        agent_name: Nombre del agente según agents.yaml.
        
    Returns:
        Tupla con el cliente (AsyncOpenAI/AsyncAnthropic) y el diccionario de configuración del agente.
    """
    agentes_config = cargar_config_agentes()
    if agent_name not in agentes_config:
        raise ValueError(f"Agente '{agent_name}' no encontrado en la configuración.")
        
    config = agentes_config[agent_name]
    provider = config.get("provider", "openrouter")
    
    client = get_client(provider)
    return client, config
