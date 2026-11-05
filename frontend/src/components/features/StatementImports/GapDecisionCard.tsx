//// Neoffice — added file (no upstream equivalent). What a person decides for a bank line whose invoice the import
//// recognised but whose sum does not settle it: the verdict in words, and the choice. The import announces, this
//// decides; the verdict is worked out now by the server, the same function the import uses.
import { useFrappeGetCall, useFrappePostCall, useSWRConfig } from "frappe-react-sdk"
import { AlertCircle } from "lucide-react"
import NoraOrb from "@/components/common/NoraOrb"
import { useSetAtom } from "jotai"
import { useEffect, useRef, useState } from "react"
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
import type { GapDecision, RuleMode } from "./types"
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

    // What the person is trying: another account for the gap, and, for a short payment, what becomes of the rest: left
    // open, passed as a gap, or closed by a credit note. The server answers with what would be written (VAT included)
    // so that they see it before confirming.
    const [account, setAccount] = useState<string | null>(null)
    const [mode, setMode] = useState<"open" | "credit" | "gap">("open")
    const settle = mode === "gap"
    const credit = mode === "credit"
    // the account of a credit note is not the account of a gap: a new mode starts from the default of its own
    const choose = (next: "open" | "credit" | "gap") => {
        setMode(next)
        setAccount(null)
    }

    const { data } = useFrappeGetCall<{ message: GapDecision | null }>(
        `${API}.get_gap_decision`,
        { bank_transaction: transaction.name, account: account ?? undefined, settle_in_full: settle ? 1 : 0, credit_note: credit ? 1 : 0 },
        ["statement-imports", "decision", transaction.name, account ?? "", mode],
        { revalidateOnFocus: false, keepPreviousData: true },
    )
    const { call: decide, loading, error } = useFrappePostCall<{ message: { payment_entry: string | null, credit_note: string | null } }>(`${API}.decide_gap`)
    const { call: setRule, loading: ruleLoading, error: ruleError } = useFrappePostCall(`${API}.set_gap_rule`)

    const decision = data?.message

    // What the customer's rule says to do with a payment like this one, or the draft it had prepared, is chosen at the
    // start; after that the person's own choice is not touched again.
    const preselected = useRef(false)
    useEffect(() => {
        if (!decision || preselected.current) return
        const wanted = decision.draft ? "credit" : decision.rule_proposal === "credit_note" ? "credit" : decision.rule_proposal === "gap" ? "gap" : null
        if (wanted) {
            preselected.current = true
            setMode(wanted)
        }
    }, [decision])

    if (!decision) return null

    const refresh = () => mutate((key) => Array.isArray(key) && key[0] === "statement-imports")

    const onDecide = (choice: "passed_gap" | "left_open") => {
        decide({ bank_transaction: transaction.name, decision: choice, account: account ?? undefined, settle_in_full: settle ? 1 : 0, credit_note: credit ? 1 : 0 }).then(() => {
            refresh()
            if (choice === "passed_gap") {
                toast.success(credit ? _("Credit note made, invoice settled and bank line reconciled") : _("Gap passed and bank line reconciled"), {
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
    const note = decision.credit_note
    const habit = decision.history
    const passLabel = isPartial
        ? (credit ? _("Create the credit note and reconcile") : settle ? _("Settle the invoice and pass the gap") : _("Record the partial payment"))
        : _("Pass the gap and reconcile")
    const showAccount = decision.account_editable && (!isPartial || settle || credit)
    const rule = decision.rule
    const draft = decision.draft
    const onRule = (level: RuleMode) => {
        setRule({ bank_transaction: transaction.name, mode: level, action: settle ? "gap" : "credit_note", account: account ?? undefined })
            .then(() => refresh())
    }
    const levelAvailable = (level: RuleMode) =>
        level !== "automatic" || (rule?.exists ? !!rule.can_automatic : (habit?.closed_by_credit ?? 0) >= (rule?.auto_after ?? 3))
    const modeButton = (value: "open" | "credit" | "gap", label: string) => (
        <Button key={value} size="sm" variant={mode === value ? "default" : "outline"} onClick={() => choose(value)}>{label}</Button>
    )

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
                        <td className="pt-1 font-medium">{verdict.kind === "partial" ? _("Stays open") : _("Gap Amount")}</td>
                        <td className="pt-1 text-right font-mono font-medium tabular-nums">{formatCurrency(Math.abs(verdict.gap), verdict.currency)}</td>
                    </tr>
                </tbody>
            </table>
            {draft && (
                <div className="flex flex-wrap items-center gap-3 rounded-md border border-amber-200 bg-white/60 p-2.5">
                    <span className="text-sm leading-snug">
                        {_("A credit note of {0} was prepared as a draft: {1}.", [formatCurrency(draft.total, verdict.currency), draft.name])}
                    </span>
                    <a className="text-sm underline underline-offset-2" href={documentHref("Sales Invoice", draft.name)} target="_blank" rel="noopener noreferrer">{_("Open the draft")}</a>
                </div>
            )}
            {isPartial && habit?.proposal === "credit_note" && note && !draft && (
                <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-white/60 p-2.5">
                    <NoraOrb size={22} className="mt-0.5 shrink-0" />
                    <div className="flex min-w-0 flex-col gap-1.5">
                        <span className="text-sm leading-snug">
                            {_("This customer pays {0} % of its invoices: {1} of its last {2} paid invoices were paid at that share, and {3} of them ended with the rest as a credit note.", [String(habit.share), String(habit.same_share), String(habit.considered), String(habit.closed_by_credit)])}
                        </span>
                        {!credit && <Button size="sm" className="w-fit" onClick={() => choose("credit")}>{_("Apply the proposal")}</Button>}
                    </div>
                </div>
            )}
            {isPartial && decision.can_settle && (
                <div className="flex flex-wrap gap-2">
                    {modeButton("open", _("Keep the rest open"))}
                    {note && modeButton("credit", _("Create the credit note of the balance"))}
                    {modeButton("gap", _("Pass the rest as a gap"))}
                </div>
            )}
            {showAccount && (
                <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium">{credit ? _("Account of the credit note") : _("Account for the gap")}</span>
                    <div className="max-w-sm">
                        <AccountsDropdown
                            root_type={credit ? ["Income"] : ["Income", "Expense"]}
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
            {credit && note && (
                <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium">{_("Credit note that will be made")}</span>
                    <div className="flex justify-between gap-4 text-sm">
                        <span className="text-muted-foreground">{_("Item")}</span>
                        <span className="min-w-0 truncate">{note.item}</span>
                    </div>
                    {note.net !== null && (
                        <div className="flex justify-between gap-4 text-sm">
                            <span className="text-muted-foreground">{_("Net")}</span>
                            <span className="font-mono tabular-nums">{formatCurrency(note.net, verdict.currency)}</span>
                        </div>
                    )}
                    {note.tax !== null && note.tax > 0 && (
                        <div className="flex justify-between gap-4 text-sm">
                            <span className="text-muted-foreground">{_("VAT")}</span>
                            <span className="font-mono tabular-nums">{formatCurrency(note.tax, verdict.currency)}</span>
                        </div>
                    )}
                    <div className="flex justify-between gap-4 border-t border-amber-200 pt-1 text-sm font-medium">
                        <span>{_("Total of the credit note")}</span>
                        <span className="font-mono tabular-nums">{formatCurrency(note.total, verdict.currency)}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">
                        {note.source === "history"
                            ? _("Made like the credit notes this customer already has ({0}), without link to the invoice.", [String(note.times)])
                            : _("This customer has no credit note yet: the account of the company is used, without link to the invoice.")}
                    </span>
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
            {isPartial && rule && (credit || settle || rule.exists) && (
                <div className="flex flex-col gap-1.5 rounded-md border border-amber-200 bg-white/60 p-2.5">
                    <span className="text-sm font-medium">{_("Rule for this customer")}</span>
                    <div className="flex flex-wrap gap-1.5">
                        {(["suggest", "draft", "automatic"] as RuleMode[]).map((level) => (
                            <Button
                                key={level}
                                size="sm"
                                variant={rule.exists && rule.mode === level ? "default" : "outline"}
                                disabled={ruleLoading || !levelAvailable(level)}
                                onClick={() => onRule(level)}
                            >
                                {level === "suggest" ? _("Propose it to me") : level === "draft" ? _("Prepare it as a draft") : _("Make it by itself")}
                            </Button>
                        ))}
                    </div>
                    <span className="text-xs text-muted-foreground">
                        {rule.exists
                            ? _("Applies to a payment at about {0} % of the invoice. Confirmed {1} times by a person: by itself from {2}.", [String(rule.share ?? 0), String(rule.confirmed_times ?? 0), String(rule.auto_after)])
                            : _("No rule yet: choosing a level makes one from this payment. By itself is available after {0} confirmations by a person.", [String(rule.auto_after)])}
                    </span>
                    {ruleError && <ErrorBanner error={ruleError} />}
                </div>
            )}
            {decision.blocker && <p className="text-sm font-medium text-destructive">{decision.blocker}</p>}
            {error && <ErrorBanner error={error} />}
            <div className="flex flex-wrap items-center gap-3">
                {decision.can_pass && (
                    <Button disabled={loading} onClick={() => onDecide("passed_gap")}>{draft && credit ? _("Validate the draft and reconcile") : passLabel}</Button>
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
