import BankBalance from "@/components/features/BankReconciliation/BankBalance"
import BankClearanceSummary from "@/components/features/BankReconciliation/BankClearanceSummary"
import BankPicker from "@/components/features/BankReconciliation/BankPicker"
import BankRecDateFilter from "@/components/features/BankReconciliation/BankRecDateFilter"
import BankReconciliationStatement from "@/components/features/BankReconciliation/BankReconciliationStatement"
import BankTransactions from "@/components/features/BankReconciliation/BankTransactionList"
import BankTransactionUnreconcileModal from "@/components/features/BankReconciliation/BankTransactionUnreconcileModal"
import CompanySelector from "@/components/features/BankReconciliation/CompanySelector"
import IncorrectlyClearedEntries from "@/components/features/BankReconciliation/IncorrectlyClearedEntries"
import MatchAndReconcile from "@/components/features/BankReconciliation/MatchAndReconcile"
import RuleConfigureButton from "@/components/features/BankReconciliation/Rules/RuleConfigureButton"
import Settings from "@/components/features/Settings/Settings"
import ActionLog from "@/components/features/ActionLog/ActionLog"
//// Neoffice — added (e38d1a6). FavoriteStar is ours: it pins /mint in the Neoffice cockpit's
//// favourites, a cockpit feature upstream does not have.
import FavoriteStar from "@/components/features/BankReconciliation/FavoriteStar"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { H1 } from "@/components/ui/typography"
import _ from "@/lib/translate"
//// Neoffice — added: framed in a tab of the desk (lib/embedded.ts).
import { EMBEDDED } from "@/lib/embedded"
import { useEffect, useLayoutEffect, useRef, useState } from "react"
//// Neoffice — added: the bank files tab (what each file brought in), and the tab shown as an atom.
import { useAtom } from "jotai"
import { bankRecTabAtom } from "@/components/features/BankReconciliation/bankRecAtoms"
import StatementImportsPanel from "@/components/features/StatementImports/StatementImportsPanel"
//// Neoffice — added: the three reports behind one tab.
import ReportsMenu from "@/components/features/BankReconciliation/ReportsMenu"


//// Neoffice — changed: takes the tab to open on (the old address of the imports opens the bank files tab) and keeps the tab shown
//// in an atom, so that a card of the bank files can take the person to the reconciliation tab.
const BankReconciliation = ({ initialTab }: { initialTab?: string }) => {

    const [tab, setTab] = useAtom(bankRecTabAtom)
    useEffect(() => {
        if (initialTab) setTab(initialTab)
    }, [initialTab, setTab])

    const ref = useRef<HTMLDivElement>(null)
    const tabsRef = useRef<HTMLDivElement>(null)

    //// Neoffice — the room left under the tabs, MEASURED: upstream subtracted a guessed 324 px from the window's height, which was
    //// wrong whenever the header wrapped or the frame was low, and the lists overflowed it (Daniel, 05.11). It follows the window
    //// and the header (the bank cards and the balances change its height).
    const [remainingHeightAfterTabs, setRoom] = useState(() => Math.max(300, window.innerHeight - 340))
    useLayoutEffect(() => {
        const measure = () => {
            const tabs = tabsRef.current
            if (!tabs) return
            const top = tabs.getBoundingClientRect().bottom + window.scrollY + 8
            // the page's own bottom padding (16 px) and a little air
            setRoom(Math.max(300, Math.round(window.innerHeight - top - 24)))
        }
        measure()
        window.addEventListener("resize", measure)
        const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(measure)
        if (observer && ref.current) observer.observe(ref.current)
        return () => {
            window.removeEventListener("resize", measure)
            observer?.disconnect()
        }
    }, [])

    return (
        <div className="p-4 flex flex-col gap-4">
            {/* //// Neoffice — gap-4 to gap-2: the top of the page is not what the person comes for. */}
            <div ref={ref} className="flex flex-col gap-2">
                {/* //// Neoffice — framed in a tab of the desk (lib/embedded.ts), the tab names the */}
                {/* //// page and the desk shows its logo: no title row, the tools go right and wrap */}
                {/* //// when the desk's page is narrow (they overflowed it, 01.10). */}
                <div className={EMBEDDED ? "flex flex-wrap justify-end gap-2" : "flex justify-between"}>
                    {/* //// Neoffice — rewritten header (031d31d, a822171, 1f2847e, e38d1a6). Upstream shows its own */}
                    {/* //// Mint wordmark; embedded in the Neoffice desk the page carries the Neoffice logo linking */}
                    {/* //// back to /app/home, then the page title and the favourite star. Cosmetic but ours: */}
                    {/* //// at the merge keep both sides and re-apply the logo block. */}
                    {!EMBEDDED && (
                        <H1 className="text-sm font-medium flex items-center gap-2 whitespace-nowrap shrink-0">
                            <a href="/app/home">
                                <img src="/assets/mint/mint/assets/neoffice_logo.svg" alt="Neoffice" className="h-7" />
                            </a>
                            <span className="text-gray-400">|</span>
                            {_("Bank Reconciliation")}
                            <FavoriteStar />
                        </H1>
                    )}
                    <div className="flex flex-wrap items-center gap-2">
                        <TooltipProvider>
                            {/* //// Neoffice — removed: the « Imports » button (the bank files are a tab now, below). */}
                            <RuleConfigureButton />
                            <Settings />
                            <ActionLog />
                        </TooltipProvider>
                        <CompanySelector />
                        <BankRecDateFilter />
                    </div>
                </div>
                {/* //// Neoffice — the compact bank cards: the screen keeps its height for the list below. */}
                <BankPicker size="row" />
                <BankBalance />
            </div>
            {/* //// Neoffice — changed: controlled by the atom (upstream: defaultValue="Match and Reconcile"). */}
            <Tabs value={tab} onValueChange={setTab}>
                {/* //// Neoffice — framed in a desk tab, six tabs do not fit the page's width: they overflowed both edges, then */}
                {/* //// wrapped on a second line. The three reports go behind one « Reports » tab (ReportsMenu), so the strip stays on one line; */}
                {/* //// the wrap stays as a safety net for a very narrow frame. */}
                <TabsList ref={tabsRef} className={EMBEDDED ? "w-full h-auto flex-wrap justify-start" : "w-full"}>
                    <TabsTrigger value="Match and Reconcile">{_("Match and Reconcile")}</TabsTrigger>
                    {/* //// Neoffice — added: the bank files that came in, and how to bring one in. */}
                    <TabsTrigger value="Bank Files">{_("Bank Files")}</TabsTrigger>
                    <TabsTrigger value="Bank Transactions">{_("Bank Transactions")}</TabsTrigger>
                    <ReportsMenu
                        reports={[
                            { value: "Bank Reconciliation Statement", label: _("Bank Reconciliation Statement") },
                            { value: "Bank Clearance Summary", label: _("Bank Clearance Summary") },
                            { value: "Incorrectly Cleared Entries", label: _("Incorrectly Cleared Entries") },
                        ]}
                        value={tab}
                        onSelect={setTab}
                    />
                </TabsList>
                <TabsContent value="Match and Reconcile">
                    <MatchAndReconcile contentHeight={remainingHeightAfterTabs} />
                </TabsContent>
                {/* //// Neoffice — added: the content of the bank files tab. */}
                <TabsContent value="Bank Files">
                    <StatementImportsPanel />
                </TabsContent>
                <TabsContent value="Bank Reconciliation Statement">
                    <BankReconciliationStatement />
                </TabsContent>
                <TabsContent value="Bank Transactions">
                    <BankTransactions />
                </TabsContent>
                <TabsContent value="Bank Clearance Summary">
                    <BankClearanceSummary />
                </TabsContent>
                <TabsContent value="Incorrectly Cleared Entries">
                    <IncorrectlyClearedEntries />
                </TabsContent>
            </Tabs>

            <BankTransactionUnreconcileModal />
        </div>
    )
}

export default BankReconciliation