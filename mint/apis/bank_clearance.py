import frappe
# //// Neoffice — for the translated messages of the voucher checks below.
from frappe import _

# //// Neoffice — POST only, as ERPNext v16 and v15-hotfix now do for every method that writes (a GET
# //// carries no CSRF token). The SPA already calls it with useFrappePostCall.
@frappe.whitelist(methods=["POST"])
def update_clearance_date(payment_document: str, payment_entry: str, account: str, clearance_date: str | None):
    """
    Update the clearance date of a voucher
    """

    if not clearance_date:
        clearance_date = None

    # Check for permissions
    frappe.has_permission("Bank Clearance", ptype="write", throw=True)

    # //// Neoffice — the right on the doctype Bank Clearance said nothing about the voucher: the writes below
    # //// are raw (db.set_value), which ignore User Permissions, and the doctype came from the request. An
    # //// accountant limited to one company could set the clearance date of another company's voucher, and
    # //// any doctype with a clearance_date column could be named. ERPNext did the same before it hardened
    # //// this tool (voucher.check_permission, "only submitted vouchers can be cleared").
    if payment_document != "Sales Invoice" and not frappe.get_meta(payment_document).has_field("clearance_date"):
        frappe.throw(_("{0} is not a voucher this tool can clear").format(_(payment_document)), title=_("Invalid Voucher"))

    voucher = frappe.get_doc(payment_document, payment_entry)
    voucher.check_permission("read")
    voucher.check_permission("write")
    if voucher.docstatus != 1:
        frappe.throw(_("Only submitted vouchers can be cleared."), title=_("Invalid Voucher"))

    if payment_document == "Sales Invoice":
                frappe.db.set_value(
                    "Sales Invoice Payment",
                    {"parent": payment_entry, "account": account, "amount": [">", 0]},
                    "clearance_date",
                    clearance_date,
                )

    else:
        frappe.db.set_value(
            payment_document, payment_entry, "clearance_date", clearance_date
        )
