/**
 * Almacenamiento del token de sesión.
 *
 * Se guarda en localStorage y viaja en el header Authorization. La alternativa
 * es una cookie httpOnly, inmune a XSS pero que exige manejo de CSRF y CORS con
 * credenciales; para este SPA el token en header es el camino simple y estándar.
 * Si algún día la app maneja datos clínicos reales, conviene migrar a cookie.
 */

const CLAVE_TOKEN = 'medsim.token'

/** Suscriptores que quieren enterarse cuando el token cambia (p. ej. un 401). */
type Escucha = (token: string | null) => void
const escuchas = new Set<Escucha>()

export function leerToken(): string | null {
  try {
    return localStorage.getItem(CLAVE_TOKEN)
  } catch {
    // Modo privado o storage bloqueado: la app sigue, solo no persiste la sesión.
    return null
  }
}

export function guardarToken(token: string): void {
  try {
    localStorage.setItem(CLAVE_TOKEN, token)
  } catch {
    /* sin persistencia disponible */
  }
  escuchas.forEach((fn) => fn(token))
}

export function borrarToken(): void {
  try {
    localStorage.removeItem(CLAVE_TOKEN)
  } catch {
    /* sin persistencia disponible */
  }
  escuchas.forEach((fn) => fn(null))
}

/** Devuelve la función para desuscribirse. */
export function alCambiarToken(fn: Escucha): () => void {
  escuchas.add(fn)
  return () => escuchas.delete(fn)
}
