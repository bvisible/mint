//// Neoffice — added file (no upstream equivalent). A line in the card of a bank line that says when vouchers that already exist
//// could match it, so that nobody books a second payment without having seen them. The list of those vouchers sits at the foot
//// of the column, under « or », below the card and its buttons: nothing in the card told that it was not empty (Daniel, 11.11).
//// It reads the same request as that list (same cache key), and shows nothing when there is no voucher.
import { ArrowDown } from "lucide-react"
import { UnreconciledTransaction, useGetVouchersForTransaction } from "@/components/features/BankReconciliation/utils"
import _ from "@/lib/translate"

/** The id of the block of vouchers under « or » (VouchersForTransaction), where the line takes the person. */
export const VOUCHERS_ANCHOR = "bank-rec-vouchers"

const MatchingVouchersHint = ({ transaction }: { transaction: UnreconciledTransaction }) => {
    const { data } = useGetVouchersForTransaction(transaction)
    const count = data?.message?.length ?? 0
    if (count === 0) return null

    return (
        <button
            type="button"
            onClick={() => document.getElementById(VOUCHERS_ANCHOR)?.scrollIntoView({ behavior: "smooth", block: "start" })}
            className="flex w-full items-center justify-between gap-3 rounded-md border border-sky-200 bg-sky-50 px-2.5 py-1.5 text-left text-sm leading-snug text-sky-950 hover:bg-sky-100"
        >
            <span>
                {count === 1
                    ? _("One existing voucher could match this line.")
                    : _("{0} existing vouchers could match this line.", [String(count)])}
            </span>
            <span className="inline-flex shrink-0 items-center gap-1 font-medium underline underline-offset-2">
                {_("See them")}
                <ArrowDown className="size-3.5" />
            </span>
        </button>
    )
}

export default MatchingVouchersHint
