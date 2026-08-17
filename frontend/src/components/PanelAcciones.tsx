import type { Caso } from '../types'

/**
 * Atajos que rellenan el composer. Corresponden a las herramientas clínicas
 * declaradas en medsimulator/agents/tools.py: el router las clasifica a partir
 * del texto, así que desde el frontend basta con inyectar la frase.
 */
const ACCIONES = [
  {
    grupo: 'Anamnesis',
    items: [
      { etiqueta: 'Motivo de consulta', texto: '¿Qué lo trae por aquí hoy? Cuénteme qué siente.' },
      { etiqueta: 'Antecedentes', texto: '¿Tiene alguna enfermedad conocida o toma medicación habitual?' },
      { etiqueta: 'Hábitos', texto: '¿Toma alcohol, fuma o consume otras sustancias? ¿Con qué frecuencia?' },
      { etiqueta: 'Alergias', texto: '¿Es alérgico a algún medicamento?' },
    ],
  },
  {
    grupo: 'Estudios',
    items: [
      { etiqueta: 'Laboratorio', texto: 'Solicito laboratorio: hemograma, electrolitos y troponinas. Justificación: ' },
      { etiqueta: 'ECG', texto: 'Solicito un electrocardiograma de 12 derivaciones. Justificación: ' },
      { etiqueta: 'Imagen', texto: 'Solicito una radiografía de tórax. Justificación: ' },
    ],
  },
  {
    grupo: 'Conducta',
    items: [
      { etiqueta: 'Interconsulta', texto: 'Solicito interconsulta con cardiología para interpretar el ECG.' },
      { etiqueta: 'Receta', texto: 'Indico el siguiente tratamiento: ' },
      { etiqueta: 'Diagnóstico', texto: 'Mi diagnóstico principal es: ' },
    ],
  },
]

interface Props {
  caso: Caso
  sesionId: string | null
  onAccion: (texto: string) => void
  onFinalizar: () => void
  onVerEvaluacion: () => void
  finalizando: boolean
  finalizada: boolean
  /** Una sesión cerrada que se retoma llega sin scorecard cargado. */
  evaluacionLista: boolean
  deshabilitado: boolean
}

export function PanelAcciones({
  caso,
  sesionId,
  onAccion,
  onFinalizar,
  onVerEvaluacion,
  finalizando,
  finalizada,
  evaluacionLista,
  deshabilitado,
}: Props) {
  return (
    <aside className="panel">
      <section className="panel__bloque">
        <h2 className="panel__titulo">Caso</h2>
        <p className="panel__caso">{caso.titulo}</p>
        <dl className="panel__datos">
          <div>
            <dt>Paciente</dt>
            <dd>{caso.paciente.nombre}</dd>
          </div>
          <div>
            <dt>Edad</dt>
            <dd>{caso.paciente.edad} años</dd>
          </div>
          <div>
            <dt>Género</dt>
            <dd>{caso.paciente.genero}</dd>
          </div>
          {sesionId && (
            <div>
              <dt>Sesión</dt>
              <dd className="mono">{sesionId}</dd>
            </div>
          )}
        </dl>
      </section>

      <section className="panel__bloque">
        <h2 className="panel__titulo">Acciones clínicas</h2>
        {ACCIONES.map((grupo) => (
          <div key={grupo.grupo} className="panel__grupo">
            <h3>{grupo.grupo}</h3>
            <div className="panel__chips">
              {grupo.items.map((accion) => (
                <button
                  key={accion.etiqueta}
                  type="button"
                  className="chip"
                  onClick={() => onAccion(accion.texto)}
                  disabled={deshabilitado}
                >
                  {accion.etiqueta}
                </button>
              ))}
            </div>
          </div>
        ))}
        <p className="panel__nota">
          Cada estudio pedido sin justificación pesa en el puntaje de costo-efectividad.
        </p>
      </section>

      {/* Una sola ranura al pie del panel para los tres estados de la sesión:
          abierta, evaluando y cerrada. Antes, con el caso cerrado, aparecía
          un botón flotante fijo a la ventana que caía justo encima de este. */}
      {finalizada ? (
        <button
          type="button"
          className="btn btn--primario btn--pie"
          onClick={onVerEvaluacion}
          disabled={!evaluacionLista}
        >
          {evaluacionLista ? 'Ver evaluación' : 'Sin evaluación guardada'}
        </button>
      ) : (
        <button
          type="button"
          className="btn btn--finalizar btn--pie"
          onClick={onFinalizar}
          disabled={finalizando || !sesionId}
        >
          {finalizando ? 'Evaluando…' : 'Finalizar y evaluar'}
        </button>
      )}
    </aside>
  )
}
