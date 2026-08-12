import { useCallback, useEffect, useState } from 'react'
import * as api from '../lib/api'
import { alCambiarToken, borrarToken, guardarToken, leerToken } from '../lib/auth'
import type { UsuarioPublico } from '../types'

type EstadoAuth = 'verificando' | 'autenticado' | 'anonimo'

export function useAuth() {
  const [estado, setEstado] = useState<EstadoAuth>(() =>
    leerToken() ? 'verificando' : 'anonimo',
  )
  const [usuario, setUsuario] = useState<UsuarioPublico | null>(null)

  // Al arrancar, un token guardado todavía no prueba nada: puede haber expirado
  // o haber sido firmado con otro secreto. Se valida contra el backend.
  useEffect(() => {
    if (!leerToken()) return

    let vigente = true
    api
      .obtenerUsuarioActual()
      .then((u) => {
        if (!vigente) return
        setUsuario(u)
        setEstado('autenticado')
      })
      .catch(() => {
        if (!vigente) return
        borrarToken()
        setUsuario(null)
        setEstado('anonimo')
      })
    return () => {
      vigente = false
    }
  }, [])

  // Si la capa de API descarta el token por un 401, la UI debe reaccionar.
  useEffect(
    () =>
      alCambiarToken((token) => {
        if (token === null) {
          setUsuario(null)
          setEstado('anonimo')
        }
      }),
    [],
  )

  const entrar = useCallback(async (email: string, password: string) => {
    const { access_token, usuario: u } = await api.login(email, password)
    guardarToken(access_token)
    setUsuario(u)
    setEstado('autenticado')
  }, [])

  const registrarse = useCallback(
    async (username: string, email: string, password: string) => {
      const { access_token, usuario: u } = await api.registrar(username, email, password)
      guardarToken(access_token)
      setUsuario(u)
      setEstado('autenticado')
    },
    [],
  )

  const salir = useCallback(() => {
    borrarToken()
    setUsuario(null)
    setEstado('anonimo')
  }, [])

  return { estado, usuario, entrar, registrarse, salir }
}
