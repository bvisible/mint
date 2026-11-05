//// Neoffice — added file (no upstream equivalent). A space of the Neoffice desk shows Mint in a
//// frame under its tabs (Finance's « Reconciliation » tab, 01.10.2026), opened as /mint?embed=1.
//// The desk already draws the chrome around it, so the frame renders the pages alone; a page
//// reached inside the frame (the statement importer) loses the query, hence the frame test too.
export const EMBEDDED: boolean =
	typeof window !== 'undefined' &&
	(new URLSearchParams(window.location.search).get('embed') === '1' || window.self !== window.top)

/** The window a navigation outside Mint goes to: the desk around the frame when embedded. */
export const outerWindow = (): Window => (EMBEDDED && window.top ? window.top : window)

let expanded = 0
let giveBack: (() => void) | null = null

/**
 * A dialog opened inside the frame is centred in the frame, which is only the room under the desk's tabs: too little for a table
 * of invoices, and its buttons fell below the visible part. While a dialog is open the frame takes the WHOLE window of the desk
 * (over its tabs and its menu, under the dialog's own dimmed backdrop), and the page of the frame keeps the place and the size it
 * had inside it, so that nothing behind the dialog moves. Returns what gives the room back; nested dialogs count.
 * Same-origin frame only: anywhere else (not framed, or a frame we cannot reach) it does nothing.
 */
export const expandFrame = (): (() => void) => {
	let frame: HTMLElement | null = null
	try {
		frame = EMBEDDED ? window.frameElement as HTMLElement | null : null
	} catch {
		frame = null
	}
	if (!frame || !frame.parentElement || !document.getElementById('root')) return () => { /* not framed */ }
	expanded += 1
	if (expanded === 1) {
		try {
			giveBack = takeTheWindow(frame)
		} catch {
			giveBack = null
		}
	}
	let given = false
	return () => {
		if (given) return
		given = true
		expanded -= 1
		if (expanded === 0 && giveBack) {
			try {
				giveBack()
			} catch {
				// the frame is left as the desk made it: a reload puts everything back
			}
			giveBack = null
		}
	}
}

const takeTheWindow = (frame: HTMLElement): (() => void) => {
	const app = document.getElementById('root') as HTMLElement
	const rect = frame.getBoundingClientRect()
	const was = { frame: frame.getAttribute('style'), app: app.getAttribute('style') }
	const scrolled = { top: window.scrollY, left: window.scrollX }
	// the desk's page keeps the room the frame took: a placeholder of the frame's size takes its place in the flow
	const holder = frame.ownerDocument.createElement('div')
	holder.style.cssText = `width:${rect.width}px;height:${rect.height}px;pointer-events:none`
	frame.parentElement?.insertBefore(holder, frame)
	// the page of the frame stays where it was, at its size, and scrolls inside its own box...
	app.style.cssText = `${was.app ?? ''};position:fixed;left:${rect.left}px;top:${rect.top}px;width:${rect.width}px;height:${rect.height}px;overflow:auto`
	app.scrollTop = scrolled.top
	app.scrollLeft = scrolled.left
	// ...while the frame itself covers the window
	frame.style.cssText = `${was.frame ?? ''};position:fixed;left:0;top:0;width:100vw;height:100vh;min-height:0;z-index:2000`
	const leave = () => giveBack?.()
	window.addEventListener('pagehide', leave)
	return () => {
		window.removeEventListener('pagehide', leave)
		const at = { top: app.scrollTop, left: app.scrollLeft }
		frame.style.cssText = was.frame ?? ''
		if (was.frame === null) frame.removeAttribute('style')
		app.style.cssText = was.app ?? ''
		if (was.app === null) app.removeAttribute('style')
		holder.remove()
		window.scrollTo(at.left, at.top)
	}
}
