import frappe

@frappe.whitelist()
def get_bank_transactions(bank_account, from_date=None, to_date=None, all_transactions=False):
    # returns bank transactions for a bank account
    filters = []
    filters.append(["bank_account", "=", bank_account])
    filters.append(["docstatus", "=", 1])
    if not all_transactions:
        # Filter for unreconciled transactions using both unallocated_amount and status
        # This ensures transactions are properly filtered even when accounting dimensions
        # differ between journal entry lines (which can cause get_allocated_amount()
        # to incorrectly calculate allocations in ERPNext's subtract_allocations function)
        filters.append(["unallocated_amount", ">", 0.0])
        filters.append(["status", "=", "Unreconciled"])
    if to_date:
        filters.append(["date", "<=", to_date])
    if from_date:
        filters.append(["date", ">=", from_date])

    transactions = frappe.get_list(
        "Bank Transaction",
        fields=[
            "date",
            "deposit",
            "withdrawal",
            "currency",
            "description",
            "transaction_type",
            "name",
            "bank_account",
            "company",
            "allocated_amount",
            "unallocated_amount",
            "reference_number",
            "party_type",
            "party",
            "status",
            "matched_rule"
        ],
        filters=filters,
        order_by="date",
    )
    return transactions