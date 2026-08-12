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

/** Una fila del historial de sesiones pasadas del usuario (GET /simulacion/historial). */
export interface SesionHistorial {
  sesion_id: string
  caso_id: string | null
  caso_titulo: string
  paciente_nombre: string | null
  estado: 'activa' | 'finalizada' | string
  puntaje: number | null
  created_at: string
}
