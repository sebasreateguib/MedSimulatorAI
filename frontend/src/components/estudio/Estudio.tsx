import { useState } from 'react'
import { Biblioteca } from './Biblioteca'
import { ChatMaterial } from './ChatMaterial'
import { Flashcards } from './Flashcards'
import { VisorDocumento, type PedidoVisor } from './VisorDocumento'
import { useEstudio } from '../../hooks/useEstudio'
import type { CitaMaterial } from '../../types'

type Pestana = 'chat' | 'flashcards'

/**
 * Sección de estudio: la biblioteca del usuario a la izquierda y, sobre ella,
 * un tutor con el que conversar o un generador de flashcards.
 *
 * La selección de documentos es compartida entre las dos pestañas a propósito:
 * poner un PDF en foco para preguntar y después generar el mazo de ese mismo
 * PDF es el recorrido normal.
 */
export function Estudio() {
  const estudio = useEstudio()
  const [pestana, setPestana] = useState<Pestana>('chat')
  const [visor, setVisor] = useState<PedidoVisor | null>(null)

  const abrirCita = (cita: CitaMaterial) =>
    setVisor({ documentoId: cita.documento_id, pagina: cita.pagina, extracto: cita.extracto })

  return (
    <section className="estudio">
      <Biblioteca
        documentos={estudio.documentos}
        subidas={estudio.subidas}
        seleccion={estudio.seleccion}
        cargando={estudio.cargandoDocumentos}
        onSubir={estudio.subir}
        onEliminar={estudio.eliminar}
        onReintentar={estudio.reintentar}
        onAlternar={estudio.alternarSeleccion}
        onLimpiarSeleccion={estudio.limpiarSeleccion}
        onVer={(doc) => setVisor({ documentoId: doc.id })}
      />

      <div className="estudio__panel">
        <header className="estudio__pestanas">
          <div className="estudio__grupo">
            <button
              type="button"
              className={`pestana${pestana === 'chat' ? ' pestana--activa' : ''}`}
              onClick={() => setPestana('chat')}
            >
              Conversación
            </button>
            <button
              type="button"
              className={`pestana${pestana === 'flashcards' ? ' pestana--activa' : ''}`}
              onClick={() => setPestana('flashcards')}
            >
              Flashcards
            </button>
          </div>

          {pestana === 'chat' && estudio.mensajes.length > 0 && (
            <button
              type="button"
              className="btn btn--fantasma"
              onClick={estudio.limpiarConversacion}
            >
              Limpiar
            </button>
          )}
        </header>

        {estudio.error && (
          <div className="alerta" role="alert">
            <span>{estudio.error}</span>
            <button type="button" onClick={estudio.descartarError} aria-label="Descartar error">
              ×
            </button>
          </div>
        )}

        {pestana === 'chat' ? (
          <ChatMaterial
            mensajes={estudio.mensajes}
            enviando={estudio.enviando}
            hayMaterial={estudio.documentosListos.length > 0}
            onEnviar={estudio.preguntar}
            onDetener={estudio.detener}
            onAbrirCita={abrirCita}
          />
        ) : (
          <Flashcards
            seleccion={estudio.seleccion}
            hayMaterial={estudio.documentosListos.length > 0}
          />
        )}
      </div>

      {visor && (
        <VisorDocumento
          pedido={visor}
          documentos={estudio.documentos}
          onCerrar={() => setVisor(null)}
        />
      )}
    </section>
  )
}
