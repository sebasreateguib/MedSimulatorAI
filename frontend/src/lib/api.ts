import type {
  Caso,
  CitaMaterial,
  DocumentoMaterial,
  EvaluacionClinica,
  EvaluacionResponse,
  FinalizarSesionResponse,
  FragmentoMaterial,
  Flashcard,
  IniciarSesionResponse,
  Mazo,
  Rol,
  SesionHistorial,
  SesionReanudada,
  TokenResponse,
  UsuarioPublico,
} from '../types'
import { borrarToken, leerToken } from './auth'

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
 * Catálogo de casos, tal como lo declaran los YAML de config/casos/.
 *
 * Antes esto caía a una copia local escrita a mano cuando el endpoint no
 * respondía. Esa copia se desincronizó de los YAML y ofrecía un caso con un id
 * que el backend no podía cargar: la lista se veía bien y el error recién
 * aparecía al intentar iniciarlo. Ahora, si el catálogo no se puede leer, se
 * dice acá y no se ofrece nada que no se pueda simular.
 */
export function listarCasos(): Promise<Caso[]> {
  return request<Caso[]>('/simulacion/casos')
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

/** El caso y la conversación de una sesión, para retomarla donde quedó. */
export function obtenerSesion(sesionId: string): Promise<SesionReanudada> {
  return request<SesionReanudada>(`/simulacion/sesion/${encodeURIComponent(sesionId)}`)
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
  // `sesion_id` va en el cuerpo: el endpoint lo declara con un modelo Pydantic
  // (FinalizarRequest), no como query param. Mandarlo en la URL devolvía 422 y
  // la sesión no se cerraba nunca: quedaba "activa" para siempre en el
  // historial.
  return request<FinalizarSesionResponse>('/simulacion/finalizar', {
    method: 'POST',
    body: JSON.stringify({ sesion_id: Number(sesionId) }),
  })
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
  /**
   * El backend anuncia con `[ROL:x]` de qué agente es lo que viene: el
   * resultado de un estudio es del sistema y la reacción posterior es del
   * paciente. Sin esto los dos terminaban concatenados en la misma burbuja.
   */
  onRol?: (rol: Rol) => void
  signal?: AbortSignal
}

const MARCA_ROL = /^\[ROL:(\w+)\]$/
const ROLES_VALIDOS: Rol[] = ['paciente', 'especialista', 'tutor', 'sistema']

/**
 * Envía el turno del estudiante y consume el stream SSE token a token.
 *
 * No se usa EventSource: solo habla GET y este endpoint es POST con body.
 * fetch + ReadableStream permite además abortar con AbortController.
 */
export async function enviarTurno(
  sesionId: string,
  mensaje: string,
  { onToken, onRol, signal }: OpcionesTurno,
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

  await consumirEventos(res, (data) => {
    if (data === '[DONE]') return 'fin'

    const marca = MARCA_ROL.exec(data)
    if (marca) {
      const rol = marca[1] as Rol
      // Un rol desconocido se ignora en vez de pintarse como texto: el backend
      // puede empezar a mandar uno nuevo antes de que el frontend lo conozca.
      if (ROLES_VALIDOS.includes(rol)) onRol?.(rol)
      return
    }

    onToken(data)
  })
}

/**
 * Lee un cuerpo SSE y entrega el payload de cada evento. Devolver 'fin' desde
 * `onEvento` corta la lectura.
 *
 * Vive acá y no dentro de `enviarTurno` porque el chat de estudio consume el
 * mismo protocolo con eventos de control propios ([CITAS], [ERROR]).
 */
async function consumirEventos(
  res: Response,
  onEvento: (data: string) => 'fin' | void,
): Promise<void> {
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
        if (onEvento(data) === 'fin') return
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

// ── Biblioteca de material ─────────────────────────────────────────

export function listarDocumentos(): Promise<DocumentoMaterial[]> {
  return request<DocumentoMaterial[]>('/biblioteca/documentos')
}

export function eliminarDocumento(id: number): Promise<void> {
  return requestSinCuerpo(`/biblioteca/documentos/${id}`, { method: 'DELETE' })
}

/** Conteo de material indexado del usuario, para los resúmenes. */
export function resumenBiblioteca(): Promise<{ documentos: number; fragmentos: number }> {
  return request<{ documentos: number; fragmentos: number }>('/biblioteca/resumen')
}

/** Vuelve a procesar un documento que quedó en error, sin volver a subirlo. */
export function reintentarIngesta(id: number): Promise<DocumentoMaterial> {
  return request<DocumentoMaterial>(`/biblioteca/documentos/${id}/reintentar`, { method: 'POST' })
}

export function buscarEnMaterial(
  consulta: string,
  documentoIds: number[] = [],
): Promise<FragmentoMaterial[]> {
  return request<FragmentoMaterial[]>('/biblioteca/buscar', {
    method: 'POST',
    body: JSON.stringify({ consulta, documento_ids: documentoIds }),
  })
}

/**
 * Sube un archivo informando el progreso.
 *
 * Usa XMLHttpRequest y no fetch: `upload.onprogress` es la única forma de saber
 * cuánto se subió, y en un PDF de 20 MB la barra es la diferencia entre esperar
 * y creer que se colgó. El body va como FormData, sin Content-Type propio: el
 * navegador tiene que poner el boundary del multipart.
 */
export function subirDocumento(
  archivo: File,
  opciones: { onProgreso?: (fraccion: number) => void; signal?: AbortSignal } = {},
): Promise<DocumentoMaterial> {
  const { onProgreso, signal } = opciones

  return new Promise((resolve, rechazar) => {
    const xhr = new XMLHttpRequest()
    const cuerpo = new FormData()
    cuerpo.append('archivo', archivo)

    xhr.open('POST', `${BASE_URL}/biblioteca/documentos`)
    for (const [clave, valor] of Object.entries(cabecerasAuth())) {
      xhr.setRequestHeader(clave, valor)
    }

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgreso?.(e.loaded / e.total)
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as DocumentoMaterial)
        } catch {
          rechazar(new ApiError('El backend devolvió una respuesta ilegible.', xhr.status))
        }
        return
      }
      siNoAutorizado(xhr.status)
      rechazar(new ApiError(mensajeDeErrorCrudo(xhr.responseText, xhr.status), xhr.status))
    }

    xhr.onerror = () => rechazar(new ApiError('No se pudo contactar al backend para subir el archivo.'))
    xhr.onabort = () => rechazar(new ApiError('Subida cancelada.'))

    signal?.addEventListener('abort', () => xhr.abort(), { once: true })
    xhr.send(cuerpo)
  })
}

/**
 * Descarga el archivo original como object URL para el visor.
 *
 * No se puede apuntar un `<img src>` o un `<iframe src>` directo al endpoint:
 * la ruta exige el header Authorization y esas etiquetas no lo mandan.
 * Quien llame tiene que hacer `URL.revokeObjectURL` al cerrar el visor.
 */
export async function urlDeArchivo(id: number): Promise<string> {
  const res = await fetch(`${BASE_URL}/biblioteca/documentos/${id}/archivo`, {
    headers: cabecerasAuth(),
  })
  if (!res.ok) {
    siNoAutorizado(res.status)
    throw new ApiError(await mensajeDeError(res), res.status)
  }
  return URL.createObjectURL(await res.blob())
}

// ── Chat sobre el material ─────────────────────────────────────────

export interface OpcionesChatEstudio {
  onToken: (token: string) => void
  onCitas?: (citas: CitaMaterial[]) => void
  documentoIds?: number[]
  signal?: AbortSignal
}

/** Un turno tal como lo espera el backend en el historial. */
export interface TurnoEstudio {
  role: 'user' | 'assistant'
  content: string
}

/**
 * Pregunta sobre el material del usuario y consume la respuesta en streaming.
 *
 * El backend no guarda la conversación: el historial que se manda acá es todo
 * el contexto que va a tener el modelo.
 */
export async function chatEstudio(
  mensaje: string,
  historial: TurnoEstudio[],
  { onToken, onCitas, documentoIds = [], signal }: OpcionesChatEstudio,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}/estudio/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...cabecerasAuth(),
      },
      body: JSON.stringify({ mensaje, historial, documento_ids: documentoIds }),
      signal,
    })
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') return
    throw new ApiError('Se perdió la conexión con el backend durante la respuesta.')
  }

  if (!res.ok) {
    siNoAutorizado(res.status)
    throw new ApiError(await mensajeDeError(res), res.status)
  }

  // Array y no un `let`: el control de flujo de TS no ve las asignaciones que
  // ocurren dentro del callback y daría por imposible el throw de abajo.
  const fallos: string[] = []

  await consumirEventos(res, (data) => {
    if (data === '[DONE]') return 'fin'
    if (data.startsWith('[CITAS]')) {
      try {
        const { citas } = JSON.parse(data.slice('[CITAS]'.length)) as { citas: CitaMaterial[] }
        onCitas?.(citas ?? [])
      } catch {
        /* si las citas vienen rotas, la respuesta igual sirve */
      }
      return
    }
    if (data.startsWith('[ERROR]')) {
      fallos.push(data.slice('[ERROR]'.length).trim())
      return
    }
    onToken(data)
  })

  if (fallos.length > 0) throw new ApiError(fallos[0])
}

// ── Flashcards ─────────────────────────────────────────────────────

export interface PedidoMazo {
  documento_ids?: number[]
  tema?: string | null
  cantidad?: number
}

export function generarMazo(pedido: PedidoMazo): Promise<Mazo> {
  return request<Mazo>('/estudio/mazos', {
    method: 'POST',
    body: JSON.stringify({
      documento_ids: pedido.documento_ids ?? [],
      tema: pedido.tema?.trim() || null,
      cantidad: pedido.cantidad ?? 10,
    }),
  })
}

export function listarMazos(): Promise<Mazo[]> {
  return request<Mazo[]>('/estudio/mazos')
}

export function obtenerMazo(id: number): Promise<Mazo> {
  return request<Mazo>(`/estudio/mazos/${id}`)
}

export function eliminarMazo(id: number): Promise<void> {
  return requestSinCuerpo(`/estudio/mazos/${id}`, { method: 'DELETE' })
}

export function registrarRepaso(
  flashcardId: number,
  resultado: 'bien' | 'mal',
): Promise<Flashcard> {
  return request<Flashcard>(`/estudio/flashcards/${flashcardId}/repaso`, {
    method: 'POST',
    body: JSON.stringify({ resultado }),
  })
}

/**
 * Igual que `request` pero para respuestas 204: `res.json()` sobre un cuerpo
 * vacío tira SyntaxError y el borrado parecería haber fallado.
 */
async function requestSinCuerpo(path: string, init?: RequestInit): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { ...cabecerasAuth(), ...init?.headers },
    })
  } catch {
    throw new ApiError('No se pudo contactar al backend.')
  }
  if (!res.ok) {
    siNoAutorizado(res.status)
    throw new ApiError(await mensajeDeError(res), res.status)
  }
}

/** Versión de `mensajeDeError` para XHR, que entrega el cuerpo ya como texto. */
function mensajeDeErrorCrudo(texto: string, status: number): string {
  try {
    const detail = JSON.parse(texto)?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? JSON.stringify(d)).join(', ')
  } catch {
    /* respuesta sin JSON */
  }
  return `Error ${status} al subir el archivo`
}

/** Devuelve el payload de las líneas `data:` de un evento, o null si no hay. */
function extraerData(evento: string): string | null {
  const lineas = evento.split(/\r?\n/).filter((l) => l.startsWith('data:'))
  if (lineas.length === 0) return null
  // El espacio posterior a `data:` es separador del protocolo, no contenido.
  return lineas.map((l) => l.slice(5).replace(/^ /, '')).join('\n')
}
