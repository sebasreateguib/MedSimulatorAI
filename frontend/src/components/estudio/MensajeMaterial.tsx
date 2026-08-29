import { Markdown } from '../Markdown'
import type { CitaMaterial, MensajeEstudio } from '../../types'

interface Props {
  mensaje: MensajeEstudio
  onAbrirCita: (cita: CitaMaterial) => void
}

export function MensajeMaterial({ mensaje, onAbrirCita }: Props) {
  const { rol, contenido, citas = [], streaming, error } = mensaje
  const esTutor = rol === 'tutor'

  return (
    <article
      className={`mensaje mensaje--${esTutor ? 'paciente' : 'estudiante'}${
        error ? ' mensaje--error' : ''
      }`}
    >
      <span className="mensaje__etiqueta">{esTutor ? 'Tutor' : 'Vos'}</span>
      <div className="mensaje__burbuja">
        {/* Lo que escribió el estudiante se muestra tal cual: formatearle el
            texto propio sería reescribirle lo que tipeó. */}
        {esTutor ? (
          <Markdown texto={contenido} citas={citas} onAbrirCita={onAbrirCita} />
        ) : (
          contenido
        )}
        {streaming && <span className="cursor" aria-label="escribiendo" />}
      </div>
    </article>
  )
}
