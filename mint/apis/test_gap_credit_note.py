# //// Neoffice — added file (no upstream equivalent).
# ////
# //// THE CREDIT NOTE OF A BALANCE: WHAT IT IS MADE OF, WHAT IT SETTLES, AND WHAT THE CUSTOMER'S HABIT SAYS.
# ////
# //// Played on real invoices of the site through the import and the calls of the bank reconciliation. The VAT
# //// templates of the site are used as they are (one included in the price and one added to it, when the site has
# //// them), so that the figure of the credit note is measured, not assumed.

from unittest.mock import patch

import frappe
from frappe.tests.roles import as_role
from frappe.utils import flt

from mint.apis import gap_credit_note, statement_follow_up as follow_up
from mint.apis.test_payment_gap_import import COMPANY, GAP_ACCOUNT, GapImportCase



def _only_for(fragment: str, rows: list):
	"""A stand-in for frappe.db.sql that answers `rows` to the one query that has `fragment` in it and lets every other
	query (the company's settings, its currency) through to the database."""
	real = frappe.db.sql

	def answer(query, *args, **kwargs):
		return rows if fragment in str(query) else real(query, *args, **kwargs)

	return patch.object(frappe.db, "sql", side_effect=answer)


def _templates(included: int):
	"""A sales tax template of the company whose rows are in the price (1) or added to it (0), and an item tax template
	of the company that puts a rate on one of ITS accounts: Swiss templates list the VAT accounts at a rate of 0, the
	rate is the line's (an item tax template is shared with purchases, so it must name an account of this template)."""
	for name in frappe.get_all("Sales Taxes and Charges Template", filters={"company": COMPANY, "disabled": 0}, pluck="name"):
		rows = frappe.get_all(
			"Sales Taxes and Charges",
			filters={"parent": name},
			fields=["included_in_print_rate", "charge_type", "account_head"],
			order_by="idx",
		)
		if not (rows and all(r.charge_type == "On Net Total" for r in rows)):
			continue
		if not all(int(r.included_in_print_rate or 0) == included for r in rows):
			continue
		item_tax = frappe.db.sql(
			"""
			select t.name from `tabItem Tax Template` t join `tabItem Tax Template Detail` d on d.parent = t.name
			where t.company = %(company)s and t.disabled = 0 and d.tax_rate > 0 and ifnull(d.not_applicable, 0) = 0
				and d.tax_type in %(heads)s
			limit 1
			""",
			{"company": COMPANY, "heads": [r.account_head for r in rows]},
		)
		if item_tax:
			return name, item_tax[0][0]
	return None


class TestGapCreditNote(GapImportCase):
	def _partial(self, share=0.6):
		owed = self._owed("Sales Invoice", self.sales)
		part = flt(owed * share, 2)
		statement = self._import(self._line("Sales Invoice", self.sales, part))
		return statement, statement.transactions[0].bank_transaction, owed, part

	def _customer(self):
		return frappe.db.get_value("Sales Invoice", self.sales, "customer")

	# -- the credit note on the article the person chose -----------------------------------------------------------------

	def _the_article(self):
		if not self.article:
			self.skipTest("needs an article that is sold")
		return self.article

	def test_the_credit_note_is_one_line_on_the_chosen_article_and_the_account_it_is_sold_on(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_credit_note
		article = self._the_article()
		invoice = frappe.get_doc("Sales Invoice", self.sales)
		gross = flt(invoice.outstanding_amount * 0.2, 2)
		name = gap_credit_note.create(COMPANY, invoice.customer, frappe.utils.nowdate(), gross, None, "test", invoice=self.sales, item_code=article)
		note = frappe.get_doc("Sales Invoice", name)
		self.assertEqual((note.docstatus, note.is_return, note.update_stock), (1, 1, 0))
		# one line, on the article, on the account the article is sold on: no copy of the lines of the invoice, no link to it
		self.assertEqual([item.item_code for item in note.items], [article])
		self.assertEqual(note.items[0].income_account, gap_credit_note._sold_on(frappe.get_cached_doc("Item", article), COMPANY))
		self.assertFalse(note.return_against)
		self.assertAlmostEqual(abs(flt(note.grand_total)), gross, places=2)

	def test_the_preview_says_the_article_its_account_and_takes_back_the_vat_of_the_sale(self):
		article = self._the_article()
		invoice = frappe.get_doc("Sales Invoice", self.sales)
		if not any(item.item_tax_template for item in invoice.items):
			self.skipTest("the invoice has no item tax template")
		gross = flt(invoice.outstanding_amount * 0.2, 2)
		shown = gap_credit_note.preview(COMPANY, invoice.customer, frappe.utils.nowdate(), gross, None, invoice=self.sales, item_code=article)
		self.assertEqual(shown["blocker"], "")
		self.assertEqual((shown["item_code"], shown["source"]), (article, "article"))
		self.assertEqual(shown["account"], shown["default_account"])
		self.assertGreater(shown["tax"], 0)
		# net + VAT + the charges that the article brings (the RPLP, when it has one) = the balance, to the cent
		self.assertAlmostEqual(shown["net"] + shown["tax"] + shown["fees"], gross, places=2)

	def test_the_credit_note_of_the_card_settles_its_balance(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_credit_note
		article = self._the_article()
		invoice = frappe.get_doc("Sales Invoice", self.sales)
		owed = flt(invoice.outstanding_amount, 2)
		gross = flt(owed * 0.2, 2)
		name = gap_credit_note.create(COMPANY, invoice.customer, frappe.utils.nowdate(), gross, None, "test", invoice=self.sales, item_code=article)
		gap_credit_note.settle(COMPANY, invoice.customer, self.sales, name, gross)
		self.assertAlmostEqual(self._owed("Sales Invoice", self.sales), flt(owed - gross, 2), places=2)

	def test_an_article_that_does_not_exist_is_refused_and_said(self):
		shown = gap_credit_note.preview(COMPANY, self._customer(), frappe.utils.nowdate(), 100.0, item_code="NO-SUCH-ARTICLE-1234")
		self.assertIn("does not exist", shown["blocker"])
		self.assertIsNone(shown["net"])

	def test_an_article_that_is_not_sold_is_refused_and_said(self):
		other = frappe.db.get_value("Item", {"disabled": 0, "is_sales_item": 0}, "name")
		if not other:
			self.skipTest("every article of this site is sold")
		self.assertIn("cannot be sold", gap_credit_note.preview(COMPANY, self._customer(), frappe.utils.nowdate(), 100.0, item_code=other)["blocker"])

	def test_a_person_is_asked_for_the_article_when_the_customer_and_the_company_have_no_habit(self):
		with _only_for("tabSales Invoice Item` it", []), _only_for("tabSales Invoice Item` line", []):
			shown = gap_credit_note.preview(COMPANY, self._customer(), frappe.utils.nowdate(), 100.0, article_required=True)
		self.assertIn("Choose the article", shown["blocker"])
		# the import acts on the habit alone: it is not asked
		with _only_for("tabSales Invoice Item` it", []):
			self.assertEqual(gap_credit_note.preview(COMPANY, self._customer(), frappe.utils.nowdate(), 100.0)["blocker"], "")

	def test_the_article_most_used_on_the_credit_notes_of_the_company_is_proposed_to_a_customer_with_no_habit(self):
		rows = [frappe._dict(item_code=self.article, times=7)]
		article = self._the_article()
		with _only_for("tabSales Invoice Item` it", []), _only_for("tabSales Invoice Item` line", rows):
			shown = gap_credit_note.preview(COMPANY, self._customer(), frappe.utils.nowdate(), 100.0, article_required=True)
		self.assertEqual((shown["blocker"], shown["item_code"], shown["source"]), ("", article, "article"))

	# -- what it is made of ---------------------------------------------------------------------------------------------

	def test_a_customer_with_no_credit_note_gets_the_company_account_and_no_item(self):
		with _only_for("tabSales Invoice Item` it", []):
			d = gap_credit_note.defaults(COMPANY, self._customer())
		self.assertEqual((d.source, d.account, d.item_code, d.times), ("company", GAP_ACCOUNT, None, 0))

	def test_the_habit_of_the_customer_wins_over_the_company(self):
		row = frappe._dict(
			item_code=None, item_name="perte-sur-debiteur", income_account=GAP_ACCOUNT, taxes_and_charges=None, times=3,
			last_day="2026-10-01", item_tax_template=None,
		)
		with _only_for("tabSales Invoice Item` it", [row]):
			d = gap_credit_note.defaults(COMPANY, self._customer())
		self.assertEqual((d.source, d.item_name, d.account, d.times), ("history", "perte-sur-debiteur", GAP_ACCOUNT, 3))

	def test_the_total_of_the_credit_note_is_the_balance_to_the_cent_without_vat(self):
		preview = gap_credit_note.preview(COMPANY, self._customer(), frappe.utils.nowdate(), 1234.56)
		self.assertEqual((preview["blocker"], preview["total"], preview["net"], preview["tax"]), ("", 1234.56, 1234.56, 0.0))

	def test_the_total_is_the_balance_with_a_template_included_in_the_price_and_with_one_added_to_it(self):
		found = 0
		for included in (1, 0):
			template = _templates(included)
			if not template:
				continue
			found += 1
			name, item_tax_template = template
			with self.subTest(included_in_price=included), patch.object(
				gap_credit_note,
				"defaults",
				return_value=frappe._dict(
					item_code=None,
					item_name="x",
					account=GAP_ACCOUNT,
					tax_template=name,
					item_tax_template=item_tax_template,
					times=0,
					source="history",
				),
			):
				preview = gap_credit_note.preview(COMPANY, self._customer(), frappe.utils.nowdate(), 1000.0)
				self.assertEqual(preview["total"], 1000.0)
				self.assertGreater(preview["tax"], 0)
				self.assertAlmostEqual(preview["net"] + preview["tax"], 1000.0, places=2)
		if not found:
			self.skipTest("no sales tax template on this site")

	def test_an_account_that_is_not_an_income_account_is_refused(self):
		expense = frappe.db.get_value("Account", {"company": COMPANY, "root_type": "Expense", "is_group": 0, "disabled": 0})
		if not expense:
			self.skipTest("no expense account on this site")
		preview = gap_credit_note.preview(COMPANY, self._customer(), frappe.utils.nowdate(), 100.0, account=expense)
		self.assertIn("income account", preview["blocker"])

	# -- what the card says --------------------------------------------------------------------------------------------------

	def test_the_card_offers_the_credit_note_of_the_balance_for_a_short_sale_payment(self):
		_statement, bank_line, owed, part = self._partial()
		decision = follow_up.get_gap_decision(bank_line)
		self.assertEqual(decision["verdict"]["kind"], "partial")
		self.assertEqual(decision["credit_note"]["total"], flt(owed - part, 2))
		self.assertFalse(decision["credit_note_chosen"])
		chosen = follow_up.get_gap_decision(bank_line, credit_note=1)
		self.assertTrue(chosen["credit_note_chosen"])
		self.assertEqual(chosen["deductions"], [])

	def test_a_rounding_is_not_offered_a_credit_note(self):
		_statement, bank_line = self._a_line_with_a_gap()
		decision = follow_up.get_gap_decision(bank_line)
		self.assertIsNone(decision["credit_note"])
		self.assertFalse(follow_up.get_gap_decision(bank_line, credit_note=1)["credit_note_chosen"])

	def _a_line_with_a_gap(self, gap=0.03):
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, flt(owed - gap, 2)))
		return statement, statement.transactions[0].bank_transaction

	# -- making it and settling the invoice with it ------------------------------------------------------------------------

	def test_the_credit_note_closes_the_invoice_with_the_payment_and_is_kept_on_the_line(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_credit_note
		statement, bank_line, owed, part = self._partial(0.6)
		answer = follow_up.decide_gap(bank_line, "passed_gap", credit_note=1, credit_item=self._the_article())
		note = frappe.get_doc("Sales Invoice", answer["credit_note"])
		self.assertEqual((note.docstatus, note.is_return, flt(note.grand_total, 2)), (1, 1, -flt(owed - part, 2)))
		self.assertFalse(note.return_against)
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)
		self.assertEqual(flt(frappe.db.get_value("Payment Entry", answer["payment_entry"], "paid_amount"), 2), part)
		line = follow_up.get_import_overview(statement.name)["lines"][0]
		self.assertEqual((line["state"], line["decision"], line["credit_note"]), ("handled", "passed_gap", note.name))

	def test_a_company_that_rounds_to_five_centimes_leaves_nothing_open_on_the_credit_note(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_credit_note
		# a gap of 0.01 beyond a multiple of 0.05: a rounded total would be 0.01 off the balance the invoice is settled by
		frappe.db.set_value("Currency", "CHF", "smallest_currency_fraction_value", 0.05)
		frappe.db.set_single_value("Global Defaults", "disable_rounded_total", 0)
		self.addCleanup(lambda: frappe.db.value_cache.pop("Currency", None))
		owed = self._owed("Sales Invoice", self.sales)
		gap = flt(int(owed * 0.4 * 20) / 20 + 0.01, 2)
		statement = self._import(self._line("Sales Invoice", self.sales, flt(owed - gap, 2)))
		answer = follow_up.decide_gap(statement.transactions[0].bank_transaction, "passed_gap", credit_note=1, credit_item=self._the_article())
		note = frappe.db.get_value("Sales Invoice", answer["credit_note"], ["grand_total", "rounded_total", "outstanding_amount"], as_dict=True)
		self.assertEqual((flt(note.grand_total, 2), flt(note.rounded_total, 2), flt(note.outstanding_amount, 2)), (-gap, 0, 0))
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)

	def test_the_credit_note_goes_to_the_account_the_person_chose(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_credit_note
		_statement, bank_line, _owed, _part = self._partial(0.7)
		other = frappe.db.get_value(
			"Account", {"company": COMPANY, "root_type": "Income", "is_group": 0, "disabled": 0, "name": ("!=", GAP_ACCOUNT)}
		)
		if not other:
			self.skipTest("no other income account on this site")
		answer = follow_up.decide_gap(bank_line, "passed_gap", account=other, credit_note=1, credit_item=self._the_article())
		accounts = frappe.get_all("Sales Invoice Item", filters={"parent": answer["credit_note"]}, pluck="income_account")
		self.assertEqual(set(accounts), {other})

	def test_nothing_is_made_when_the_credit_note_cannot_be(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_credit_note
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		with self.assertRaises(frappe.ValidationError):
			follow_up.decide_gap(bank_line, "passed_gap", credit_note=1, credit_item=self._the_article())
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Unreconciled")
		before = frappe.db.count("Sales Invoice", {"is_return": 1})
		_s2, partial_line, _o, _p = self._partial(0.5)
		# the credit note cannot be brought to the balance: the refusal is said and nothing is written
		article = self._the_article()
		with patch.object(gap_credit_note, "_measured", side_effect=frappe.ValidationError("cannot be brought")):
			self.assertIn("cannot be brought", follow_up.get_gap_decision(partial_line, credit_note=1, credit_item=article)["blocker"])
			with self.assertRaises(frappe.ValidationError):
				follow_up.decide_gap(partial_line, "passed_gap", credit_note=1, credit_item=article)
		self.assertEqual(frappe.db.get_value("Bank Transaction", partial_line, "status"), "Unreconciled")
		self.assertEqual(frappe.db.count("Sales Invoice", {"is_return": 1}), before)

	def test_the_credit_note_needs_no_gap_account_of_the_company(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_credit_note
		# the account of the credit note is the one its article is sold on: the account of the gaps, which a loss on customers
		# uses, is not in it, so a company that has none can still make one
		frappe.db.set_value("Neoffice Company Settings", COMPANY, "payment_gap_account", None)
		frappe.clear_document_cache("Company", COMPANY)
		_statement, bank_line, owed, part = self._partial(0.6)
		article = self._the_article()
		chosen = follow_up.get_gap_decision(bank_line, credit_note=1, credit_item=article)
		self.assertTrue(chosen["credit_note_chosen"])
		self.assertTrue(chosen["can_pass"])
		self.assertEqual(chosen["blocker"], "")
		self.assertEqual(chosen["credit_note"]["item_code"], article)
		answer = follow_up.decide_gap(bank_line, "passed_gap", credit_note=1, credit_item=article)
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", answer["credit_note"], "grand_total"), 2), -flt(owed - part, 2))
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)

	def test_a_purchase_is_never_offered_a_credit_note_of_the_balance(self):
		owed = self._owed("Purchase Invoice", self.purchase)
		statement = self._import(self._line("Purchase Invoice", self.purchase, flt(owed / 2, 2)))
		decision = follow_up.get_gap_decision(statement.transactions[0].bank_transaction)
		self.assertEqual(decision["verdict"]["kind"], "partial")
		self.assertIsNone(decision["credit_note"])

	# -- the habit of the customer -------------------------------------------------------------------------------------------

	def _rows(self, shares, closed_by_credit):
		rows = []
		for index, (paid, grand) in enumerate(shares):
			outstanding = 0.0 if index < closed_by_credit else grand - paid
			rows.append(frappe._dict(name=f"INV-{index}", grand_total=grand, outstanding_amount=outstanding, paid=paid))
		return rows

	def test_a_habit_is_read_from_the_second_time(self):
		rows = self._rows([(80, 100)] * 4 + [(100, 100)], closed_by_credit=3)
		with _only_for("tabPayment Entry Reference", rows):
			habit = gap_credit_note.history(COMPANY, "C", "NOW", 0.8)
		self.assertEqual((habit["considered"], habit["same_share"], habit["closed_by_credit"]), (5, 4, 3))
		self.assertEqual((habit["share"], habit["proposal"]), (80.0, "credit_note"))

	def test_one_occurrence_is_not_a_habit(self):
		rows = self._rows([(80, 100)] + [(100, 100)] * 4, closed_by_credit=1)
		with _only_for("tabPayment Entry Reference", rows):
			habit = gap_credit_note.history(COMPANY, "C", "NOW", 0.8)
		self.assertEqual((habit["same_share"], habit["closed_by_credit"], habit["proposal"]), (1, 1, None))

	def test_a_share_close_to_the_usual_one_counts_and_a_distant_one_does_not(self):
		rows = self._rows([(79.5, 100), (81, 100), (60, 100), (80, 100)], closed_by_credit=4)
		with _only_for("tabPayment Entry Reference", rows):
			habit = gap_credit_note.history(COMPANY, "C", "NOW", 0.8)
		self.assertEqual(habit["same_share"], 3)

	def test_the_habit_is_read_from_the_real_invoices_of_the_site_without_failing(self):
		habit = gap_credit_note.history(COMPANY, self._customer(), self.sales, 0.8)
		self.assertGreaterEqual(habit["considered"], habit["same_share"])
		self.assertGreaterEqual(habit["same_share"], habit["closed_by_credit"])

	# -- the rights --------------------------------------------------------------------------------------------------------------

	def test_somebody_without_the_right_cannot_make_a_credit_note(self):
		_statement, bank_line, _owed, _part = self._partial(0.6)
		with as_role("Guest"):
			with self.assertRaises(frappe.PermissionError):
				follow_up.decide_gap(bank_line, "passed_gap", credit_note=1, credit_item=self.article)
			with self.assertRaises(frappe.PermissionError):
				gap_credit_note.create(COMPANY, self._customer(), frappe.utils.nowdate(), 10.0, None, "x")
