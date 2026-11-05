//// Neoffice — added file (no upstream equivalent). The bank lines of an account that came from an import with a gap
//// nobody has decided yet: the filter « To decide » of the bank reconciliation and the chip on their rows.
import { useFrappeGetCall } from "frappe-react-sdk"
import { useMemo } from "react"
import { API } from "./api"
import type { LineToDecide } from "./types"

export const useLinesToDecide = (bankAccount?: string) => {
    const { data } = useFrappeGetCall<{ message: LineToDecide[] }>(
        `${API}.get_lines_to_decide`,
        { bank_account: bankAccount },
        bankAccount ? ["statement-imports", "to-decide", bankAccount] : null,
        { revalidateOnFocus: false },
    )
    const lines = useMemo(() => data?.message ?? [], [data])
    const byBankLine = useMemo(() => new Map(lines.map((line) => [line.bank_transaction, line])), [lines])
    return { lines, byBankLine }
}
