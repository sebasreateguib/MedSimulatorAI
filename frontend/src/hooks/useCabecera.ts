import { useEffect, useRef, useState } from 'react'

/**
 * Estado visual de la cabecera fija, en dos ejes independientes:
 *
 * - `enTope`: la página está sin scrollear. La cabecera puede ser transparente
 *   porque no hay nada debajo todavía.
 * - `sobrePlaca`: la cabecera todavía flota sobre la lámina oscura del hero,
 *   así que va invertida (texto hueso, fondo tinta).
 *
 * Dos centinelas con IntersectionObserver en vez de un listener de scroll: el
 * navegador avisa solo al cruzar cada borde, no en cada píxel de rueda.
 */
export function useCabecera(alturaNav = 76) {
  const topeRef = useRef<HTMLDivElement>(null)
  const centinelaRef = useRef<HTMLDivElement>(null)
  const [enTope, setEnTope] = useState(true)
  const [sobrePlaca, setSobrePlaca] = useState(true)

  useEffect(() => {
    const tope = topeRef.current
    if (!tope) return
    const observer = new IntersectionObserver(([entrada]) => setEnTope(entrada.isIntersecting), {
      threshold: 0,
    })
    observer.observe(tope)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const centinela = centinelaRef.current
    if (!centinela) return
    const observer = new IntersectionObserver(
      ([entrada]) => setSobrePlaca(entrada.boundingClientRect.top > alturaNav),
      { threshold: 0, rootMargin: `-${alturaNav}px 0px 0px 0px` },
    )
    observer.observe(centinela)
    return () => observer.disconnect()
  }, [alturaNav])

  return { topeRef, centinelaRef, enTope, sobrePlaca }
}
