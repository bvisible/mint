//// Neoffice — added file (no upstream equivalent). « Reconciliation » (between entries), next to the bank
//// reconciliation of the statement: pick customers or suppliers, then one party, then tick what settles what.
import { useFrappeGetCall } from "frappe-react-sdk"
import { useEffect, useState } from "react"
import CompanySelector from "@/components/features/BankReconciliation/CompanySelector"
import PartyDetail from "@/components/features/PartyReconciliation/PartyDetail"
import PartyList from "@/components/features/PartyReconciliation/PartyList"
import type { PartyType } from "@/components/features/PartyReconciliation/types"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TooltipProvider } from "@/components/ui/tooltip"
import { H1 } from "@/components/ui/typography"
import { useCurrentCompany } from "@/hooks/useCurrentCompany"
import { EMBEDDED } from "@/lib/embedded"
import _ from "@/lib/translate"

const PartyReconciliation = () => {
    const company = useCurrentCompany() as string
    const [partyType, setPartyType] = useState<PartyType>("Customer")
    const [party, setParty] = useState<string | null>(null)
    // Raised after a reconciliation: the list and the party are asked again.
    const [version, setVersion] = useState(0)

    const { data: currencyData } = useFrappeGetCall<{ message: { default_currency: string } }>(
        "frappe.client.get_value",
        { doctype: "Company", filters: company, fieldname: "default_currency" },
        company ? ["party-reconciliation", "currency", company] : null,
        { revalidateOnFocus: false },
    )
    const currency = currencyData?.message?.default_currency ?? ""

    // Another kind of party or another company: the party chosen belongs to the one before.
    useEffect(() => setParty(null), [partyType, company])

    return (
        <TooltipProvider>
            <div className="@container p-4 flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    {!EMBEDDED && <H1 className="text-sm font-medium">{_("Reconciliation")}</H1>}
                    <Tabs value={partyType} onValueChange={(value) => setPartyType(value as PartyType)}>
                        <TabsList>
                            <TabsTrigger value="Customer">{_("Customers")}</TabsTrigger>
                            <TabsTrigger value="Supplier">{_("Suppliers")}</TabsTrigger>
                        </TabsList>
                    </Tabs>
                    <CompanySelector />
                </div>

                <div className="grid gap-4 @3xl:grid-cols-[15rem_minmax(0,1fr)]">
                    {/* The list keeps its place while the party scrolls, and has its scrollbar when it is long. */}
                    <div className="min-w-0 @3xl:sticky @3xl:top-2 @3xl:self-start @3xl:max-h-[calc(100vh-1rem)] @3xl:overflow-y-auto">
                        <PartyList company={company} partyType={partyType} selected={party} onSelect={setParty} version={version} currency={currency} />
                    </div>
                    {party ? (
                        <PartyDetail company={company} partyType={partyType} party={party} version={version} onReconciled={() => setVersion((current) => current + 1)} />
                    ) : (
                        <div className="flex items-center justify-center rounded-lg border border-dashed p-12 text-muted-foreground text-center">
                            {partyType === "Customer" ? _("Choose a customer to reconcile its payments and credit notes with its invoices.") : _("Choose a supplier to reconcile its payments and debit notes with its invoices.")}
                        </div>
                    )}
                </div>
            </div>
        </TooltipProvider>
    )
}

export default PartyReconciliation
