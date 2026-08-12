import { useEffect, useState } from 'react'

/**
 * true cuando el viewport no da para el diagrama horizontal.
 *
 * Se consulta con matchMedia y no midiendo el contenedor: el punto de corte
 * queda declarado una sola vez y no hay que observar tamaños en cada frame.
 */
export function useEsAngosto(anchoMaximo = 760) {
  const consulta = `(max-width: ${anchoMaximo}px)`
  const [angosto, setAngosto] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(consulta).matches,
  )

  useEffect(() => {
    const mq = window.matchMedia(consulta)
    const aplicar = () => setAngosto(mq.matches)
    aplicar()
    mq.addEventListener('change', aplicar)
    return () => mq.removeEventListener('change', aplicar)
  }, [consulta])

  return angosto
}
