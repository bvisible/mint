//// Neoffice — added file (no upstream equivalent). One party: its open invoices on the left, what could settle
//// them on the right, a calculator below. The party is the one chosen and the one reconciled: nothing here mixes two.
import { useFrappeGetCall } from "frappe-react-sdk"
import { AlertTriangle, Search } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import ErrorBanner from "@/components/ui/error-banner"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatDate } from "@/lib/date"
import { formatCurrency } from "@/lib/numbers"
import _ from "@/lib/translate"
import { cn } from "@/lib/utils"
import ReconcileDialog, { type Chosen } from "./ReconcileDialog"
import RowMenu, { type MenuState } from "./RowMenu"
import type { InvoiceRow, PartyDetailData, PartyType, Selection, SettlementRow } from "./types"
import { amountProblem, byDate, includesText, invoiceKey, parseAmount, round2, settlementKey, settlementKind } from "./utils"
import VoucherSheet, { type VoucherRef } from "./VoucherSheet"
import { API } from "./api"

type Props = {
    company: string,
    partyType: PartyType,
    party: string,
    /** Raised by the screen after a reconciliation: the party is asked again. */
    version: number,
    onReconciled: () => void,
}

const deskRoute = (type: string, name: string) => `/app/${type.toLowerCase().replace(/ /g, "-")}/${encodeURIComponent(name)}`

const sumOf = (picks: Selection) =>
    round2(Object.values(picks).reduce((total, text) => {
        const value = parseAmount(text)
        return total + (Number.isFinite(value) && value > 0 ? value : 0)
    }, 0))

const PartyDetail = ({ company, partyType, party, version, onReconciled }: Props) => {
    const { data, error, isLoading } = useFrappeGetCall<{ message: PartyDetailData }>(
        `${API}.get_party_detail`,
        { company, party_type: partyType, party },
        ["party-reconciliation", "detail", company, partyType, party, version],
        { revalidateOnFocus: false },
    )
    const detail = data?.message

    const [invoicePicks, setInvoicePicks] = useState<Selection>({})
    const [settlementPicks, setSettlementPicks] = useState<Selection>({})
    const [invoiceSearch, setInvoiceSearch] = useState("")
    const [settlementSearch, setSettlementSearch] = useState("")
    const [voucher, setVoucher] = useState<VoucherRef | null>(null)
    const [menu, setMenu] = useState<MenuState>(null)
    const [confirming, setConfirming] = useState(false)

    // Another party, or the same one after a reconciliation, starts with nothing ticked.
    useEffect(() => {
        setInvoicePicks({})
        setSettlementPicks({})
        setInvoiceSearch("")
        setSettlementSearch("")
    }, [party, version])

    const invoices = useMemo(
        () => [...(detail?.invoices ?? [])].sort(byDate<InvoiceRow>((row) => row.invoice_date)).filter((row) =>
            includesText(invoiceSearch, row.invoice_number, row.reference, row.remark, row.outstanding_amount.toFixed(2))),
        [detail, invoiceSearch],
    )
    const settlements = useMemo(
        () => [...(detail?.payments ?? [])].sort(byDate<SettlementRow>((row) => row.posting_date)).filter((row) =>
            includesText(settlementSearch, row.reference_name, row.reference, row.remark, row.amount.toFixed(2))),
        [detail, settlementSearch],
    )

    if (isLoading) return <Skeleton className="h-96 w-full" />
    if (error) return <ErrorBanner error={error} />
    if (!detail) return null

    const currency = detail.currency
    const invoiceTotal = sumOf(invoicePicks)
    const settlementTotal = sumOf(settlementPicks)
    const settled = round2(Math.min(invoiceTotal, settlementTotal))

    const invoiceByKey = new Map(detail.invoices.map((row) => [invoiceKey(row), row]))
    const settlementByKey = new Map(detail.payments.map((row) => [settlementKey(row), row]))
    const problems = [
        ...Object.entries(invoicePicks).map(([key, text]) => amountProblem(text, invoiceByKey.get(key)?.outstanding_amount ?? 0)),
        ...Object.entries(settlementPicks).map(([key, text]) => amountProblem(text, settlementByKey.get(key)?.amount ?? 0)),
    ].filter(Boolean)
    const ready = settled > 0 && problems.length === 0

    const chosen: Chosen = {
        invoices: Object.entries(invoicePicks).map(([key, text]) => {
            const row = invoiceByKey.get(key)!
            return { invoice_type: row.invoice_type, invoice_number: row.invoice_number, amount: parseAmount(text) }
        }),
        payments: Object.entries(settlementPicks).map(([key, text]) => {
            const row = settlementByKey.get(key)!
            return { reference_type: row.reference_type, reference_name: row.reference_name, reference_row: row.reference_row ?? null, amount: parseAmount(text) }
        }),
    }

    const tick = (setter: (update: (previous: Selection) => Selection) => void, key: string, on: boolean, amount: number) =>
        setter((previous) => {
            const next = { ...previous }
            if (on) next[key] = amount.toFixed(2)
            else delete next[key]
            return next
        })

    const menuFor = (event: React.MouseEvent, type: string, name: string, reference: string | null | undefined, toggle: () => void, ticked: boolean) => {
        event.preventDefault()
        setMenu({
            x: event.clientX,
            y: event.clientY,
            items: [
                { label: _("Show details"), onSelect: () => setVoucher({ type, name }) },
                { label: _("Open in a new tab"), onSelect: () => { window.open(deskRoute(type, name), "_blank", "noopener") } },
                { label: _("Copy the reference"), onSelect: () => { navigator.clipboard?.writeText(reference || name).then(() => toast.success(_("Copied")), () => toast.error(_("Could not copy"))) } },
                { label: ticked ? _("Untick") : _("Tick"), onSelect: toggle },
            ],
        })
    }

    return (
        <div className="@container flex flex-col gap-4 min-w-0">
            {/* The party, its account, and where the ledger stands */}
            <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div className="min-w-0">
                    <h2 className="text-xl font-semibold truncate">{detail.label}</h2>
                    <p className="text-sm text-muted-foreground">{detail.account}</p>
                </div>
                <div className="flex flex-wrap gap-2 text-sm">
                    <Badge variant="outline">{_("Open")}: <span className="font-mono tabular-nums">{formatCurrency(detail.totals.open, currency)}</span></Badge>
                    <Badge variant="outline">{_("To apply")}: <span className="font-mono tabular-nums">{formatCurrency(detail.totals.credit, currency)}</span></Badge>
                    <Badge variant="secondary">{_("Balance")}: <span className="font-mono tabular-nums">{formatCurrency(detail.totals.balance, currency)}</span></Badge>
                </div>
            </div>
            {detail.check.difference !== 0 && (
                <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                    <AlertTriangle className="size-4 mt-0.5 shrink-0" />
                    <span>{_("The ledger says {0}, the open documents say {1}: a difference of {2}.", [formatCurrency(detail.check.ledger, currency), formatCurrency(detail.check.documents, currency), formatCurrency(detail.check.difference, currency)])}</span>
                </div>
            )}
            {detail.other_accounts.length > 0 && (
                <div className="flex items-start gap-2 rounded-md border bg-muted px-3 py-2 text-sm">
                    <AlertTriangle className="size-4 mt-0.5 shrink-0" />
                    <span>{_("This party also has balances on other accounts, which are reconciled separately:")} {detail.other_accounts.map((other) => `${other.account} (${formatCurrency(other.balance, currency)})`).join(", ")}</span>
                </div>
            )}

            <div className="grid gap-4 @5xl:grid-cols-2">
                {/* Left: what has to be settled */}
                <section className="flex flex-col gap-2 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                        <h3 className="font-medium">{_("Open invoices")}</h3>
                        <div className="relative w-48">
                            <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
                            <Input className="pl-7 h-9" value={invoiceSearch} onChange={(event) => setInvoiceSearch(event.target.value)} placeholder={_("Amount or reference")} />
                        </div>
                    </div>
                    <div className="max-h-[45vh] overflow-y-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-8" />
                                <TableHead>{_("Date")}</TableHead>
                                <TableHead>{_("Invoice")}</TableHead>
                                <TableHead className="text-right">{_("Due")}</TableHead>
                                <TableHead className="text-right">{_("To settle")}</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {invoices.map((row) => {
                                const key = invoiceKey(row)
                                const ticked = key in invoicePicks
                                const problem = ticked ? amountProblem(invoicePicks[key], row.outstanding_amount) : null
                                const toggle = () => tick(setInvoicePicks, key, !ticked, row.outstanding_amount)
                                return (
                                    <TableRow key={key} data-state={ticked ? "selected" : undefined} className="cursor-pointer"
                                        onClick={() => setVoucher({ type: row.invoice_type, name: row.invoice_number })}
                                        onContextMenu={(event) => menuFor(event, row.invoice_type, row.invoice_number, row.reference, toggle, ticked)}>
                                        <TableCell onClick={(event) => event.stopPropagation()}>
                                            <Checkbox checked={ticked} onCheckedChange={(on) => tick(setInvoicePicks, key, on === true, row.outstanding_amount)} aria-label={_("Tick")} />
                                        </TableCell>
                                        <TableCell className="whitespace-nowrap">{formatDate(row.invoice_date)}</TableCell>
                                        <TableCell className="min-w-0">
                                            <div className="font-medium">{row.invoice_number}</div>
                                            {row.reference && <div className="text-xs text-muted-foreground truncate max-w-48">{row.reference}</div>}
                                        </TableCell>
                                        <TableCell className="text-right whitespace-nowrap">{row.due_date ? formatDate(row.due_date) : ""}</TableCell>
                                        <TableCell className="text-right" onClick={(event) => event.stopPropagation()}>
                                            {ticked ? (
                                                <Input className={cn("h-8 w-28 text-right font-mono tabular-nums ml-auto", problem && "border-destructive")} title={problem ?? ""}
                                                    value={invoicePicks[key]} onChange={(event) => setInvoicePicks((previous) => ({ ...previous, [key]: event.target.value }))} />
                                            ) : (
                                                <span className="font-mono tabular-nums">{formatCurrency(row.outstanding_amount, row.currency)}</span>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                )
                            })}
                            {invoices.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground py-6">{_("No open invoice.")}</TableCell></TableRow>}
                        </TableBody>
                    </Table>
                    </div>
                </section>

                {/* Right: what could settle them */}
                <section className="flex flex-col gap-2 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                        <h3 className="font-medium">{_("Payments, credit notes and entries")}</h3>
                        <div className="relative w-48">
                            <Search className="absolute left-2 top-2.5 size-4 text-muted-foreground" />
                            <Input className="pl-7 h-9" value={settlementSearch} onChange={(event) => setSettlementSearch(event.target.value)} placeholder={_("Amount or reference")} />
                        </div>
                    </div>
                    <div className="max-h-[45vh] overflow-y-auto">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="w-8" />
                                <TableHead>{_("Date")}</TableHead>
                                <TableHead>{_("Document")}</TableHead>
                                <TableHead>{_("Reference")}</TableHead>
                                <TableHead className="text-right">{_("To use")}</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {settlements.map((row) => {
                                const key = settlementKey(row)
                                const ticked = key in settlementPicks
                                const problem = ticked ? amountProblem(settlementPicks[key], row.amount) : null
                                const toggle = () => tick(setSettlementPicks, key, !ticked, row.amount)
                                return (
                                    <TableRow key={key} data-state={ticked ? "selected" : undefined} className="cursor-pointer"
                                        onClick={() => setVoucher({ type: row.reference_type, name: row.reference_name })}
                                        onContextMenu={(event) => menuFor(event, row.reference_type, row.reference_name, row.reference, toggle, ticked)}>
                                        <TableCell onClick={(event) => event.stopPropagation()}>
                                            <Checkbox checked={ticked} onCheckedChange={(on) => tick(setSettlementPicks, key, on === true, row.amount)} aria-label={_("Tick")} />
                                        </TableCell>
                                        <TableCell className="whitespace-nowrap">{formatDate(row.posting_date)}</TableCell>
                                        <TableCell className="min-w-0">
                                            <Badge variant="secondary">{settlementKind(partyType, row)}</Badge>
                                            <div className="text-xs mt-0.5">{row.reference_name}</div>
                                        </TableCell>
                                        <TableCell className="min-w-0">
                                            <div className="truncate max-w-40">{row.reference}</div>
                                            {row.remark && <div className="text-xs text-muted-foreground truncate max-w-40">{row.remark}</div>}
                                        </TableCell>
                                        <TableCell className="text-right" onClick={(event) => event.stopPropagation()}>
                                            {ticked ? (
                                                <Input className={cn("h-8 w-28 text-right font-mono tabular-nums ml-auto", problem && "border-destructive")} title={problem ?? ""}
                                                    value={settlementPicks[key]} onChange={(event) => setSettlementPicks((previous) => ({ ...previous, [key]: event.target.value }))} />
                                            ) : (
                                                <span className="font-mono tabular-nums">{formatCurrency(row.amount, row.currency)}</span>
                                            )}
                                        </TableCell>
                                    </TableRow>
                                )
                            })}
                            {settlements.length === 0 && <TableRow><TableCell colSpan={5} className="text-center text-muted-foreground py-6">{_("Nothing to apply.")}</TableCell></TableRow>}
                        </TableBody>
                    </Table>
                    </div>
                </section>
            </div>

            {/* The calculator: if I take this much, how much is left */}
            <div className="sticky bottom-0 rounded-lg border bg-card p-4 shadow-sm">
                <div className="grid gap-x-6 gap-y-1 text-sm @lg:grid-cols-2 @4xl:grid-cols-4">
                    <Figure label={_("Invoices ticked")} value={formatCurrency(invoiceTotal, currency)} />
                    <Figure label={_("Ticked to use")} value={formatCurrency(settlementTotal, currency)} />
                    <Figure label={_("Reconciled")} value={formatCurrency(settled, currency)} strong />
                    <Figure label={_("Still due on the ticked invoices")} value={formatCurrency(round2(invoiceTotal - settled), currency)} />
                    <Figure label={_("Unused on the ticked lines")} value={formatCurrency(round2(settlementTotal - settled), currency)} />
                    <Figure label={_("Party still due after")} value={formatCurrency(round2(detail.totals.open - settled), currency)} />
                    <Figure label={_("Party to apply after")} value={formatCurrency(round2(detail.totals.credit - settled), currency)} />
                </div>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm text-muted-foreground">
                        {problems.length > 0 ? _("An amount is not valid.") : settled === 0 ? _("Tick at least one invoice and one payment, credit note or entry.") : ""}
                    </span>
                    <Button disabled={!ready} onClick={() => setConfirming(true)}>{_("Reconcile")}</Button>
                </div>
            </div>

            <RowMenu menu={menu} onClose={() => setMenu(null)} />
            <VoucherSheet voucher={voucher} onClose={() => setVoucher(null)} />
            <ReconcileDialog
                open={confirming}
                onOpenChange={setConfirming}
                company={company}
                partyType={partyType}
                party={party}
                account={detail.account}
                chosen={chosen}
                currency={currency}
                onDone={onReconciled}
            />
        </div>
    )
}

const Figure = ({ label, value, strong }: { label: string, value: string, strong?: boolean }) => (
    <div className="flex items-baseline justify-between gap-2 min-w-0">
        <span className="text-muted-foreground">{label}</span>
        <span className={cn("font-mono tabular-nums", strong && "font-semibold")}>{value}</span>
    </div>
)

export default PartyDetail
