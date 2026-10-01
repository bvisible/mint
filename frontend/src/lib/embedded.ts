//// Neoffice — added file (no upstream equivalent). A space of the Neoffice desk shows Mint in a
//// frame under its tabs (Finance's « Reconciliation » tab, 01.10.2026), opened as /mint?embed=1.
//// The desk already draws the chrome around it, so the frame renders the pages alone; a page
//// reached inside the frame (the statement importer) loses the query, hence the frame test too.
export const EMBEDDED: boolean =
	typeof window !== 'undefined' &&
	(new URLSearchParams(window.location.search).get('embed') === '1' || window.self !== window.top)

/** The window a navigation outside Mint goes to: the desk around the frame when embedded. */
export const outerWindow = (): Window => (EMBEDDED && window.top ? window.top : window)
