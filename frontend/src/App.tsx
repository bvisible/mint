import { useEffect } from 'react'
//// Neoffice — NOT ours: this import and the BankStatementImporter one below are
//// upstream v1.5.0, hand-ported with the CSV importer (89e7929). Take upstream's at
//// the merge. The imports after Toaster (toast, NeoCockpit, FrappeLayout, NoraLearn)
//// ARE ours: /mint runs inside the Neoffice cockpit and carries the Nora Learn overlay.
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { FrappeProvider } from 'frappe-react-sdk'
import BankReconciliation from './pages/BankReconciliation'
//// Neoffice — NOT ours: upstream v1.5.0 route, hand-ported (89e7929). See the note above.
import BankStatementImporter from './pages/BankStatementImporter'
import { Toaster } from './components/ui/sonner'
//// Neoffice — added (2c514a4, 44c8b52). NeoCockpit is the shared Neoffice shell;
//// FrappeLayout is the same shell fed by the mini-boot when embedded in Frappe;
//// NoraLearnProvider is the in-app tutorial/Ask-NORA overlay. None exist upstream.
import { toast } from 'sonner'
import { NeoCockpit } from '@neoffice/frappe-sidebar-react'
import { FrappeLayout } from './components/layout'
import { NoraLearnProvider } from '@neoffice/nora-learn-react'
import '@neoffice/nora-learn-react/styles'
//// Neoffice — added: Mint framed in a tab of the desk (lib/embedded.ts).
import { EMBEDDED, outerWindow } from './lib/embedded'

// Frappe integration flag — set by mint/www/mint.html before the bundle loads.
// When true, we wrap routes in the FrappeLayout (native sidebar + navbar)
// reimplemented locally, sourced from the curated mini-boot. When false (vite
// standalone dev), we fall back to the simpler @neoffice/frappe-sidebar-react
// package which only needs basic boot data.
const FRAPPE_INTEGRATION =
	typeof window !== 'undefined' &&
	(window as unknown as { __FRAPPE_INTEGRATION__?: boolean }).__FRAPPE_INTEGRATION__ === true

function App() {
	useEffect(() => {
		// Check if user is logged in by checking the Cookie "user_id"
		// In Frappe, unauthenticated users are "Guest"
		const userId = document.cookie?.split('; ').find(row => row.startsWith('user_id='))?.split('=')[1]?.trim()
		const isLoggedIn = userId !== 'Guest'

		if (!isLoggedIn) {
			if (import.meta.env.DEV) {
				return
			}
			//// Neoffice — framed in the desk, the login replaces the desk, not the frame.
			outerWindow().location.href = '/login?redirect-to=/mint'
			return
		}
	}, [])

	//// Neoffice — framed in a tab of the desk: no page of its own around it. The desk's links
	//// (a document, the home page) open in the desk rather than inside the frame - the router's
	//// own links are unaffected, it handles their clicks itself - and the page lets the desk's
	//// background show through.
	useEffect(() => {
		if (!EMBEDDED) return
		const base = document.createElement('base')
		base.target = '_top'
		document.head.appendChild(base)
		document.documentElement.classList.add('mint-embedded')
		//// Neoffice — <html> too: the desk's stylesheet paints it with --bg-color, the desk's page
		//// background, one shade darker than the card the frame sits on (Jérémy, 01.10: « la même
		//// couleur »). Both transparent, the frame shows the card itself, dark mode included.
		document.documentElement.style.setProperty('background', 'transparent', 'important')
		document.body.style.setProperty('background', 'transparent', 'important')
	}, [])

	// //// NEOFFICE PATCH — Bridge Frappe theme onto html[data-theme]
	// WHY: Mint is always embedded inside the Frappe shell on Neoffice
	//      deployments. Frappe writes the active theme to localStorage
	//      (`theme_active` already resolved + `appearance` raw) but the
	//      Mint route is rendered by its own www/mint.html template and
	//      Frappe never sets `<html data-theme="dark">` on it. The
	//      injected Neoffice menu stylesheet keys all its dark rules on
	//      that attribute, so the navbar/sidebar around Mint stayed in
	//      light mode no matter what the user picked in Frappe.
	//      Mirror the value here + live-sync via storage/poll.
	// REVIEW: drop when the Neoffice shell-bridge package exposes a
	//         single helper we can import everywhere.
	useEffect(() => {
		const readFrappeTheme = (): 'light' | 'dark' | null => {
			try {
				const ta = window.localStorage.getItem('theme_active')
				if (ta === 'dark' || ta === 'light') return ta
				const ap = (window.localStorage.getItem('appearance') || '').replace(/^"|"$/g, '')
				if (ap === 'dark' || ap === 'light') return ap
				if (ap === 'automatic') {
					return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
				}
			} catch { /* sandboxed contexts can throw */ }
			return null
		}
		const apply = (mode: 'light' | 'dark') => {
			document.documentElement.setAttribute('data-theme', mode)
		}
		let last = readFrappeTheme()
		if (last) apply(last)
		const sync = () => {
			const fresh = readFrappeTheme()
			if (!fresh || fresh === last) return
			last = fresh
			apply(fresh)
		}
		window.addEventListener('storage', sync)
		const id = window.setInterval(sync, 1000)
		return () => {
			window.removeEventListener('storage', sync)
			window.clearInterval(id)
		}
	}, [])

	const Routing = (
		<BrowserRouter basename={import.meta.env.VITE_BASE_NAME ? `/${import.meta.env.VITE_BASE_NAME}` : ''}>
			<Routes>
				<Route index element={<BankReconciliation />} />
				<Route path="/statement-importer" element={<BankStatementImporter />} />
				<Route path="*" element={<Navigate to="/" />} />
			</Routes>
		</BrowserRouter>
	)

	//// Neoffice — framed in the desk, the routes alone: the desk draws the menu and the tabs.
	const Shell = EMBEDDED ? (
		Routing
	) : FRAPPE_INTEGRATION ? (
		<FrappeLayout>{Routing}</FrappeLayout>
	) : (
		// standalone vite dev — same NeoCockpit shell, just without the mini-boot
		<NeoCockpit env="spa">{Routing}</NeoCockpit>
	)

	return (
		<FrappeProvider
			swrConfig={{
				errorRetryCount: 2
			}}
			socketPort={import.meta.env.VITE_SOCKET_PORT}
			siteName={window.frappe?.boot?.sitename ?? import.meta.env.VITE_SITE_NAME}>
			{/* //// Neoffice — replaced upstream's bare <BankReconciliation /> render. Routes */}
			{/* //// now go through the cockpit shell (Shell above) and the Nora Learn overlay; the */}
			{/* //// Toaster loses theme='light' because the cockpit drives light/dark itself. */}
			<NoraLearnProvider config={{
				appName: 'mint',
				navigate: (url) => { outerWindow().location.href = url },
				getCurrentRoute: () => window.location.pathname,
				showAlert: (msg, variant) => {
					if (variant === 'success') toast.success(msg)
					else if (variant === 'error') toast.error(msg)
					else if (variant === 'warning') toast.warning(msg)
					else toast.info(msg)
				},
			}}>
				{Shell}
			</NoraLearnProvider>
			<Toaster richColors />
		</FrappeProvider>
	)
}

export default App
