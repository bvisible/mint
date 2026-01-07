import { FrappeProvider } from 'frappe-react-sdk'
import BankReconciliation from './pages/BankReconciliation'
import { Toaster } from './components/ui/sonner'
import { FrappeSidebar } from '@neoffice/frappe-sidebar-react'

function App() {

	return (
		<FrappeProvider
			swrConfig={{
				errorRetryCount: 2
			}}
			socketPort={import.meta.env.VITE_SOCKET_PORT}
			siteName={window.frappe?.boot?.sitename ?? import.meta.env.VITE_SITE_NAME}>
			<div className="flex h-screen overflow-hidden">
				<FrappeSidebar />
				<div className="flex-1 overflow-auto">
					<BankReconciliation />
				</div>
			</div>
			<Toaster richColors />
		</FrappeProvider>
	)
}

export default App
