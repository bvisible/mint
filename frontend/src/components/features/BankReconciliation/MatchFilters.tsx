import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import _ from '@/lib/translate'
import { Settings } from 'lucide-react'
////// Neoffice — added import (88a7d8b) for the draft Journal Entry toggle below.
import { bankRecMatchFilters, bankRecIncludeDraftJE } from './bankRecAtoms'
import { useAtom, useAtomValue } from 'jotai'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Separator } from '@/components/ui/separator'

const MatchFilters = () => {
////// Neoffice — added (88a7d8b). The Include Drafts switch only makes sense when Journal Entry
////// is among the document types, so its visibility is derived here. Upstream's component has
////// no state at all.

    const matchFilters = useAtomValue(bankRecMatchFilters)
    const showDraftOption = matchFilters.includes('journal_entry')

    return (
        <Popover>
            <Tooltip>
                <PopoverTrigger asChild>
                    <TooltipTrigger asChild>
                        <Button size='sm' variant='outline' aria-label={_("Configure match filters for vouchers")}>
                            <Settings />
                        </Button>
                    </TooltipTrigger>
                </PopoverTrigger>
                <TooltipContent>
                    {_("Configure match filters for vouchers")}
                </TooltipContent>
            </Tooltip>
            <PopoverContent>
                <div className="flex flex-col gap-4">
                    <ToggleSwitch label={_("Show Only Exact Amount")} id="exact_match" />
                    <Separator />
                    <ToggleSwitch label={_("Payment Entry")} id="payment_entry" />
                    <ToggleSwitch label={_("Journal Entry")} id="journal_entry" />
                    {/*//// Neoffice — added row (88a7d8b): the Include Drafts switch, indented under Journal Entry. */}
                    {showDraftOption && <IncludeDraftToggle />}
                    <ToggleSwitch label={_("Purchase Invoice")} id="purchase_invoice" />
                    <ToggleSwitch label={_("Sales Invoice")} id="sales_invoice" />
                    <ToggleSwitch label={_("Expense Claim")} id="expense_claim" />
                    <ToggleSwitch label={_("Bank Transaction")} id="bank_transaction" />
                </div>
            </PopoverContent>
        </Popover>
    )
}

const ToggleSwitch = ({ label, id }: { label: string, id: string }) => {

    const [matchFilters, setMatchFilters] = useAtom(bankRecMatchFilters)

    return <div className="flex items-center space-x-2">
        <Switch id={id} checked={matchFilters.includes(id)} onCheckedChange={(checked) => {
            if (checked) {
                setMatchFilters([...matchFilters, id])
            } else {
                setMatchFilters(matchFilters.filter(filter => filter !== id))
            }
        }} />
        <Label htmlFor={id}>{label}</Label>
    </div>
}

////// Neoffice — added component (88a7d8b). Drives bankRecIncludeDraftJE, which utils.ts passes
////// to our get_linked_payments wrapper. No upstream equivalent: ERPNext only ever returns
////// submitted vouchers.
const IncludeDraftToggle = () => {

    const [includeDraft, setIncludeDraft] = useAtom(bankRecIncludeDraftJE)

    return <div className="flex items-center space-x-2 pl-4">
        <Switch id="include_draft_je" checked={includeDraft} onCheckedChange={setIncludeDraft} />
        <Label htmlFor="include_draft_je" className="text-muted-foreground text-sm">
            {_("Include Drafts")}
        </Label>
    </div>
}

export default MatchFilters