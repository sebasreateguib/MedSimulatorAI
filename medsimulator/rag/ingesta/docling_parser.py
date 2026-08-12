"""
Módulo para el parseo de documentos PDF utilizando Docling.
Extrae contenido estructurado y preserva la estructura de las tablas.
"""

import logging
import os
from typing import Any, Dict

from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat

logger = logging.getLogger(__name__)

class DoclingParser:
    """
    Parser de PDFs utilizando Docling (IBM) con reconocimiento de estructura de tablas.
    """
    
    def __init__(self):
        logger.info("Inicializando DoclingParser")
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_table_structure = True
        pipeline_options.do_ocr = True  # OCR fallback para páginas escaneadas
        
        self.converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: pipeline_options
            }
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
            elif item.label in ["text", "title", "section_header", "list_item"]:
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
