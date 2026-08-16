export type Rol = 'estudiante' | 'paciente' | 'especialista' | 'tutor' | 'sistema'

export interface Mensaje {
  id: string
  rol: Rol
  contenido: string
  /** true mientras el SSE sigue emitiendo tokens para este mensaje. */
  streaming?: boolean
  /** Marca los mensajes que fallaron para poder reintentar/estilar distinto. */
  error?: boolean
  timestamp: number
}

export interface Caso {
  id: string
  titulo: string
  motivo_consulta: string
  paciente: {
    nombre: string
    edad: number
    genero: string
  }
  dificultad: 'basico' | 'intermedio' | 'avanzado'
}

export interface IniciarSesionResponse {
  sesion_id: string
  mensaje: string
}

export interface FinalizarSesionResponse {
  sesion_id: string
  mensaje: string
}

/** Coincide con EvaluacionClinica en medsimulator/llm/schemas.py. */
export interface EvaluacionClinica {
  puntaje_total: number
  razonamiento_diagnostico: string
  costo_efectividad: string
  pruebas_innecesarias: string[]
  errores_criticos: string[]
  retroalimentacion: string
}

/**
 * El backend todavía devuelve un scorecard mock con otra forma
 * (score_general / feedback). Aceptamos ambas y normalizamos en la capa de API.
 */
export interface EvaluacionMockResponse {
  sesion_id: string
  score_general: number
  feedback: string
  diagnostico_correcto_identificado: boolean
}

export type EvaluacionResponse = Partial<EvaluacionClinica> & Partial<EvaluacionMockResponse>

export type EstadoSesion = 'inactiva' | 'iniciando' | 'activa' | 'finalizando' | 'finalizada'

/** Usuario autenticado tal como lo devuelve el backend (sin el hash). */
export interface UsuarioPublico {
  id: number
  username: string
  email: string
}

/** Respuesta de POST /auth/login y /auth/registro. */
export interface TokenResponse {
  access_token: string
  token_type: string
  usuario: UsuarioPublico
}

// ── Biblioteca y estudio ───────────────────────────────────────────

/** 'documento' son los de ofimática (docx, pptx, xlsx, html, epub). */
export type TipoDocumento = 'pdf' | 'imagen' | 'texto' | 'documento'

/**
 * 'procesando' mientras corre la ingesta en el backend (parseo + embeddings).
 * Hasta que no pase a 'listo' el documento no es consultable.
 */
export type EstadoDocumento = 'procesando' | 'listo' | 'error'

/** Un archivo subido por el usuario (GET /biblioteca/documentos). */
export interface DocumentoMaterial {
  id: number
  nombre: string
  tipo: TipoDocumento
  mime: string | null
  tamano_bytes: number | null
  estado: EstadoDocumento
  detalle_error: string | null
  paginas: number | null
  n_chunks: number
  created_at: string | null
}

/** Fragmento del material que sostiene una afirmación de la respuesta. */
export interface CitaMaterial {
  /** Número con el que el modelo la referencia en el texto: [1], [2]… */
  n: number
  documento_id: number
  fuente: string
  pagina: number | null
  seccion: string | null
  extracto: string
}

/** Resultado crudo de POST /biblioteca/buscar, sin pasar por el modelo. */
export interface FragmentoMaterial {
  documento_id: number
  fuente: string
  pagina: number | null
  seccion: string | null
  texto: string
}

export interface MensajeEstudio {
  id: string
  rol: 'estudiante' | 'tutor'
  contenido: string
  citas?: CitaMaterial[]
  streaming?: boolean
  error?: boolean
  timestamp: number
}

export interface Flashcard {
  id: number
  anverso: string
  reverso: string
  fuente: string | null
  pagina: number | null
  aciertos: number
  fallos: number
  ultima_revision: string | null
}

/** En el listado `flashcards` viene vacío y solo cuenta `total`. */
export interface Mazo {
  id: number
  titulo: string
  tema: string | null
  documento_ids: number[]
  created_at: string | null
  total: number
  flashcards: Flashcard[]
}

/** Una fila del historial de sesiones pasadas del usuario (GET /simulacion/historial). */
/** Un mensaje ya cerrado que vuelve de la base, sin estado de streaming. */
export interface MensajeSesion {
  rol: Rol
  contenido: string
}

/** Lo que devuelve GET /simulacion/sesion/{id} para retomar una consulta. */
export interface SesionReanudada {
  sesion_id: string
  estado: 'activa' | 'finalizada' | string
  caso: Caso
  mensajes: MensajeSesion[]
}

export interface SesionHistorial {
  sesion_id: string
  caso_id: string | null
  caso_titulo: string
  paciente_nombre: string | null
  estado: 'activa' | 'finalizada' | string
  puntaje: number | null
  created_at: string
}
