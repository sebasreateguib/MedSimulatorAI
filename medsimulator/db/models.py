"""
Módulo de modelos SQLAlchemy y pgvector para el sistema MedSimulator.
"""

import logging
import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import declarative_base, relationship, mapped_column, Mapped
from pgvector.sqlalchemy import Vector

logger = logging.getLogger(__name__)

Base = declarative_base()

class Usuario(Base):
    """Modelo de Usuario del simulador."""
    __tablename__ = "usuarios"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    # Hash bcrypt de la contraseña. Nunca se guarda ni se devuelve la contraseña en claro.
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    sesiones = relationship("Sesion", back_populates="usuario")
    
    def __repr__(self) -> str:
        return f"<Usuario(id={self.id}, username='{self.username}')>"


class Sesion(Base):
    """Modelo de Sesión de simulación clínica."""
    __tablename__ = "sesiones"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    estado: Mapped[str] = mapped_column(String, default="activa")
    caso_data: Mapped[dict] = mapped_column(JSON, nullable=True) # Información del caso clínico
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    
    usuario = relationship("Usuario", back_populates="sesiones")
    transcripciones = relationship("Transcripcion", back_populates="sesion")
    evaluaciones = relationship("Evaluacion", back_populates="sesion")

    def __repr__(self) -> str:
        return f"<Sesion(id={self.id}, usuario_id={self.usuario_id}, estado='{self.estado}')>"


class Transcripcion(Base):
    """Modelo para guardar el registro de interacciones (chatbot/voz)."""
    __tablename__ = "transcripciones"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sesion_id: Mapped[int] = mapped_column(Integer, ForeignKey("sesiones.id"), nullable=False)
    rol: Mapped[str] = mapped_column(String, nullable=False) # 'usuario' o 'asistente'
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    
    sesion = relationship("Sesion", back_populates="transcripciones")

    def __repr__(self) -> str:
        return f"<Transcripcion(id={self.id}, sesion_id={self.sesion_id}, rol='{self.rol}')>"


class Chunk(Base):
    """
    Modelo para almacenar los chunks de conocimiento (GPC, PubMed, openFDA) 
    junto con sus embeddings generados.
    """
    __tablename__ = "chunks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    documento_origen: Mapped[str] = mapped_column(String, nullable=False)
    seccion: Mapped[str] = mapped_column(String, nullable=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    metadatos: Mapped[str] = mapped_column(Text, nullable=True) # JSON con metadatos adicionales
    # Dimensión del vector 1024, ajustado para el modelo de embedding específico (ej. bge-m3)
    embedding = mapped_column(Vector(1024))

    # El operator class tiene que coincidir con la distancia que usa la consulta:
    # `BuscadorHibrido` ordena por `cosine_distance`, así que con `vector_l2_ops`
    # el planner ignoraba el índice y caía en scan secuencial.
    __table_args__ = (
        Index(
            "hnsw_index_for_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
    )

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, documento_origen='{self.documento_origen}')>"
    
    
class Documento(Base):
    """
    Material de estudio subido por un usuario (PDF, imagen o texto).

    El archivo original queda en disco (`ruta`) para poder previsualizarlo; en
    la base solo viven los metadatos y el estado de la ingesta, que corre en
    segundo plano porque parsear un PDF con OCR tarda más que un request.
    """
    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)  # nombre original del archivo
    tipo: Mapped[str] = mapped_column(String, nullable=False)    # 'pdf' | 'imagen' | 'texto'
    mime: Mapped[str] = mapped_column(String, nullable=True)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    ruta: Mapped[str] = mapped_column(String, nullable=False)
    # 'procesando' mientras corre la ingesta, 'listo' cuando hay chunks, 'error' si falló.
    estado: Mapped[str] = mapped_column(String, default="procesando", nullable=False)
    detalle_error: Mapped[str] = mapped_column(Text, nullable=True)
    paginas: Mapped[int] = mapped_column(Integer, nullable=True)
    n_chunks: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    chunks = relationship("ChunkDocumento", back_populates="documento", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Documento(id={self.id}, nombre='{self.nombre}', estado='{self.estado}')>"


class ChunkDocumento(Base):
    """
    Fragmento indexado del material de un usuario.

    Va en una tabla aparte de `chunks` a propósito: aquel corpus es la
    literatura común y verificada (GPC, PubMed, openFDA), este es material
    privado de cada estudiante y toda consulta tiene que filtrar por dueño.
    """
    __tablename__ = "chunks_documento"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    documento_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Desnormalizado desde documentos: el filtro por dueño entra en cada búsqueda
    # vectorial y un JOIN ahí obligaría al planner a descartar el índice HNSW.
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    seccion: Mapped[str] = mapped_column(String, nullable=True)
    pagina: Mapped[int] = mapped_column(Integer, nullable=True)
    embedding = mapped_column(Vector(1024))

    documento = relationship("Documento", back_populates="chunks")

    __table_args__ = (
        Index(
            "hnsw_index_chunks_documento",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    def __repr__(self) -> str:
        return f"<ChunkDocumento(id={self.id}, documento_id={self.documento_id})>"


class Mazo(Base):
    """Conjunto de flashcards generadas a partir del material del usuario."""
    __tablename__ = "mazos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String, nullable=False)
    tema: Mapped[str] = mapped_column(String, nullable=True)
    # Ids de los documentos que alimentaron la generación, para poder mostrarlos.
    documento_ids: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    flashcards = relationship(
        "Flashcard", back_populates="mazo", cascade="all, delete-orphan", order_by="Flashcard.id"
    )

    def __repr__(self) -> str:
        return f"<Mazo(id={self.id}, titulo='{self.titulo}')>"


class Flashcard(Base):
    """
    Tarjeta de repaso. `aciertos`/`fallos` alcanzan para ordenar el repaso por
    lo que peor se sabe sin arrastrar un algoritmo de repetición espaciada.
    """
    __tablename__ = "flashcards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mazo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mazos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    anverso: Mapped[str] = mapped_column(Text, nullable=False)
    reverso: Mapped[str] = mapped_column(Text, nullable=False)
    fuente: Mapped[str] = mapped_column(String, nullable=True)
    pagina: Mapped[int] = mapped_column(Integer, nullable=True)
    aciertos: Mapped[int] = mapped_column(Integer, default=0)
    fallos: Mapped[int] = mapped_column(Integer, default=0)
    ultima_revision: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)

    mazo = relationship("Mazo", back_populates="flashcards")

    def __repr__(self) -> str:
        return f"<Flashcard(id={self.id}, mazo_id={self.mazo_id})>"


class Evaluacion(Base):
    """Modelo para almacenar los resultados de validación y evaluación de sesiones."""
    __tablename__ = "evaluaciones"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sesion_id: Mapped[int] = mapped_column(Integer, ForeignKey("sesiones.id"), nullable=False)
    puntaje: Mapped[int] = mapped_column(Integer, nullable=True)
    evaluacion_clinica: Mapped[dict] = mapped_column(JSON, nullable=True) # EvaluacionClinica en formato JSON
    feedback: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    
    sesion = relationship("Sesion", back_populates="evaluaciones")

    def __repr__(self) -> str:
        return f"<Evaluacion(id={self.id}, sesion_id={self.sesion_id}, puntaje={self.puntaje})>"
