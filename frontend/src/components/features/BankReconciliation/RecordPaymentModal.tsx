import { atom, useAtom, useAtomValue, useSetAtom } from "jotai"
import { bankRecRecordPaymentModalAtom, bankRecSelectedTransactionAtom, bankRecUnreconcileModalAtom, SelectedBank, selectedBankAccountAtom } from "./bankRecAtoms"
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogHeader, DialogFooter, DialogClose, DialogTrigger } from "@/components/ui/dialog"
import _ from "@/lib/translate"
import { UnreconciledTransaction, useGetRuleForTransaction, useRefreshUnreconciledTransactions, useUpdateActionLog } from "./utils"
import { useFieldArray, useForm, useFormContext, useWatch } from "react-hook-form"
import { getCompanyCostCenter, getCompanyCurrency } from "@/lib/company"
import { FrappeConfig, FrappeContext, useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk"
import { toast } from "sonner"
import ErrorBanner from "@/components/ui/error-banner"
import { Button } from "@/components/ui/button"
import SelectedTransactionDetails from "./SelectedTransactionDetails"
import { AccountFormField, CurrencyFormField, DataField, DateField, LinkFormField, PartyTypeFormField, SmallTextField } from "@/components/ui/form-elements"
import { Form } from "@/components/ui/form"
import { ChangeEvent, useCallback, useContext, useEffect, useRef, useMemo, useState } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
import { AlertCircleIcon, Plus, Trash2, X } from "lucide-react"
import { flt, formatCurrency } from "@/lib/numbers"
import { cn } from "@/lib/utils"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { PaymentEntry } from "@/types/Accounts/PaymentEntry"
import { H4 } from "@/components/ui/typography"
import { usePaymentEntryCalculations } from "@/hooks/usePaymentEntryCalculations"
import { MissingFiltersBanner } from "./MissingFiltersBanner"
import { formatDate } from "@/lib/date"
import { slug } from "@/lib/frappe"
import MarkdownRenderer from "@/components/ui/markdown"
import { Separator } from "@/components/ui/separator"
import { PaymentEntryDeduction } from "@/types/Accounts/PaymentEntryDeduction"
import { TableLoader } from "@/components/ui/loaders"
import SelectedTransactionsTable from "./SelectedTransactionsTable"
import { useCurrentCompany } from "@/hooks/useCurrentCompany"
import { Label } from "@/components/ui/label"
import { FileDropzone } from "@/components/ui/file-dropzone"
import { BankTransaction } from "@/types/Accounts/BankTransaction"
import FileUploadBanner from "@/components/common/FileUploadBanner"

// Hook pour calcul TVA sur les déductions
const useDeductionsVatCalculation = () => {
    const { call } = useFrappePostCall<{
        message: {
            deductions: PaymentEntryDeduction[]
            total_deductions: number
            has_vat: boolean
        }
    }>('mint.apis.bank_reconciliation.calculate_deductions_with_vat')

    return { calculateVat: call }
}

const RecordPaymentModal = () => {

    const [isOpen, setIsOpen] = useAtom(bankRecRecordPaymentModalAtom)

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogContent className='!max-w-[min(95vw,1400px)] w-[min(95vw,1400px)] sm:!max-w-[min(95vw,1400px)]'>
                <DialogHeader>
                    <DialogTitle>{_("Record Payment")}</DialogTitle>
                    <DialogDescription>
                        {_("Record a payment entry against a customer or supplier")}
                    </DialogDescription>
                </DialogHeader>
                <RecordPaymentModalContent />
            </DialogContent>
        </Dialog>
    )
}


const RecordPaymentModalContent = () => {

    const selectedBankAccount = useAtomValue(selectedBankAccountAtom)

    const selectedTransaction = useAtomValue(bankRecSelectedTransactionAtom(selectedBankAccount?.name ?? ''))

    if (!selectedTransaction || !selectedBankAccount) {
        return <div className='p-4'>
            <span className='text-center'>No transaction selected</span>
        </div>
    }

    if (selectedTransaction.length === 1) {
        return <PaymentEntryForm
            selectedBankAccount={selectedBankAccount}
            selectedTransaction={selectedTransaction[0]} />
    }

    return <BulkPaymentEntryForm
        transactions={selectedTransaction} />

}

const BulkPaymentEntryForm = ({ transactions }: { transactions: UnreconciledTransaction[] }) => {


    const setIsOpen = useSetAtom(bankRecRecordPaymentModalAtom)

    const form = useForm<{
        party_type: PaymentEntry['party_type'],
        party: PaymentEntry['party'],
        party_name: PaymentEntry['party_name'],
        /** GL account that's paid from or paid to */
        account: string
        mode_of_payment: PaymentEntry['mode_of_payment']
    }>()

    const { call: createPaymentEntry, loading, error } = useFrappePostCall<{ message: { transaction: BankTransaction, payment_entry: PaymentEntry }[] }>('mint.apis.bank_reconciliation.create_bulk_payment_entry_and_reconcile')

    const onReconcile = useRefreshUnreconciledTransactions()

    const addToActionLog = useUpdateActionLog()

    const onSubmit = (data: { party_type: PaymentEntry['party_type'], party: PaymentEntry['party'], account: string, mode_of_payment: PaymentEntry['mode_of_payment'] }) => {

        createPaymentEntry({
            bank_transaction_names: transactions.map((transaction) => transaction.name),
            party_type: data.party_type,
            party: data.party,
            account: data.account
        }).then(({ message }) => {

            addToActionLog({
                type: 'payment',
                timestamp: (new Date()).getTime(),
                isBulk: true,
                items: message.map((item) => ({
                    bankTransaction: item.transaction,
                    voucher: {
                        reference_doctype: "Payment Entry",
                        reference_name: item.payment_entry.name,
                        reference_no: item.payment_entry.reference_no,
                        reference_date: item.payment_entry.reference_date,
                        posting_date: item.payment_entry.posting_date,
                        party_type: item.payment_entry.party_type,
                        party: item.payment_entry.party,
                        doc: item.payment_entry,
                    }
                })),
                bulkCommonData: {
                    party_type: data.party_type,
                    party: data.party,
                    account: data.account,
                }
            })

            toast.success(_("Payment Recorded"), {
                duration: 4000,
                closeButton: true,
            })
            onReconcile(transactions[transactions.length - 1])
            setIsOpen(false)
        })
    }

    const party_type = useWatch({ control: form.control, name: 'party_type' })

    const party_name = useWatch({ control: form.control, name: 'party_name' })

    const party = useWatch({ control: form.control, name: 'party' })

    const { call } = useContext(FrappeContext) as FrappeConfig

    const currentCompany = useCurrentCompany()

    const company = transactions && transactions.length > 0 ? transactions[0].company : (currentCompany ?? '')

    const onPartyChange = (event: ChangeEvent<HTMLInputElement>) => {
        // Fetch the party and account
        if (event.target.value) {
            call.get('mint.apis.bank_reconciliation.get_party_details', {
                company: company,
                party_type: party_type,
                party: event.target.value
            }).then((res) => {
                form.setValue('party_name', res.message.party_name)
                form.setValue('account', res.message.party_account)
            })
        } else {
            // Clear the party and account
            form.setValue('party_name', '')
            form.setValue('account', '')
        }

    }

    return <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className='flex flex-col gap-4'>

                {error && <ErrorBanner error={error} />}

                <SelectedTransactionsTable />

                <div className='grid grid-cols-8 gap-4'>
                    <div className="col-span-1">
                        <PartyTypeFormField
                            name='party_type'
                            label={_("Party Type")}
                            isRequired
                            inputProps={{
                                triggerProps: {
                                    className: 'w-full'
                                },
                            }}
                            rules={{
                                required: "Party Type is required"
                            }}
                        />
                    </div>
                    <div className="col-span-3">
                        {party_type ? <LinkFormField
                            name={`party`}
                            label={_("Party")}
                            isRequired
                            rules={{
                                onChange: onPartyChange,
                                required: _('Party is required')
                            }}
                            // Show the party name if it's different from the party - usually the case when a naming series is used
                            formDescription={party_name !== party ? party_name : undefined}
                            doctype={party_type}

                        /> : <DataField
                            name={`party`}
                            label={_("Party")}
                            rules={{
                                required: _('Party is required')
                            }}
                            isRequired
                            inputProps={{
                                disabled: true,
                            }}
                        />
                        }


                    </div>

                    <div className="col-span-2">
                        <AccountFormField
                            name='account'
                            label={_("Account")}
                            isRequired
                            rules={{
                                required: _('Account is required')
                            }}
                            account_type={['Payable', 'Receivable']}
                            filterFunction={(acc) => {
                                if (party_type === 'Supplier' || party_type === 'Employee' || party_type === 'Shareholder') {
                                    return acc.account_type === 'Payable'
                                } else if (party_type === 'Customer') {
                                    return acc.account_type === 'Receivable'
                                }
                                return true
                            }}
                        />
                    </div>

                    <div className="col-span-2">
                        <LinkFormField
                            name='mode_of_payment'
                            label={_("Mode of Payment")}
                            doctype="Mode of Payment"
                        />
                    </div>

                </div>


                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant={'outline'} disabled={loading}>{_("Cancel")}</Button>
                    </DialogClose>
                    <Button type='submit' disabled={loading}>{_("Submit")}</Button>
                </DialogFooter>
            </div>
        </form>
    </Form>

}

const PaymentEntryForm = ({ selectedTransaction, selectedBankAccount }: { selectedTransaction: UnreconciledTransaction, selectedBankAccount: SelectedBank }) => {

    const setIsOpen = useSetAtom(bankRecRecordPaymentModalAtom)

    const onClose = () => {
        setIsOpen(false)
    }

    const { data: rule } = useGetRuleForTransaction(selectedTransaction)

    const isWithdrawal = (selectedTransaction.withdrawal && selectedTransaction.withdrawal > 0) ? true : false

    const form = useForm<PaymentEntry>({
        defaultValues: {
            payment_type: isWithdrawal ? 'Pay' : 'Receive',
            bank_account: selectedTransaction.bank_account,
            company: selectedTransaction?.company,
            // If the money is paid, it's usually to a supplier. If it's received, it's usually from a customer
            party_type: rule?.party_type ?? (isWithdrawal ? 'Supplier' : 'Customer'),
            party: rule?.party ?? '',
            // If the transaction is a withdrawal, set the paid from to the selected bank account
            paid_from: isWithdrawal ? selectedBankAccount.account : (rule?.account ?? ''),
            // If the transaction is a deposit, set the paid to to the selected bank account
            paid_to: !isWithdrawal ? selectedBankAccount.account : (rule?.account ?? ''),
            // Set the amount to the amount of the selected transaction
            paid_amount: selectedTransaction.unallocated_amount,
            base_paid_amount: selectedTransaction.unallocated_amount,
            received_amount: selectedTransaction.unallocated_amount,
            base_received_amount: selectedTransaction.unallocated_amount,
            reference_date: selectedTransaction.date,
            posting_date: selectedTransaction.date,
            reference_no: (selectedTransaction.reference_number || selectedTransaction.description || '').slice(0, 140),
            target_exchange_rate: 1,
            source_exchange_rate: 1,
        }
    })

    const onReconcile = useRefreshUnreconciledTransactions()

    const setUnpaidInvoiceOpen = useSetAtom(isUnpaidInvoicesButtonOpen)

    useEffect(() => {
        if (rule && rule.party && rule.party_type && rule.account) {
            setUnpaidInvoiceOpen(true)
        }

    }, [rule, setUnpaidInvoiceOpen])

    // Auto-focus on Party field when modal opens
    useEffect(() => {
        const timer = setTimeout(() => {
            const dialog = document.querySelector('[role="dialog"]')
            if (dialog) {
                const comboboxButtons = dialog.querySelectorAll('button[role="combobox"]')
                // The first combobox in the form is PartyType, the second is Party
                const partyButton = comboboxButtons[1] as HTMLButtonElement
                if (partyButton) {
                    partyButton.focus()
                    partyButton.click()
                }
            }
        }, 300)
        return () => clearTimeout(timer)
    }, [])

    const { call: createPaymentEntry, loading, error, isCompleted } = useFrappePostCall<{ message: { transaction: BankTransaction, payment_entry: PaymentEntry } }>('mint.apis.bank_reconciliation.create_payment_entry_and_reconcile')

    const setBankRecUnreconcileModalAtom = useSetAtom(bankRecUnreconcileModalAtom)

    const addToActionLog = useUpdateActionLog()

    const { file: frappeFile } = useContext(FrappeContext) as FrappeConfig

    const [isUploading, setIsUploading] = useState(false)
    const [uploadProgress, setUploadProgress] = useState(0)

    const [files, setFiles] = useState<File[]>([])

    const onSubmit = (data: PaymentEntry) => {

        createPaymentEntry({
            bank_transaction_name: selectedTransaction.name,
            payment_entry_doc: {
                ...data,
                custom_remarks: data.remarks ? true : false
            }
        }).then(async ({ message }) => {
            addToActionLog({
                type: 'payment',
                timestamp: (new Date()).getTime(),
                isBulk: false,
                items: [
                    {
                        bankTransaction: message.transaction,
                        voucher: {
                            reference_doctype: "Payment Entry",
                            reference_name: message.payment_entry.name,
                            reference_no: message.payment_entry.reference_no,
                            reference_date: message.payment_entry.reference_date,
                            posting_date: message.payment_entry.posting_date,
                            doc: message.payment_entry,
                        }
                    }
                ]
            })
            toast.success(_("Payment Entry Created"), {
                duration: 4000,
                closeButton: true,
                action: {
                    label: _("Undo"),
                    onClick: () => setBankRecUnreconcileModalAtom(selectedTransaction.name)
                },
                actionButtonStyle: {
                    backgroundColor: "rgb(0, 138, 46)"
                }
            })

            if (files.length > 0) {
                setIsUploading(true)

                const uploadPromises = files.map(f => {
                    return frappeFile.uploadFile(f, {
                        isPrivate: true,
                        doctype: "Payment Entry",
                        docname: message.payment_entry.name,
                    }, (_bytesUploaded, _totalBytes, progress) => {

                        setUploadProgress((currentProgress) => {
                            //If there are multiple files, we need to add the progress to the current progress
                            return currentProgress + ((progress?.progress ?? 0) / files.length)
                        })

                    })
                })

                return Promise.all(uploadPromises).then(() => {
                    setUploadProgress(0)
                    setIsUploading(false)
                })
            } else {
                return Promise.resolve()
            }

        }).then(() => {
            setUploadProgress(0)
            setIsUploading(false)
            onReconcile(selectedTransaction)
            onClose()
        })
    }

    if (isUploading && isCompleted) {
        return <FileUploadBanner uploadProgress={uploadProgress} />
    }

    return <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className='flex flex-col gap-4'>
                {error && <ErrorBanner error={error} />}
                <div className='grid grid-cols-2 gap-4 items-start'>
                    <div className='flex flex-col gap-3'>
                        <SelectedTransactionDetails transaction={selectedTransaction} />
                        <DataField name='reference_no' label={_("Reference")} isRequired inputProps={{ autoFocus: false }} />
                    </div>
                    <div className='grid grid-cols-2 gap-x-4 gap-y-2'>
                        <DateField
                            name='posting_date'
                            label={_("Posting Date")}
                            isRequired
                            inputProps={{ autoFocus: false }}
                        />
                        <DateField
                            name='reference_date'
                            label={_("Reference Date")}
                            isRequired
                            inputProps={{ autoFocus: false }}
                        />
                        <PartyTypeFormField
                            name='party_type'
                            label={isWithdrawal ? _("Paid to (Party Type)") : _("Received from (Party Type)")}
                            isRequired
                            inputProps={{
                                triggerProps: {
                                    className: 'w-full'
                                },
                                type: isWithdrawal ? 'Payable' : 'Receivable'
                            }}
                            rules={{
                                required: "Party Type is required"
                            }}
                        />
                        <PartyField />
                        <AccountDropdown isWithdrawal={isWithdrawal} />
                        <LinkFormField
                            name='mode_of_payment'
                            label={_("Mode of Payment")}
                            doctype="Mode of Payment"
                        />
                    </div>
                </div>

                <Separator />

                <InvoicesSection currency={selectedTransaction.currency ?? getCompanyCurrency(selectedTransaction.company ?? '')} />

                <Separator />

                <OtherChargesSection currency={selectedTransaction.currency ?? getCompanyCurrency(selectedTransaction.company ?? '')} />

                <Separator />

                <div className="grid grid-cols-2 gap-4">
                    <SmallTextField
                        name='remarks'
                        label={_("Custom Remarks")}
                        formDescription={_("This will be auto-populated if not set.")}
                    />
                    <div
                        data-slot="form-item"
                        className="flex flex-col gap-2"
                    >
                        <Label>{_("Attachments")}</Label>
                        <FileDropzone files={files} setFiles={setFiles} />
                    </div>
                </div>
                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant={'outline'} disabled={loading}>{_("Cancel")}</Button>
                    </DialogClose>
                    <Button type='submit' disabled={loading || isUploading}>{_("Submit")}</Button>
                </DialogFooter>
            </div>
        </form>
    </Form>
}

const isUnpaidInvoicesButtonOpen = atom(false)

const PartyField = () => {

    const { control, setValue } = useFormContext<PaymentEntry>()

    const party_type = useWatch({
        control,
        name: `party_type`
    })

    const { call } = useContext(FrappeContext) as FrappeConfig

    const company = useWatch({ control, name: 'company' })

    const party_name = useWatch({ control, name: 'party_name' })

    const type = useWatch({ control, name: 'payment_type' })

    const party = useWatch({ control, name: 'party' })

    const setIsOpen = useSetAtom(isUnpaidInvoicesButtonOpen)

    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        // Fetch the party and account
        if (event.target.value) {
            call.get('mint.apis.bank_reconciliation.get_party_details', {
                company: company,
                party_type: party_type,
                party: event.target.value
            }).then((res) => {
                setValue('party_name', res.message.party_name)
                if (type === 'Pay') {
                    setValue('paid_to', res.message.party_account)
                } else {
                    setValue('paid_from', res.message.party_account)
                }
                setIsOpen(true)
            })
        } else {
            // Clear the party and account
            setValue('party_name', '')
            if (type === 'Pay') {
                setValue('paid_to', '')
            } else {
                setValue('paid_from', '')
            }
        }

    }

    if (!party_type) {
        return <DataField
            name={`party`}
            label={_("Party")}
            isRequired
            inputProps={{
                disabled: true,
            }}
        />
    }

    return <LinkFormField
        name={`party`}
        label={_("Party")}
        rules={{
            onChange
        }}
        // Show the party name if it's different from the party - usually the case when a naming series is used
        formDescription={party_name !== party ? party_name : undefined}
        doctype={party_type}

    />
}


const AccountDropdown = ({ isWithdrawal }: { isWithdrawal: boolean }) => {

    // If it's a withdrawal, then we need to show the "Paid to" account
    // If it's a deposit, then we need to show the "Paid from" account

    const { control, setValue } = useFormContext<PaymentEntry>()

    const party_type = useWatch({ control, name: 'party_type' })

    const setIsOpen = useSetAtom(isUnpaidInvoicesButtonOpen)

    const accountTypes: string[] | undefined = useMemo(() => {
        if (party_type === 'Supplier' || party_type === 'Employee' || party_type === 'Shareholder') {
            return ['Payable']
        } else if (party_type === 'Customer') {
            return ['Receivable']
        }
        return undefined
    }, [party_type])

    const onAccountChange = (event: ChangeEvent<HTMLInputElement>) => {
        if (event.target.value) {
            setValue('unallocated_amount', 0)
            setValue('total_allocated_amount', 0)
            setValue('difference_amount', 0)
            setValue('references', [])
            setIsOpen(true)
        }
    }


    if (isWithdrawal) {
        return <AccountFormField
            name='paid_to'
            label={_("Paid To (GL Account)")}
            isRequired
            rules={{
                required: 'Paid To is required',
                onChange: onAccountChange
            }}
            account_type={accountTypes}
        />

    } else {
        return <AccountFormField
            name='paid_from'
            label={_("Paid From (GL Account)")}
            isRequired
            rules={{
                required: 'Paid From is required',
                onChange: onAccountChange
            }}
            account_type={accountTypes}
        />
    }

}


const InvoicesSection = ({ currency }: { currency: string }) => {

    const { setTotalAllocatedAmount } = usePaymentEntryCalculations()

    const { control } = useFormContext<PaymentEntry>()
    const { fields, remove } = useFieldArray({
        control,
        name: 'references'
    })

    const [selectedRows, setSelectedRows] = useState<number[]>([])

    const onSelectRow = useCallback((index: number) => {
        setSelectedRows(prev => {
            if (prev.includes(index)) {
                return prev.filter(i => i !== index)
            }
            return [...prev, index]
        })
    }, [])

    const onSelectAll = useCallback(() => {
        setSelectedRows(prev => {
            if (prev.length === fields.length) {
                return []
            }
            return [...fields.map((_, index) => index)]
        })
    }, [fields])

    const onRemove = useCallback(() => {
        remove(selectedRows)
        setSelectedRows([])
    }, [remove, selectedRows])

    return <div className="flex flex-col gap-2">
        <div className="flex gap-4 items-center">
            <H4 className="text-base">{_("Invoices")}</H4>
            <GetUnpaidInvoicesButton />
        </div>
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead><Checkbox
                        disabled={fields.length === 0}
                        // Make this accessible to screen readers
                        aria-label={_("Select all")}
                        checked={selectedRows.length > 0 && selectedRows.length === fields.length}
                        onCheckedChange={onSelectAll} /></TableHead>
                    <TableHead>{_("Reference Document")}</TableHead>
                    <TableHead>{_("Invoice No")}</TableHead>
                    <TableHead>{_("Due Date")}</TableHead>
                    <TableHead className="text-right">{_("Grand Total")}</TableHead>
                    <TableHead className="text-right">{_("Outstanding")}</TableHead>
                    <TableHead className="text-right">{_("Allocated")}</TableHead>
                    <TableHead className='w-14'></TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {fields.map((field, index) => (
                    <TableRow key={field.id}>
                        <TableCell>
                            <Checkbox
                                checked={selectedRows.includes(index)}
                                onCheckedChange={() => onSelectRow(index)}
                                // Make this accessible to screen readers
                                aria-label={_("Select row {0}", [String(index + 1)])}
                            />
                        </TableCell>

                        <TableCell>
                            <a
                                target="_blank"
                                className="underline underline-offset-2"
                                href={`/app/${slug(field.reference_doctype)}/${field.reference_name}`}>{field.reference_doctype}: {field.reference_name}</a>
                        </TableCell>
                        <TableCell>
                            {field.bill_no ?? "-"}
                        </TableCell>
                        <TableCell>
                            {formatDate(field.due_date)}
                        </TableCell>
                        <TableCell className="text-right">
                            {formatCurrency(field.total_amount, currency)}
                        </TableCell>
                        <TableCell className="text-right">
                            {formatCurrency(field.outstanding_amount, currency)}
                        </TableCell>
                        <TableCell className="text-right max-w-36">
                            <CurrencyFormField
                                name={`references.${index}.allocated_amount`}
                                label={_("Allocated")}
                                isRequired
                                rules={{
                                    onChange: () => setTotalAllocatedAmount()
                                }}
                                hideLabel
                                currency={currency}
                            />
                        </TableCell>
                        <TableCell>
                            <DifferenceButton index={index} currency={currency} />
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
        <div className="flex justify-between gap-2">
            <div className="flex gap-2 justify-end">
                {selectedRows.length > 0 && <div>
                    <Button size='sm' type='button' variant={'destructive'} onClick={onRemove}><Trash2 /> {_("Remove")}</Button>
                </div>}
            </div>
            <Summary currency={currency} />
        </div>
    </div>

}

const DifferenceButton = ({ index, currency }: { index: number, currency: string }) => {

    const { setTotalAllocatedAmount } = usePaymentEntryCalculations()

    const { control, setValue } = useFormContext<PaymentEntry>()

    const outstandingAmount = useWatch({
        control,
        name: `references.${index}.outstanding_amount`
    }) ?? 0

    const allocatedAmount = useWatch({
        control,
        name: `references.${index}.allocated_amount`
    }) ?? 0

    const difference = flt(outstandingAmount - allocatedAmount, 2)

    const onPayInFull = useCallback(() => {
        setValue(`references.${index}.allocated_amount`, outstandingAmount, { shouldDirty: true })
        setTotalAllocatedAmount()
    }, [outstandingAmount, index, setValue, setTotalAllocatedAmount])

    if (difference !== 0) {

        return <Tooltip>
            <TooltipTrigger asChild>
                <Button
                    variant='ghost'
                    onClick={onPayInFull}
                    size='icon'
                    className="text-muted-foreground">
                    <AlertCircleIcon />
                </Button>
            </TooltipTrigger>
            <TooltipContent>
                {_("The invoice is not fully allocated as there is a difference of {0}.", [formatCurrency(difference, currency) ?? ''])}
                <br />
                {_("Click to pay in full.")}
            </TooltipContent>
        </Tooltip>

    }

    return null
}

const Summary = ({ currency }: { currency: string }) => {

    const { control, setValue, getValues } = useFormContext<PaymentEntry>()

    const { setUnallocatedAmount } = usePaymentEntryCalculations()

    const amount = useWatch({
        control,
        name: 'paid_amount'
    })

    const unallocatedAmount = useWatch({
        control,
        name: 'unallocated_amount'
    })

    const allocatedAmount = useWatch({
        control,
        name: 'total_allocated_amount'
    })

    const differenceAmount = useWatch({
        control,
        name: 'difference_amount'
    })

    const onAddRow = useCallback((amount?: number) => {
        if (amount) {
            const deductions = getValues('deductions') ?? []

            setValue('deductions', [...deductions, {
                amount: amount,
                account: '',
                cost_center: getCompanyCostCenter(getValues('company')),
                description: ''
            } as PaymentEntryDeduction])

            setUnallocatedAmount()
        }
    }, [setUnallocatedAmount, getValues, setValue])

    const TextComponent = ({ className, children }: { className?: string, children: React.ReactNode }) => {
        return <span className={cn("w-32 text-right font-medium text-sm font-mono", className)}>{children}</span>
    }

    return <div className="flex flex-col gap-2 items-end">
        <div className="flex gap-2 justify-between">
            <TextComponent>{_("Total Amount")}</TextComponent>
            <TextComponent>{formatCurrency(amount, currency)}</TextComponent>
        </div>
        <div className="flex gap-2 justify-between">
            <TextComponent>{_("Allocated")}</TextComponent>
            <TextComponent>{formatCurrency(allocatedAmount, currency)}</TextComponent>
        </div>

        {(unallocatedAmount && unallocatedAmount !== 0) ? <div className="flex gap-2 justify-between">
            <TextComponent>{_("Unallocated")}</TextComponent>
            <Tooltip>
                <TooltipTrigger asChild>
                    <Button type='button' variant='link' className="p-0 text-destructive underline h-fit" role='button' onClick={() => onAddRow(unallocatedAmount ?? 0)}>
                        <TextComponent className='text-destructive'>{formatCurrency(unallocatedAmount, currency)}</TextComponent>
                    </Button>
                </TooltipTrigger>
                <TooltipContent>
                    {_("Add a charge to the payment entry with the unallocated amount")}
                </TooltipContent>
            </Tooltip>


        </div> : null}

        {(differenceAmount && differenceAmount !== 0) ? <div className="flex gap-2 justify-between">
            <TextComponent>{_("Difference")}</TextComponent>
            <Tooltip>
                <TooltipTrigger asChild>
                    <Button type='button' variant='link' className="p-0 text-destructive underline h-fit" role='button' onClick={() => onAddRow(differenceAmount ?? 0)}>
                        <TextComponent className='text-destructive'>{formatCurrency(differenceAmount, currency)}</TextComponent>
                    </Button>
                </TooltipTrigger>
                <TooltipContent>
                    {_("Add a charge to the payment entry with the difference amount")}
                </TooltipContent>
            </Tooltip>


        </div> : null}

    </div>
}
const GetUnpaidInvoicesButton = () => {

    const [isOpen, setIsOpen] = useAtom(isUnpaidInvoicesButtonOpen)

    const { control } = useFormContext<PaymentEntry>()

    const partyType = useWatch({ control, name: 'party_type' })
    const party = useWatch({ control, name: 'party' })
    const partyName = useWatch({ control, name: 'party_name' })
    const amount = useWatch({ control, name: 'paid_amount' })

    return <>

        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            {partyType && party && <DialogTrigger asChild>
                <Button variant='outline' size='sm' type='button'>Get Unpaid Invoices</Button>
            </DialogTrigger>}
            <DialogContent className='!max-w-[min(75vw,1100px)] w-[min(75vw,1100px)] sm:!max-w-[min(75vw,1100px)]'>
                <DialogHeader>
                    <DialogTitle>Select Invoices</DialogTitle>
                    <DialogDescription>Unpaid invoices from {partyName} for {formatCurrency(amount)}.</DialogDescription>
                </DialogHeader>
                <FetchInvoicesModal onClose={() => setIsOpen(false)} />
            </DialogContent>
        </Dialog>
    </>
}

interface OutstandingInvoice {
    voucher_type: string
    voucher_no: string
    bill_no?: string
    due_date: string
    invoice_amount: number
    outstanding_amount: number,
    payment_term?: string,
    payment_term_outstanding?: string,
    account?: string,
    allocated_amount?: number,
}
const FetchInvoicesModal = ({ onClose }: { onClose: () => void }) => {

    const { getValues, setValue } = useFormContext<PaymentEntry>()

    const { allocatePartyAmount } = usePaymentEntryCalculations()

    const { data, isLoading, error } = useFrappeGetCall<{
        message: OutstandingInvoice[],
        _server_messages?: string
    }>('erpnext.accounts.doctype.payment_entry.payment_entry.get_outstanding_reference_documents', {
        args: {
            company: getValues('company'),
            posting_date: getValues('posting_date'),
            party_type: getValues('party_type'),
            party: getValues('party'),
            party_account: getValues('payment_type') === 'Pay' ? getValues('paid_to') : getValues('paid_from'),
            get_outstanding_invoices: true,
            allocate_payment_amount: 1
        }
    })

    const message = useMemo(() => {
        if (data && data._server_messages) {
            const message = JSON.parse(JSON.parse(data._server_messages)[0])

            return message.message
        }
        return ''
    }, [data])

    const [selectedInvoices, setSelectedInvoices] = useState<OutstandingInvoice[]>([])

    const onSelectRow = (row: OutstandingInvoice) => {
        if (selectedInvoices.includes(row)) {
            setSelectedInvoices(selectedInvoices.filter((invoice) => invoice !== row))
        } else {
            setSelectedInvoices([...selectedInvoices, row])
        }
    }

    const { call: allocateAmountToReferences, loading: allocateAmountToReferencesLoading, error: allocateAmountToReferencesError } = useFrappePostCall('run_doc_method')

    const onSelect = () => {

        allocateAmountToReferences({
            args: {
                paid_amount: getValues("payment_type") === "Pay" ? getValues("paid_amount") : getValues("received_amount"),
                allocate_payment_amount: 1,
                paid_amount_change: false
            },
            method: 'allocate_amount_to_references',
            docs: {
                doctype: 'Payment Entry',
                ...getValues(),
                name: "new-payment-entry-1",
                __unsaved: 1,
                __islocal: 1,
                references: selectedInvoices.map((ref: OutstandingInvoice) => ({
                    reference_doctype: ref.voucher_type,
                    reference_name: ref.voucher_no,
                    due_date: ref.due_date,
                    total_amount: ref.invoice_amount,
                    outstanding_amount: ref.outstanding_amount,
                    bill_no: ref.bill_no,
                    payment_term: ref.payment_term,
                    payment_term_outstanding: ref.payment_term_outstanding,
                    allocated_amount: ref.allocated_amount,
                    account: ref.account,
                    exchange_rate: 1,
                }))
            }
        }).then((res) => {
            const doc = res.docs[0]
            setValue('references', doc.references)
            setValue('unallocated_amount', doc.unallocated_amount)
            setValue('total_allocated_amount', doc.total_allocated_amount)
            setValue('difference_amount', doc.difference_amount)

            allocatePartyAmount(getValues("payment_type") === "Pay" ? getValues("paid_amount") : getValues("received_amount"))

            onClose()
        })
    }
    return <div className="flex flex-col gap-4">
        {isLoading ? <TableLoader columns={6} /> : null}
        {error && <ErrorBanner error={error} />}
        {error && <ErrorBanner error={allocateAmountToReferencesError} />}
        {message ? <MissingFiltersBanner text={<MarkdownRenderer content={message} />} /> : null}

        {data?.message && data?.message?.length > 0 ? <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>
                        <Checkbox checked={selectedInvoices.length === data?.message?.length} onCheckedChange={(checked) => {
                            if (checked) {
                                setSelectedInvoices(data?.message)
                            } else {
                                setSelectedInvoices([])
                            }
                        }} />
                    </TableHead>
                    <TableHead>
                        Type
                    </TableHead>
                    <TableHead>
                        Name
                    </TableHead>
                    <TableHead>
                        Invoice No
                    </TableHead>
                    <TableHead>
                        Due Date
                    </TableHead>
                    <TableHead className="text-right">
                        Grand Total
                    </TableHead>
                    <TableHead className="text-right">
                        Outstanding
                    </TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {data.message.map((ref) => (
                    <TableRow
                        key={ref.voucher_no}
                        onClick={(e) => {
                            const target = e.target as HTMLElement
                            // Do not select the checkbox if the user clicks on the checkbox or the link
                            if (target.tagName !== 'INPUT' && !target.className.includes('chakra-checkbox') && !target.className.includes('chakra-link')) {
                                onSelectRow(ref)
                            }
                        }}
                        className="cursor-pointer">
                        <TableCell>
                            <Checkbox checked={selectedInvoices.includes(ref)}
                                onCheckedChange={(checked) => {
                                    if (checked) {
                                        setSelectedInvoices([...selectedInvoices, ref])
                                    } else {
                                        setSelectedInvoices(selectedInvoices.filter((invoice) => invoice !== ref))
                                    }
                                }}
                            />
                        </TableCell>
                        <TableCell>
                            {ref.voucher_type}
                        </TableCell>
                        <TableCell>
                            <a
                                target="_blank"
                                className="underline underline-offset-2"
                                href={`/app/${slug(ref.voucher_type)}/${ref.voucher_no}`}>{ref.voucher_no}</a>
                        </TableCell>
                        <TableCell>
                            {ref.bill_no ?? "-"}
                        </TableCell>
                        <TableCell>
                            {formatDate(ref.due_date)}
                        </TableCell>
                        <TableCell className="text-right">
                            {formatCurrency(ref.invoice_amount)}
                        </TableCell>
                        <TableCell className="text-right font-medium">
                            {formatCurrency(ref.outstanding_amount)}
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table> : null}
        <div className="flex justify-between items-center">
            <div className="flex gap-2">
                <span className="text-muted-foreground">Invoices: <span className="text-foreground font-mono font-medium">{selectedInvoices.length}</span></span> /
                <span className="text-muted-foreground">Total: <span className="text-foreground font-mono font-medium">{formatCurrency(selectedInvoices.reduce((acc, invoice) => acc + invoice.outstanding_amount, 0))}</span></span>
            </div>
            <DialogFooter className="pt-2">
                <DialogClose asChild>
                    <Button variant='ghost' disabled={allocateAmountToReferencesLoading}>Cancel</Button>
                </DialogClose>
                <Button onClick={onSelect} disabled={allocateAmountToReferencesLoading}>Select</Button>
            </DialogFooter>
        </div>

    </div>
}



const OtherChargesSection = ({ currency }: { currency: string }) => {

    const { setTotalAllocatedAmount } = usePaymentEntryCalculations()
    const { getValues, control, setValue, watch } = useFormContext<PaymentEntry>()
    const { calculateVat } = useDeductionsVatCalculation()

    const { fields, append, remove, replace } = useFieldArray({
        control: control,
        name: 'deductions'
    })

    const [selectedRows, setSelectedRows] = useState<number[]>([])
    const [isCalculating, setIsCalculating] = useState(false)

    const company = watch('company')

    const onSelectRow = useCallback((index: number) => {
        setSelectedRows(prev => {
            if (prev.includes(index)) {
                return prev.filter(i => i !== index)
            }
            return [...prev, index]
        })
    }, [])

    const onSelectAll = useCallback(() => {
        setSelectedRows(prev => {
            if (prev.length === fields.length) {
                return []
            }
            return [...fields.map((_, index) => index)]
        })
    }, [fields])

    const onRemove = useCallback(() => {
        // Filter out selected rows
        const newDeductions = fields.filter((_, index) => !selectedRows.includes(index))
        replace(newDeductions)
        setSelectedRows([])
        setTotalAllocatedAmount()
    }, [fields, selectedRows, replace, setTotalAllocatedAmount])

    const onRemoveVat = useCallback((index: number) => {
        // Remove VAT line and update base amount
        const deduction = fields[index]
        if (!deduction._is_vat_line) return

        // Find the base deduction (previous non-VAT line with same source)
        const baseIndex = fields.findIndex((d, i) =>
            i < index &&
            d._is_base_for_vat &&
            d.account === deduction._source_account
        )

        if (baseIndex >= 0) {
            const baseDeduction = fields[baseIndex]
            // Restore original amount (base + VAT)
            const originalAmount = baseDeduction.amount + deduction.amount

            // Update base deduction
            setValue(`deductions.${baseIndex}.amount`, originalAmount)
            setValue(`deductions.${baseIndex}._is_base_for_vat`, false)
        }

        // Remove VAT line
        remove(index)
        setTotalAllocatedAmount()
    }, [fields, setValue, remove, setTotalAllocatedAmount])

    const onAdd = () => {
        append({
            account: '',
            cost_center: getCompanyCostCenter(getValues('company')),
            description: '',
            amount: 0
        } as PaymentEntryDeduction)

        // Auto-focus on the Account field of the newly added row
        setTimeout(() => {
            const rows = document.querySelectorAll('[data-deduction-row]')
            const lastRow = rows[rows.length - 1]
            if (lastRow) {
                const accountBtn = lastRow.querySelector('[data-fieldname="account"] button') as HTMLButtonElement
                    ?? lastRow.querySelector('button[class*="min-w-64"]') as HTMLButtonElement
                if (accountBtn) {
                    accountBtn.focus()
                    accountBtn.click()
                }
            }
        }, 100)
    }

    // Trigger VAT calculation when account or amount changes
    const handleVatCalculation = useCallback(async (index: number) => {
        const currentDeductions = getValues('deductions') || []
        const deduction = currentDeductions[index]

        // Skip if no account or amount is zero or if already a VAT line
        if (!deduction?.account || deduction.amount === 0 || deduction._is_vat_line) {
            return
        }

        // Check if there's already a VAT line for this deduction (next line)
        const nextIndex = index + 1
        const hasExistingVatLine = nextIndex < currentDeductions.length &&
            currentDeductions[nextIndex]._is_vat_line &&
            currentDeductions[nextIndex]._source_account === deduction.account

        // If already has VAT line and this is a base line, remove the old VAT line first
        if (hasExistingVatLine) {
            // Remove the existing VAT line
            const deductionsWithoutOldVat = [
                ...currentDeductions.slice(0, nextIndex),
                ...currentDeductions.slice(nextIndex + 1)
            ]
            replace(deductionsWithoutOldVat)
            // Wait a tick for the replace to complete
            await new Promise(resolve => setTimeout(resolve, 0))
        }

        setIsCalculating(true)

        try {
            const result = await calculateVat({
                deductions: [deduction],
                company: company,
                is_vat_excluded: false,
                disable_vat_calculation: false
            })

            if (result?.message?.has_vat && result?.message?.deductions) {
                // Replace the single deduction with base + VAT
                const freshDeductions = getValues('deductions') || []
                const newDeductions = [
                    ...freshDeductions.slice(0, index),
                    ...result.message.deductions,
                    ...freshDeductions.slice(index + 1)
                ]
                replace(newDeductions)
                setTotalAllocatedAmount()
            }
        } catch (error) {
            console.error('VAT calculation error:', error)
        } finally {
            setIsCalculating(false)
        }
    }, [calculateVat, company, getValues, replace, setTotalAllocatedAmount])

    return <div className="flex flex-col gap-2">
        <div className="flex gap-2 items-center">
            <H4 className="text-base">Other Charges / Deductions</H4>
            <TotalDeductions currency={currency} />
            {isCalculating && <span className="text-xs text-muted-foreground">{_("Calculating VAT...")}</span>}
        </div>
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead><Checkbox
                        disabled={fields.length === 0}
                        aria-label={_("Select all")}
                        checked={selectedRows.length > 0 && selectedRows.length === fields.length}
                        onCheckedChange={onSelectAll} /></TableHead>
                    <TableHead>{_("Account")} <span className="text-destructive">*</span></TableHead>
                    <TableHead>{_("Cost Center")} <span className="text-destructive">*</span></TableHead>
                    <TableHead>{_("Description")}</TableHead>
                    <TableHead className="text-right">{_("Amount")} <span className="text-destructive">*</span></TableHead>
                    <TableHead className="w-14"></TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {fields.map((field, index) => {
                    const isVatLine = field._is_vat_line
                    const isBaseForVat = field._is_base_for_vat

                    return (
                        <TableRow
                            key={field.id}
                            data-deduction-row={index}
                            className={cn(
                                isVatLine && 'bg-blue-50 dark:bg-blue-950/20'
                            )}
                        >
                            <TableCell>
                                {!isVatLine && <Checkbox
                                    checked={selectedRows.includes(index)}
                                    onCheckedChange={() => onSelectRow(index)}
                                    aria-label={_("Select row {0}", [String(index + 1)])}
                                />}
                            </TableCell>

                            <TableCell className="align-top">
                                <div className="flex items-center gap-2">
                                    {isVatLine ? (
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm">{field.account}</span>
                                            <span className='text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded'>
                                                {_("VAT")}
                                            </span>
                                        </div>
                                    ) : (
                                        <AccountFormField
                                            name={`deductions.${index}.account`}
                                            label={_("Account")}
                                            rules={{
                                                required: _("Account is required"),
                                                onChange: () => handleVatCalculation(index)
                                            }}
                                            buttonClassName="min-w-64"
                                            isRequired
                                            hideLabel
                                        />
                                    )}
                                </div>
                            </TableCell>
                            <TableCell className="align-top">
                                {isVatLine ? (
                                    <span className="text-sm text-muted-foreground">{field.cost_center}</span>
                                ) : (
                                    <LinkFormField
                                        doctype="Cost Center"
                                        reference_doctype="Payment Entry Deduction"
                                        customQuery={{
                                            query: "erpnext.controllers.queries.get_filtered_dimensions",
                                            filters: {
                                                "dimension": "cost_center",
                                                "company": getValues('company'),
                                            }
                                        }}
                                        rules={{
                                            required: _("Cost Center is required"),
                                        }}
                                        name={`deductions.${index}.cost_center`}
                                        label={_("Cost Center")}
                                        buttonClassName="min-w-48"
                                        hideLabel
                                    />
                                )}
                            </TableCell>
                            <TableCell className="align-top">
                                {isVatLine ? (
                                    <span className="text-sm text-muted-foreground italic">{field.description}</span>
                                ) : (
                                    <DataField
                                        name={`deductions.${index}.description`}
                                        label={_("Remarks")}
                                        inputProps={{
                                            placeholder: _("e.g. Bank Charges"),
                                            className: 'min-w-64'
                                        }}
                                        hideLabel
                                    />
                                )}
                            </TableCell>
                            <TableCell className="text-right align-top">
                                {isVatLine ? (
                                    <span className="font-mono text-sm text-blue-700 dark:text-blue-300">
                                        {formatCurrency(field.amount, currency)}
                                    </span>
                                ) : (
                                    <CurrencyFormField
                                        name={`deductions.${index}.amount`}
                                        label={_("Amount")}
                                        isRequired
                                        hideLabel
                                        currency={currency}
                                        rules={{
                                            onChange: () => {
                                                setTotalAllocatedAmount()
                                            },
                                            onBlur: () => {
                                                handleVatCalculation(index)
                                            }
                                        }}
                                    />
                                )}
                            </TableCell>
                            <TableCell>
                                {isVatLine && (
                                    <Tooltip>
                                        <TooltipTrigger asChild>
                                            <Button
                                                variant='ghost'
                                                size='icon'
                                                type='button'
                                                className="text-blue-600 hover:text-blue-800"
                                                onClick={() => onRemoveVat(index)}
                                            >
                                                <X className="w-4 h-4" />
                                            </Button>
                                        </TooltipTrigger>
                                        <TooltipContent>
                                            {_("Remove VAT extraction")}
                                        </TooltipContent>
                                    </Tooltip>
                                )}
                            </TableCell>
                        </TableRow>
                    )
                })}
            </TableBody>
        </Table>
        <div className="flex justify-between gap-2">
            <div className="flex gap-2 justify-end">
                <div>
                    <Button size='sm' type='button' variant={'outline'} onClick={onAdd}><Plus /> {_("Add Row")}</Button>
                </div>
                {selectedRows.length > 0 && <div>
                    <Button size='sm' type='button' variant={'destructive'} onClick={onRemove}><Trash2 /> {_("Remove")}</Button>
                </div>}
            </div>
        </div>
    </div>
}

const TotalDeductions = ({ currency }: { currency: string }) => {

    const { control } = useFormContext<PaymentEntry>()

    const total_deductions = useWatch({ control, name: 'deductions' })?.reduce((acc: number, row: PaymentEntryDeduction) => acc + row.amount, 0) ?? 0

    return <span className={cn("font-mono font-medium", total_deductions !== 0 ? "text-destructive" : "text-muted-foreground")}>({formatCurrency(total_deductions, currency)})</span>
}
export default RecordPaymentModal