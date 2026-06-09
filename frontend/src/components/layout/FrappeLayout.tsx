/**
 * FrappeLayout — Frappe-embedded shell (/mint/*).
 *
 * Now delegates to the shared NeoCockpit chrome (bvisible/frappe-sidebar-react):
 * one sidebar that absorbs the header, gray frame + floating white panel around
 * the content. Replaces the old copy-pasted FrappeSidebar.tsx + FrappeNavbar.tsx
 * (deleted). NeoCockpit reads window.frappe.boot (the curated mini-boot) and
 * navigates via window.location.href (env="spa").
 */
import type { ReactNode } from 'react'
import { NeoCockpit } from '@neoffice/frappe-sidebar-react'

interface FrappeLayoutProps {
	children: ReactNode
}

export function FrappeLayout({ children }: FrappeLayoutProps) {
	return (
		<NeoCockpit env="spa">
			<div className="page-content">{children}</div>
		</NeoCockpit>
	)
}
