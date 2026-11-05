//// Neoffice — added file (no upstream equivalent). What a person decides for a bank line whose invoice the import
//// recognised but whose sum does not settle it: the verdict in words, and the choice. The import announces, this
//// decides; the verdict is worked out now by the server, the same function the import uses.
import { useFrappeGetCall, useFrappePostCall, useSWRConfig } from "frappe-react-sdk"
import { AlertCircle } from "lucide-react"
import { useSetAtom } from "jotai"
import { useState } from "react"
import { toast } from "sonner"
import { bankRecRecordPaymentModalAtom, bankRecUnreconcileModalAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import { UnreconciledTransaction, useRefreshUnreconciledTransactions } from "@/components/features/BankReconciliation/utils"
import AccountsDropdown from "@/components/common/AccountsDropdown"
import { Button } from "@/components/ui/button"
import ErrorBanner from "@/components/ui/error-banner"
import { formatDate } from "@/lib/date"
import { formatCurrency } from "@/lib/numbers"
import _ from "@/lib/translate"
import { API } from "./api"
import type { GapDecision } from "./types"
import { documentHref } from "./utils"

/** The verdict, in a sentence a person can check against the figures under it. */
const sentence = (decision: GapDecision): string => {
    const { verdict, invoice, party } = decision
    const who = party ?? ""
    const owed = formatCurrency(verdict.outstanding, verdict.currency)
    const paid = formatCurrency(verdict.amount, verdict.currency)
    const gap = formatCurrency(Math.abs(verdict.gap), verdict.currency)
    const until = decision.discount_date ? formatDate(decision.discount_date, "Do MMM YYYY") : ""
    switch (verdict.kind) {
        case "rounding":
            return _("Invoice {0} of {1} settles at {2}. You paid {3}, that is {4} less: a rounding.", [invoice, who, owed, paid, gap])
        case "early_discount":
            return decision.discount_percent
                ? _("Invoice {0} of {1} settles at {2}. You paid {3}, that is {4} less: the early payment discount of {5} % that its terms grant until {6}.", [invoice, who, owed, paid, gap, String(decision.discount_percent), until])
                : _("Invoice {0} of {1} settles at {2}. You paid {3}, that is {4} less: the early payment discount that its terms grant.", [invoice, who, owed, paid, gap])
        case "accepted_rebate":
            return _("Invoice {0} of {1} settles at {2}. You paid {3}, that is {4} less: a rebate within what the company accepts.", [invoice, who, owed, paid, gap])
        case "partial":
            return _("Invoice {0} of {1} still owes {2}. You paid {3}: a partial payment, what came in is booked and {4} stays open.", [invoice, who, owed, paid, gap])
        case "overpaid":
            return _("Invoice {0} of {1} settles at {2}. You paid {3}, that is {4} more than is owed: that is never passed by itself.", [invoice, who, owed, paid, gap])
        default:
            return decision.blocker
    }
}

const GapDecisionCard = ({ transaction }: { transaction: UnreconciledTransaction }) => {
    const { mutate } = useSWRConfig()
    const onReconcile = useRefreshUnreconciledTransactions()
    const setRecordPaymentOpen = useSetAtom(bankRecRecordPaymentModalAtom)
    const setUnreconcile = useSetAtom(bankRecUnreconcileModalAtom)

    // What the person is trying: another account for the gap, or a short payment settled in full. The server answers
    // with the rows the gap would be booked as, so that they see them (VAT included) before confirming.
    const [account, setAccount] = useState<string | null>(null)
    const [settle, setSettle] = useState(false)

    const { data } = useFrappeGetCall<{ message: GapDecision | null }>(
        `${API}.get_gap_decision`,
        { bank_transaction: transaction.name, account: account ?? undefined, settle_in_full: settle ? 1 : 0 },
        ["statement-imports", "decision", transaction.name, account ?? "", settle],
        { revalidateOnFocus: false, keepPreviousData: true },
    )
    const { call: decide, loading, error } = useFrappePostCall<{ message: { payment_entry: string | null } }>(`${API}.decide_gap`)

    const decision = data?.message
    if (!decision) return null

    const refresh = () => mutate((key) => Array.isArray(key) && key[0] === "statement-imports")

    const onDecide = (choice: "passed_gap" | "left_open") => {
        decide({ bank_transaction: transaction.name, decision: choice, account: account ?? undefined, settle_in_full: settle ? 1 : 0 }).then(() => {
            refresh()
            if (choice === "passed_gap") {
                toast.success(_("Gap passed and bank line reconciled"), {
                    duration: 4000,
                    closeButton: true,
                    action: { label: _("Undo"), onClick: () => setUnreconcile(transaction.name) },
                })
                onReconcile(transaction)
            } else {
                toast.success(_("Left open"))
            }
        })
    }

    const { verdict } = decision
    // formatted apart: a string literal inside the arguments of _() is read by the extractor as its CONTEXT
    const decidedDay = decision.decided_on ? formatDate(decision.decided_on, "Do MMM YYYY") : ""
    const isPartial = verdict.kind === "partial"
    const passLabel = isPartial
        ? (settle ? _("Settle the invoice and pass the gap") : _("Record the partial payment"))
        : _("Pass the gap and reconcile")
    const showAccount = decision.account_editable && (!isPartial || settle)

    return (
        <div className="flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-950">
            <div className="flex items-center gap-2">
                <AlertCircle className="size-5 text-amber-700" />
                <span className="text-lg font-medium">{_("A gap to decide")}</span>
            </div>
            <p className="text-sm leading-relaxed">{sentence(decision)}</p>
            <table className="w-full max-w-sm text-sm">
                <tbody>
                    <tr>
                        <td className="py-0.5 text-muted-foreground">{_("Still owed on the invoice")}</td>
                        <td className="py-0.5 text-right font-mono tabular-nums">{formatCurrency(verdict.outstanding, verdict.currency)}</td>
                    </tr>
                    <tr>
                        <td className="py-0.5 text-muted-foreground">{_("Paid to the bank")}</td>
                        <td className="py-0.5 text-right font-mono tabular-nums">{formatCurrency(verdict.amount, verdict.currency)}</td>
                    </tr>
                    <tr className="border-t border-amber-200">
                        <td className="pt-1 font-medium">{verdict.kind === "partial" ? _("Stays open") : _("Gap")}</td>
                        <td className="pt-1 text-right font-mono font-medium tabular-nums">{formatCurrency(Math.abs(verdict.gap), verdict.currency)}</td>
                    </tr>
                </tbody>
            </table>
            {isPartial && decision.can_settle && (
                <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant={settle ? "outline" : "default"} onClick={() => setSettle(false)}>{_("Keep the rest open")}</Button>
                    <Button size="sm" variant={settle ? "default" : "outline"} onClick={() => setSettle(true)}>{_("Pass the rest as a gap")}</Button>
                </div>
            )}
            {showAccount && (
                <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium">{_("Account for the gap")}</span>
                    <div className="max-w-sm">
                        <AccountsDropdown
                            root_type={["Income", "Expense"]}
                            company={transaction.company}
                            value={account ?? decision.account ?? undefined}
                            onChange={(value) => setAccount(value || null)}
                        />
                    </div>
                    {account && account !== decision.default_account && (
                        <button type="button" className="w-fit text-xs underline underline-offset-2" onClick={() => setAccount(null)}>{_("Back to the company's account")}</button>
                    )}
                </div>
            )}
            {decision.deductions.length > 0 && (
                <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium">{_("Booked as")}</span>
                    {decision.deductions.map((row, index) => (
                        <div key={`${row.account}-${index}`} className="flex justify-between gap-4 text-sm">
                            <span className="min-w-0 truncate text-muted-foreground">{row.account}</span>
                            <span className="font-mono tabular-nums">{formatCurrency(Math.abs(row.amount), verdict.currency)}</span>
                        </div>
                    ))}
                    {decision.deductions.length > 1 && (
                        <span className="text-xs text-muted-foreground">{_("The VAT is cut from the account, as in the payment entry.")}</span>
                    )}
                </div>
            )}
            {decision.blocker && <p className="text-sm font-medium text-destructive">{decision.blocker}</p>}
            {error && <ErrorBanner error={error} />}
            <div className="flex flex-wrap items-center gap-3">
                {decision.can_pass && (
                    <Button disabled={loading} onClick={() => onDecide("passed_gap")}>{passLabel}</Button>
                )}
                {decision.decision !== "left_open" && (
                    <Button variant="outline" disabled={loading} onClick={() => onDecide("left_open")}>{_("Leave open")}</Button>
                )}
                <Button variant="link" className="px-0" onClick={() => setRecordPaymentOpen(true)}>{_("Record another way")}</Button>
                <a className="text-sm underline underline-offset-2" href={documentHref(decision.invoice_type, decision.invoice)}>{decision.invoice}</a>
            </div>
            <p className="text-xs text-muted-foreground">
                {decision.decision === "left_open"
                    ? _("Left open by {0} on {1}.", [decision.decided_by ?? "", decidedDay])
                    : _("Your name and the date are noted on the line of the import.")}
            </p>
        </div>
    )
}

export default GapDecisionCard
