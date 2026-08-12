"""
Módulo para la extracción de información de fármacos e interacciones desde openFDA.
"""

import logging
import httpx
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

BASE_URL = "https://api.fda.gov"

async def buscar_medicamento(nombre: str) -> Dict[str, Any]:
    """Busca información sobre un medicamento (etiquetas) en la API de openFDA."""
    logger.info(f"Buscando medicamento en openFDA: {nombre}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/drug/label.json",
                params={"search": f"openfda.brand_name:\"{nombre}\""},
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("results"):
                return {"nombre": nombre, "error": "No encontrado"}
                
            resultado = data["results"][0]
            
            return {
                "nombre": nombre,
                "indicaciones": "\n".join(resultado.get("indications_and_usage", [])),
                "dosis": "\n".join(resultado.get("dosage_and_administration", [])),
                "contraindicaciones": "\n".join(resultado.get("contraindications", [])),
                "efectos_adversos": "\n".join(resultado.get("adverse_reactions", [])),
                "interacciones": "\n".join(resultado.get("drug_interactions", []))
            }
    except Exception as e:
        logger.error(f"Error buscando medicamento {nombre} en openFDA: {e}")
        return {"nombre": nombre, "error": str(e)}

async def obtener_interacciones(nombre_medicamento: str) -> List[Dict[str, Any]]:
    """Obtiene las interacciones documentadas de un medicamento."""
    medicamento = await buscar_medicamento(nombre_medicamento)
    if "error" in medicamento or not medicamento.get("interacciones"):
        return []
        
    # OpenFDA proporciona texto libre en 'drug_interactions' de las etiquetas.
    # Podríamos estructurar esto más, pero devolver el texto crudo estructurado como dict sirve.
    return [{"medicamento": nombre_medicamento, "descripcion_interaccion": medicamento["interacciones"]}]
