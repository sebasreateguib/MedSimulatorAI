import type { Mensaje as MensajeType, Rol } from '../types'

const ETIQUETAS: Record<Rol, string> = {
  estudiante: 'Vos',
  paciente: 'Paciente',
  especialista: 'Especialista',
  tutor: 'Tutor',
  sistema: 'Contexto',
}

interface Props {
  mensaje: MensajeType
  nombrePaciente?: string
}

export function Mensaje({ mensaje, nombrePaciente }: Props) {
  const { rol, contenido, streaming, error } = mensaje
  const etiqueta = rol === 'paciente' && nombrePaciente ? nombrePaciente : ETIQUETAS[rol]

  if (rol === 'sistema') {
    return (
      <div className="mensaje mensaje--sistema">
        <span className="mensaje__etiqueta">{etiqueta}</span>
        <p>{contenido}</p>
      </div>
    )
  }

  return (
    <article className={`mensaje mensaje--${rol}${error ? ' mensaje--error' : ''}`}>
      <span className="mensaje__etiqueta">{etiqueta}</span>
      <div className="mensaje__burbuja">
        {contenido}
        {streaming && <span className="cursor" aria-label="escribiendo" />}
      </div>
    </article>
  )
}
