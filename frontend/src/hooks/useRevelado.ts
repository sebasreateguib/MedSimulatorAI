import { useEffect } from 'react'

/**
 * Revela los elementos marcados con [data-revelar] al entrar en viewport.
 * Un solo observer para toda la página; se desuscribe de cada elemento
 * apenas se revela, así el scroll no paga nada después de la primera pasada.
 */
export function useRevelado() {
  useEffect(() => {
    const elementos = Array.from(document.querySelectorAll<HTMLElement>('[data-revelar]'))
    if (elementos.length === 0) return

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      elementos.forEach((el) => el.classList.add('revelado'))
      return
    }

    const observer = new IntersectionObserver(
      (entradas) => {
        for (const entrada of entradas) {
          if (!entrada.isIntersecting) continue
          entrada.target.classList.add('revelado')
          observer.unobserve(entrada.target)
        }
      },
      { rootMargin: '0px 0px -12% 0px', threshold: 0.15 },
    )

    elementos.forEach((el) => observer.observe(el))
    return () => observer.disconnect()
  }, [])
}
