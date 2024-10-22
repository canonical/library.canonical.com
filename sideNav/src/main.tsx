import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// Declare the __NAV_ITEMS__ property on the Window interface
declare global {
  interface Window {
    __NAV_ITEMS__: any;
    __PREVIOUS_SLUG__:any;
  }
}


createRoot(document.getElementById('merge-point')!).render(
  <StrictMode>
    <App/>
  </StrictMode>,
)
