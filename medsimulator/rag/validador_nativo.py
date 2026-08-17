"""
Validación de afirmaciones clínicas con las citations nativas de Anthropic.

Acá la fundamentación la impone el decodificador: el modelo no puede citar un
texto que no esté en los documentos que se le pasaron, así que la cita literal
llega verificada de origen. Es la contracara de `ValidadorCasero`, que consigue
lo mismo con un paso de verificación programática sobre cualquier proveedor.

Requiere hablar con la API de Anthropic directamente: `citations` no existe en
el endpoint compatible con OpenAI que el proyecto usa para Groq y OpenRouter.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# El modelo abre la respuesta con esta marca. Las citations no se llevan con las
# salidas estructuradas —la API rechaza el pedido si se piden juntas—, así que
# el veredicto viaja en el texto y se lee con una expresión regular.
PATRON_VEREDICTO = re.compile(
    r"VEREDICTO:\s*(correcto|incorrecto|no_verificable)", re.IGNORECASE
)


class ValidadorNativo:
    """
    Validador que utiliza la API de documentos/citas nativa de Anthropic
    para fundamentar las afirmaciones generadas.
    """

    def __init__(self, client, modelo: str, max_tokens: int = 1024):
        """
        El cliente llega inyectado desde `get_client_for_agent("validador")`:
        construirlo acá adentro con `AsyncAnthropic()` era lo que hacía que este
        validador ignorara `config/agents.yaml` —modelo incluido, que quedó
        clavado en uno ya retirado— y buscara la key por su cuenta.
        """
        logger.info("Inicializando ValidadorNativo (modelo=%s)", modelo)
        self._client = client
        self.modelo = modelo
        self.max_tokens = max_tokens

    def _documentos(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        documentos = []
        for chunk in chunks:
            titulo = str(chunk.get("fuente", "Desconocido"))
            if chunk.get("pagina"):
                titulo += f" — p. {chunk['pagina']}"
            documentos.append({
                "type": "document",
                "source": {
                    "type": "text",
                    "media_type": "text/plain",
                    "data": chunk.get("texto", ""),
                },
                "title": titulo,
                "citations": {"enabled": True},
            })
        return documentos

    async def validar(self, afirmacion: str, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Valida una afirmación contra un conjunto de chunks de contexto.

        Devuelve el contrato común de los validadores:
        `{valido, afirmaciones, citas, explicacion}`, con `valido` en None
        cuando no se pudo emitir juicio.
        """
        if not chunks:
            return self._sin_juicio("No hay fragmentos del corpus contra los que validar.")

        logger.info("Validando con citations contra %d fragmentos", len(chunks))
        documentos = self._documentos(chunks)

        instruccion = (
            f"Evaluá si los documentos respaldan esta afirmación de un estudiante de "
            f"medicina: '{afirmacion}'.\n\n"
            "Empezá tu respuesta con una línea exactamente así:\n"
            "VEREDICTO: correcto|incorrecto|no_verificable\n\n"
            "Usá 'correcto' si los documentos respaldan la afirmación, 'incorrecto' si la "
            "contradicen y 'no_verificable' si no hablan del tema. Después explicá en dos "
            "o tres oraciones, citando extensamente los pasajes relevantes."
        )

        try:
            response = await self._client.messages.create(
                model=self.modelo,
                max_tokens=self.max_tokens,
                messages=[{
                    "role": "user",
                    "content": [*documentos, {"type": "text", "text": instruccion}],
                }],
            )
        except Exception as e:
            logger.error("Error al validar con Anthropic: %s", e, exc_info=True)
            return self._sin_juicio(f"El validador no pudo consultar al modelo: {e}")

        citas: List[Dict[str, Any]] = []
        explicacion = ""

        for block in response.content:
            if block.type != "text":
                continue
            explicacion += block.text
            for cita in getattr(block, "citations", None) or []:
                citas.append(self._cita_publica(cita, chunks))

        veredicto = self._leer_veredicto(explicacion)
        # Una cita no es un respaldo: el modelo puede estar citando justamente el
        # pasaje que contradice al estudiante. El juicio sale del veredicto; las
        # citas son la evidencia que lo sostiene.
        explicacion = PATRON_VEREDICTO.sub("", explicacion, count=1).strip()

        return {
            "valido": {"correcto": True, "incorrecto": False}.get(veredicto),
            "afirmaciones": [{
                "afirmacion": afirmacion,
                "veredicto": veredicto,
                "cita_literal": citas[0]["texto_citado"] if citas else "",
                "fuente": citas[0]["documento"] if citas else None,
                "pagina": citas[0]["pagina"] if citas else None,
            }],
            "citas": citas,
            "explicacion": explicacion,
        }

    @staticmethod
    def _leer_veredicto(texto: str) -> str:
        encontrado = PATRON_VEREDICTO.search(texto)
        if encontrado:
            return encontrado.group(1).lower()
        logger.warning("El validador no emitió la línea VEREDICTO; se toma como no verificable.")
        return "no_verificable"

    @staticmethod
    def _cita_publica(cita: Any, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Traduce una cita de la API a la forma que consume el resto del sistema.

        La página no viene de la API: sobre documentos de texto plano las citas
        traen `char_location` (offsets de caracteres), no páginas. El número sale
        del chunk, que lo trae de sus metadatos, y se lo empareja por
        `document_index` —el orden en que se armaron los documentos.
        """
        indice = getattr(cita, "document_index", None)
        chunk = chunks[indice] if isinstance(indice, int) and indice < len(chunks) else None
        return {
            "texto_citado": getattr(cita, "cited_text", ""),
            "documento": (chunk or {}).get("fuente") or getattr(cita, "document_title", None),
            "pagina": (chunk or {}).get("pagina"),
            "chunk_id": (chunk or {}).get("id"),
        }

    @staticmethod
    def _sin_juicio(motivo: str) -> Dict[str, Any]:
        return {"valido": None, "afirmaciones": [], "citas": [], "explicacion": motivo}
