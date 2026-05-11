/**
 * Helper d'accès au shim `window.__` défini dans index.html.
 *
 * Le shim fait : lookup dans `frappe._messages`, fallback sur la string source.
 * Supporte les placeholders positionnels `{0}` et le pattern `Source|Context`.
 *
 * On l'exporte comme fonction TypeScript-typée pour les composants React.
 */
declare global {
	interface Window {
		__?: (text: string, args?: (string | number)[], context?: string) => string
	}
}

export function t(text: string, args?: (string | number)[], context?: string): string {
	if (typeof window === 'undefined' || !window.__) return text
	return window.__(text, args, context)
}
