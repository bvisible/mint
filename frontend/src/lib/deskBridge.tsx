//// Neoffice — added file (no upstream equivalent). The contract of an application framed in a space of the
//// desk (neoffice_theme workspace_tabs.js, « the application and the frame talk »): the frame tells the desk
//// which screen it shows (« mint:route »), and the desk moves the frame to the screen of the tab the reader
//// opens (« mint:navigate »). Without it, two tabs of Mint under one desk page would share one frame that
//// no tab could move: the second tab would show the screen of the first.
import { useEffect } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { EMBEDDED } from "./embedded"

const DeskBridge = () => {
    const location = useLocation()
    const navigate = useNavigate()

    // Each screen the router reaches is told to the desk (the path is the router's own, without « /mint »).
    useEffect(() => {
        if (!EMBEDDED || window.parent === window) return
        window.parent.postMessage({ type: "mint:route", path: location.pathname }, window.location.origin)
    }, [location.pathname])

    // The desk asks for a screen: only from the page that frames this one, only from this origin.
    useEffect(() => {
        if (!EMBEDDED) return
        const listen = (event: MessageEvent) => {
            if (event.origin !== window.location.origin || event.source !== window.parent) return
            const data = event.data as { type?: unknown, path?: unknown } | null
            if (!data || data.type !== "mint:navigate" || typeof data.path !== "string" || !data.path.startsWith("/")) return
            navigate(data.path)
        }
        window.addEventListener("message", listen)
        return () => window.removeEventListener("message", listen)
    }, [navigate])

    return null
}

export default DeskBridge
