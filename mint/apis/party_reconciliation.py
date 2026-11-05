# //// Neoffice — added file (no upstream equivalent).
# ////
# //// RECONCILING A PARTY'S PAYMENTS, CREDITS AND JOURNAL ENTRIES AGAINST ITS INVOICES, WITHOUT THE DOCTYPE'S SCREEN.
# ////
# //// ERPNext's Payment Reconciliation is an engine behind a desk page: pick the party, tick, "Allocate", "Reconcile",
# //// and "Allocate" with nothing ticked allocates everything in order. This module calls the same engine the way that
# //// page does (the document is not stored: set the party, get_unreconciled_entries, allocate_entries with rows
# //// we choose, reconcile) and puts what the page lacks around it: the parties that have something to reconcile,
# //// the amount to use per row, a preview that writes nothing, a check of every right on every voucher, and a
# //// refusal when the rows changed since the screen was drawn (two people at the same time).
# //// Nothing here is computed again: the allocation, the exchange gain or loss and the credit-note journal entries
# //// are the engine's. It knows nothing of Mint's doctypes, so it can move into ERPNext's banking/ with the rest.

import json

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

PARTY_TYPES = ("Customer", "Supplier")
ACCOUNT_TYPES = {"Customer": "Receivable", "Supplier": "Payable"}
NAME_FIELDS = {"Customer": "customer_name", "Supplier": "supplier_name"}
ROW_LIMIT = 500
# Below half a cent an amount is a rounding residue, not something left to reconcile.
CENT = 0.005


def _guard(company: str, party_type: str, party: str | None = None):
	if party_type not in PARTY_TYPES:
		frappe.throw(_("Only customers and suppliers can be reconciled here."), title=_("Invalid Party Type"))
	frappe.has_permission("Payment Reconciliation", ptype="read", throw=True)
	frappe.has_permission("Company", ptype="read", doc=company, throw=True)
	if party:
		frappe.has_permission(party_type, ptype="read", doc=party, throw=True)


def _as_list(value) -> list:
	if isinstance(value, str):
		value = json.loads(value or "[]")
	return list(value or [])


def _ledger(company: str, party_type: str, party: str | None = None):
	"""What is still open at the payment ledger, by document: positive for what has to be settled (invoices, in
	both directions of trade), negative for what can settle it (payments, credit notes, journal entries)."""
	conditions = ["delinked = 0", "company = %(company)s", "party_type = %(party_type)s", "account_type = %(account_type)s"]
	values = {"company": company, "party_type": party_type, "account_type": ACCOUNT_TYPES[party_type], "cent": CENT}
	if party:
		conditions.append("party = %(party)s")
		values["party"] = party
	return frappe.db.sql(
		f"""
		SELECT party, account, against_voucher_type, against_voucher_no,
			SUM(amount) AS outstanding, MIN(posting_date) AS posting_date
		FROM `tabPayment Ledger Entry`
		WHERE {" AND ".join(conditions)}
		GROUP BY party, account, against_voucher_type, against_voucher_no
		HAVING ABS(SUM(amount)) > %(cent)s
		""",
		values,
		as_dict=True,
	)


@frappe.whitelist(methods=["GET"])
def get_parties(company: str, party_type: str, search: str | None = None, only_open: int = 1, limit: int = 100):
	"""The parties of a kind with something to reconcile: open documents AND amounts that could settle them."""
	_guard(company, party_type)

	parties = {}
	for row in _ledger(company, party_type):
		party = parties.setdefault(
			row.party,
			{"party": row.party, "open": 0.0, "open_count": 0, "credit": 0.0, "credit_count": 0, "oldest": None, "accounts": set()},
		)
		if row.outstanding > 0:
			party["open"] += row.outstanding
			party["open_count"] += 1
		else:
			party["credit"] -= row.outstanding
			party["credit_count"] += 1
		party["accounts"].add(row.account)
		if row.posting_date and (not party["oldest"] or row.posting_date < party["oldest"]):
			party["oldest"] = row.posting_date

	if int(only_open):
		parties = {k: v for k, v in parties.items() if v["open_count"] and v["credit_count"]}

	# get_list, not get_all: the parties the user may not read are not listed.
	field = NAME_FIELDS[party_type]
	readable = {
		row.name: row.get(field)
		for row in frappe.get_list(party_type, filters={"name": ["in", list(parties) or [""]]}, fields=["name", field], limit_page_length=0)
	}
	needle = (search or "").strip().lower()
	result = []
	for name, party in parties.items():
		if name not in readable:
			continue
		label = readable[name] or name
		if needle and needle not in name.lower() and needle not in str(label).lower():
			continue
		result.append(
			{
				**party,
				"label": label,
				"open": flt(party["open"], 2),
				"credit": flt(party["credit"], 2),
				"accounts": sorted(party["accounts"]),
			}
		)
	# What has waited longest first.
	result.sort(key=lambda p: (p["oldest"] or getdate(nowdate())))
	return result[: max(1, int(limit))]


def _engine(company: str, party_type: str, party: str, account: str | None):
	"""The engine's document, with the entries it finds for this party loaded."""
	from erpnext.accounts.party import get_party_account

	account = account or get_party_account(party_type, party, company)
	if not account:
		frappe.throw(_("{0} {1} has no {2} account in {3}.").format(_(party_type), party, _(ACCOUNT_TYPES[party_type]), company))
	doc = frappe.get_doc("Payment Reconciliation")
	doc.company = company
	doc.party_type = party_type
	doc.party = party
	doc.receivable_payable_account = account
	doc.invoice_limit = ROW_LIMIT
	doc.payment_limit = ROW_LIMIT
	doc.get_unreconciled_entries()
	return doc


def _plain(row) -> dict:
	row = row.as_dict() if hasattr(row, "as_dict") else dict(row)
	return {key: value for key, value in row.items() if key not in ("doctype", "parent", "parentfield", "parenttype", "owner", "creation", "modified", "modified_by", "idx", "docstatus")}


def _enrich(rows: list[dict], doctype_key: str, name_key: str, fields: dict[str, list[str]]):
	"""Add what the engine's rows do not carry (reference, due date, remark) from the vouchers themselves."""
	by_type = {}
	for row in rows:
		by_type.setdefault(row.get(doctype_key), []).append(row.get(name_key))
	for doctype, names in by_type.items():
		wanted = fields.get(doctype)
		if not wanted or not frappe.get_meta(doctype, cached=True):
			continue
		found = {
			d.name: d
			for d in frappe.get_all(doctype, filters={"name": ["in", names]}, fields=["name", *wanted])
		}
		for row in rows:
			if row.get(doctype_key) == doctype and row.get(name_key) in found:
				row.update({k: v for k, v in found[row[name_key]].items() if k != "name"})


INVOICE_FIELDS = {
	"Sales Invoice": ["due_date", "po_no AS reference", "remarks AS remark"],
	"Purchase Invoice": ["due_date", "bill_no AS reference", "remarks AS remark"],
	"Journal Entry": ["cheque_no AS reference", "user_remark AS remark"],
}
SETTLEMENT_FIELDS = {
	"Payment Entry": ["reference_no AS reference", "remarks AS remark", "mode_of_payment"],
	"Journal Entry": ["cheque_no AS reference", "user_remark AS remark"],
	"Sales Invoice": ["po_no AS reference", "remarks AS remark", "return_against"],
	"Purchase Invoice": ["bill_no AS reference", "remarks AS remark", "return_against"],
}


def _balance_check(doc, open_total: float, credit_total: float) -> dict:
	"""The ledger's balance of the party on the account, against what the open documents say."""
	from erpnext.accounts.utils import get_balance_on

	sign = 1 if ACCOUNT_TYPES[doc.party_type] == "Receivable" else -1
	ledger = sign * flt(get_balance_on(account=doc.receivable_payable_account, date=nowdate(), party_type=doc.party_type, party=doc.party, company=doc.company))
	documents = flt(open_total - credit_total, 2)
	return {"ledger": flt(ledger, 2), "documents": documents, "difference": flt(ledger - documents, 2)}


@frappe.whitelist(methods=["GET"])
def get_party_detail(company: str, party_type: str, party: str, account: str | None = None):
	"""One party: its open documents on the left, what could settle them on the right."""
	_guard(company, party_type, party)
	doc = _engine(company, party_type, party, account)

	invoices = [_plain(row) for row in doc.invoices]
	settlements = [_plain(row) for row in doc.payments]
	_enrich(invoices, "invoice_type", "invoice_number", INVOICE_FIELDS)
	_enrich(settlements, "reference_type", "reference_name", SETTLEMENT_FIELDS)

	open_total = sum(flt(row["outstanding_amount"]) for row in invoices)
	credit_total = sum(flt(row["amount"]) for row in settlements)
	# A party can have documents on more than one collective account (an advance, a separate account of its own):
	# the engine reconciles one account at a time, and the screen says where the rest is.
	elsewhere = {}
	for row in _ledger(company, party_type, party):
		if row.account != doc.receivable_payable_account:
			elsewhere[row.account] = elsewhere.get(row.account, 0.0) + flt(row.outstanding)

	return {
		"party": party,
		"party_type": party_type,
		"label": frappe.db.get_value(party_type, party, NAME_FIELDS[party_type]) or party,
		"company": company,
		"account": doc.receivable_payable_account,
		"currency": frappe.get_cached_value("Company", company, "default_currency"),
		"invoices": invoices,
		"payments": settlements,
		"totals": {"open": flt(open_total, 2), "credit": flt(credit_total, 2), "balance": flt(open_total - credit_total, 2)},
		"check": _balance_check(doc, open_total, credit_total),
		"other_accounts": [{"account": a, "balance": flt(v, 2)} for a, v in sorted(elsewhere.items())],
	}


def _pick(rows: list[dict], chosen: list, kind_key: str, name_key: str, amount_key: str, row_key: str | None = None) -> list[dict]:
	"""The rows the user ticked, each with the amount to use, refused when it is no longer what the screen showed.

	A journal entry can have several open lines for one party: for those the line is part of the key."""

	def key_of(item) -> tuple:
		return (item.get(kind_key), item.get(name_key), (item.get(row_key) or None) if row_key else None)

	by_key = {key_of(row): row for row in rows}
	picked = []
	seen = set()
	for choice in chosen:
		key = key_of(choice)
		if key in seen:
			frappe.throw(_("{0} {1} is chosen twice.").format((_(key[0]) if key[0] else ""), key[1]))
		seen.add(key)
		row = by_key.get(key)
		if not row:
			frappe.throw(
				_("{0} {1} is no longer open: someone has reconciled it, or it was cancelled. Reload the party.").format((_(key[0]) if key[0] else ""), key[1]),
				title=_("The party has changed"),
			)
		available = flt(row[amount_key])
		amount = flt(choice.get("amount")) or available
		if amount <= 0 or amount > available + CENT:
			frappe.throw(
				_("{0} {1}: {2} asked, {3} left. Reload the party.").format((_(key[0]) if key[0] else ""), key[1], amount, available),
				title=_("The party has changed"),
			)
		picked.append({**row, amount_key: min(amount, available)})
	return picked


def _voucher_key(row) -> tuple:
	"""A payment row: the voucher and, for a journal entry, the line of it."""
	return (row.get("reference_type"), row.get("reference_name"), row.get("reference_row") or None)


def _allocate(company: str, party_type: str, party: str, account: str | None, invoices, payments):
	invoices, payments = _as_list(invoices), _as_list(payments)
	if not invoices or not payments:
		# The engine allocates everything in order when nothing is named: never ask it that.
		frappe.throw(_("Choose at least one invoice and one payment, credit note or entry."))
	_guard(company, party_type, party)
	doc = _engine(company, party_type, party, account)
	chosen_invoices = _pick(
		[_plain(r) for r in doc.invoices], invoices, "invoice_type", "invoice_number", "outstanding_amount"
	)
	payment_rows = [_plain(r) for r in doc.payments]
	rows_by_key = {_voucher_key(r): r for r in payment_rows}
	chosen_payments = _pick(payment_rows, payments, "reference_type", "reference_name", "amount", "reference_row")

	# Each voucher the allocation will change is one the user may write; the invoices only have to be readable.
	for row in chosen_payments:
		frappe.has_permission(row["reference_type"], ptype="write", doc=row["reference_name"], throw=True)
	for row in chosen_invoices:
		frappe.has_permission(row["invoice_type"], ptype="read", doc=row["invoice_number"], throw=True)

	# The engine spends the rows it is given: what was chosen is measured before it runs.
	chosen = {
		"invoices": flt(sum(flt(r["outstanding_amount"]) for r in chosen_invoices), 2),
		"payments": flt(sum(flt(r["amount"]) for r in chosen_payments), 2),
	}
	# The amount a payment is given to spend can be less than what it holds; the engine compares the amount it
	# "unreconciled" with what the payment really holds, and refuses an entry that "was modified after you pulled it".
	holds = {_voucher_key(r): flt(rows_by_key[_voucher_key(r)]["amount"]) for r in chosen_payments}
	doc.allocate_entries({"invoices": chosen_invoices, "payments": chosen_payments})
	for row in doc.get("allocation"):
		row.unreconciled_amount = holds[_voucher_key(row)]
	return doc, chosen


def _allocation(doc) -> list[dict]:
	keep = (
		"reference_type", "reference_name", "invoice_type", "invoice_number", "allocated_amount",
		"unreconciled_amount", "amount", "difference_amount", "currency",
	)
	return [{key: row.get(key) for key in keep} for row in doc.get("allocation")]


@frappe.whitelist(methods=["POST"])
def preview(company: str, party_type: str, party: str, invoices: str | list, payments: str | list, account: str | None = None):
	"""What the reconciliation of these rows would write. Nothing is written."""
	doc, chosen = _allocate(company, party_type, party, account, invoices, payments)
	allocation = _allocation(doc)
	settled = flt(sum(flt(row["allocated_amount"]) for row in allocation), 2)
	return {
		"allocation": allocation,
		"settled": settled,
		"difference": flt(sum(flt(row.get("difference_amount")) for row in allocation), 2),
		"invoices_left": flt(chosen["invoices"] - settled, 2),
		"credits_left": flt(chosen["payments"] - settled, 2),
	}


@frappe.whitelist(methods=["POST"])
def reconcile(company: str, party_type: str, party: str, invoices: str | list, payments: str | list, account: str | None = None):
	"""Reconcile the rows the user chose, with the engine's own code."""
	frappe.has_permission("Payment Reconciliation", ptype="write", throw=True)
	doc, _chosen = _allocate(company, party_type, party, account, invoices, payments)
	allocation = _allocation(doc)
	doc.reconcile()
	return {"allocation": allocation, "detail": get_party_detail(company, party_type, party, doc.receivable_payable_account)}


# What a click on a row shows: the lines, the remark, who made it and when.
VOUCHER_PAGES = {"Payment Entry": "payment-entry", "Journal Entry": "journal-entry", "Sales Invoice": "sales-invoice", "Purchase Invoice": "purchase-invoice"}


@frappe.whitelist(methods=["GET"])
def get_voucher_detail(voucher_type: str, voucher_name: str):
	if voucher_type not in VOUCHER_PAGES:
		frappe.throw(_("{0} is not a voucher this screen shows.").format(_(voucher_type)), title=_("Invalid Voucher"))
	voucher = frappe.get_doc(voucher_type, voucher_name)
	voucher.check_permission("read")

	lines = []
	if voucher_type == "Journal Entry":
		lines = [
			{"account": r.account, "party": r.party, "debit": r.debit_in_account_currency, "credit": r.credit_in_account_currency, "remark": r.user_remark}
			for r in voucher.accounts
		]
	elif voucher_type == "Payment Entry":
		lines = [
			{"reference": f"{r.reference_doctype} {r.reference_name}", "allocated": r.allocated_amount, "outstanding": r.outstanding_amount}
			for r in voucher.references
		]
	else:
		lines = [{"item": r.item_name or r.item_code, "qty": r.qty, "amount": r.amount} for r in voucher.items[:20]]

	return {
		"voucher_type": voucher_type,
		"name": voucher.name,
		"posting_date": voucher.get("posting_date"),
		"status": ["Draft", "Submitted", "Cancelled"][voucher.docstatus],
		"remark": voucher.get("remarks") or voucher.get("user_remark") or "",
		"reference": voucher.get("reference_no") or voucher.get("cheque_no") or voucher.get("bill_no") or voucher.get("po_no") or "",
		"owner": voucher.owner,
		"creation": voucher.creation,
		"lines": lines,
		"attachments": frappe.db.count("File", {"attached_to_doctype": voucher_type, "attached_to_name": voucher_name}),
		"route": f"/app/{VOUCHER_PAGES[voucher_type]}/{voucher.name}",
	}
