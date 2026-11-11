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
    /** the bank files tab: what came in and what became of each line */
    bankFiles: `${MANUAL_URL}/fichiers-bancaires`,
    /** bringing a statement in by hand (CAMT or PDF) */
    importStatement: `${MANUAL_URL}/import-releve-camt-pdf`,
    /** the four figures at the top of the bank reconciliation */
    figures: `${MANUAL_URL}/rapprochement-bancaire#les-chiffres-du-haut`,
    /** a line whose invoice was not recognised: choosing the invoices it settles */
    pickInvoices: `${MANUAL_URL}/rapprochement-bancaire#une-ligne-importée-sans-facture-reconnue-choisir-les-factures`,
} as const

/** `more`: a second page of the manual, when the hint speaks of two subjects. `small`: the size of the labels of the figures at
 * the top, where it replaces the bare « i » of ERPNext. `width`: the width of the card that opens. */
const InfoHint = ({ children, href = MANUAL.decide, more, side = "top", small = false, width = "w-72" }: { children: ReactNode, href?: string, more?: { href: string, label: string }, side?: "top" | "left" | "bottom" | "right", small?: boolean, width?: string }) => (
    <HoverCard openDelay={80} closeDelay={150}>
        <HoverCardTrigger asChild>
            <button
                type="button"
                aria-label={_("What does this do?")}
                className={`inline-flex shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-black/5 hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${small ? "size-5" : "size-7"}`}
            >
                <Lightbulb className={small ? "size-3.5" : "size-4"} />
            </button>
        </HoverCardTrigger>
        <HoverCardContent className={`${width} text-sm`} align={small ? "start" : "end"} side={side}>
            <div className="flex flex-col gap-2 leading-snug">
                <div className="flex flex-col gap-1.5">{children}</div>
                <div className="flex flex-col gap-1">
                    <a className="w-fit text-xs underline underline-offset-2" href={href} target="_blank" rel="noopener noreferrer">
                        {_("Read more in the manual")}
                    </a>
                    {more && (
                        <a className="w-fit text-xs underline underline-offset-2" href={more.href} target="_blank" rel="noopener noreferrer">
                            {more.label}
                        </a>
                    )}
                </div>
            </div>
        </HoverCardContent>
    </HoverCard>
)

export default InfoHint
