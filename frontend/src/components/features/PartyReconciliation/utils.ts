//// Neoffice — added file (no upstream equivalent). Keys, amounts and labels of the party reconciliation.
import _ from "@/lib/translate"
import type { InvoiceRow, PartyType, SettlementRow } from "./types"

export const invoiceKey = (row: Pick<InvoiceRow, "invoice_type" | "invoice_number">) =>
    `${row.invoice_type}|${row.invoice_number}`

export const settlementKey = (row: Pick<SettlementRow, "reference_type" | "reference_name" | "reference_row">) =>
    `${row.reference_type}|${row.reference_name}|${row.reference_row ?? ""}`

/** An amount as a person types it: « 1'234.50 », « 1 234,5 ». NaN when it is not a number. */
export const parseAmount = (text: string): number => {
    const clean = text.replace(/['’\s]/g, "").replace(",", ".")
    return clean === "" ? NaN : Number(clean)
}

export const round2 = (value: number) => Math.round((value + Number.EPSILON) * 100) / 100

/** Why an amount cannot be used, or null. `available` is what the row still holds. */
export const amountProblem = (text: string, available: number): string | null => {
    const value = parseAmount(text)
    if (Number.isNaN(value) || value <= 0) return _("Enter an amount greater than zero")
    if (round2(value) > round2(available)) return _("More than what is left")
    return null
}

/** What a settlement is, for a reader: a payment, a credit note, an entry. */
export const settlementKind = (partyType: PartyType, row: SettlementRow): string => {
    if (row.reference_type === "Payment Entry") return row.is_advance ? _("Advance") : _("Payment")
    if (row.reference_type === "Journal Entry") return _("Journal Entry")
    return partyType === "Customer" ? _("Credit Note") : _("Debit Note")
}

export const includesText = (needle: string, ...fields: (string | number | null | undefined)[]) => {
    const wanted = needle.trim().toLowerCase()
    if (!wanted) return true
    return fields.some((field) => field !== null && field !== undefined && String(field).toLowerCase().includes(wanted))
}

export const byDate = <T,>(dateOf: (row: T) => string) => (a: T, b: T) => dateOf(a).localeCompare(dateOf(b))
