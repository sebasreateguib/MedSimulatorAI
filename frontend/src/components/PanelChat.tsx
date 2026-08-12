import { useEffect, useRef } from 'react'
import { Mensaje } from './Mensaje'
import type { Mensaje as MensajeType } from '../types'

interface Props {
  mensajes: MensajeType[]
  nombrePaciente?: string
}

export function PanelChat({ mensajes, nombrePaciente }: Props) {
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
    if (pegadoAlFondo.current) {
      finRef.current?.scrollIntoView({ block: 'end' })
    }
  }, [mensajes])

  return (
    <div className="chat" ref={contenedorRef} onScroll={alScrollear}>
      <div className="chat__lista">
        {mensajes.map((m) => (
          <Mensaje key={m.id} mensaje={m} nombrePaciente={nombrePaciente} />
        ))}
        <div ref={finRef} />
      </div>
    </div>
  )
}
