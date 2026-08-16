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

      {esTutor && !streaming && citas.length > 0 && (
        <ul className="citas">
          {citas.map((cita) => (
            <li key={cita.n}>
              <button type="button" className="citas__item" onClick={() => onAbrirCita(cita)}>
                <span className="citas__n mono">{cita.n}</span>
                <span className="citas__fuente">
                  {cita.fuente}
                  {cita.pagina ? `, pág. ${cita.pagina}` : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </article>
  )
}
