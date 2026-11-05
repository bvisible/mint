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
}

export type ImportOverview = Omit<StatementImport, "creation" | "owner" | "import_summary" | "status"> & {
    created_on: string,
    created_by: string,
    summary: string | null,
    lines: ImportLine[],
}
