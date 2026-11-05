//// Neoffice — added file (no upstream equivalent). The bank files tab: every bank file that came in (by the bank connection or
//// deposited by hand), what became of each of its lines, and the ways to bring a new one in.
import { useAtomValue } from "jotai"
import { ImportIcon, Info } from "lucide-react"
import { selectedBankAccountAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import { Button } from "@/components/ui/button"
import _ from "@/lib/translate"
import { depositStatement } from "./depositStatement"
import StatementImportList from "./StatementImportList"

const StatementImportsPanel = () => {
    const bankAccount = useAtomValue(selectedBankAccountAtom)

    return (
        <div className="flex flex-col gap-4 pt-2">
            <div className="flex flex-wrap items-center justify-end gap-2">
                {/* the explanation is behind the icon: the list is what the person came for */}
                <span title={_("Every bank file that came in, by the bank connection or deposited by hand, and what became of each of its lines: passed by the import, reconciled afterwards, or still waiting for someone.")}>
                    <Info className="size-4 text-muted-foreground" />
                </span>
                <Button size="sm" onClick={() => depositStatement(bankAccount?.name)}>
                    <ImportIcon className="size-4" />{_("Import a bank statement (XML or PDF)")}
                </Button>
            </div>
            {bankAccount ? (
                <StatementImportList bankAccount={bankAccount.name} currency={bankAccount.account_currency ?? ""} version={0} />
            ) : null}
        </div>
    )
}

export default StatementImportsPanel
