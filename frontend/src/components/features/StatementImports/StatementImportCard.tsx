//// Neoffice — added file (no upstream equivalent). One import: when, where from, how far along, and its lines.
import { ChevronDown, ChevronRight } from "lucide-react"
import { useState } from "react"
import { useSetAtom } from "jotai"
import { bankRecTabAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { formatDate } from "@/lib/date"
import _ from "@/lib/translate"
import { cn } from "@/lib/utils"
import StatementImportLines from "./StatementImportLines"
import type { StatementImport } from "./types"
import { STATE_ORDER, sourceLabel, stateLabel, stateTone } from "./utils"

const StatementImportCard = ({ item, currency, version }: { item: StatementImport, currency: string, version: number }) => {
    const setTab = useSetAtom(bankRecTabAtom)
    const { progress, counts } = item
    // open where something waits (the person has to open it to deal with it), closed where nothing does
    const [open, setOpen] = useState(progress.waiting > 0)
    const percent = progress.total ? (progress.done / progress.total) * 100 : 0
    const draft = item.docstatus === 0

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
                            <Button size="sm" onClick={() => setTab("Match and Reconcile")}>
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
