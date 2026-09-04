import frappe
#//// Neoffice — NOTHING in this file is our intent: it is upstream code carried by hand.
#//// This import and the str | datetime.date hint at the bottom come from the v1.5.0
#//// port (89e7929); the get_list rewrite below is a byte-identical backport of upstream
#//// 5ba8c6b. At the next merge take upstream's bank_account.py and drop every marker.
import datetime

@frappe.whitelist(methods=["GET"])
@frappe.read_only()
def get_list(company: str, show_disabled: bool = False):

    #//// Neoffice — backport of upstream 5ba8c6b (cherry-pick), drop at the merge: frappe.get_list
    #//// applies User Permissions, the pypika join it replaces did not.
    filters = {
        "is_company_account": 1,
        "company": company
    }

    #//// Neoffice — backport of upstream 5ba8c6b (cherry-pick), drop at the merge.
    if not show_disabled:
        filters["disabled"] = 0

    #//// Neoffice — backport of upstream 5ba8c6b (cherry-pick), drop at the merge.
    bank_accounts = frappe.get_list("Bank Account", 
                                    filters=filters, 
                                    order_by="is_default desc",
                                    fields=["name", "account", "company", "account_name", "is_default", "bank", "account_type", "account_subtype", "bank_account_no", "last_integration_date", "is_credit_card"])

    #//// Neoffice — backport of upstream 5ba8c6b (cherry-pick), drop at the merge: account_currency
    #//// was a column of the dropped join, it is now read per row from the Account cache.
    for bank_account in bank_accounts:
        bank_account.account_currency = frappe.get_cached_value("Account", bank_account.account, "account_currency")

    #//// Neoffice — backport of upstream 5ba8c6b (cherry-pick), drop at the merge: the stray
    #//// blank line and the renamed return come from upstream's commit verbatim.
    
    return bank_accounts

@frappe.whitelist(methods=["GET"])
def get_closing_balance_as_per_statement(bank_account: str, date: str):
    """
        Get the closing balance as per statement for a bank account and date
    """
    latest_balance = frappe.get_list("Mint Bank Statement Balance", filters={
        "bank_account": bank_account,
        "date": ["<=", date]
    }, fields=["balance", "date"], order_by="date desc", limit=1)

    if latest_balance:
        return {
            "balance": latest_balance[0].balance,
            "date": latest_balance[0].date
        }
    return {
        "balance": 0,
        "date": None
    }

@frappe.whitelist()
#//// Neoffice — NOT ours: upstream v1.5.0 signature, hand-ported (89e7929). Take upstream's.
def set_closing_balance_as_per_statement(bank_account: str, date: str | datetime.date, balance: float):
    """
    Set the closing balance as per statement for a bank account and date
    """

    existing = frappe.db.exists("Mint Bank Statement Balance", {
        "bank_account": bank_account,
        "date": date
    })

    if existing:
        doc = frappe.get_doc("Mint Bank Statement Balance", existing)
        doc.balance = balance
        doc.save()
    else:
        doc = frappe.new_doc("Mint Bank Statement Balance")
        doc.bank_account = bank_account
        doc.date = date
        doc.balance = balance
        doc.save()