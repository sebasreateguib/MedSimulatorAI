"""
Agente Especialista para interconsultas.
"""
import logging
from typing import Dict, Any

from medsimulator.llm.client import get_client_for_agent

logger = logging.getLogger(__name__)

class AgenteEspecialista:
    """
    Agente que maneja consultas de especialistas (cardiólogo, radiólogo, etc).
    Razona sobre metadatos de hallazgos precargados.
    """
    ESPECIALIDADES = {
        "cardiologia": "Cardiólogo",
        "radiologia": "Radiólogo", 
        "neumologia": "Neumólogo",
        "neurologia": "Neurólogo",
        "gastroenterologia": "Gastroenterólogo"
    }
    
    def __init__(self):
        logger.info("Inicializando AgenteEspecialista")
        self.client, self.config = get_client_for_agent("especialista")
        self.model = self.config.get("model", "deepseek/deepseek-chat")
        self.temperature = self.config.get("temperature", 0.3)

    async def consultar(self, especialidad: str, pregunta: str, caso: Dict[str, Any]) -> str:
        """
        Responde a una interconsulta basada en los hallazgos.
        
        Args:
            especialidad: Tipo de especialista (ej. 'cardiologia').
            pregunta: Pregunta del estudiante.
            caso: Datos del caso clínico.
            
        Returns:
            Opinión o reporte del especialista.
        """
        logger.debug(f"Consulta a {especialidad}: {pregunta}")
        
        rol = self.ESPECIALIDADES.get(especialidad.lower(), "Especialista")
        
        # Extraer hallazgos relevantes (laboratorios, ECG, imágenes)
        hallazgos_ecg = caso.get("hallazgos_ecg", "")
        labs = caso.get("resultados_laboratorio", caso.get("laboratorios", {}))
        
        contexto_hallazgos = f"Hallazgos ECG: {hallazgos_ecg}\n"
        contexto_hallazgos += f"Laboratorios: {labs}\n"
        
        system_prompt = (
            f"Eres un {rol} experto de interconsulta en un hospital.\n"
            f"El médico a cargo (un estudiante) te está haciendo una pregunta sobre un paciente.\n"
            f"Aquí tienes los hallazgos clínicos conocidos sobre este paciente:\n"
            f"{contexto_hallazgos}\n\n"
            "REGLAS:\n"
            "1. Responde a la pregunta del médico basándote EXCLUSIVAMENTE en los hallazgos provistos.\n"
            "2. Proporciona una opinión técnica y profesional desde tu especialidad.\n"
            "3. No reveles el diagnóstico final de inmediato a menos que sea obvio por tu interpretación; en lugar de eso, describe tus hallazgos, tu impresión diagnóstica y sugiere pasos a seguir.\n"
            "4. Sé conciso pero exhaustivo en tu análisis."
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": pregunta}
                ],
                temperature=self.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error en interconsulta con {especialidad}: {e}")
            return f"Lo siento, como {rol} no estoy disponible en este momento."
