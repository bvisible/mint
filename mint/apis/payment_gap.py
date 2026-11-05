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
# ////   accepted_rebate  sales only: less than owed, within the company's percentage AND its cap
# ////   partial          less than owed beyond that: the money has come in, it is recorded, the rest stays open
# ////   overpaid         more than owed: never passed by itself
# //// A verdict says whether it may be passed AUTOMATICALLY (nobody in front of the screen) and, when it may not,
# //// why. Nothing is automatic until the company switches it on (Neoffice Company Settings, « Payment Gaps »);
# //// a partial payment is validated by itself only when the invoice is recognised without doubt.
# //// The entry is made by ERPNext's own get_payment_entry; only the deduction of a rounding or of a rebate is
# //// added to it, with its VAT cut from the account as the reconciliation screen does.

import frappe
from frappe import _
from frappe.utils import flt, getdate

CENT = 0.01
SETTINGS = "Neoffice Company Settings"
INVOICE_TYPES = ("Sales Invoice", "Purchase Invoice")


def get_settings(company: str) -> frappe._dict:
	"""What the company decided for the gaps of a payment. Everything off, tolerance 0.05, when it decided nothing."""
	settings = frappe._dict(
		automatic=0, partial_automatic=0, rounding_tolerance=0.05, rebate_percent=0.0, rebate_cap=0.0, account=None
	)
	if frappe.db.exists("DocType", SETTINGS) and frappe.db.exists(SETTINGS, company):
		row = frappe.db.get_value(
			SETTINGS,
			company,
			[
				"payment_gap_automatic",
				"payment_gap_partial_automatic",
				"rounding_tolerance",
				"accepted_rebate_percent",
				"accepted_rebate_cap",
				"payment_gap_account",
			],
			as_dict=True,
		)
		if row:
			settings.update(
				automatic=1 if row.payment_gap_automatic else 0,
				partial_automatic=1 if row.payment_gap_partial_automatic else 0,
				# an empty tolerance means 0.05, a 0 means none
				rounding_tolerance=flt(row.rounding_tolerance) if row.rounding_tolerance is not None else 0.05,
				rebate_percent=flt(row.accepted_rebate_percent),
				rebate_cap=flt(row.accepted_rebate_cap),
				account=row.payment_gap_account,
			)
	if not settings.account:
		settings.account = frappe.get_cached_value("Company", company, "default_discount_account")
	return settings


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
		sure=_is_sure(invoice, reference),
		currency=invoice.currency,
		company=invoice.company,
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
			verdict.kind = "overpaid"
		elif (
			receiving
			and settings.rebate_percent > 0
			and settings.rebate_cap > 0
			and gap <= flt(outstanding * settings.rebate_percent / 100, 2) + 1e-9
			and gap <= settings.rebate_cap + 1e-9
		):
			verdict.kind = "accepted_rebate"
		else:
			verdict.kind = "partial"

	_decide_automatic(verdict, settings)
	return verdict


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
	elif verdict.kind in ("rounding", "accepted_rebate") and not settings.account:
		verdict.reason = _("The company has no payment gap account.")
	elif verdict.kind == "early_discount" and not frappe.get_cached_value(
		"Company", verdict.company, "default_discount_account"
	):
		verdict.reason = _("The company has no early payment discount account.")
	elif verdict.kind == "partial" and not settings.partial_automatic:
		verdict.reason = _("A partial payment is validated by a person.")
	elif verdict.kind == "partial" and not verdict.sure:
		verdict.reason = _("The invoice is not recognised without doubt: a person validates the partial payment.")
	else:
		verdict.automatic = True


def book(verdict, invoice_type: str, invoice_name: str, ledger_account: str, on, reference: str, remark: str) -> str:
	"""The Payment Entry of an automatic verdict, made by ERPNext's get_payment_entry and submitted. Its name."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	if not verdict.automatic or verdict.kind in ("", "overpaid"):
		frappe.throw(_("This payment is not to be passed by itself: {0}").format(verdict.reason or verdict.kind))
	invoice = frappe.get_doc(invoice_type, invoice_name)
	receiving = invoice_type == "Sales Invoice"
	on = getdate(on)

	if verdict.kind in ("early_discount", "partial", "exact"):
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
		for deduction in _deductions(verdict, invoice, signed):
			pe.append("deductions", deduction)

	pe.posting_date = on
	pe.reference_date = on
	pe.reference_no = reference
	pe.remarks = remark
	pe.insert()
	pe.submit()
	return pe.name


def _deductions(verdict, invoice, signed) -> list[dict]:
	settings = get_settings(verdict.company)
	deduction = {
		"account": settings.account,
		"cost_center": frappe.get_cached_value("Company", verdict.company, "cost_center"),
		"amount": signed,
		"description": _("Payment gap of {0}").format(invoice.name),
	}
	if verdict.kind != "accepted_rebate":
		# a rounding of a few centimes carries no VAT line
		return [deduction]
	# The VAT is cut from the account, as the reconciliation screen does, but an invoice that carries no VAT gets none.
	from mint.apis.bank_reconciliation import calculate_deductions_with_vat

	has_tax = bool(flt(invoice.get("total_taxes_and_charges")))
	return calculate_deductions_with_vat([deduction], verdict.company, False, not has_tax)["deductions"]
