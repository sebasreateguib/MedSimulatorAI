import { useEffect, useState } from 'react'
import { verificarSalud } from '../lib/api'

type Estado = 'verificando' | 'ok' | 'caido'

export function EstadoBackend() {
  const [estado, setEstado] = useState<Estado>('verificando')

  useEffect(() => {
    let vigente = true
    const comprobar = async () => {
      const ok = await verificarSalud()
      if (vigente) setEstado(ok ? 'ok' : 'caido')
    }
    comprobar()
    const id = setInterval(comprobar, 15000)
    return () => {
      vigente = false
      clearInterval(id)
    }
  }, [])

  const texto = { verificando: 'Conectando…', ok: 'API conectada', caido: 'API sin conexión' }[estado]

  return (
    <span className={`estado estado--${estado}`} title="Estado de /health en el backend">
      <span className="estado__punto" />
      {texto}
    </span>
  )
}
