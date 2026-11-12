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
# //// The credit note is ONE LINE (12.11, Jérémy): the article the person chooses for it (a loss on customers, a discount, the
# //// article of a customer's habit), on the account that article is sold on, with the VAT of the sale it settles, and it is
# //// settled against the invoice by the party's ledger. It is not drawn from the invoice, line by line: a credit note that
# //// returns goods, with the stock moves and its link to the invoice, is made by hand, and the card then leaves the balance to
# //// pay (the credit note is matched afterwards). It is for sales only: a supplier's credit note is the supplier's to issue.

import frappe
from frappe import _
from frappe.utils import add_years, flt, getdate, nowdate

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
			# the unit is the stock unit of the article: saving fills this in, the measure (validated before it) needs it now
			"conversion_factor": 1,
			"income_account": account,
			"cost_center": frappe.get_cached_value("Company", company, "cost_center"),
			"item_tax_template": d.get("item_tax_template"),
		},
	)
	if d.get("no_surcharge"):
		_without_surcharges(doc)
	if d.tax_template:
		doc.set_taxes()
	doc.calculate_taxes_and_totals()
	return doc


def _invoice_charged_a_surcharge(invoice: str | None) -> bool:
	"""Did the sale the balance is of carry a fixed charge that the theme adds to the net total of a sales document (the RPLP)?
	A site without the theme has no such rows, and a balance with no invoice in hand has none to take back."""
	if not invoice or not frappe.db.has_column("Sales Taxes and Charges", "neo_surcharge_type"):
		return False
	return bool(
		frappe.db.exists(
			"Sales Taxes and Charges",
			{"parent": invoice, "parenttype": "Sales Invoice", "neo_surcharge_type": ["is", "set"]},
		)
	)


def _without_surcharges(doc) -> None:
	"""Switch off, on this document, the fixed charges the theme adds to the net total of a sales document. A credit note of the
	balance gives back what the sale charged and not more: an article that carries the RPLP would otherwise add one to a note
	that settles an invoice which had none. The switches are the theme's own (one per charge); a site without them is untouched."""
	for slot in (1, 2, 3):
		field = f"neo_surcharge_{slot}_apply"
		if doc.meta.has_field(field):
			doc.set(field, 0)


def _default_uom() -> str:
	return frappe.db.get_single_value("Stock Settings", "stock_uom") or "Nos"


def _as_saving_will(doc):
	"""What saving does to the figures of the document: `before_validate` (where the theme adds a fixed charge of an article, the
	RPLP, on the net total) and `validate`. Only on a copy that is thrown away: a second validation would add the charge again."""
	doc.run_method("before_validate")
	doc.run_method("validate")


def _measured(company: str, customer: str, on, gross: float, d: frappe._dict, account: str):
	"""The document whose grand total is the balance, as saving will make it (the charges that a hook adds are in it): the rate
	is brought to it, whatever the VAT template is (included in the price or added to it), and the result is refused if it cannot
	be brought to the cent. A rate is kept to the cent and a charge is rounded on its own, so the balance may fall between two
	rates: the rates next to the one found are tried before refusing."""
	gross = flt(gross, 2)

	def total_of(rate: float) -> float:
		probe = _document(company, customer, on, rate, d, account)
		_as_saving_will(probe)
		return abs(flt(probe.grand_total, 2))

	rate = gross
	for _pass in range(3):
		total = total_of(rate)
		if abs(total - gross) <= 0.005:
			return _document(company, customer, on, rate, d, account)
		if not total:
			break
		rate = flt(rate * gross / total, 2)
	for cents in (1, -1, 2, -2, 3, -3):
		near = flt(rate + cents / 100, 2)
		if abs(total_of(near) - gross) <= 0.005:
			return _document(company, customer, on, near, d, account)
	frappe.throw(_("The credit note cannot be brought to {0}.").format(gross))


def article_problem(item_code: str) -> str:
	"""Why this article cannot be the line of a credit note, or an empty string: it exists and it is sold."""
	row = frappe.db.get_value("Item", item_code, ["disabled", "is_sales_item"], as_dict=True)
	if not row:
		return _("Article {0} does not exist.").format(item_code)
	if row.disabled or not row.is_sales_item:
		return _("Article {0} cannot be sold.").format(item_code)
	return ""


def _sold_on(item, company: str) -> str | None:
	"""The income account an article is sold on in this company: its own default, else its item group's, else the company's."""
	rows = list(item.get("item_defaults") or [])
	if item.item_group:
		rows += frappe.get_cached_doc("Item Group", item.item_group).get("item_group_defaults") or []
	for row in rows:
		if row.company == company and row.get("income_account"):
			return row.income_account
	return frappe.get_cached_value("Company", company, "default_income_account")


def _vat_of(item, company: str, invoice: str | None) -> str | None:
	"""The item tax template that gives the line its VAT rate (the rate of a Swiss line comes from it, the template of the
	document only lists the accounts): the article's own for this company, else the one of the largest line of the invoice
	the balance is of, so that the credit note takes back the VAT the sale charged."""
	for row in item.get("taxes") or []:
		if row.item_tax_template and frappe.db.get_value(
			"Item Tax Template", row.item_tax_template, ["company", "disabled"]
		) == (company, 0):
			return row.item_tax_template
	if invoice:
		found = frappe.db.sql(
			"""
			select item_tax_template from `tabSales Invoice Item`
			where parent = %s and ifnull(item_tax_template, '') != ''
			order by abs(net_amount) desc limit 1
			""",
			(invoice,),
		)
		return found[0][0] if found else None
	return None


def with_article(company: str, d: frappe._dict, item_code: str, invoice: str | None) -> frappe._dict:
	"""`d` with the article the person chose: its name, the account it is sold on and the VAT of the sale the balance is of."""
	item = frappe.get_cached_doc("Item", item_code)
	return frappe._dict(
		item_code=item.name,
		item_name=item.item_name or item.name,
		account=_sold_on(item, company) or d.account,
		tax_template=(frappe.db.get_value("Sales Invoice", invoice, "taxes_and_charges") if invoice else None) or d.tax_template,
		item_tax_template=_vat_of(item, company, invoice) or d.item_tax_template,
		times=0,
		source="article",
	)


def usual_article(company: str) -> str | None:
	"""The article the credit notes of the company were most often made on over its latest year, among the articles that are still
	sold: what a customer with no habit of its own is proposed, so that a person finds the card filled in."""
	rows = frappe.db.sql(
		"""
		select line.item_code, count(*) as times
		from `tabSales Invoice Item` line
		join `tabSales Invoice` si on si.name = line.parent
		join `tabItem` article on article.name = line.item_code
		where si.is_return = 1 and si.docstatus = 1 and si.company = %(company)s and si.posting_date >= %(since)s
			and article.disabled = 0 and article.is_sales_item = 1
		group by line.item_code
		order by times desc
		limit 1
		""",
		{"company": company, "since": add_years(nowdate(), -1)},
		as_dict=True,
	)
	return rows[0].item_code if rows else None


def _plan(company: str, customer: str, account: str | None, invoice: str | None, item_code: str | None, article_required: bool = False):
	"""What the credit note is made of and why it cannot be made, if it cannot: (the line, the account, the blocker).
	`article_required`: a person is making it on the card, who is asked for the article when neither the customer nor the company
	has a habit to fill it in (the import acts on the habit alone)."""
	d = defaults(company, customer)
	blocker = ""
	if not item_code and article_required and d.source == "company":
		item_code = usual_article(company)
		if not item_code:
			blocker = _("Choose the article of the credit note.")
	if item_code:
		blocker = article_problem(item_code)
		if not blocker:
			d = with_article(company, d, item_code, invoice)
	# the fixed charges of the theme come back only when the sale made them
	d["no_surcharge"] = not _invoice_charged_a_surcharge(invoice)
	chosen = account or d.account
	return d, chosen, blocker or problem(company, chosen)


def preview(
	company: str,
	customer: str,
	on,
	gross: float,
	account: str | None = None,
	invoice: str | None = None,
	item_code: str | None = None,
	article_required: bool = False,
) -> dict:
	"""What the credit note of the balance would be, measured, nothing written. The line is the article `item_code` when a
	person chose one (on the account it is sold on, with the VAT of `invoice`, the sale the balance is of), else the habit of
	the customer, else the gap account of the company. `article_required`: a person is choosing, and the company's account
	with no article is not an answer."""
	d, chosen, blocker = _plan(company, customer, account, invoice, item_code, article_required)
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
		"fees": 0.0,
		"fees_label": None,
		"fees_account": None,
		# each VAT line that will be booked, with its account: a person reads there which VAT account the note goes to
		"tax_lines": [],
		"total": flt(gross, 2),
	}
	if not blocker:
		try:
			doc = _measured(company, customer, on, gross, d, chosen)
			# the figures as saving will make them, this copy is only for them
			_as_saving_will(doc)
		except frappe.ValidationError as error:
			frappe.clear_last_message()
			out["blocker"] = str(error)
			return out
		# a fixed charge that a hook adds for the article (the RPLP) is told apart from the VAT: net + VAT + charges = the balance
		charges = [row for row in doc.taxes if row.charge_type == "Actual"]
		out["net"] = abs(flt(doc.net_total, 2))
		out["fees"] = abs(flt(sum(flt(row.tax_amount) for row in charges), 2))
		out["fees_label"] = charges[0].description if charges else None
		out["fees_account"] = charges[0].account_head if charges else None
		out["tax"] = flt(abs(flt(doc.total_taxes_and_charges, 2)) - out["fees"], 2)
		out["tax_lines"] = [
			{"account": row.account_head, "amount": abs(flt(row.tax_amount, 2))}
			for row in doc.taxes
			if row.charge_type != "Actual" and flt(row.tax_amount, 2)
		]
	return out


def _built(
	company: str,
	customer: str,
	on,
	gross: float,
	account: str | None,
	remark: str,
	invoice: str | None = None,
	item_code: str | None = None,
):
	"""The credit note of the balance, measured and not yet saved (what create() and prepare() both start from)."""
	frappe.has_permission("Sales Invoice", ptype="create", throw=True)
	d, chosen, blocker = _plan(company, customer, account, invoice, item_code)
	if blocker:
		frappe.throw(blocker)
	doc = _measured(company, customer, on, gross, d, chosen)
	doc.remarks = remark
	return doc


def prepare(
	company: str,
	customer: str,
	on,
	gross: float,
	account: str | None,
	remark: str,
	invoice: str | None = None,
	item_code: str | None = None,
) -> str:
	"""The credit note of the balance saved as a DRAFT: nothing is booked, a person opens it, corrects it if needed, and
	validates it from the card of the gap (create() then submits this very draft)."""
	doc = _built(company, customer, on, gross, account, remark, invoice, item_code)
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
	item_code: str | None = None,
) -> str:
	"""The credit note of the balance, made and submitted: the draft prepared earlier when there is one and it is still
	right, else a new one. Its name."""
	frappe.has_permission("Sales Invoice", ptype="create", throw=True)
	if draft:
		name = _submitted_draft(company, customer, gross, draft, remark)
		if name:
			return name
	doc = _built(company, customer, on, gross, account, remark, invoice, item_code)
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
