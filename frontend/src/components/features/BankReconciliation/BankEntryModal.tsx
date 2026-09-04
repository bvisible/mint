import { useAtom, useAtomValue, useSetAtom } from "jotai"
import { bankRecRecordJournalEntryModalAtom, bankRecSelectedTransactionAtom, bankRecUnreconcileModalAtom, selectedBankAccountAtom } from "./bankRecAtoms"
import { Dialog, DialogContent, DialogTitle, DialogDescription, DialogHeader, DialogFooter, DialogClose } from "@/components/ui/dialog"
import _ from "@/lib/translate"
import { UnreconciledTransaction, useGetRuleForTransaction, useRefreshUnreconciledTransactions, useUpdateActionLog } from "./utils"
import { useFieldArray, useForm, useFormContext, useWatch } from "react-hook-form"
import { JournalEntry } from "@/types/Accounts/JournalEntry"
import { getCompanyCostCenter, getCompanyCurrency } from "@/lib/company"
////// Neoffice — useFrappeFileUpload added (bc1a48f). This modal is heavily ours: the Swiss VAT
////// preview step (10998d9, 9f68df2, 71db75b) and the justificatif attachment (bc1a48f,
////// 16d00de). Upstream posts the entry straight away and attaches nothing.
import { FrappeConfig, FrappeContext, useFrappeFileUpload, useFrappePostCall } from "frappe-react-sdk"
import { toast } from "sonner"
import ErrorBanner from "@/components/ui/error-banner"
import { Button } from "@/components/ui/button"
import SelectedTransactionDetails from "./SelectedTransactionDetails"
import { AccountFormField, CurrencyFormField, DataField, DateField, LinkFormField, PartyTypeFormField, SmallTextField } from "@/components/ui/form-elements"
////// Neoffice — added (16d00de): our own drag-and-drop zone is built from a hidden Input plus
////// a Label, instead of the shared FileDropzone upstream uses (removed below).
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Form } from "@/components/ui/form"
////// Neoffice — useRef / useState / DragEvent added (16d00de) for that drop zone.
import { useCallback, useContext, useMemo, useRef, useState, DragEvent } from "react"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Checkbox } from "@/components/ui/checkbox"
////// Neoffice — Paperclip / X / FileIcon / Upload added (16d00de), icons of the drop zone.
import { ArrowDownRight, ArrowUpRight, Plus, Trash2, Paperclip, X, FileIcon, Upload } from "lucide-react"
import { flt, formatCurrency } from "@/lib/numbers"
import { cn } from "@/lib/utils"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import SelectedTransactionsTable from "./SelectedTransactionsTable"
import { JournalEntryAccount } from "@/types/Accounts/JournalEntryAccount"
////// Neoffice — upstream's FileUploadBanner and FileDropzone imports were REMOVED here
////// (16d00de, 287ec03). The shared dropzone is multi-file and posts on drop; a bank entry
////// takes exactly one justificatif, uploaded only once the Journal Entry exists and has a
////// name to attach it to. Label moved up with the other UI imports.
import { BankTransaction } from "@/types/Accounts/BankTransaction"

const BankEntryModal = () => {

    const [isOpen, setIsOpen] = useAtom(bankRecRecordJournalEntryModalAtom)

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            {/*//// Neoffice — width rewritten (e582a55), same clamp as the other modals: upstream's width */}
            {/*//// overflows the desk chrome the SPA is embedded in. */}
            <DialogContent className='!max-w-[min(92vw,1300px)] w-[min(92vw,1300px)] sm:!max-w-[min(92vw,1300px)]'>
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
            {/*//// Neoffice — wrapped in _() (1f2847e); upstream ships the bare English string. */}
            <span className='text-center'>{_("No transaction selected")}</span>
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

    const { call, loading, error } = useFrappePostCall<{ message: { transaction: BankTransaction, journal_entry: JournalEntry }[] }>('mint.apis.bank_reconciliation.create_bulk_bank_entry_and_reconcile')

    const onReconcile = useRefreshUnreconciledTransactions()
    const addToActionLog = useUpdateActionLog()

    const setIsOpen = useSetAtom(bankRecRecordJournalEntryModalAtom)

    const onSubmit = (data: { account: string }) => {

        call({
            bank_transactions: selectedTransactions.map(transaction => transaction.name),
            account: data.account
        }).then(({ message }) => {

            addToActionLog({
                type: 'bank_entry',
                timestamp: (new Date()).getTime(),
                isBulk: true,
                items: message.map((item) => ({
                    bankTransaction: item.transaction,
                    voucher: {
                        reference_doctype: "Journal Entry",
                        reference_name: item.journal_entry.name,
                        doc: item.journal_entry,
                        posting_date: item.journal_entry.posting_date,
                    }
                })),
                bulkCommonData: {
                    account: data.account,
                }
            })

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
                        label={_('Account')}
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
    ////// Neoffice — two fields added (10998d9): they are posted to create_bank_entry_and_reconcile
    ////// and preview_bank_entry_with_vat, and decide whether the amounts are read as TTC and
    ////// whether the VAT split runs at all. Upstream's form has no VAT.
    entries: JournalEntry['accounts'],
    is_vat_excluded?: boolean,
    disable_vat_calculation?: boolean
}


const BankEntryForm = ({ selectedTransaction }: { selectedTransaction: UnreconciledTransaction }) => {

    const selectedBankAccount = useAtomValue(selectedBankAccountAtom)

    const { data: rule } = useGetRuleForTransaction(selectedTransaction)

    const setIsOpen = useSetAtom(bankRecRecordJournalEntryModalAtom)

    ////// Neoffice — added state (10998d9, 9f68df2, 16d00de). Upstream submits the form directly;
    ////// ours first renders a server-computed preview of the Journal Entry with its VAT lines,
    ////// keeps a per-modal VAT override, and holds the selected file until the entry exists.
    const [previewData, setPreviewData] = useState<any>(null)
    const [vatDisabled, setVatDisabled] = useState(false)
    const [selectedFile, setSelectedFile] = useState<File | null>(null)
    const [isDragging, setIsDragging] = useState(false)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const { upload: uploadFile, loading: uploadLoading } = useFrappeFileUpload()

    const onClose = () => {
        setIsOpen(false)
        ////// Neoffice — added (10998d9, 16d00de). Everything down to the submit handler is ours: the
        ////// close reset (a leftover preview reopened on the next transaction) and the drag-and-drop
        ////// handlers of the attachment zone.
        setPreviewData(null)
        setVatDisabled(false)
        setSelectedFile(null)
        setIsDragging(false)
    }

    // Drag and drop handlers
    const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragging(true)
    }

    const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragging(false)
    }

    const handleDrop = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault()
        e.stopPropagation()
        setIsDragging(false)

        const files = e.dataTransfer.files
        if (files && files.length > 0) {
            const file = files[0]
            // Validate file type
            const validTypes = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.doc', '.docx', '.xls', '.xlsx']
            const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase()
            if (validTypes.includes(fileExtension)) {
                setSelectedFile(file)
            } else {
                toast.error(_("Invalid file type. Allowed: PDF, JPG, PNG, GIF, DOC, DOCX, XLS, XLSX"))
            }
        }
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file) {
            setSelectedFile(file)
        }
    }

    const removeFile = () => {
        setSelectedFile(null)
        if (fileInputRef.current) {
            fileInputRef.current.value = ''
        }
    }

    const isWithdrawal = (selectedTransaction.withdrawal && selectedTransaction.withdrawal > 0) ? true : false

    const defaultAccounts = useMemo(() => {

        const isWithdrawal = (selectedTransaction.withdrawal && selectedTransaction.withdrawal > 0) ? true : false

        const accounts: Partial<JournalEntryAccount>[] = [
            {
                account: selectedBankAccount?.account ?? '',
                bank_account: selectedTransaction.bank_account,
                // Bank is debited if it's a deposit
                debit: isWithdrawal ? 0 : selectedTransaction.unallocated_amount,
                credit: isWithdrawal ? selectedTransaction.unallocated_amount : 0,
                party_type: '',
                party: '',
                cost_center: ''
            }]

        // If there is no rule, we can just add the entries for the bank account transaction and the other side will be the reverse
        if (!rule) {
            accounts.push(
                {
                    account: '',
                    // Amounts will be the reverse of the bank account transaction
                    debit: isWithdrawal ? selectedTransaction.unallocated_amount : 0,
                    credit: isWithdrawal ? 0 : selectedTransaction.unallocated_amount,
                    cost_center: getCompanyCostCenter(selectedTransaction.company ?? '') ?? '',
                }
            )
        } else {
            // Rule exists, so we need to check the type of rule
            if (!rule.bank_entry_type || rule.bank_entry_type === "Single Account") {
                // Only a single account needs to be added
                accounts.push({
                    account: rule.account ?? '',
                    // Amounts will be the reverse of the bank account transaction
                    debit: isWithdrawal ? selectedTransaction.unallocated_amount : 0,
                    credit: isWithdrawal ? 0 : selectedTransaction.unallocated_amount,
                    cost_center: getCompanyCostCenter(selectedTransaction.company ?? '') ?? '',
                })
            } else {
                // For multiple accounts, we need to loop over and add entries for each
                // The last row will just be the remaining amount
                let hasTotallyEmptyRowEarlier = false;

                let totalDebits = isWithdrawal ? 0 : selectedTransaction.unallocated_amount ?? 0
                let totalCredits = isWithdrawal ? selectedTransaction.unallocated_amount ?? 0 : 0

                for (let i = 0; i < (rule.accounts?.length ?? 0); i++) {

                    const acc = rule.accounts?.[i]
                    // If it's the last row, add the difference amount
                    if (i === (rule.accounts?.length ?? 0) - 1 && !hasTotallyEmptyRowEarlier) {

                        const differenceAmount = flt(totalDebits - totalCredits, 2)
                        accounts.push({
                            account: acc?.account ?? '',
                            debit: differenceAmount > 0 ? 0 : Math.abs(differenceAmount),
                            credit: differenceAmount > 0 ? Math.abs(differenceAmount) : 0,
                            cost_center: getCompanyCostCenter(selectedTransaction.company ?? '') ?? '',
                            user_remark: acc?.user_remark ?? '',
                        })
                    } else {

                        /**
                         * The debit and credit amounts can also be expressions - like "transaction_amount * 0.5"
                         * So we need to compute the value of the expression
                         * We can use the eval function to do this. But we need to expose certain variables to the expression.
                         * One of them is transaction_amount which is the unallocated amount of the selected transaction
                         * @param expression - The expression to compute
                         * @returns The computed value
                         */
                        const computeExpression = (expression: string) => {

                            const script = `
                                const transaction_amount = ${selectedTransaction.unallocated_amount ?? 0}
                                ${expression};
                            `

                            let value = 0;

                            try {
                                value = eval(script);
                            } catch (error: unknown) {
                                console.error(error);
                                value = 0;
                            }

                            return value;
                        }
                        if (!acc?.debit && !acc?.credit) {
                            hasTotallyEmptyRowEarlier = true;
                        }

                        const computedDebit = acc?.debit ? flt(computeExpression(acc.debit), 2) : 0
                        const computedCredit = acc?.credit ? flt(computeExpression(acc.credit), 2) : 0

                        totalDebits = flt(totalDebits + computedDebit, 2)
                        totalCredits = flt(totalCredits + computedCredit, 2)
                        accounts.push({
                            account: acc?.account ?? '',
                            debit: computedDebit,
                            credit: computedCredit,
                            cost_center: getCompanyCostCenter(selectedTransaction.company ?? '') ?? '',
                            user_remark: acc?.user_remark ?? '',
                        })
                    }
                }
            }
        }

        return accounts

    }, [rule, selectedTransaction, selectedBankAccount])

    const form = useForm<BankEntryFormData>({
        defaultValues: {
            voucher_type: selectedBankAccount?.is_credit_card ? 'Credit Card Entry' : 'Bank Entry',
            cheque_date: selectedTransaction.date,
            posting_date: selectedTransaction.date,
            cheque_no: (selectedTransaction.reference_number || selectedTransaction.description || '').slice(0, 140),
            user_remark: selectedTransaction.description,
            entries: defaultAccounts,
        }
    })

    const onReconcile = useRefreshUnreconciledTransactions()

    ////// Neoffice — added call (10998d9): preview_bank_entry_with_vat is our endpoint. It computes
    ////// the VAT split server-side and returns the Journal Entry lines WITHOUT saving anything.
    const { call: previewBankEntry, loading: previewLoading, error: previewError } = useFrappePostCall('mint.apis.bank_reconciliation.preview_bank_entry_with_vat')
    const { call: createBankEntry, loading: submitLoading, error: submitError } = useFrappePostCall('mint.apis.bank_reconciliation.create_bank_entry_and_reconcile')

    const setBankRecUnreconcileModalAtom = useSetAtom(bankRecUnreconcileModalAtom)
    const addToActionLog = useUpdateActionLog()

    ////// Neoffice — loading and error now cover the three calls (preview, submit, upload).
    const loading = previewLoading || submitLoading || uploadLoading
    const error = previewError || submitError

    ////// Neoffice — added (10998d9, 71db75b). Upstream's submit creates the entry; ours renders the
    ////// preview first. The override argument exists because the VAT toggle has to re-preview with
    ////// the new value immediately, before React has committed the state.
    const onPreview = (data: BankEntryFormData, overrideVatDisabled?: boolean) => {
        const vatDisabledValue = overrideVatDisabled !== undefined ? overrideVatDisabled : vatDisabled
        previewBankEntry({
            bank_transaction_name: selectedTransaction.name,
            ...data,
            is_vat_excluded: false,  // Always use TTC mode (amounts include VAT)
            disable_vat_calculation: vatDisabledValue  // Use state to disable VAT calculation
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

    ////// Neoffice — async (bc1a48f): the file upload after creation has to be awaited.
    const onConfirmSubmit = async () => {
        const data = form.getValues()

        ////// Neoffice — wrapped in try/catch and the two VAT flags added (10998d9, bc1a48f).
        try {
            const result = await createBankEntry({
                bank_transaction_name: selectedTransaction.name,
                ...data,
                is_vat_excluded: false,  // Always use TTC mode (amounts include VAT)
                disable_vat_calculation: vatDisabled  // Use state to disable VAT calculation
            })

            ////// Neoffice — defensive (bc1a48f). create_bank_entry_and_reconcile now returns the Journal
            ////// Entry NAME plus the bank transaction (we need the name to attach the file), where upstream
            ////// returned the whole document. Both shapes are accepted so an instance running the older
            ////// server does not break.
            const message = result?.message || result

            // Log the action for undo support
            addToActionLog({
                type: 'bank_entry',
                isBulk: false,
                timestamp: (new Date()).getTime(),
                items: [
                    {
                        bankTransaction: message.transaction,
                        voucher: {
                            reference_doctype: "Journal Entry",
                            ////// Neoffice — same two shapes handled in the action log entry (bc1a48f).
                            reference_name: message.journal_entry?.name || message.journal_entry,
                            reference_no: message.journal_entry?.cheque_no,
                            reference_date: message.journal_entry?.cheque_date,
                            posting_date: message.journal_entry?.posting_date,
                            doc: message.journal_entry,
                        }
                    }
                ]
            })
////// Neoffice — added (bc1a48f). The justificatif is uploaded and attached only once the
////// Journal Entry exists: an upload keyed on a document that was never created leaves an
////// orphan File on the site.

            // Get journal entry name from response
            const journalEntryName = message.journal_entry?.name || message.journal_entry

            // If a file was selected, upload it and attach to the Journal Entry
            if (selectedFile && journalEntryName) {
                try {
                    await uploadFile(selectedFile, {
                        isPrivate: true,
                        doctype: "Journal Entry",
                        docname: journalEntryName,
                    })
                } catch (uploadError) {
                    console.error("File upload error:", uploadError)
                    // Still show success for JE creation even if file upload fails
                    toast.warning(_("Bank Entry created but file upload failed"), {
                        duration: 5000,
                    })
                }
            }

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
////// Neoffice — upstream's FileDropzone upload block was REMOVED here (16d00de, 287ec03): it
////// looped over a files array and drove an isUploading flag this component no longer has.
////// Replaced by the single-file upload just above.

            onReconcile(selectedTransaction)
            onClose()
        ////// Neoffice — catch added around the whole create-and-attach sequence (bc1a48f).
        } catch (err) {
            console.error("Error creating bank entry:", err)
        }
    }

    const onEditPreview = () => {
        setPreviewData(null)
    }

    ////// Neoffice — added (9f68df2, 71db75b). Toggling VAT off re-runs the preview at once with the
    ////// new value: an accountant flips it to check the effect, and a stale preview is worse than
    ////// no preview. Upstream has no VAT and no toggle.
    const handleVatToggle = () => {
        const newVatDisabled = !vatDisabled
        setVatDisabled(newVatDisabled)
        onPreview(form.getValues(), newVatDisabled)
    }

    // If we have preview data, show the preview
    if (previewData) {
        return <JournalEntryPreview
            preview={previewData}
            onEdit={onEditPreview}
            onConfirm={onConfirmSubmit}
            loading={loading}
            vatDisabled={vatDisabled}
            onVatToggle={handleVatToggle}
            selectedFile={selectedFile}
        />
    }

    return <Form {...form}>
        {/*//// Neoffice — the form now submits to onPreview, not to the create call (10998d9). The entry */}
        {/*//// is only written from the preview screen. */}
        <form onSubmit={form.handleSubmit((data) => onPreview(data))}>
            <div className='flex flex-col gap-4'>
                {error && <ErrorBanner error={error} />}
                <div className='grid grid-cols-2 gap-4'>
                    <SelectedTransactionDetails transaction={selectedTransaction} />

                    <div className='flex flex-col gap-4'>
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
                                rules={{
                                    required: _("Reference Date is required"),
                                }}
                            />
                        </div>
                        <DataField name='cheque_no' label={_("Reference")} isRequired inputProps={{ autoFocus: false }}
                            rules={{
                                required: _("Reference is required"),
                            }} />
                    </div>
                </div>

                <div>
                    <Entries company={selectedTransaction.company ?? ''} isWithdrawal={isWithdrawal} currency={selectedTransaction.currency ?? getCompanyCurrency(selectedTransaction.company ?? '')} />
                </div>
                <div className='flex flex-col gap-2'>
                    <div className='grid grid-cols-2 gap-4'>
                        <SmallTextField
                            name='user_remark'
                            label={_("Remarks")}
                        />
                        {/*//// Neoffice — attachment zone rewritten (16d00de). Upstream drops a shared FileDropzone in; */}
                        {/*//// ours is a hidden file input plus a drag target, so the file is held in state and uploaded */}
                        {/*//// after the Journal Entry is created (see onConfirmSubmit above). */}
                        <div className='flex flex-col gap-2'>
                            <Label>{_("Attachment")}</Label>
                            <Input
                                ref={fileInputRef}
                                type="file"
                                accept=".pdf,.jpg,.jpeg,.png,.gif,.doc,.docx,.xls,.xlsx"
                                onChange={handleFileSelect}
                                className='hidden'
                            />
                            {!selectedFile ? (
                                <div
                                    onDragOver={handleDragOver}
                                    onDragLeave={handleDragLeave}
                                    onDrop={handleDrop}
                                    onClick={() => fileInputRef.current?.click()}
                                    className={cn(
                                        'border-2 border-dashed rounded-lg p-4 cursor-pointer transition-colors',
                                        'flex flex-col items-center justify-center gap-2 min-h-[100px]',
                                        isDragging
                                            ? 'border-primary bg-primary/5'
                                            : 'border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50'
                                    )}
                                >
                                    <Upload className={cn(
                                        'w-8 h-8',
                                        isDragging ? 'text-primary' : 'text-muted-foreground'
                                    )} />
                                    <div className='text-center'>
                                        <p className='text-sm text-muted-foreground'>
                                            {isDragging
                                                ? _("Drop file here")
                                                : _("Drag and drop file here")}
                                        </p>
                                        <p className='text-xs text-muted-foreground/70 mt-1'>
                                            {_("or click to browse")}
                                        </p>
                                    </div>
                                </div>
                            ) : (
                                <div className='border rounded-lg p-3 bg-muted/30'>
                                    <div className='flex items-center justify-between'>
                                        <div className='flex items-center gap-2 min-w-0'>
                                            <FileIcon className='w-5 h-5 text-primary flex-shrink-0' />
                                            <span className='text-sm truncate'>{selectedFile.name}</span>
                                        </div>
                                        <Button
                                            type='button'
                                            variant='ghost'
                                            size='sm'
                                            className='h-6 w-6 p-0 flex-shrink-0 hover:bg-destructive/10 hover:text-destructive'
                                            onClick={removeFile}
                                        >
                                            <X className='w-4 h-4' />
                                        </Button>
                                    </div>
                                    <p className='text-xs text-muted-foreground mt-1'>
                                        {(selectedFile.size / 1024).toFixed(1)} KB
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <DialogClose asChild>
                        <Button variant={'outline'} disabled={loading}>{_("Cancel")}</Button>
                    </DialogClose>
                    {/*//// Neoffice — the primary action is now Preview, not Submit (10998d9). */}
                    <Button type='submit' disabled={loading}>
                        {loading ? _("Loading...") : _("Preview")}
                    </Button>
                </DialogFooter>
            </div>
        </form>
    </Form>

}

const Entries = ({ company, isWithdrawal, currency }: { company: string, isWithdrawal: boolean, currency: string }) => {

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
        const totalDebits = existingEntries.reduce((acc, curr) => flt(acc + (curr.debit ?? 0), 2), 0)
        const totalCredits = existingEntries.reduce((acc, curr) => flt(acc + (curr.credit ?? 0), 2), 0)

        const remainingAmount = flt(totalDebits - totalCredits, 2)

        // Remaining amount is credit if it's positive - since some debit is pending to be cleared.
        const debitAmount = remainingAmount > 0 ? 0 : Math.abs(remainingAmount)
        const creditAmount = remainingAmount > 0 ? Math.abs(remainingAmount) : 0

        append({
            party_type: '',
            party: '',
            account: '',
            debit: debitAmount,
            credit: creditAmount,
            cost_center: getCompanyCostCenter(company) ?? ''
        } as JournalEntryAccount, {
            focusName: `entries.${existingEntries.length}.account`
        })
    }, [company, append, getValues])

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

    /**
     * When add difference is clicked, check if the last row has nothing filled in.
     * If last row is empty (no debit or credit), then set that row's amount. Else, add a new row with the difference amount.
     */
    const onAddDifferenceClicked = () => {

        const existingEntries = getValues('entries')
        const totalDebits = existingEntries.reduce((acc, curr) => flt(acc + (curr.debit ?? 0), 2), 0)
        const totalCredits = existingEntries.reduce((acc, curr) => flt(acc + (curr.credit ?? 0), 2), 0)

        const lastIndex = existingEntries.length - 1

        const isLastRowEmpty = (existingEntries[lastIndex]?.debit === 0 || existingEntries[lastIndex]?.debit === undefined) && (existingEntries[lastIndex]?.credit === 0 || existingEntries[lastIndex]?.credit === undefined)

        const remainingAmount = flt(totalDebits - totalCredits, 2)

        // Remaining amount is credit if it's positive - since some debit is pending to be cleared.
        const debitAmount = remainingAmount > 0 ? 0 : Math.abs(remainingAmount)
        const creditAmount = remainingAmount > 0 ? Math.abs(remainingAmount) : 0

        if (isLastRowEmpty) {
            setValue(`entries.${lastIndex}.debit`, debitAmount)
            setValue(`entries.${lastIndex}.credit`, creditAmount)
        } else {
            append({
                party_type: '',
                party: '',
                account: '',
                debit: debitAmount,
                credit: creditAmount,
                cost_center: getCompanyCostCenter(company) ?? ''
            } as JournalEntryAccount, {
                focusName: `entries.${existingEntries.length}.account`
            })
        }
    }



    return <div className="flex flex-col gap-2">
        {/*//// Neoffice — table-fixed with a minimum width (5ba4a3d, 37d4ce0). With upstream's auto */}
        {/*//// layout the Debit and Credit columns collapsed to a few pixels as soon as an account name */}
        {/*//// was long, and the modal grew a horizontal scrollbar. */}
        <Table className="table-fixed min-w-[900px]">
            <TableHeader>
                <TableRow>
                    {/*//// Neoffice — explicit checkbox column width (37d4ce0), part of the fixed layout above. */}
                    <TableHead className="w-8"><Checkbox
                        disabled={fields.length === 0}
                        // Make this accessible to screen readers
                        aria-label={_("Select all")}
                        checked={selectedRows.length > 0 && selectedRows.length === fields.length}
                        onCheckedChange={onSelectAll} /></TableHead>
                    {/*//// Neoffice — explicit column widths (5ba4a3d, 37d4ce0): they add up to 100% so the amounts */}
                    {/*//// keep their room whatever the account label is. */}
                    <TableHead className="w-[18%]">{_("Party")}</TableHead>
                    <TableHead className="w-[22%]">{_("Account")}</TableHead>
                    <TableHead className="w-[14%]">{_("Cost Center")}</TableHead>
                    <TableHead className="w-[14%]">{_("Remarks")}</TableHead>
                    <TableHead className="w-[14%] text-right">{_("Debit")}</TableHead>
                    <TableHead className="w-[14%] text-right">{_("Credit")}</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {fields.map((field, index) => (
                    <TableRow key={field.id} className={index === 0 ? 'bg-muted/70 cursor-not-allowed' : ''} title={index === 0 ? _("This is the bank account entry. You cannot edit it.") : ''}>
                        <TableCell>
                            <Checkbox
                                checked={selectedRows.includes(index)}
                                onCheckedChange={() => onSelectRow(index)}
                                // Make this accessible to screen readers
                                aria-label={_("Select row {0}", [String(index + 1)])}
                                disabled={index === 0}
                            />
                        </TableCell>

                        <TableCell className="align-top">
                            <div className="flex">
                                <PartyTypeFormField
                                    name={`entries.${index}.party_type`}
                                    label={_("Party Type")}
                                    isRequired
                                    readOnly={index === 0}
                                    hideLabel
                                    inputProps={{
                                        type: isWithdrawal ? 'Payable' : 'Receivable',
                                        triggerProps: {
                                            className: 'rounded-r-none',
                                            tabIndex: -1
                                        },
                                        readOnly: index === 0,
                                    }} />
                                <PartyField index={index} onChange={onPartyChange} readOnly={index === 0} />
                            </div>

                        </TableCell>
                        <TableCell className="align-top">
                            <AccountFormField
                                name={`entries.${index}.account`}
                                label={_("Account")}
                                rules={{
                                    required: _("Account is required"),
                                    onChange: (event) => {
                                        onAccountChange(event.target.value, index)
                                    }
                                }}
                                ////// Neoffice — w-full (37d4ce0): inside a fixed-width column the control must fill its cell,
                                ////// otherwise it kept its intrinsic width and overflowed.
                                buttonClassName="w-full"
                                readOnly={index === 0}
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
                                ////// Neoffice — w-full (37d4ce0), same reason as the account field above.
                                buttonClassName="w-full"
                                readOnly={index === 0}
                                hideLabel
                            />
                        </TableCell>
                        <TableCell className="align-top">
                            <DataField
                                name={`entries.${index}.user_remark`}
                                label={_("Remarks")}
                                readOnly={index === 0}
                                inputProps={{
                                    placeholder: _("e.g. Bank Charges"),
                                    ////// Neoffice — w-full (37d4ce0), same reason.
                                    className: 'w-full',
                                    readOnly: index === 0
                                }}
                                hideLabel
                            />
                        </TableCell>
                        <TableCell className={cn("text-right align-top")}>
                            <CurrencyFormField
                                name={`entries.${index}.debit`}
                                label={_("Debit")}
                                isRequired
                                hideLabel
                                readOnly={index === 0}
                                style={index === 0 ? !isWithdrawal ? {
                                    color: "black",
                                } : {} : {}}
                                currency={currency}
                                leftSlot={index === 0 && !isWithdrawal ? <Tooltip>
                                    <TooltipTrigger asChild><ArrowDownRight className="text-green-600" /></TooltipTrigger>
                                    <TooltipContent>{_("Bank account debit for deposit")}</TooltipContent>
                                </Tooltip> : undefined}
                            />
                        </TableCell>
                        <TableCell className={cn("text-right align-top")}>
                            <CurrencyFormField
                                name={`entries.${index}.credit`}
                                style={index === 0 && isWithdrawal ? {
                                    color: "black",
                                } : {}}
                                label={_("Credit")}
                                isRequired
                                hideLabel
                                readOnly={index === 0}
                                currency={currency}
                                leftSlot={index === 0 && isWithdrawal ? <Tooltip>
                                    <TooltipTrigger asChild><ArrowUpRight className="text-destructive" /></TooltipTrigger>
                                    <TooltipContent>{_("Bank account credit for withdrawal")}</TooltipContent>
                                </Tooltip> : undefined}
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
            <Summary currency={currency} addRow={onAddDifferenceClicked} />
        </div>
    </div>

}

const PartyField = ({ index, onChange, readOnly }: { index: number, onChange: (value: string, index: number) => void, readOnly: boolean }) => {

    const { control } = useFormContext<BankEntryFormData>()

    const party_type = useWatch({
        control,
        name: `entries.${index}.party_type`
    })

    if (!party_type) {
        return <DataField
            name={`entries.${index}.party`}
            label={_("Party")}
            isRequired
            inputProps={{
                disabled: true,
                ////// Neoffice — w-full (37d4ce0), same reason, disabled party field.
                className: 'rounded-l-none border-l-0 w-full'
            }}
            hideLabel
        />
    }

    return <LinkFormField
        name={`entries.${index}.party`}
        label={_("Party")}
        rules={{
            onChange: (event) => {
                onChange(event.target.value, index)
            },
        }}
        hideLabel
        readOnly={readOnly}
        ////// Neoffice — w-full (37d4ce0), same reason, editable party field.
        buttonClassName="rounded-l-none border-l-0 w-full"
        doctype={party_type}

    />
}

const Summary = ({ currency, addRow }: { currency: string, addRow: () => void }) => {

    const { control } = useFormContext<BankEntryFormData>()

    const entries = useWatch({ control, name: 'entries' })

    const { total, totalCredits, totalDebits } = useMemo(() => {
        // Do a total debits - total credits
        const totalDebits = entries.reduce((acc, curr) => flt(acc + (curr.debit ?? 0), 2), 0)
        const totalCredits = entries.reduce((acc, curr) => flt(acc + (curr.credit ?? 0), 2), 0)
        return { total: flt(totalDebits - totalCredits, 2), totalDebits, totalCredits }
    }, [entries])

    const onAddRow = useCallback(() => {
        addRow()
    }, [addRow])

    const TextComponent = ({ className, children }: { className?: string, children: React.ReactNode }) => {
        return <span className={cn("w-32 text-right font-medium text-sm font-mono", className)}>{children}</span>
    }

    return <div className="flex flex-col gap-2 items-end">
        <div className="flex gap-2 justify-between">
            <TextComponent>{_("Total Debit")}</TextComponent>
            <TextComponent>{formatCurrency(totalDebits, currency)}</TextComponent>
        </div>
        <div className="flex gap-2 justify-between">
            <TextComponent>{_("Total Credit")}</TextComponent>
            <TextComponent>{formatCurrency(totalCredits, currency)}</TextComponent>
        </div>
        {total !== 0 && <div className="flex gap-2 justify-between">
            <TextComponent>{_("Difference")}</TextComponent>
            <Tooltip>
                <TooltipTrigger asChild>
                    <Button type='button' variant='link' className="p-0 text-destructive underline h-fit" role='button' onClick={onAddRow}>
                        <TextComponent className='text-destructive'>{formatCurrency(total, currency)}</TextComponent>
                    </Button>
                </TooltipTrigger>
                <TooltipContent>
                    {_("Add a row with the difference amount")}
                </TooltipContent>
            </Tooltip>
        </div>}

    </div>

}

////// Neoffice — added: everything from here to the end of the file is ours (10998d9, 9f68df2,
////// 71db75b). JournalEntryPreview renders what the server computed BEFORE anything is saved:
////// the base lines, the VAT lines it extracted, the totals and the balance check, plus the
////// toggle that turns the split off. Upstream never shows the entry before creating it.
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
    vatDisabled: boolean
    onVatToggle: () => void
    selectedFile?: File | null
}

const JournalEntryPreview = ({ preview, onEdit, onConfirm, loading, vatDisabled, onVatToggle, selectedFile }: JournalEntryPreviewProps) => {
    // Check if preview contains VAT lines
    const hasVatLines = preview?.accounts?.some(account => account._is_vat_line) ?? false

    // Safety check
    if (!preview || !preview.accounts) {
        return (
            <div className='flex flex-col gap-4 p-4'>
                <ErrorBanner error={{ message: _("Preview data is invalid. Please try again.") } as any} />
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
                    {selectedFile && (
                        <div className='col-span-2 flex items-center gap-2 mt-2'>
                            <span className='font-medium'>{_("Attachment")}:</span>
                            <div className='flex items-center gap-1 bg-blue-50 dark:bg-blue-950/30 px-2 py-1 rounded text-blue-700 dark:text-blue-300'>
                                <Paperclip className='w-3 h-3' />
                                <span className='text-xs'>{selectedFile.name}</span>
                            </div>
                        </div>
                    )}
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

            {/* Show Remove/Add VAT button only if VAT lines are present or were removed */}
            {(hasVatLines || vatDisabled) && (
                <div className='flex justify-center'>
                    <Button
                        variant={vatDisabled ? "default" : "outline"}
                        onClick={onVatToggle}
                        disabled={loading}
                        type="button"
                    >
                        {vatDisabled ? _("With VAT") : _("Remove VAT")}
                    </Button>
                </div>
            )}

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
