import frappe
import datetime

# //// Neoffice — getdate: the file's balance is compared with the typed one by day (get_closing_balance_as_per_statement).
from frappe.utils import getdate

@frappe.whitelist(methods=["GET"])
@frappe.read_only()
def get_list(company: str, show_disabled: bool = False):

    filters = {
        "is_company_account": 1,
        "company": company
    }

    if not show_disabled:
        filters["disabled"] = 0

    bank_accounts = frappe.get_list("Bank Account", 
                                    filters=filters, 
                                    order_by="is_default desc",
                                    fields=["name", "account", "company", "account_name", "is_default", "bank", "account_type", "account_subtype", "bank_account_no", "last_integration_date", "is_credit_card",
                                            # //// Neoffice — iban read (01.10) for its IID only, see below.
                                            "iban"])

    for bank_account in bank_accounts:
        bank_account.account_currency = frappe.get_cached_value("Account", bank_account.account, "account_currency")
        # //// Neoffice — added (01.10): what names the account's bank for its logo (logos.ts,
        # //// findBankLogo), whatever the Bank record is called: the BIC of the bank, and the IID of a
        # //// Swiss or Liechtenstein IBAN (its 5th to 9th character). Not the IBAN itself: the logo
        # //// needs no more.
        bank_account.bic = frappe.get_cached_value("Bank", bank_account.bank, "swift_number") if bank_account.bank else None
        iban = (bank_account.pop("iban", None) or "").replace(" ", "").upper()
        bank_account.bank_iid = iban[4:9] if iban[:2] in ("CH", "LI") and iban[4:9].isdigit() else None

    
    return bank_accounts

@frappe.whitelist(methods=["GET"])
def get_closing_balance_as_per_statement(bank_account: str, date: str):
    """
        Get the closing balance as per statement for a bank account and date
    """
    # //// Neoffice — the balance document has no company of its own, so get_list below let an accountant limited
    # //// to one company read the statement balance of another company's bank account. The right is on the account.
    frappe.has_permission("Bank Account", ptype="read", doc=bank_account, throw=True)

    latest_balance = frappe.get_list("Mint Bank Statement Balance", filters={
        "bank_account": bank_account,
        "date": ["<=", date]
    }, fields=["balance", "date"], order_by="date desc", limit=1)

    # //// Neoffice — the statement file the bank sent carries its closing balance: when it is more recent than the one
    # //// somebody typed (or nobody typed any), it is the balance as per statement, and the answer says where it
    # //// comes from. Typing was the only way before, so the figure was empty until somebody did. A tie goes to the
    # //// typed one: a person's correction wins over the file of the same day.
    from mint.apis.statement_follow_up import latest_file_balance

    typed = latest_balance[0] if latest_balance else None
    from_file = latest_file_balance(bank_account, date)
    if from_file and (not typed or getdate(from_file.date) > getdate(typed.date)):
        return {
            "balance": from_file.balance,
            "date": from_file.date,
            "source": "file",
            "statement_import": from_file.name,
        }
    # //// Neoffice — the same answers as before, each now naming where the figure comes from.
    if typed:
        return {
            "balance": typed.balance,
            "date": typed.date,
            "source": "typed"
        }
    # //// Neoffice — nothing typed, no file: the same empty answer, with its source empty too.
    return {
        "balance": 0,
        "date": None,
        "source": None
    }

# //// Neoffice — POST only, as ERPNext v16 and v15-hotfix do for every method that writes; the SPA already
# //// posts it (useFrappePostCall).
@frappe.whitelist(methods=["POST"])
def set_closing_balance_as_per_statement(bank_account: str, date: str | datetime.date, balance: float):
    """
    Set the closing balance as per statement for a bank account and date
    """
    # //// Neoffice — same as the reader above: the balance document is saved under its own doctype's right,
    # //// which says nothing about the bank account (ERPNext v16 checks the account when a balance is set).
    frappe.has_permission("Bank Account", ptype="read", doc=bank_account, throw=True)

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