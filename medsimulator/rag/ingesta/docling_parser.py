"""
Módulo para el parseo de documentos PDF utilizando Docling.
Extrae contenido estructurado y preserva la estructura de las tablas.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

logger = logging.getLogger(__name__)

# Etiquetas de docling que aportan contenido. Se dejan afuera a propósito
# `page_header`, `page_footer` y `picture`: repiten el título del documento en
# cada página o no tienen texto, y solo ensucian los chunks.
#
# `paragraph` es la que usan los cuadros de texto de PowerPoint y buena parte
# del cuerpo de los DOCX: sin ella, de una diapositiva solo entraba el título.
LABELS_CON_CONTENIDO = [
    "text",
    "paragraph",
    "title",
    "section_header",
    "list_item",
    "caption",
    "formula",
    "code",
]

class DoclingParser:
    """
    Parser de PDFs utilizando Docling (IBM) con reconocimiento de estructura de tablas.

    Acepta otros formatos vía `formatos` (por ejemplo `InputFormat.IMAGE` para
    fotos de apuntes): docling los procesa con el mismo pipeline del PDF, así
    que el OCR y la detección de tablas valen igual.
    """

    def __init__(self, formatos: Optional[List[InputFormat]] = None):
        formatos = formatos or [InputFormat.PDF]
        logger.info(f"Inicializando DoclingParser (formatos: {[f.name for f in formatos]})")
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_table_structure = True
        pipeline_options.do_ocr = True  # OCR fallback para páginas escaneadas

        opciones_por_formato = {
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
        }

        self.converter = DocumentConverter(
            allowed_formats=formatos,
            format_options={
                formato: opciones_por_formato[formato]
                for formato in formatos
                if formato in opciones_por_formato
            },
        )

    def parsear_documento(self, path: str) -> Dict[str, Any]:
        """
        Parsea un documento PDF y devuelve su contenido estructurado.
        Conserva el número de página para auditabilidad.
        """
        logger.info(f"Parseando documento: {path}")
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"El archivo {path} no existe.")
            
        result = self.converter.convert(path)
        doc = result.document
        
        paginas_info = []
        filename = os.path.basename(path)
        
        for item, level in doc.iterate_items():
            page_no = item.prov[0].page_no if item.prov else None
            
            tipo = "texto"
            contenido = ""
            
            if item.label == "table":
                tipo = "tabla"
                # Exportar la tabla a Markdown para preservar la estructura
                contenido = item.export_to_markdown()
            elif item.label in LABELS_CON_CONTENIDO:
                contenido = item.text
            else:
                continue
                
            if contenido.strip():
                paginas_info.append({
                    "numero": page_no,
                    "contenido": contenido,
                    "tipo": tipo,
                    "label": item.label
                })
        
        return {
            "fuente": filename,
            "paginas": paginas_info
        }
