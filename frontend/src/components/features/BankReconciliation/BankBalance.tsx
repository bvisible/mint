import { useAtomValue, useSetAtom } from "jotai"
import { bankRecClosingBalanceAtom, bankRecDateAtom, SelectedBank, selectedBankAccountAtom } from "./bankRecAtoms"
import { FrappeConfig, FrappeContext, useFrappeGetDocCount, useFrappeGetDocList, useFrappePostCall, useSWRConfig } from "frappe-react-sdk"
import { BankTransaction } from "@/types/Accounts/BankTransaction"
import { Progress } from "@/components/ui/progress"
import { useGetAccountClosingBalance, useGetAccountClosingBalanceAsPerStatement, useGetAccountOpeningBalance, useGetUnreconciledTransactions } from "./utils"
import { flt, formatCurrency } from "@/lib/numbers"
import { Skeleton } from "@/components/ui/skeleton"
import { StatContainer, StatLabel, StatValue } from "@/components/ui/stats"
import { Edit, Info, Trash2 } from "lucide-react"
import { H4, Paragraph } from "@/components/ui/typography"
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card"
import { getCompanyCurrency } from "@/lib/company"
import _ from "@/lib/translate"
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { formatDate } from "@/lib/date"
import { Form } from "@/components/ui/form"
import { CurrencyFormField } from "@/components/ui/form-elements"
import { useForm } from "react-hook-form"
import { Button } from "@/components/ui/button"
//// Neoffice — useMemo: the amount still to deal with (ReconcileProgress).
import { useContext, useMemo, useState } from "react"
import { Separator } from "@/components/ui/separator"
import { MintBankStatementBalance } from "@/types/Mint/MintBankStatementBalance"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { toast } from "sonner"
import ErrorBanner from "@/components/ui/error-banner"

const BankBalance = () => {

    const bankAccount = useAtomValue(selectedBankAccountAtom)

    if (!bankAccount) {
        return null
    }
    return (
        //// Neoffice — the balance strip was made responsive (1f2847e). Upstream splits it 80/20 with
        //// fixed widths and a hard border; embedded in the desk chrome the available width is much
        //// smaller and the figures overflowed, so the row wraps and the divider only shows from lg.
        //// Every hunk of this file below is the same density/responsive pass plus one _() wrap.
        //// Neoffice — one band: the four figures and the progress side by side, their explanations behind an info icon
        //// (Daniel, 05.11: « il faut optimiser la place au sommet », what matters is the list below).
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
            <div className="flex flex-1 min-w-0 flex-wrap items-start gap-x-6 gap-y-1 pr-4 lg:pr-6 lg:border-r-border lg:border-r">
                <OpeningBalance />
                <ClosingBalance />
                <ClosingBalanceAsPerStatement />
                <Difference />
                {/* //// Neoffice — what is left to deal with is no longer a fifth figure: it is the block on the right. */}
            </div>

            <ReconcileProgress />
        </div>
    )
}

//// Neoffice — added: the label of a figure with, behind an info icon, where it comes from. Nobody could tell what the
//// four figures were (Daniel, 05.11: « je ne comprends pas d'où il prend ces valeurs »); the sentence is not shown all
//// the time, it would cost a line of the screen.
const LabelWithInfo = ({ label, title, info }: { label: string, title?: string, info?: React.ReactNode }) => (
    <div className="flex items-start gap-1">
        <StatLabel>{label}</StatLabel>
        {info && <HoverCard openDelay={100}>
            <HoverCardTrigger><Info size='14px' className="text-secondary-foreground/80" /></HoverCardTrigger>
            <HoverCardContent className="w-80" align="start" side="bottom">
                {/* //// Neoffice — the full wording of the figure is the title of the hover (the label itself is short). */}
                {title && <H4 className="text-base">{title}</H4>}
                <Paragraph className="mt-1 text-sm">{info}</Paragraph>
            </HoverCardContent>
        </HoverCard>}
    </div>
)

const OpeningBalance = () => {
    const bankAccount = useAtomValue(selectedBankAccountAtom)
    const { data, isLoading } = useGetAccountOpeningBalance()

    //// Neoffice — min-w-48 to min-w-32 (1f2847e), same density pass.
    return <StatContainer className="min-w-32">
        <LabelWithInfo label={_("Opening")} title={_("Opening Balance")} info={_("Calculated the same way, the day before the period starts.")} />
        {/* //// Neoffice — skeleton resized to match the smaller figures (1f2847e). */}
        {isLoading ? <Skeleton className="w-[120px] h-7" /> : <StatValue className="font-mono text-lg">{formatCurrency(flt(data?.message, 2), bankAccount?.account_currency ?? getCompanyCurrency(bankAccount?.company ?? ''))}</StatValue>}
    </StatContainer>
}

const ClosingBalance = () => {
    const bankAccount = useAtomValue(selectedBankAccountAtom)
    const { data, isLoading } = useGetAccountClosingBalance()

    return (
        //// Neoffice — min-w-48 to min-w-36 (1f2847e), same density pass.
        <StatContainer className="min-w-36">
            <div className="flex items-start gap-1">
                <StatLabel>
                    {/* //// Neoffice — short label (it was « Closing Balance as per system »): the strip fits one line. */}
                    {_("Closing")} · {_("System")}
                </StatLabel>
                <HoverCard openDelay={100}>
                    <HoverCardTrigger>
                        <Info size='14px' className="text-secondary-foreground/80" />
                    </HoverCardTrigger>
                    <HoverCardContent className="w-96" align="start" side="right">
                        <H4 className="text-base">{_("Closing balance as per system")}</H4>
                        <Paragraph className="mt-2 text-sm">
                            {_("This is what the system expects the closing balance to be in your bank statement.")}
                            <br />
                            {_("It takes into account all the transactions that have been posted and subtracts the transactions that have not cleared yet.")}
                            <br />
                            {_("If your bank statement shows a different closing balance, it is because all transactions have not reconciled yet.")}
                            <br /><br />
                            {/* //// Neoffice — sentence rebuilt with a _() placeholder (1f2847e). Upstream hard-codes the */}
                            {/* //// English text around a <strong> tab name, which cannot be translated as one sentence. */}
                            {_("For more information, click on the {0} tab below.", [_("Bank Reconciliation Statement")])}
                        </Paragraph>
                    </HoverCardContent>
                </HoverCard>

            </div>
            {/* //// Neoffice — skeleton resized (1f2847e), same density pass. */}
            {isLoading ? <Skeleton className="w-[120px] h-7" /> : <StatValue className="font-mono text-lg">{formatCurrency(flt(data?.message, 2), bankAccount?.account_currency ?? getCompanyCurrency(bankAccount?.company ?? ''))}</StatValue>}
        </StatContainer>
    )
}

const Difference = () => {
    const bankAccount = useAtomValue(selectedBankAccountAtom)

    const { data, isLoading } = useGetAccountClosingBalance()

    const value = useAtomValue(bankRecClosingBalanceAtom(bankAccount?.name ?? ''))

    const difference = flt(value.value - (data?.message ?? 0))

    const isError = difference !== 0

    //// Neoffice — sm:min-w-56 to sm:min-w-32 (1f2847e), same density pass.
    return <StatContainer className="w-fit text-right sm:min-w-32">
        <LabelWithInfo label={_("Difference")} info={_("Statement minus system.")} />
        {/* //// Neoffice — skeleton resized (1f2847e), same density pass. */}
        {isLoading ? <Skeleton className="w-[120px] h-7" /> : <StatValue className={isError ? 'text-destructive font-mono' : 'font-mono'}>
            {formatCurrency(difference,
                bankAccount?.account_currency ?? getCompanyCurrency(bankAccount?.company ?? ''))
            }</StatValue>}
        {/* //// Neoffice — the caption of the figure moved behind the info icon of its label (LabelWithInfo). */}
    </StatContainer>
}

const ReconcileProgress = () => {

    const bankAccount = useAtomValue(selectedBankAccountAtom)

    const dates = useAtomValue(bankRecDateAtom)

    const { data: totalCount } = useFrappeGetDocCount<BankTransaction>('Bank Transaction', [
        ["bank_account", "=", bankAccount?.name ?? ''],
        ['docstatus', '=', 1],
        ['date', '<=', dates?.toDate],
        ['date', '>=', dates?.fromDate]
    //// Neoffice — NOT ours: one argument dropped from useFrappeGetDocCount when upstream v1.5.0
    //// moved to a newer frappe-react-sdk, hand-carried (89e7929). Take upstream's at the merge.
    ], false, undefined, {
        revalidateOnFocus: false
    })

    const { data: unreconciledTransactions, } = useGetUnreconciledTransactions()

    const reconciledCount = (totalCount ?? 0) - (unreconciledTransactions?.message?.length ?? 0)

    const progress = (totalCount ? reconciledCount / totalCount : 0) * 100
    //// Neoffice — the amount still to deal with is the sum of the lines the tables below show, in and out apart
    //// (Daniel, 05.11: next to the number of entries, the amount to process).
    const { deposits, withdrawals } = useMemo(() => {
        let deposits = 0
        let withdrawals = 0
        for (const transaction of unreconciledTransactions?.message ?? []) {
            const left = flt(transaction.unallocated_amount ?? (transaction.deposit || transaction.withdrawal), 2)
            if (flt(transaction.deposit) > 0) deposits += left
            else withdrawals += left
        }
        return { deposits, withdrawals }
    }, [unreconciledTransactions])
    const currency = bankAccount?.account_currency ?? getCompanyCurrency(bankAccount?.company ?? '')
    //// Neoffice — fixed 18% width replaced by a min/max clamp (1f2847e): in the embedded shell
    //// the percentage collapsed the progress block to a few pixels on a laptop.
    //// Neoffice — one block for what is left: the amounts in and out, the count of what is reconciled beside the label and
    //// the bar as a thin line under them, so that the strip stays on one line (Daniel, 05.11).
    return <StatContainer className="min-w-[15rem] gap-0.5">
        <div className="flex items-baseline justify-between gap-3">
            <StatLabel>{_("Still to deal with")}</StatLabel>
            <span className="whitespace-nowrap text-xs text-muted-foreground">{reconciledCount} / {totalCount} {_("reconciled")}</span>
        </div>
        {/* //// Neoffice — the amounts in and out of what is left. */}
        <span className="whitespace-nowrap font-mono text-sm font-semibold tabular-nums">
            +{formatCurrency(deposits, currency)} <span className="text-muted-foreground">·</span> −{formatCurrency(withdrawals, currency)}
        </span>
        {/* //// Neoffice — the bar as a thin line under the amounts. */}
        <Progress value={progress} max={100} className="mt-0.5 h-[3px]" />
    </StatContainer>
}

const ClosingBalanceAsPerStatement = () => {

    const bankAccount = useAtomValue(selectedBankAccountAtom)
    const dates = useAtomValue(bankRecDateAtom)
    const setValue = useSetAtom(bankRecClosingBalanceAtom(bankAccount?.name ?? ''))

    const { data, isLoading } = useGetAccountClosingBalanceAsPerStatement({
        onSuccess: (data) => {
            if (data?.message && data?.message?.balance) {
                setValue({
                    value: data?.message?.balance,
                    stringValue: data?.message?.balance.toString()
                })
            }
        }
    })

    const isDateSame = data?.message?.date === dates.toDate
    //// Neoffice — the day is formatted out here: a string literal inside the arguments of _() is read by the extractor
    //// as the CONTEXT of the message, and a message with a context is never found without it.
    const statementDay = formatDate(data?.message?.date ?? '', 'Do MMM YYYY')

    const [isOpen, setIsOpen] = useState(false)


    //// Neoffice — min-w-48 to min-w-36 (1f2847e), same density pass.
    return <StatContainer className="min-w-36">
        <LabelWithInfo
            label={`${_("Closing")} · ${_("Statement")}`}
            title={_("Closing Balance as per statement")}
            info={data?.message?.source === "file"
                ? _("From the statement file imported, as of {0}.", [statementDay])
                : data?.message?.source === "typed"
                    ? _("Typed by hand.")
                    : _("Not known yet: click the figure to enter it.")}
        />
        <div className="flex items-baseline gap-2">
            <Dialog open={isOpen} onOpenChange={setIsOpen}>
                <DialogTrigger>
                    <Tooltip>
                        {/* //// Neoffice — gap and skeleton tightened (1f2847e), same density pass. */}
                        <TooltipTrigger asChild>
                            <div className="flex items-center gap-3 underline cursor-pointer underline-offset-6">
                                {isLoading ? <Skeleton className="w-[120px] h-7" /> : <StatValue className="font-mono text-lg">{formatCurrency(flt(data?.message?.balance, 2), bankAccount?.account_currency ?? getCompanyCurrency(bankAccount?.company ?? ''))}</StatValue>}
                                <Edit className="w-4 h-4" />
                            </div>
                        </TooltipTrigger>
                        <TooltipContent>
                            {_("Click to set the closing balance as per statement")}
                        </TooltipContent>
                    </Tooltip>
                </DialogTrigger>
                <DialogContent>
                    <ClosingBalanceForm
                        defaultBalance={data?.message?.balance ?? 0}
                        date={dates.toDate}
                        bankAccount={bankAccount}
                        onClose={() => setIsOpen(false)}
                    />


                </DialogContent>
            </Dialog>
            {/* //// Neoffice — the source of the figure moved behind the info icon of its label (LabelWithInfo). */}
            {!isDateSame && data?.message.date && <span className="text-xs font-medium text-destructive">{_("As of {0}", [formatDate(data?.message?.date ?? '', 'Do MMM YYYY')])}</span>}
        </div>
    </StatContainer>

}

const ClosingBalanceForm = ({ defaultBalance, date, bankAccount, onClose }: { defaultBalance: number, date: string, bankAccount: SelectedBank | null, onClose: VoidFunction }) => {

    const { mutate } = useSWRConfig()

    const form = useForm<{ balance: number }>({
        defaultValues: {
            balance: defaultBalance
        }
    })

    const setValue = useSetAtom(bankRecClosingBalanceAtom(bankAccount?.name ?? ''))

    const { call, loading, error } = useFrappePostCall("mint.apis.bank_account.set_closing_balance_as_per_statement")

    const onSubmit = (data: { balance: number }) => {
        if (data.balance) {
            call({
                bank_account: bankAccount?.name ?? '',
                date: date,
                balance: data.balance
            })
                .then(() => {
                    // Mutate the closing balance as per statement
                    mutate(`bank-reconciliation-account-closing-balance-as-per-statement-${bankAccount?.name}-${date}`)
                    setValue({
                        value: data.balance,
                        stringValue: data.balance.toString()
                    })
                    toast.success(_("Closing balance set."))
                    onClose()


                })
        } else {
            toast.error(_("Closing balance is required."))
        }
    }

    const currency = bankAccount?.account_currency ?? getCompanyCurrency(bankAccount?.company ?? '')


    return <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
            <DialogHeader>
                <DialogTitle>{_("Set closing balance as per bank statement")}</DialogTitle>
                <DialogDescription>
                    {_("Enter the closing balance you see in your bank statement for {0} as of the {1}", [bankAccount?.account_name ?? bankAccount?.name ?? '', formatDate(date, 'Do MMM YYYY')])}
                </DialogDescription>
            </DialogHeader>
            {error && <ErrorBanner error={error} />}
            <div className="py-4">
                <CurrencyFormField
                    name="balance"
                    label={_("Closing balance on bank statement as of {0}", [formatDate(date, 'Do MMM YYYY')])}
                    isRequired
                    currency={currency}
                />
            </div>

            <DialogFooter>
                <DialogClose asChild>
                    <Button variant={'outline'} disabled={loading}>{_("Cancel")}</Button>
                </DialogClose>
                <Button type='submit' disabled={loading}>{_("Save")}</Button>
            </DialogFooter>

            <ClosingBalancesList bankAccount={bankAccount} date={date} />
        </form>
    </Form>
}

const ClosingBalancesList = ({ bankAccount, date }: { bankAccount: SelectedBank | null, date: string }) => {

    const { data, mutate } = useFrappeGetDocList<MintBankStatementBalance>("Mint Bank Statement Balance", {
        filters: [["bank_account", "=", bankAccount?.name ?? ''], ["date", "<=", date]],
        orderBy: {
            field: "date",
            order: "desc"
        },
        fields: ["date", "balance", "name"],
        limit: 10
    })

    const { db } = useContext(FrappeContext) as FrappeConfig

    const onDelete = (name: string) => {
        toast.promise(db.deleteDoc("Mint Bank Statement Balance", name).then(() => {
            mutate()
        }), {
            loading: _("Deleting closing balance..."),
            success: _("Closing balance deleted."),
            error: _("Failed to delete closing balance.")
        })
    }

    if (data?.length === 0) {
        return null
    }

    return <div>
        <Separator className="my-8" />
        <p className="text-sm text-center">{_("Balances as per bank statement before {0}", [formatDate(date, 'Do MMM YYYY')])}</p>
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>{_("Date")}</TableHead>
                    <TableHead className="text-right">{_("Balance")}</TableHead>
                    <TableHead></TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {data?.map((item) => (
                    <TableRow key={item.name}>
                        <TableCell>{formatDate(item.date, 'Do MMM YYYY')}</TableCell>
                        <TableCell className="text-right">{formatCurrency(flt(item.balance, 2), bankAccount?.account_currency ?? getCompanyCurrency(bankAccount?.company ?? ''))}</TableCell>
                        <TableCell className="text-right">
                            <Button
                                title={_("Delete")}
                                type='button' size='icon' className="h-fit w-fit p-0 hover:bg-transparent active:bg-transparent hover:text-destructive" variant='ghost' onClick={() => onDelete(item.name)}>
                                <Trash2 />
                            </Button>
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    </div>

}

export default BankBalance