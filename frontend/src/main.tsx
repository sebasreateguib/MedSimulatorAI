import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Primero el sistema base: así los modificadores de landing.css lo pisan y no al revés.
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
