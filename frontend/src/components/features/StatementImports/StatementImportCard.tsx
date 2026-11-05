//// Neoffice — added file (no upstream equivalent). One import: when, where from, how far along, and its lines.
import { ChevronDown, ChevronRight } from "lucide-react"
import { useState } from "react"
import { useAtom, useSetAtom } from "jotai"
import { useFrappeGetCall } from "frappe-react-sdk"
import { bankRecDateAtom, bankRecImportFilterAtom, bankRecTabAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { formatDate } from "@/lib/date"
import _ from "@/lib/translate"
import { cn } from "@/lib/utils"
import { API } from "./api"
import StatementImportLines from "./StatementImportLines"
import type { ImportOverview, StatementImport } from "./types"
import { STATE_ORDER, WAITING_STATES, sourceLabel, stateLabel, stateTone } from "./utils"

const StatementImportCard = ({ item, currency, version }: { item: StatementImport, currency: string, version: number }) => {
    const setTab = useSetAtom(bankRecTabAtom)
    const setImportFilter = useSetAtom(bankRecImportFilterAtom)
    const [dates, setDates] = useAtom(bankRecDateAtom)
    const { progress, counts } = item
    // the lines of this file: the same call, and the same key, as the table below, so that it is asked once
    const { data: overview } = useFrappeGetCall<{ message: ImportOverview }>(
        `${API}.get_import_overview`,
        { name: item.name },
        progress.waiting > 0 ? ["statement-imports", "overview", item.name, version] : null,
        { revalidateOnFocus: false },
    )
    // open where something waits (the person has to open it to deal with it), closed where nothing does
    const [open, setOpen] = useState(progress.waiting > 0)
    const percent = progress.total ? (progress.done / progress.total) * 100 : 0
    const draft = item.docstatus === 0

    // « Process the N that wait »: the reconciliation, on the lines of THIS file that wait, the first one open. Without the file's
    // lines the button only changed the tab and the person landed on the whole list, with nothing to say which lines were hers.
    const processWaiting = () => {
        const waiting = (overview?.message.lines ?? []).filter((line) => WAITING_STATES.includes(line.state) && line.bank_transaction)
        if (waiting.length > 0) {
            const days = waiting.map((line) => line.date).sort()
            // the period of the page must hold them: a file of last month is not in « this month »
            setDates({
                fromDate: days[0] < dates.fromDate ? days[0] : dates.fromDate,
                toDate: days[days.length - 1] > dates.toDate ? days[days.length - 1] : dates.toDate,
            })
            setImportFilter({
                label: formatDate(item.creation, "Do MMM YYYY"),
                lines: waiting.map((line) => line.bank_transaction as string),
            })
        }
        setTab("Match and Reconcile")
    }

    return (
        <div className="rounded-lg border bg-card text-card-foreground">
            <div className="flex flex-col gap-3 p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                        <div className="font-medium">{formatDate(item.creation, "Do MMM YYYY")}</div>
                        <div className="text-xs text-muted-foreground">
                            {sourceLabel(item.source)}
                            {item.source === "manual" && item.owner ? ` · ${item.owner}` : ""}
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {draft && <Badge variant="outline">{_("Draft")}</Badge>}
                        {!draft && progress.total > 0 && progress.waiting === 0 && <Badge variant="secondary">{_("Everything is dealt with")}</Badge>}
                        {progress.waiting > 0 && (
                            <Button size="sm" onClick={processWaiting}>
                                {_("Process the {0} that wait", [String(progress.waiting)])}
                            </Button>
                        )}
                    </div>
                </div>

                {progress.total > 0 ? (
                    <div className="flex flex-col gap-1">
                        <div className="text-sm font-medium">
                            {_("{0} / {1} dealt with", [String(progress.done), String(progress.total)])}
                        </div>
                        <Progress value={percent} max={100} />
                    </div>
                ) : (
                    <div className="text-sm text-muted-foreground">
                        {draft ? _("Nothing was imported yet.") : _("Nothing to handle: every line was already in the bank.")}
                    </div>
                )}

                <div className="flex flex-wrap gap-2">
                    {STATE_ORDER.filter((state) => counts[state] > 0).map((state) => (
                        <span key={state} className={cn("inline-flex whitespace-nowrap rounded-sm border px-2 py-0.5 text-xs font-medium", stateTone(state))}>
                            {counts[state]} {stateLabel(state)}
                        </span>
                    ))}
                </div>

                <button
                    type="button"
                    className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
                    onClick={() => setOpen((current) => !current)}
                    aria-expanded={open}
                >
                    {open ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                    {open ? _("Hide the lines") : _("Show the lines")}
                </button>
            </div>
            {open && (
                <div className="border-t p-4">
                    <StatementImportLines name={item.name} currency={currency} version={version} />
                </div>
            )}
        </div>
    )
}

export default StatementImportCard
