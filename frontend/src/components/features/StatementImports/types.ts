//// Neoffice — added file (no upstream equivalent). The shapes of mint.apis.statement_follow_up (see api.ts).

export type LineState =
    | "passed_alone"
    | "handled"
    | "left_open"
    | "to_decide"
    | "to_match"
    | "duplicate"
    | "failed"
    | "cancelled"
    | "not_imported"

export type Counts = Record<LineState, number>

export type Progress = { total: number, waiting: number, done: number }

export type StatementImport = {
    name: string,
    creation: string,
    owner: string,
    bank_account: string,
    currency: string | null,
    import_summary: string | null,
    docstatus: number,
    status: string | null,
    source: "ebics" | "manual",
    counts: Counts,
    progress: Progress,
}

export type Voucher = {
    doctype: string,
    name: string,
    amount: number | null,
    by: string | null,
    on: string | null,
}

export type ImportLine = {
    idx: number,
    date: string,
    amount: number,
    direction: "in" | "out",
    party: string | null,
    description: string | null,
    reference: string | null,
    state: LineState,
    difference_kind: string | null,
    difference_amount: number | null,
    bank_transaction: string | null,
    vouchers: Voucher[],
    decision: string | null,
    decided_by: string | null,
    decided_on: string | null,
    credit_note: string | null,
    /** The rule of the customer that prepared or made the handling of this line. */
    rule: string | null,
}

export type ImportOverview = Omit<StatementImport, "creation" | "owner" | "import_summary" | "status"> & {
    created_on: string,
    created_by: string,
    summary: string | null,
    lines: ImportLine[],
}

/** A bank line that came from an import with a gap nobody has decided yet (get_lines_to_decide). */
export type LineToDecide = {
    bank_transaction: string,
    statement_import: string,
    idx: number,
    kind: string,
    gap: number,
    party: string | null,
}

/** What a person is asked to decide for one bank line, the verdict worked out now (get_gap_decision). */
export type GapDecision = {
    bank_transaction: string,
    statement_import: string,
    invoice_type: "Sales Invoice" | "Purchase Invoice",
    invoice: string,
    party: string | null,
    /** The party of the invoice by its document name: « Record another way » opens the payment form pointed at it. */
    party_doctype: "Customer" | "Supplier",
    party_id: string | null,
    verdict: {
        kind: string,
        gap: number,
        amount: number,
        outstanding: number,
        discount: number,
        currency: string,
        reason: string,
        /** An accepted rebate above the amount the company asks to confirm: the import does not pass it, a person does. */
        needs_confirmation?: boolean,
        confirm_above?: number,
    },
    /** The validated dunnings whose fee the surplus pays (verdict kind dunning_fee, empty otherwise). */
    dunnings: { name: string, amount: number, income_account: string | null }[],
    can_pass: boolean,
    blocker: string,
    decision: string | null,
    decided_by: string | null,
    decided_on: string | null,
    discount_percent: number | null,
    discount_date: string | null,
    /** The gap may be passed on another account than the company's (a rounding, a rebate, a short payment settled). */
    account_editable: boolean,
    default_account: string | null,
    account: string | null,
    settle_in_full: boolean,
    can_settle: boolean,
    /** More came in than is owed: the person chooses between keeping the surplus for a next invoice and booking it as a difference. */
    can_decide_surplus: boolean,
    /** The rows the gap would be booked as, the VAT cut from the account included (nothing is written yet). */
    deductions: { account: string, amount: number, description: string | null }[],
    /** A short payment of a sale can be closed by a credit note of the balance (null for anything else). */
    credit_note_chosen: boolean,
    credit_note: CreditNotePreview | null,
    /** What the customer's own invoices say about a payment at this share (null when there is nothing to read). */
    history: GapHistory | null,
    /** The rule a person made for this customer (exists = false when there is none), and what it says to do here. */
    rule: GapRule | null,
    rule_proposal: "credit_note" | "gap" | null,
    /** The credit note the rule had the import prepare as a draft, waiting to be validated. */
    draft: { name: string, total: number } | null,
}

export type RuleMode = "suggest" | "draft" | "automatic"

export type GapRule = {
    exists: boolean,
    auto_after: number,
    name?: string,
    mode?: RuleMode,
    action?: "credit_note" | "gap",
    share?: number,
    account?: string | null,
    confirmed_times?: number,
    can_automatic?: boolean,
    matches?: boolean,
    disabled?: boolean,
}

export type CreditNotePreview = {
    item: string,
    item_code: string | null,
    default_account: string | null,
    account: string | null,
    tax_template: string | null,
    /** How many times the customer already had a credit note made like this one (0 = the company's account). */
    times: number,
    source: "history" | "company",
    blocker: string,
    net: number | null,
    tax: number | null,
    total: number,
}

export type GapHistory = {
    considered: number,
    same_share: number,
    closed_by_credit: number,
    share: number,
    proposal: "credit_note" | null,
}

//// The invoices a bank line settles (mint.apis.line_invoices): the open invoices of the party, the payments prepared for the line.
export type LineInvoice = {
    name: string,
    posting_date: string,
    due_date: string | null,
    outstanding: number,
    total: number,
    bill_no?: string | null,
    same_amount: boolean,
}

export type LineEntry = {
    name: string,
    party: string | null,
    amount: number,
    by: string,
    on: string,
    references: { invoice: string, amount: number }[],
}

export type LineCandidates = {
    bank_transaction: string,
    show: boolean,
    direction: "in" | "out",
    amount: number,
    currency: string,
    reason: "none" | "several" | "paid" | "open",
    reference_hint: string | null,
    paid_on: string | null,
    invoice_type: "Sales Invoice" | "Purchase Invoice",
    party_type: "Customer" | "Supplier",
    party: string | null,
    party_label: string | null,
    party_source: "chosen" | "transaction" | "import" | "iban" | null,
    invoices: LineInvoice[],
    recognised: string[],
    drafts: LineEntry[],
    submitted: LineEntry[],
}
