import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import './lib/namespace'

// Defensive sync — frappe.model.sync(frappe.boot.docs) throws when docs is
// missing (the curated mini-boot might omit it on a fresh install before the
// session has loaded meta). React still needs to mount in that case.
function safeSyncDocs() {
  try {
    // @ts-expect-error - frappe globals provided by index.html
    if (window.frappe?.model?.sync && window.frappe?.boot?.docs) {
      // @ts-expect-error - frappe globals provided by index.html
      window.frappe.model.sync(window.frappe.boot.docs)
    }
  } catch (e) {
    console.warn('[mint] frappe.model.sync failed, continuing without docs:', e)
  }
}

if (import.meta.env.DEV) {
  fetch('/api/method/mint.www.mint.get_context_for_dev', {
    method: 'POST',
  })
    .then(response => response.json())
    .then((values) => {
      const v = JSON.parse(values.message)
      if (!window.frappe) window.frappe = {}
      // @ts-expect-error - frappe will be available
      frappe.boot = v
      // @ts-expect-error - frappe will be available
      frappe._messages = frappe.boot['__messages']
      safeSyncDocs()
      createRoot(document.getElementById('root') as HTMLElement).render(
        <StrictMode>
          <App />
        </StrictMode>,
      )
    })
} else {
  safeSyncDocs()
  createRoot(document.getElementById('root') as HTMLElement).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}
