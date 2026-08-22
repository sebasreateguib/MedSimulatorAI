"""
Agente Paciente para roleplay clínico.
"""
import logging
from typing import Dict, Any, List, AsyncGenerator

from medsimulator.llm.client import get_client_for_agent

logger = logging.getLogger(__name__)

class AgentePaciente:
    """
    Agente que simula al paciente. Responde basado en una historia
    clínica oculta SIN revelar directamente el diagnóstico.
    """
    def __init__(self):
        logger.info("Inicializando AgentePaciente")
        self.client, self.config = get_client_for_agent("paciente")
        self.model = self.config.get("model", "openai/gpt-oss-120b")
        self.temperature = self.config.get("temperature", 0.8)

    def _construir_prompt(self, caso: Dict[str, Any]) -> str:
        """Construye el prompt de sistema del paciente."""
        datos_paciente = caso.get("paciente", {})
        nombre = datos_paciente.get("nombre", "Paciente")
        edad = datos_paciente.get("edad", 50)
        genero = datos_paciente.get("genero", "Desconocido")
        sintomas = ", ".join(datos_paciente.get("sintomas", []))
        estado_emocional = datos_paciente.get("estado_emocional", "Neutro")
        historia_oculta = datos_paciente.get("historia_oculta", "")
        
        prompt = (
            f"Eres un paciente en una simulación médica. Tu nombre es {nombre}, tienes {edad} años y tu género es {genero}.\n"
            f"Tus síntomas principales son: {sintomas}.\n"
            f"Tu estado emocional actual es: {estado_emocional}.\n\n"
            f"HISTORIA OCULTA (lo que sabes pero no ofreces a menos que el médico pregunte específicamente de manera empática):\n"
            f"{historia_oculta}\n\n"
            "REGLAS ESTRICTAS:\n"
            "1. NUNCA reveles el diagnóstico médico. Eres un paciente, no un médico.\n"
            "2. Responde de forma natural, humana y congruente con tu estado emocional.\n"
            "3. Mantente siempre en tu papel de paciente. No uses lenguaje médico avanzado a menos que sea razonable para tu personaje.\n"
            "4. Sé conciso. No des discursos largos; responde a lo que el médico (el estudiante) te pregunta."
        )
        return prompt

    def _construir_mensajes(self, mensaje: str, historial: List[Dict[str, Any]], caso: Dict[str, Any]) -> List[Dict[str, Any]]:
        system_prompt = self._construir_prompt(caso)
        mensajes = [{"role": "system", "content": system_prompt}]
        
        # Agregar el historial, filtrando para pasar sólo mensajes de user/assistant/system 
        # (algunos LLMs pueden fallar si pasamos mensajes 'tool' sin el id correcto, o podemos simplemente pasar el texto)
        for msg in historial:
            # Simplificar el historial para el LLM del paciente
            role = msg.get("role")
            if role in ["user", "assistant"]:
                mensajes.append({"role": role, "content": msg.get("content", "")})
                
        # Agregar el mensaje actual si no está en el historial
        if not mensajes or mensajes[-1].get("content") != mensaje:
            mensajes.append({"role": "user", "content": mensaje})
            
        return mensajes

    async def responder(self, mensaje: str, historial: List[Dict[str, Any]], caso: Dict[str, Any]) -> str:
        """
        Genera la respuesta del paciente ante el mensaje del estudiante.
        """
        logger.debug(f"Paciente procesando mensaje: {mensaje}")
        mensajes = self._construir_mensajes(mensaje, historial, caso)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=mensajes,
                temperature=self.temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("Error al generar respuesta del paciente: %s", e, exc_info=True)
            return "Lo siento doctor, me siento un poco mareado y no entendí la pregunta."

    async def responder_stream(self, mensaje: str, historial: List[Dict[str, Any]], caso: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """
        Genera la respuesta del paciente con streaming.
        """
        logger.debug(f"Paciente procesando mensaje (streaming): {mensaje}")
        mensajes = self._construir_mensajes(mensaje, historial, caso)
        
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=mensajes,
                temperature=self.temperature,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error("Error al generar respuesta del paciente por stream: %s", e, exc_info=True)
            yield "Lo siento doctor, me siento mal..."
