//// Neoffice — added file (no upstream equivalent). The one way to bring a bank statement in by hand: XML (CAMT) or PDF, deposited in
//// the form of the desk for the bank account of the page. A CSV or an Excel file is not handled yet: the importer of upstream
//// (/statement-importer) stays in the app but nothing links to it.
import { outerWindow } from "@/lib/embedded"

export const depositStatement = (bankAccount?: string) => {
    const query = bankAccount ? `?bank_account=${encodeURIComponent(bankAccount)}` : ""
    outerWindow().location.assign(`/app/mint-bank-statement-import/new${query}`)
}
