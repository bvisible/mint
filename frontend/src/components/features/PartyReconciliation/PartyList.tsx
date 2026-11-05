//// Neoffice — added file (no upstream equivalent). The customers or suppliers that have something to reconcile.
import { useFrappeGetCall } from "frappe-react-sdk"
import { Search } from "lucide-react"
import { useEffect, useState } from "react"
import ErrorBanner from "@/components/ui/error-banner"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { formatDate } from "@/lib/date"
import { formatCurrency } from "@/lib/numbers"
import _ from "@/lib/translate"
import { cn } from "@/lib/utils"
import type { PartyRow, PartyType } from "./types"

type Props = {
    company: string,
    partyType: PartyType,
    selected: string | null,
    onSelect: (party: string) => void,
    /** Raised by the screen after a reconciliation: the list is asked again. */
    version: number,
    currency: string,
}

const PartyList = ({ company, partyType, selected, onSelect, version, currency }: Props) => {
    const [search, setSearch] = useState("")
    const [typed, setTyped] = useState("")
    const [onlyReconcilable, setOnlyReconcilable] = useState(true)

    // One request per pause in typing, not per key.
    useEffect(() => {
        const timer = window.setTimeout(() => setSearch(typed), 250)
        return () => window.clearTimeout(timer)
    }, [typed])

    const { data, error, isLoading } = useFrappeGetCall<{ message: PartyRow[] }>(
        "mint.apis.party_reconciliation.get_parties",
        { company, party_type: partyType, search, only_open: onlyReconcilable ? 1 : 0, limit: 200 },
        ["party-reconciliation", "parties", company, partyType, search, onlyReconcilable, version],
        { revalidateOnFocus: false },
    )

    const parties = data?.message ?? []

    return (
        <div className="flex flex-col gap-3 min-w-0">
            <div className="relative">
                <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
                <Input
                    className="pl-8"
                    value={typed}
                    onChange={(event) => setTyped(event.target.value)}
                    placeholder={partyType === "Customer" ? _("Search a customer") : _("Search a supplier")}
                />
            </div>
            <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <Switch checked={onlyReconcilable} onCheckedChange={setOnlyReconcilable} />
                {_("Only those with something to reconcile")}
            </label>

            {error && <ErrorBanner error={error} />}

            <div className="flex flex-col gap-1">
                {isLoading && [0, 1, 2, 3].map((index) => <Skeleton key={index} className="h-16 w-full" />)}
                {!isLoading && parties.length === 0 && (
                    <p className="text-sm text-muted-foreground py-6 text-center">
                        {onlyReconcilable ? _("Nothing to reconcile.") : _("No open documents.")}
                    </p>
                )}
                {parties.map((party) => (
                    <button
                        key={party.party}
                        type="button"
                        onClick={() => onSelect(party.party)}
                        className={cn(
                            "text-left rounded-md border px-3 py-2 transition-colors hover:bg-accent min-w-0",
                            selected === party.party && "bg-accent border-primary",
                        )}>
                        <div className="font-medium truncate">{party.label}</div>
                        <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                            <span>{party.open_count} {_("open")}</span>
                            <span className="font-mono tabular-nums">{formatCurrency(party.open, currency)}</span>
                        </div>
                        <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                            <span>{party.credit_count} {_("to apply")}</span>
                            <span className="font-mono tabular-nums">{formatCurrency(party.credit, currency)}</span>
                        </div>
                        {party.oldest && (
                            <div className="mt-1 text-xs text-muted-foreground">{_("Since")} {formatDate(party.oldest)}</div>
                        )}
                    </button>
                ))}
            </div>
        </div>
    )
}

export default PartyList
