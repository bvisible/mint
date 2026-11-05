//// Neoffice — added file (no upstream equivalent). The reconciliation on the whole surface of the screen, and back (Daniel, 05.11):
//// framed in a tab of Finance the page has the room under the desk's header and tabs, and a width the person chose; at /mint it has the
//// whole window. One icon goes from the first to the second, on the same screen (and the same tab of the bank page), and the same icon
//// comes back. Both pages of the reconciliation carry it: the bank's and the party's.
import { useAtomValue } from "jotai"
import { Maximize2, Minimize2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { EMBEDDED, outerWindow } from "@/lib/embedded"
import _ from "@/lib/translate"
import { bankRecTabAtom } from "./bankRecAtoms"

/** The query of the full page that says which tab to open on. */
export const FULL_PAGE_TAB_PARAM = "tab"

// The tabs of Finance that frame the two pages, and the address the frame shows for the bank files (it opens its own tab).
const BANK_TAB = "/app/accounting?tab=reconcile"
const PARTY_TAB = "/app/accounting?tab=party_reconcile"
const BANK_FILES_SCREEN = "/mint/statement-imports"
const PARTY_SCREEN = "/mint/party-reconciliation"

const FullPageButton = () => {
    const tab = useAtomValue(bankRecTabAtom)

    const label = EMBEDDED ? _("Work on the whole page") : _("Back to Finance")

    const go = () => {
        const here = window.location.pathname
        const party = here.startsWith(PARTY_SCREEN)
        if (EMBEDDED) {
            // the same screen at the top of the window; the bank page also says which of its tabs is open
            outerWindow().location.assign(party ? PARTY_SCREEN : `/mint?${FULL_PAGE_TAB_PARAM}=${encodeURIComponent(tab)}`)
        } else if (party) {
            window.location.assign(PARTY_TAB)
        } else {
            window.location.assign(tab === "Bank Files" ? `${BANK_TAB}&screen=${encodeURIComponent(BANK_FILES_SCREEN)}` : BANK_TAB)
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
