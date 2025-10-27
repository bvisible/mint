import { useAtom, useAtomValue, useSetAtom } from "jotai"
import { bankRecRecordJournalEntryModalAtom, bankRecSelectedTransactionAtom, bankRecUnreconcileModalAtom, selectedBankAccountAtom } from "./bankRecAtoms"
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogHeader, DialogFooter, DialogClose } from "@/components/ui/dialog"
import _ from "@/lib/translate"
import { UnreconciledTransaction, useGetRuleForTransaction, useRefreshUnreconciledTransactions } from "./utils"
import { useFieldArray, useForm, useFormContext, useWatch, Controller } from "react-hook-form"
import { JournalEntry } from "@/types/Accounts/JournalEntry"
import { getCompanyCostCenter, getCompanyCurrency } from "@/lib/company"
import { FrappeConfig, FrappeContext, useFrappePostCall } from "frappe-react-sdk"
import { toast } from "sonner"
import ErrorBanner from "@/components/ui/error-banner"
import { Button } from "@/components/ui/button"
import SelectedTransactionDetails from "./SelectedTransactionDetails"
import { AccountFormField, CurrencyFormField, DataField, DateField, LinkFormField, PartyTypeFormField, SmallTextField } from "@/components/ui/form-elements"
import { Form } from "@/components/ui/form"
import { useCallback, useContext, useMemo, useRef, useState } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Plus, Trash2 } from "lucide-react"
import { formatCurrency } from "@/lib/numbers"
import { cn } from "@/lib/utils"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import SelectedTransactionsTable from "./SelectedTransactionsTable"

const BankEntryModal = () => {

    const [isOpen, setIsOpen] = useAtom(bankRecRecordJournalEntryModalAtom)

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogContent className='min-w-[95vw]'>
                <DialogHeader>
                    <DialogTitle>{_("Bank Entry")}</DialogTitle>
                    <DialogDescription>
                        {_("Record a journal entry for expenses, income or split transactions.")}
                    </DialogDescription>
                </DialogHeader>
                <RecordBankEntryModalContent />
            </DialogContent>
        </Dialog>
    )
}

const RecordBankEntryModalContent = () => {

    const selectedBankAccount = useAtomValue(selectedBankAccountAtom)

    const selectedTransaction = useAtomValue(bankRecSelectedTransactionAtom(selectedBankAccount?.name ?? ''))

    if (!selectedTransaction || !selectedBankAccount) {
        return <div className='p-4'>
            <span className='text-center'>No transaction selected</span>
        </div>
    }

    if (selectedTransaction.length === 1) {
        return <BankEntryForm
            selectedTransaction={selectedTransaction[0]} />
    }

    return <BulkBankEntryForm
        selectedTransactions={selectedTransaction}
    />

}

const BulkBankEntryForm = ({ selectedTransactions }: { selectedTransactions: UnreconciledTransaction[] }) => {

    const form = useForm<{
        account: string
    }>({
        defaultValues: {
            account: ''
        }
    })

    const { call, loading, error } = useFrappePostCall('mint.apis.bank_reconciliation.create_bulk_bank_entry_and_reconcile')

    const onReconcile = useRefreshUnreconciledTransactions()

    const setIsOpen = useSetAtom(bankRecRecordJournalEntryModalAtom)

    const onSubmit = (data: { account: string }) => {

        call({
            bank_transactions: selectedTransactions.map(transaction => transaction.name),
            account: data.account
        }).then(() => {

            toast.success(_("Bank Entries Created"), {
                duration: 4000,
            })

            // Set this to the last selected transaction
            onReconcile(selectedTransactions[selectedTransactions.length - 1])
            setIsOpen(false)
        })
    }

    return <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
            <div className="flex flex-col gap-4">
                {error && <ErrorBanner error={error} />}
                <SelectedTransactionsTable />

                <div className="grid grid-cols-3 gap-4">
                    <AccountFormField
                        name='account'
                        filterFunction={(acc) => {
                            // Do not allow payable and receivable accounts
                            return acc.account_type !== 'Payable' && acc.account_type !== 'Receivable'
                        }}
                        label='Account'
                        isRequired
                    />
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


interface BankEntryFormData extends Pick<JournalEntry, 'voucher_type' | 'cheque_date' | 'posting_date' | 'cheque_no' | 'user_remark'> {
    entries: {
        account: string,
        party_type: string,
        party: string,
        amount: number,
        cost_center?: string,
        user_remark?: string,
    }[],
    is_vat_excluded?: boolean,
    disable_vat_calculation?: boolean
}


const BankEntryForm = ({ selectedTransaction }: { selectedTransaction: UnreconciledTransaction }) => {

    const selectedBankAccount = useAtomValue(selectedBankAccountAtom)

    const { data: rule } = useGetRuleForTransaction(selectedTransaction)

    const setIsOpen = useSetAtom(bankRecRecordJournalEntryModalAtom)

    const [previewData, setPreviewData] = useState<any>(null)

    const onClose = () => {
        setIsOpen(false)
        setPreviewData(null)
    }

    const isWithdrawal = (selectedTransaction.withdrawal && selectedTransaction.withdrawal > 0) ? true : false

    const form = useForm<BankEntryFormData>({
        defaultValues: {
            voucher_type: selectedBankAccount?.is_credit_card ? 'Credit Card Entry' : 'Bank Entry',
            cheque_date: selectedTransaction.date,
            posting_date: selectedTransaction.date,
            cheque_no: (selectedTransaction.reference_number || selectedTransaction.description || '').slice(0, 140),
            user_remark: selectedTransaction.description,
            is_vat_excluded: false, // Default to TTC (amounts include VAT)
            disable_vat_calculation: false,
            entries: [
                {
                    account: rule?.account ?? '',
                    amount: selectedTransaction.unallocated_amount,
                    party_type: '',
                    cost_center: getCompanyCostCenter(selectedTransaction.company ?? '') ?? ''
                }
            ],
        }
    })

    const onReconcile = useRefreshUnreconciledTransactions()

    const { call: previewBankEntry, loading: previewLoading, error: previewError } = useFrappePostCall('mint.apis.bank_reconciliation.preview_bank_entry_with_vat')
    const { call: createBankEntry, loading: submitLoading, error: submitError } = useFrappePostCall('mint.apis.bank_reconciliation.create_bank_entry_and_reconcile')

    const setBankRecUnreconcileModalAtom = useSetAtom(bankRecUnreconcileModalAtom)

    const loading = previewLoading || submitLoading
    const error = previewError || submitError

    const onPreview = (data: BankEntryFormData) => {
        previewBankEntry({
            bank_transaction_name: selectedTransaction.name,
            ...data
        }).then((result) => {
            console.log("Preview API Response:", result)
            // frappe-react-sdk wraps the response in a 'message' field
            const previewData = result?.message || result
            console.log("Preview Data:", previewData)
            setPreviewData(previewData)
        }).catch((error) => {
            console.error("Preview Error:", error)
        })
    }

    const onConfirmSubmit = () => {
        const data = form.getValues()

        createBankEntry({
            bank_transaction_name: selectedTransaction.name,
            ...data
        }).then(() => {
            toast.success(_("Bank Entry Created"), {
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
            onReconcile(selectedTransaction)
            onClose()
        })
    }

    const onEditPreview = () => {
        setPreviewData(null)
    }

    // If we have preview data, show the preview
    if (previewData) {
        return <JournalEntryPreview
            preview={previewData}
            onEdit={onEditPreview}
            onConfirm={onConfirmSubmit}
            loading={loading}
        />
    }
    return <Form {...form}>
        <form onSubmit={form.handleSubmit(onPreview)}>
            <div className='flex flex-col gap-4'>
                {error && <ErrorBanner error={error} />}
                <div className='grid grid-cols-2 gap-4'>
                    <SelectedTransactionDetails transaction={selectedTransaction} />

                    <div className='flex flex-col gap-4'>
                        <div className='grid grid-cols-2 gap-4'>
                            <DateField
                                name='posting_date'
                                label={"Posting Date"}
                                isRequired
                                inputProps={{ autoFocus: false }}
                            />
                            <DateField
                                name='cheque_date'
                                label={"Reference Date"}
                                isRequired
                                inputProps={{ autoFocus: false }}
                                rules={{
                                    required: _("Reference Date is required"),
                                }}
                            />
                        </div>
                        <DataField name='cheque_no' label={"Reference No"} isRequired inputProps={{ autoFocus: false }}
                            rules={{
                                required: _("Reference No is required"),
                            }} />
                    </div>
                </div>

                <div>
                    <Entries company={selectedTransaction.company ?? ''} isWithdrawal={isWithdrawal} amount={selectedTransaction.unallocated_amount} currency={selectedTransaction.currency ?? getCompanyCurrency(selectedTransaction.company ?? '')} />
                </div>
                <div className='flex flex-col gap-2'>
                    <div className='grid grid-cols-2 gap-4'>
                        <SmallTextField
                            name='user_remark'
                            label={"Remarks"}
                        />
                        <div className='flex items-center gap-2'>
                            <Controller
                                name='is_vat_excluded'
                                control={form.control}
                                render={({ field }) => (
                                    <div className='flex items-center gap-2'>
                                        <Checkbox
                                            id='is_vat_excluded'
                                            checked={field.value}
                                            onCheckedChange={field.onChange}
                                        />
                                        <Label htmlFor='is_vat_excluded' className='cursor-pointer'>
                                            {_("Amount excluding VAT (HT)")}
                                        </Label>
                                    </div>
                                )}
                            />
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant={'outline'} disabled={loading}>{_("Cancel")}</Button>
                    </DialogClose>
                    <Button type='submit' disabled={loading}>
                        {loading ? _("Loading...") : _("Preview")}
                    </Button>
                </DialogFooter>
            </div>
        </form>
    </Form>

}

const Entries = ({ company, isWithdrawal, amount, currency }: { company: string, isWithdrawal: boolean, amount?: number, currency: string }) => {

    const { getValues, setValue, control } = useFormContext<BankEntryFormData>()

    const { call } = useContext(FrappeContext) as FrappeConfig

    const costCenterMapRef = useRef<Record<string, string>>({})

    const partyMapRef = useRef<Record<string, string>>({})

    const onPartyChange = (value: string, index: number) => {
        // Get the account for the party type
        if (value) {
            if (partyMapRef.current[value]) {
                setValue(`entries.${index}.account`, partyMapRef.current[value])
            } else {
                call.get('erpnext.accounts.party.get_party_account', {
                    party: value,
                    party_type: getValues(`entries.${index}.party_type`),
                    company: company
                }).then((result: { message: string }) => {
                    setValue(`entries.${index}.account`, result.message)
                    partyMapRef.current[value] = result.message
                })
            }
        } else {
            setValue(`entries.${index}.account`, '')
        }
    }

    const onAccountChange = (value: string, index: number) => {
        // If it's an income or expense account, get the default cost center
        if (value) {
            if (costCenterMapRef.current[value]) {
                setValue(`entries.${index}.cost_center`, costCenterMapRef.current[value])
            } else {
                call.get('mint.apis.bank_reconciliation.get_account_defaults', {
                    account: value
                }).then((result: { message: string }) => {
                    costCenterMapRef.current[value] = result.message
                    setValue(`entries.${index}.cost_center`, result.message)
                })
            }
        } else {
            setValue(`entries.${index}.cost_center`, '')
        }
    }

    const { fields, append, remove } = useFieldArray({
        control: control,
        name: 'entries'
    })

    const onAdd = useCallback(() => {
        const existingEntries = getValues('entries')
        const remainingAmount = (amount ?? 0) - existingEntries.reduce((acc, curr) => acc + curr.amount, 0)
        append({
            party_type: '',
            party: '',
            account: '',
            amount: remainingAmount,
            cost_center: getCompanyCostCenter(company) ?? ''
        }, {
            focusName: `entries.${existingEntries.length}.account`
        })
    }, [company, append, amount, getValues])

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
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead><Checkbox
                        disabled={fields.length === 0}
                        // Make this accessible to screen readers
                        aria-label={_("Select all")}
                        checked={selectedRows.length > 0 && selectedRows.length === fields.length}
                        onCheckedChange={onSelectAll} /></TableHead>
                    <TableHead>{_("Party")}</TableHead>
                    <TableHead>{_("Account")}</TableHead>
                    <TableHead>{_("Cost Center")}</TableHead>
                    <TableHead>{_("Remarks")}</TableHead>
                    <TableHead className="text-right">{_("Amount")}</TableHead>
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

                        <TableCell className="align-top">
                            <div className="flex">
                                <PartyTypeFormField
                                    name={`entries.${index}.party_type`}
                                    label={"Party Type"}
                                    isRequired
                                    hideLabel
                                    inputProps={{
                                        type: isWithdrawal ? 'Payable' : 'Receivable',
                                        triggerProps: {
                                            className: 'rounded-r-none',
                                            tabIndex: -1
                                        },
                                    }} />
                                <PartyField index={index} onChange={onPartyChange} />
                            </div>

                        </TableCell>
                        <TableCell className="align-top">
                            <AccountFormField
                                name={`entries.${index}.account`}
                                label={_("Account")}
                                rules={{
                                    required: _("Account is required"),
                                    onChange: (value) => {
                                        onAccountChange(value, index)
                                    }
                                }}
                                buttonClassName="min-w-64"
                                isRequired
                                hideLabel
                            />
                        </TableCell>
                        <TableCell className="align-top">
                            <LinkFormField
                                doctype="Cost Center"
                                name={`entries.${index}.cost_center`}
                                label={_("Cost Center")}
                                filters={[["company", "=", company], ["is_group", "=", 0], ["disabled", "=", 0]]}
                                buttonClassName="min-w-48"
                                hideLabel
                            />
                        </TableCell>
                        <TableCell className="align-top">
                            <DataField
                                name={`entries.${index}.user_remark`}
                                label={_("Remarks")}
                                inputProps={{
                                    placeholder: _("e.g. Bank Charges"),
                                    className: 'min-w-64'
                                }}
                                hideLabel
                            />
                        </TableCell>
                        <TableCell className="text-right align-top">
                            <CurrencyFormField
                                name={`entries.${index}.amount`}
                                label={"Amount"}
                                isRequired
                                hideLabel
                                currency={currency}
                            />
                        </TableCell>
                    </TableRow>
                ))}
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
            <Summary amount={amount} currency={currency} addRow={onAdd} />
        </div>
    </div>

}

const PartyField = ({ index, onChange }: { index: number, onChange: (value: string, index: number) => void }) => {

    const { control } = useFormContext<BankEntryFormData>()

    const party_type = useWatch({
        control,
        name: `entries.${index}.party_type`
    })

    if (!party_type) {
        return <DataField
            name={`entries.${index}.party`}
            label={"Party"}
            isRequired
            inputProps={{
                disabled: true,
                className: 'rounded-l-none border-l-0 min-w-64'
            }}
            hideLabel
        />
    }

    return <LinkFormField
        name={`entries.${index}.party`}
        label={"Party"}
        rules={{
            onChange: (value) => {
                onChange(value, index)
            }
        }}
        hideLabel
        buttonClassName="rounded-l-none border-l-0 min-w-64"
        doctype={party_type}

    />
}

const Summary = ({ amount, currency, addRow }: { amount?: number, currency: string, addRow: () => void }) => {

    const { control } = useFormContext<BankEntryFormData>()

    const entries = useWatch({ control, name: 'entries' })

    const total = useMemo(() => {
        return entries.reduce((acc, curr) => acc + curr.amount, 0)
    }, [entries])

    const onAddRow = useCallback(() => {
        addRow()
    }, [addRow])

    const TextComponent = ({ className, children }: { className?: string, children: React.ReactNode }) => {
        return <span className={cn("w-32 text-right font-medium text-sm font-mono", className)}>{children}</span>
    }

    return <div className="flex flex-col gap-2 items-end">
        <div className="flex gap-2 justify-between">
            <TextComponent>{_("Split amount")}</TextComponent>
            <TextComponent>{formatCurrency(total, currency)}</TextComponent>
        </div>
        <div className="flex gap-2 justify-between">
            <TextComponent>{_("Original amount")}</TextComponent>
            <TextComponent>{formatCurrency(amount, currency)}</TextComponent>
        </div>
        {(amount ?? 0) !== total && <div className="flex gap-2 justify-between">
            <TextComponent>{_("Difference")}</TextComponent>
            <Tooltip>
                <TooltipTrigger asChild>
                    <Button type='button' variant='link' className="p-0 text-destructive underline h-fit" role='button' onClick={onAddRow}>
                        <TextComponent className='text-destructive'>{formatCurrency((amount ?? 0) - total, currency)}</TextComponent>
                    </Button>
                </TooltipTrigger>
                <TooltipContent>
                    {_("Add a row to with the difference amount")}
                </TooltipContent>
            </Tooltip>


        </div>}

    </div>

}

interface JournalEntryPreviewProps {
    preview: {
        voucher_type: string
        company: string
        posting_date: string
        cheque_date: string
        cheque_no: string
        user_remark: string
        accounts: Array<{
            account: string
            debit: number
            credit: number
            party_type?: string
            party?: string
            user_remark?: string
            cost_center?: string
            _is_vat_line?: boolean
            _is_base_for_vat?: boolean
            _is_bank_account?: boolean
            _source_account?: string
        }>
        total_debit: number
        total_credit: number
        is_balanced: boolean
        currency: string
    }
    onEdit: () => void
    onConfirm: () => void
    loading?: boolean
}

const JournalEntryPreview = ({ preview, onEdit, onConfirm, loading }: JournalEntryPreviewProps) => {
    // Safety check
    if (!preview || !preview.accounts) {
        return (
            <div className='flex flex-col gap-4 p-4'>
                <ErrorBanner error={new Error(_("Preview data is invalid. Please try again."))} />
                <DialogFooter>
                    <Button variant={'outline'} onClick={onEdit}>
                        {_("Back to Form")}
                    </Button>
                </DialogFooter>
            </div>
        )
    }

    return (
        <div className='flex flex-col gap-4'>
            <div className='bg-muted/50 p-4 rounded-md'>
                <h3 className='font-semibold mb-2'>{_("Journal Entry Details")}</h3>
                <div className='grid grid-cols-2 gap-2 text-sm'>
                    <div><span className='font-medium'>{_("Voucher Type")}:</span> {preview.voucher_type}</div>
                    <div><span className='font-medium'>{_("Company")}:</span> {preview.company}</div>
                    <div><span className='font-medium'>{_("Posting Date")}:</span> {preview.posting_date}</div>
                    <div><span className='font-medium'>{_("Reference Date")}:</span> {preview.cheque_date}</div>
                    <div className='col-span-2'><span className='font-medium'>{_("Reference No")}:</span> {preview.cheque_no}</div>
                </div>
            </div>

            <div>
                <h3 className='font-semibold mb-2'>{_("Accounting Entries")}</h3>
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>{_("Account")}</TableHead>
                            <TableHead>{_("Party")}</TableHead>
                            <TableHead>{_("Cost Center")}</TableHead>
                            <TableHead className='text-right'>{_("Debit")}</TableHead>
                            <TableHead className='text-right'>{_("Credit")}</TableHead>
                            <TableHead>{_("Remarks")}</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {preview.accounts.map((account, index) => (
                            <TableRow
                                key={index}
                                className={cn(
                                    account._is_vat_line && 'bg-blue-50 dark:bg-blue-950/20',
                                    account._is_bank_account && 'bg-green-50 dark:bg-green-950/20'
                                )}
                            >
                                <TableCell>
                                    <div className='flex items-center gap-2'>
                                        {account.account}
                                        {account._is_vat_line && (
                                            <span className='text-xs bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded'>
                                                {_("VAT")}
                                            </span>
                                        )}
                                        {account._is_bank_account && (
                                            <span className='text-xs bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-2 py-0.5 rounded'>
                                                {_("Bank")}
                                            </span>
                                        )}
                                    </div>
                                </TableCell>
                                <TableCell>
                                    {account.party_type && account.party ? `${account.party_type}: ${account.party}` : '-'}
                                </TableCell>
                                <TableCell>{account.cost_center || '-'}</TableCell>
                                <TableCell className='text-right font-mono'>
                                    {account.debit > 0 ? formatCurrency(account.debit, preview.currency) : '-'}
                                </TableCell>
                                <TableCell className='text-right font-mono'>
                                    {account.credit > 0 ? formatCurrency(account.credit, preview.currency) : '-'}
                                </TableCell>
                                <TableCell className='text-sm text-muted-foreground'>
                                    {account.user_remark || '-'}
                                </TableCell>
                            </TableRow>
                        ))}
                        <TableRow className='font-semibold bg-muted/50'>
                            <TableCell colSpan={3} className='text-right'>{_("Total")}</TableCell>
                            <TableCell className='text-right font-mono'>{formatCurrency(preview.total_debit, preview.currency)}</TableCell>
                            <TableCell className='text-right font-mono'>{formatCurrency(preview.total_credit, preview.currency)}</TableCell>
                            <TableCell></TableCell>
                        </TableRow>
                    </TableBody>
                </Table>

                {!preview.is_balanced && (
                    <div className='mt-2 p-2 bg-destructive/10 border border-destructive rounded-md text-sm text-destructive'>
                        {_("Warning: The journal entry is not balanced. Debit and credit totals must be equal.")}
                    </div>
                )}
            </div>

            <DialogFooter>
                <Button variant={'outline'} onClick={onEdit} disabled={loading}>
                    {_("Edit")}
                </Button>
                <Button onClick={onConfirm} disabled={loading || !preview.is_balanced}>
                    {loading ? _("Submitting...") : _("Confirm and Submit")}
                </Button>
            </DialogFooter>
        </div>
    )
}


export default BankEntryModal
