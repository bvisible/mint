//// Neoffice — added file (no upstream equivalent). The bank files tab: every bank file that came in (by the bank connection or
//// deposited by hand), what became of each of its lines, and the ways to bring a new one in.
import { useAtomValue } from "jotai"
import { FileSpreadsheet, FileText, ImportIcon, Info } from "lucide-react"
import { Link } from "react-router"
import { selectedBankAccountAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { outerWindow } from "@/lib/embedded"
import _ from "@/lib/translate"
import StatementImportList from "./StatementImportList"

const StatementImportsPanel = () => {
    const bankAccount = useAtomValue(selectedBankAccountAtom)
    // a statement of the bank (XML, PDF) is deposited in the form of the desk, for the bank account of the page; a CSV or an
    // Excel file goes through the importer of Mint
    const depositStatement = () => {
        const query = bankAccount ? `?bank_account=${encodeURIComponent(bankAccount.name)}` : ""
        outerWindow().location.assign(`/app/mint-bank-statement-import/new${query}`)
    }

    return (
        <div className="flex flex-col gap-4 pt-2">
            <div className="flex flex-wrap items-center justify-end gap-2">
                {/* the explanation is behind the icon: the list is what the person came for */}
                <span title={_("Every bank file that came in, by the bank connection or deposited by hand, and what became of each of its lines: passed by the import, reconciled afterwards, or still waiting for someone.")}>
                    <Info className="size-4 text-muted-foreground" />
                </span>
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button size="sm">
                            <ImportIcon className="size-4" />{_("Import a bank file")}
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
            </div>
            {bankAccount ? (
                <StatementImportList bankAccount={bankAccount.name} currency={bankAccount.account_currency ?? ""} version={0} />
            ) : null}
        </div>
    )
}

export default StatementImportsPanel
