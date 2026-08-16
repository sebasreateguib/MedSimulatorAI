import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../lib/api'
import type { CitaMaterial, DocumentoMaterial, MensajeEstudio } from '../types'

/** Cada cuánto se vuelve a preguntar por los documentos que están procesándose. */
const INTERVALO_SONDEO_MS = 2500

/** Turnos previos que viajan al backend. Más que esto empuja las citas fuera de la ventana. */
const TURNOS_ENVIADOS = 8

let contador = 0
const nuevoId = () => `e${++contador}`

export interface SubidaEnCurso {
  nombre: string
  progreso: number
}

/**
 * Estado de la sección de estudio: la biblioteca del usuario y la conversación
 * sobre ella. Las flashcards viven aparte porque no comparten estado con el
 * chat más allá de qué documentos están seleccionados.
 */
export function useEstudio() {
  const [documentos, setDocumentos] = useState<DocumentoMaterial[]>([])
  const [cargandoDocumentos, setCargandoDocumentos] = useState(true)
  const [subidas, setSubidas] = useState<SubidaEnCurso[]>([])
  const [seleccion, setSeleccion] = useState<number[]>([])
  const [mensajes, setMensajes] = useState<MensajeEstudio[]>([])
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)

  const refrescar = useCallback(async () => {
    try {
      const lista = await api.listarDocumentos()
      setDocumentos(lista)
      // Un documento que desaparece (borrado desde otra pestaña) no puede
      // quedar seleccionado: se enviaría un id muerto en cada consulta.
      const vivos = new Set(lista.map((d) => d.id))
      setSeleccion((prev) => prev.filter((id) => vivos.has(id)))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo cargar tu material.')
    } finally {
      setCargandoDocumentos(false)
    }
  }, [])

  useEffect(() => {
    refrescar()
  }, [refrescar])

  // Sondeo mientras haya ingestas corriendo: el backend procesa en segundo
  // plano y no tiene forma de avisar cuándo terminó.
  useEffect(() => {
    const hayPendientes = documentos.some((d) => d.estado === 'procesando')
    if (!hayPendientes) return

    const id = window.setInterval(refrescar, INTERVALO_SONDEO_MS)
    return () => window.clearInterval(id)
  }, [documentos, refrescar])

  const subir = useCallback(
    async (archivos: File[]) => {
      for (const archivo of archivos) {
        setSubidas((prev) => [...prev, { nombre: archivo.name, progreso: 0 }])
        try {
          const documento = await api.subirDocumento(archivo, {
            onProgreso: (fraccion) =>
              setSubidas((prev) =>
                prev.map((s) => (s.nombre === archivo.name ? { ...s, progreso: fraccion } : s)),
              ),
          })
          // Entra ya en la lista en estado 'procesando'; el sondeo lo actualiza.
          setDocumentos((prev) => [documento, ...prev])
          setSeleccion((prev) => [...prev, documento.id])
        } catch (err) {
          setError(err instanceof Error ? err.message : `No se pudo subir ${archivo.name}.`)
        } finally {
          setSubidas((prev) => prev.filter((s) => s.nombre !== archivo.name))
        }
      }
    },
    [],
  )

  const eliminar = useCallback(async (id: number) => {
    try {
      await api.eliminarDocumento(id)
      setDocumentos((prev) => prev.filter((d) => d.id !== id))
      setSeleccion((prev) => prev.filter((s) => s !== id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo eliminar el documento.')
    }
  }, [])

  const reintentar = useCallback(async (id: number) => {
    try {
      const documento = await api.reintentarIngesta(id)
      // Vuelve a 'procesando': el sondeo se reactiva solo y sigue el resultado.
      setDocumentos((prev) => prev.map((d) => (d.id === id ? documento : d)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo reintentar el procesamiento.')
    }
  }, [])

  const alternarSeleccion = useCallback((id: number) => {
    setSeleccion((prev) => (prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]))
  }, [])

  const limpiarSeleccion = useCallback(() => setSeleccion([]), [])

  const preguntar = useCallback(
    async (texto: string) => {
      const contenido = texto.trim()
      if (!contenido || enviando) return

      const respuestaId = nuevoId()
      setEnviando(true)
      setError(null)

      // El historial que ve el modelo es el de antes de este turno.
      const historial = mensajes
        .filter((m) => !m.error && m.contenido.trim())
        .slice(-TURNOS_ENVIADOS)
        .map((m) => ({
          role: m.rol === 'estudiante' ? ('user' as const) : ('assistant' as const),
          content: m.contenido,
        }))

      setMensajes((prev) => [
        ...prev,
        { id: nuevoId(), rol: 'estudiante', contenido, timestamp: Date.now() },
        { id: respuestaId, rol: 'tutor', contenido: '', streaming: true, timestamp: Date.now() },
      ])

      const controller = new AbortController()
      abortRef.current = controller

      const escribirEn = (id: string, fn: (m: MensajeEstudio) => MensajeEstudio) =>
        setMensajes((prev) => prev.map((m) => (m.id === id ? fn(m) : m)))

      try {
        await api.chatEstudio(contenido, historial, {
          documentoIds: seleccion,
          signal: controller.signal,
          onToken: (token) =>
            escribirEn(respuestaId, (m) => ({ ...m, contenido: m.contenido + token })),
          onCitas: (citas: CitaMaterial[]) => escribirEn(respuestaId, (m) => ({ ...m, citas })),
        })
        escribirEn(respuestaId, (m) => ({ ...m, streaming: false }))
      } catch (err) {
        const mensaje = err instanceof Error ? err.message : 'Error durante la consulta.'
        setError(mensaje)
        escribirEn(respuestaId, (m) => ({
          ...m,
          streaming: false,
          error: true,
          contenido: m.contenido || mensaje,
        }))
      } finally {
        abortRef.current = null
        setEnviando(false)
      }
    },
    [enviando, mensajes, seleccion],
  )

  const detener = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setMensajes((prev) => prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)))
    setEnviando(false)
  }, [])

  const limpiarConversacion = useCallback(() => {
    detener()
    setMensajes([])
  }, [detener])

  const listos = documentos.filter((d) => d.estado === 'listo')

  return {
    documentos,
    documentosListos: listos,
    cargandoDocumentos,
    subidas,
    seleccion,
    mensajes,
    enviando,
    error,
    subir,
    eliminar,
    reintentar,
    refrescar,
    alternarSeleccion,
    limpiarSeleccion,
    preguntar,
    detener,
    limpiarConversacion,
    descartarError: () => setError(null),
  }
}
