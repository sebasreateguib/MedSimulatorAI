"""
Router de autenticación: registro, login y datos del usuario actual.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from medsimulator.app.dependencias import usuario_actual
from medsimulator.app.security import (
    LIMITE_BYTES_PASSWORD,
    crear_token_acceso,
    hashear_password,
    verificar_password,
)
from medsimulator.db import get_db
from medsimulator.db.models import Usuario

logger = logging.getLogger(__name__)

router = APIRouter()

# Hash descartable para gastar el mismo tiempo de bcrypt cuando el email no
# existe: sin esto, un login fallido respondería más rápido para emails no
# registrados y permitiría enumerarlos midiendo la latencia.
_HASH_SEÑUELO = hashear_password("contraseña-señuelo-para-igualar-tiempos")

CREDENCIALES_INVALIDAS = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Email o contraseña incorrectos.",
    headers={"WWW-Authenticate": "Bearer"},
)


# ── Modelos de entrada y salida ──────────────────────────────────────

class RegistroRequest(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    email: EmailStr
    # El máximo lo impone bcrypt, que ignora todo lo que exceda 72 bytes.
    password: str = Field(min_length=8, max_length=LIMITE_BYTES_PASSWORD)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=LIMITE_BYTES_PASSWORD)


class UsuarioPublico(BaseModel):
    """Vista del usuario apta para exponer: nunca incluye el hash."""
    id: int
    username: str
    email: EmailStr

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioPublico


# ── Endpoints ────────────────────────────────────────────────────────

@router.post("/registro", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def registrar(request: RegistroRequest, db: AsyncSession = Depends(get_db)):
    """
    Crea una cuenta nueva y devuelve un token para usarla de inmediato.
    """
    existente = await db.execute(
        select(Usuario).where(
            (Usuario.email == request.email) | (Usuario.username == request.username)
        )
    )
    if existente.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta con ese email o nombre de usuario.",
        )

    usuario = Usuario(
        username=request.username,
        email=request.email,
        password_hash=hashear_password(request.password),
    )
    db.add(usuario)
    await db.commit()
    await db.refresh(usuario)

    logger.info(f"Usuario registrado: id={usuario.id} username={usuario.username}")
    return TokenResponse(
        access_token=crear_token_acceso(usuario.id),
        usuario=UsuarioPublico.model_validate(usuario),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Valida las credenciales y devuelve un JWT.

    El mensaje de error es el mismo para email inexistente y contraseña
    incorrecta, para no revelar qué emails están registrados.
    """
    resultado = await db.execute(select(Usuario).where(Usuario.email == request.email))
    usuario = resultado.scalar_one_or_none()

    if usuario is None:
        verificar_password(request.password, _HASH_SEÑUELO)
        raise CREDENCIALES_INVALIDAS

    if not verificar_password(request.password, usuario.password_hash):
        logger.info(f"Login fallido para el usuario id={usuario.id}")
        raise CREDENCIALES_INVALIDAS

    logger.info(f"Login exitoso: id={usuario.id}")
    return TokenResponse(
        access_token=crear_token_acceso(usuario.id),
        usuario=UsuarioPublico.model_validate(usuario),
    )


@router.get("/yo", response_model=UsuarioPublico)
async def yo(usuario: Usuario = Depends(usuario_actual)):
    """
    Devuelve el usuario dueño del token. El frontend lo usa al arrancar para
    saber si el token guardado sigue siendo válido.
    """
    return UsuarioPublico.model_validate(usuario)
