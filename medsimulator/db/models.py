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

    __table_args__ = (
        Index(
            "hnsw_index_for_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_l2_ops"}
        ),
    )

    def __repr__(self) -> str:
        return f"<Chunk(id={self.id}, documento_origen='{self.documento_origen}')>"
    
    
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
