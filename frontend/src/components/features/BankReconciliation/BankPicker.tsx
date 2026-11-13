import { useAtom, useSetAtom } from "jotai"
import { SelectedBank, selectedBankAccountAtom } from "./bankRecAtoms"
//// Neoffice — added: useState drives the open/closed popover of the new size "select" (1e4b754).
import { useCallback, useState } from "react"
import { useGetBankAccounts, useGetUnreconciledTransactions } from "./utils"
import { cn } from "@/lib/utils"
import { Check, ChevronDown, Landmark } from "lucide-react"
//// Neoffice — added: the selector of the size « select » (below).
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { H4 } from "@/components/ui/typography"
import { getTimeago } from "@/lib/date"
import ErrorBanner from "@/components/ui/error-banner"
import _ from "@/lib/translate"

//// Neoffice — the size « row » is ours: the logo and the name on one line, the account under it (two lines, not three).
//// Neoffice — the size « select » is ours too: one selector instead of a row of cards (Daniel, 11.11: the bank at the top left,
//// the four figures under it, and the row of cards gone, since what matters is the list below).
const BankPicker = ({ className, size = 'base' }: { className?: string, size?: 'base' | 'sm' | 'row' | 'select' }) => {

    const setSelectedBank = useSetAtom(selectedBankAccountAtom)

    const onLoadingSuccess = useCallback((data?: SelectedBank[]) => {
        if (!data) return
        if (data.length === 1) {
            setSelectedBank(data[0])
        } else if (data.length > 1) {
            const defaultBank = data.find((bank: SelectedBank) => bank.is_default)
            if (defaultBank) {
                setSelectedBank(defaultBank)
            }
        }
    }, [setSelectedBank])

    const { banks, isLoading, error } = useGetBankAccounts(onLoadingSuccess)

    if (isLoading) {
        return null
    }

    if (error) {
        return <ErrorBanner error={error} />
    }
    //// Neoffice — added: size "select" renders the top-left bank selector instead of the row of
    //// cards, which moves to the body of the page (1e4b754).
    if (size === 'select') {
        return <BankSelect banks={banks ?? []} className={className} />
    }
    return (
        <div
            className={cn("flex gap-3 items-stretch w-full overflow-x-auto bank-picker-scrollbar pr-4",
                banks?.length > 4 ? 'pb-2' : '', className,
            )}
            style={{
                scrollbarWidth: 'thin',
                scrollbarColor: 'rgb(209 213 219) rgb(243 244 246)',
            }}
        >
            {
                banks?.map((bank) => (
                    <BankPickerItem key={bank.name} bank={bank} size={size} />
                ))
            }
        </div>
    )
}

//// Neoffice — added: the logo (or the symbol of the bank), its name and, under it, the account of the books.
const BankLabel = ({ bank }: { bank: SelectedBank }) => (
    <span className="flex min-w-0 items-center gap-2 text-left">
        {bank.logo
            ? <img src={`/assets/mint/mint/${bank.logo}`} alt={bank.bank || bank.name || ''} className="shrink-0 object-contain"
                style={{ maxWidth: '64px', maxHeight: '20px', width: 'auto', height: 'auto' }} />
            : bank.logo_mark
                ? <img src={`/assets/mint/mint/${bank.logo_mark}`} alt="" className="shrink-0" style={{ width: '20px', height: '20px' }} />
                : <Landmark size="18px" className="shrink-0" />}
        <span className="flex min-w-0 flex-col leading-tight">
            <span className="truncate text-sm font-medium">{bank.account_name}</span>
            <span title={_("GL Account")} className="truncate text-xs font-normal text-muted-foreground">{bank.account}</span>
        </span>
    </span>
)

//// Neoffice — added: the bank to reconcile is chosen in a list that opens under the selector, like the company next to it; with a
//// single account it is only a label. Two lines (the bank, its account) in the height of the buttons beside it.
const BankSelect = ({ banks, className }: { banks: SelectedBank[], className?: string }) => {
    const [selectedBank, setSelectedBank] = useAtom(selectedBankAccountAtom)
    const { mutate } = useGetUnreconciledTransactions()
    const [open, setOpen] = useState(false)

    const several = banks.length > 1
    const box = cn("h-11 min-w-56 max-w-80 justify-between gap-2 px-2.5", className)
    //// Neoffice — the selection kept between visits could hold a copy of the bank from before its logo was known, so the
    //// selector drew the generic icon where the list under it drew the logo; show the bank of the list instead (cf3d74f
    //// "fix(bank reconciliation): the bank selector shows the logo of the bank of the list, not the older copy held by the selection")
    // the atom may hold an older copy of the bank (without its logo): what is shown is the bank of the list
    const shown = banks.find((bank) => bank.name === selectedBank?.name) ?? selectedBank
    const content = shown
        ? <BankLabel bank={shown} />
        : <span className="text-sm font-normal text-muted-foreground">{_("Select a bank account")}</span>

    if (!several) {
        return <div className={cn("flex items-center rounded-md border bg-card", box)}>{content}</div>
    }

    const choose = (bank: SelectedBank) => {
        setSelectedBank(bank)
        mutate()
        setOpen(false)
    }

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button variant="outline" role="combobox" aria-expanded={open} className={box}>
                    {content}
                    <ChevronDown className="opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="flex w-80 max-w-[90vw] flex-col gap-0.5 p-1">
                {banks.map((bank) => (
                    <button
                        key={bank.name}
                        type="button"
                        title={_("Select {0}", [bank.account_name ?? ''])}
                        onClick={() => choose(bank)}
                        className={cn("flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1.5 hover:bg-accent", selectedBank?.name === bank.name && "bg-accent")}
                    >
                        <BankLabel bank={bank} />
                        {selectedBank?.name === bank.name && <Check className="size-4 shrink-0" />}
                    </button>
                ))}
            </PopoverContent>
        </Popover>
    )
}

const BankPickerItem = ({ bank, size = 'base' }: { bank: SelectedBank, size?: 'base' | 'sm' | 'row' }) => {

    const [selectedBank, setSelectedBank] = useAtom(selectedBankAccountAtom)

    const isSelected = selectedBank?.name === bank.name

    const { mutate } = useGetUnreconciledTransactions()

    const onSelect = () => {
        setSelectedBank(bank)
        mutate()
    }

    //// Neoffice — the compact card of the bank reconciliation screen (Daniel, 05.11: « le logo puis le nom à côté,
    //// comme ça on n'a que deux lignes et pas trois »): what matters is the list below, not the top of the page.
    if (size === 'row') {
        return <div
            role="button"
            title={_("Select {0}", [bank.account_name ?? ''])}
            onClick={onSelect}
            className={cn('flex min-w-56 max-w-72 cursor-pointer items-center gap-2 rounded-md border-2 bg-card px-2 py-1',
                isSelected ? 'border-primary bg-primary-foreground' : 'border-gray-200 hover:bg-gray-50')}
        >
            {bank.logo
                ? <img src={`/assets/mint/mint/${bank.logo}`} alt={bank.bank || bank.name || ''} className="object-contain"
                    style={{ maxWidth: '72px', maxHeight: '22px', width: 'auto', height: 'auto' }} />
                : bank.logo_mark
                    ? <img src={`/assets/mint/mint/${bank.logo_mark}`} alt="" style={{ width: '20px', height: '20px' }} />
                    : <Landmark size="18px" />}
            <div className="flex min-w-0 flex-col leading-tight">
                <span className="truncate text-sm font-medium">{bank.account_name}</span>
                <span title={_("GL Account")} className="truncate text-xs text-muted-foreground">{bank.account}</span>
            </div>
        </div>
    }

    return <div
        role="button"
        //// Neoffice — wrapped in _() (1f2847e). Upstream builds the tooltip with a template literal,
        //// `Select ${bank.account_name}`, which the extractor cannot see: it stayed English.
        title={_("Select {0}", [bank.account_name ?? ''])}
        onClick={onSelect}
        className={cn('rounded-md border-2 border-gray-200 min-w-80 relative p-2 bg-card overflow-hidden cursor-pointer',
            isSelected ? 'border-primary bg-primary-foreground' : 'hover:bg-gray-50',
            {
                "max-w-60 min-w-60": size === 'sm',
            }
        )}
    >
        {bank.logo ? <img
            src={`/assets/mint/mint/${bank.logo}`}
            alt={bank.bank || bank.name || ''}
            //// Neoffice — the inline style bounding the logo is OURS (e582a55): upstream pins the image
            //// to a fixed height, which squashed the wide Swiss logos (PostFinance, Raiffeisen). The
            //// surrounding cn() blocks with size === 'sm' are upstream v1.5.0 (89e7929). Keep both.
            className={cn("object-left object-contain mb-1", {
                'mb-2': size === 'sm',
            })}
            //// Neoffice — the bounding style is ours (e582a55), see the marker above className.
            style={size === 'sm'
                ? { maxWidth: '64px', maxHeight: '20px', width: 'auto', height: 'auto' }
                : { maxWidth: '112px', maxHeight: '32px', width: 'auto', height: 'auto' }}
        /> : <div className={cn("rounded-md flex items-center h-10 gap-2", {
            "h-6 mb-2": size === 'sm',
        })}>
            {/* //// Neoffice — the bank's symbol in place of the generic icon when no full logo */}
            {/* //// exists (BCGE: its symbol alone, beside its name; logos.ts, 01.10). */}
            {bank.logo_mark ? <img
                src={`/assets/mint/mint/${bank.logo_mark}`}
                alt=""
                style={size === 'sm' ? { width: '16px', height: '16px' } : { width: '30px', height: '30px' }}
            /> : <Landmark size={size === 'sm' ? '16px' : '30px'} />}
            <H4 className={cn("text-base mb-0", {
                'text-xs': size === 'sm',
            })}>{bank.bank}</H4>
        </div>}

        <div className="flex flex-col gap-0.5">
            {/* //// Neoffice — the _("GL Account") wrap on the next line is ours (1f2847e). */}
            <span className={cn("tracking-tight font-medium", {
                'text-xs': size === 'sm',
            })}>{bank.account_name}</span>
            <span title={_("GL Account")} className={cn("text-ellipsis line-clamp-1", size === 'sm' ? 'text-xs' : "text-sm")}>{bank.account}</span>
            {bank.last_integration_date && size !== 'sm' && <span className="text-xs text-muted-foreground">{_("Last Synced Transaction")}: {getTimeago(bank.last_integration_date)}</span>}
        </div>

        <div className={cn("absolute -top-1 right-0", {
            "-top-1.5": size === 'sm',
        })}>
            {bank.account_type && <span className={cn("uppercase rounded-bl-sm text-xs tracking-tight font-semibold py-1 px-1.5",
                isSelected ? 'bg-primary text-primary-foreground' : 'bg-gray-200 text-secondary-foreground/70',
                {
                    'text-[10px]': size === 'sm',
                }
            )}>
                {bank.account_type?.slice(0, 24)}
            </span>}
        </div>

    </div >
}

export default BankPicker