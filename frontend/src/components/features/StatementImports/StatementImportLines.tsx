//// Neoffice — added file (no upstream equivalent). The lines of one import and what became of each.
import { useFrappeGetCall } from "frappe-react-sdk"
import { useState } from "react"
import ErrorBanner from "@/components/ui/error-banner"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatDate } from "@/lib/date"
import { formatCurrency } from "@/lib/numbers"
import _ from "@/lib/translate"
import { cn } from "@/lib/utils"
import { API } from "./api"
import type { ImportOverview } from "./types"
import { describeLine, documentHref, stateLabel, stateTone } from "./utils"

const WAITING = ["to_decide", "to_match"]

const StatementImportLines = ({ name, currency, version }: { name: string, currency: string, version: number }) => {
    // the view the person chose; until they choose, what waits when something waits, else everything
    const [chosen, setChosen] = useState<"waiting" | "all" | null>(null)
    const { data, error, isLoading } = useFrappeGetCall<{ message: ImportOverview }>(
        `${API}.get_import_overview`,
        { name },
        ["statement-imports", "overview", name, version],
        { revalidateOnFocus: false },
    )

    if (error) return <ErrorBanner error={error} />
    if (isLoading || !data) return <Skeleton className="h-24 w-full" />

    const waitingCount = data.message.lines.filter((line) => WAITING.includes(line.state)).length
    const view = chosen ?? (waitingCount > 0 ? "waiting" : "all")
    const lines = data.message.lines.filter((line) => view === "all" || WAITING.includes(line.state))

    return (
        <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2" role="group" aria-label={_("Lines shown")}>
                <Button size="sm" variant={view === "waiting" ? "default" : "outline"} onClick={() => setChosen("waiting")}>
                    {_("Waiting ({0})", [String(waitingCount)])}
                </Button>
                <Button size="sm" variant={view === "all" ? "default" : "outline"} onClick={() => setChosen("all")}>
                    {_("All ({0})", [String(data.message.lines.length)])}
                </Button>
            </div>
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>{_("Date")}</TableHead>
                        <TableHead>{_("Description")}</TableHead>
                        <TableHead className="text-right">{_("Amount")}</TableHead>
                        <TableHead>{_("State")}</TableHead>
                        <TableHead>{_("What became of it")}</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {lines.map((line) => (
                        <TableRow key={line.idx}>
                            <TableCell className="whitespace-nowrap">{formatDate(line.date, "Do MMM YYYY")}</TableCell>
                            <TableCell className="max-w-[18rem]">
                                <div className="truncate font-medium">{line.party || line.description}</div>
                                {line.party && line.description && <div className="truncate text-xs text-muted-foreground">{line.description}</div>}
                            </TableCell>
                            <TableCell className={cn("text-right font-mono tabular-nums whitespace-nowrap", line.direction === "out" && "text-muted-foreground")}>
                                {line.direction === "out" ? "−" : "+"}{formatCurrency(line.amount, currency)}
                            </TableCell>
                            <TableCell>
                                <span className={cn("inline-flex whitespace-nowrap rounded-sm border px-2 py-0.5 text-xs font-medium", stateTone(line.state))}>
                                    {stateLabel(line.state)}
                                </span>
                            </TableCell>
                            <TableCell className="text-sm">
                                <div>{describeLine(line, currency)}</div>
                                <div className="flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                                    {line.vouchers.map((voucher) => (
                                        <a key={voucher.name} className="underline underline-offset-2" href={documentHref(voucher.doctype, voucher.name)}>{voucher.name}</a>
                                    ))}
                                    {line.credit_note && (
                                        <a className="underline underline-offset-2" href={documentHref("Sales Invoice", line.credit_note)}>{line.credit_note}</a>
                                    )}
                                    {line.bank_transaction && (
                                        <a className="underline underline-offset-2" href={documentHref("Bank Transaction", line.bank_transaction)}>{line.bank_transaction}</a>
                                    )}
                                </div>
                            </TableCell>
                        </TableRow>
                    ))}
                    {lines.length === 0 && (
                        <TableRow>
                            <TableCell colSpan={5} className="py-6 text-center text-muted-foreground">{_("Nothing waits in this import.")}</TableCell>
                        </TableRow>
                    )}
                </TableBody>
            </Table>
        </div>
    )
}

export default StatementImportLines
