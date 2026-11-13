import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


# //// Neoffice — ERPNext v16 ships three of these four fields as standard fields (the bank module moved
# //// from Mint into ERPNext), so a fresh install there would add each of them twice. Upstream Mint
# //// handles it by returning early when reconciliation_type exists (561c65c, 2026-07-10), which would
# //// also skip matched_rule: that one v16 names matched_transaction_rule and links to its own rule
# //// doctype, so we still need ours. We skip per field instead. No effect on v15, where none of the
# //// four is a standard field. An in-place upgrade v15 -> v16 is NOT covered here: the Custom Field
# //// rows already exist, a patch has to remove them when the fleet moves to v16.
def _without_standard_fields(custom_fields):
    kept = {}
    for doctype, fields in custom_fields.items():
        left = [
            field for field in fields
            if not frappe.db.exists("DocField", {"parent": doctype, "fieldname": field["fieldname"]})
        ]
        if left:
            kept[doctype] = left
    return kept


def after_install():

    # //// Neoffice — upstream's early return when reconciliation_type exists (561c65c) is replaced by the
    # //// per-field check of _without_standard_fields: the dict is built first so each field can be checked.
    custom_fields = {
        "Bank Transaction Payments": [
			{
				"fieldname": "reconciliation_type",
				"fieldtype": "Select",
				"label": "Reconciliation Type",
				"options": "Matched\nVoucher Created",
				"insert_after": "clearance_date",
				"read_only": 1,
				"default": "Matched",
			}
		],
        "Bank Account": [
            {
                "fieldname": "is_credit_card",
                "fieldtype": "Check",
                "label": "Is Credit Card",
                "insert_after": "bank_account_no",
                "default": 0,
			}
		],
        "Bank Transaction": [
            {
                "fieldname": "is_rule_evaluated",
                "fieldtype": "Check",
                "label": "Is Rule Evaluated",
                "default": 0,
                "allow_on_submit": 1,
                "insert_after": "party",
			},
            {
                "fieldname": "matched_rule",
                "insert_after": "is_rule_evaluated",
                "fieldtype": "Link",
                "label": "Matched Rule",
                "options": "Mint Bank Transaction Rule",
                "read_only": 1,
                "allow_on_submit": 1,
			}
		]
        }

    # //// Neoffice — only the fields ERPNext does not already ship (see _without_standard_fields).
    create_custom_fields(_without_standard_fields(custom_fields))
