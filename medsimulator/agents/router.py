"""
Agente Router para clasificación de intenciones.
"""
import logging
import json
from typing import Literal

from medsimulator.llm.client import get_client_for_agent

logger = logging.getLogger(__name__)

TipoIntencion = Literal["anamnesis", "laboratorio", "imagen", "receta", "diagnostico", "interconsulta", "otro"]

class AgenteRouter:
    """
    Agente rápido que clasifica la intención del estudiante.
    Ideal para usar con un modelo pequeño y veloz (ej. Llama 3 8B).
    """
    def __init__(self):
        logger.info("Inicializando AgenteRouter")
        self.client, self.config = get_client_for_agent("router")
        self.model = self.config.get("model", "openai/gpt-oss-20b")
        self.temperature = self.config.get("temperature", 0.0)

    async def clasificar(self, mensaje: str) -> TipoIntencion:
        """
        Clasifica la intención del mensaje del estudiante.
        
        Args:
            mensaje: Mensaje del estudiante.
            
        Returns:
            Categoría de intención.
        """
        logger.debug(f"Clasificando intención de: {mensaje}")
        
        system_prompt = (
            "Eres un clasificador de intenciones para una simulación clínica.\n"
            "Clasifica la intención del estudiante de medicina según las siguientes categorías:\n"
            "- anamnesis: Hace preguntas al paciente sobre síntomas, dolor, historial, etc.\n"
            "- laboratorio: Solicita exámenes de sangre, orina, u otros fluidos.\n"
            "- imagen: Solicita radiografías, tomografías, ecografías, ECG, etc.\n"
            "- receta: Prescribe medicamentos, indica tratamiento o da indicaciones terapéuticas.\n"
            "- diagnostico: Comunica o establece un diagnóstico médico.\n"
            "- interconsulta: Pide opinión a otro especialista (cardiólogo, radiólogo, etc).\n"
            "- otro: Cualquier otra interacción (saludos, despedidas, comentarios sin sentido).\n\n"
            "Responde ÚNICAMENTE con un JSON válido con la clave 'intencion' y el valor de la categoría que mejor se ajuste."
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": mensaje}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            data = json.loads(content)
            intencion = data.get("intencion", "anamnesis").lower()
            
            valid_intents = ["anamnesis", "laboratorio", "imagen", "receta", "diagnostico", "interconsulta", "otro"]
            if intencion in valid_intents:
                return intencion
            else:
                return "otro"
                
        except Exception as e:
            logger.error(f"Error al clasificar intención: {e}")
            return "anamnesis"
