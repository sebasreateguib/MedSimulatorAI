import { useCallback, useEffect, useState } from 'react'
import { Composer } from './components/Composer'
import { EstadoBackend } from './components/EstadoBackend'
import { PanelAcciones } from './components/PanelAcciones'
import { PanelChat } from './components/PanelChat'
import { Scorecard } from './components/Scorecard'
import { SelectorCaso } from './components/SelectorCaso'
import { Landing } from './components/landing/Landing'
import { useSimulacion } from './hooks/useSimulacion'

/** Lee el hash de la URL y decide la vista inicial. */
function vistaDesdeHash(): 'landing' | 'simulador' {
  return window.location.hash === '#simulador' ? 'simulador' : 'landing'
}

export default function App() {
  const sim = useSimulacion()
  const [vista, setVistaRaw] = useState<'landing' | 'simulador'>(vistaDesdeHash)
  // Contador para reinyectar el mismo atajo dos veces seguidas en el composer.
  const [borrador, setBorrador] = useState<{ texto: string; n: number }>({ texto: '', n: 0 })
  const [scorecardVisible, setScorecardVisible] = useState(true)

  /** Cambia la vista y sincroniza el hash en la URL. */
  const setVista = useCallback((v: 'landing' | 'simulador') => {
    setVistaRaw(v)
    if (v === 'simulador') {
      window.history.pushState(null, '', '#simulador')
    } else {
      window.history.replaceState(null, '', window.location.pathname)
    }
  }, [])

  // Responder a navegación con botones atrás/adelante del navegador.
  useEffect(() => {
    const alNavegar = () => setVistaRaw(vistaDesdeHash())
    window.addEventListener('popstate', alNavegar)
    return () => window.removeEventListener('popstate', alNavegar)
  }, [])

  const enSesion = sim.estado === 'activa' || sim.estado === 'finalizando' || sim.estado === 'finalizada'
  const bloqueado = sim.estado !== 'activa'

  if (vista === 'landing') {
    return <Landing onEntrar={() => setVista('simulador')} />
  }

  return (
    <div className="app">
      <header className="topbar">
        <button
          type="button"
          className="topbar__marca topbar__marca--boton"
          onClick={() => {
            sim.reiniciar()
            setVista('landing')
          }}
          title="Volver al inicio"
        >
          <span className="logo" aria-hidden="true" />
          <div>
            <h1>MedSimulator AI</h1>
            <p>Paciente virtual · especialistas · tutor evaluador</p>
          </div>
        </button>
        <div className="topbar__acciones">
          <EstadoBackend />
          {enSesion && (
            <button type="button" className="btn btn--fantasma" onClick={sim.reiniciar}>
              Salir del caso
            </button>
          )}
        </div>
      </header>

      {sim.error && (
        <div className="alerta" role="alert">
          <span>{sim.error}</span>
          <button type="button" onClick={sim.descartarError} aria-label="Descartar error">
            ×
          </button>
        </div>
      )}

      <main className={enSesion ? 'main main--sesion' : 'main'}>
        {!enSesion || !sim.caso ? (
          <SelectorCaso onSeleccionar={sim.iniciar} cargando={sim.estado === 'iniciando'} />
        ) : (
          <>
            <div className="conversacion">
              <PanelChat mensajes={sim.mensajes} nombrePaciente={sim.caso.paciente.nombre} />
              <Composer
                onEnviar={sim.enviar}
                onDetener={sim.detener}
                enviando={sim.enviando}
                deshabilitado={bloqueado}
                borrador={borrador.n > 0 ? borrador.texto : undefined}
              />
            </div>

            <PanelAcciones
              caso={sim.caso}
              sesionId={sim.sesionId}
              onAccion={(texto) => setBorrador((prev) => ({ texto, n: prev.n + 1 }))}
              onFinalizar={() => {
                setScorecardVisible(true)
                sim.finalizar()
              }}
              finalizando={sim.estado === 'finalizando'}
              deshabilitado={bloqueado}
            />
          </>
        )}
      </main>

      {sim.evaluacion && scorecardVisible && (
        <Scorecard
          evaluacion={sim.evaluacion}
          onCerrar={() => setScorecardVisible(false)}
          onNuevaSesion={sim.reiniciar}
        />
      )}

      {sim.estado === 'finalizada' && !scorecardVisible && (
        <button type="button" className="fab" onClick={() => setScorecardVisible(true)}>
          Ver evaluación
        </button>
      )}
    </div>
  )
}
