//// Neoffice — added file (no upstream equivalent). The small lightbulb that holds the explanation of a button or of a
//// choice. The sentence is not written under every button (nobody reads it after the twentieth time, and it costs a line
//// of a screen that has none to spare): it opens when the icon is hovered, with a way to the page of the manual that
//// speaks of it, never to the front page of the manual (Daniel, 11.11).
import { Lightbulb } from "lucide-react"
import type { ReactNode } from "react"
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"
import _ from "@/lib/translate"

/** The public manual of Neoffice. */
export const MANUAL_URL = "https://wiki.neoffice.ch/wiki/manuel"

const GAPS_PAGE = `${MANUAL_URL}/ecarts-de-paiement`

/** The page of the manual (and the heading of that page) that each hint opens: the subject, not the front page. */
export const MANUAL = {
    /** how a difference between the payment and the invoice is decided in the bank reconciliation */
    decide: `${GAPS_PAGE}#décider-dun-écart-dans-le-rapprochement-bancaire`,
    /** a partial payment: leave the rest, credit note, or write it off */
    partial: `${GAPS_PAGE}#un-paiement-partiel-trois-choix`,
    /** what each choice writes in the books */
    booked: `${GAPS_PAGE}#ce-que-ça-écrit-en-comptabilité`,
    /** the accounts and the thresholds of the company, set once */
    settings: `${GAPS_PAGE}#régler-la-société-une-fois`,
    /** the rule of a customer who always pays a share */
    rule: `${GAPS_PAGE}#la-règle-pour-un-client-qui-paie-toujours-une-part`,
    /** the payment form that the « Reconcile manually » button opens */
    manualPayment: `${MANUAL_URL}/rapprochement-bancaire-paiements`,
} as const

const InfoHint = ({ children, href = MANUAL.decide, side = "top" }: { children: ReactNode, href?: string, side?: "top" | "left" | "bottom" }) => (
    <HoverCard openDelay={80} closeDelay={150}>
        <HoverCardTrigger asChild>
            <button
                type="button"
                aria-label={_("What does this do?")}
                className="inline-flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-black/5 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            >
                <Lightbulb className="size-4" />
            </button>
        </HoverCardTrigger>
        <HoverCardContent className="w-72 text-sm" align="end" side={side}>
            <div className="flex flex-col gap-2 leading-snug">
                <div className="flex flex-col gap-1.5">{children}</div>
                <a className="w-fit text-xs underline underline-offset-2" href={href} target="_blank" rel="noopener noreferrer">
                    {_("Read more in the manual")}
                </a>
            </div>
        </HoverCardContent>
    </HoverCard>
)

export default InfoHint
