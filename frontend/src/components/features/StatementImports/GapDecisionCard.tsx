//// Neoffice — added file (no upstream equivalent). What a person decides for a bank line whose invoice the import
//// recognised but whose sum does not settle it: the verdict in words, and the choice. The import announces, this
//// decides; the verdict is worked out now by the server, the same function the import uses.
//// The card is one column in the panel of the line: a headline, a sentence, what to choose, then the buttons (the main
//// one in ink, then « Reconcile manually »), which stay at the foot of the visible panel while the rest of the card
//// scrolls (they were below the fold and tied to the list under the card, Daniel, 11.11). Nothing is explained under a
//// button: the explanation is behind its lightbulb (InfoHint), with the page of the manual that speaks of it. There is no
//// « leave it open » button: a person who does nothing leaves the line open anyway.
//// The words are those of the books, not of the code: a difference, a credit note, a loss on customers, a discount.
//// A short payment of a sale has four choices (12.11, Jérémy and Daniel): leave the balance to pay (a credit note will be made and matched
//// later, goods back in stock), take it off the turnover (one entry on the sales accounts of the invoice, with its VAT), make a credit
//// note (one line on the article the person chooses, filled in from the habit) or book it as a loss on the customer (the write-off account). The
//// choices sit in two columns and so does what will be booked, when the panel is wide (a container query), one column otherwise.
//// More came in than is owed (an overpayment): two choices as for a short payment, the first proposed. Keep the surplus for a
//// next invoice (the payment is booked in full, the invoice settled, the surplus stays on the payment to be matched later), or
//// book it as a difference on an account, the way the fee of a dunning is (Jérémy, Daniel, 12.11: the card offered nothing).
import { useFrappeGetCall, useFrappePostCall, useSWRConfig } from "frappe-react-sdk"
import { ChevronDown, ChevronRight, ExternalLink } from "lucide-react"
import NoraOrb from "@/components/common/NoraOrb"
import { useSetAtom } from "jotai"
import { useEffect, useRef, useState, type ReactNode } from "react"
import { toast } from "sonner"
import { bankRecRecordPaymentModalAtom, bankRecRecordPaymentPrefillAtom, bankRecUnreconcileModalAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import { UnreconciledTransaction, useRefreshUnreconciledTransactions } from "@/components/features/BankReconciliation/utils"
import AccountsDropdown from "@/components/common/AccountsDropdown"
import LinkFieldCombobox from "@/components/common/LinkFieldCombobox"
import { Button } from "@/components/ui/button"
import ErrorBanner from "@/components/ui/error-banner"
import { cn } from "@/lib/utils"
import { formatDate } from "@/lib/date"
import { formatCurrency } from "@/lib/numbers"
import _ from "@/lib/translate"
import { API } from "./api"
import InfoHint, { MANUAL } from "./InfoHint"
import MatchingVouchersHint from "./MatchingVouchersHint"
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
            return _("Invoice {0} of {1} settles at {2}. You paid {3}, that is {4} more than is owed.", [invoice, who, owed, paid, gap])
        default:
            return decision.blocker
    }
}

/** What becomes of the rest of a short payment: nothing (it stays due), a deduction of the turnover, a credit note, a loss. */
type Mode = "open" | "deduct" | "credit" | "gap"

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
    // the article of the credit note: filled in by the server (the habit of the customer, else the one the company uses most) until the person picks another
    const [creditItem, setCreditItem] = useState<string | null>(null)
    const [mode, setMode] = useState<Mode>("open")
    // what is folded away until asked for: the rows that will be booked, the rule for this customer
    const [showBooked, setShowBooked] = useState(false)
    const [showRule, setShowRule] = useState(false)
    const settle = mode === "gap"
    const credit = mode === "credit"
    const deduct = mode === "deduct"
    // the account of a loss is not the account of anything else: a new mode starts from the default of its own
    const choose = (next: Mode) => {
        setMode(next)
        setAccount(null)
        setCreditItem(null)
    }
    // another article is sold on its own account: the account starts again from the one of the article
    const chooseArticle = (value: string) => {
        setCreditItem(value || null)
        setAccount(null)
    }

    const { data } = useFrappeGetCall<{ message: GapDecision | null }>(
        `${API}.get_gap_decision`,
        { bank_transaction: transaction.name, account: account ?? undefined, settle_in_full: settle ? 1 : 0, credit_note: credit ? 1 : 0, deduct_from_sales: deduct ? 1 : 0, credit_item: credit ? (creditItem ?? undefined) : undefined },
        ["statement-imports", "decision", transaction.name, account ?? "", mode, creditItem ?? ""],
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
        // the article the person sees (filled in or chosen) is the one the credit note is made on
        decide({ bank_transaction: transaction.name, decision: "passed_gap", account: account ?? decision.credit_note?.account ?? undefined, settle_in_full: settle ? 1 : 0, credit_note: credit ? 1 : 0, deduct_from_sales: deduct ? 1 : 0, credit_item: credit ? (creditItem ?? decision.credit_note?.item_code ?? undefined) : undefined }).then(() => {
            refresh()
            toast.success(credit ? _("Credit note made, invoice settled and bank line reconciled") : deduct ? _("Balance taken off the turnover, invoice settled and bank line reconciled") : isOverpaid && !settle ? _("Invoice settled and bank line reconciled, the surplus stays available") : _("Difference booked and bank line reconciled"), {
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
    const isOverpaid = verdict.kind === "overpaid"
    // a rebate the company accepts but asks to confirm is decided like a short payment: the same choices (12.11, Jérémy)
    const isConfirmRebate = verdict.kind === "accepted_rebate" && !!verdict.needs_confirmation
    const isSale = decision.invoice_type === "Sales Invoice"
    const confirming = !!verdict.needs_confirmation
    const note = decision.credit_note
    const habit = decision.history
    const gapText = formatCurrency(Math.abs(verdict.gap), verdict.currency)
    const owed = formatCurrency(verdict.outstanding, verdict.currency)
    // who the surplus waits for: the customer or the supplier of the invoice, by the name the card already uses
    const who = decision.party ?? (decision.invoice_type === "Sales Invoice" ? _("the customer") : _("the supplier"))
    const showAccount = decision.account_editable && ((!isPartial && !isOverpaid && !isConfirmRebate) || settle)
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
        : isOverpaid
            ? (isSale ? _("An overpayment of {0} on invoice {1}", [gapText, decision.invoice]) : _("{0} paid too much on invoice {1}", [gapText, decision.invoice]))
            : _("A difference of {0} on invoice {1}", [gapText, decision.invoice])

    const passLabel = draft && credit
        ? _("Validate the draft and reconcile")
        : isPartial
            ? (credit ? _("Create the credit note and reconcile") : deduct ? _("Take it off the turnover and reconcile") : settle ? (isSale ? _("Settle the invoice and book the loss") : _("Settle the invoice and book the difference")) : _("Record the partial payment"))
            : isConfirmRebate
                ? (credit ? _("Create the credit note and reconcile") : deduct ? _("Take it off the turnover and reconcile") : settle ? _("Confirm the rebate and reconcile") : _("Record the partial payment"))
            : isOverpaid
                ? (settle ? _("Settle the invoice and book the difference") : _("Settle the invoice and keep the surplus"))
            : verdict.kind === "dunning_fee"
                ? _("Book the dunning fee and reconcile")
                : confirming ? _("Confirm the rebate and reconcile") : _("Settle the invoice and reconcile")

    // what the main button does, said once behind its icon (the reason it is off, when it is)
    const passHint = !decision.can_pass && decision.blocker
        ? decision.blocker
        : isPartial
            ? (credit
                ? _("Makes a credit note of {0} on the article chosen above and settles the invoice. The payment received is booked as it is.", [gapText])
                : deduct
                ? _("Settles the invoice: the payment is booked for what came in and {0} is taken off the turnover, on the sales account of the invoice with its VAT.", [gapText])
                : settle
                    ? _("Settles the invoice: the payment is booked for what came in and {0} goes to the account chosen above.", [gapText])
                    : _("Books the payment received. The invoice stays due for {0}.", [gapText]))
            : isConfirmRebate
                ? (credit
                    ? _("Makes a credit note of {0} on the article chosen above and settles the invoice. The payment received is booked as it is.", [gapText])
                    : deduct
                        ? _("Settles the invoice: the payment is booked for what came in and {0} is taken off the turnover, on the sales account of the invoice with its VAT.", [gapText])
                        : settle
                            ? _("Settles the invoice: the payment is booked for what came in and the difference of {0} goes to the account chosen above.", [gapText])
                            : _("Books the payment received. The invoice stays due for {0}.", [gapText]))
            : isOverpaid
                ? (settle
                    ? _("Settles the invoice: the payment is booked for what came in and {0} goes to the account chosen above.", [gapText])
                    : isSale
                        ? _("Books the whole payment: the invoice is settled and {0} stays available for the customer, to match with a next invoice.", [gapText])
                        : _("Books the whole payment: the invoice is settled and {0} stays open with the supplier, to match with a next invoice.", [gapText]))
            : verdict.kind === "dunning_fee"
                ? _("The fee of the dunning is booked on its own account and settles it.")
                : _("Settles the invoice: the payment is booked for what came in and the difference of {0} goes to the account chosen above.", [gapText])

    // the page of the manual that the main button speaks of: the three choices of a partial payment, or the card in general
    const passPage = isPartial ? MANUAL.partial : MANUAL.decide

    // one line of what will be booked: the account, the amount (a row of the table on the right of the choices)
    const bookedRow = (label: string, amount: number, strong = false) => (
        <div className={cn("flex justify-between gap-4 text-sm", strong && "font-medium")}>
            <span className={cn("min-w-0", !strong && "text-muted-foreground")}>{label}</span>
            <span className="shrink-0 font-mono tabular-nums">{formatCurrency(amount, verdict.currency)}</span>
        </div>
    )

    const tile = (value: Mode, label: string, hint: ReactNode, proposed: boolean, href: string = MANUAL.partial) => (
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
            <InfoHint href={href}>{hint}</InfoHint>
        </div>
    )

    return (
        <div className="flex flex-col rounded-lg border bg-card">
            <div className="flex flex-col gap-2.5 p-3.5">
                <div className="flex items-center justify-between gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
                        <span className="size-1.5 rounded-full bg-current" />
                        {confirming ? _("To confirm") : _("To decide")}
                    </span>
                    <span className="flex items-center gap-2 text-xs text-muted-foreground">
                        <a className="underline underline-offset-2" href={documentHref(decision.invoice_type, decision.invoice)} target="_blank" rel="noopener noreferrer">{decision.invoice}</a>
                        <span>{lineDay}</span>
                    </span>
                </div>
                <div className="flex flex-col gap-1">
                    <span className="text-xl leading-tight font-medium">{headline}</span>
                    <p className="text-sm leading-relaxed text-muted-foreground">{sentence(decision)}</p>
                </div>
                {/* vouchers that already exist for this line are under « or », below the card: say so before the person books a second one */}
                <MatchingVouchersHint transaction={transaction} />
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
                {(isPartial || isConfirmRebate) && decision.can_settle && (
                    <div className="flex flex-col gap-2" role="radiogroup">
                        <span className="text-base font-medium">{_("What becomes of the remaining {0}?", [gapText])}</span>
                        <div className="grid grid-cols-1 gap-2 @[36rem]:grid-cols-2">
                            {tile("open", _("Leave the balance to pay"), _("Only the payment received is booked. The invoice stays open for {0}: choose this when the customer still has to pay the rest, or when a credit note will be made afterwards (goods brought back into stock, for example) and matched later.", [gapText]), false)}
                            {decision.can_deduct && tile(
                                "deduct",
                                _("Take it off the turnover"),
                                _("The invoice is settled and {0} is taken off the turnover, on the sales account of the invoice and with its VAT: one entry, no document for the customer. Choose this for an arrangement with the customer, a commercial gesture or a rebate.", [gapText]),
                                false,
                            )}
                            {note && tile(
                                "credit",
                                _("Make a credit note"),
                                _("Makes a credit note of {0} on the article you choose, with the VAT of the invoice, and settles the invoice. It is one line and moves no stock. When goods come back, make the credit note yourself from the invoice, then choose Leave the balance to pay.", [gapText]),
                                habit?.proposal === "credit_note" || decision.rule_proposal === "credit_note",
                            )}
                            {tile(
                                "gap",
                                isConfirmRebate ? _("Book it as a rebate") : isSale ? _("Book it as a loss on the customer") : _("Write off the balance as a loss or a discount"),
                                isConfirmRebate
                                    ? _("The invoice is settled and {0} is booked as a rebate on the account you choose below (the one the company set, by default). Choose this to accept the rebate as it is.", [gapText])
                                    : isSale
                                    ? _("The invoice is settled and {0} is booked as a loss on the account you choose below (the one the company set, by default). Choose this when the customer will not pay the rest.", [gapText])
                                    : _("The invoice is settled and {0} is booked on the account you choose below: a loss on customers when the customer will not pay the rest, or a discount when you grant one. Unlike a credit note, no document is made for the customer.", [gapText]),
                                decision.rule_proposal === "gap",
                            )}
                        </div>
                    </div>
                )}
                {isOverpaid && decision.can_decide_surplus && (
                    <div className="flex flex-col gap-2" role="radiogroup">
                        <span className="text-base font-medium">{_("What becomes of the surplus of {0}?", [gapText])}</span>
                        {tile(
                            "open",
                            _("Keep it for a next invoice"),
                            isSale
                                ? _("The payment is booked in full. The invoice is settled and {0} stays available for the customer on this payment: you match it to another invoice later, in a reconciliation.", [gapText])
                                : _("The payment is booked in full. The invoice is settled and {0} stays open with the supplier on this payment: you match it to another invoice later, in a reconciliation.", [gapText]),
                            true,
                            MANUAL.decide,
                        )}
                        {tile(
                            "gap",
                            _("Book it as a difference"),
                            _("The invoice is settled and {0} is booked on the account you choose below, like the fee of a dunning. Nothing stays available for later.", [gapText]),
                            false,
                            MANUAL.decide,
                        )}
                        {!settle && (
                            <p className="text-sm leading-snug text-muted-foreground">
                                {isSale
                                    ? _("The payment is booked in full: {0} settle the invoice and {1} stay available for {2}, to match with a next invoice.", [owed, gapText, who])
                                    : _("The payment is booked in full: {0} settle the invoice and {1} stay open with {2}, to match with a next invoice.", [owed, gapText, who])}
                            </p>
                        )}
                    </div>
                )}
                {(isPartial || isConfirmRebate) && (deduct || (credit && note)) && (
                    <div className="grid grid-cols-1 gap-3 @[36rem]:grid-cols-2 @[36rem]:gap-x-6">
                        <div className="flex flex-col gap-2.5">
                            <p className="text-sm leading-snug text-muted-foreground">
                                {deduct
                                    ? _("{0} are taken off the turnover, on the sales account of the invoice and with its VAT: one entry, and the invoice is settled. For an arrangement with the customer, a commercial gesture or a rebate.", [gapText])
                                    : _("A credit note of {0} is made on the article below, with the VAT of the invoice. It settles the invoice.", [gapText])}
                            </p>
                            {credit && note && !draft && (
                                <>
                                    <div className="flex flex-col gap-1">
                                        <span className="text-sm font-medium">{_("Article")}</span>
                                        <LinkFieldCombobox
                                            doctype="Item"
                                            filters={[["is_sales_item", "=", 1], ["disabled", "=", 0]]}
                                            value={creditItem ?? note.item_code ?? ""}
                                            onChange={chooseArticle}
                                            placeholder={_("Choose an article")}
                                        />
                                        <span className="text-xs leading-snug text-muted-foreground">
                                            {creditItem
                                                ? _("The article you chose.")
                                                : note.source === "history"
                                                    ? _("Filled in: the article of the credit notes of this customer.")
                                                    : note.source === "article"
                                                        ? _("Filled in: the article most used for the credit notes of the company.")
                                                        : _("Choose the article that tells why: a discount, a loss on a customer.")}
                                        </span>
                                    </div>
                                    <div className="flex flex-col gap-1">
                                        <span className="text-sm font-medium">{_("Account")}</span>
                                        <AccountsDropdown
                                            root_type={["Income"]}
                                            company={transaction.company}
                                            value={account ?? note.account ?? undefined}
                                            onChange={(value) => setAccount(value || null)}
                                        />
                                        <span className="text-xs leading-snug text-muted-foreground">
                                            {decision.default_account && decision.default_account !== (account ?? note.account)
                                                ? _("The account the article is sold on. For a loss on a customer, choose {0}.", [decision.default_account])
                                                : _("The account the article is sold on.")}
                                        </span>
                                    </div>
                                </>
                            )}
                            {credit && (
                                <p className="rounded-md border border-amber-200 bg-amber-50 p-2.5 text-sm leading-snug text-amber-950">
                                    <b>{_("Goods are coming back and must go into stock?")}</b>{" "}
                                    {_("Make the credit note yourself from the invoice, then choose Leave the balance to pay: you match it afterwards.")}
                                </p>
                            )}
                        </div>
                        <div className="flex flex-col gap-1.5 self-start rounded-md border bg-white p-3">
                            <span className="text-sm font-medium">{deduct ? _("What will be booked") : _("The credit note")}</span>
                            {deduct ? (
                                <>
                                    {decision.deductions.map((row, index) => (
                                        <div key={`${row.account}-${index}`}>{bookedRow(`${_("Debit")} · ${row.account}`, Math.abs(row.amount))}</div>
                                    ))}
                                    {decision.booked_credit_account && bookedRow(`${_("Credit")} · ${decision.booked_credit_account} (${who})`, Math.abs(verdict.gap))}
                                </>
                            ) : note && (
                                <>
                                    {note.item && (
                                        <div className="flex justify-between gap-4 text-sm">
                                            <span className="text-muted-foreground">{_("Article")}</span>
                                            <span className="min-w-0 truncate">{note.item}</span>
                                        </div>
                                    )}
                                    {note.net !== null && bookedRow(`${_("Net")} · ${note.account ?? ""}`, note.net)}
                                    {note.tax_lines.map((line, index) => (
                                        <div key={`${line.account}-${index}`}>{bookedRow(`${_("VAT")} · ${line.account}`, line.amount)}</div>
                                    ))}
                                    {note.fees > 0 && bookedRow(`${note.fees_label ?? _("Charges")}${note.fees_account ? ` · ${note.fees_account}` : ""}`, note.fees)}
                                    {bookedRow(_("Total of the credit note"), note.total, true)}
                                </>
                            )}
                            <div className="my-0.5 border-t" />
                            <div className="flex justify-between gap-4 text-sm font-medium">
                                <span>{_("Invoice {0}: amount due", [decision.invoice])}</span>
                                <span className="shrink-0 font-mono tabular-nums">{gapText} → {formatCurrency(0, verdict.currency)}</span>
                            </div>
                        </div>
                    </div>
                )}
                {missingSetting && (
                    <div className="flex flex-col gap-2 rounded-md border border-amber-200 bg-amber-50 p-2.5 text-amber-950">
                        <span className="text-sm leading-snug">
                            <b>{isSale ? _("The company has not said yet where to book the differences on sales.") : _("The company has not said yet where to book the differences on purchases.")}</b>{" "}
                            {_("Until it does, each difference is decided one by one: choose an account for this line below.")}
                        </span>
                        {settingsHref && (
                            <div className="flex items-center gap-2">
                                <Button asChild variant="outline" className="h-10 flex-1">
                                    <a href={settingsHref} target="_blank" rel="noopener noreferrer">{_("Fill in the settings")} <ExternalLink className="size-4" /></a>
                                </Button>
                                <InfoHint href={MANUAL.settings}>{_("Opens the settings of the company in a new tab: this screen stays open. The accounts are in the section Payment Gaps.")}</InfoHint>
                            </div>
                        )}
                    </div>
                )}
                {showAccount && (
                    <div className="flex flex-col gap-1">
                        <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-medium">{_("Account for the difference")}</span>
                            <InfoHint href={MANUAL.settings}>
                                {_("The account where the difference is booked: for a sale, a loss on customers or a discount account; for a purchase, an expense account. Your fiduciary knows which one to use. The company sets it once in its settings.")}
                            </InfoHint>
                        </div>
                        <AccountsDropdown
                            root_type={isSale ? ["Income"] : ["Expense"]}
                            company={transaction.company}
                            value={account ?? decision.account ?? undefined}
                            onChange={(value) => setAccount(value || null)}
                        />
                        {account && account !== decision.default_account && decision.default_account && (
                            <button type="button" className="w-fit text-xs underline underline-offset-2" onClick={() => setAccount(null)}>{_("Back to the company's account")}</button>
                        )}
                    </div>
                )}
                {decision.deductions.length > 0 && !deduct && (
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
            </div>
            {/* the buttons stay at the foot of the visible panel while the card scrolls under them */}
            <div className="sticky bottom-0 z-10 flex flex-col gap-1.5 rounded-b-lg border-t bg-card px-3.5 py-2.5 shadow-[0_-8px_10px_-8px_rgba(0,0,0,0.12)] @[36rem]:flex-row">
                <div className="flex items-center gap-2 @[36rem]:flex-1">
                    <Button className="h-9 flex-1" disabled={loading || !decision.can_pass} onClick={onDecide}>{passLabel}</Button>
                    <InfoHint href={passPage}>
                        <span>{passHint}</span>
                        <span className="text-xs text-muted-foreground">{_("Your name and the date are noted on the line of the import.")}</span>
                    </InfoHint>
                </div>
                <div className="flex items-center gap-2 @[36rem]:flex-1">
                    <Button variant="outline" className="h-9 flex-1" disabled={loading} onClick={() => {
                        // the form opens on the customer (or supplier) of the invoice, not on whoever the bank wrote
                        if (decision.party_id) setRecordPaymentPrefill({ party_type: decision.party_doctype, party: decision.party_id })
                        setRecordPaymentOpen(true)
                    }}>{_("Reconcile manually")}</Button>
                    <InfoHint href={MANUAL.manualPayment}>{_("Opens the full payment form, pointed at the customer (or supplier) of this invoice. Use it when none of the choices fits.")}</InfoHint>
                </div>
            </div>
        </div>
    )
}

export default GapDecisionCard
