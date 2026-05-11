import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { FrappeProvider } from 'frappe-react-sdk'
import BankReconciliation from './pages/BankReconciliation'
import BankStatementImporter from './pages/BankStatementImporter'
import { Toaster } from './components/ui/sonner'
import { toast } from 'sonner'
import { FrappeSidebar as PackageFrappeSidebar } from '@neoffice/frappe-sidebar-react'
import { FrappeLayout } from './components/layout'
import { NoraLearnProvider } from '@neoffice/nora-learn-react'
import '@neoffice/nora-learn-react/styles'

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
			window.location.href = '/login?redirect-to=/mint'
			return
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

	const Shell = FRAPPE_INTEGRATION ? (
		<FrappeLayout>{Routing}</FrappeLayout>
	) : (
		<div className="flex h-screen overflow-hidden">
			<PackageFrappeSidebar homeUrl="/app/home" />
			<div className="flex-1 overflow-auto">{Routing}</div>
		</div>
	)

	return (
		<FrappeProvider
			swrConfig={{
				errorRetryCount: 2
			}}
			socketPort={import.meta.env.VITE_SOCKET_PORT}
			siteName={window.frappe?.boot?.sitename ?? import.meta.env.VITE_SITE_NAME}>
			<NoraLearnProvider config={{
				appName: 'mint',
				navigate: (url) => { window.location.href = url },
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
