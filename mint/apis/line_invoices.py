# //// Neoffice — added file (no upstream equivalent).
# ////
# //// THE INVOICES A BANK LINE SETTLES, WHEN THE IMPORT DID NOT NAME THEM (OR NAMED THEM WRONG).
# ////
# //// An import recognises the invoice of a line by its reference. Three cases leave the line to a person with no
# //// single invoice to settle: nothing was recognised, several invoices were (one amount for several invoices), or the
# //// reference is that of an invoice that was already paid (a customer who reuses an old payment slip). The person
# //// is shown the open invoices of the party (found by the line, by the import or by the IBAN of the payer), picks the
# //// ones the payment settles and the amounts split between them; the payment is then either validated and
# //// reconciled at once, or PREPARED AS A DRAFT that the person opens, corrects by hand, validates, and comes back to
# //// reconcile. Nothing here invents a party or an amount: what is not certain is a choice of the person.

import ast
import json

import frappe
from frappe import _
from frappe.utils import flt, getdate

from mint.apis import statement_follow_up as follow_up

# a payment is split between invoices to the cent
CENT = 0.005
# the open invoices of a party offered at most: older ones first, a person with more picks them in the payment window
MAX_INVOICES = 100


def _recognised(line) -> list[str]:
	"""The invoices the import recognised for this line (none, one or several)."""
	if not line or not line.invoice_matches:
		return []
	try:
		matches = ast.literal_eval(line.invoice_matches)
	except (ValueError, SyntaxError):
		return []
	return [str(m) for m in matches] if isinstance(matches, (list, tuple)) else []


def _party_of(bank_line, line, party_type: str, chosen: str | None):
	"""The party this payment is from (or to) and how it was found: chosen by the person, written on the bank line, named
	by the import (its name, or the name the bank gave), or found by the IBAN of the payer. (None, None) when nothing says."""
	if chosen:
		return chosen, "chosen"
	if bank_line.party_type == party_type and bank_line.party:
		return bank_line.party, "transaction"
	if line:
		display = "customer_name" if party_type == "Customer" else "supplier_name"
		for name in (line.party_match, line.party_name):
			if not name:
				continue
			found = frappe.db.exists(party_type, name) or frappe.db.get_value(party_type, {display: name}, "name")
			if found:
				return found, "import"
	iban = ((line and frappe.db.get_value(follow_up.LINE, line.name, "party_iban")) or bank_line.bank_party_iban or "").replace(
		" ", ""
	)
	if iban:
		rows = frappe.db.sql(
			"""
			select party from `tabBank Account`
			where replace(iban, ' ', '') = %(iban)s and party_type = %(party_type)s and ifnull(party, '') != ''
				and ifnull(disabled, 0) = 0
			limit 2
			""",
			{"iban": iban, "party_type": party_type},
		)
		# two parties with the same IBAN is not a finding
		if len(rows) == 1:
			return rows[0][0], "iban"
	return None, None


def _open_invoices(doctype: str, party: str, company: str, currency: str, amount: float) -> list[dict]:
	party_field = "customer" if doctype == "Sales Invoice" else "supplier"
	fields = ["name", "posting_date", "due_date", "outstanding_amount", "grand_total", "currency"]
	if doctype == "Purchase Invoice":
		fields.append("bill_no")
	rows = frappe.get_list(
		doctype,
		filters={"docstatus": 1, "company": company, party_field: party, "outstanding_amount": (">", 0), "currency": currency},
		fields=fields,
		order_by="due_date asc, posting_date asc, name asc",
		limit_page_length=MAX_INVOICES,
	)
	return [
		{
			"name": r.name,
			"posting_date": r.posting_date,
			"due_date": r.due_date,
			"outstanding": flt(r.outstanding_amount, 2),
			"total": flt(r.grand_total, 2),
			"bill_no": r.get("bill_no"),
			"same_amount": abs(flt(r.outstanding_amount) - amount) <= CENT,
		}
		for r in rows
	]


def _references_of(entry: str) -> list[dict]:
	return [
		{"invoice": r.reference_name, "amount": flt(r.allocated_amount, 2)}
		for r in frappe.get_all(
			"Payment Entry Reference",
			filters={"parent": entry},
			fields=["reference_name", "allocated_amount"],
			order_by="idx",
		)
	]


def _entries_of(bank_line, receiving: bool) -> tuple[list[dict], list[dict]]:
	"""The payments prepared for this bank line, told apart by the reference they carry (the reference of the line): the drafts
	that wait to be validated, and the ones validated in another tab that wait to be reconciled."""
	filters = {
		"company": bank_line.company,
		"reference_no": bank_line.reference_number or bank_line.name,
		"payment_type": "Receive" if receiving else "Pay",
	}
	drafts, submitted = [], []
	for docstatus, into in ((0, drafts), (1, submitted)):
		for r in frappe.get_list(
			"Payment Entry",
			filters={**filters, "docstatus": docstatus},
			fields=["name", "party", "paid_amount", "creation", "owner"],
			order_by="creation desc",
		):
			if docstatus == 1 and frappe.db.exists(
				"Bank Transaction Payments", {"payment_document": "Payment Entry", "payment_entry": r.name}
			):
				continue
			into.append(
				{
					"name": r.name,
					"party": r.party,
					"amount": flt(r.paid_amount, 2),
					"by": r.owner,
					"on": r.creation,
					"references": _references_of(r.name),
				}
			)
	return drafts, submitted


@frappe.whitelist()
def get_candidates(bank_transaction: str, party: str | None = None) -> dict | None:
	"""What a person is shown for a bank line that no single invoice settles: the open invoices of the party, the amount
	that is the same as the payment, and the payments already prepared for the line. `show` says whether the card is
	needed at all; None when the line is dealt with."""
	follow_up._check_rights()
	frappe.has_permission("Bank Transaction", "read", bank_transaction, throw=True)
	bank_line = frappe.db.get_value(
		"Bank Transaction",
		bank_transaction,
		follow_up.BANK_LINE_FIELDS + ["party_type", "party", "bank_party_iban", "bank_party_name"],
		as_dict=True,
	)
	if not follow_up._is_open(bank_line):
		return None
	receiving = flt(bank_line.deposit) > 0
	doctype = "Sales Invoice" if receiving else "Purchase Invoice"
	party_type = "Customer" if receiving else "Supplier"
	amount = follow_up._amount_of(bank_line)
	line = follow_up._import_line_of(bank_transaction)
	recognised = _recognised(line)

	reason = "none"
	paid_on = None
	if len(recognised) > 1:
		reason = "several"
	elif len(recognised) == 1 and frappe.db.exists(doctype, recognised[0]):
		if flt(frappe.db.get_value(doctype, recognised[0], "outstanding_amount")) > CENT:
			# one open invoice is the business of the card of the gap, not of this one
			reason = "open"
		else:
			reason = "paid"
			paid_on = frappe.db.sql(
				"""
				select max(pe.posting_date) from `tabPayment Entry Reference` per
				join `tabPayment Entry` pe on pe.name = per.parent and pe.docstatus = 1
				where per.reference_doctype = %s and per.reference_name = %s
				""",
				(doctype, recognised[0]),
			)[0][0]

	drafts, submitted = _entries_of(bank_line, receiving)
	chosen_party, source = _party_of(bank_line, line, party_type, party)
	invoices = (
		_open_invoices(doctype, chosen_party, bank_line.company, bank_line.currency, amount) if chosen_party else []
	)
	party_label = (
		frappe.db.get_value(party_type, chosen_party, "customer_name" if receiving else "supplier_name") if chosen_party else None
	)
	# shown whenever the import left the line with no single invoice: with the party found, its open invoices; without, the
	# search for the party (the person says who it is, then the invoices of that person come)
	show = bool(drafts or submitted) or (bool(line) and reason in ("none", "paid", "several"))
	return {
		"bank_transaction": bank_transaction,
		"show": show,
		"direction": "in" if receiving else "out",
		"amount": flt(amount, 2),
		"currency": bank_line.currency,
		"reason": reason,
		"reference_hint": (line.remittance_reference if line and line.remittance_reference else None)
		or (recognised[0] if recognised else None),
		"paid_on": paid_on,
		"invoice_type": doctype,
		"party_type": party_type,
		"party": chosen_party,
		"party_label": party_label,
		"party_source": source,
		"invoices": invoices,
		"recognised": recognised,
		"drafts": drafts,
		"submitted": submitted,
	}


def _as_list(allocations) -> list[dict]:
	if isinstance(allocations, str):
		allocations = json.loads(allocations or "[]")
	return [
		{"invoice": str(row.get("invoice")), "amount": flt(row.get("amount"), 2)}
		for row in allocations or []
		if flt(row.get("amount")) > 0
	]


def _entry(bank_line, doctype: str, party_type: str, party: str, allocations: list[dict]):
	"""The payment entry (not saved) that settles these invoices with the amount of the bank line, the invoices split as chosen."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry, get_reference_details

	ledger_account = frappe.get_cached_value("Bank Account", bank_line.bank_account, "account")
	reference = bank_line.reference_number or bank_line.name
	first = allocations[0]
	pe = get_payment_entry(
		doctype,
		first["invoice"],
		party_amount=first["amount"],
		bank_account=ledger_account,
		reference_date=bank_line.date,
		reference_no=reference,
	)
	for row in allocations[1:]:
		details = get_reference_details(doctype, row["invoice"], pe.party_account_currency, party_type, party)
		pe.append(
			"references",
			{
				"reference_doctype": doctype,
				"reference_name": row["invoice"],
				"bill_no": details.get("bill_no"),
				"due_date": details.get("due_date"),
				"total_amount": details.get("total_amount"),
				"outstanding_amount": details.get("outstanding_amount"),
				"allocated_amount": row["amount"],
				"exchange_rate": details.get("exchange_rate"),
			},
		)
	total = flt(sum(row["amount"] for row in allocations), 2)
	pe.paid_amount = pe.received_amount = total
	pe.posting_date = bank_line.date
	pe.reference_date = bank_line.date
	pe.reference_no = reference
	pe.remarks = _("{0} - Payment for {1}").format(party, ", ".join(row["invoice"] for row in allocations))
	return pe


def _check_allocations(bank_line, doctype: str, party: str, allocations: list[dict]) -> float:
	"""The split is sound: open invoices of this party, in the currency of the line, each within what it still owes, and the
	whole equal to what the bank moved. The amount, or throws."""
	if not allocations:
		frappe.throw(_("Pick the invoices this payment settles."))
	if len({row["invoice"] for row in allocations}) != len(allocations):
		frappe.throw(_("An invoice appears twice in the split."))
	company_currency = frappe.get_cached_value("Company", bank_line.company, "default_currency")
	if bank_line.currency != company_currency:
		frappe.throw(_("A payment in a foreign currency is recorded in the payment window."))
	party_field = "customer" if doctype == "Sales Invoice" else "supplier"
	for row in allocations:
		invoice = frappe.db.get_value(
			doctype,
			row["invoice"],
			["docstatus", "company", party_field, "outstanding_amount", "currency"],
			as_dict=True,
		)
		if not invoice or invoice.docstatus != 1 or invoice.company != bank_line.company or invoice[party_field] != party:
			frappe.throw(_("{0} is not an open invoice of {1}.").format(row["invoice"], party))
		if invoice.currency != bank_line.currency:
			frappe.throw(_("{0} is not in the currency of the payment.").format(row["invoice"]))
		if row["amount"] > flt(invoice.outstanding_amount) + CENT:
			frappe.throw(
				_("{0}: {1} asked, {2} still owed.").format(row["invoice"], row["amount"], flt(invoice.outstanding_amount, 2))
			)
	amount = flt(follow_up._amount_of(bank_line), 2)
	total = flt(sum(row["amount"] for row in allocations), 2)
	if abs(total - amount) > CENT:
		frappe.throw(_("The invoices add up to {0}, the payment is {1}.").format(total, amount))
	return amount


def _reconcile(bank_transaction: str, entry) -> dict:
	from mint.apis.bank_reconciliation import reconcile_vouchers

	return reconcile_vouchers(
		bank_transaction,
		json.dumps([{"payment_doctype": "Payment Entry", "payment_name": entry.name, "amount": entry.paid_amount}]),
		is_new_voucher=True,
	)


@frappe.whitelist(methods=["POST"])
def settle(bank_transaction: str, allocations: list | str, party: str, draft: int | str = 0) -> dict:
	"""One payment, one or several invoices: the payment entry is made with the split the person chose, then validated and
	reconciled with the bank line, or left as a DRAFT (`draft`) that the person opens and corrects before validating."""
	follow_up._check_rights()
	frappe.has_permission("Payment Entry", "create", throw=True)
	frappe.has_permission("Bank Transaction", "write", bank_transaction, throw=True)
	bank_line = frappe.db.get_value("Bank Transaction", bank_transaction, follow_up.BANK_LINE_FIELDS, as_dict=True)
	if not follow_up._is_open(bank_line):
		frappe.throw(_("This bank line is already dealt with."))
	receiving = flt(bank_line.deposit) > 0
	doctype = "Sales Invoice" if receiving else "Purchase Invoice"
	party_type = "Customer" if receiving else "Supplier"
	split = _as_list(allocations)
	_check_allocations(bank_line, doctype, party, split)
	pe = _entry(bank_line, doctype, party_type, party, split)
	pe.insert()
	if str(draft).lower() in ("1", "true"):
		return {"payment_entry": pe.name, "draft": True}
	pe.submit()
	_reconcile(bank_transaction, pe)
	return {"payment_entry": pe.name, "draft": False}


def _prepared_entry(bank_transaction: str, payment_entry: str):
	"""The payment prepared for this bank line (the reference of the line on it), draft or validated and not yet reconciled."""
	bank_line = frappe.db.get_value("Bank Transaction", bank_transaction, follow_up.BANK_LINE_FIELDS, as_dict=True)
	if not follow_up._is_open(bank_line):
		frappe.throw(_("This bank line is already dealt with."))
	receiving = flt(bank_line.deposit) > 0
	drafts, submitted = _entries_of(bank_line, receiving)
	if payment_entry not in {e["name"] for e in drafts + submitted}:
		frappe.throw(_("{0} was not prepared for this bank line.").format(payment_entry))
	return frappe.get_doc("Payment Entry", payment_entry), bank_line


@frappe.whitelist(methods=["POST"])
def submit_draft(bank_transaction: str, payment_entry: str) -> dict:
	"""Validate the payment prepared for the line (as the person corrected it) and reconcile it; when it was already
	validated in its own tab, only reconcile it."""
	follow_up._check_rights()
	frappe.has_permission("Bank Transaction", "write", bank_transaction, throw=True)
	frappe.has_permission("Payment Entry", "submit", payment_entry, throw=True)
	pe, bank_line = _prepared_entry(bank_transaction, payment_entry)
	if pe.docstatus == 0:
		pe.save()
		pe.submit()
	amount = flt(follow_up._amount_of(bank_line), 2)
	if abs(flt(pe.paid_amount, 2) - amount) > CENT:
		frappe.throw(_("The payment is {0}, the bank line {1}.").format(flt(pe.paid_amount, 2), amount))
	_reconcile(bank_transaction, pe)
	return {"payment_entry": pe.name}


@frappe.whitelist(methods=["POST"])
def delete_draft(bank_transaction: str, payment_entry: str) -> bool:
	"""Throw away a draft prepared for the line (only a draft, only one prepared for this line)."""
	follow_up._check_rights()
	frappe.has_permission("Bank Transaction", "write", bank_transaction, throw=True)
	frappe.has_permission("Payment Entry", "delete", payment_entry, throw=True)
	pe, _bank_line = _prepared_entry(bank_transaction, payment_entry)
	if pe.docstatus != 0:
		frappe.throw(_("{0} is not a draft.").format(payment_entry))
	frappe.delete_doc("Payment Entry", payment_entry)
	return True
