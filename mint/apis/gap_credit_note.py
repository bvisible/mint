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
# //// The credit note is DRAWN FROM THE INVOICE (12.11, Jérémy: « une note de crédit est une déduction du chiffre
# //// d'affaires, sur le 3200 ou le 3400, liée à sa facture »): it is the return of the invoice (return_against), on the
# //// sales accounts and with the VAT of the invoice itself, each line at the share of the invoice that the balance is.
# //// It used to be one line on the customer's habit or on the gap account of the company, without link (the 3295 « loss
# //// on customers »: a write-off, which the other choice of the card still is). The engine settles it against the
# //// invoice by the party's ledger, as before. It is for sales only: a supplier's credit note is the supplier's to issue.

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
			# the credit note settles exactly the balance: a total rounded to five centimes would leave a few cents open on it
			"disable_rounded_total": 1,
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


def _returned(invoice: str, on, factor: float, account: str | None, nudge: float = 0.0):
	"""ERPNext's own return of the invoice (linked to it, with its items, its sales accounts and its taxes), every line
	brought to `factor` of the invoice, and nothing else done to it: not validated, so that saving it validates it once.
	`nudge` is a few cents added to the rate of the largest line, to bring the total to the cent."""
	from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

	doc = make_sales_return(invoice)
	doc.update(
		{
			"posting_date": getdate(on),
			"set_posting_time": 1,
			"update_stock": 0,
			# the credit note settles exactly the balance: a total rounded to five centimes would leave a few cents open on it
			"disable_rounded_total": 1,
			"ignore_pricing_rule": 1,
		}
	)
	for item in doc.items:
		if account:
			item.income_account = account
		# the rate is the one to bring: nothing may recompute it from a price list or a discount of the invoice
		rate = flt(item.rate)
		item.price_list_rate = 0
		item.discount_percentage = 0
		item.discount_amount = 0
		item.rate = flt(rate * factor, 6)
	if nudge and doc.items:
		largest = max(doc.items, key=lambda item: abs(flt(item.rate) * flt(item.qty)))
		largest.rate = flt(flt(largest.rate) + nudge / (abs(flt(largest.qty)) or 1), 6)
	return doc


def _as_saving_will(doc):
	"""What saving does to the figures of the document, once: `before_validate` (where ERPNext shares a fixed charge of the
	invoice out in the proportion of the return) and `validate`. Only on a copy that is thrown away."""
	doc.run_method("before_validate")
	doc.run_method("validate")


def _from_invoice(invoice: str, on, gross: float, account: str | None = None):
	"""The credit note of the balance drawn from its invoice and not yet saved: the return of the invoice, every line at the
	share of the invoice that the balance is, the share brought (by validating a fresh copy, as saving will) until the grand
	total is the balance to the cent. `account`, when given (the rule of a customer, a person), replaces the sales accounts
	of the lines. No stock moves: goods that come back are the person's own credit note.

	A copy is validated once and thrown away: validating twice would take a fixed charge of the invoice (an `Actual` tax
	row, which ERPNext shares out in the proportion of the return) off twice. What is returned is a fresh copy at the
	share that was found, for saving to validate."""
	gross = flt(gross, 2)
	source = frappe.db.get_value("Sales Invoice", invoice, ["docstatus", "is_return", "grand_total"], as_dict=True)
	if not source or source.docstatus != 1 or source.is_return or not flt(source.grand_total):
		frappe.throw(_("The credit note of the balance is drawn from an invoice that is submitted and not a return."))
	factor = gross / flt(source.grand_total)
	nudge = 0.0
	for _pass in range(8):
		probe = _returned(invoice, on, factor, account, nudge)
		_as_saving_will(probe)
		total = abs(flt(probe.grand_total, 2))
		difference = flt(gross - total, 2)
		if abs(difference) <= 0.005:
			return _returned(invoice, on, factor, account, nudge)
		if not total:
			break
		if abs(difference) > 0.5:
			# far: bring every line along
			factor = factor * gross / total
		else:
			# near: the cents that are missing go on the largest line
			nudge += difference
	frappe.throw(_("The credit note cannot be brought to {0}.").format(gross))


def _preview_from_invoice(company: str, invoice: str, on, gross: float, account: str | None) -> dict:
	blocker = problem(company, account) if account else ""
	out = {
		"item": None,
		"item_code": None,
		"default_account": None,
		"account": account,
		"tax_template": None,
		"times": 0,
		"source": "invoice",
		"linked_to": invoice,
		"accounts": [],
		"blocker": blocker,
		"net": None,
		"tax": None,
		"total": flt(gross, 2),
	}
	if blocker:
		return out
	try:
		doc = _from_invoice(invoice, on, gross, account)
		# measured as saving will: validated once, and this copy is only for the figures
		_as_saving_will(doc)
	except frappe.ValidationError as error:
		frappe.clear_last_message()
		out["blocker"] = str(error)
		return out
	out["net"] = abs(flt(doc.net_total, 2))
	out["tax"] = abs(flt(doc.total_taxes_and_charges, 2))
	nets: dict[str, float] = {}
	for item in doc.items:
		nets[item.income_account] = nets.get(item.income_account, 0.0) + abs(flt(item.net_amount))
	out["accounts"] = [{"account": name, "net": flt(net, 2)} for name, net in nets.items()]
	return out


def preview(company: str, customer: str, on, gross: float, account: str | None = None, invoice: str | None = None) -> dict:
	"""What the credit note of the balance would be, measured, nothing written. Drawn from `invoice` when it is given (the
	way the card and the import make it); else from the customer's habit, as it was made before."""
	if invoice:
		return _preview_from_invoice(company, invoice, on, gross, account)
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


def _built(company: str, customer: str, on, gross: float, account: str | None, remark: str, invoice: str | None = None):
	"""The credit note of the balance, measured and not yet saved (what create() and prepare() both start from)."""
	frappe.has_permission("Sales Invoice", ptype="create", throw=True)
	if invoice:
		blocker = problem(company, account) if account else ""
		if blocker:
			frappe.throw(blocker)
		doc = _from_invoice(invoice, on, gross, account)
		doc.remarks = remark
		return doc
	d = defaults(company, customer)
	chosen = account or d.account
	blocker = problem(company, chosen)
	if blocker:
		frappe.throw(blocker)
	doc = _measured(company, customer, on, gross, d, chosen)
	doc.remarks = remark
	return doc


def prepare(company: str, customer: str, on, gross: float, account: str | None, remark: str, invoice: str | None = None) -> str:
	"""The credit note of the balance saved as a DRAFT: nothing is booked, a person opens it, corrects it if needed, and
	validates it from the card of the gap (create() then submits this very draft)."""
	doc = _built(company, customer, on, gross, account, remark, invoice)
	doc.insert()
	return doc.name


def _submitted_draft(company: str, customer: str, gross: float, draft: str, remark: str) -> str | None:
	"""Submit the draft prepared earlier when it is still the credit note of this balance; a draft made for another
	amount or another customer is out of date: it is removed (it is the draft this flow prepared, never a document of
	somebody else's work, and nothing was ever booked on it) and None is returned."""
	row = frappe.db.get_value(
		"Sales Invoice", draft, ["docstatus", "customer", "company", "is_return", "grand_total"], as_dict=True
	)
	if not row or row.docstatus != 0 or not row.is_return:
		return None
	if row.customer == customer and row.company == company and abs(abs(flt(row.grand_total, 2)) - flt(gross, 2)) <= 0.005:
		doc = frappe.get_doc("Sales Invoice", draft)
		doc.remarks = remark
		doc.submit()
		return doc.name
	# the line of the import that points at it lets go first: a document that is linked cannot be deleted
	for row in frappe.get_all("Mint Bank Statement Import Transactions", filters={"credit_note": draft}, pluck="name"):
		frappe.db.set_value("Mint Bank Statement Import Transactions", row, "credit_note", None, update_modified=False)
	frappe.delete_doc("Sales Invoice", draft, ignore_permissions=True)
	return None


def create(
	company: str,
	customer: str,
	on,
	gross: float,
	account: str | None,
	remark: str,
	draft: str | None = None,
	invoice: str | None = None,
) -> str:
	"""The credit note of the balance, made and submitted: the draft prepared earlier when there is one and it is still
	right, else a new one. Its name."""
	frappe.has_permission("Sales Invoice", ptype="create", throw=True)
	if draft:
		name = _submitted_draft(company, customer, gross, draft, remark)
		if name:
			return name
	doc = _built(company, customer, on, gross, account, remark, invoice)
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


def share_paid(invoice: str, amount: float) -> float:
	"""The share of the invoice the customer will have paid once this payment is booked: what already settled the invoice
	(a payment, a journal entry: its total less what is still owed) plus this payment, over its total. Called BEFORE the
	payment is booked. The payment that completes an advance is thus not mistaken for a short one (30 % where the
	customer has paid 80 % in all), and the rule of a customer compares like with like."""
	row = frappe.db.get_value("Sales Invoice", invoice, ["grand_total", "outstanding_amount"], as_dict=True)
	total = flt(row.grand_total) if row else 0
	if not total:
		return 0
	return (total - flt(row.outstanding_amount) + flt(amount)) / total


def _paid_invoices(company: str, customer: str, exclude: str = "") -> list:
	"""The latest invoices of the customer that received a payment, with what was paid on each (payment entries)."""
	return frappe.db.sql(
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
		{"company": company, "customer": customer, "invoice": exclude},
		as_dict=True,
	)


def history(company: str, customer: str, invoice: str, share: float) -> dict:
	"""What this customer's own invoices say about a payment at this share: how many of its latest paid invoices were
	paid at the same share, and how many of those had the rest closed by something else than a payment (a credit note)."""
	rows = _paid_invoices(company, customer, invoice)
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


def usual_share(company: str, customer: str) -> float | None:
	"""The share of its invoices this customer usually pays, as a fraction: the one that most of its latest paid invoices
	are within two points of, among those paid in part. None when none of them was paid in part (or none was paid)."""
	shares = [flt(r.paid) / flt(r.grand_total) for r in _paid_invoices(company, customer)]
	# an invoice paid in full says nothing about a customer who pays less
	shares = [share for share in shares if share < 0.995]
	if not shares:
		return None
	return max(shares, key=lambda share: sum(abs(share - other) <= SAME_SHARE for other in shares))
