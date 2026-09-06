//// Neoffice — added file (no upstream equivalent): typed accessor for the window shim that
//// frontend/index.html installs when the desk bundle is absent (16eec35). WARNING: nothing
//// imports t() today — components use lib/translate instead. Its docstring is also in
//// merge: wire it up or delete it. Its French docstring was translated on 2026-09-06.
/**
 * Access helper for the `window.__` shim defined in index.html.
 *
 * The shim looks the text up in `frappe._messages` and falls back to the source
 * string. It supports positional placeholders `{0}` and the `Source|Context` pattern.
 *
 * Exported as a TypeScript-typed function for the React components.
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
