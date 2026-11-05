//// Neoffice — added file (no upstream equivalent). The reports of the reconciliation page (the statement, the clearance summary, the
//// entries cleared incorrectly) behind ONE tab: six tabs did not fit on a line, and these three are read from time to time, not
//// worked in. The tab shows the name of the report that is open, so that the person knows where she is.
import { ChevronDown } from "lucide-react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import _ from "@/lib/translate"
import { cn } from "@/lib/utils"

export type Report = { value: string; label: string }

// the look of a tab of components/ui/tabs.tsx, for a trigger that opens a menu instead of choosing a tab
const LOOK =
    "data-[state=active]:bg-background data-[state=active]:shadow-sm text-foreground inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center gap-1.5 rounded-md border border-transparent px-2 py-1 text-sm font-medium whitespace-nowrap transition-[color,box-shadow] focus-visible:ring-[3px] focus-visible:ring-ring/50 [&_svg]:pointer-events-none [&_svg]:shrink-0"

const ReportsMenu = ({ reports, value, onSelect }: { reports: Report[]; value: string; onSelect: (value: string) => void }) => {
    const open = reports.find((report) => report.value === value)

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <button type="button" role="tab" aria-selected={!!open} data-state={open ? "active" : "inactive"} className={cn(LOOK)}>
                    {open ? open.label : _("Reports")}
                    <ChevronDown className="size-4" />
                </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
                {reports.map((report) => (
                    <DropdownMenuItem key={report.value} onSelect={() => onSelect(report.value)}>
                        {report.label}
                    </DropdownMenuItem>
                ))}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}

export default ReportsMenu
