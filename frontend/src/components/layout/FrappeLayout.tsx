////// Neoffice — added file (no upstream equivalent): the shell /mint renders inside when it is
////// served from the Frappe desk (711dfb1, then 2c514a4 / 166aa08 which swapped the local copy
////// for the shared NeoCockpit package). Upstream's SPA is standalone and has no chrome.
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
		// Mint is the finance surface: pin the Finance module in the menu
		<NeoCockpit env="spa" defaultApp="Finance">
			<div className="page-content">{children}</div>
		</NeoCockpit>
	)
}
