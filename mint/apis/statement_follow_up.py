# //// Neoffice — added file (no upstream equivalent).
# ////
# //// WHAT BECAME OF EACH LINE OF A BANK STATEMENT IMPORT: THE FOLLOW-UP THAT NEVER GOES STALE.
# ////
# //// An import hands its lines over: some are passed by themselves, some wait for a person in the bank
# //// reconciliation, some match nothing. What a line IS afterwards is read from the Bank Transaction it created, at
# //// the moment somebody looks, and never copied back onto the import: a copy would have to be kept in step by every
# //// path that reconciles a line (the reconciliation screen, ERPNext's own tool, an undo, a cancelled entry) and the
# //// first path forgotten would leave the import saying « to do » over a line that is done, or the reverse.
# //// The only thing the import stores is what no document records: that a person decided to leave a gap open, who,
# //// and when (`note_decision`).
# ////
# //// States of a line, in the order they are told:
# ////   passed_alone   the import made the entry itself and the bank line is reconciled
# ////   handled        the bank line was reconciled afterwards, by a person or a rule (who, when, with what)
# ////   left_open      a person decided to leave the gap open
# ////   to_decide      the invoice is recognised, the sum does not settle it, nobody has decided yet
# ////   to_match       no invoice recognised: the line waits in the bank reconciliation like any other
# ////   duplicate      the bank line already existed, nothing was created
# ////   failed         the import could not handle the line
# ////   cancelled      the bank line was cancelled afterwards

import frappe
from frappe import _
from frappe.utils import now_datetime

IMPORT = "Mint Bank Statement Import"
LINE = "Mint Bank Statement Import Transactions"
STATES = ("passed_alone", "handled", "left_open", "to_decide", "to_match", "duplicate", "failed", "cancelled")
WAITING = ("to_decide", "to_match")
DECISIONS = ("passed_gap", "left_open")


def classify(line, bank_line) -> str:
	"""The state of one import line, given the row of the import and the row of its Bank Transaction (or None)."""
	if line.status == "Existing":
		return "duplicate"
	if line.status == "Error":
		return "failed"
	if not bank_line:
		return "to_match"
	if bank_line.docstatus == 2 or bank_line.status == "Cancelled":
		return "cancelled"
	if bank_line.status in ("Reconciled", "Settled"):
		if line.decision == "left_open":
			# reconciled since: the decision to leave the gap open no longer describes it
			return "handled"
		return "passed_alone" if line.payment_entry else "handled"
	if line.decision == "left_open":
		return "left_open"
	return "to_decide" if line.difference_kind and line.difference_kind != "exact" else "to_match"


def _bank_lines(names) -> dict:
	names = [name for name in names if name]
	if not names:
		return {}
	rows = frappe.get_all(
		"Bank Transaction", filters={"name": ("in", names)}, fields=["name", "status", "docstatus"]
	)
	return {row.name: row for row in rows}


def _bank_line_of(line) -> str | None:
	return line.get("bank_transaction") or line.get("existing_bank_transaction") or None


def _check_rights(import_name: str | None = None):
	frappe.has_permission(IMPORT, "read", import_name, throw=True)
	frappe.has_permission("Bank Transaction", "read", throw=True)


def _source(statement) -> str:
	"""« ebics » when the statement came through a bank connection, « manual » when somebody deposited the file."""
	if frappe.get_meta(IMPORT).get_field("ebics_connection") and statement.get("ebics_connection"):
		return "ebics"
	return "manual"


def _vouchers(bank_line: str) -> list[dict]:
	"""The entries a reconciled bank line is linked to, with who made them and when."""
	rows = frappe.get_all(
		"Bank Transaction Payments",
		filters={"parent": bank_line, "parenttype": "Bank Transaction"},
		fields=["payment_document", "payment_entry", "allocated_amount"],
		order_by="idx",
	)
	vouchers = []
	for row in rows:
		made = frappe.db.get_value(row.payment_document, row.payment_entry, ["owner", "creation"], as_dict=True)
		vouchers.append(
			{
				"doctype": row.payment_document,
				"name": row.payment_entry,
				"amount": row.allocated_amount,
				"by": made.owner if made else None,
				"on": made.creation if made else None,
			}
		)
	return vouchers


@frappe.whitelist()
def get_import_overview(name: str) -> dict:
	"""One import told line by line: where it came from, how far along it is, and what became of each line."""
	_check_rights(name)
	statement = frappe.get_doc(IMPORT, name)
	bank_lines = _bank_lines([_bank_line_of(line) for line in statement.transactions])
	lines, counts = [], dict.fromkeys(STATES, 0)
	for line in statement.transactions:
		bank_line = bank_lines.get(_bank_line_of(line))
		state = classify(line, bank_line)
		counts[state] += 1
		vouchers = _vouchers(_bank_line_of(line)) if state in ("passed_alone", "handled") else []
		lines.append(
			{
				"idx": line.idx,
				"date": line.date,
				"amount": line.amount,
				"direction": "in" if line.credit_debit == "CRDT" else "out",
				"party": line.party_name,
				"description": line.description,
				"reference": line.unique_reference or line.reference,
				"state": state,
				"difference_kind": line.difference_kind,
				"difference_amount": line.difference_amount,
				"bank_transaction": _bank_line_of(line),
				"vouchers": vouchers,
				"decision": line.decision,
				"decided_by": line.decided_by,
				"decided_on": line.decided_on,
			}
		)
	return {
		"name": statement.name,
		"created_on": statement.creation,
		"created_by": statement.owner,
		"source": _source(statement),
		"bank_account": statement.bank_account,
		"currency": statement.currency,
		"summary": statement.import_summary,
		"docstatus": statement.docstatus,
		"counts": counts,
		"progress": _progress(counts),
		"lines": lines,
	}


def _progress(counts: dict) -> dict:
	"""How many lines there were to handle, how many still wait. Duplicates created nothing, so they do not count."""
	total = sum(count for state, count in counts.items() if state != "duplicate")
	waiting = sum(counts[state] for state in WAITING)
	return {"total": total, "waiting": waiting, "done": total - waiting}


@frappe.whitelist()
def list_imports(bank_account: str | None = None, start: int = 0, limit: int = 20) -> list[dict]:
	"""The latest imports with their counts: what a person looks at to see whether everything is dealt with."""
	_check_rights()
	filters = {"bank_account": bank_account} if bank_account else {}
	statements = frappe.get_list(
		IMPORT,
		filters=filters,
		fields=["name", "creation", "owner", "bank_account", "currency", "import_summary", "docstatus", "status"],
		order_by="creation desc",
		start=int(start),
		page_length=min(int(limit), 100),
	)
	if not statements:
		return []
	names = [statement.name for statement in statements]
	lines = frappe.get_all(
		LINE,
		filters={"parent": ("in", names), "parenttype": IMPORT},
		fields=[
			"parent",
			"status",
			"payment_entry",
			"difference_kind",
			"decision",
			"bank_transaction",
			"existing_bank_transaction",
		],
		limit_page_length=0,
	)
	bank_lines = _bank_lines([_bank_line_of(line) for line in lines])
	counts = {name: dict.fromkeys(STATES, 0) for name in names}
	for line in lines:
		counts[line.parent][classify(line, bank_lines.get(_bank_line_of(line)))] += 1
	connected = bool(frappe.get_meta(IMPORT).get_field("ebics_connection"))
	sources = (
		dict(frappe.get_all(IMPORT, filters={"name": ("in", names)}, fields=["name", "ebics_connection"], as_list=True))
		if connected
		else {}
	)
	return [
		{
			**statement,
			"source": "ebics" if sources.get(statement.name) else "manual",
			"counts": counts[statement.name],
			"progress": _progress(counts[statement.name]),
		}
		for statement in statements
	]


def note_decision(bank_transaction: str, decision: str) -> bool:
	"""Record that a person decided for the import line that created this bank line: who and when.

	Called by the reconciliation when somebody passes a gap or leaves it open. False when the bank line did not come
	from an import (nothing to record)."""
	if decision not in DECISIONS:
		frappe.throw(_("Unknown decision {0}.").format(decision))
	rows = frappe.get_all(LINE, filters={"bank_transaction": bank_transaction, "parenttype": IMPORT}, pluck="name")
	for row in rows:
		frappe.db.set_value(
			LINE,
			row,
			{"decision": decision, "decided_by": frappe.session.user, "decided_on": now_datetime()},
			update_modified=False,
		)
	return bool(rows)
