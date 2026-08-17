"""
Ingesta del material de estudio que sube cada usuario (PDF, imagen o texto).

Se apoya en las mismas piezas que la ingesta de guías clínicas —DoclingParser
para el parseo, ChunkerClinico para la partición— pero el resultado va a
`chunks_documento` y no al corpus común: es material privado del estudiante.

Todo lo que hay acá es sincrónico y pesado (OCR, modelos de embeddings). El
router lo ejecuta en un hilo aparte para no bloquear el event loop.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from docling.datamodel.base_models import InputFormat

from medsimulator.rag.embeddings import EmbeddingService
from medsimulator.rag.ingesta.chunking import ChunkerClinico
from medsimulator.rag.ingesta.docling_parser import DoclingParser

logger = logging.getLogger(__name__)

# Extensión → tipo lógico. El tipo decide cómo se extrae el texto y cómo lo
# previsualiza el frontend, así que se guarda en la fila del documento.
EXTENSIONES: Dict[str, str] = {
    ".pdf": "pdf",
    ".png": "imagen",
    ".jpg": "imagen",
    ".jpeg": "imagen",
    ".webp": "imagen",
    ".tif": "imagen",
    ".tiff": "imagen",
    ".bmp": "imagen",
    ".txt": "texto",
    ".md": "texto",
    ".markdown": "texto",
    # Ofimática: docling los parsea con pipelines propios (sin OCR ni layout),
    # así que son baratos. Las diapositivas de clase entran por acá.
    ".docx": "documento",
    ".pptx": "documento",
    ".xlsx": "documento",
    ".html": "documento",
    ".htm": "documento",
    ".epub": "documento",
}

MIMES: Dict[str, str] = {
    "pdf": "application/pdf",
    "imagen": "image/*",
    "texto": "text/plain",
    "documento": "application/octet-stream",
}

# Mime real por extensión, para el `<img>` del visor y para mandarle la imagen
# al modelo de visión: `image/*` no sirve en ninguno de los dos casos.
MIMES_IMAGEN: Dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".bmp": "image/bmp",
}

# Formatos que la API de Anthropic acepta como imagen. Un TIFF o un BMP hay que
# convertirlos antes de mandarlos.
MIMES_VISION = {"image/png", "image/jpeg", "image/webp", "image/gif"}

# 25 MB. Un PDF de guía clínica entra cómodo y el OCR de algo más grande
# tardaría lo suficiente como para que la subida deje de parecer interactiva.
TAMANO_MAXIMO_BYTES = 25 * 1024 * 1024


def tipo_de_archivo(nombre: str) -> Optional[str]:
    """Tipo lógico ('pdf'|'imagen'|'texto'|'documento') o None si no se soporta."""
    _, extension = os.path.splitext(nombre.lower())
    return EXTENSIONES.get(extension)


def mime_de_archivo(nombre: str, tipo: str) -> str:
    """Mime concreto, con el de la imagen resuelto por extensión."""
    _, extension = os.path.splitext(nombre.lower())
    if tipo == "imagen":
        return MIMES_IMAGEN.get(extension, "image/png")
    if tipo == "texto":
        return "text/markdown" if extension in (".md", ".markdown") else "text/plain"
    return MIMES.get(tipo, "application/octet-stream")


# Formatos de docling que se habilitan en el converter, en el orden de EXTENSIONES.
FORMATOS_DOCLING = [
    InputFormat.PDF,
    InputFormat.IMAGE,
    InputFormat.DOCX,
    InputFormat.PPTX,
    InputFormat.XLSX,
    InputFormat.HTML,
    InputFormat.EPUB,
]


class MaterialVacioError(RuntimeError):
    """El archivo se parseó bien pero no dejó texto indexable."""


class ProcesadorMaterial:
    """
    Convierte un archivo subido en chunks con embedding listos para guardar.

    El parser y el modelo de embeddings se cargan una sola vez y se comparten
    entre subidas: instanciar DoclingParser por documento volvería a levantar
    los modelos de layout y OCR en cada archivo.
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        chunker: Optional[ChunkerClinico] = None,
    ):
        self.embedding_service = embedding_service or EmbeddingService()
        # Chunks más chicos que en las guías: el material del estudiante suele
        # ser apuntes y diapositivas, donde un chunk de 1000 caracteres mezcla
        # temas que después el buscador no puede separar.
        self.chunker = chunker or ChunkerClinico(tamano_chunk=700, superposicion=120)
        self._parser: Optional[DoclingParser] = None

    @property
    def parser(self) -> DoclingParser:
        """Carga perezosa: subir un .txt no debería levantar los modelos de OCR."""
        if self._parser is None:
            self._parser = DoclingParser(formatos=FORMATOS_DOCLING)
        return self._parser

    def precalentar(self) -> None:
        """
        Deja los modelos cargados y compilados antes del primer usuario.

        La primera imagen que pasa por acá tarda ~2 minutos (descarga del modelo
        de layout, del de tablas y del OCR, más el warmup de torch.compile) y
        después baja a ~2 segundos. Sin precalentar, ese costo se lo come quien
        suba el primer archivo, y con el semáforo de ingesta encima bloquea a
        todos los demás.
        """
        logger.info("Precalentando modelos de ingesta…")
        self.embedding_service.generar_embedding("precalentamiento")

        # Una imagen mínima recorre el pipeline completo —layout, tablas, OCR—
        # sin necesidad de un archivo de prueba en el repo.
        import tempfile

        from PIL import Image

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            ruta = tmp.name
        try:
            Image.new("RGB", (64, 64), "white").save(ruta)
            self.parser.parsear_documento(ruta)
        except Exception as e:
            # Que falle el precalentamiento no puede tumbar la app: la ingesta
            # real volverá a intentarlo y ahí sí reportará el error.
            logger.warning(f"El precalentamiento no terminó bien: {e}")
        finally:
            os.unlink(ruta)

        logger.info("Modelos de ingesta listos.")

    def procesar(self, ruta: str, nombre: str, tipo: str) -> Dict[str, Any]:
        """
        Extrae, parte y vectoriza un archivo.

        Devuelve `{"chunks": [...], "paginas": int}`, donde cada chunk trae
        texto, sección, página y su embedding.
        """
        logger.info(f"Procesando material '{nombre}' (tipo={tipo})")
        return self._chunkear_y_vectorizar(self._extraer(ruta, nombre, tipo), nombre)

    def procesar_texto_crudo(
        self, texto: str, nombre: str, seccion: str = "General"
    ) -> Dict[str, Any]:
        """
        Indexa texto que no salió de un archivo, como la descripción que produce
        el modelo de visión para una imagen sin texto legible.
        """
        documento = {
            "fuente": nombre,
            "paginas": [
                {"numero": None, "contenido": seccion, "tipo": "texto", "label": "section_header"},
                {"numero": None, "contenido": texto, "tipo": "texto", "label": "text"},
            ],
        }
        return self._chunkear_y_vectorizar(documento, nombre)

    def _chunkear_y_vectorizar(self, documento: Dict[str, Any], nombre: str) -> Dict[str, Any]:
        chunks = [c for c in self.chunker.chunkear(documento) if c["texto"].strip()]

        if not chunks:
            raise MaterialVacioError(
                "No se pudo extraer texto del archivo. Si es un escaneo, probá con "
                "una imagen más nítida o con el PDF original."
            )

        embeddings = self.embedding_service.generar_embeddings_batch(
            [c["texto"] for c in chunks]
        )
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        paginas = {p["numero"] for p in documento["paginas"] if p.get("numero")}
        logger.info(f"Material '{nombre}': {len(chunks)} chunks, {len(paginas)} páginas")

        return {"chunks": chunks, "paginas": len(paginas) or None}

    def _extraer(self, ruta: str, nombre: str, tipo: str) -> Dict[str, Any]:
        """Normaliza cualquier formato a la forma `{fuente, paginas[]}` de docling."""
        if tipo == "texto":
            return self._extraer_texto_plano(ruta, nombre)

        documento = self.parser.parsear_documento(ruta)
        # El parser nombra la fuente con el archivo en disco (un uuid): para las
        # citas hace falta el nombre con el que el usuario lo subió.
        documento["fuente"] = nombre
        return documento

    def _extraer_texto_plano(self, ruta: str, nombre: str) -> Dict[str, Any]:
        """
        Un .txt o .md no tiene páginas ni layout: cada párrafo entra como item y
        los encabezados markdown se marcan como sección para que el chunker los
        propague a las citas.
        """
        with open(ruta, "r", encoding="utf-8", errors="replace") as f:
            contenido = f.read()

        paginas: List[Dict[str, Any]] = []
        for parrafo in contenido.split("\n\n"):
            texto = parrafo.strip()
            if not texto:
                continue
            es_encabezado = texto.startswith("#") and len(texto) < 200
            paginas.append({
                "numero": None,
                "contenido": texto.lstrip("# ").strip() if es_encabezado else texto,
                "tipo": "texto",
                "label": "section_header" if es_encabezado else "text",
            })

        return {"fuente": nombre, "paginas": paginas}
