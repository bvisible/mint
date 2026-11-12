//// Neoffice — added file (no upstream equivalent). A line in the card of a bank line that says when vouchers that already exist
//// could match it, so that nobody books a second payment without having seen them. The list of those vouchers sits at the foot
//// of the column, under « or », below the card and its buttons: nothing in the card told that it was not empty (Daniel, 11.11).
//// It reads the same request as that list (same cache key), and shows nothing when no voucher looks like the line.
//// That request returns EVERY open voucher of the period, whatever the line: the first version counted them all and said
//// « 104 vouchers » on every line (Jérémy, 12.11). Only the vouchers that have the line's amount, or its reference, are counted:
//// the same two clues the rows of the list light up with (« Amount matches », « Complete / Partial Match »).
import { ArrowDown } from "lucide-react"
import { LinkedPayment, UnreconciledTransaction, useGetVouchersForTransaction } from "@/components/features/BankReconciliation/utils"
import _ from "@/lib/translate"

/** The id of the block of vouchers under « or » (VouchersForTransaction), where the line takes the person. */
export const VOUCHERS_ANCHOR = "bank-rec-vouchers"

/** A reference shorter than this would be « found » in almost any description, so a partial match needs at least this many characters. */
const MIN_PARTIAL_REFERENCE_LENGTH = 5

/** Whether an open voucher has the amount of the line, or its reference (in full, or partly when the reference is long enough). */
export const voucherLooksLikeLine = (voucher: LinkedPayment, transaction: UnreconciledTransaction): boolean => {
    const lineAmount = transaction.unallocated_amount ?? transaction.deposit ?? transaction.withdrawal ?? 0
    if (lineAmount && Math.abs((voucher.paid_amount ?? 0) - lineAmount) < 0.005) return true

    const reference = (voucher.reference_no ?? "").trim()
    if (!reference) return false
    const texts = [transaction.reference_number, transaction.description].filter(Boolean) as string[]
    if (texts.some((text) => text === reference)) return true
    return reference.length >= MIN_PARTIAL_REFERENCE_LENGTH && texts.some((text) => text.includes(reference))
}

const MatchingVouchersHint = ({ transaction }: { transaction: UnreconciledTransaction }) => {
    const { data } = useGetVouchersForTransaction(transaction)
    const count = data?.message?.filter((voucher) => voucherLooksLikeLine(voucher, transaction)).length ?? 0
    if (count === 0) return null

    return (
        <button
            type="button"
            onClick={() => document.getElementById(VOUCHERS_ANCHOR)?.scrollIntoView({ behavior: "smooth", block: "start" })}
            className="flex w-full items-center justify-between gap-3 rounded-md border border-sky-200 bg-sky-50 px-2.5 py-1.5 text-left text-sm leading-snug text-sky-950 hover:bg-sky-100"
        >
            <span>
                {count === 1
                    ? _("One existing voucher has the amount or the reference of this line.")
                    : _("{0} existing vouchers have the amount or the reference of this line.", [String(count)])}
            </span>
            <span className="inline-flex shrink-0 items-center gap-1 font-medium underline underline-offset-2">
                {_("See them")}
                <ArrowDown className="size-3.5" />
            </span>
        </button>
    )
}

export default MatchingVouchersHint
