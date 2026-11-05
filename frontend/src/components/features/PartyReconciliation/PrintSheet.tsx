//// Neoffice — added file (no upstream equivalent). A document drawn on a sheet of paper, as the side preview of the desk
//// draws it (neoffice_theme `PrintSheet`): the HTML of its print format in a frame with no script, at the width of a
//// page, scaled to the room there is, with no PDF in between. The PDF and the print are one click away.
import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { FileText, Printer } from "lucide-react"
import { Button } from "@/components/ui/button"
import _ from "@/lib/translate"

// 210 mm at 96 dpi: the page is never narrowed, only scaled; a short document still shows as a whole sheet
const PAGE_PX = 794
const PAGE_H = Math.round(297 * 96 / 25.4)
// the « continued on next page » footer is for the pages of the PDF: on one flowing page it would sit at the top
const FRAME_CSS = "html{overflow:hidden}html,body{margin:0;background:#fff}#footer-html{display:none!important}.neo-lp-end{height:0;clear:both}"
// the grey gutter and card of the print view go: the sheet has the paper's whole width
const GUTTER_STYLE = "display:block!important;margin:0!important;padding:0!important;background:#fff!important"
const SHEET_STYLE = "width:auto!important;max-width:none!important;margin-left:0!important;margin-right:0!important;box-shadow:none!important;border:0!important;border-radius:0!important"

export type PrintAnswer = { html?: string, style?: string, print_css?: string, error?: string }

type Props = { drawn: PrintAnswer | undefined, loading: boolean, pdfUrl?: string | null, title: string }

/** The PDF of the document, printed from a frame out of sight (the same PDF as the « PDF » button). */
const printPdf = (url: string) => {
    const frame = document.createElement("iframe")
    frame.setAttribute("aria-hidden", "true")
    frame.style.cssText = "position:fixed;width:0;height:0;border:0;visibility:hidden"
    frame.onload = () => {
        // the frame's first, empty page loads too: wait for the PDF's
        if (!frame.contentWindow || frame.contentWindow.location.href === "about:blank") return
        try {
            setTimeout(() => { frame.contentWindow?.focus(); frame.contentWindow?.print() }, 250)
        } catch {
            window.open(url, "_blank", "noopener")
        }
    }
    frame.src = url
    document.body.appendChild(frame)
    setTimeout(() => frame.remove(), 120000)
}

const PrintSheet = ({ drawn, loading, pdfUrl, title }: Props) => {
    const hostRef = useRef<HTMLDivElement>(null)
    const [mode, setMode] = useState<"live" | "pdf">("live")
    const [height, setHeight] = useState(PAGE_H)
    const [scale, setScale] = useState(1)

    const fit = useCallback(() => {
        const room = (hostRef.current?.clientWidth ?? 0) - 32
        if (room > 0) setScale(Math.min(1, Math.max(0.3, room / PAGE_PX)))
    }, [])
    useEffect(() => {
        const host = hostRef.current
        if (!host || !window.ResizeObserver) return
        const observer = new ResizeObserver(fit)
        observer.observe(host)
        fit()
        return () => observer.disconnect()
    }, [fit, mode, drawn])

    const srcDoc = useMemo(() => {
        if (!drawn?.html) return ""
        const printCss = drawn.print_css ? `<link rel="stylesheet" href="${drawn.print_css}">` : ""
        return `<!doctype html><html><head><meta charset="utf-8"><base href="${window.location.origin}/">${printCss}` +
            `<style>${drawn.style ?? ""}</style><style>${FRAME_CSS}</style></head><body>` +
            `<div class="print-format-gutter" style="${GUTTER_STYLE}"><div class="print-format" style="${SHEET_STYLE}">` +
            `${drawn.html}<div class="neo-lp-end"></div></div></div></body></html>`
    }, [drawn])

    // measured from the drawing itself: a document is never shorter than a sheet
    const onLoad = (event: React.SyntheticEvent<HTMLIFrameElement>) => {
        const doc = event.currentTarget.contentDocument
        if (!doc) return
        const content = Math.max(doc.documentElement.scrollHeight, doc.body ? doc.body.scrollHeight : 0)
        setHeight(Math.max(content, PAGE_H))
    }

    const failed = !loading && (!drawn || drawn.error || !drawn.html)

    return (
        <div className="flex flex-col gap-2">
            <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">
                    {loading ? _("Updating…") : failed ? "" : _("Up to date")}
                </span>
                <span className="flex-1" />
                {pdfUrl && (
                    <Button variant={mode === "pdf" ? "secondary" : "outline"} size="sm" onClick={() => setMode(mode === "pdf" ? "live" : "pdf")}
                        title={mode === "pdf" ? _("Back to the live preview") : _("Show the PDF of the saved version")}>
                        <FileText className="size-4" />PDF
                    </Button>
                )}
                {pdfUrl && (
                    <Button variant="outline" size="sm" onClick={() => printPdf(pdfUrl)} title={_("Print the PDF")}>
                        <Printer className="size-4" />{_("Print")}
                    </Button>
                )}
            </div>
            {mode === "pdf" && pdfUrl ? (
                <iframe title={title} src={`${pdfUrl}#view=FitH`} className="h-[68vh] w-full rounded-md border bg-white" />
            ) : (
                <div ref={hostRef} className="overflow-hidden rounded-md border bg-muted/40 p-4">
                    {failed ? (
                        <p className="text-sm text-muted-foreground">{_("The preview could not be drawn.")}</p>
                    ) : (
                        <div className="mx-auto" style={{ width: PAGE_PX * scale, height: height * scale }}>
                            <div style={{ width: PAGE_PX, height, transform: `scale(${scale})`, transformOrigin: "top left" }}>
                                <iframe
                                    title={title}
                                    sandbox="allow-same-origin"
                                    srcDoc={srcDoc}
                                    onLoad={onLoad}
                                    className="border-0 bg-white shadow-sm"
                                    style={{ width: PAGE_PX, height }}
                                />
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}

export default PrintSheet
