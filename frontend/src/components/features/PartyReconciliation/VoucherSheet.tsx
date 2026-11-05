//// Neoffice — added file (no upstream equivalent). What a click on a row shows: the lines, the remark, who made it.
import { useFrappeGetCall } from "frappe-react-sdk"
import { Copy, ExternalLink } from "lucide-react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import ErrorBanner from "@/components/ui/error-banner"
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { formatDate } from "@/lib/date"
import _ from "@/lib/translate"
import type { VoucherDetailData } from "./types"

export type VoucherRef = { type: string, name: string }

type Props = { voucher: VoucherRef | null, onClose: () => void }

const COLUMNS: Record<string, string> = {
    account: "Account", party: "Party", debit: "Debit", credit: "Credit", remark: "Remarks",
    reference: "Reference", allocated: "Allocated", outstanding: "Outstanding Amount", item: "Item", qty: "Quantity", amount: "Amount",
}

const VoucherSheet = ({ voucher, onClose }: Props) => {
    const { data, error, isLoading } = useFrappeGetCall<{ message: VoucherDetailData }>(
        "mint.apis.party_reconciliation.get_voucher_detail",
        { voucher_type: voucher?.type, voucher_name: voucher?.name },
        // null: nothing is asked while no row is open
        voucher ? ["party-reconciliation", "voucher", voucher.type, voucher.name] : null,
        { revalidateOnFocus: false },
    )
    const detail = data?.message

    const copy = async (text: string) => {
        try {
            await navigator.clipboard.writeText(text)
            toast.success(_("Copied"))
        } catch {
            toast.error(_("Could not copy"))
        }
    }

    const columns = detail?.lines.length ? Object.keys(detail.lines[0]).filter((key) => key in COLUMNS) : []

    return (
        <Sheet open={voucher !== null} onOpenChange={(open) => { if (!open) onClose() }}>
            <SheetContent className="sm:max-w-xl w-full overflow-y-auto">
                <SheetHeader>
                    <SheetTitle>{voucher ? `${_(voucher.type)} ${voucher.name}` : ""}</SheetTitle>
                    <SheetDescription>{detail ? [detail.posting_date ? formatDate(detail.posting_date) : "", detail.owner].filter(Boolean).join(" · ") : ""}</SheetDescription>
                </SheetHeader>
                <div className="flex flex-col gap-4 px-4 pb-4">
                    {error && <ErrorBanner error={error} />}
                    {isLoading && <Skeleton className="h-40 w-full" />}
                    {detail && (
                        <>
                            <div className="flex flex-wrap items-center gap-2">
                                <Badge variant="secondary">{_(detail.status)}</Badge>
                                {detail.reference && <span className="text-sm">{_("Reference")}: <span className="font-mono">{detail.reference}</span></span>}
                                {detail.attachments > 0 && <span className="text-sm text-muted-foreground">{detail.attachments} {_("attachment(s)")}</span>}
                            </div>
                            {detail.remark && <p className="text-sm whitespace-pre-line text-muted-foreground">{detail.remark}</p>}
                            <p className="text-xs text-muted-foreground">{_("Created")} {formatDate(detail.creation)}</p>

                            {columns.length > 0 && (
                                <Table>
                                    <TableHeader>
                                        <TableRow>{columns.map((key) => <TableHead key={key}>{_(COLUMNS[key])}</TableHead>)}</TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {detail.lines.map((line, index) => (
                                            <TableRow key={index}>
                                                {columns.map((key) => (
                                                    <TableCell key={key} className={typeof line[key] === "number" ? "font-mono tabular-nums text-right" : ""}>{line[key] ?? ""}</TableCell>
                                                ))}
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            )}

                            <div className="flex flex-wrap gap-2">
                                <Button variant="outline" onClick={() => window.open(detail.route, "_blank", "noopener")}>
                                    <ExternalLink className="size-4" />{_("Open in a new tab")}
                                </Button>
                                <Button variant="ghost" onClick={() => copy(detail.reference || detail.name)}>
                                    <Copy className="size-4" />{_("Copy the reference")}
                                </Button>
                            </div>
                        </>
                    )}
                </div>
            </SheetContent>
        </Sheet>
    )
}

export default VoucherSheet
