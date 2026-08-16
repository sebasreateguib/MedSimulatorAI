import { useRef, useState } from 'react'
import type { DocumentoMaterial } from '../../types'
import type { SubidaEnCurso } from '../../hooks/useEstudio'

/** Extensiones que acepta el backend (medsimulator/rag/ingesta/materiales.py). */
const ACEPTADOS =
  '.pdf,.png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp,.txt,.md,.markdown,' +
  '.docx,.pptx,.xlsx,.html,.htm,.epub'

const ROTULO_TIPO: Record<DocumentoMaterial['tipo'], string> = {
  pdf: 'PDF',
  imagen: 'IMG',
  texto: 'TXT',
  documento: 'DOC',
}

function formatearPeso(bytes: number | null): string {
  if (!bytes) return '—'
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/** Línea de estado bajo el nombre: qué se puede hacer con este documento. */
function detalleDocumento(doc: DocumentoMaterial): string {
  if (doc.estado === 'procesando') return 'Procesando…'
  if (doc.estado === 'error') return doc.detalle_error ?? 'No se pudo procesar'
  const partes = [`${doc.n_chunks} fragmentos`]
  if (doc.paginas) partes.push(`${doc.paginas} pág.`)
  partes.push(formatearPeso(doc.tamano_bytes))
  return partes.join(' · ')
}

interface Props {
  documentos: DocumentoMaterial[]
  subidas: SubidaEnCurso[]
  seleccion: number[]
  cargando: boolean
  onSubir: (archivos: File[]) => void
  onEliminar: (id: number) => void
  onReintentar: (id: number) => void
  onAlternar: (id: number) => void
  onLimpiarSeleccion: () => void
  onVer: (doc: DocumentoMaterial) => void
}

export function Biblioteca({
  documentos,
  subidas,
  seleccion,
  cargando,
  onSubir,
  onEliminar,
  onReintentar,
  onAlternar,
  onLimpiarSeleccion,
  onVer,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [arrastrando, setArrastrando] = useState(false)

  const elegirArchivos = (lista: FileList | null) => {
    if (!lista || lista.length === 0) return
    onSubir(Array.from(lista))
    // Sin esto, volver a elegir el mismo archivo no dispara `change`.
    if (inputRef.current) inputRef.current.value = ''
  }

  return (
    <aside className="biblioteca">
      <div className="biblioteca__cab">
        <h2 className="panel__titulo">Tu material</h2>
        {seleccion.length > 0 && (
          <button type="button" className="biblioteca__limpiar mono" onClick={onLimpiarSeleccion}>
            {seleccion.length} en foco ×
          </button>
        )}
      </div>

      <div
        className={`dropzona${arrastrando ? ' dropzona--activa' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setArrastrando(true)
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={(e) => {
          e.preventDefault()
          setArrastrando(false)
          elegirArchivos(e.dataTransfer.files)
        }}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACEPTADOS}
          onChange={(e) => elegirArchivos(e.target.files)}
          hidden
        />
        <button type="button" className="dropzona__boton" onClick={() => inputRef.current?.click()}>
          Subir material
        </button>
        <p className="dropzona__ayuda mono">PDF · imágenes · txt/md — o arrastralos acá</p>
      </div>

      {subidas.map((s) => (
        <div key={s.nombre} className="subida">
          <p className="subida__nombre">{s.nombre}</p>
          <div className="subida__barra">
            <span style={{ width: `${Math.round(s.progreso * 100)}%` }} />
          </div>
        </div>
      ))}

      {cargando && <p className="rotulo biblioteca__vacio">Cargando…</p>}

      {!cargando && documentos.length === 0 && (
        <p className="biblioteca__vacio">
          Todavía no subiste nada. Cargá los apuntes, una guía o la foto de una diapositiva y
          preguntale al tutor sobre eso.
        </p>
      )}

      <ul className="biblioteca__lista">
        {documentos.map((doc) => {
          const enFoco = seleccion.includes(doc.id)
          return (
            <li
              key={doc.id}
              className={`documento documento--${doc.estado}${enFoco ? ' documento--foco' : ''}`}
            >
              <button
                type="button"
                className="documento__cuerpo"
                onClick={() => onAlternar(doc.id)}
                disabled={doc.estado !== 'listo'}
                aria-pressed={enFoco}
                title={
                  doc.estado === 'listo'
                    ? 'Limitar las respuestas a este documento'
                    : 'Disponible cuando termine de procesarse'
                }
              >
                <span className="documento__tipo mono">{ROTULO_TIPO[doc.tipo]}</span>
                <span className="documento__texto">
                  <span className="documento__nombre">{doc.nombre}</span>
                  <span className="documento__meta mono">{detalleDocumento(doc)}</span>
                </span>
              </button>

              <div className="documento__acciones">
                {doc.estado === 'error' && (
                  <button
                    type="button"
                    className="documento__accion"
                    onClick={() => onReintentar(doc.id)}
                    aria-label={`Reintentar ${doc.nombre}`}
                    title="Volver a procesar"
                  >
                    ↻
                  </button>
                )}
                <button
                  type="button"
                  className="documento__accion"
                  onClick={() => onVer(doc)}
                  aria-label={`Ver ${doc.nombre}`}
                  title="Ver el archivo"
                >
                  ↗
                </button>
                <button
                  type="button"
                  className="documento__accion documento__accion--borrar"
                  onClick={() => onEliminar(doc.id)}
                  aria-label={`Eliminar ${doc.nombre}`}
                  title="Eliminar de la biblioteca"
                >
                  ×
                </button>
              </div>
            </li>
          )
        })}
      </ul>

      {documentos.length > 0 && (
        <p className="panel__nota">
          {seleccion.length === 0
            ? 'Sin selección, el tutor busca en todo tu material.'
            : 'El tutor solo va a mirar los documentos en foco.'}
        </p>
      )}
    </aside>
  )
}
