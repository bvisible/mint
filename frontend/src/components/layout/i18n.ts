//// Neoffice — added file (no upstream equivalent): typed accessor for the window shim that
//// frontend/index.html installs when the desk bundle is absent (16eec35). WARNING: nothing
//// imports t() today — components use lib/translate instead. Its docstring is also in
//// French, unlike the rest of the codebase. Decide at the merge: wire it up or delete it.
/**
 * Access helper for the `window.__` shim defined in index.html.
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
