//// Neoffice — added file (no upstream equivalent). The small lightbulb that holds the explanation of a button or of a
//// choice. The sentence is not written under every button (nobody reads it after the twentieth time, and it costs a line
//// of a screen that has none to spare): it opens when the icon is hovered, with a way to the manual for whoever wants more.
import { Lightbulb } from "lucide-react"
import type { ReactNode } from "react"
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"
import _ from "@/lib/translate"

/** The public manual of Neoffice, until the page of the payment gaps has its own address. */
export const MANUAL_URL = "https://wiki.neoffice.ch/wiki/manuel"

const InfoHint = ({ children, side = "top" }: { children: ReactNode, side?: "top" | "left" | "bottom" }) => (
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
                <a className="w-fit text-xs underline underline-offset-2" href={MANUAL_URL} target="_blank" rel="noopener noreferrer">
                    {_("Open the manual")}
                </a>
            </div>
        </HoverCardContent>
    </HoverCard>
)

export default InfoHint
