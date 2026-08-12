"""
Agente Tutor y Evaluador del desempeño del estudiante.
"""
import logging
import json
from typing import Dict, Any, List, Optional
from pydantic import ValidationError

from medsimulator.llm.client import get_client_for_agent
from medsimulator.llm.schemas import EvaluacionClinica

logger = logging.getLogger(__name__)

class AgenteTutor:
    """
    Agente que evalúa silenciosamente el progreso del estudiante,
    detecta errores críticos para interrumpir y genera el scorecard final.
    """
    def __init__(self):
        logger.info("Inicializando AgenteTutor")
        self.client, self.config = get_client_for_agent("tutor")
        self.model = self.config.get("model", "claude-3-opus-20240229") # Asumiendo Claude Opus real
        self.temperature = self.config.get("temperature", 0.0)
        self._eventos: List[Dict[str, Any]] = []
        self._alertas: List[Dict[str, Any]] = []

    def registrar_evento(self, evento: Dict[str, Any]) -> None:
        """Registra un evento de herramienta para evaluación."""
        self._eventos.append(evento)

    async def evaluar_turno_rapido(self, evento: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluación rápida y económica para detectar errores críticos durante la simulación.
        
        Args:
            evento: Datos de la acción tomada.
            
        Returns:
            Alerta si es crítica, de lo contrario None.
        """
        logger.debug(f"Tutor evaluando turno rápido: {evento.get('herramienta', 'desconocida')}")
        # En una versión real, esto sería una llamada rápida a un modelo como Haiku o Llama-8B
        # Por simplificación, haremos una regla hardcodeada o una evaluación mock si es extremadamente obvio.
        # Por ahora, simplemente no interrumpe a menos que haya un patrón claro.
        
        # Ejemplo: si el evento es recetar algo muy peligroso (se evaluaría con LLM).
        return None

    def debe_interrumpir(self, severidad: str) -> bool:
        """
        Determina si el tutor debe interrumpir la simulación.
        """
        return severidad in ["alta", "critica"]

    async def evaluar_final(self, historial: List[Dict[str, Any]], caso: Dict[str, Any]) -> EvaluacionClinica:
        """
        Produce el scorecard final estructurado utilizando Claude.
        """
        logger.info("Generando evaluación final del estudiante")
        
        historial_texto = json.dumps(historial, indent=2, ensure_ascii=False)
        diagnostico_correcto = caso.get("diagnostico_correcto", "")
        criterios = "\n".join(caso.get("criterios_diagnosticos", []))
        plan = "\n".join(caso.get("plan_tratamiento_esperado", []))
        
        system_prompt = (
            "Eres un médico tutor experto evaluando el desempeño de un estudiante de medicina.\n"
            "Analiza el historial de interacción del estudiante con el paciente y el uso de herramientas clínicas.\n\n"
            f"DATOS DEL CASO:\n"
            f"Diagnóstico correcto: {diagnostico_correcto}\n"
            f"Criterios esperados que el estudiante debió identificar:\n{criterios}\n"
            f"Plan de tratamiento esperado:\n{plan}\n\n"
            "INSTRUCCIONES DE EVALUACIÓN:\n"
            "1. Puntaje Total (0-100): Asigna una nota justa.\n"
            "2. Razonamiento diagnóstico: Evalúa si las preguntas y pruebas solicitadas tenían sentido lógico.\n"
            "3. Costo-efectividad: ¿Pidió pruebas de más? ¿Pidió pruebas muy costosas sin justificación?\n"
            "4. Pruebas innecesarias: Lista específica de laboratorios o imágenes que no debió pedir.\n"
            "5. Errores críticos: Acciones que pusieron en peligro al paciente.\n"
            "6. Retroalimentación: Un mensaje final constructivo.\n\n"
            "Debe responder obligatoriamente con un JSON que cumpla el esquema de la evaluación."
        )
        
        schema_json = EvaluacionClinica.model_json_schema()
        
        try:
            # Usando tool calling con Claude para asegurar formato estructurado
            # Se requiere anthropic API
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                temperature=self.temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Aquí está el historial clínico:\n{historial_texto}\nPor favor, genera la evaluación en formato JSON estricto."}
                ],
                tools=[
                    {
                        "name": "generar_evaluacion",
                        "description": "Genera el reporte de evaluación estructurado.",
                        "input_schema": schema_json
                    }
                ],
                tool_choice={"type": "tool", "name": "generar_evaluacion"}
            )
            
            # Extraer los argumentos del tool_call
            for content_block in response.content:
                if content_block.type == "tool_use" and content_block.name == "generar_evaluacion":
                    datos_eval = content_block.input
                    return EvaluacionClinica(**datos_eval)
                    
            raise ValueError("Claude no retornó el uso de la herramienta 'generar_evaluacion'")
            
        except Exception as e:
            logger.error(f"Error generando evaluación final: {e}")
            return EvaluacionClinica(
                puntaje_total=0,
                razonamiento_diagnostico=f"Error en la evaluación: {str(e)}",
                costo_efectividad="N/A",
                pruebas_innecesarias=[],
                errores_criticos=["Fallo en el sistema evaluador"],
                retroalimentacion="Por favor, contacta al administrador."
            )
