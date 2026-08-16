import { useEffect, useState } from 'react'
import * as api from '../../lib/api'
import type { DocumentoMaterial } from '../../types'

export interface PedidoVisor {
  documentoId: number
  /** Página a la que saltar cuando se abre desde una cita. */
  pagina?: number | null
  /** Fragmento citado, para resaltarlo arriba del archivo. */
  extracto?: string | null
}

interface Props {
  pedido: PedidoVisor
  documentos: DocumentoMaterial[]
  onCerrar: () => void
}

/**
 * Muestra el archivo original de la biblioteca.
 *
 * El endpoint pide JWT, así que no se puede apuntar un `<iframe src>` al backend:
 * se baja el archivo con el header puesto y se lo sirve desde un object URL, que
 * hay que revocar al cerrar para no dejar el blob colgado en memoria.
 */
export function VisorDocumento({ pedido, documentos, onCerrar }: Props) {
  const documento = documentos.find((d) => d.id === pedido.documentoId)
  const [url, setUrl] = useState<string | null>(null)
  const [texto, setTexto] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let vigente = true
    let creada: string | null = null

    api
      .urlDeArchivo(pedido.documentoId)
      .then(async (objectUrl) => {
        creada = objectUrl
        if (!vigente) return
        if (documento?.tipo === 'texto') {
          setTexto(await (await fetch(objectUrl)).text())
        }
        setUrl(objectUrl)
      })
      .catch((err) => {
        if (vigente) setError(err instanceof Error ? err.message : 'No se pudo abrir el archivo.')
      })

    return () => {
      vigente = false
      if (creada) URL.revokeObjectURL(creada)
    }
  }, [pedido.documentoId, documento?.tipo])

  // Cerrar con Escape, como el resto de las capas de la app.
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCerrar()
    }
    window.addEventListener('keydown', alTeclear)
    return () => window.removeEventListener('keydown', alTeclear)
  }, [onCerrar])

  return (
    <div className="overlay" role="dialog" aria-modal="true" onClick={onCerrar}>
      <div className="visor" onClick={(e) => e.stopPropagation()}>
        <header className="visor__cab">
          <div>
            <p className="rotulo">Material</p>
            <h2>{documento?.nombre ?? 'Documento'}</h2>
          </div>
          <button type="button" className="visor__cerrar" onClick={onCerrar} aria-label="Cerrar">
            ×
          </button>
        </header>

        {pedido.extracto && (
          <blockquote className="visor__extracto">
            {pedido.extracto}
            {pedido.pagina ? <span className="mono"> — pág. {pedido.pagina}</span> : null}
          </blockquote>
        )}

        <div className="visor__cuerpo">
          {error && <p className="vacio">{error}</p>}
          {!error && !url && <p className="rotulo">Abriendo el archivo…</p>}

          {url && documento?.tipo === 'pdf' && (
            // #page= lo interpreta el visor nativo del navegador: abre en la
            // página citada en lugar de dejar al usuario buscándola.
            <iframe
              className="visor__marco"
              src={pedido.pagina ? `${url}#page=${pedido.pagina}` : url}
              title={documento.nombre}
            />
          )}

          {url && documento?.tipo === 'imagen' && (
            <img className="visor__imagen" src={url} alt={documento.nombre} />
          )}

          {texto !== null && documento?.tipo === 'texto' && (
            <pre className="visor__texto">{texto}</pre>
          )}

          {url && documento?.tipo === 'documento' && (
            // Un .docx o un .pptx no los renderiza el navegador. Se ofrece el
            // archivo para abrirlo con la aplicación del sistema; el contenido
            // ya está indexado, así que el tutor igual puede citarlo.
            <div className="visor__sin-vista">
              <p>Este formato no se puede previsualizar en el navegador.</p>
              <a className="btn btn--secundario" href={url} download={documento.nombre}>
                Descargar {documento.nombre}
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
