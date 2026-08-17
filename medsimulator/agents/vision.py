"""
Agente de visión: describe imágenes que el OCR no puede leer.

Una foto de un ECG, un diagrama de flujo o un esquema anatómico no tiene texto
que extraer, así que la ingesta normal las descarta por vacías. Este agente las
convierte en la única forma en que un RAG textual puede indexarlas: una
descripción escrita, densa en términos buscables.

Es el único punto del sistema que necesita un modelo multimodal, y por eso vive
aparte de `AgenteEstudio`: los modelos de chat y de flashcards son de texto.
"""

import base64
import io
import logging
import os
from typing import Optional

from medsimulator.llm.client import get_client_for_agent
from medsimulator.rag.ingesta.materiales import MIMES_IMAGEN, MIMES_VISION

logger = logging.getLogger(__name__)

# Anthropic rechaza imágenes de más de 5 MB ya codificadas en base64, que crece
# ~33% sobre el original. Por encima de esto hay que reescalar antes de mandar.
MAX_BYTES_IMAGEN = 3 * 1024 * 1024

PROMPT = (
    "Describí esta imagen de material de estudio de medicina para que un buscador "
    "de texto pueda encontrarla.\n\n"
    "Incluí, si están presentes:\n"
    "- Qué tipo de imagen es (electrocardiograma, radiografía, esquema anatómico, "
    "diagrama de flujo, tabla, gráfico, diapositiva).\n"
    "- Todo el texto visible, transcrito literalmente: rótulos, ejes, valores, títulos.\n"
    "- Los hallazgos o el contenido clínico que muestra, con la terminología que usaría "
    "un docente al explicarla.\n"
    "- La estructura del contenido si es un diagrama o un flujo (qué lleva a qué).\n\n"
    "Escribí en español, en prosa corrida, sin encabezados ni viñetas. No inventes "
    "hallazgos que no se ven: si algo está borroso o no se distingue, decilo."
)


class AgenteVision:
    """
    Convierte una imagen en texto indexable.

    Habla los dos dialectos multimodales que usa el proyecto —el de Anthropic
    (bloques `image` con base64) y el compatible con OpenAI que exponen Groq y
    OpenRouter (`image_url` con data URI)— para que cambiar el proveedor en
    agents.yaml no obligue a tocar este archivo.
    """

    def __init__(self):
        logger.info("Inicializando AgenteVision")
        self.proveedor = None
        self.client, self.config = get_client_for_agent("vision")
        self.proveedor = self.config.get("provider", "openrouter")
        self.model = self.config.get("model", "google/gemini-2.5-flash-lite")
        self.max_tokens = self.config.get("max_tokens", 1200)

    async def describir_imagen(self, ruta: str, nombre: str) -> str:
        """
        Devuelve la descripción de la imagen, o lanza si no se pudo generar.

        El llamador la indexa como si fuera el texto del documento.
        """
        datos, mime = self._preparar(ruta, nombre)
        b64 = base64.b64encode(datos).decode()
        logger.info(f"Describiendo '{nombre}' con {self.model} ({len(datos)} bytes, {mime})")

        if self.proveedor == "anthropic":
            texto = await self._describir_anthropic(b64, mime)
        else:
            texto = await self._describir_openai(b64, mime)

        if not texto:
            raise ValueError("El modelo de visión no devolvió una descripción.")
        return texto

    async def _describir_anthropic(self, b64: str, mime: str) -> str:
        respuesta = await self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mime, "data": b64},
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }],
        )
        return "".join(
            bloque.text for bloque in respuesta.content if getattr(bloque, "type", "") == "text"
        ).strip()

    async def _describir_openai(self, b64: str, mime: str) -> str:
        respuesta = await self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    {"type": "text", "text": PROMPT},
                ],
            }],
        )
        return (respuesta.choices[0].message.content or "").strip()

    def _preparar(self, ruta: str, nombre: str) -> tuple[bytes, str]:
        """
        Entrega la imagen en un formato que la API acepta y de un tamaño que
        pasa el límite: convierte TIFF/BMP a PNG y reescala lo que sea enorme.
        """
        _, extension = os.path.splitext(nombre.lower())
        mime = MIMES_IMAGEN.get(extension, "image/png")
        peso = os.path.getsize(ruta)

        if mime in MIMES_VISION and peso <= MAX_BYTES_IMAGEN:
            with open(ruta, "rb") as f:
                return f.read(), mime

        from PIL import Image

        with Image.open(ruta) as img:
            img = img.convert("RGB")
            # 2000 px de lado mayor: por encima de eso el modelo reescala igual y
            # solo se paga el ancho de banda.
            img.thumbnail((2000, 2000))
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)

        return buffer.getvalue(), "image/png"


_agente: Optional[AgenteVision] = None


def obtener_agente_vision() -> AgenteVision:
    """Singleton perezoso: solo se construye si alguna imagen lo necesita."""
    global _agente
    if _agente is None:
        _agente = AgenteVision()
    return _agente
