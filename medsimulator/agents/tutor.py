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


class EvaluacionFallida(RuntimeError):
    """
    El evaluador no pudo producir un scorecard.

    Antes esto se resolvía devolviendo una evaluación de puntaje 0 con el texto
    del error adentro. Esa nota falsa se guardaba en la base como cualquier
    otra: contaba en el promedio del estudiante y en las métricas. Un fallo de
    infraestructura tiene que verse como un fallo, no como un aplazo.
    """


class AgenteTutor:
    """
    Agente que evalúa silenciosamente el progreso del estudiante,
    detecta errores críticos para interrumpir y genera el scorecard final.
    """
    def __init__(self):
        logger.info("Inicializando AgenteTutor")
        self.client, self.config = get_client_for_agent("tutor")
        self.model = self.config.get("model", "anthropic/claude-opus-5")
        self.temperature = self.config.get("temperature", 0.0)
        self.max_tokens = self.config.get("max_tokens", 2000)
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
            "LARGO: el scorecard se corta si te extendés. 'razonamiento_diagnostico' en 100 "
            "palabras como máximo, 'costo_efectividad' y 'retroalimentacion' en 60 cada uno, "
            "y las listas en ítems de una línea. Denso y concreto, sin preámbulos.\n\n"
            "Respondé SOLO con un objeto JSON que cumpla este esquema, sin texto alrededor:\n"
            f"{json.dumps(EvaluacionClinica.model_json_schema(), ensure_ascii=False)}"
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Aquí está el historial clínico:\n{historial_texto}\nPor favor, genera la evaluación en formato JSON estricto."}
                ],
                response_format={"type": "json_object"},
            )

            eleccion = response.choices[0]
            crudo = eleccion.message.content or ""
            if not crudo.strip():
                raise ValueError("El evaluador devolvió una respuesta vacía.")

            # Un corte por límite de tokens deja el JSON abierto a la mitad. Sin
            # este chequeo el fallo aparece como "JSON inválido" y se pierde la
            # causa real, que es max_tokens corto para el largo del historial.
            if eleccion.finish_reason == "length":
                raise ValueError(
                    f"El evaluador se cortó por max_tokens ({self.max_tokens}): "
                    "el scorecard quedó incompleto."
                )

            try:
                datos_eval = json.loads(crudo)
            except json.JSONDecodeError as e:
                logger.error(f"El evaluador no devolvió JSON válido: {crudo[:400]}")
                raise ValueError("El evaluador no devolvió un JSON parseable.") from e

            try:
                return EvaluacionClinica(**datos_eval)
            except ValidationError as e:
                logger.error(f"Scorecard inválido: {e}")
                raise ValueError("El evaluador devolvió un scorecard con campos faltantes.") from e

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
