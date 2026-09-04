////// Neoffice — added file (no upstream equivalent): edit and submit a DRAFT Journal Entry
////// straight from the reconciliation screen (9bfe719, a401621, e582a55). ERPNext only offers
////// submitted vouchers for matching, so an accountant had to leave Mint, submit the JE and
////// come back. Pairs with get_linked_payments / submit_draft_je_and_reconcile in
////// mint/apis/bank_reconciliation.py.
import { useAtom, useAtomValue, useSetAtom } from "jotai"
import { bankRecDraftJEModalAtom, bankRecSelectedTransactionAtom, bankRecUnreconcileModalAtom, selectedBankAccountAtom } from "./bankRecAtoms"
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogHeader, DialogFooter, DialogClose } from "@/components/ui/dialog"
import _ from "@/lib/translate"
import { useRefreshUnreconciledTransactions } from "./utils"
import { useForm } from "react-hook-form"
import { useFrappePostCall } from "frappe-react-sdk"
import { toast } from "sonner"
import ErrorBanner from "@/components/ui/error-banner"
import { Button } from "@/components/ui/button"
import { DateField, SmallTextField } from "@/components/ui/form-elements"
import { Form } from "@/components/ui/form"
import { formatCurrency } from "@/lib/numbers"
import { formatDate } from "@/lib/date"
import { getErrorMessage } from "@/lib/frappe"
import { FileEdit, Calendar, MessageSquare } from "lucide-react"
import { Badge } from "@/components/ui/badge"

interface DraftJEFormData {
    posting_date: string
    cheque_date: string
    user_remark: string
}

const DraftJEModal = () => {
    const [modalState, setModalState] = useAtom(bankRecDraftJEModalAtom)
    const isOpen = modalState.voucher !== null

    const onOpenChange = (open: boolean) => {
        if (!open) {
            setModalState({ voucher: null })
        }
    }

    return (
        <Dialog open={isOpen} onOpenChange={onOpenChange}>
            <DialogContent className='max-w-lg'>
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <FileEdit className="w-5 h-5" />
                        {_("Submit Draft Journal Entry")}
                    </DialogTitle>
                    <DialogDescription>
                        {_("Update dates and remarks before submitting and reconciling the Journal Entry.")}
                    </DialogDescription>
                </DialogHeader>
                {modalState.voucher && <DraftJEForm />}
            </DialogContent>
        </Dialog>
    )
}

const DraftJEForm = () => {
    const selectedBankAccount = useAtomValue(selectedBankAccountAtom)
    const selectedTransaction = useAtomValue(bankRecSelectedTransactionAtom(selectedBankAccount?.name ?? ''))
    const [modalState, setModalState] = useAtom(bankRecDraftJEModalAtom)
    const voucher = modalState.voucher!

    const transaction = selectedTransaction?.[0]

    const form = useForm<DraftJEFormData>({
        defaultValues: {
            posting_date: transaction?.date ?? voucher.posting_date,
            cheque_date: transaction?.date ?? voucher.reference_date,
            user_remark: voucher.user_remark ?? '',
        }
    })

    const onReconcile = useRefreshUnreconciledTransactions()
    const setBankRecUnreconcileModalAtom = useSetAtom(bankRecUnreconcileModalAtom)

    const { call, loading, error } = useFrappePostCall('mint.apis.bank_reconciliation.submit_draft_je_and_reconcile')

    const onClose = () => {
        setModalState({ voucher: null })
    }

    const onSubmit = (data: DraftJEFormData) => {
        if (!transaction) return

        call({
            bank_transaction_name: transaction.name,
            journal_entry_name: voucher.name,
            posting_date: data.posting_date,
            cheque_date: data.cheque_date,
            user_remark: data.user_remark,
        }).then(() => {
            toast.success(_("Journal Entry submitted and reconciled"), {
                duration: 4000,
                closeButton: true,
                action: {
                    label: _("Undo"),
                    onClick: () => setBankRecUnreconcileModalAtom(transaction.name)
                },
                actionButtonStyle: {
                    backgroundColor: "rgb(0, 138, 46)"
                }
            })
            onReconcile(transaction)
            onClose()
        }).catch((err) => {
            console.error(err)
            toast.error(_("Error"), {
                duration: 5000,
                description: getErrorMessage(err)
            })
        })
    }

    return (
        <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)}>
                <div className='flex flex-col gap-4'>
                    {error && <ErrorBanner error={error} />}

                    {/* Journal Entry Info */}
                    <div className='bg-muted/50 p-4 rounded-md space-y-2'>
                        <div className="flex items-center justify-between">
                            <span className="font-medium">{voucher.name}</span>
                            <Badge variant='outline' className="border-orange-400 text-orange-600 bg-orange-50">
                                <FileEdit className="w-3 h-3 mr-1" />
                                {_("Draft")}
                            </Badge>
                        </div>
                        <div className="text-sm text-muted-foreground">
                            {_("Amount")}: <span className="font-mono font-medium text-foreground">{formatCurrency(voucher.paid_amount, transaction?.currency ?? 'CHF')}</span>
                        </div>
                        {voucher.user_remark && (
                            <div className="text-sm text-muted-foreground flex items-start gap-2">
                                <MessageSquare className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                <span className="line-clamp-2">{voucher.user_remark}</span>
                            </div>
                        )}
                    </div>

                    {/* Bank Transaction Info */}
                    {transaction && (
                        <div className='bg-blue-50 dark:bg-blue-950/20 p-4 rounded-md space-y-1'>
                            <div className="text-sm font-medium text-blue-700 dark:text-blue-300 flex items-center gap-2">
                                <Calendar className="w-4 h-4" />
                                {_("Bank Transaction Date")}: {formatDate(transaction.date)}
                            </div>
                            <div className="text-xs text-muted-foreground">
                                {_("The dates will be updated to match the bank transaction.")}
                            </div>
                        </div>
                    )}

                    {/* Form Fields */}
                    <div className='grid grid-cols-2 gap-4'>
                        <DateField
                            name='posting_date'
                            label={_("Posting Date")}
                            isRequired
                            inputProps={{ autoFocus: false }}
                        />
                        <DateField
                            name='cheque_date'
                            label={_("Reference Date")}
                            isRequired
                            inputProps={{ autoFocus: false }}
                        />
                    </div>

                    <SmallTextField
                        name='user_remark'
                        label={_("Remarks")}
                        inputProps={{
                            placeholder: _("Add a remark for this entry...")
                        }}
                    />

                    <DialogFooter>
                        <DialogClose asChild>
                            <Button variant={'outline'} disabled={loading}>{_("Cancel")}</Button>
                        </DialogClose>
                        <Button type='submit' disabled={loading} className="bg-green-600 hover:bg-green-700">
                            {loading ? _("Submitting...") : _("Submit & Reconcile")}
                        </Button>
                    </DialogFooter>
                </div>
            </form>
        </Form>
    )
}

export default DraftJEModal
