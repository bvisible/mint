import { useAtom, useSetAtom } from "jotai"
import { SelectedBank, selectedBankAccountAtom } from "./bankRecAtoms"
import { useCallback } from "react"
import { useGetBankAccounts, useGetUnreconciledTransactions } from "./utils"
import { cn } from "@/lib/utils"
import { Landmark } from "lucide-react"
import { H4 } from "@/components/ui/typography"
import { getTimeago } from "@/lib/date"
import ErrorBanner from "@/components/ui/error-banner"
import _ from "@/lib/translate"

////// Neoffice — NOT ours: the size prop is upstream v1.5.0, hand-carried (89e7929); the
////// statement importer renders the same picker in a compact form. Take upstream's.
const BankPicker = ({ className, size = 'base' }: { className?: string, size?: 'base' | 'sm' }) => {

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
    return (
        <div
            className={cn("flex gap-3 items-stretch w-full overflow-x-auto bank-picker-scrollbar pr-4",
                ////// Neoffice — NOT ours: upstream v1.5.0 scroll padding, hand-carried (89e7929).
                banks?.length > 4 ? 'pb-2' : '', className,
            )}
            style={{
                scrollbarWidth: 'thin',
                scrollbarColor: 'rgb(209 213 219) rgb(243 244 246)',
            }}
        >
            {
                banks?.map((bank) => (
                    ////// Neoffice — NOT ours: size forwarded to the item, upstream v1.5.0 (89e7929).
                    <BankPickerItem key={bank.name} bank={bank} size={size} />
                ))
            }
        </div>
    )
}

////// Neoffice — NOT ours: upstream v1.5.0 signature, hand-carried (89e7929).
const BankPickerItem = ({ bank, size = 'base' }: { bank: SelectedBank, size?: 'base' | 'sm' }) => {

    const [selectedBank, setSelectedBank] = useAtom(selectedBankAccountAtom)

    const isSelected = selectedBank?.name === bank.name

    const { mutate } = useGetUnreconciledTransactions()

    const onSelect = () => {
        setSelectedBank(bank)
        mutate()
    }

    return <div
        role="button"
        ////// Neoffice — wrapped in _() (1f2847e). Upstream builds the tooltip with a template literal,
        ////// `Select ${bank.account_name}`, which the extractor cannot see: it stayed English.
        title={_("Select {0}", [bank.account_name ?? ''])}
        onClick={onSelect}
        className={cn('rounded-md border-2 border-gray-200 min-w-80 relative p-2 bg-card overflow-hidden cursor-pointer',
            ////// Neoffice — NOT ours: upstream v1.5.0 compact-size classes, hand-carried (89e7929).
            isSelected ? 'border-primary bg-primary-foreground' : 'hover:bg-gray-50',
            {
                "max-w-60 min-w-60": size === 'sm',
            }
        )}
    >
        {bank.logo ? <img
            src={`/assets/mint/mint/${bank.logo}`}
            alt={bank.bank || bank.name || ''}
            ////// Neoffice — the inline style bounding the logo is OURS (e582a55): upstream pins the image
            ////// to a fixed height, which squashed the wide Swiss logos (PostFinance, Raiffeisen). The
            ////// surrounding cn() blocks with size === 'sm' are upstream v1.5.0 (89e7929). Keep both.
            className={cn("object-left object-contain mb-1", {
                'mb-2': size === 'sm',
            })}
            style={size === 'sm'
                ? { maxWidth: '64px', maxHeight: '20px', width: 'auto', height: 'auto' }
                : { maxWidth: '112px', maxHeight: '32px', width: 'auto', height: 'auto' }}
        /> : <div className={cn("rounded-md flex items-center h-10 gap-2", {
            "h-6 mb-2": size === 'sm',
        })}>
            <Landmark size={size === 'sm' ? '16px' : '30px'} />
            <H4 className={cn("text-base mb-0", {
                'text-xs': size === 'sm',
            })}>{bank.bank}</H4>
        </div>}

        <div className="flex flex-col gap-0.5">
            {/*//// Neoffice — NOT ours below, except the _("GL Account") wrap on the next line, which is */}
            {/*//// ours (1f2847e): the rest is upstream v1.5.0's compact size (89e7929). */}
            <span className={cn("tracking-tight font-medium", {
                'text-xs': size === 'sm',
            })}>{bank.account_name}</span>
            <span title={_("GL Account")} className={cn("text-ellipsis line-clamp-1", size === 'sm' ? 'text-xs' : "text-sm")}>{bank.account}</span>
            {bank.last_integration_date && size !== 'sm' && <span className="text-xs text-muted-foreground">{_("Last Synced Transaction")}: {getTimeago(bank.last_integration_date)}</span>}
        </div>

        {/*//// Neoffice — NOT ours: upstream v1.5.0 compact-size offsets, hand-carried (89e7929). */}
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
            {/*//// Neoffice — NOT ours: upstream v1.5.0 guards the badge on account_type being set, so the */}
            {/*//// closing brace moved. Hand-carried (89e7929). */}
            </span>}
        </div>

    {/*//// Neoffice — NOT ours: a stray space in the closing tag, from upstream v1.5.0 (89e7929). */}
    </div >
}

export default BankPicker