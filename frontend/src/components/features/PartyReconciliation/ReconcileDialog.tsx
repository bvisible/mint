//// Neoffice — added file (no upstream equivalent). What a reconciliation will write, then the reconciliation.
import { useFrappePostCall } from "frappe-react-sdk"
import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import ErrorBanner from "@/components/ui/error-banner"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatCurrency } from "@/lib/numbers"
import _ from "@/lib/translate"
import type { PartyType, PreviewData } from "./types"

export type Chosen = {
    invoices: { invoice_type: string, invoice_number: string, amount: number }[],
    payments: { reference_type: string, reference_name: string, reference_row?: string | null, amount: number }[],
}

type Props = {
    open: boolean,
    onOpenChange: (open: boolean) => void,
    company: string,
    partyType: PartyType,
    party: string,
    account: string,
    chosen: Chosen,
    currency: string,
    onDone: () => void,
}

const ReconcileDialog = ({ open, onOpenChange, company, partyType, party, account, chosen, currency, onDone }: Props) => {
    const { call: previewCall, loading, error, reset } = useFrappePostCall<{ message: PreviewData }>("mint.apis.party_reconciliation.preview")
    const { call: reconcileCall, loading: reconciling, error: reconcileError } = useFrappePostCall<{ message: unknown }>("mint.apis.party_reconciliation.reconcile")
    const [preview, setPreview] = useState<PreviewData | null>(null)

    const payload = { company, party_type: partyType, party, account, invoices: chosen.invoices, payments: chosen.payments }

    useEffect(() => {
        if (!open) {
            setPreview(null)
            reset()
            return
        }
        previewCall(payload).then((result) => setPreview(result.message)).catch(() => undefined)
        // The preview is asked once per opening, for the rows chosen at that moment.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open])

    const confirm = () => {
        reconcileCall(payload)
            .then(() => {
                toast.success(_("Reconciled"))
                onDone()
                onOpenChange(false)
            })
            .catch(() => undefined)
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle>{_("Reconcile")}</DialogTitle>
                    <DialogDescription>{_("This is what will be written. Nothing is changed until you confirm.")}</DialogDescription>
                </DialogHeader>

                {error && <ErrorBanner error={error} />}
                {reconcileError && <ErrorBanner error={reconcileError} />}
                {loading && <Skeleton className="h-32 w-full" />}

                {preview && (
                    <div className="flex flex-col gap-4">
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>{_("Payment, credit note or entry")}</TableHead>
                                    <TableHead>{_("Invoice")}</TableHead>
                                    <TableHead className="text-right">{_("Amount")}</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {preview.allocation.map((row, index) => (
                                    <TableRow key={index}>
                                        <TableCell>{_(row.reference_type)} {row.reference_name}</TableCell>
                                        <TableCell>{row.invoice_number}</TableCell>
                                        <TableCell className="text-right font-mono tabular-nums">{formatCurrency(row.allocated_amount, currency)}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                        <div className="grid gap-1 text-sm">
                            <div className="flex justify-between"><span>{_("Reconciled")}</span><span className="font-mono tabular-nums font-semibold">{formatCurrency(preview.settled, currency)}</span></div>
                            <div className="flex justify-between text-muted-foreground"><span>{_("Still due on these invoices")}</span><span className="font-mono tabular-nums">{formatCurrency(preview.invoices_left, currency)}</span></div>
                            <div className="flex justify-between text-muted-foreground"><span>{_("Unused on these payments and credits")}</span><span className="font-mono tabular-nums">{formatCurrency(preview.credits_left, currency)}</span></div>
                            {preview.difference !== 0 && (
                                <div className="flex justify-between text-amber-700"><span>{_("Exchange difference")}</span><span className="font-mono tabular-nums">{formatCurrency(preview.difference, currency)}</span></div>
                            )}
                        </div>
                    </div>
                )}

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>{_("Cancel")}</Button>
                    <Button onClick={confirm} disabled={!preview || reconciling}>{reconciling ? _("Reconciling…") : _("Reconcile")}</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export default ReconcileDialog
