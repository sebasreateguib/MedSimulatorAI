import { useCallback, useEffect, useState } from 'react'
import { Autenticacion } from './components/Autenticacion'
import { Composer } from './components/Composer'
import { EstadoBackend } from './components/EstadoBackend'
import { HistorialSesiones } from './components/HistorialSesiones'
import { MetricasCasos, MetricasUso } from './components/Metricas'
import { PanelAcciones } from './components/PanelAcciones'
import { PanelChat } from './components/PanelChat'
import { Scorecard } from './components/Scorecard'
import { SelectorCaso } from './components/SelectorCaso'
import { Landing } from './components/landing/Landing'
import { AppSidebar } from './components/shadcn-space/blocks/sidebar-01/app-sidebar'
import { SidebarInset, SidebarProvider } from './components/ui/sidebar'
import { useAuth } from './hooks/useAuth'
import { useSimulacion } from './hooks/useSimulacion'

type VistaSimulador = 'sesion' | 'historial' | 'metricas' | 'metricas-casos'

/** Lee el hash de la URL y decide la vista inicial. */
function vistaDesdeHash(): 'landing' | 'simulador' {
  return window.location.hash === '#simulador' ? 'simulador' : 'landing'
}

export default function App() {
  const sim = useSimulacion()
  const auth = useAuth()
  const [vista, setVistaRaw] = useState<'landing' | 'simulador'>(vistaDesdeHash)
  const [vistaSimulador, setVistaSimulador] = useState<VistaSimulador>('sesion')
  // Contador para reinyectar el mismo atajo dos veces seguidas en el composer.
  const [borrador, setBorrador] = useState<{ texto: string; n: number }>({ texto: '', n: 0 })
  const [scorecardVisible, setScorecardVisible] = useState(true)

  /** Cambia la vista y sincroniza el hash en la URL. */
  const setVista = useCallback((v: 'landing' | 'simulador') => {
    setVistaRaw(v)
    if (v === 'simulador') {
      window.history.pushState(null, '', '#simulador')
    } else {
      // Conserva el query string: sin esto, volver al inicio borraba flags como
      // `?demo` y la vuelta al simulador ya no los tenía.
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
    }
  }, [])

  // Responder a navegación con botones atrás/adelante del navegador.
  useEffect(() => {
    const alNavegar = () => setVistaRaw(vistaDesdeHash())
    window.addEventListener('popstate', alNavegar)
    return () => window.removeEventListener('popstate', alNavegar)
  }, [])

  const enSesion =
    sim.estado === 'activa' || sim.estado === 'finalizando' || sim.estado === 'finalizada'
  const bloqueado = sim.estado !== 'activa'
  /** Los tableros van a ancho completo; el resto conserva el ancho de lectura. */
  const enTablero = vistaSimulador === 'metricas' || vistaSimulador === 'metricas-casos'

  if (vista === 'landing') {
    return <Landing onEntrar={() => setVista('simulador')} />
  }

  // Validando el token guardado: evita el parpadeo de la pantalla de acceso
  // para quien ya tenía sesión iniciada.
  if (auth.estado === 'verificando') {
    return (
      <div className="acceso">
        <p className="rotulo">Verificando sesión…</p>
      </div>
    )
  }

  if (auth.estado === 'anonimo') {
    return (
      <Autenticacion
        onEntrar={auth.entrar}
        onRegistrarse={auth.registrarse}
        onVolver={() => setVista('landing')}
      />
    )
  }

  return (
    // h-svh: sin una altura definida acá, el `height: 100%` de .app no resuelve
    // y .main (flex:1) colapsa, rompiendo el scroll interno del chat.
    <SidebarProvider className="h-svh overflow-hidden">
      <AppSidebar
        onIrInicio={() => {
          sim.reiniciar()
          setVista('landing')
        }}
        onNuevoCaso={() => {
          sim.reiniciar()
          setVistaSimulador('sesion')
        }}
        onVerEvaluacion={() => {
          setVistaSimulador('sesion')
          setScorecardVisible(true)
        }}
        onVerHistorial={() => setVistaSimulador('historial')}
        onVerMetricas={() => setVistaSimulador('metricas')}
        onVerMetricasCasos={() => setVistaSimulador('metricas-casos')}
        tieneEvaluacion={!!sim.evaluacion}
        usuario={auth.usuario}
        onSalir={() => {
          sim.reiniciar()
          setVistaSimulador('sesion')
          auth.salir()
        }}
      />
      <SidebarInset>
        <div className={`app${enTablero ? ' app--pleno' : ''}`}>
          <header className="topbar">
            <p className="topbar__contexto">Paciente virtual · especialistas · tutor evaluador</p>
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

          {vistaSimulador === 'historial' && (
            <main className="main">
              <HistorialSesiones
                onNuevoCaso={() => {
                  sim.reiniciar()
                  setVistaSimulador('sesion')
                }}
              />
            </main>
          )}

          {vistaSimulador === 'metricas' && (
            <main className="main main--pleno">
              <MetricasUso />
            </main>
          )}

          {vistaSimulador === 'metricas-casos' && (
            <main className="main main--pleno">
              <MetricasCasos />
            </main>
          )}

          {vistaSimulador === 'sesion' && (
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
          )}

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
      </SidebarInset>
    </SidebarProvider>
  )
}
