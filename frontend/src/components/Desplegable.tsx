import { useEffect, useId, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'

/**
 * Desplegable propio, en reemplazo de `<select>`.
 *
 * La lista de un `<select>` nativo la dibuja el sistema operativo: no toma el
 * papel, la tinta ni la mono del atlas, y en macOS aparece con el azul del
 * sistema y esquinas redondeadas en medio de una interfaz que no redondea nada.
 * Es el único control cuyo menú no se puede alcanzar con CSS, así que se
 * reimplementa el mínimo del patrón `combobox` de ARIA: rol, teclado completo y
 * el foco siempre en el disparador (la opción marcada viaja por
 * `aria-activedescendant`, que es lo que evita andar moviendo el foco a mano).
 */

export interface OpcionDesplegable<T> {
  valor: T
  etiqueta: string
}

interface Props<T> {
  valor: T
  opciones: OpcionDesplegable<T>[]
  onCambiar: (valor: T) => void
  /** Nombre accesible: el disparador solo muestra la opción elegida. */
  etiqueta: string
  deshabilitado?: boolean
  className?: string
}

export function Desplegable<T extends string | number>({
  valor,
  opciones,
  onCambiar,
  etiqueta,
  deshabilitado = false,
  className,
}: Props<T>) {
  const [abierto, setAbierto] = useState(false)
  /** Opción resaltada mientras se navega, que no es todavía la elegida. */
  const [marcada, setMarcada] = useState(0)

  const contenedor = useRef<HTMLDivElement>(null)
  const disparador = useRef<HTMLButtonElement>(null)
  const lista = useRef<HTMLUListElement>(null)
  const id = useId()

  const elegida = Math.max(
    0,
    opciones.findIndex((o) => o.valor === valor),
  )

  const abrir = () => {
    setMarcada(elegida)
    setAbierto(true)
  }

  const elegir = (indice: number) => {
    const opcion = opciones[indice]
    if (opcion) onCambiar(opcion.valor)
    setAbierto(false)
    disparador.current?.focus()
  }

  // Cierre al tocar afuera. Va en `pointerdown` y no en `click`: si no, apretar
  // sobre otro control lo dejaba abierto hasta soltar y se veían los dos menús.
  useEffect(() => {
    if (!abierto) return
    const alTocar = (e: PointerEvent) => {
      if (!contenedor.current?.contains(e.target as Node)) setAbierto(false)
    }
    document.addEventListener('pointerdown', alTocar)
    return () => document.removeEventListener('pointerdown', alTocar)
  }, [abierto])

  // Con listas largas la opción marcada puede caer fuera del recuadro.
  useEffect(() => {
    if (!abierto) return
    lista.current
      ?.querySelector<HTMLElement>('[data-marcada="true"]')
      ?.scrollIntoView({ block: 'nearest' })
  }, [abierto, marcada])

  // Todo el teclado cuelga del disparador porque el foco nunca se va de ahí.
  const alTeclado = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (!abierto) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        abrir()
      }
      return
    }

    switch (e.key) {
      case 'Escape':
        e.preventDefault()
        setAbierto(false)
        break
      // Sin `preventDefault`: se cierra el menú y el tabulado sigue su curso.
      case 'Tab':
        setAbierto(false)
        break
      case 'Enter':
      case ' ':
        e.preventDefault()
        elegir(marcada)
        break
      case 'ArrowDown':
        e.preventDefault()
        setMarcada((i) => Math.min(opciones.length - 1, i + 1))
        break
      case 'ArrowUp':
        e.preventDefault()
        setMarcada((i) => Math.max(0, i - 1))
        break
      case 'Home':
        e.preventDefault()
        setMarcada(0)
        break
      case 'End':
        e.preventDefault()
        setMarcada(opciones.length - 1)
        break
    }
  }

  return (
    <div ref={contenedor} className={className ? `desplegable ${className}` : 'desplegable'}>
      <button
        ref={disparador}
        type="button"
        className="desplegable__disparador"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={abierto}
        aria-controls={`${id}-lista`}
        aria-label={etiqueta}
        aria-activedescendant={abierto ? `${id}-op-${marcada}` : undefined}
        disabled={deshabilitado}
        onClick={() => (abierto ? setAbierto(false) : abrir())}
        onKeyDown={alTeclado}
      >
        <span className="desplegable__valor">{opciones[elegida]?.etiqueta ?? ''}</span>
        <span className="desplegable__punta" aria-hidden="true" />
      </button>

      {abierto && (
        <ul
          ref={lista}
          id={`${id}-lista`}
          className="desplegable__lista"
          role="listbox"
          aria-label={etiqueta}
        >
          {opciones.map((o, i) => (
            <li
              key={String(o.valor)}
              id={`${id}-op-${i}`}
              className="desplegable__opcion"
              role="option"
              aria-selected={i === elegida}
              data-marcada={i === marcada}
              // `pointerdown` otra vez: el `click` llega después del `blur` del
              // disparador, y para entonces el menú ya se cerró sin elegir nada.
              onPointerDown={(e) => {
                e.preventDefault()
                elegir(i)
              }}
              onPointerEnter={() => setMarcada(i)}
            >
              <span className="desplegable__tilde" aria-hidden="true">
                {i === elegida ? '✓' : ''}
              </span>
              {o.etiqueta}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
