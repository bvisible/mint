//// Neoffice — added file (no upstream equivalent). Words and links of the follow-up of the statement imports.
import { formatDate } from "@/lib/date"
import { formatCurrency } from "@/lib/numbers"
import _ from "@/lib/translate"
import type { ImportLine, LineState } from "./types"

/** The states of a line that still waits for someone: a gap to decide, or no invoice recognised. */
export const WAITING_STATES: LineState[] = ["to_decide", "to_match"]

/** The order a person reads them in: what is done, then what waits, then what needs no one. */
export const STATE_ORDER: LineState[] = [
    "passed_alone", "handled", "left_open", "to_decide", "to_match", "failed", "cancelled", "duplicate", "not_imported",
]

export const stateLabel = (state: LineState): string => ({
    passed_alone: _("Passed by the import"),
    handled: _("Reconciled afterwards"),
    left_open: _("Left open"),
    to_decide: _("To decide"),
    to_match: _("To match"),
    duplicate: _("Already in the bank"),
    failed: _("Not handled"),
    cancelled: _("Cancelled"),
    not_imported: _("Not imported yet"),
}[state])

/** Done is green, what waits is amber, what went wrong is red, the rest is quiet. */
export const stateTone = (state: LineState): string => ({
    passed_alone: "border-green-200 bg-green-50 text-green-800",
    handled: "border-green-200 bg-green-50 text-green-800",
    left_open: "border-border bg-muted text-muted-foreground",
    to_decide: "border-amber-300 bg-amber-50 text-amber-900",
    to_match: "border-amber-300 bg-amber-50 text-amber-900",
    failed: "border-red-200 bg-red-50 text-red-800",
    cancelled: "border-border bg-muted text-muted-foreground",
    duplicate: "border-border bg-muted text-muted-foreground",
    not_imported: "border-border bg-muted text-muted-foreground",
}[state])

export const kindLabel = (kind: string | null): string => ({
    rounding: _("rounding"),
    early_discount: _("early payment discount"),
    accepted_rebate: _("accepted rebate"),
    partial: _("partial payment"),
    dunning_fee: _("dunning fee"),
    overpaid: _("overpayment"),
} as Record<string, string>)[kind ?? ""] ?? ""

export const sourceLabel = (source: "ebics" | "manual"): string =>
    source === "ebics" ? _("Bank connection") : _("File deposited by hand")

/** A document of the desk, opened in the desk (the frame's links go to the top window). */
export const documentHref = (doctype: string, name: string) =>
    `/app/${doctype.toLowerCase().replace(/ /g, "-")}/${encodeURIComponent(name)}`

/** What became of a line, in a sentence. The days are formatted apart: a string literal inside the arguments of _()
 * is read by the message extractor as the CONTEXT of the message, and a message with a context is never found without it. */
const day = (value: string | null) => (value ? formatDate(value, "Do MMM YYYY") : "")

export const describeLine = (line: ImportLine, currency: string): string => {
    const gap = line.difference_kind && line.difference_kind !== "exact"
        ? `${formatCurrency(Math.abs(line.difference_amount ?? 0), currency)} (${kindLabel(line.difference_kind)})`
        : ""
    const voucher = line.vouchers[0]
    switch (line.state) {
        case "passed_alone":
            if (line.rule) return _("Made by itself by the rule of the customer, credit note {0}", [line.credit_note ?? ""])
            return gap ? _("Passed by the import, difference of {0}", [gap]) : _("Passed by the import")
        case "handled":
            if (line.credit_note) return _("Reconciled, the rest settled by the credit note {0}", [line.credit_note])
            return voucher?.by
                ? _("Reconciled by {0} on {1}", [voucher.by, day(voucher.on)])
                : _("Reconciled in the bank reconciliation")
        case "left_open":
            return _("Left open by {0} on {1}", [line.decided_by ?? "", day(line.decided_on)])
        case "to_decide":
            return gap ? _("Difference of {0}: to decide", [gap]) : _("To decide")
        case "to_match":
            return _("No invoice recognised: to match in the bank reconciliation")
        case "duplicate":
            return _("The bank already had this line: nothing was created")
        case "failed":
            return _("The import could not handle this line")
        case "cancelled":
            return _("The bank line was cancelled")
        default:
            return _("Not imported yet")
    }
}
