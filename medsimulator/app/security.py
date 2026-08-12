"""
Primitivas de seguridad: hashing de contraseñas (bcrypt) y firma/verificación
de JSON Web Tokens (JWT).

Este módulo no conoce FastAPI ni la base de datos a propósito: solo transforma
credenciales en hashes y tokens. La política de acceso vive en app/dependencias.py.
"""
import datetime
import logging

import bcrypt
import jwt

from medsimulator.app.config import settings

logger = logging.getLogger(__name__)

# bcrypt trunca silenciosamente lo que exceda 72 bytes: una contraseña de 100
# caracteres validaría igual que sus primeros 72. Preferimos rechazarla.
LIMITE_BYTES_PASSWORD = 72


class PasswordDemasiadoLarga(ValueError):
    """La contraseña excede el límite que bcrypt puede considerar."""


def hashear_password(password: str) -> str:
    """Devuelve el hash bcrypt (con salt incorporado) de una contraseña."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > LIMITE_BYTES_PASSWORD:
        raise PasswordDemasiadoLarga(
            f"La contraseña supera los {LIMITE_BYTES_PASSWORD} bytes admitidos."
        )
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: str) -> bool:
    """Compara una contraseña en claro contra su hash almacenado."""
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > LIMITE_BYTES_PASSWORD:
        return False
    try:
        return bcrypt.checkpw(password_bytes, password_hash.encode("utf-8"))
    except ValueError:
        # Hash corrupto o con formato inesperado: no es una credencial válida.
        logger.warning("Se intentó verificar contra un hash con formato inválido.")
        return False


def crear_token_acceso(usuario_id: int) -> str:
    """Firma un JWT cuyo `sub` es el id del usuario."""
    ahora = datetime.datetime.now(datetime.timezone.utc)
    expira = ahora + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(usuario_id),  # el estándar exige que `sub` sea string
        "iat": ahora,
        "exp": expira,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def leer_token_acceso(token: str) -> int | None:
    """
    Valida firma y expiración de un token y devuelve el id de usuario.
    Devuelve None si el token es inválido, expiró o no trae un `sub` usable.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        logger.info("Token rechazado: expirado.")
        return None
    except jwt.PyJWTError as e:
        logger.info(f"Token rechazado: {e}")
        return None

    sub = payload.get("sub")
    if sub is None:
        return None
    try:
        return int(sub)
    except (TypeError, ValueError):
        logger.warning("Token con 'sub' no numérico.")
        return None
