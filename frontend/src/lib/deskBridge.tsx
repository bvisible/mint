//// Neoffice — added file (no upstream equivalent). The contract of an application framed in a space of the
//// desk (neoffice_theme workspace_tabs.js, « the application and the frame talk »): the frame tells the desk
//// which screen it shows (« <app>:route »), and the desk moves the frame to the screen of the tab the reader
//// opens (« <app>:navigate »). Without it, two tabs of one application under one desk page would share one
//// frame that no tab could move: the second tab would show the screen of the first.
//// <app> is the first segment of the address the frame is served at, never a name written here: it is the name
//// of the application today and will be the banking module's after the v16 move, with nothing to change.
import { useEffect } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { EMBEDDED } from "./embedded"

const appSegment = () => window.location.pathname.split("/")[1] ?? ""

const DeskBridge = () => {
    const location = useLocation()
    const navigate = useNavigate()

    // Each screen the router reaches is told to the desk (the path is the router's own, without the application's root).
    useEffect(() => {
        const app = appSegment()
        if (!EMBEDDED || !app || window.parent === window) return
        window.parent.postMessage({ type: `${app}:route`, path: location.pathname }, window.location.origin)
    }, [location.pathname])

    // The desk asks for a screen: only from the page that frames this one, only from this origin.
    useEffect(() => {
        const app = appSegment()
        if (!EMBEDDED || !app) return
        const listen = (event: MessageEvent) => {
            if (event.origin !== window.location.origin || event.source !== window.parent) return
            const data = event.data as { type?: unknown, path?: unknown } | null
            if (!data || data.type !== `${app}:navigate` || typeof data.path !== "string" || !data.path.startsWith("/")) return
            navigate(data.path)
        }
        window.addEventListener("message", listen)
        return () => window.removeEventListener("message", listen)
    }, [navigate])

    return null
}

export default DeskBridge
