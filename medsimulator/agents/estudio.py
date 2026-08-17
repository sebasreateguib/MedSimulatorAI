"""
Agente de estudio: conversa sobre el material que subió el estudiante y arma
flashcards a partir de él.

A diferencia del paciente o el especialista, este agente no interpreta ningún
rol clínico: responde apoyado en los fragmentos recuperados de la biblioteca
del usuario y tiene prohibido completar con lo que "sabe" el modelo. Si el
material no alcanza, lo dice.
"""

import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import ValidationError

from medsimulator.llm.client import get_client_for_agent
from medsimulator.llm.schemas import FlashcardGenerada, MazoGenerado

logger = logging.getLogger(__name__)

# Cuántos turnos previos se mandan al modelo. El material ya ocupa buena parte
# de la ventana: arrastrar la conversación entera empuja los fragmentos afuera.
TURNOS_DE_CONTEXTO = 8


class AgenteEstudio:
    """Chat fundamentado y generación de flashcards sobre el material del usuario."""

    def __init__(self):
        logger.info("Inicializando AgenteEstudio")
        self.client, self.config = get_client_for_agent("estudio")
        self.model = self.config.get("model", "llama-3.3-70b-versatile")
        self.temperature = self.config.get("temperature", 0.3)

        self.client_fichas, self.config_fichas = get_client_for_agent("flashcards")
        self.model_fichas = self.config_fichas.get("model", "llama-3.3-70b-versatile")

    # ── Contexto ────────────────────────────────────────────────────

    @staticmethod
    def formatear_contexto(fragmentos: List[Dict[str, Any]]) -> str:
        """
        Numera los fragmentos como [1], [2]… El número es el contrato con el
        frontend: el modelo cita por índice y la UI resuelve cada marca contra
        la lista de citas que viaja al final del stream.
        """
        bloques = []
        for i, f in enumerate(fragmentos, start=1):
            cabecera = f"[{i}] {f.get('fuente', 'Material')}"
            if f.get("pagina"):
                cabecera += f", pág. {f['pagina']}"
            if f.get("seccion"):
                cabecera += f" — {f['seccion']}"
            bloques.append(f"{cabecera}\n{f['texto']}")
        return "\n\n".join(bloques)

    def _prompt_sistema(self, fragmentos: List[Dict[str, Any]]) -> str:
        if not fragmentos:
            return (
                "Sos un tutor de medicina que solo puede responder con el material "
                "de estudio del alumno. En esta consulta no se recuperó ningún "
                "fragmento: explicá que no encontraste nada en su material y "
                "sugerile subir el documento correspondiente o reformular la "
                "pregunta. No respondas de memoria."
            )

        return (
            "Sos un tutor de medicina que ayuda a un estudiante a entender SU material.\n\n"
            "MATERIAL DISPONIBLE (fragmentos recuperados de sus documentos):\n"
            f"{self.formatear_contexto(fragmentos)}\n\n"
            "REGLAS:\n"
            "1. Respondé únicamente con lo que dicen los fragmentos. Si el material no "
            "alcanza para responder, decilo explícitamente en vez de completar de memoria.\n"
            "2. Citá con la marca [n] al final de cada afirmación que salga de un fragmento. "
            "Usá los números tal como aparecen arriba.\n"
            "3. Escribí en español, claro y directo, con el nivel de un docente de facultad.\n"
            "4. Cuando el estudiante pida un resumen o un esquema, respetá la estructura del "
            "material: no inventes secciones que no están.\n"
            "5. Nada de esto es consejo médico para pacientes reales: es material de estudio.\n\n"
            "FORMATO (la interfaz renderiza Markdown):\n"
            "- Una respuesta corta va en prosa, sin encabezados ni viñetas: titular dos "
            "oraciones las vuelve más difíciles de leer, no más ordenadas.\n"
            "- Enumeraciones —criterios, pasos, diferenciales— en lista con '- '.\n"
            "- Comparaciones de varios elementos por varios atributos (fármacos por dosis y "
            "vía, escalas por umbral y conducta), en tabla de Markdown.\n"
            "- **Negrita** para el término clave de cada punto: dosis, valores de corte, "
            "nombres de escalas. Con moderación.\n"
            "- Encabezados '## ' solo si la respuesta cubre varios temas separados.\n"
            "- Nada de HTML."
        )

    # ── Chat ────────────────────────────────────────────────────────

    async def responder_stream(
        self,
        mensaje: str,
        historial: List[Dict[str, str]],
        fragmentos: List[Dict[str, Any]],
    ) -> AsyncGenerator[str, None]:
        """Responde token a token sobre los fragmentos recuperados."""
        mensajes = [{"role": "system", "content": self._prompt_sistema(fragmentos)}]
        for turno in historial[-TURNOS_DE_CONTEXTO:]:
            if turno.get("role") in ("user", "assistant") and turno.get("content"):
                mensajes.append({"role": turno["role"], "content": turno["content"]})
        mensajes.append({"role": "user", "content": mensaje})

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=mensajes,
                temperature=self.temperature,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Error en el chat de estudio: {e}", exc_info=True)
            yield "No pude generar la respuesta. Revisá la conexión con el proveedor del modelo."

    # ── Flashcards ──────────────────────────────────────────────────

    async def generar_flashcards(
        self,
        fragmentos: List[Dict[str, Any]],
        cantidad: int = 10,
        tema: Optional[str] = None,
    ) -> MazoGenerado:
        """
        Arma un mazo a partir del material. Devuelve JSON estructurado; si el
        modelo entrega algo que no valida, se propaga el error para que el
        endpoint responda 502 en vez de guardar un mazo a medias.
        """
        logger.info(f"Generando {cantidad} flashcards (tema={tema or 'todo el material'})")

        system_prompt = (
            "Sos un tutor de medicina que arma tarjetas de repaso a partir del material "
            "de estudio de un alumno.\n\n"
            f"MATERIAL:\n{self.formatear_contexto(fragmentos)}\n\n"
            "REGLAS:\n"
            f"1. Generá exactamente {cantidad} tarjetas, salvo que el material no dé para tantas.\n"
            "2. Cada tarjeta sale del material: nada de conocimiento externo.\n"
            "3. El anverso es una pregunta concreta (no 'Hablá sobre X'); el reverso responde "
            "en 1-3 oraciones, completo pero sin relleno.\n"
            "4. Priorizá lo evaluable: definiciones, criterios diagnósticos, dosis, mecanismos, "
            "diferenciales, valores de corte.\n"
            "5. En 'fuente' poné el nombre del documento del fragmento que usaste y en 'pagina' "
            "su página cuando el fragmento la traiga.\n\n"
            'Respondé SOLO con un JSON con esta forma: {"titulo": "...", "flashcards": '
            '[{"anverso": "...", "reverso": "...", "fuente": "...", "pagina": 1}]}'
        )

        pedido = (
            f"Generá el mazo sobre: {tema}." if tema
            else "Generá el mazo cubriendo los temas centrales del material."
        )

        response = await self.client_fichas.chat.completions.create(
            model=self.model_fichas,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": pedido},
            ],
            temperature=self.config_fichas.get("temperature", 0.4),
            response_format={"type": "json_object"},
        )

        crudo = response.choices[0].message.content or "{}"
        try:
            datos = json.loads(crudo)
        except json.JSONDecodeError as e:
            logger.error(f"El generador de flashcards no devolvió JSON válido: {crudo[:400]}")
            raise ValueError("El modelo no devolvió un mazo en formato válido.") from e

        # Algunos modelos devuelven la lista pelada o la envuelven en otra clave.
        if isinstance(datos, list):
            datos = {"titulo": tema or "Mazo de repaso", "flashcards": datos}
        datos.setdefault("titulo", tema or "Mazo de repaso")

        try:
            mazo = MazoGenerado(**datos)
        except ValidationError as e:
            logger.error(f"Mazo inválido: {e}")
            raise ValueError("El modelo devolvió un mazo con campos faltantes.") from e

        if not mazo.flashcards:
            raise ValueError("El material no alcanzó para generar tarjetas.")

        mazo.flashcards = self._completar_fuentes(mazo.flashcards[:cantidad], fragmentos)
        return mazo

    @staticmethod
    def _completar_fuentes(
        flashcards: List[FlashcardGenerada],
        fragmentos: List[Dict[str, Any]],
    ) -> List[FlashcardGenerada]:
        """
        Rellena la fuente que el modelo haya omitido con el documento dominante
        del contexto: una tarjeta sin origen no se puede volver a mirar.
        """
        if not fragmentos:
            return flashcards

        fuente_por_defecto = fragmentos[0].get("fuente")
        for ficha in flashcards:
            if not ficha.fuente:
                ficha.fuente = fuente_por_defecto
        return flashcards
