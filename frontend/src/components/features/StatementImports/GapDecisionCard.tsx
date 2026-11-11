//// Neoffice — added file (no upstream equivalent). What a person decides for a bank line whose invoice the import
//// recognised but whose sum does not settle it: the verdict in words, and the choice. The import announces, this
//// decides; the verdict is worked out now by the server, the same function the import uses.
//// The card is one column in the panel of the line: a headline, a sentence, what to choose, then the buttons (the main
//// one in ink, then « Reconcile manually »). Nothing is explained under a button: the explanation is behind its info
//// icon (InfoHint). There is no « leave it open » button: a person who does nothing leaves the line open anyway.
import { useFrappeGetCall, useFrappePostCall, useSWRConfig } from "frappe-react-sdk"
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react"
import NoraOrb from "@/components/common/NoraOrb"
import { useSetAtom } from "jotai"
import { useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import { bankRecRecordPaymentModalAtom, bankRecRecordPaymentPrefillAtom, bankRecUnreconcileModalAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import { UnreconciledTransaction, useRefreshUnreconciledTransactions } from "@/components/features/BankReconciliation/utils"
import AccountsDropdown from "@/components/common/AccountsDropdown"
import { Button } from "@/components/ui/button"
import ErrorBanner from "@/components/ui/error-banner"
import { cn } from "@/lib/utils"
import { formatDate } from "@/lib/date"
import { formatCurrency } from "@/lib/numbers"
import _ from "@/lib/translate"
import { API } from "./api"
import InfoHint from "./InfoHint"
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
        case "dunning_fee":
            return _("Invoice {0} of {1} settles at {2}. You paid {3}, that is {4} more: the fee of the dunning {5}, booked on its account and settling it.", [invoice, who, owed, paid, gap, decision.dunnings.map((dunning) => dunning.name).join(", ")])
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
    const setRecordPaymentPrefill = useSetAtom(bankRecRecordPaymentPrefillAtom)
    const setUnreconcile = useSetAtom(bankRecUnreconcileModalAtom)

    // What the person is trying: another account for the gap, and, for a short payment, what becomes of the rest: left
    // open, passed as a gap, or closed by a credit note. The server answers with what would be written (VAT included)
    // so that they see it before confirming.
    const [account, setAccount] = useState<string | null>(null)
    const [mode, setMode] = useState<"open" | "credit" | "gap">("open")
    // what is folded away until asked for: the rows that will be booked, the rule for this customer
    const [showBooked, setShowBooked] = useState(false)
    const [showRule, setShowRule] = useState(false)
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

    const onDecide = () => {
        decide({ bank_transaction: transaction.name, decision: "passed_gap", account: account ?? undefined, settle_in_full: settle ? 1 : 0, credit_note: credit ? 1 : 0 }).then(() => {
            refresh()
            toast.success(credit ? _("Credit note made, invoice settled and bank line reconciled") : _("Gap passed and bank line reconciled"), {
                duration: 4000,
                closeButton: true,
                action: { label: _("Undo"), onClick: () => setUnreconcile(transaction.name) },
            })
            onReconcile(transaction)
        })
    }

    const { verdict } = decision
    // formatted apart: a string literal inside the arguments of _() is read by the extractor as its CONTEXT
    const decidedDay = decision.decided_on ? formatDate(decision.decided_on, "Do MMM YYYY") : ""
    const lineDay = transaction.date ? formatDate(transaction.date, "Do MMM YYYY") : ""
    const isPartial = verdict.kind === "partial"
    const isSale = decision.invoice_type === "Sales Invoice"
    const confirming = !!verdict.needs_confirmation
    const note = decision.credit_note
    const habit = decision.history
    const gapText = formatCurrency(Math.abs(verdict.gap), verdict.currency)
    const showAccount = decision.account_editable && (!isPartial || settle || credit)
    // the company has not said where a gap of this kind of invoice goes: the card says so, and where to say it
    const missingSetting = showAccount && !credit && !decision.default_account
    const settingsHref = transaction.company ? `/app/neoffice-company-settings/${encodeURIComponent(transaction.company)}` : ""
    const rule = decision.rule
    const draft = decision.draft
    const onRule = (level: RuleMode) => {
        setRule({ bank_transaction: transaction.name, mode: level, action: settle ? "gap" : "credit_note", account: account ?? undefined })
            .then(() => refresh())
    }
    const levelAvailable = (level: RuleMode) =>
        level !== "automatic" || (rule?.exists ? !!rule.can_automatic : (habit?.closed_by_credit ?? 0) >= (rule?.auto_after ?? 3))

    const headline = isPartial
        ? _("Paid {0} out of {1}", [formatCurrency(verdict.amount, verdict.currency), formatCurrency(verdict.outstanding, verdict.currency)])
        : _("A gap of {0} on invoice {1}", [gapText, decision.invoice])

    const passLabel = draft && credit
        ? _("Validate the draft and reconcile")
        : isPartial
            ? (credit ? _("Create the credit note and reconcile") : settle ? _("Settle the invoice and pass the gap") : _("Record the partial payment"))
            : verdict.kind === "dunning_fee"
                ? _("Book the dunning fee and reconcile")
                : confirming ? _("Confirm the rebate and reconcile") : _("Settle the invoice and reconcile")

    // what the main button does, said once behind its icon (the reason it is off, when it is)
    const passHint = !decision.can_pass && decision.blocker
        ? decision.blocker
        : isPartial
            ? (credit
                ? _("Makes a credit note of {0} and settles the invoice. The payment received is booked as it is.", [gapText])
                : settle
                    ? _("Settles the invoice: the payment is booked for what came in and {0} goes to the account chosen above.", [gapText])
                    : _("Books the payment received. The invoice stays due for {0}.", [gapText]))
            : verdict.kind === "dunning_fee"
                ? _("The fee of the dunning is booked on its own account and settles it.")
                : _("Settles the invoice: the payment is booked for what came in and the gap of {0} goes to the account chosen above.", [gapText])

    const tile = (value: "open" | "credit" | "gap", label: string, hint: string, proposed: boolean) => (
        <div key={value} className="flex items-center gap-2">
            <button
                type="button"
                role="radio"
                aria-checked={mode === value}
                onClick={() => choose(value)}
                className={cn(
                    "flex min-h-10 flex-1 items-center gap-3 rounded-lg border bg-white px-3 py-2 text-left text-sm font-medium",
                    mode === value ? "border-2 border-foreground px-[11px]" : "hover:bg-black/[0.03]",
                )}
            >
                <span className={cn("size-4 shrink-0 rounded-full border-2", mode === value ? "border-foreground bg-[radial-gradient(circle,currentColor_0_4px,white_4.5px)]" : "border-muted-foreground/50")} />
                <span className="min-w-0 flex-1">{label}</span>
                {proposed && <span className="shrink-0 rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-800">{_("Proposed")}</span>}
            </button>
            <InfoHint>{hint}</InfoHint>
        </div>
    )

    return (
        <div className="flex flex-col gap-3 rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
                    <span className="size-1.5 rounded-full bg-current" />
                    {confirming ? _("To confirm") : _("To decide")}
                </span>
                <span className="text-xs text-muted-foreground">{lineDay}</span>
            </div>
            <div className="flex flex-col gap-1">
                <span className="text-xl leading-tight font-medium">{headline}</span>
                <p className="text-sm leading-relaxed text-muted-foreground">{sentence(decision)}</p>
            </div>
            {confirming && (
                <p className="rounded-md border border-amber-200 bg-amber-50 p-2.5 text-sm leading-snug text-amber-950">
                    {verdict.confirm_above
                        ? _("This rebate is above {0}: the import does not pass it by itself, you confirm it.", [formatCurrency(verdict.confirm_above, verdict.currency)])
                        : _("The company has not named an amount up to which a rebate is passed by itself: you confirm it.")}
                </p>
            )}
            {draft && (
                <div className="flex flex-wrap items-center gap-3 rounded-md border border-orange-200 bg-orange-50 p-2.5">
                    <span className="text-sm leading-snug">
                        {_("A credit note of {0} was prepared as a draft: {1}.", [formatCurrency(draft.total, verdict.currency), draft.name])}
                    </span>
                    <a className="text-sm underline underline-offset-2" href={documentHref("Sales Invoice", draft.name)} target="_blank" rel="noopener noreferrer">{_("Open the draft")}</a>
                </div>
            )}
            {isPartial && habit?.proposal === "credit_note" && note && !draft && (
                <div className="flex items-start gap-2 rounded-md border border-orange-200 bg-orange-50 p-2.5">
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
                <div className="flex flex-col gap-2" role="radiogroup">
                    <span className="text-base font-medium">{_("What becomes of the remaining {0}?", [gapText])}</span>
                    {tile("open", _("Keep the rest open"), _("The invoice stays due for {0}. Only the payment received is booked.", [gapText]), false)}
                    {note && tile(
                        "credit",
                        _("Create the credit note of the balance"),
                        note.source === "history"
                            ? _("The customer owes nothing more. Made like the credit notes this customer already has ({0}), without link to the invoice.", [String(note.times)])
                            : _("The customer owes nothing more. This customer has no credit note yet: the account of the company is used, without link to the invoice."),
                        habit?.proposal === "credit_note" || decision.rule_proposal === "credit_note",
                    )}
                    {tile("gap", _("Pass the rest as a gap"), _("The invoice is settled and {0} goes to the account you choose below: it is more than the company accepts by itself, so you decide.", [gapText]), decision.rule_proposal === "gap")}
                </div>
            )}
            {credit && note && (
                <div className="flex flex-wrap items-baseline gap-x-4 gap-y-0.5 text-sm">
                    {note.net !== null && <span><span className="text-muted-foreground">{_("Net")}</span> <span className="font-mono tabular-nums">{formatCurrency(note.net, verdict.currency)}</span></span>}
                    {note.tax !== null && note.tax > 0 && <span><span className="text-muted-foreground">{_("VAT")}</span> <span className="font-mono tabular-nums">{formatCurrency(note.tax, verdict.currency)}</span></span>}
                    <span className="font-medium">{_("Total of the credit note")} <span className="font-mono tabular-nums">{formatCurrency(note.total, verdict.currency)}</span></span>
                </div>
            )}
            {missingSetting && (
                <div className="flex flex-col gap-2 rounded-md border border-amber-200 bg-amber-50 p-2.5 text-amber-950">
                    <span className="text-sm leading-snug">
                        <b>{isSale ? _("The company has not said yet where to pass the gaps on sales.") : _("The company has not said yet where to pass the gaps on purchases.")}</b>{" "}
                        {_("Until it does, each gap is decided one by one: choose an account for this line below.")}
                    </span>
                    {settingsHref && (
                        <div className="flex items-center gap-2">
                            <Button asChild variant="outline" className="h-10 flex-1">
                                <a href={settingsHref} target="_blank" rel="noopener noreferrer">{_("Fill in the settings")} <ExternalLink className="size-4" /></a>
                            </Button>
                            <InfoHint>{_("Opens the settings of the company in a new tab: this screen stays open. The gap accounts are in the section Payment Gaps.")}</InfoHint>
                        </div>
                    )}
                </div>
            )}
            {showAccount && (
                <div className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium">{credit ? _("Account of the credit note") : _("Account for the gap")}</span>
                    <AccountsDropdown
                        root_type={credit || isSale ? ["Income"] : ["Expense"]}
                        company={transaction.company}
                        value={account ?? decision.account ?? undefined}
                        onChange={(value) => setAccount(value || null)}
                    />
                    {account && account !== decision.default_account && decision.default_account && (
                        <button type="button" className="w-fit text-xs underline underline-offset-2" onClick={() => setAccount(null)}>{_("Back to the company's account")}</button>
                    )}
                </div>
            )}
            {decision.deductions.length > 0 && (
                <div className="flex flex-col gap-1">
                    <button type="button" className="flex w-fit items-center gap-1 text-sm font-medium" onClick={() => setShowBooked(!showBooked)}>
                        {showBooked ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                        {_("Show what will be booked")}
                    </button>
                    {showBooked && (
                        <>
                            {decision.deductions.map((row, index) => (
                                <div key={`${row.account}-${index}`} className="flex justify-between gap-4 text-sm">
                                    <span className="min-w-0 truncate text-muted-foreground">{row.account}</span>
                                    <span className="font-mono tabular-nums">{formatCurrency(Math.abs(row.amount), verdict.currency)}</span>
                                </div>
                            ))}
                            {decision.deductions.length > 1 && (
                                <span className="text-xs text-muted-foreground">{_("The VAT is cut from the account, as in the payment entry.")}</span>
                            )}
                        </>
                    )}
                </div>
            )}
            {isPartial && rule && (credit || settle || rule.exists) && (
                <div className="flex flex-col gap-1.5">
                    <button type="button" className="flex w-fit items-center gap-1 text-sm font-medium" onClick={() => setShowRule(!showRule)}>
                        {showRule ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                        {_("Remember this choice for this customer")}
                    </button>
                    {showRule && (
                        <div className="flex flex-col gap-1.5 rounded-md border bg-white p-2.5">
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
                </div>
            )}
            {/* the note about the missing setting already says it, and the main button is off until an account is chosen */}
            {decision.blocker && !(missingSetting && !account) && <p className="text-sm font-medium text-destructive">{decision.blocker}</p>}
            {error && <ErrorBanner error={error} />}
            {decision.decision === "left_open" && (
                <p className="text-xs text-muted-foreground">{_("Left open by {0} on {1}.", [decision.decided_by ?? "", decidedDay])}</p>
            )}
            <div className="flex flex-col gap-2 pt-1">
                <div className="flex items-center gap-2">
                    <Button className="h-10 flex-1" disabled={loading || !decision.can_pass} onClick={onDecide}>{passLabel}</Button>
                    <InfoHint>
                        <span>{passHint}</span>
                        <span className="text-xs text-muted-foreground">{_("Your name and the date are noted on the line of the import.")}</span>
                    </InfoHint>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" className="h-10 flex-1" disabled={loading} onClick={() => {
                        // the form opens on the customer (or supplier) of the invoice, not on whoever the bank wrote
                        if (decision.party_id) setRecordPaymentPrefill({ party_type: decision.party_doctype, party: decision.party_id })
                        setRecordPaymentOpen(true)
                    }}>{_("Reconcile manually")}</Button>
                    <InfoHint>{_("Opens the full payment form, pointed at the customer (or supplier) of this invoice. Use it when none of the choices fits.")}</InfoHint>
                </div>
                <a className="w-fit text-sm underline underline-offset-2" href={documentHref(decision.invoice_type, decision.invoice)}>{decision.invoice}</a>
            </div>
        </div>
    )
}

export default GapDecisionCard
