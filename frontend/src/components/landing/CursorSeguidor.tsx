import { useEffect, useRef } from 'react'

/** Cuánto se acerca el anillo al punto por frame. Más bajo = más arrastre. */
const SEGUIMIENTO = 0.16

/** Elementos que ponen el cursor en estado activo. */
const ACCIONABLE = 'a, button, [data-cursor="activo"]'

/**
 * Punto que sigue al mouse exacto + anillo que lo persigue con retraso.
 *
 * Todo se escribe directo al DOM desde un rAF: si esto viviera en estado de
 * React, cada píxel de movimiento dispararía un render del árbol entero.
 * El color sale de `mix-blend-mode: difference`, así el cursor se invierte
 * solo sobre el papel, sobre la lámina oscura y sobre los strands de color.
 */
export function CursorSeguidor() {
  const puntoRef = useRef<HTMLDivElement>(null)
  const anilloRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const punto = puntoRef.current
    const anillo = anilloRef.current
    if (!punto || !anillo) return

    // En táctil no hay puntero al que seguir.
    if (window.matchMedia('(pointer: coarse)').matches) return

    // Con movimiento reducido el anillo deja de arrastrarse y pega al punto.
    const suave = !window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let x = window.innerWidth / 2
    let y = window.innerHeight / 2
    let anilloX = x
    let anilloY = y
    let visible = false
    let raf = 0

    const ubicar = (el: HTMLElement, px: number, py: number) => {
      el.style.transform = `translate3d(${px}px, ${py}px, 0) translate(-50%, -50%)`
    }

    const mostrar = () => {
      if (visible) return
      visible = true
      punto.classList.add('cursor--visible')
      anillo.classList.add('cursor--visible')
    }

    const ocultar = () => {
      visible = false
      punto.classList.remove('cursor--visible')
      anillo.classList.remove('cursor--visible')
    }

    const alMover = (e: PointerEvent) => {
      x = e.clientX
      y = e.clientY
      // El punto no interpola: tiene que caer donde el sistema pone el puntero.
      ubicar(punto, x, y)
      mostrar()
    }

    const alEntrarEn = (e: PointerEvent) => {
      const activo = (e.target as Element | null)?.closest?.(ACCIONABLE) != null
      punto.classList.toggle('cursor--activo', activo)
      anillo.classList.toggle('cursor--activo', activo)
    }

    const alPresionar = () => {
      punto.classList.add('cursor--presionado')
      anillo.classList.add('cursor--presionado')
    }

    const alSoltar = () => {
      punto.classList.remove('cursor--presionado')
      anillo.classList.remove('cursor--presionado')
    }

    const bucle = () => {
      const k = suave ? SEGUIMIENTO : 1
      anilloX += (x - anilloX) * k
      anilloY += (y - anilloY) * k
      ubicar(anillo, anilloX, anilloY)
      raf = requestAnimationFrame(bucle)
    }

    window.addEventListener('pointermove', alMover, { passive: true })
    window.addEventListener('pointerover', alEntrarEn, { passive: true })
    window.addEventListener('pointerdown', alPresionar, { passive: true })
    window.addEventListener('pointerup', alSoltar, { passive: true })
    document.addEventListener('pointerleave', ocultar)
    window.addEventListener('blur', ocultar)
    raf = requestAnimationFrame(bucle)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', alMover)
      window.removeEventListener('pointerover', alEntrarEn)
      window.removeEventListener('pointerdown', alPresionar)
      window.removeEventListener('pointerup', alSoltar)
      document.removeEventListener('pointerleave', ocultar)
      window.removeEventListener('blur', ocultar)
    }
  }, [])

  return (
    <>
      <div ref={anilloRef} className="cursor-anillo" aria-hidden="true">
        <span />
      </div>
      <div ref={puntoRef} className="cursor-punto" aria-hidden="true">
        <span />
      </div>
    </>
  )
}
