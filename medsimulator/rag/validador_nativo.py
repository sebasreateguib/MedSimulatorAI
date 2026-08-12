"""
Módulo de validación utilizando la funcionalidad nativa de citas (citations) de Anthropic.
"""

import logging
import anthropic
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ValidadorNativo:
    """
    Validador que utiliza la API de documentos/citas nativa de Anthropic 
    para fundamentar las afirmaciones generadas.
    """
    
    def __init__(self):
        logger.info("Inicializando ValidadorNativo (Anthropic Citations)")
        self._client = anthropic.AsyncAnthropic()
        
    async def validar(self, afirmacion: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Valida una afirmación contra un conjunto de chunks de contexto.
        """
        logger.info("Iniciando validación con Anthropic Citations")
        
        documentos = []
        for i, chunk in enumerate(chunks):
            titulo = f"{chunk.get('fuente', 'Desconocido')} - p.{chunk.get('pagina', 'N/A')}"
            documentos.append({
                "type": "document",
                "source": {
                    "type": "text",
                    "media_type": "text/plain",
                    "data": chunk.get("texto", "")
                },
                "title": titulo,
                "citations": {"enabled": True}
            })
            
        try:
            response = await self._client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": [
                        *documentos,
                        {"type": "text", "text": f"Por favor evalúa si esta afirmación está respaldada por los documentos proporcionados: '{afirmacion}'. Cita extensamente las partes relevantes."}
                    ]}
                ]
            )
            
            citas_extraidas = []
            explicacion = ""
            
            for block in response.content:
                if block.type == "text":
                    explicacion += block.text
                    if hasattr(block, "citations") and block.citations:
                        for cita in block.citations:
                            citas_extraidas.append({
                                "texto_citado": cita.cited_text,
                                "documento": cita.document_title
                            })
                            
            return {
                "valido": len(citas_extraidas) > 0,
                "citas": citas_extraidas,
                "explicacion": explicacion
            }
            
        except Exception as e:
            logger.error(f"Error al validar con Anthropic: {e}")
            return {
                "valido": False,
                "citas": [],
                "explicacion": f"Error: {str(e)}"
            }
