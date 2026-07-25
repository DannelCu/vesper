import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'
import ProcessDetail from './ProcessDetail.jsx'

// See the comment in main.jsx for why import.meta.env.DEV, not
// window.VESPER_DEV_URL, is what actually tells vesper dev apart from this
// app's serve_frontend=True production build.
if (!import.meta.env.DEV) {
  window.vesper.security.lockdown({ force: true })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ProcessDetail />
  </StrictMode>
)
