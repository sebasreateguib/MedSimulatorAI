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
        # El proveedor decide la forma de la llamada, no solo a quién se le
        # factura: la API nativa de Anthropic habla `messages.parse`, y Groq y
        # OpenRouter hablan el shape de OpenAI. Ver `_evaluar_anthropic` y
        # `_evaluar_openai`; cambiar de una a otra es editar agents.yaml.
        self.proveedor = self.config.get("provider", "anthropic")
        self.model = self.config.get("model", "claude-opus-5")
        self.max_tokens = self.config.get("max_tokens", 2000)
        # `temperature` solo viaja por la ruta OpenAI: Opus 5 la eliminó y
        # devuelve 400 si se la manda. En la ruta nativa el equivalente es
        # `effort`, que regula cuánto razona antes de puntuar.
        self.temperature = self.config.get("temperature", 0.0)
        self.effort = self.config.get("effort", "high")
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

    def _prompt_sistema(self, caso: Dict[str, Any], incluir_schema: bool) -> str:
        """
        Arma la consigna del evaluador.

        `incluir_schema` es la única diferencia entre las dos rutas: la nativa
        recibe el schema como parámetro de la request y lo tiene garantizado,
        así que repetirlo en el prompt solo gastaría tokens de entrada.
        """
        diagnostico_correcto = caso.get("diagnostico_correcto", "")
        criterios = "\n".join(caso.get("criterios_diagnosticos", []))
        plan = "\n".join(caso.get("plan_tratamiento_esperado", []))

        prompt = (
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
            "y las listas en ítems de una línea. Denso y concreto, sin preámbulos.\n"
        )

        if incluir_schema:
            prompt += (
                "\nRespondé SOLO con un objeto JSON que cumpla este esquema, sin texto alrededor:\n"
                f"{json.dumps(EvaluacionClinica.model_json_schema(), ensure_ascii=False)}"
            )

        return prompt

    async def evaluar_final(self, historial: List[Dict[str, Any]], caso: Dict[str, Any]) -> EvaluacionClinica:
        """
        Produce el scorecard final estructurado utilizando Claude.
        """
        logger.info(
            "Generando evaluación final del estudiante (%s/%s)", self.proveedor, self.model
        )

        historial_texto = json.dumps(historial, indent=2, ensure_ascii=False)
        mensaje_usuario = (
            f"Aquí está el historial clínico:\n{historial_texto}\n"
            "Por favor, genera la evaluación en formato JSON estricto."
        )

        try:
            if self.proveedor == "anthropic":
                return await self._evaluar_anthropic(
                    self._prompt_sistema(caso, incluir_schema=False), mensaje_usuario
                )
            return await self._evaluar_openai(
                self._prompt_sistema(caso, incluir_schema=True), mensaje_usuario
            )

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

    async def _evaluar_anthropic(self, system_prompt: str, mensaje_usuario: str) -> EvaluacionClinica:
        """
        Ruta nativa de Anthropic.

        `output_format` manda el schema como parte de la request, así que el
        modelo no puede devolver otra cosa: se van las tres ramas de error que
        necesitaba la ruta OpenAI (respuesta vacía, JSON no parseable, campos
        faltantes) y `parsed_output` ya viene validado contra el modelo Pydantic.
        """
        respuesta = await self.client.messages.parse(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": mensaje_usuario}],
            output_format=EvaluacionClinica,
            output_config={"effort": self.effort},
        )

        # Mismo motivo que en la ruta OpenAI: un corte por límite de tokens deja
        # el scorecard incompleto, y sin este chequeo el fallo se vería como un
        # schema inválido en vez de como un max_tokens corto.
        if respuesta.stop_reason == "max_tokens":
            raise ValueError(
                f"El evaluador se cortó por max_tokens ({self.max_tokens}): "
                "el scorecard quedó incompleto."
            )

        if respuesta.parsed_output is None:
            raise ValueError("El evaluador no devolvió un scorecard.")

        return respuesta.parsed_output

    async def _evaluar_openai(self, system_prompt: str, mensaje_usuario: str) -> EvaluacionClinica:
        """
        Ruta compatible con OpenAI: la que usan Groq y OpenRouter.

        Acá el schema es una promesa del prompt, no del protocolo, así que hay
        que verificar a mano todo lo que la ruta nativa da garantizado.
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": mensaje_usuario},
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
