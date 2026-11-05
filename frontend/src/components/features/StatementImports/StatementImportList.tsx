//// Neoffice — added file (no upstream equivalent). The latest imports of a bank account, each with its progress.
import { useFrappeGetCall } from "frappe-react-sdk"
import { ListIcon } from "lucide-react"
import { Empty, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import ErrorBanner from "@/components/ui/error-banner"
import { Skeleton } from "@/components/ui/skeleton"
import _ from "@/lib/translate"
import { API } from "./api"
import StatementImportCard from "./StatementImportCard"
import type { StatementImport } from "./types"

const StatementImportList = ({ bankAccount, currency, version }: { bankAccount: string, currency: string, version: number }) => {
    const { data, error, isLoading } = useFrappeGetCall<{ message: StatementImport[] }>(
        `${API}.list_imports`,
        { bank_account: bankAccount, limit: 30 },
        ["statement-imports", "list", bankAccount, version],
        { revalidateOnFocus: false },
    )

    if (error) return <ErrorBanner error={error} />
    if (isLoading) return <Skeleton className="h-32 w-full" />
    const imports = data?.message ?? []
    if (imports.length === 0) {
        return (
            <Empty>
                <EmptyHeader>
                    <EmptyMedia variant="icon"><ListIcon /></EmptyMedia>
                    <EmptyTitle>{_("No bank statements imported yet")}</EmptyTitle>
                </EmptyHeader>
            </Empty>
        )
    }
    return (
        <div className="flex flex-col gap-3">
            {imports.map((item) => (
                <StatementImportCard key={item.name} item={item} currency={currency} version={version} />
            ))}
        </div>
    )
}

export default StatementImportList
