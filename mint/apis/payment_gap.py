# //// Neoffice — added file (no upstream equivalent).
# ////
# //// WHAT A PAYMENT IS TO THE INVOICE IT SETTLES, WHEN IT DOES NOT SETTLE IT TO THE CENT.
# ////
# //// One question, asked once: « this sum, for this invoice, on this date: what is it? ». The import of the bank
# //// statement, the window after a manual deposit and the screen that reconciles a party all ask it here, so that
# //// they never disagree. The answer is a verdict:
# ////   exact            to the cent: the payment settles the invoice
# ////   rounding         within the rounding tolerance of the company, in either direction
# ////   early_discount   the sum is the invoice minus the discount its payment terms grant on that date
# ////   accepted_rebate  sales only: less than owed by a small sum the company always accepts, or, beyond it, by up to the
# ////                    company's percentage of the balance (the percentage alone decides what is accepted). Above the
# ////                    amount the company asks to confirm, it is still accepted but never passed by itself: a person
# ////                    confirms it, and the screen says why
# ////   partial          less than owed beyond that: the money has come in, it is recorded, the rest stays open
# ////   dunning_fee      sales only: more than owed, by exactly what a validated dunning of that invoice still asks for
# ////                    (its fee and interest): booked on the account of the dunning, linked to it, which resolves it
# ////   overpaid         more than owed, and not a dunning's fee: never passed by itself. A PERSON decides what the surplus
# ////                    becomes, as for a partial payment: kept on the payment as an amount left open for a next invoice
# ////                    (the entry carries it as its unallocated amount, which a later reconciliation allocates), or
# ////                    passed as a difference on an account, the way the fee of a dunning is (a negative deduction, no VAT)
# //// A verdict says whether it may be passed AUTOMATICALLY (nobody in front of the screen) and, when it may not,
# //// why. Nothing is automatic until the company switches it on (Neoffice Company Settings, « Payment Gaps »);
# //// a partial payment is validated by itself only when the invoice is recognised without doubt.
# //// The entry is made by ERPNext's own get_payment_entry; only the deduction of a rounding or of a rebate is
# //// added to it, with its VAT cut from the account as the reconciliation screen does.

import frappe
from frappe import _
from frappe.utils import flt, fmt_money, getdate

CENT = 0.01
SETTINGS = "Neoffice Company Settings"
INVOICE_TYPES = ("Sales Invoice", "Purchase Invoice")


def get_settings(company: str) -> frappe._dict:
	"""What the company decided for the gaps of a payment. Everything off, tolerance 0.05, when it decided nothing."""
	settings = frappe._dict(
		automatic=0,
		partial_automatic=0,
		rounding_tolerance=0.05,
		rebate_floor=0.0,
		rebate_percent=0.0,
		rebate_cap=0.0,
		account=None,
		account_purchases=None,
	)
	if frappe.db.exists("DocType", SETTINGS) and frappe.db.exists(SETTINGS, company):
		fields = [
			"payment_gap_automatic",
			"payment_gap_partial_automatic",
			"rounding_tolerance",
			"accepted_rebate_percent",
			"accepted_rebate_cap",
			"payment_gap_account",
		]
		# the small sum and the account of the purchases are newer fields: a site whose schema has not caught up with the
		# code reads them as none
		for newer in ("accepted_rebate_floor", "payment_gap_account_purchases"):
			if frappe.db.has_column(SETTINGS, newer):
				fields.append(newer)
		row = frappe.db.get_value(SETTINGS, company, fields, as_dict=True)
		if row:
			settings.update(
				automatic=1 if row.payment_gap_automatic else 0,
				partial_automatic=1 if row.payment_gap_partial_automatic else 0,
				# an empty tolerance means 0.05, a 0 means none
				rounding_tolerance=flt(row.rounding_tolerance) if row.rounding_tolerance is not None else 0.05,
				rebate_floor=flt(row.get("accepted_rebate_floor")),
				rebate_percent=flt(row.accepted_rebate_percent),
				rebate_cap=flt(row.accepted_rebate_cap),
				account=row.payment_gap_account,
				account_purchases=row.get("payment_gap_account_purchases"),
			)
	if not settings.account:
		settings.account = frappe.get_cached_value("Company", company, "default_discount_account")
	return settings


def gap_account(settings, invoice_type: str) -> str | None:
	"""The account a gap goes to by default: a sale and a purchase have one each (an income account for what a customer
	short-pays, an expense account for what is short-paid to a supplier)."""
	return settings.account_purchases if invoice_type == "Purchase Invoice" else settings.account


def no_account_message(invoice_type: str) -> str:
	return (
		_("The company has no payment gap account on purchases.")
		if invoice_type == "Purchase Invoice"
		else _("The company has no payment gap account.")
	)


def _reference_key(value) -> str:
	return "".join(str(value or "").split()).upper()


def _is_sure(invoice, reference) -> bool:
	"""The invoice is recognised without doubt: a structured QR or creditor reference that is its own, or, for a
	purchase invoice, a line of a payment run. A name or an amount is never enough to validate a partial payment."""
	if invoice.doctype == "Sales Invoice":
		key = _reference_key(reference)
		return bool(key) and key in {_reference_key(invoice.get("esr_reference")), _reference_key(invoice.get("scor_reference"))} - {""}
	return bool(invoice.get("is_proposed"))


def _discount(invoice, on, outstanding) -> float:
	"""The early payment discount the payment terms of the invoice grant on `on` (ERPNext's own figure)."""
	try:
		from erpnextswiss.erpnextswiss.payment_terms import _discount_terms, discount_at
	except ImportError:
		return 0.0
	if not _discount_terms(invoice):
		return 0.0
	return flt(discount_at(invoice, invoice.get("party_account_currency"), on, outstanding), 2)


def judge(invoice_type: str, invoice_name: str, amount: float, on, reference: str | None = None) -> frappe._dict:
	"""What a payment of `amount` on `on` is to this invoice, and whether it may be passed by itself."""
	if invoice_type not in INVOICE_TYPES:
		frappe.throw(_("{0} is not an invoice a payment can settle.").format(_(invoice_type)))
	# read from the database: the dates of a schedule held in memory are text
	invoice = frappe.get_doc(invoice_type, invoice_name)
	settings = get_settings(invoice.company)
	receiving = invoice_type == "Sales Invoice"
	amount = flt(amount, 2)
	outstanding = flt(invoice.outstanding_amount, 2)
	gap = flt(outstanding - amount, 2)
	verdict = frappe._dict(
		kind="",
		gap=gap,
		amount=amount,
		outstanding=outstanding,
		discount=0.0,
		automatic=False,
		reason="",
		# an accepted rebate above the amount the company asks to confirm: a person confirms it (see _needs_confirmation)
		needs_confirmation=False,
		confirm_above=0.0,
		invoice_type=invoice_type,
		sure=_is_sure(invoice, reference),
		currency=invoice.currency,
		company=invoice.company,
		# the dunnings whose fee this payment pays (kind dunning_fee): [{name, amount, dunning_type, income_account, cost_center}]
		dunnings=[],
	)
	if invoice.docstatus != 1 or outstanding <= 0 or amount <= 0:
		verdict.reason = _("The invoice is not open.")
		return verdict

	if abs(gap) <= CENT:
		verdict.kind = "exact"
	else:
		discount = _discount(invoice, on, outstanding)
		if discount and abs(gap - discount) <= CENT:
			verdict.kind, verdict.discount = "early_discount", discount
		elif abs(gap) <= settings.rounding_tolerance:
			verdict.kind = "rounding"
		elif gap < 0:
			# a customer who got a dunning pays the invoice AND its fee: that surplus is the fee, not a gift
			charges = _dunning_charges(invoice, -gap) if receiving else []
			if charges:
				verdict.kind, verdict.dunnings = "dunning_fee", charges
			else:
				verdict.kind = "overpaid"
		elif receiving and _within_accepted_rebate(gap, outstanding, settings):
			verdict.kind = "accepted_rebate"
			verdict.confirm_above = settings.rebate_cap
			verdict.needs_confirmation = _needs_confirmation(gap, settings)
		else:
			verdict.kind = "partial"

	_decide_automatic(verdict, settings)
	return verdict


def _within_accepted_rebate(gap: float, outstanding: float, settings) -> bool:
	"""Whether a customer who paid `gap` less than the invoice balance is within what the company accepts.

	Two doors, and the percentage alone decides beyond the first. A small sum is always accepted, whatever the invoice
	(a few centimes on a small invoice are not refused for being more than a percent of it). Beyond it, a share of the
	balance. The amount the company asks to confirm is not a limit of what is accepted: see _needs_confirmation."""
	if settings.rebate_floor > 0 and gap <= settings.rebate_floor + 1e-9:
		return True
	return settings.rebate_percent > 0 and gap <= flt(outstanding * settings.rebate_percent / 100, 2) + 1e-9


def _needs_confirmation(gap: float, settings) -> bool:
	"""An accepted rebate larger than the amount the company names is not passed by itself, even when passing by itself is
	on: a person looks at it first. The small sum is exempt, it is accepted without a look. No amount named (0) means no
	rebate above the small sum is passed by itself: a company that fills in a percentage and nothing else is asked to
	confirm every rebate, never the other way round."""
	if settings.rebate_floor > 0 and gap <= settings.rebate_floor + 1e-9:
		return False
	return settings.rebate_cap <= 0 or gap > settings.rebate_cap + 1e-9


def _decide_automatic(verdict, settings):
	company_currency = frappe.get_cached_value("Company", verdict.company, "default_currency")
	if verdict.kind == "exact":
		verdict.automatic = True
		return
	if verdict.kind == "overpaid":
		verdict.reason = _("More came in than is owed: that is never passed by itself.")
	elif not settings.automatic:
		verdict.reason = _("The company has not switched on passing payment gaps by itself.")
	elif verdict.currency != company_currency:
		verdict.reason = _("The invoice is not in the currency of the company.")
	elif verdict.kind in ("rounding", "accepted_rebate") and not gap_account(settings, verdict.invoice_type):
		verdict.reason = no_account_message(verdict.invoice_type)
	elif verdict.kind == "early_discount" and not frappe.get_cached_value(
		"Company", verdict.company, "default_discount_account"
	):
		verdict.reason = _("The company has no early payment discount account.")
	elif verdict.kind == "dunning_fee" and (problem := _dunning_account_problem(verdict)):
		verdict.reason = problem
	elif verdict.kind == "dunning_fee" and not verdict.sure:
		# the sum is the only evidence that the surplus is the fee: a structured reference of the invoice is needed besides
		verdict.reason = _("The invoice is not recognised without doubt: a person validates a payment that includes a dunning fee.")
	elif verdict.kind == "accepted_rebate" and verdict.needs_confirmation:
		verdict.reason = (
			_("This difference is above {0}: a person confirms it.").format(fmt_money(settings.rebate_cap, currency=verdict.currency))
			if settings.rebate_cap > 0
			else _("The company has not named an amount up to which a rebate is passed by itself: a person confirms it.")
		)
	elif verdict.kind == "partial" and not settings.partial_automatic:
		verdict.reason = _("A partial payment is validated by a person.")
	elif verdict.kind == "partial" and not verdict.sure:
		verdict.reason = _("The invoice is not recognised without doubt: a person validates the partial payment.")
	else:
		verdict.automatic = True


def book(
	verdict,
	invoice_type: str,
	invoice_name: str,
	ledger_account: str,
	on,
	reference: str,
	remark: str,
	by_person: bool = False,
	account: str | None = None,
	settle_in_full: bool = False,
	deduct_from_sales: bool = False,
) -> str:
	"""The Payment Entry of a verdict, made by ERPNext's get_payment_entry and submitted. Its name.

	An automatic verdict is booked by the import, nobody in front of the screen. `by_person` stands for a person who
	looked at the verdict and decided: the switches of the company then say nothing, but what cannot be booked cleanly
	still is not (an overpayment, a gap with no account to go to).

	`account` is the account a person chose for the gap instead of the company's. `settle_in_full` is a person's choice
	for a payment that came in short beyond what the company accepts: the invoice is settled and the gap, with its VAT
	cut from the account, is passed on that account, instead of being left open on the invoice. For a payment that came
	in OVER the invoice it is the same choice the other way round: left off, the whole payment is booked and the surplus
	stays on it as an unallocated amount (the customer's, or the supplier's, to match with a next invoice); on, the surplus
	is passed on the account, with no VAT.

	`deduct_from_sales` is a person's other way to settle a short payment of a SALE: the balance is taken off the turnover,
	a debit on each sales account of the invoice and on each of its VAT accounts, in the share of the invoice that the
	balance is (see sales_deduction_rows). The accounts are the invoice's own, nobody chooses one."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	if verdict.kind == "" or not (verdict.automatic or by_person):
		frappe.throw(_("This payment is not to be passed by itself: {0}").format(verdict.reason or verdict.kind))
	if verdict.kind == "overpaid" and (problem := surplus_problem(verdict)):
		frappe.throw(problem)
	if deduct_from_sales and verdict.kind != "partial":
		frappe.throw(_("The balance of a sale is taken off the turnover only for a short payment."))
	if account:
		check_account(verdict.company, account)
	if by_person and not deduct_from_sales:
		_check_the_gap_has_an_account(verdict, account, settle_in_full)
	invoice = frappe.get_doc(invoice_type, invoice_name)
	if deduct_from_sales and (problem := deduct_problem(verdict, invoice)):
		frappe.throw(problem)
	receiving = invoice_type == "Sales Invoice"
	on = getdate(on)

	if verdict.kind in ("early_discount", "exact") or (
		verdict.kind == "partial" and not (settle_in_full or deduct_from_sales)
	):
		# ERPNext deducts the discount by itself inside the window of the payment terms: the plan says what to hand it
		# so that the entry pays exactly the sum the bank moved, with or without the discount (see payment_terms).
		from erpnextswiss.erpnextswiss.payment_terms import assert_pays_the_row, entry_plan

		plan = entry_plan(invoice, invoice.currency, verdict.amount, on)
		pe = get_payment_entry(
			invoice_type,
			invoice_name,
			party_amount=plan.party_amount,
			bank_account=ledger_account,
			reference_date=plan.reference_date,
			reference_no=reference,
		)
		assert_pays_the_row(pe, invoice, invoice.currency, verdict.amount)
	else:
		# rounding, accepted rebate: the invoice is settled in full, the bank moved less (or more), the gap is a deduction
		pe = get_payment_entry(
			invoice_type,
			invoice_name,
			party_amount=verdict.outstanding,
			bank_account=ledger_account,
			reference_date=on,
			reference_no=reference,
		)
		pe.paid_amount = pe.received_amount = verdict.amount
		# What Payment Entry wants: for a Receive, difference = allocated - received, so a shortfall is a positive
		# deduction; for a Pay, difference = paid - allocated, so the same shortfall is a negative one.
		signed = verdict.gap if receiving else -verdict.gap
		# a surplus that a person keeps has no deduction: what came in above the invoice stays on the entry, unallocated
		keeps_the_surplus = verdict.kind == "overpaid" and not settle_in_full
		if deduct_from_sales:
			rows = sales_deduction_rows(invoice, verdict.gap)
		else:
			rows = [] if keeps_the_surplus else _deductions(verdict, invoice, signed, account)
		for deduction in rows:
			pe.append("deductions", deduction)

	pe.posting_date = on
	pe.reference_date = on
	pe.reference_no = reference
	pe.remarks = remark
	pe.insert()
	pe.submit()
	return pe.name


def account_problem(verdict, account: str | None = None, settle_in_full: bool = False) -> str:
	"""Why a gap cannot be booked by a person, or an empty string: a gap goes to an account of the company, and the
	account that is missing is said instead of the entry failing on it."""
	if verdict.kind == "dunning_fee":
		# the account is the one of the dunning, nobody chooses it: what is missing is that the dunning has none
		return _dunning_account_problem(verdict)
	settings = get_settings(verdict.company)
	passes_as_deduction = verdict.kind in ("rounding", "accepted_rebate") or (
		verdict.kind in ("partial", "overpaid") and settle_in_full
	)
	if passes_as_deduction and not (account or gap_account(settings, verdict.invoice_type)):
		return no_account_message(verdict.invoice_type)
	if verdict.kind == "early_discount" and not frappe.get_cached_value(
		"Company", verdict.company, "default_discount_account"
	):
		return _("The company has no early payment discount account.")
	return ""


def deduct_problem(verdict, invoice) -> str:
	"""Why the balance of this invoice cannot be taken off the turnover, or an empty string. Only a sale, in the currency of
	the company (the rows are worked out in it), and one that has a sales account to take the balance off."""
	if invoice.doctype != "Sales Invoice":
		return _("Only the balance of a sale is taken off the turnover.")
	if verdict.currency != frappe.get_cached_value("Company", verdict.company, "default_currency"):
		return _("The invoice is not in the currency of the company: use Reconcile manually.")
	if not any(item.income_account for item in invoice.items):
		return _("The invoice has no sales account to take the balance off.")
	return ""


def sales_deduction_rows(invoice, gap: float) -> list[dict]:
	"""The balance of a sale taken off its turnover: one debit per sales account of the invoice and one per VAT account of
	it, each in the share of the invoice that the balance is (the net lines on the accounts they were sold on, the VAT as
	the invoice charged it). The cents of rounding go on the largest row, so that the rows add up to `gap` exactly and the
	invoice is settled to the cent. What is taken off the turnover also takes its VAT off, as a credit note would."""
	total = flt(invoice.grand_total, 2)
	if not total or not flt(gap):
		return []
	share = flt(gap) / total
	cost_center = frappe.get_cached_value("Company", invoice.company, "cost_center")
	description = _("Balance of {0} taken off the sales").format(invoice.name)
	nets: dict[str, float] = {}
	for item in invoice.items:
		if item.income_account:
			nets[item.income_account] = nets.get(item.income_account, 0.0) + flt(item.net_amount)
	rows = [
		{"account": account, "cost_center": cost_center, "amount": flt(net * share, 2), "description": description}
		for account, net in nets.items()
	]
	for tax in invoice.taxes:
		if flt(tax.tax_amount) and tax.account_head:
			rows.append(
				{
					"account": tax.account_head,
					"cost_center": tax.cost_center or cost_center,
					"amount": flt(flt(tax.tax_amount) * share, 2),
					"description": description,
				}
			)
	if not rows:
		return []
	largest = max(rows, key=lambda row: abs(row["amount"]))
	largest["amount"] = flt(largest["amount"] + flt(gap) - sum(row["amount"] for row in rows), 2)
	return [row for row in rows if row["amount"]]


def surplus_problem(verdict) -> str:
	"""Why a person cannot decide the surplus of an overpaid line here, or an empty string. The entry that keeps a surplus
	open, or passes it, is made in the currency of the company only (the figures of a foreign currency are the payment
	window's): the line is left to it."""
	if verdict.currency != frappe.get_cached_value("Company", verdict.company, "default_currency"):
		return _("The invoice is not in the currency of the company: use Reconcile manually.")
	return ""


def _check_the_gap_has_an_account(verdict, account=None, settle_in_full=False):
	problem = account_problem(verdict, account, settle_in_full)
	if problem:
		frappe.throw(problem)


def check_account(company: str, account: str):
	"""The account a person chose for a gap: an income or expense account of this company that can be posted to."""
	row = frappe.db.get_value(
		"Account", account, ["company", "is_group", "disabled", "root_type", "account_type"], as_dict=True
	)
	if not row or row.company != company:
		frappe.throw(_("Account {0} does not belong to company {1}").format(account, company))
	if row.is_group or row.disabled:
		frappe.throw(_("Account {0} cannot be posted to.").format(account))
	if row.root_type not in ("Income", "Expense") or row.account_type in ("Receivable", "Payable", "Bank", "Cash"):
		frappe.throw(_("A difference goes to an income or expense account, not {0}.").format(account))


def preview(
	verdict, invoice, account: str | None = None, settle_in_full: bool = False, deduct_from_sales: bool = False
) -> list[dict]:
	"""The rows that the gap will be booked as, VAT included, the way the entry will carry them (nothing is written)."""
	if deduct_from_sales:
		return sales_deduction_rows(invoice, verdict.gap)
	receiving = invoice.doctype == "Sales Invoice"
	signed = verdict.gap if receiving else -verdict.gap
	if verdict.kind == "dunning_fee":
		return _dunning_deductions(verdict)
	if verdict.kind == "early_discount":
		return [
			{
				"account": frappe.get_cached_value("Company", verdict.company, "default_discount_account"),
				"amount": signed,
				"description": _("Payment gap of {0}").format(invoice.name),
			}
		]
	if verdict.kind in ("rounding", "accepted_rebate") or (verdict.kind in ("partial", "overpaid") and settle_in_full):
		return _deductions(verdict, invoice, signed, account)
	return []


def _deductions(verdict, invoice, signed, account: str | None = None) -> list[dict]:
	if verdict.kind == "dunning_fee":
		return _dunning_deductions(verdict)
	settings = get_settings(verdict.company)
	deduction = {
		"account": account or gap_account(settings, invoice.doctype),
		"cost_center": frappe.get_cached_value("Company", verdict.company, "cost_center"),
		"amount": signed,
		"description": _("Payment gap of {0}").format(invoice.name),
	}
	if verdict.kind in ("rounding", "overpaid"):
		# a rounding of a few centimes carries no VAT line; nor does a surplus passed as a difference, which pays for no supply
		# (the fee of a dunning is the same)
		return [deduction]
	# The VAT is cut from the account, as the reconciliation screen does, but an invoice that carries no VAT gets none.
	from mint.apis.bank_reconciliation import calculate_deductions_with_vat

	has_tax = bool(flt(invoice.get("total_taxes_and_charges")))
	return calculate_deductions_with_vat([deduction], verdict.company, False, not has_tax)["deductions"]


def _dunning_charges(invoice, surplus: float) -> list[frappe._dict]:
	"""The validated dunnings of this invoice whose fee and interest are still owed, when they are what came in above it.

	A customer who was sent a dunning pays the invoice and the fee in one transfer. The surplus is that fee when it is,
	to the cent, what ONE dunning still asks for (the latest first: the customer pays the last notice) or what ALL of
	them ask for together; anything else is an overpayment that a person looks at. A sum in a foreign currency is never
	matched: a dunning is raised in the currency of its invoice but its fee is booked in the company's."""
	if invoice.currency != frappe.get_cached_value("Company", invoice.company, "default_currency"):
		return []
	names = frappe.get_all("Overdue Payment", filters={"sales_invoice": invoice.name, "docstatus": 1}, pluck="parent", distinct=True)
	if not names:
		return []
	owed = []
	for row in frappe.get_all(
		"Dunning",
		filters={
			"name": ("in", names),
			"docstatus": 1,
			"customer": invoice.customer,
			"company": invoice.company,
			"status": "Unresolved",
		},
		fields=["name"],
		order_by="posting_date desc, creation desc",
	):
		dunning = frappe.get_doc("Dunning", row.name)
		# ERPNext's own figure: what is left of the fee and interest once the payments that carry them are taken off, and 0
		# when a later notice that covers this one is settled
		amount = flt(dunning.get_unpaid_base_dunning_amount(), 2)
		if amount > 0:
			owed.append(
				frappe._dict(
					name=dunning.name,
					amount=amount,
					dunning_type=dunning.dunning_type,
					income_account=dunning.income_account,
					cost_center=dunning.cost_center,
				)
			)
	for charge in owed:
		if abs(charge.amount - surplus) <= CENT:
			return [charge]
	if len(owed) > 1 and abs(sum(charge.amount for charge in owed) - surplus) <= CENT:
		return owed
	return []


def _dunning_account_problem(verdict) -> str:
	"""A dunning whose fee has no account to be booked on, or an empty string. The account of a dunning is the one of its
	Dunning Type (the dunnings raised before the type had one have none): it is said where to set it."""
	for charge in verdict.dunnings:
		if not charge.income_account:
			return _("The dunning {0} has no Income Account to book its fee on: set it on the Dunning Type {1}.").format(
				charge.name, charge.dunning_type
			)
	return ""


def _dunning_deductions(verdict) -> list[dict]:
	"""One negative deduction per dunning, the way ERPNext makes the payment of a dunning itself (`get_payment_entry`): on
	the account of the dunning, linked to it. That link is what tells ERPNext the fee is paid, so that the dunning is
	resolved with its invoice (`update_dunnings_linked_to_payment`); a surplus passed on a plain account would leave the
	dunning « Unresolved » for ever. A fee is not subject to VAT, so there is none to cut."""
	rows = [
		{
			"account": charge.income_account,
			"cost_center": charge.cost_center or frappe.get_cached_value("Company", verdict.company, "cost_center"),
			"amount": -flt(charge.amount, 2),
			"description": _("Interest and/or dunning fee"),
			"dunning": charge.name,
		}
		for charge in verdict.dunnings
	]
	# the few centimes between what came in and what the dunnings ask (the match allows one cent) go on the last row, so
	# that the entry has no difference left
	rows[-1]["amount"] = flt(rows[-1]["amount"] + verdict.gap - sum(row["amount"] for row in rows), 2)
	return rows
