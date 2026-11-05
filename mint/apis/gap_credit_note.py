# //// Neoffice — added file (no upstream equivalent).
# ////
# //// THE CREDIT NOTE OF A BALANCE: WHEN A CUSTOMER ALWAYS PAYS A SHARE OF WHAT IS ASKED.
# ////
# //// Some customers settle a fixed share of every invoice (an architect who pays 80 %) and the office issues a credit
# //// note for the rest each time. A payment that came in short beyond what the company accepts as a gap can then be
# //// closed the way the office closes it: the payment is booked for what came in, a credit note is made for the
# //// balance, and the engine of ERPNext settles the invoice with it. Nothing here invents a habit: the item, the
# //// account and the VAT template of the credit note are those of the credit notes the customer already has, the
# //// company's gap account when it has none, and the proposal "this customer's payments are at this share and the
# //// rest ended as a credit note" is read from the customer's own invoices.
# ////
# //// The credit note has NO link to the invoice (return_against stays empty): that is how the offices here make them,
# //// and the engine settles it by the party's ledger, not by that link. It is for sales only: a supplier's credit
# //// note is the supplier's to issue.

import frappe
from frappe import _
from frappe.utils import flt, getdate

# Two shares are "the same" within two points of a percent: an invoice of 6'428.20 paid 80 % is 5'142.56.
SAME_SHARE = 0.02
# What a customer's habit is read from: its latest invoices that were paid in part or in whole.
HISTORY = 10
# A habit is a habit from the second time.
AT_LEAST = 2


def _company_currency(company: str) -> str:
	return frappe.get_cached_value("Company", company, "default_currency")


def defaults(company: str, customer: str) -> frappe._dict:
	"""What the credit note of this customer is made of: what its latest credit notes were made of (the item, the
	account, the VAT template, the one used most often), else the company's gap account and no item."""
	from mint.apis import payment_gap

	row = frappe.db.sql(
		"""
		select it.item_code, it.item_name, it.income_account, it.item_tax_template, si.taxes_and_charges,
			count(*) as times, max(si.posting_date) as last_day
		from `tabSales Invoice Item` it
		join `tabSales Invoice` si on si.name = it.parent
		where si.is_return = 1 and si.docstatus = 1 and si.company = %(company)s and si.customer = %(customer)s
			and ifnull(it.income_account, '') != ''
		group by it.item_code, it.item_name, it.income_account, it.item_tax_template, si.taxes_and_charges
		order by times desc, last_day desc
		limit 1
		""",
		{"company": company, "customer": customer},
		as_dict=True,
	)
	if row:
		row = row[0]
		return frappe._dict(
			item_code=row.item_code,
			item_name=row.item_name or row.item_code,
			account=row.income_account,
			tax_template=row.taxes_and_charges,
			# the VAT of a Swiss invoice is the rate of the line, which ERPNext derives from the item tax template of the
			# line; the template of the document only lists the accounts. Both are those of the customer's credit note.
			item_tax_template=row.get("item_tax_template"),
			times=row.times,
			source="history",
		)
	return frappe._dict(
		item_code=None,
		item_name=_("Credit note of the balance"),
		account=payment_gap.get_settings(company).account,
		tax_template=None,
		item_tax_template=None,
		times=0,
		source="company",
	)


def problem(company: str, account: str | None) -> str:
	"""Why this account cannot take a credit note, or an empty string: it is an income account of the company."""
	if not account:
		return _("The company has no payment gap account.")
	row = frappe.db.get_value("Account", account, ["company", "is_group", "disabled", "root_type"], as_dict=True)
	if not row or row.company != company:
		return _("Account {0} does not belong to company {1}").format(account, company)
	if row.is_group or row.disabled:
		return _("Account {0} cannot be posted to.").format(account)
	if row.root_type != "Income":
		return _("A credit note goes to an income account, not {0}.").format(account)
	return ""


def _document(company: str, customer: str, on, rate: float, d: frappe._dict, account: str):
	"""The credit note in memory, for ONE unit of the balance at `rate` (what is asked is `rate`, VAT included when its
	template says so). Saved by create(), only measured by preview()."""
	doc = frappe.new_doc("Sales Invoice")
	doc.update(
		{
			"company": company,
			"customer": customer,
			"posting_date": getdate(on),
			"set_posting_time": 1,
			"is_return": 1,
			"update_stock": 0,
			"currency": _company_currency(company),
			"conversion_rate": 1,
			"taxes_and_charges": d.tax_template,
		}
	)
	doc.append(
		"items",
		{
			"item_code": d.item_code,
			"item_name": d.item_name,
			"description": d.item_name,
			"qty": -1,
			"rate": rate,
			"uom": frappe.db.get_value("Item", d.item_code, "stock_uom") if d.item_code else _default_uom(),
			"income_account": account,
			"cost_center": frappe.get_cached_value("Company", company, "cost_center"),
			"item_tax_template": d.get("item_tax_template"),
		},
	)
	if d.tax_template:
		doc.set_taxes()
	doc.calculate_taxes_and_totals()
	return doc


def _default_uom() -> str:
	return frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"


def _measured(company: str, customer: str, on, gross: float, d: frappe._dict, account: str):
	"""The document whose grand total is the balance: the rate is brought to it, whatever the VAT template is
	(included in the price or added to it), and the result is refused if it cannot be brought to the cent."""
	gross = flt(gross, 2)
	rate = gross
	for _pass in range(3):
		doc = _document(company, customer, on, rate, d, account)
		total = abs(flt(doc.grand_total, 2))
		if abs(total - gross) <= 0.005:
			return doc
		if not total:
			break
		rate = flt(rate * gross / total, 4)
	frappe.throw(_("The credit note cannot be brought to {0}.").format(gross))


def preview(company: str, customer: str, on, gross: float, account: str | None = None) -> dict:
	"""What the credit note of the balance would be, measured, nothing written."""
	d = defaults(company, customer)
	chosen = account or d.account
	blocker = problem(company, chosen)
	out = {
		"item": d.item_name,
		"item_code": d.item_code,
		"default_account": d.account,
		"account": chosen,
		"tax_template": d.tax_template,
		"times": d.times,
		"source": d.source,
		"blocker": blocker,
		"net": None,
		"tax": None,
		"total": flt(gross, 2),
	}
	if not blocker:
		doc = _measured(company, customer, on, gross, d, chosen)
		out["net"] = abs(flt(doc.net_total, 2))
		out["tax"] = abs(flt(doc.total_taxes_and_charges, 2))
	return out


def create(company: str, customer: str, on, gross: float, account: str | None, remark: str) -> str:
	"""The credit note of the balance, made and submitted. Its name."""
	frappe.has_permission("Sales Invoice", ptype="create", throw=True)
	d = defaults(company, customer)
	chosen = account or d.account
	blocker = problem(company, chosen)
	if blocker:
		frappe.throw(blocker)
	doc = _measured(company, customer, on, gross, d, chosen)
	doc.remarks = remark
	doc.insert()
	doc.submit()
	return doc.name


def settle(company: str, customer: str, invoice: str, credit_note: str, amount: float):
	"""The credit note settles the balance of the invoice, with the engine of ERPNext (the one of the reconciliation
	screen of a party): the same rows, the same checks, the same entry."""
	from mint.apis.party_reconciliation import _allocate

	frappe.has_permission("Payment Reconciliation", ptype="write", throw=True)
	doc, _chosen = _allocate(
		company,
		"Customer",
		customer,
		None,
		[{"invoice_type": "Sales Invoice", "invoice_number": invoice, "amount": flt(amount, 2)}],
		[{"reference_type": "Sales Invoice", "reference_name": credit_note, "amount": flt(amount, 2)}],
	)
	doc.reconcile()


def history(company: str, customer: str, invoice: str, share: float) -> dict:
	"""What this customer's own invoices say about a payment at this share: how many of its latest paid invoices were
	paid at the same share, and how many of those had the rest closed by something else than a payment (a credit note)."""
	rows = frappe.db.sql(
		f"""
		select si.name, si.grand_total, si.outstanding_amount, paid.amount as paid
		from `tabSales Invoice` si
		join (
			select per.reference_name as invoice, sum(per.allocated_amount) as amount
			from `tabPayment Entry Reference` per
			join `tabPayment Entry` pe on pe.name = per.parent and pe.docstatus = 1 and pe.payment_type = 'Receive'
			where per.reference_doctype = 'Sales Invoice'
			group by per.reference_name
		) paid on paid.invoice = si.name
		where si.docstatus = 1 and si.is_return = 0 and si.company = %(company)s and si.customer = %(customer)s
			and si.grand_total > 0 and si.name != %(invoice)s
		order by si.posting_date desc, si.creation desc
		limit {int(HISTORY)}
		""",
		{"company": company, "customer": customer, "invoice": invoice},
		as_dict=True,
	)
	same = [r for r in rows if abs(flt(r.paid) / flt(r.grand_total) - share) <= SAME_SHARE]
	# closed by something else than a payment: nothing left to pay, and the payments are less than the invoice
	closed = [r for r in same if abs(flt(r.outstanding_amount)) <= 0.01 and flt(r.paid) < flt(r.grand_total) - 0.01]
	return {
		"considered": len(rows),
		"same_share": len(same),
		"closed_by_credit": len(closed),
		"share": flt(share * 100, 1),
		"proposal": "credit_note" if len(same) >= AT_LEAST and len(closed) >= AT_LEAST else None,
	}
