import frappe
from frappe import _
# //// Neoffice — added (4713d8c). preview_bank_entry_with_vat below coerces every debit and
# //// credit through flt: the SPA posts amounts as strings and a bare sum() of them silently
# //// concatenated. Upstream imports no flt here.
from frappe.utils import flt
import json
import datetime
from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import create_payment_entry_bts, create_journal_entry_bts
from erpnext.accounts.party import get_party_account
from erpnext import get_default_cost_center
# //// Neoffice — added (10998d9). vat_utils.py is a file we added: Swiss VAT is extracted
# //// from the TTC amount the SPA posts and split into a base line plus a tax line before the
# //// Journal Entry is built. Upstream books the amounts as received, VAT never enters here.
from mint.apis.vat_utils import calculate_journal_entry_with_vat

@frappe.whitelist()
def clear_clearing_date(voucher_type: str, voucher_name: str):
    """
        Clear the clearing date of a voucher
    """
    # using db_set to trigger notification
    payment_entry = frappe.get_doc(voucher_type, voucher_name)

    if payment_entry.has_permission("write"):
        payment_entry.db_set("clearance_date", None)


@frappe.whitelist()
def reconcile_vouchers(bank_transaction_name: str | int, vouchers: str, is_new_voucher: bool = False):
	 
    # updated clear date of all the vouchers based on the bank transaction
    vouchers = json.loads(vouchers)
    transaction = frappe.get_doc("Bank Transaction", bank_transaction_name)
    
    # Add the vouchers with zero allocation. Save() will perform the allocations and clearance
    # We are overriding the default behavior of the method to set the reconciliation type
    if 0.0 >= transaction.unallocated_amount:
        frappe.throw(_("Bank Transaction {0} is already fully reconciled").format(transaction.name))
    
    for voucher in vouchers:
        transaction.append(
            "payment_entries",
            {
                "payment_document": voucher["payment_doctype"],
                "payment_entry": voucher["payment_name"],
                "allocated_amount": 0.0,  # Temporary
                "reconciliation_type": "Voucher Created" if is_new_voucher else "Matched",
            },
        )
    transaction.validate_duplicate_references()
    transaction.allocate_payment_entries()
    transaction.update_allocated_amount()
    transaction.set_status()
    transaction.save()
    
    return transaction

@frappe.whitelist()
def unreconcile_transaction(transaction_name: str | int):
    """
        Unreconcile an entire bank transaction - so this does not handle individual entries

        If the individual entries in the bank transaction are matched, just remove the payment entries
        Else, cancel the individual entries
    """
    transaction = frappe.get_doc("Bank Transaction", transaction_name)

    vouchers_to_cancel = []

    for entry in transaction.payment_entries:
        if entry.reconciliation_type == "Voucher Created":
            vouchers_to_cancel.append({
                "doctype": entry.payment_document,
                "name": entry.payment_entry,
            })
            
    transaction.remove_payment_entries()

    for voucher in vouchers_to_cancel:
        frappe.get_doc(voucher["doctype"], voucher["name"]).cancel()

@frappe.whitelist()
def undo_reconciliation_action(bank_transaction_id: str | int, voucher_type: str, voucher_id: str | int):
    """
     API to remove a single reconciliation action - for example only undoing one voucher instead of undoing the entire transaction
    """

    bank_transaction = frappe.get_doc("Bank Transaction", bank_transaction_id)

    # Find the voucher in the bank transaction and depending on the action, either remove it or cancel the voucher
    for entry in bank_transaction.payment_entries:
        if entry.payment_document == voucher_type and entry.payment_entry == voucher_id:
            if entry.reconciliation_type  == "Voucher Created":
                frappe.get_doc(voucher_type, voucher_id).cancel()
            else:
                bank_transaction.remove_payment_entry(entry)
                bank_transaction.save()

    return {
        "success": True,
    }


@frappe.whitelist(methods=["POST"])
def create_bulk_internal_transfer(bank_transaction_names: list[str|int], 
                                  bank_account: str):
    """
        Create an internal transfer for multiple bank transactions
    """
    output = []

    for bank_transaction_name in bank_transaction_names:

        bank_transaction = frappe.db.get_value("Bank Transaction", bank_transaction_name, ["name", "withdrawal", "bank_account", "date", "reference_number", "description"], as_dict=True)

        transaction_account = frappe.get_cached_value("Bank Account", bank_transaction.bank_account, "account")

        is_withdrawal = bank_transaction.withdrawal > 0.0

        if is_withdrawal:
            paid_from = transaction_account
            paid_to = bank_account
        else:
            paid_from = bank_account
            paid_to = transaction_account
        
        reference_no = (bank_transaction.reference_number or bank_transaction.description or '')[:140]
        
        final_transaction = create_internal_transfer(bank_transaction_name=bank_transaction.name,
                                 posting_date=bank_transaction.date,
                                 reference_date=bank_transaction.date,
                                 reference_no=reference_no,
                                 paid_from=paid_from,
                                 paid_to=paid_to,)
        
        output.append(final_transaction)
    
    return output

@frappe.whitelist()
def create_internal_transfer(bank_transaction_name: str|int, 
                             posting_date: str | datetime.date, 
                             reference_date: str | datetime.date, 
                             reference_no: str, 
                             paid_from: str, 
                             paid_to: str,
                             custom_remarks: bool = False,
                             remarks: str = None,
                             mirror_transaction_name: str | int = None,
                             dimensions: dict = None):
    """
    Create an internal transfer payment entry
    """

    bank_transaction = frappe.get_doc("Bank Transaction", bank_transaction_name)

    bank_account = frappe.get_cached_value("Bank Account", bank_transaction.bank_account, "account")
    company = frappe.get_cached_value("Account", bank_account, "company")

    is_withdrawal = bank_transaction.withdrawal > 0.0

    pe = frappe.new_doc("Payment Entry")

    pe.company = company
    pe.payment_type = "Internal Transfer"
    pe.posting_date = posting_date
    pe.reference_date = reference_date
    pe.reference_no = reference_no
    pe.custom_remarks = custom_remarks
    pe.paid_amount = bank_transaction.unallocated_amount
    pe.received_amount = bank_transaction.unallocated_amount

    # TODO: Support multi-currency transactions
    pe.target_exchange_rate = 1.0

    if custom_remarks:
        pe.remarks = remarks
    
    if dimensions:
        pe.update(dimensions)

    if is_withdrawal:
         pe.paid_to = paid_to
         pe.paid_from = bank_account
    else:
         pe.paid_from = paid_from
         pe.paid_to = bank_account
    
    pe.insert()
    pe.submit()

    vouchers = json.dumps(
		[
			{
				"payment_doctype": "Payment Entry",
				"payment_name": pe.name,
				"amount": bank_transaction.unallocated_amount,
			}
		]
	)

    transaction_id = reconcile_vouchers(bank_transaction_name, vouchers, is_new_voucher=True)

    if mirror_transaction_name:
        # Reconcile the mirror transaction
        reconcile_vouchers(mirror_transaction_name, vouchers, is_new_voucher=False)

    return {
        "transaction": transaction_id,
        "payment_entry": pe,
    }

@frappe.whitelist(methods=['POST'])
def create_bulk_bank_entry_and_reconcile(bank_transactions: list[str|int], 
                                         account: str):
    """
     Create bank entries for all transactions and reconcile them
    """

    output = []

    for bank_transaction in bank_transactions:
        transactions_details = frappe.db.get_value("Bank Transaction", bank_transaction, ["name", "deposit", "withdrawal", "bank_account", "currency", "unallocated_amount", "date", "reference_number", "description"], as_dict=True)

        is_credit_card = frappe.get_cached_value("Bank Account", transactions_details.bank_account, "is_credit_card")

        # Check Number will be limited to 140 characters
        cheque_no = (transactions_details.reference_number or transactions_details.description or '')[:140]

        is_withdrawal = transactions_details.withdrawal > 0.0

        entries = []

        gl_account = frappe.get_cached_value("Bank Account", transactions_details.bank_account, "account")

        if is_withdrawal:
            entries.append({
                "account": gl_account,
                "bank_account": transactions_details.bank_account,
                "credit_in_account_currency": transactions_details.unallocated_amount,
                "credit": transactions_details.unallocated_amount,
                "debit_in_account_currency": 0,
                "debit": 0,
            })

            entries.append({
                "account": account,
                "credit": 0,
                "debit": transactions_details.unallocated_amount,
            })
        else:
            entries.append({
                "account": gl_account,
                "bank_account": transactions_details.bank_account,
                "debit_in_account_currency": transactions_details.unallocated_amount,
                "debit": transactions_details.unallocated_amount,
                "credit_in_account_currency": 0,
                # //// Neoffice — backport of upstream v1.5.2 (cherry-pick, 2bdac9c), drop at the merge:
                # //// upstream repeated the "debit" key in this dict literal, so the second one overwrote the
                # //// first and the bank line of a bulk split was written with debit 0.
                "credit": 0,
            })

            entries.append({
                "account": account,
                "debit": 0,
                "credit": transactions_details.unallocated_amount,
            })

        final_transaction = create_bank_entry_and_reconcile(bank_transaction_name=bank_transaction,
                                        cheque_date=transactions_details.date,
                                        posting_date=transactions_details.date,
                                        cheque_no=cheque_no,
                                        user_remark=transactions_details.description,
                                        entries=entries,
                                        voucher_type=("Credit Card Entry" if is_credit_card else "Bank Entry"))
        
        output.append(final_transaction)
    
    return output



@frappe.whitelist(methods=['POST'])
# //// Neoffice — whitespace only: upstream's line ends with a trailing space, an editor
# //// stripped it. Take upstream's line at the merge.
def create_bank_entry_and_reconcile(bank_transaction_name: str | int,
                                    cheque_date: str | datetime.date,
                                    posting_date: str | datetime.date,
                                    cheque_no: str,
                                    entries: list,
                                    user_remark: str = None,
                                    voucher_type: str = "Bank Entry",
                                    # //// Neoffice — the two parameters below are ours (10998d9). is_vat_excluded says whether the
                                    # //// SPA sent HT or TTC amounts; disable_vat_calculation is the escape hatch for companies on
                                    # //// the Swiss flat-rate method, where no VAT is extracted. Upstream's signature ends at
                                    # //// dimensions, so this whole parameter block conflicts at the merge: keep both sides.
                                    dimensions: dict = None,
                                    is_vat_excluded: bool = False,
                                    disable_vat_calculation: bool = False):
    # //// Neoffice — the Args: block inside the docstring below is ours, added with the two VAT
    # //// parameters (10998d9). The marker sits outside the docstring on purpose: a comment put
    # //// inside it would become part of the documented text.
    """
        Create a bank entry and reconcile it with the bank transaction

        Args:
            bank_transaction_name: Name of the bank transaction
            cheque_date: Reference date
            posting_date: Posting date
            cheque_no: Reference number
            entries: List of entry dictionaries
            user_remark: Remarks
            voucher_type: Voucher type (Bank Entry or Credit Card Entry)
            dimensions: Additional dimensions
            is_vat_excluded: If True, amounts are HT. If False, amounts are TTC (default)
            disable_vat_calculation: If True, disable automatic VAT calculation
    """
    # Create a new journal entry based on the bank transaction
    bank_transaction = frappe.db.get_values(
        "Bank Transaction",
        bank_transaction_name,
        fieldname=["name", "deposit", "withdrawal", "bank_account", "currency", "unallocated_amount"],
        as_dict=True,
    )[0]

    bank_account = frappe.get_cached_value("Bank Account", bank_transaction.bank_account, "account")
    company = frappe.get_cached_value("Account", bank_account, "company")

    default_cost_center = get_default_cost_center(company)

    # //// Neoffice — added (52f898c). is_withdrawal drives the VAT direction (input tax on a
    # //// withdrawal, output tax on a deposit) for calculate_journal_entry_with_vat below.
    is_withdrawal = bank_transaction.withdrawal > 0.0

    bank_entry = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": voucher_type,
        "company": company,
        "cheque_date": cheque_date,
        "posting_date": posting_date,
        "cheque_no": cheque_no,
        "user_remark": user_remark,
    })
    
    if not dimensions:
        dimensions = {}
    # //// Neoffice — added (10998d9). Upstream loops straight over `entries`; we first run them
    # //// through calculate_journal_entry_with_vat, which turns each TTC line into a base line
    # //// plus a VAT line, and the loop below iterates the result instead of the raw input.

    # Calculate entries with VAT if applicable
    processed_entries = calculate_journal_entry_with_vat(
        entries=entries,
        is_withdrawal=is_withdrawal,
        is_vat_excluded=is_vat_excluded,
        disable_vat_calculation=disable_vat_calculation,
        company=company
    )

    for entry in processed_entries:
        # Check if this account is a Income or Expense Account
        # If it is, and no cost center is added, select the company default cost center
        # //// Neoffice — changed (10998d9). Upstream reads cost_center from the entry only. Our SPA
        # //// sends one cost center for the whole voucher, in `dimensions`; without this fallback
        # //// every P&L line silently took the company default instead of the chosen one.
        cost_center = entry.get("cost_center") or dimensions.get("cost_center")

        if not cost_center:
            report_type = frappe.get_cached_value("Account", entry["account"], "report_type")
            if report_type == "Profit and Loss":
                # Cost center is required
                cost_center = default_cost_center

        bank_entry.append("accounts", {
            "account": entry["account"],
            # TODO: Multi currency support
            "debit_in_account_currency": entry.get("debit"),
            "credit_in_account_currency": entry.get("credit"),
            "debit": entry.get("debit"),
            "credit": entry.get("credit"),
            "party_type": entry.get("party_type") if entry.get("party") else None,
            "party": entry.get("party"),
            "user_remark": entry.get("user_remark"),
            **entry,
            "cost_center": cost_center
        })

    bank_entry.insert()
    bank_entry.submit()

    if bank_transaction.deposit > 0.0:
        paid_amount = bank_transaction.deposit
    else:
        paid_amount = bank_transaction.withdrawal

    transaction = reconcile_vouchers(bank_transaction_name, json.dumps([{
        "payment_doctype": "Journal Entry",
        "payment_name": bank_entry.name,
        "amount": paid_amount,
    }]), is_new_voucher=True)

    # Return transaction, journal entry name and bank_transaction for file attachments
    return {
        "transaction": transaction,
        # //// Neoffice — changed here, and everything from this return down to
        # //// create_bulk_payment_entry_and_reconcile is ours. Upstream returns the whole bank_entry
        # //// document; we return its name plus the bank transaction so the SPA can attach the
        # //// uploaded justificatif afterwards (bc1a48f). preview_bank_entry_with_vat (e08aff5,
        # //// 4713d8c, 52f898c) renders the VAT split before anything is saved, and
        # //// calculate_deductions_with_vat (4aa971b) does the same for Payment Entry deductions.
        # //// Neither exists upstream.
        "journal_entry": bank_entry.name,
        "bank_transaction": bank_transaction_name
    }


@frappe.whitelist(methods=['POST'])
def preview_bank_entry_with_vat(bank_transaction_name: str,
                                cheque_date: str | datetime.date,
                                posting_date: str | datetime.date,
                                cheque_no: str,
                                entries: list,
                                user_remark: str = None,
                                voucher_type: str = "Bank Entry",
                                dimensions: dict = None,
                                is_vat_excluded: bool = False,
                                disable_vat_calculation: bool = False):
    """
        Preview a bank entry with VAT calculations without saving

        Returns:
            Dictionary with journal entry structure including all lines (base + VAT)
    """
    # Get bank transaction details
    bank_transaction = frappe.db.get_values(
        "Bank Transaction",
        bank_transaction_name,
        fieldname=["name", "deposit", "withdrawal", "bank_account", "currency", "unallocated_amount"],
        as_dict=True,
    )[0]

    bank_account = frappe.get_cached_value("Bank Account", bank_transaction.bank_account, "account")
    company = frappe.get_cached_value("Account", bank_account, "company")

    default_cost_center = get_default_cost_center(company)

    is_withdrawal = bank_transaction.withdrawal > 0.0

    if not dimensions:
        dimensions = {}

    # Calculate entries with VAT if applicable (same logic as create_bank_entry_and_reconcile)
    processed_entries = calculate_journal_entry_with_vat(
        entries=entries,
        is_withdrawal=is_withdrawal,
        is_vat_excluded=is_vat_excluded,
        disable_vat_calculation=disable_vat_calculation,
        company=company
    )

    # Build the journal entry structure (same logic as create_bank_entry_and_reconcile)
    journal_entry_lines = []

    for entry in processed_entries:
        account = entry.get("account")
        # Skip entries without account
        if not account:
            continue

        cost_center = entry.get("cost_center") or dimensions.get("cost_center")

        if not cost_center:
            report_type = frappe.get_cached_value("Account", account, "report_type")
            if report_type == "Profit and Loss":
                cost_center = default_cost_center

        # Check if this is the bank account line
        is_bank_line = entry.get("bank_account") is not None

        journal_entry_lines.append({
            "account": account,
            "bank_account": entry.get("bank_account"),
            "debit": flt(entry.get("debit", 0)),
            "credit": flt(entry.get("credit", 0)),
            "cost_center": cost_center,
            "party_type": entry.get("party_type") if entry.get("party") else None,
            "party": entry.get("party"),
            "user_remark": entry.get("user_remark"),
            "_is_bank_account": is_bank_line,
            "_is_vat_line": entry.get("_is_vat_line", False),
            "_is_base_for_vat": entry.get("_is_base_for_vat", False),
            "_source_account": entry.get("_source_account")
        })

    # Calculate totals
    total_debit = sum(line["debit"] for line in journal_entry_lines)
    total_credit = sum(line["credit"] for line in journal_entry_lines)

    return {
        "voucher_type": voucher_type,
        "company": company,
        "posting_date": posting_date,
        "cheque_date": cheque_date,
        "cheque_no": cheque_no,
        "user_remark": user_remark,
        "accounts": journal_entry_lines,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": abs(total_debit - total_credit) < 0.01,
        "currency": bank_transaction.currency,
        "is_vat_excluded": is_vat_excluded,
        "disable_vat_calculation": disable_vat_calculation
    }


@frappe.whitelist(methods=['POST'])
def calculate_deductions_with_vat(
    deductions: list,
    company: str,
    is_vat_excluded: bool = False,
    disable_vat_calculation: bool = False
) -> dict:
    # //// Neoffice — RULE #00: French docstring made English (13577b4 "chore: the residues of the marking pass, in one lot").
    """
    Compute the deductions, extracting the VAT automatically.

    Pour chaque déduction:
    - Si compte a taxable_account: split en HT + ligne TVA
    - Sinon: retourne tel quel

    Réutilise: get_account_tax_info(), excluding_vat_price() de vat_utils.py

    Args:
        deductions: List of deduction dictionaries with 'account', 'amount', 'cost_center', 'description'
        company: Company name
        is_vat_excluded: If True, amounts are HT. If False, amounts are TTC (default)
        disable_vat_calculation: If True, skip VAT calculation

    Returns:
        Dictionary with:
        - deductions: Processed deductions list (including VAT lines)
        - total_deductions: Total amount of all deductions
        - has_vat: Boolean indicating if VAT lines were added
    """
    from mint.apis.vat_utils import (
        get_company_vat_method,
        get_account_tax_info,
        excluding_vat_price,
        calculate_vat_amount
    )

    # Vérifier si forfait (pas de TVA)
    if company:
        vat_method = get_company_vat_method(company)
        if vat_method and "Flat" in vat_method:
            disable_vat_calculation = True

    result_deductions = []
    has_vat = False

    for deduction in deductions:
        account = deduction.get("account")
        amount = flt(deduction.get("amount", 0))

        if not account or amount == 0 or disable_vat_calculation:
            result_deductions.append(deduction)
            continue

        # Récupérer info TVA du compte
        tax_info = get_account_tax_info(account)

        if not tax_info:
            result_deductions.append(deduction)
            continue

        has_vat = True

        # Extraction TVA
        if is_vat_excluded:
            # Mode HT: montant = base, calculer TVA dessus
            base_amount = amount
            vat_amount = calculate_vat_amount(base_amount, tax_info["tax_rate"], True)
        else:
            # Mode TTC: montant inclut TVA, extraire base
            base_amount = excluding_vat_price(amount, tax_info["tax_rate"])
            vat_amount = amount - base_amount

        # Ajouter déduction base (montant HT)
        base_deduction = deduction.copy()
        base_deduction["amount"] = base_amount
        base_deduction["_is_base_for_vat"] = True
        result_deductions.append(base_deduction)

        # Ajouter ligne TVA
        vat_deduction = {
            "account": tax_info["tax_account"],
            "amount": vat_amount,
            "cost_center": deduction.get("cost_center"),
            "description": f"TVA - {deduction.get('description', account)}",
            "_is_vat_line": True,
            "_source_account": account
        }
        result_deductions.append(vat_deduction)

    total_deductions = sum(flt(d.get("amount", 0)) for d in result_deductions)

    return {
        "deductions": result_deductions,
        "total_deductions": total_deductions,
        "has_vat": has_vat
    }


@frappe.whitelist(methods=['POST'])
def create_bulk_payment_entry_and_reconcile(bank_transaction_names: list[str | int], 
                                            party_type: str, 
                                            party: str | int, 
                                            account: str,
                                            mode_of_payment: str | None = None):
    """
        Create a payment entry and reconcile it with the bank transaction
    """

    output = []

    for bank_transaction_name in bank_transaction_names:
        bank_transaction = frappe.db.get_value("Bank Transaction", bank_transaction_name, ["name", "deposit", "withdrawal", "bank_account", "currency", "unallocated_amount", "date", "reference_number", "description"], as_dict=True)

        transaction_account = frappe.get_cached_value("Bank Account", bank_transaction.bank_account, "account")

        is_withdrawal = bank_transaction.withdrawal > 0.0

        if is_withdrawal:
            paid_from = transaction_account
            paid_to = account
        else:
            paid_from = account
            paid_to = transaction_account
        
        payment_entry_doc = frappe.get_doc({
            "doctype": "Payment Entry",
            "payment_type": "Pay" if is_withdrawal else "Receive",
            "bank_account": bank_transaction.bank_account,
            "company": bank_transaction.company,
            "mode_of_payment": mode_of_payment,
            "party_type": party_type,
            "party": party,
            "paid_from": paid_from,
            "paid_to": paid_to,
            "paid_amount": bank_transaction.unallocated_amount,
            "base_paid_amount": bank_transaction.unallocated_amount,
            "received_amount": bank_transaction.unallocated_amount,
            "base_received_amount": bank_transaction.unallocated_amount,
            "target_exchange_rate": 1,
            "source_exchange_rate": 1,
            "reference_date": bank_transaction.date,
            "posting_date": bank_transaction.date,
            "reference_no": (bank_transaction.reference_number or bank_transaction.description or '')[:140],
        })

        payment_entry_doc.insert()
        payment_entry_doc.submit()

        final_transaction = reconcile_vouchers(bank_transaction_name, json.dumps([{
            "payment_doctype": "Payment Entry",
            "payment_name": payment_entry_doc.name,
            "amount": payment_entry_doc.paid_amount,
        }]), is_new_voucher=True)

        output.append({
            "transaction": final_transaction,
            "payment_entry": payment_entry_doc,
        })

    return output

    
@frappe.whitelist(methods=['POST'])
def create_payment_entry_and_reconcile(bank_transaction_name: str | int, 
                                       payment_entry_doc: dict):
    """
        Create a payment entry and reconcile it with the bank transaction
    """
    payment_entry = frappe.get_doc({
        **payment_entry_doc,
        "doctype": "Payment Entry",
    })
    payment_entry.insert()
    payment_entry.submit()
    transaction = reconcile_vouchers(bank_transaction_name, json.dumps([{
        "payment_doctype": "Payment Entry",
        "payment_name": payment_entry.name,
        "amount": payment_entry.paid_amount,
    }]), is_new_voucher=True)

    return {
        "transaction": transaction,
        "payment_entry": payment_entry,
    }


@frappe.whitelist(methods=['GET'])
def get_account_defaults(account: str):
    """
        Get the default cost center and write off account for an account
    """
    # //// Neoffice — guarded (10998d9). Upstream unpacks frappe.db.get_value(...) straight into
    # //// two names. Our SPA calls this endpoint on every keystroke of the account field, so it
    # //// arrives with an empty or not-yet-existing account and the unpack raised TypeError on
    # //// None. Same return value in the normal case.
    if not account:
        return ""

    result = frappe.db.get_value("Account", account, ["company", "report_type"], as_dict=False)

    if not result:
        return ""

    company, report_type = result

    return get_default_cost_center(company) if report_type == "Profit and Loss" else  ""


@frappe.whitelist(methods=["GET"])
def get_party_details(company: str, party_type: str, party: str | int):

    if not frappe.db.exists(party_type, party):
        frappe.throw(_("{0} {1} does not exist").format(party_type, party))

    party_account = get_party_account(party_type, party, company)
    _party_name = "title" if party_type == "Shareholder" else party_type.lower() + "_name"
    party_name = frappe.db.get_value(party_type, party, _party_name)

    return {
        "party_account": party_account,
        "party_name": party_name,
    }

@frappe.whitelist(methods=["GET"])
def search_for_transfer_transaction(transaction_id: str | int):
    """
    When users try to create a transfer, we could help them by searching for the mirror transaction.

    So for a withdrawal of 1000, we could search for a deposit of 1000 on the same date.

    If the mirror transaction is found, we return the bank account and account details.
    """
    company, withdrawal, deposit, date, bank_account = frappe.db.get_value("Bank Transaction", transaction_id, ["company", "withdrawal", "deposit", "date", "bank_account"])

    
    days = frappe.db.get_single_value("Mint Settings", "transfer_match_days")

    if not days:
        days = 4

    min_date = frappe.utils.add_days(date, -days)
    max_date = frappe.utils.add_days(date, days)
    mirror_tx = frappe.db.get_list("Bank Transaction", filters={
        "company": company,
        "date": ["between", [min_date, max_date]],
        "withdrawal": deposit,
        "bank_account": ["!=", bank_account],
        "deposit": withdrawal,
        "docstatus": 1,
        "status": "Unreconciled",
    }, fields=["name", "bank_account", "reference_number", "date", "description", "withdrawal", "deposit", "currency"])

    if len(mirror_tx) == 1:
        return {
            "name": mirror_tx[0].name,
            "reference_number": mirror_tx[0].reference_number,
            "description": mirror_tx[0].description,
            "currency": mirror_tx[0].currency,
            "withdrawal": mirror_tx[0].withdrawal,
            "deposit": mirror_tx[0].deposit,
            "date": mirror_tx[0].date,
            "bank_account": mirror_tx[0].bank_account,
            "account": frappe.get_cached_value("Bank Account", mirror_tx[0].bank_account, "account"),
        }

    return None

# //// Neoffice — added: everything from here to the end of the file is ours (88a7d8b, 9bfe719,
# //// a401621, 23db5d9). ERPNext's get_linked_payments only returns SUBMITTED vouchers, so a
# //// draft Journal Entry could never be matched against a bank line. get_linked_payments
# //// wraps it and merges get_draft_journal_entries; submit_draft_je_and_reconcile then
# //// submits the draft and reconciles in one call. Upstream calls ERPNext's endpoint direct.

@frappe.whitelist(methods=['GET'])
def get_linked_payments(
    bank_transaction_name: str,
    document_types=None,
    from_date: str = None,
    to_date: str = None,
    filter_by_reference_date: int = 0,
    from_reference_date: str = None,
    to_reference_date: str = None,
    include_draft_je: int = 1,
):
    """
    Get linked payments for a bank transaction, with optional support for draft Journal Entries.

    This extends ERPNext's get_linked_payments to include draft Journal Entries,
    allowing users to reconcile with JEs before submitting them.

    Args:
        bank_transaction_name: Name of the bank transaction
        document_types: List of document types to search for
        from_date: Start date for search
        to_date: End date for search
        filter_by_reference_date: Whether to filter by reference date
        from_reference_date: Start reference date
        to_reference_date: End reference date
        include_draft_je: If True, include draft Journal Entries (default: True)
    """
    from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
        get_linked_payments as erpnext_get_linked_payments,
    )

    # Parse document_types if it's a string (from frontend)
    if isinstance(document_types, str):
        document_types = json.loads(document_types)

    # Get submitted vouchers from ERPNext
    submitted_vouchers = erpnext_get_linked_payments(
        bank_transaction_name=bank_transaction_name,
        document_types=document_types,
        from_date=from_date,
        to_date=to_date,
        filter_by_reference_date=filter_by_reference_date,
        from_reference_date=from_reference_date,
        to_reference_date=to_reference_date,
    )

    # If include_draft_je is True and journal_entry is in document_types, get draft JEs
    if int(include_draft_je) and document_types and 'journal_entry' in document_types:
        draft_jes = get_draft_journal_entries(
            bank_transaction_name=bank_transaction_name,
            from_date=from_date,
            to_date=to_date,
            filter_by_reference_date=filter_by_reference_date,
            from_reference_date=from_reference_date,
            to_reference_date=to_reference_date,
        )
        # Combine and sort by posting_date, then by rank (for same-date entries)
        all_vouchers = submitted_vouchers + draft_jes
        return sorted(all_vouchers, key=lambda x: (x.get("posting_date", ""), -x.get("rank", 0)))

    return submitted_vouchers


def get_draft_journal_entries(
    bank_transaction_name: str,
    from_date: str = None,
    to_date: str = None,
    filter_by_reference_date: int = 0,
    from_reference_date: str = None,
    to_reference_date: str = None,
):
    """
    Get draft Journal Entries that could match the bank transaction.

    Returns a list of draft JEs with the same structure as get_linked_payments.
    """
    from frappe.query_builder.functions import Sum
    from pypika.terms import ValueWrapper
    from frappe.utils import cint

    transaction = frappe.get_doc("Bank Transaction", bank_transaction_name)
    bank_account_details = frappe.db.get_values(
        "Bank Account", transaction.bank_account, ["account", "company"], as_dict=True
    )[0]
    gl_account = bank_account_details.account

    # Determine credit or debit based on transaction type
    cr_or_dr = "credit" if transaction.withdrawal > 0.0 else "debit"

    je = frappe.qb.DocType("Journal Entry")
    jea = frappe.qb.DocType("Journal Entry Account")

    amount_field = f"{cr_or_dr}_in_account_currency"

    # Build date filter
    if cint(filter_by_reference_date):
        filter_by_date = je.cheque_date.between(from_reference_date, to_reference_date)
    else:
        filter_by_date = je.posting_date.between(from_date, to_date)

    # Query for draft Journal Entries (docstatus = 0)
    subquery = (
        frappe.qb.from_(jea)
        .join(je)
        .on(jea.parent == je.name)
        .select(
            Sum(getattr(jea, amount_field)).as_("paid_amount"),
            ValueWrapper("Journal Entry").as_("doctype"),
            je.name,
            je.cheque_no.as_("reference_no"),
            je.cheque_date.as_("reference_date"),
            je.pay_to_recd_from.as_("party"),
            jea.party_type,
            je.posting_date,
            jea.account_currency.as_("currency"),
            je.user_remark,  # Include user_remark for display
            ValueWrapper(1).as_("is_draft"),  # Flag to identify drafts
        )
        .where(je.docstatus == 0)  # Draft status
        .where(je.voucher_type != "Opening Entry")
        .where(jea.account == gl_account)
        .where(filter_by_date)
        .groupby(je.name)
        .orderby(je.cheque_date if cint(filter_by_reference_date) else je.posting_date)
    )

    # Calculate ranking
    ref_rank = frappe.qb.terms.Case().when(subquery.reference_no == transaction.reference_number, 1).else_(0)
    amount_equality = subquery.paid_amount == transaction.unallocated_amount
    amount_rank = frappe.qb.terms.Case().when(amount_equality, 1).else_(0)

    query = (
        frappe.qb.from_(subquery)
        .select(
            "*",
            (ref_rank + amount_rank).as_("rank"),  # Slightly lower rank than submitted (no +1)
        )
        .where(subquery.paid_amount > 0.0)
    )

    draft_jes = query.run(as_dict=True)

    # Subtract any existing allocations (same logic as ERPNext)
    return subtract_allocations_for_drafts(gl_account, draft_jes)


def subtract_allocations_for_drafts(gl_account, vouchers):
    """
    Subtract any existing Bank Transaction allocations from draft vouchers.
    """
    from erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool import (
        get_total_allocated_amount,
        get_allocated_amount,
    )

    copied = []
    voucher_docs = [(voucher.get("doctype"), voucher.get("name")) for voucher in vouchers]
    voucher_allocated_amounts = get_total_allocated_amount(voucher_docs)

    for voucher in vouchers:
        if amount := get_allocated_amount(voucher_allocated_amounts, voucher, gl_account):
            voucher["paid_amount"] -= amount

        if voucher["paid_amount"] > 0:
            copied.append(voucher)

    return copied


@frappe.whitelist(methods=['POST'])
def submit_draft_je_and_reconcile(
    bank_transaction_name: str,
    journal_entry_name: str,
    posting_date: str | datetime.date = None,
    cheque_date: str | datetime.date = None,
    user_remark: str = None,
):
    """
    Submit a draft Journal Entry and reconcile it with the bank transaction.

    This allows users to:
    1. Update the posting_date and cheque_date to match the bank transaction date
    2. Add/update the user_remark
    3. Submit the Journal Entry
    4. Reconcile with the bank transaction

    Args:
        bank_transaction_name: Name of the bank transaction
        journal_entry_name: Name of the draft Journal Entry to submit
        posting_date: New posting date (optional, uses existing if not provided)
        cheque_date: New reference date (optional, uses existing if not provided)
        user_remark: New user remark (optional, uses existing if not provided)
    """
    # Get the bank transaction first (needed for reference_no fallback and reconciliation)
    bank_transaction = frappe.get_doc("Bank Transaction", bank_transaction_name)

    # Get the draft Journal Entry
    je = frappe.get_doc("Journal Entry", journal_entry_name)

    # Verify it's a draft
    if je.docstatus != 0:
        frappe.throw(_("Journal Entry {0} is not a draft").format(journal_entry_name))

    # Update fields if provided
    if posting_date:
        je.posting_date = posting_date
        # Also update posting_date in accounts for proper GL entries
        for account in je.accounts:
            account.posting_date = posting_date

    if cheque_date:
        je.cheque_date = cheque_date
        # If cheque_date is set but cheque_no is empty, use bank transaction reference
        if not je.cheque_no:
            je.cheque_no = (bank_transaction.reference_number or bank_transaction.description or "")[:140]

    if user_remark is not None:
        je.user_remark = user_remark

    # Save and submit the Journal Entry
    je.save()
    je.submit()

    # Get the amount for reconciliation
    if bank_transaction.deposit > 0.0:
        paid_amount = bank_transaction.deposit
    else:
        paid_amount = bank_transaction.withdrawal

    # Reconcile with the bank transaction
    return reconcile_vouchers(bank_transaction_name, json.dumps([{
        "payment_doctype": "Journal Entry",
        "payment_name": je.name,
        "amount": paid_amount,
    }]), is_new_voucher=False)

