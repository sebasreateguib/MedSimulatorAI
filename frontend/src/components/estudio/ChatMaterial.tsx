import { useEffect, useRef, useState } from 'react'
import { MensajeMaterial } from './MensajeMaterial'
import type { CitaMaterial, MensajeEstudio } from '../../types'

/** Arranques que muestran de qué sirve el tutor cuando la conversación está vacía. */
const SUGERENCIAS = [
  'Resumime los puntos clave de este material.',
  '¿Qué criterios diagnósticos menciona?',
  'Tomame una pregunta de examen sobre esto.',
  'Explicame el mecanismo como si fuera la primera vez que lo veo.',
]

interface Props {
  mensajes: MensajeEstudio[]
  enviando: boolean
  hayMaterial: boolean
  onEnviar: (texto: string) => void
  onDetener: () => void
  onAbrirCita: (cita: CitaMaterial) => void
}

export function ChatMaterial({
  mensajes,
  enviando,
  hayMaterial,
  onEnviar,
  onDetener,
  onAbrirCita,
}: Props) {
  const [texto, setTexto] = useState('')
  const areaRef = useRef<HTMLTextAreaElement>(null)
  const finRef = useRef<HTMLDivElement>(null)
  const contenedorRef = useRef<HTMLDivElement>(null)
  const pegadoAlFondo = useRef(true)

  // Solo autoscrolleamos si el usuario no se fue a leer hacia arriba.
  const alScrollear = () => {
    const el = contenedorRef.current
    if (!el) return
    pegadoAlFondo.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  useEffect(() => {
    if (pegadoAlFondo.current) finRef.current?.scrollIntoView({ block: 'end' })
  }, [mensajes])

  // Altura automática hasta un tope, para que no crezca sin control.
  useEffect(() => {
    const el = areaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [texto])

  const enviar = (valor: string) => {
    const contenido = valor.trim()
    if (!contenido || enviando) return
    onEnviar(contenido)
    setTexto('')
  }

  return (
    <div className="conversacion conversacion--estudio">
      <div className="chat" ref={contenedorRef} onScroll={alScrollear}>
        <div className="chat__lista">
          {mensajes.length === 0 && (
            <div className="estudio__arranque">
              <p className="rotulo">Tutor sobre tu material</p>
              <p>
                {hayMaterial
                  ? 'Preguntá lo que quieras sobre lo que subiste. Cada respuesta cita el fragmento del que sale.'
                  : 'Subí un PDF, una imagen o tus apuntes en el panel de la izquierda para empezar.'}
              </p>
              {hayMaterial && (
                <div className="panel__chips">
                  {SUGERENCIAS.map((s) => (
                    <button key={s} type="button" className="chip" onClick={() => enviar(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {mensajes.map((m) => (
            <MensajeMaterial key={m.id} mensaje={m} onAbrirCita={onAbrirCita} />
          ))}
          <div ref={finRef} />
        </div>
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault()
          enviar(texto)
        }}
      >
        <textarea
          ref={areaRef}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              enviar(texto)
            }
          }}
          placeholder="Preguntá sobre tu material… (Enter para enviar, Shift+Enter para salto de línea)"
          rows={1}
          disabled={!hayMaterial}
          aria-label="Pregunta sobre el material"
        />
        {enviando ? (
          <button type="button" className="btn btn--detener" onClick={onDetener}>
            Detener
          </button>
        ) : (
          <button type="submit" className="btn btn--primario" disabled={!texto.trim() || !hayMaterial}>
            Preguntar
          </button>
        )}
      </form>
    </div>
  )
}
