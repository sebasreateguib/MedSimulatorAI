import { useEffect, useRef, useState } from 'react'

interface Props {
  onEnviar: (texto: string) => void
  onDetener: () => void
  enviando: boolean
  deshabilitado: boolean
  /** Texto inyectado desde el panel de acciones clínicas. */
  borrador?: string
}

export function Composer({ onEnviar, onDetener, enviando, deshabilitado, borrador }: Props) {
  const [texto, setTexto] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (borrador) {
      setTexto(borrador)
      ref.current?.focus()
    }
  }, [borrador])

  // Altura automática hasta un tope, para que no crezca sin control.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`
  }, [texto])

  const enviar = () => {
    if (!texto.trim() || enviando || deshabilitado) return
    onEnviar(texto)
    setTexto('')
  }

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault()
        enviar()
      }}
    >
      <textarea
        ref={ref}
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            enviar()
          }
        }}
        placeholder="Preguntale al paciente… (Enter para enviar, Shift+Enter para salto de línea)"
        rows={1}
        disabled={deshabilitado}
        aria-label="Mensaje para el paciente"
      />
      {enviando ? (
        <button type="button" className="btn btn--detener" onClick={onDetener}>
          Detener
        </button>
      ) : (
        <button type="submit" className="btn btn--primario" disabled={!texto.trim() || deshabilitado}>
          Enviar
        </button>
      )}
    </form>
  )
}
