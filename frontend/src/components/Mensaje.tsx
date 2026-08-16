import { Markdown } from './Markdown'
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
        {/* Los resultados de estudios vienen en Markdown: el título del estudio
            en negrita y los valores de laboratorio como lista. */}
        <Markdown texto={contenido} />
      </div>
    )
  }

  return (
    <article className={`mensaje mensaje--${rol}${error ? ' mensaje--error' : ''}`}>
      <span className="mensaje__etiqueta">{etiqueta}</span>
      <div className="mensaje__burbuja">
        {/* El estudiante ve su propio texto sin tocar; el resto pasa por el
            renderizador, que devuelve el texto intacto si no trae markdown
            —el habla del paciente casi nunca lo trae—. */}
        {rol === 'estudiante' ? contenido : <Markdown texto={contenido} />}
        {streaming && <span className="cursor" aria-label="escribiendo" />}
      </div>
    </article>
  )
}
