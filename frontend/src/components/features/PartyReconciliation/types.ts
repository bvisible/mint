//// Neoffice — added file (no upstream equivalent). The shapes of the server module of the party reconciliation (see api.ts).

export type PartyType = "Customer" | "Supplier"

export type PartyRow = {
    party: string,
    label: string,
    open: number,
    open_count: number,
    credit: number,
    credit_count: number,
    oldest: string | null,
    accounts: string[],
}

export type InvoiceRow = {
    invoice_type: string,
    invoice_number: string,
    invoice_date: string,
    amount: number,
    outstanding_amount: number,
    currency: string,
    due_date?: string | null,
    reference?: string | null,
    remark?: string | null,
}

/** A payment, a credit note or a journal entry line: whatever can settle an invoice. */
export type SettlementRow = {
    reference_type: string,
    reference_name: string,
    reference_row?: string | null,
    posting_date: string,
    amount: number,
    currency: string,
    is_advance?: number | string,
    reference?: string | null,
    remark?: string | null,
    mode_of_payment?: string | null,
    return_against?: string | null,
}

export type PartyDetailData = {
    party: string,
    party_type: PartyType,
    label: string,
    company: string,
    account: string,
    currency: string,
    invoices: InvoiceRow[],
    payments: SettlementRow[],
    totals: { open: number, credit: number, balance: number },
    check: { ledger: number, documents: number, difference: number },
    other_accounts: { account: string, balance: number }[],
}

export type AllocationRow = {
    reference_type: string,
    reference_name: string,
    invoice_type: string,
    invoice_number: string,
    allocated_amount: number,
    difference_amount?: number,
    currency?: string,
}

export type PreviewData = {
    allocation: AllocationRow[],
    settled: number,
    difference: number,
    invoices_left: number,
    credits_left: number,
}

export type VoucherDetailData = {
    voucher_type: string,
    name: string,
    posting_date?: string,
    status: string,
    remark: string,
    reference: string,
    owner: string,
    creation: string,
    lines: Record<string, string | number | null>[],
    attachments: number,
    route: string,
    pdf_url?: string | null,
    printable?: boolean,
}

/** What the user ticked: the row key and the amount, as typed. */
export type Selection = Record<string, string>
