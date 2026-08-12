"""
Helpers de prompt caching para optimizar llamadas al LLM.
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

def verificar_cache(resp: Any) -> None:
    """
    Verifica y registra las métricas de uso de caché en la respuesta del LLM.
    
    Args:
        resp: Respuesta de la API del LLM (OpenAI/Anthropic).
    """
    try:
        u = resp.usage
        if not u:
            return
            
        input_tokens = getattr(u, 'input_tokens', 0)
        cache_creation = getattr(u, 'cache_creation_input_tokens', 0)
        cache_read = getattr(u, 'cache_read_input_tokens', 0)
        
        total = input_tokens + cache_creation + cache_read
        
        if total > 0:
            hit_rate = (100.0 * cache_read / total) if total > 0 else 0.0
            logger.info("cache: escritos=%d leídos=%d sin_cachear=%d hit_rate=%.0f%%",
                     cache_creation, cache_read, input_tokens, hit_rate)
    except Exception as e:
        logger.warning(f"No se pudieron leer las métricas de caché: {e}")

def build_system_message_with_cache(content: str, provider: str = "anthropic") -> Dict[str, Any]:
    """
    Construye un mensaje de sistema con control de caché según el proveedor.
    
    Args:
        content: Contenido del mensaje de sistema.
        provider: Proveedor para adaptar el formato de caché.
        
    Returns:
        Diccionario con el mensaje formateado.
    """
    if provider == "anthropic":
        return {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": content,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
        }
    
    # Formato genérico para otros proveedores
    return {
        "role": "system",
        "content": content
    }

def build_system_congelado(reglas: str, herramientas: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Construye un mensaje de sistema congelado (FROZEN prompt) que no varía con el tiempo,
    maximizando así la tasa de aciertos de la caché. No incluye variables dinámicas 
    como fechas o IDs únicos.
    
    Args:
        reglas: Reglas inmutables del sistema.
        herramientas: Definición estática de herramientas disponibles.
        
    Returns:
        Diccionario con el mensaje de sistema optimizado para caché.
    """
    content = reglas
    if herramientas:
        content += "\n\nHerramientas disponibles:\n"
        for h in herramientas:
            content += f"- {h.get('name', 'Herramienta')}: {h.get('description', '')}\n"
            
    return build_system_message_with_cache(content, provider="anthropic")
