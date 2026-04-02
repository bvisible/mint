import { useEffect } from 'react'
import { FrappeProvider } from 'frappe-react-sdk'
import BankReconciliation from './pages/BankReconciliation'
import { Toaster } from './components/ui/sonner'
import { toast } from 'sonner'
import { FrappeSidebar } from '@neoffice/frappe-sidebar-react'
import { NoraLearnProvider } from '@neoffice/nora-learn-react'
import '@neoffice/nora-learn-react/styles'

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
			// Redirect to Frappe login page
			window.location.href = '/login?redirect-to=/mint'
			return
		}
	}, [])

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
				<div className="flex h-screen overflow-hidden">
					<FrappeSidebar homeUrl="/app/home" />
					<div className="flex-1 overflow-auto">
						<BankReconciliation />
					</div>
				</div>
			</NoraLearnProvider>
			<Toaster richColors />
		</FrappeProvider>
	)
}

export default App
