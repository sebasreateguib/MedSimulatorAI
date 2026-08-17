"""
Validación casera de afirmaciones clínicas contra el corpus.

Dos pasos, y el segundo es el que vale: primero el modelo descompone lo que
dijo el estudiante en afirmaciones y cita, para cada una, el texto literal del
chunk que la respalda; después el código busca esa cita dentro del chunk. Si no
está, el veredicto baja a `no_verificable` por más seguro que sonara el modelo.

Es la contracara de `ValidadorNativo`, que delega la fundamentación a las
citations nativas de Anthropic. Esta versión corre sobre cualquier proveedor
compatible con OpenAI —que es lo que el proyecto tiene cargado— a cambio de un
paso de verificación programática que allá viene de fábrica.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError

from medsimulator.llm.schemas import AfirmacionValidada

logger = logging.getLogger(__name__)


class RespuestaValidada(BaseModel):
    """Modelo estructurado para la respuesta completa y sus afirmaciones."""
    afirmaciones: List[AfirmacionValidada]


def _normalizar(texto: str) -> str:
    """
    Colapsa espacios y baja a minúsculas para comparar citas.

    El parser de PDF mete saltos de línea y espacios dobles donde el modelo
    escribe una oración corrida: sin esto, una cita correcta palabra por palabra
    fallaría la verificación por un `\\n` en el medio.
    """
    return re.sub(r"\s+", " ", texto).strip().lower()


class ValidadorCasero:
    """
    Validador que fuerza una salida estructurada del LLM y luego
    verifica programáticamente si la cita literal existe en el chunk original.
    """

    def __init__(self, llm_client=None, modelo: str = "", temperature: float = 0.0):
        logger.info("Inicializando ValidadorCasero (modelo=%s)", modelo or "sin definir")
        self.llm_client = llm_client
        self.modelo = modelo
        self.temperature = temperature

    # ── Contexto ────────────────────────────────────────────────────

    @staticmethod
    def _contexto(chunks: List[Dict[str, Any]]) -> str:
        """
        Numera los chunks por su id real y no por su posición: el modelo tiene
        que devolver ese mismo id en `chunk_id` para que la verificación pueda
        encontrar el texto contra el que comparar.
        """
        bloques = []
        for chunk in chunks:
            cabecera = f"[chunk_id: {chunk.get('id')}] {chunk.get('fuente', 'Desconocido')}"
            if chunk.get("pagina"):
                cabecera += f", p. {chunk['pagina']}"
            if chunk.get("seccion"):
                cabecera += f" — {chunk['seccion']}"
            bloques.append(f"{cabecera}\n{chunk.get('texto', '')}")
        return "\n\n".join(bloques)

    def _prompt(self, afirmacion: str, chunks: List[Dict[str, Any]]) -> str:
        return (
            "Sos un verificador clínico. Recibís una afirmación de un estudiante de "
            "medicina y fragmentos de guías de práctica clínica, y tenés que decidir si "
            "los fragmentos respaldan lo que dijo.\n\n"
            f"FRAGMENTOS:\n{self._contexto(chunks)}\n\n"
            "INSTRUCCIONES:\n"
            "1. Descomponé la afirmación en las afirmaciones verificables que contenga "
            "(un fármaco, una dosis, un criterio: cada una por separado).\n"
            "2. Para cada una, elegí el fragmento que la respalda o la contradice y copiá "
            "en 'cita_literal' el texto EXACTO de ese fragmento, carácter por carácter. "
            "No parafrasees, no arregles la ortografía, no completes con lo que sabés: la "
            "cita se busca después dentro del fragmento y si no aparece se descarta.\n"
            "3. 'chunk_id' es el id del fragmento del que sacaste la cita, tal como figura "
            "arriba entre corchetes.\n"
            "4. Veredicto: 'correcto' si el fragmento respalda la afirmación, 'incorrecto' "
            "si la contradice, 'no_verificable' si ningún fragmento habla del tema. Para "
            "'no_verificable' dejá 'cita_literal' y 'chunk_id' en cadena vacía.\n\n"
            'Respondé SOLO con un JSON con esta forma: {"afirmaciones": [{"afirmacion": '
            '"...", "chunk_id": "...", "cita_literal": "...", "veredicto": "correcto"}]}'
        )

    # ── Validación ──────────────────────────────────────────────────

    async def validar(self, afirmacion: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Valida una afirmación usando un LLM para extraer citas, y luego
        verificándolas literalmente contra los chunks.

        Devuelve el contrato común de los validadores:
        `{valido, afirmaciones, citas, explicacion}`. `valido` es None cuando no
        se pudo emitir un juicio —sin cliente, sin corpus, error del proveedor—,
        que no es lo mismo que un juicio negativo.
        """
        if not self.llm_client:
            logger.warning("ValidadorCasero sin cliente LLM: no se puede validar.")
            return self._sin_juicio("El validador no tiene un cliente LLM configurado.")

        if not chunks:
            return self._sin_juicio("No hay fragmentos del corpus contra los que validar.")

        logger.info("Validando contra %d fragmentos: %s", len(chunks), afirmacion[:80])

        try:
            response = await self.llm_client.chat.completions.create(
                model=self.modelo,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": self._prompt(afirmacion, chunks)},
                    {"role": "user", "content": f"Afirmación a validar: {afirmacion}"},
                ],
                response_format={"type": "json_object"},
            )
            crudo = response.choices[0].message.content or ""
        except Exception as e:
            logger.error("Error llamando al LLM validador: %s", e, exc_info=True)
            return self._sin_juicio(f"El validador no pudo consultar al modelo: {e}")

        respuesta = self._parsear(crudo)
        if respuesta is None:
            return self._sin_juicio("El validador no devolvió un JSON con la forma esperada.")

        # El paso que le da sentido a todo: hasta acá el veredicto es lo que el
        # modelo dice de sí mismo.
        verificada = self._verificar_citas(respuesta, {str(c.get("id")): c for c in chunks})

        afirmaciones = [a.model_dump() for a in verificada.afirmaciones]
        for a, original in zip(afirmaciones, verificada.afirmaciones):
            chunk = next((c for c in chunks if str(c.get("id")) == original.chunk_id), None)
            a["fuente"] = chunk.get("fuente") if chunk else None
            a["pagina"] = chunk.get("pagina") if chunk else None

        juzgadas = [a for a in verificada.afirmaciones if a.veredicto != "no_verificable"]
        return {
            # Sin ninguna afirmación juzgable no hay veredicto: el corpus no
            # cubre el tema, que no es lo mismo que "el estudiante se equivocó".
            "valido": all(a.veredicto == "correcto" for a in juzgadas) if juzgadas else None,
            "afirmaciones": afirmaciones,
            "citas": [
                {
                    "texto_citado": a["cita_literal"],
                    "documento": a.get("fuente"),
                    "pagina": a.get("pagina"),
                }
                for a in afirmaciones
                if a["veredicto"] != "no_verificable" and a["cita_literal"]
            ],
            "explicacion": self._resumir(afirmaciones),
        }

    @staticmethod
    def _sin_juicio(motivo: str) -> Dict[str, Any]:
        return {"valido": None, "afirmaciones": [], "citas": [], "explicacion": motivo}

    @staticmethod
    def _parsear(crudo: str) -> Optional[RespuestaValidada]:
        """Del texto del modelo al modelo Pydantic, tolerando envoltorios."""
        if not crudo.strip():
            return None
        try:
            datos = json.loads(crudo)
        except json.JSONDecodeError:
            logger.error("El validador no devolvió JSON válido: %s", crudo[:400])
            return None

        # Algunos modelos devuelven la lista pelada en vez del objeto.
        if isinstance(datos, list):
            datos = {"afirmaciones": datos}

        try:
            return RespuestaValidada(**datos)
        except ValidationError as e:
            logger.error("El validador devolvió afirmaciones inválidas: %s", e)
            return None

    def _verificar_citas(
        self,
        respuesta: RespuestaValidada,
        chunks_dict: Dict[str, Any],
    ) -> RespuestaValidada:
        """
        Baja a `no_verificable` toda afirmación cuya cita no aparezca de verdad
        en el chunk que dice haber citado. Es la única parte del circuito que no
        depende de la buena fe del modelo.
        """
        for a in respuesta.afirmaciones:
            if a.veredicto == "no_verificable":
                continue

            chunk = chunks_dict.get(a.chunk_id)
            if chunk is None:
                a.veredicto = "no_verificable"
                logger.warning("Chunk %s no está en el contexto provisto", a.chunk_id)
                continue

            if not a.cita_literal.strip():
                a.veredicto = "no_verificable"
                logger.warning("Afirmación sin cita literal: %s", a.afirmacion[:80])
                continue

            if _normalizar(a.cita_literal) not in _normalizar(chunk.get("texto", "")):
                a.veredicto = "no_verificable"
                logger.warning(
                    "Cita no hallada en el chunk %s: '%s'", a.chunk_id, a.cita_literal[:80]
                )

        return respuesta

    @staticmethod
    def _resumir(afirmaciones: List[Dict[str, Any]]) -> str:
        if not afirmaciones:
            return "El modelo no extrajo ninguna afirmación verificable."
        conteo = {"correcto": 0, "incorrecto": 0, "no_verificable": 0}
        for a in afirmaciones:
            conteo[a["veredicto"]] = conteo.get(a["veredicto"], 0) + 1
        return (
            f"{conteo['correcto']} respaldada(s) por el corpus, "
            f"{conteo['incorrecto']} contradicha(s), "
            f"{conteo['no_verificable']} sin respaldo verificable."
        )
