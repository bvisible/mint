//// Neoffice — added file (no upstream equivalent). « Imports »: what each bank statement brought in and what became
//// of each of its lines, read from the bank lines themselves, so that it is right whoever reconciled them and where.
import { useAtomValue } from "jotai"
import { Link } from "react-router"
import BankPicker from "@/components/features/BankReconciliation/BankPicker"
import { selectedBankAccountAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import CompanySelector from "@/components/features/BankReconciliation/CompanySelector"
import StatementImportList from "@/components/features/StatementImports/StatementImportList"
import { Button } from "@/components/ui/button"
import { TooltipProvider } from "@/components/ui/tooltip"
import { H1, Paragraph } from "@/components/ui/typography"
import { EMBEDDED } from "@/lib/embedded"
import _ from "@/lib/translate"

const StatementImports = () => {
    const bankAccount = useAtomValue(selectedBankAccountAtom)

    return (
        <TooltipProvider>
            <div className="@container p-4 flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    {!EMBEDDED && <H1 className="text-sm font-medium">{_("Imports")}</H1>}
                    <div className="flex flex-wrap items-center gap-2">
                        <CompanySelector />
                        <Button variant="outline" size="sm" asChild>
                            <Link to="/">{_("Bank Reconciliation")}</Link>
                        </Button>
                    </div>
                </div>
                <BankPicker />
                <Paragraph className="text-sm text-muted-foreground">
                    {_("Every bank statement that came in, and what became of each of its lines: passed by the import, reconciled afterwards, or still waiting for someone.")}
                </Paragraph>
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
