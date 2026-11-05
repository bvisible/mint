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
# ////   not_imported   the import is still a draft: nothing was created yet
# ////
# //// An import made before its lines carried their bank line (`bank_transaction`) is followed all the same: the bank
# //// line is found by the key the import itself uses to spot a duplicate (account, date, reference, amount, direction).

import ast

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime

IMPORT = "Mint Bank Statement Import"
LINE = "Mint Bank Statement Import Transactions"
STATES = (
	"passed_alone",
	"handled",
	"left_open",
	"to_decide",
	"to_match",
	"duplicate",
	"failed",
	"cancelled",
	"not_imported",
)
NOT_COUNTED = ("duplicate", "not_imported")
WAITING = ("to_decide", "to_match")
DECISIONS = ("passed_gap", "left_open")


def classify(line, bank_line) -> str:
	"""The state of one import line, given the row of the import and the row of its Bank Transaction (or None)."""
	if line.status == "Existing":
		return "duplicate"
	if line.status == "Error":
		return "failed"
	if line.status in ("To Process", "", None):
		return "not_imported"
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


def _resolve_missing_links(bank_account: str, lines) -> None:
	"""Give the lines of an older import their bank line, found by the import's own duplicate key (n-th line with a key
	is the n-th bank line with it, as the import counts them)."""
	missing = [
		line
		for line in lines
		if not _bank_line_of(line) and line.status not in ("Existing", "Error", "To Process", "", None)
	]
	references = {line.unique_reference or line.reference for line in missing} - {None, ""}
	if not missing or not references:
		return
	rows = frappe.get_all(
		"Bank Transaction",
		filters={"bank_account": bank_account, "reference_number": ("in", list(references)), "docstatus": ("!=", 2)},
		fields=["name", "date", "reference_number", "deposit", "withdrawal"],
		order_by="creation asc",
		limit_page_length=0,
	)
	pool = {}
	for row in rows:
		key = (str(row.date), row.reference_number, flt(row.withdrawal or row.deposit, 2), flt(row.withdrawal) > 0)
		pool.setdefault(key, []).append(row.name)
	seen = {}
	for line in missing:
		key = (
			str(line.date),
			line.unique_reference or line.reference,
			flt(line.amount, 2),
			line.credit_debit == "DBIT",
		)
		rank = seen.get(key, 0)
		seen[key] = rank + 1
		if rank < len(pool.get(key, [])):
			line.bank_transaction = pool[key][rank]


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


def latest_file_balance(bank_account: str, on_or_before) -> frappe._dict | None:
	"""The closing balance the bank itself wrote in the latest statement file imported for this account, with the day
	of the last line of that statement (the file gives the balance, not always its day). None when no file says one."""
	rows = frappe.db.sql(
		f"""
		select i.name, i.closing_balance as balance, max(t.date) as date
		from `tab{IMPORT}` i
		join `tab{LINE}` t on t.parent = i.name and t.parenttype = %(doctype)s
		where i.docstatus = 1 and i.file_type = 'XML' and i.bank_account = %(bank_account)s
			and i.closing_balance != 0 and t.status in ('Paid', 'Imported', 'Existing')
		group by i.name, i.closing_balance, i.creation
		having max(t.date) <= %(on_or_before)s
		order by max(t.date) desc, i.creation desc
		limit 1
		""",
		{"doctype": IMPORT, "bank_account": bank_account, "on_or_before": on_or_before},
		as_dict=True,
	)
	return rows[0] if rows else None


@frappe.whitelist()
def get_import_overview(name: str) -> dict:
	"""One import told line by line: where it came from, how far along it is, and what became of each line."""
	_check_rights(name)
	statement = frappe.get_doc(IMPORT, name)
	_resolve_missing_links(statement.bank_account, statement.transactions)
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
				"credit_note": line.get("credit_note"),
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
	"""How many lines there were to handle, how many still wait. Duplicates created nothing and a draft imported nothing, so they do not count."""
	total = sum(count for state, count in counts.items() if state not in NOT_COUNTED)
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
			"date",
			"amount",
			"credit_debit",
			"unique_reference",
			"reference",
			"idx",
			"payment_entry",
			"difference_kind",
			"decision",
			"bank_transaction",
			"existing_bank_transaction",
		],
		order_by="parent, idx",
		limit_page_length=0,
	)
	accounts = {statement.name: statement.bank_account for statement in statements}
	for name in names:
		_resolve_missing_links(accounts[name], [line for line in lines if line.parent == name])
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


def note_decision(bank_transaction: str, decision: str, credit_note: str | None = None) -> bool:
	"""Record that a person decided for the import line that created this bank line: who and when.

	Called by the reconciliation when somebody passes a gap or leaves it open. False when the bank line did not come
	from an import (nothing to record)."""
	if decision not in DECISIONS:
		frappe.throw(_("Unknown decision {0}.").format(decision))
	rows = frappe.get_all(LINE, filters={"bank_transaction": bank_transaction, "parenttype": IMPORT}, pluck="name")
	for row in rows:
		values = {"decision": decision, "decided_by": frappe.session.user, "decided_on": now_datetime()}
		if credit_note:
			values["credit_note"] = credit_note
		frappe.db.set_value(LINE, row, values, update_modified=False)
	return bool(rows)


# -- deciding a gap, from the bank reconciliation ---------------------------------------------------------------------
# The import announces, the bank reconciliation decides: a line whose invoice was recognised but whose sum did not settle
# it waits there like any other bank line, with the verdict in words and the choice of a person.

BANK_LINE_FIELDS = [
	"name",
	"bank_account",
	"date",
	"deposit",
	"withdrawal",
	"unallocated_amount",
	"status",
	"docstatus",
	"reference_number",
	"currency",
	"company",
]


def _import_line_of(bank_transaction: str):
	"""The import line that created this bank line, or None (the bank line came from somewhere else)."""
	rows = frappe.get_all(
		LINE,
		filters={"bank_transaction": bank_transaction, "parenttype": IMPORT},
		fields=[
			"name",
			"parent",
			"idx",
			"invoice_matches",
			"party_match",
			"party_name",
			"difference_kind",
			"difference_amount",
			"decision",
			"decided_by",
			"decided_on",
			"remittance_reference",
		],
		order_by="creation desc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def _invoice_of(line, bank_line):
	"""The ONE invoice the import recognised: a sales invoice for a deposit, a purchase invoice for a withdrawal."""
	try:
		matches = ast.literal_eval(line.invoice_matches) if line.invoice_matches else []
	except (ValueError, SyntaxError):
		matches = []
	if not isinstance(matches, (list, tuple)) or len(matches) != 1:
		return None, None
	doctype = "Sales Invoice" if flt(bank_line.deposit) > 0 else "Purchase Invoice"
	return (doctype, matches[0]) if frappe.db.exists(doctype, matches[0]) else (None, None)


def _is_open(bank_line) -> bool:
	return bool(bank_line) and bank_line.docstatus == 1 and bank_line.status not in ("Reconciled", "Settled", "Cancelled")


def _amount_of(bank_line) -> float:
	return flt(bank_line.unallocated_amount) or flt(bank_line.deposit) or flt(bank_line.withdrawal)


@frappe.whitelist()
def get_lines_to_decide(bank_account: str, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
	"""The bank lines of an account that came from an import with a gap nobody has decided yet, within the period the
	reconciliation shows (a count that includes lines outside it leads to a list that looks empty)."""
	_check_rights()
	frappe.has_permission("Bank Account", "read", bank_account, throw=True)
	return frappe.db.sql(
		f"""
		select bt.name as bank_transaction, t.parent as statement_import, t.idx, t.difference_kind as kind,
			t.difference_amount as gap, t.party_name as party
		from `tab{LINE}` t
		join `tab{IMPORT}` i on i.name = t.parent and i.docstatus != 2 and i.bank_account = %(account)s
		join `tabBank Transaction` bt on bt.name = t.bank_transaction and bt.docstatus = 1
			and bt.status not in ('Reconciled', 'Settled', 'Cancelled')
		where t.parenttype = %(doctype)s and ifnull(t.difference_kind, '') not in ('', 'exact')
			and ifnull(t.decision, '') != 'left_open'
			and (%(from_date)s is null or bt.date >= %(from_date)s) and (%(to_date)s is null or bt.date <= %(to_date)s)
		order by bt.date desc, t.parent desc, t.idx
		""",
		{"account": bank_account, "doctype": IMPORT, "from_date": from_date or None, "to_date": to_date or None},
		as_dict=True,
	)


def _discount_terms_of(invoice_type: str, invoice: str, on) -> dict:
	"""The percentage and the last day of the early payment discount still open on `on`, when the terms carry one."""
	rows = frappe.get_all(
		"Payment Schedule",
		filters={"parent": invoice, "parenttype": invoice_type},
		fields=["discount", "discount_type", "discount_date"],
		order_by="idx",
	)
	for row in rows:
		if flt(row.discount) and row.discount_date and getdate(row.discount_date) >= getdate(on):
			return {
				"discount_percent": flt(row.discount) if row.discount_type == "Percentage" else None,
				"discount_date": row.discount_date,
			}
	return {"discount_percent": None, "discount_date": None}


def _company_currency(company: str) -> str:
	return frappe.get_cached_value("Company", company, "default_currency")


def _as_flag(value) -> bool:
	return str(value).lower() in ("1", "true")


def _account_blocker(company: str, account: str | None) -> str:
	"""Why the account a person typed cannot take the gap, or an empty string (the message is said, not raised)."""
	if not account:
		return ""
	from mint.apis import payment_gap

	try:
		payment_gap.check_account(company, account)
	except frappe.ValidationError as error:
		frappe.clear_last_message()
		return str(error)
	return ""


@frappe.whitelist()
def get_gap_decision(
	bank_transaction: str, account: str | None = None, settle_in_full: int | str = 0, credit_note: int | str = 0
) -> dict | None:
	"""What a person is asked to decide for this bank line, with the verdict worked out now (the invoice may have moved
	since the import). None when the line did not come from an import, has no recognised invoice, or is dealt with.

	`account`, `settle_in_full` and `credit_note` are what the person is trying: the rows the gap would be booked as (VAT
	cut from the account by the same function the payment window uses), or the credit note of the balance, come back,
	nothing is written."""
	_check_rights()
	frappe.has_permission("Bank Transaction", "read", bank_transaction, throw=True)
	bank_line = frappe.db.get_value("Bank Transaction", bank_transaction, BANK_LINE_FIELDS, as_dict=True)
	if not _is_open(bank_line):
		return None
	line = _import_line_of(bank_transaction)
	if not line:
		return None
	invoice_type, invoice = _invoice_of(line, bank_line)
	if not invoice:
		return None
	from mint.apis import payment_gap

	verdict = payment_gap.judge(invoice_type, invoice, _amount_of(bank_line), bank_line.date, line.remittance_reference)
	# the credit note of the balance is for a short payment of a sale; it excludes passing the rest as a gap
	creditable = verdict.kind == "partial" and invoice_type == "Sales Invoice" and verdict.currency == _company_currency(
		verdict.company
	)
	credit = _as_flag(credit_note) and creditable
	settle = _as_flag(settle_in_full) and verdict.kind == "partial" and not credit
	editable = verdict.kind in ("rounding", "accepted_rebate", "partial")
	account = (account or None) if editable else None
	blocker = ""
	if verdict.kind in ("", "overpaid"):
		blocker = verdict.reason or _("More came in than is owed: that is never passed by itself.")
	else:
		blocker = _account_blocker(verdict.company, account) or payment_gap.account_problem(verdict, account, settle)
	settings = payment_gap.get_settings(verdict.company)
	rows = []
	if not blocker and verdict.kind not in ("", "overpaid", "exact") and not credit:
		rows = payment_gap.preview(verdict, frappe.get_doc(invoice_type, invoice), account, settle)
	customer = frappe.db.get_value(invoice_type, invoice, "customer") if invoice_type == "Sales Invoice" else None
	credit_preview = history = None
	if creditable and customer:
		from mint.apis import gap_credit_note

		credit_preview = gap_credit_note.preview(
			verdict.company, customer, bank_line.date, verdict.gap, account if credit else None
		)
		total = frappe.db.get_value("Sales Invoice", invoice, "grand_total")
		history = gap_credit_note.history(
			verdict.company, customer, invoice, flt(verdict.amount) / flt(total) if flt(total) else 0
		)
		if credit and credit_preview["blocker"]:
			blocker = credit_preview["blocker"]
	return {
		"bank_transaction": bank_transaction,
		"statement_import": line.parent,
		"invoice_type": invoice_type,
		"invoice": invoice,
		"party": line.party_name or line.party_match,
		"verdict": {
			key: verdict[key]
			for key in ("kind", "gap", "amount", "outstanding", "discount", "currency", "reason")
		},
		"can_pass": not blocker and verdict.kind not in ("", "exact"),
		"blocker": blocker,
		"account_editable": editable,
		"default_account": settings.account if editable else None,
		"account": (credit_preview["account"] if credit else None) or account or (settings.account if editable else None),
		"settle_in_full": settle,
		"credit_note_chosen": credit,
		"credit_note": credit_preview,
		"history": history,
		# offered for every partial payment: a company with no gap account of its own is not a reason to hide the choice,
		# the person picks the account in the card and what still blocks is said (`blocker`) once they have chosen
		"can_settle": verdict.kind == "partial",
		"deductions": [
			{"account": row.get("account"), "amount": flt(row.get("amount"), 2), "description": row.get("description")}
			for row in rows
		],
		"decision": line.decision,
		"decided_by": line.decided_by,
		"decided_on": line.decided_on,
		**_discount_terms_of(invoice_type, invoice, bank_line.date),
	}


@frappe.whitelist(methods=["POST"])
def decide_gap(
	bank_transaction: str,
	decision: str,
	account: str | None = None,
	settle_in_full: int | str = 0,
	credit_note: int | str = 0,
) -> dict:
	"""A person passes the gap of a bank line (the entry is made, linked to the line) or leaves it open.

	`account` is the account the person chose for the gap instead of the company's; `settle_in_full` settles a short
	payment beyond what the company accepts, the gap being passed on that account instead of left open; `credit_note`
	closes it the way the offices do: the payment is booked for what came in and a credit note of the balance settles
	the invoice (its account is `account`, else the customer's habit, else the company's gap account)."""
	if decision not in DECISIONS:
		frappe.throw(_("Unknown decision {0}.").format(decision))
	_check_rights()
	frappe.has_permission("Bank Transaction", "write", bank_transaction, throw=True)
	bank_line = frappe.db.get_value("Bank Transaction", bank_transaction, BANK_LINE_FIELDS, as_dict=True)
	if not _is_open(bank_line):
		frappe.throw(_("This bank line is already dealt with."))
	line = _import_line_of(bank_transaction)
	if not line:
		frappe.throw(_("This bank line did not come from an import."))
	if decision == "left_open":
		note_decision(bank_transaction, "left_open")
		return {"bank_transaction": bank_transaction, "payment_entry": None}

	invoice_type, invoice = _invoice_of(line, bank_line)
	if not invoice:
		frappe.throw(_("No invoice was recognised for this line."))
	frappe.has_permission("Payment Entry", "create", throw=True)
	frappe.has_permission(invoice_type, "read", invoice, throw=True)

	from mint.apis import payment_gap
	from mint.mint.doctype.mint_bank_statement_import.mint_bank_statement_import import _link_payment_entry_to_bt

	verdict = payment_gap.judge(invoice_type, invoice, _amount_of(bank_line), bank_line.date, line.remittance_reference)
	editable = verdict.kind in ("rounding", "accepted_rebate", "partial")
	credit = _as_flag(credit_note)
	if credit and not (verdict.kind == "partial" and invoice_type == "Sales Invoice"):
		frappe.throw(_("A credit note of the balance is for the short payment of a sales invoice."))
	if credit:
		# what can refuse the credit note is checked BEFORE the payment is booked: nothing is written for a refusal
		from mint.apis import gap_credit_note

		blocker = gap_credit_note.preview(
			verdict.company,
			frappe.db.get_value("Sales Invoice", invoice, "customer"),
			bank_line.date,
			verdict.gap,
			account or None,
		)["blocker"]
		if blocker:
			frappe.throw(blocker)
	entry = payment_gap.book(
		verdict,
		invoice_type,
		invoice,
		frappe.get_cached_value("Bank Account", bank_line.bank_account, "account"),
		bank_line.date,
		bank_line.reference_number or "",
		_("{0} - Payment for {1}").format(line.party_name or line.party_match, invoice),
		by_person=True,
		account=None if credit else ((account or None) if editable else None),
		settle_in_full=_as_flag(settle_in_full) and verdict.kind == "partial" and not credit,
	)
	_link_payment_entry_to_bt(
		frappe.get_doc("Bank Transaction", bank_transaction), entry, reconciliation_type="Voucher Created"
	)
	made = None
	if credit:
		from mint.apis import gap_credit_note

		customer = frappe.db.get_value("Sales Invoice", invoice, "customer")
		made = gap_credit_note.create(
			verdict.company,
			customer,
			bank_line.date,
			verdict.gap,
			account or None,
			_("Balance of {0}, paid {1} on {2}").format(invoice, verdict.amount, bank_line.date),
		)
		gap_credit_note.settle(verdict.company, customer, invoice, made, verdict.gap)
	note_decision(bank_transaction, "passed_gap", made)
	return {"bank_transaction": bank_transaction, "payment_entry": entry, "credit_note": made}


# -- what the person who deposited the file reads when the import is done -----------------------------------------------

DESK_IMPORTS = "/app/accounting?tab=reconcile&screen=%2Fmint%2Fstatement-imports"


def result_message(stats: dict, currency: str) -> str:
	"""The window after an import: what passed by itself, what waits and where to go to deal with it."""
	to_match = max(stats["unreconciled"] - stats["to_decide"], 0)
	waiting = stats["to_decide"] + to_match
	read = stats["total"]

	def row(tone: str, label: str, text: str) -> str:
		return f'<div style="margin-bottom:10px"><span class="indicator-pill {tone}">{label}</span> {text}</div>'

	rows = [f"<p>{frappe.utils.escape_html(_('{0} lines read in the file.').format(read))}</p>"]
	if stats["auto_matched"]:
		text = _("Booked.")
		if stats["passed_with_gap"]:
			text = _("Booked, {0} of them with a small gap ({1} in all).").format(
				stats["passed_with_gap"], frappe.utils.fmt_money(stats["gap_total"], currency=currency)
			)
		rows.append(row("green", _("{0} passed by themselves").format(stats["auto_matched"]), text))
	if stats["to_decide"]:
		rows.append(
			row(
				"orange",
				_("{0} to decide").format(stats["to_decide"]),
				_("A gap waits for your decision in the bank reconciliation."),
			)
		)
	if to_match:
		rows.append(
			row(
				"orange",
				_("{0} to match").format(to_match),
				_("No invoice recognised: they wait like any bank line not reconciled."),
			)
		)
	if stats["duplicates"]:
		rows.append(
			row(
				"gray",
				_("{0} already in the bank").format(stats["duplicates"]),
				_("Nothing was created for them."),
			)
		)
	if stats["errors"]:
		rows.append(row("red", _("{0} not handled").format(stats["errors"]), _("See the error log.")))
	links = [f'<a href="{DESK_IMPORTS}">{frappe.utils.escape_html(_("See all the imports"))}</a>']
	if waiting:
		links.insert(
			0,
			f'<a class="btn btn-primary btn-sm" href="{DESK_IMPORTS}">'
			f"{frappe.utils.escape_html(_('Settle the {0} that wait').format(waiting))}</a>",
		)
	rows.append("<p>" + " &nbsp; ".join(links) + "</p>")
	return "".join(rows)
