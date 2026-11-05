//// Neoffice — added file (no upstream equivalent). « Imports »: what each bank statement brought in and what became
//// of each of its lines, read from the bank lines themselves, so that it is right whoever reconciled them and where.
import { useAtomValue } from "jotai"
import { FileSpreadsheet, FileText, ImportIcon, Info } from "lucide-react"
import { Link } from "react-router"
import BankPicker from "@/components/features/BankReconciliation/BankPicker"
import { selectedBankAccountAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import CompanySelector from "@/components/features/BankReconciliation/CompanySelector"
import StatementImportList from "@/components/features/StatementImports/StatementImportList"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { TooltipProvider } from "@/components/ui/tooltip"
import { H1 } from "@/components/ui/typography"
import { EMBEDDED, outerWindow } from "@/lib/embedded"
import _ from "@/lib/translate"

const StatementImports = () => {
    const bankAccount = useAtomValue(selectedBankAccountAtom)
    // a statement of the bank (XML, PDF) is deposited in the form of the desk, for the bank account of the page; a CSV or an
    // Excel file goes through the importer of Mint
    const depositStatement = () => {
        const query = bankAccount ? `?bank_account=${encodeURIComponent(bankAccount.name)}` : ""
        outerWindow().location.assign(`/app/mint-bank-statement-import/new${query}`)
    }

    return (
        <TooltipProvider>
            <div className="@container p-4 flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    {!EMBEDDED && <H1 className="text-sm font-medium">{_("Imports")}</H1>}
                    <div className="flex flex-wrap items-center gap-2">
                        {/* the explanation is behind the icon: the list is what the person came for */}
                        <span title={_("Every bank statement that came in, and what became of each of its lines: passed by the import, reconciled afterwards, or still waiting for someone.")}>
                            <Info className="size-4 text-muted-foreground" />
                        </span>
                        <CompanySelector />
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button size="sm">
                                    <ImportIcon className="size-4" />{_("Import a statement")}
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onSelect={depositStatement}>
                                    <FileText className="size-4" />{_("Statement from the bank (XML or PDF)")}
                                </DropdownMenuItem>
                                <DropdownMenuItem asChild>
                                    <Link to="/statement-importer">
                                        <FileSpreadsheet className="size-4" />{_("CSV or Excel file")}
                                    </Link>
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                        <Button variant="outline" size="sm" asChild>
                            <Link to="/">{_("Bank Reconciliation")}</Link>
                        </Button>
                    </div>
                </div>
                <BankPicker />
                {bankAccount ? (
                    <StatementImportList
                        bankAccount={bankAccount.name}
                        currency={bankAccount.account_currency ?? ""}
                        version={0}
                    />
                ) : null}
            </div>
        </TooltipProvider>
    )
}

export default StatementImports
