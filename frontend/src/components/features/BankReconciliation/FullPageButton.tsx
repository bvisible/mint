//// Neoffice — added file (no upstream equivalent). The reconciliation on the whole surface of the screen, and back (Daniel, 05.11):
//// framed in a tab of Finance the page has the room under the desk's header and tabs, and a width the person chose; at /mint it has the
//// whole window. One icon goes from the first to the second, on the same tab of the page, and the same icon comes back.
import { useAtomValue } from "jotai"
import { Maximize2, Minimize2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { EMBEDDED, outerWindow } from "@/lib/embedded"
import _ from "@/lib/translate"
import { bankRecTabAtom } from "./bankRecAtoms"

/** The query of the full page that says which tab to open on. */
export const FULL_PAGE_TAB_PARAM = "tab"

// The tab of Finance that frames the page, and the address the frame shows for the bank files (it opens its own tab).
const FINANCE_TAB = "/app/accounting?tab=reconcile"
const BANK_FILES_SCREEN = "/mint/statement-imports"

const FullPageButton = () => {
    const tab = useAtomValue(bankRecTabAtom)

    const label = EMBEDDED ? _("Work on the whole page") : _("Back to Finance")

    const go = () => {
        if (EMBEDDED) {
            outerWindow().location.assign(`/mint?${FULL_PAGE_TAB_PARAM}=${encodeURIComponent(tab)}`)
        } else {
            window.location.assign(tab === "Bank Files" ? `${FINANCE_TAB}&screen=${encodeURIComponent(BANK_FILES_SCREEN)}` : FINANCE_TAB)
        }
    }

    return (
        <Tooltip>
            <TooltipTrigger asChild>
                <Button size="icon" variant="outline" title={label} aria-label={label} onClick={go}>
                    {EMBEDDED ? <Maximize2 /> : <Minimize2 />}
                </Button>
            </TooltipTrigger>
            <TooltipContent>{label}</TooltipContent>
        </Tooltip>
    )
}

export default FullPageButton
