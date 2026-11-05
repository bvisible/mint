//// Neoffice — added file (no upstream equivalent). The bank lines of an account that came from an import with a gap
//// nobody has decided yet: the filter « To decide » of the bank reconciliation and the chip on their rows.
import { useAtomValue } from "jotai"
import { useFrappeGetCall } from "frappe-react-sdk"
import { useMemo } from "react"
import { bankRecDateAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import { API } from "./api"
import type { LineToDecide } from "./types"

export const useLinesToDecide = (bankAccount?: string) => {
    // the period the reconciliation shows: the count of « To decide » is the count of what the list can show
    const dates = useAtomValue(bankRecDateAtom)
    const { data } = useFrappeGetCall<{ message: LineToDecide[] }>(
        `${API}.get_lines_to_decide`,
        { bank_account: bankAccount, from_date: dates?.fromDate, to_date: dates?.toDate },
        bankAccount ? ["statement-imports", "to-decide", bankAccount, dates?.fromDate, dates?.toDate] : null,
        { revalidateOnFocus: false },
    )
    const lines = useMemo(() => data?.message ?? [], [data])
    const byBankLine = useMemo(() => new Map(lines.map((line) => [line.bank_transaction, line])), [lines])
    return { lines, byBankLine }
}
