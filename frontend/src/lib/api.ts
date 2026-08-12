import type {
  Caso,
  EvaluacionClinica,
  EvaluacionResponse,
  FinalizarSesionResponse,
  IniciarSesionResponse,
  SesionHistorial,
  TokenResponse,
  UsuarioPublico,
} from '../types'
import { borrarToken, leerToken } from './auth'
import { CASOS_LOCALES } from './casos'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export class ApiError extends Error {
  status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Header Authorization cuando hay sesión iniciada. */
function cabecerasAuth(): Record<string, string> {
  const token = leerToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * Un 401 significa que el token venció o dejó de ser válido: se descarta para
 * que la app vuelva a la pantalla de acceso en vez de reintentar en loop.
 */
function siNoAutorizado(status: number) {
  if (status === 401) borrarToken()
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...cabecerasAuth(),
        ...init?.headers,
      },
    })
  } catch {
    throw new ApiError('No se pudo contactar al backend. ¿Está corriendo uvicorn en :8000?')
  }

  if (!res.ok) {
    siNoAutorizado(res.status)
    throw new ApiError(await mensajeDeError(res), res.status)
  }
  return (await res.json()) as T
}

/** FastAPI devuelve {detail: ...}; los errores de validación traen una lista. */
async function mensajeDeError(res: Response): Promise<string> {
  try {
    const body = await res.json()
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((d) => d?.msg ?? JSON.stringify(d)).join(', ')
    }
  } catch {
    /* respuesta sin JSON: caemos al genérico */
  }
  return `Error ${res.status} al llamar a la API`
}

export async function verificarSalud(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`)
    return res.ok
  } catch {
    return false
  }
}

/**
 * El backend todavía no expone un catálogo de casos; mientras tanto usamos el
 * espejo local de config/casos/. Cuando exista GET /simulacion/casos, este
 * intento gana y el fallback deja de usarse sin tocar los componentes.
 */
export async function listarCasos(): Promise<Caso[]> {
  try {
    const casos = await request<Caso[]>('/simulacion/casos')
    if (Array.isArray(casos) && casos.length > 0) return casos
  } catch {
    /* endpoint aún no implementado */
  }
  return CASOS_LOCALES
}

export function iniciarSesion(casoId: string): Promise<IniciarSesionResponse> {
  return request<IniciarSesionResponse>('/simulacion/iniciar', {
    method: 'POST',
    body: JSON.stringify({ caso_id: casoId }),
  })
}

/** Sesiones pasadas del usuario autenticado, más reciente primero. */
export function obtenerHistorial(): Promise<SesionHistorial[]> {
  return request<SesionHistorial[]>('/simulacion/historial')
}


// ── Autenticación ──────────────────────────────────────────────────

export function registrar(
  username: string,
  email: string,
  password: string,
): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/registro', {
    method: 'POST',
    body: JSON.stringify({ username, email, password }),
  })
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

/** Valida el token guardado y devuelve su dueño. */
export function obtenerUsuarioActual(): Promise<UsuarioPublico> {
  return request<UsuarioPublico>('/auth/yo')
}

export function finalizarSesion(sesionId: string): Promise<FinalizarSesionResponse> {
  // El endpoint declara sesion_id como query param, no como body.
  return request<FinalizarSesionResponse>(
    `/simulacion/finalizar?sesion_id=${encodeURIComponent(sesionId)}`,
    { method: 'POST' },
  )
}

export async function obtenerEvaluacion(sesionId: string): Promise<EvaluacionClinica> {
  const raw = await request<EvaluacionResponse>(`/evaluacion/${encodeURIComponent(sesionId)}`)
  return normalizarEvaluacion(raw)
}

/** Acepta el scorecard mock actual y el EvaluacionClinica definitivo. */
function normalizarEvaluacion(raw: EvaluacionResponse): EvaluacionClinica {
  return {
    puntaje_total: raw.puntaje_total ?? raw.score_general ?? 0,
    razonamiento_diagnostico:
      raw.razonamiento_diagnostico ??
      (raw.diagnostico_correcto_identificado === undefined
        ? 'Sin datos'
        : raw.diagnostico_correcto_identificado
          ? 'Diagnóstico principal identificado correctamente.'
          : 'No se llegó al diagnóstico principal.'),
    costo_efectividad: raw.costo_efectividad ?? 'Sin datos',
    pruebas_innecesarias: raw.pruebas_innecesarias ?? [],
    errores_criticos: raw.errores_criticos ?? [],
    retroalimentacion: raw.retroalimentacion ?? raw.feedback ?? '',
  }
}

export interface OpcionesTurno {
  onToken: (token: string) => void
  signal?: AbortSignal
}

/**
 * Envía el turno del estudiante y consume el stream SSE token a token.
 *
 * No se usa EventSource: solo habla GET y este endpoint es POST con body.
 * fetch + ReadableStream permite además abortar con AbortController.
 */
export async function enviarTurno(
  sesionId: string,
  mensaje: string,
  { onToken, signal }: OpcionesTurno,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}/simulacion/turno`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...cabecerasAuth(),
      },
      body: JSON.stringify({ sesion_id: sesionId, mensaje_estudiante: mensaje }),
      signal,
    })
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') return
    throw new ApiError('Se perdió la conexión con el backend durante el turno.')
  }

  if (!res.ok) {
    siNoAutorizado(res.status)
    throw new ApiError(await mensajeDeError(res), res.status)
  }
  if (!res.body) throw new ApiError('El backend no devolvió un stream legible.')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Los eventos SSE se separan por una línea en blanco.
      let corte: number
      while ((corte = indiceFinDeEvento(buffer)) !== -1) {
        const bruto = buffer.slice(0, corte)
        buffer = buffer.slice(corte).replace(/^(\r?\n){2}/, '')

        const data = extraerData(bruto)
        if (data === null) continue
        if (data === '[DONE]') return
        onToken(data)
      }
    }
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') return
    throw err
  } finally {
    reader.cancel().catch(() => {})
  }
}

function indiceFinDeEvento(buffer: string): number {
  const lf = buffer.indexOf('\n\n')
  const crlf = buffer.indexOf('\r\n\r\n')
  if (lf === -1) return crlf
  if (crlf === -1) return lf
  return Math.min(lf, crlf)
}

/** Devuelve el payload de las líneas `data:` de un evento, o null si no hay. */
function extraerData(evento: string): string | null {
  const lineas = evento.split(/\r?\n/).filter((l) => l.startsWith('data:'))
  if (lineas.length === 0) return null
  // El espacio posterior a `data:` es separador del protocolo, no contenido.
  return lineas.map((l) => l.slice(5).replace(/^ /, '')).join('\n')
}
