//// Neoffice — added file (no upstream equivalent). What a person does with a bank line that no single invoice settles:
//// one amount for several invoices, a reference that is the one of an invoice already paid, or no reference at all. The
//// open invoices of the party are listed (found by the import, the line or the IBAN of the payer), the person picks the
//// ones the payment settles, the amount is split between them (oldest first, editable), and the payment is validated
//// and reconciled at once, or prepared as a DRAFT that is opened in its own tab, corrected, validated, and reconciled here.
import { useFrappeGetCall, useFrappePostCall, useSWRConfig } from "frappe-react-sdk"
import { FileEdit, Info, ListChecks } from "lucide-react"
import { useSetAtom } from "jotai"
import { useEffect, useMemo, useRef, useState } from "react"
import { toast } from "sonner"
import { bankRecRecordPaymentModalAtom, bankRecUnreconcileModalAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import { UnreconciledTransaction, useRefreshUnreconciledTransactions } from "@/components/features/BankReconciliation/utils"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import ErrorBanner from "@/components/ui/error-banner"
import { Input } from "@/components/ui/input"
import { formatDate } from "@/lib/date"
import { formatCurrency } from "@/lib/numbers"
import _ from "@/lib/translate"
import { LINE_API } from "./api"
import type { LineCandidates, LineEntry } from "./types"
import { documentHref } from "./utils"

const CENT = 0.005
const cents = (value: number) => Math.round(value * 100) / 100

type Picked = Record<string, string>

const LineInvoicesCard = ({ transaction }: { transaction: UnreconciledTransaction }) => {
    const { mutate } = useSWRConfig()
    const onReconcile = useRefreshUnreconciledTransactions()
    const setUnreconcile = useSetAtom(bankRecUnreconcileModalAtom)
    const setRecordPaymentOpen = useSetAtom(bankRecRecordPaymentModalAtom)

    // revalidated on focus: a draft validated in its own tab shows up as soon as the person comes back
    const { data } = useFrappeGetCall<{ message: LineCandidates | null }>(
        `${LINE_API}.get_candidates`,
        { bank_transaction: transaction.name },
        ["line-invoices", transaction.name],
        { revalidateOnFocus: true, keepPreviousData: true },
    )
    const { call: settle, loading: settling, error: settleError } = useFrappePostCall<{ message: { payment_entry: string, draft: boolean } }>(`${LINE_API}.settle`)
    const { call: submitDraft, loading: submitting, error: submitError } = useFrappePostCall(`${LINE_API}.submit_draft`)
    const { call: deleteDraft, loading: deleting, error: deleteError } = useFrappePostCall(`${LINE_API}.delete_draft`)

    const candidates = data?.message
    const [picked, setPicked] = useState<Picked>({})

    // the invoices the import named are ticked at the start, the amount split between them oldest first
    const split = (names: string[], amount: number, invoices: LineCandidates["invoices"]): Picked => {
        let left = amount
        const next: Picked = {}
        for (const name of names) {
            const invoice = invoices.find((row) => row.name === name)
            if (!invoice || left <= CENT) continue
            const part = Math.min(invoice.outstanding, left)
            next[name] = part.toFixed(2)
            left = cents(left - part)
        }
        return next
    }
    const started = useRef(false)
    useEffect(() => {
        if (!candidates || started.current) return
        started.current = true
        if (candidates.reason === "several") setPicked(split(candidates.recognised, candidates.amount, candidates.invoices))
    }, [candidates])

    const allocated = useMemo(() => cents(Object.values(picked).reduce((sum, value) => sum + (parseFloat(value) || 0), 0)), [picked])

    if (!candidates?.show) return null

    const { currency } = candidates
    const rest = cents(candidates.amount - allocated)
    const complete = Object.keys(picked).length > 0 && Math.abs(rest) <= CENT
    const entries = [...candidates.drafts, ...candidates.submitted]
    const busy = settling || submitting || deleting

    const refresh = () => mutate((key) => Array.isArray(key) && (key[0] === "statement-imports" || key[0] === "line-invoices"))
    const done = (message: string) => {
        refresh()
        toast.success(message, {
            duration: 4000,
            closeButton: true,
            action: { label: _("Undo"), onClick: () => setUnreconcile(transaction.name) },
        })
        onReconcile(transaction)
    }

    const toggle = (name: string, outstanding: number) => {
        setPicked((current) => {
            const next = { ...current }
            if (name in next) {
                delete next[name]
                return next
            }
            const left = cents(candidates.amount - Object.values(current).reduce((sum, value) => sum + (parseFloat(value) || 0), 0))
            next[name] = (left > CENT ? Math.min(outstanding, left) : outstanding).toFixed(2)
            return next
        })
    }
    const only = (name: string, outstanding: number) => setPicked({ [name]: Math.min(outstanding, candidates.amount).toFixed(2) })
    const rows = () => Object.entries(picked).map(([invoice, amount]) => ({ invoice, amount: parseFloat(amount) || 0 }))

    const onSettle = () => {
        settle({ bank_transaction: transaction.name, allocations: rows(), party: candidates.party }).then(() => {
            done(_("Payment recorded, invoices settled and bank line reconciled"))
        })
    }
    const onPrepare = () => {
        // opened at the click (a window opened after the answer is taken for a pop-up), pointed at the draft once it exists
        const tab = window.open("", "_blank")
        settle({ bank_transaction: transaction.name, allocations: rows(), party: candidates.party, draft: 1 })
            .then((answer) => {
                const href = documentHref("Payment Entry", answer.message.payment_entry)
                if (tab) tab.location.href = href
                refresh()
                toast.success(_("Draft {0} prepared: correct it in its tab, validate it, then come back here.", [answer.message.payment_entry]))
            })
            .catch(() => tab?.close())
    }
    const onSubmitDraft = (entry: LineEntry) => {
        submitDraft({ bank_transaction: transaction.name, payment_entry: entry.name }).then(() => done(_("Payment validated and bank line reconciled")))
    }
    const onDeleteDraft = (entry: LineEntry) => {
        deleteDraft({ bank_transaction: transaction.name, payment_entry: entry.name }).then(() => {
            refresh()
            toast.success(_("Draft deleted"))
        })
    }

    const title = candidates.reason === "several" ? _("One payment, several invoices") : candidates.reason === "paid" ? _("No invoice recognised") : _("Pick the invoices this payment settles")
    // formatted apart: a string literal inside the arguments of _() is read by the extractor as its CONTEXT
    const paidOn = candidates.paid_on ? formatDate(candidates.paid_on, "Do MMM YYYY") : ""
    const lead = candidates.reason === "several"
        ? _("The import recognised {0} invoices.", [String(candidates.recognised.length)])
        : candidates.reason === "paid"
            ? (candidates.paid_on
                ? _("The reference {0} is that of an invoice already paid, on {1}. This payment does not settle it.", [candidates.reference_hint ?? "", paidOn])
                : _("The reference {0} is that of an invoice already paid. This payment does not settle it.", [candidates.reference_hint ?? ""]))
            : _("The import recognised no invoice.")
    const found = candidates.party_source === "iban" ? _("Found by the IBAN of the payer.") : candidates.party_source === "import" ? _("Named by the import.") : ""

    return (
        <div className="flex flex-col gap-3 rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2">
                <ListChecks className="size-5 text-muted-foreground" />
                <span className="text-lg font-medium">{title}</span>
                <span title={_("The open invoices of the party, the oldest first. Tick the ones this payment settles: the amount is split between them and stays editable. A draft is opened in its own tab so that you can correct it by hand before validating.")}>
                    <Info className="size-4 text-muted-foreground" />
                </span>
            </div>
            <p className="text-sm leading-relaxed">
                {lead}
                {candidates.party && (
                    <span className="text-muted-foreground"> {_(candidates.party_type)} <span className="font-medium text-foreground">{candidates.party}</span>. {found}</span>
                )}
            </p>

            {entries.map((entry) => {
                const isDraft = candidates.drafts.some((draft) => draft.name === entry.name)
                const preparedOn = formatDate(entry.on, "Do MMM YYYY")
                return (
                    <div key={entry.name} className="flex flex-col gap-2 rounded-md border border-orange-300 bg-orange-50/60 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                            <Badge variant="outline" className="border-orange-400 bg-orange-50 text-orange-600"><FileEdit className="mr-1 size-3" />{isDraft ? _("Draft waiting") : _("Validated, to reconcile")}</Badge>
                            <a className="font-medium underline underline-offset-2" href={documentHref("Payment Entry", entry.name)} target="_blank" rel="noopener noreferrer">{entry.name}</a>
                        </div>
                        <p className="text-sm text-muted-foreground">
                            {_("Prepared by {0} on {1}: {2} on {3}.", [entry.by, preparedOn, formatCurrency(entry.amount, currency), entry.references.map((r) => r.invoice).join(", ")])}
                            {isDraft ? " " + _("Correct it in its tab if needed, validate it, then come back here.") : ""}
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                            {isDraft && (
                                <Button variant="outline" size="sm" onClick={() => window.open(documentHref("Payment Entry", entry.name), "_blank", "noopener")}>{_("Open the draft")}</Button>
                            )}
                            <Button size="sm" disabled={busy} onClick={() => onSubmitDraft(entry)}>
                                {isDraft ? _("Validate and reconcile") : _("Reconcile with {0}", [entry.name])}
                            </Button>
                            {isDraft && <Button variant="ghost" size="sm" disabled={busy} onClick={() => onDeleteDraft(entry)}>{_("Delete the draft")}</Button>}
                        </div>
                    </div>
                )
            })}

            {entries.length === 0 && (
                <>
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b text-left text-xs text-muted-foreground">
                                <th className="w-8 py-1" />
                                <th className="py-1 font-normal">{_("Invoice")}</th>
                                <th className="py-1 pr-2 font-normal leading-tight">{_("Due Date")}</th>
                                <th className="py-1 pl-2 text-right font-normal leading-tight">{_("Still owed")}</th>
                                <th className="w-32 py-1 pl-3 text-right font-normal leading-tight">{_("Settled by this payment")}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {candidates.invoices.map((invoice) => {
                                const on = invoice.name in picked
                                return (
                                    <tr key={invoice.name} className="border-b last:border-0">
                                        <td className="py-1"><Checkbox checked={on} onCheckedChange={() => toggle(invoice.name, invoice.outstanding)} aria-label={invoice.name} /></td>
                                        <td className="py-1">
                                            <a className="font-medium underline underline-offset-2" href={documentHref(candidates.invoice_type, invoice.name)} target="_blank" rel="noopener noreferrer">{invoice.name}</a>
                                            {invoice.bill_no ? <span className="ml-1 text-xs text-muted-foreground">{invoice.bill_no}</span> : null}
                                            {invoice.same_amount && !on && (
                                                <button type="button" className="ml-2" onClick={() => only(invoice.name, invoice.outstanding)} title={_("The same amount as the payment")}>
                                                    <Badge variant="secondary" className="cursor-pointer">{_("Same amount: pick this one")}</Badge>
                                                </button>
                                            )}
                                        </td>
                                        <td className="py-1 text-muted-foreground">{invoice.due_date ? formatDate(invoice.due_date, "Do MMM YYYY") : ""}</td>
                                        <td className="py-1 text-right font-mono tabular-nums">{formatCurrency(invoice.outstanding, currency)}</td>
                                        <td className="py-1 text-right">
                                            {on ? (
                                                <Input
                                                    type="number"
                                                    step="0.01"
                                                    min="0"
                                                    max={invoice.outstanding}
                                                    className="h-7 w-28 text-right font-mono tabular-nums"
                                                    value={picked[invoice.name]}
                                                    onChange={(event) => setPicked((current) => ({ ...current, [invoice.name]: event.target.value }))}
                                                />
                                            ) : <span className="text-muted-foreground">—</span>}
                                        </td>
                                    </tr>
                                )
                            })}
                        </tbody>
                    </table>
                    <table className="w-full max-w-sm text-sm">
                        <tbody>
                            <tr>
                                <td className="py-0.5 text-muted-foreground">{_("Received")}</td>
                                <td className="py-0.5 text-right font-mono tabular-nums">{formatCurrency(candidates.amount, currency)}</td>
                            </tr>
                            <tr>
                                <td className="py-0.5 text-muted-foreground">{_("Split over {0} invoices", [String(Object.keys(picked).length)])}</td>
                                <td className="py-0.5 text-right font-mono tabular-nums">{formatCurrency(allocated, currency)}</td>
                            </tr>
                            <tr className="border-t">
                                <td className="pt-1 font-medium">{_("Left to split")}</td>
                                <td className={`pt-1 text-right font-mono font-medium tabular-nums ${Math.abs(rest) <= CENT ? "text-emerald-700" : "text-destructive"}`}>{formatCurrency(rest, currency)}</td>
                            </tr>
                        </tbody>
                    </table>
                </>
            )}

            {(settleError || submitError || deleteError) && <ErrorBanner error={settleError ?? submitError ?? deleteError} />}
            <div className="flex flex-wrap items-center gap-3">
                {entries.length === 0 && (
                    <>
                        <Button disabled={!complete || busy} onClick={onSettle}>{_("Validate and reconcile")}</Button>
                        <Button variant="outline" disabled={!complete || busy} onClick={onPrepare}>{_("Prepare the draft")}</Button>
                    </>
                )}
                <Button variant="link" className="px-0" onClick={() => setRecordPaymentOpen(true)}>{_("Record another way")}</Button>
            </div>
        </div>
    )
}

export default LineInvoicesCard
