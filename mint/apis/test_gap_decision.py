# //// Neoffice — added file (no upstream equivalent).
# ////
# //// A PERSON DECIDES THE GAP OF A BANK LINE: THE FILTER, THE VERDICT IN WORDS, PASSING IT OR LEAVING IT OPEN.
# ////
# //// Played on real invoices of the site through the import itself, then through the calls the bank reconciliation
# //// makes. The company's switches are OFF throughout: a person who decides does not need them.

import frappe
from frappe.tests.roles import as_role
from frappe.utils import add_days, flt

from mint.apis import statement_follow_up as follow_up
from mint.apis.test_payment_gap_import import COMPANY, GAP_ACCOUNT, GapImportCase


class TestGapDecision(GapImportCase):
	def _a_line_with_a_gap(self, gap=0.03):
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, flt(owed - gap, 2)))
		return statement, statement.transactions[0].bank_transaction

	def _states(self, statement):
		return [line["state"] for line in follow_up.get_import_overview(statement.name)["lines"]]

	# -- the filter and the verdict ---------------------------------------------------------------------------------------

	def test_the_lines_waiting_for_a_decision_are_listed_with_their_gap(self):
		statement, bank_line = self._a_line_with_a_gap(0.03)
		listed = {row.bank_transaction: row for row in follow_up.get_lines_to_decide(self.bank_account)}
		self.assertEqual((listed[bank_line].kind, flt(listed[bank_line].gap, 2)), ("rounding", 0.03))

	def test_the_count_follows_the_period_the_reconciliation_shows(self):
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		today = frappe.utils.nowdate()
		inside = follow_up.get_lines_to_decide(self.bank_account, add_days(today, -1), add_days(today, 1))
		self.assertIn(bank_line, [row.bank_transaction for row in inside])
		before = follow_up.get_lines_to_decide(self.bank_account, add_days(today, -400), add_days(today, -300))
		self.assertNotIn(bank_line, [row.bank_transaction for row in before])
		everything = follow_up.get_lines_to_decide(self.bank_account)
		self.assertIn(bank_line, [row.bank_transaction for row in everything])

	def test_the_choice_for_a_partial_payment_is_offered_even_when_the_company_has_no_gap_account(self):
		frappe.db.set_value("Neoffice Company Settings", "AlpInnovate SA", "payment_gap_account", None)
		frappe.db.set_value("Company", "AlpInnovate SA", "default_discount_account", None)
		frappe.clear_document_cache("Company", "AlpInnovate SA")
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, flt(owed / 2, 2)))
		decision = follow_up.get_gap_decision(statement.transactions[0].bank_transaction, settle_in_full=1)
		self.assertTrue(decision["can_settle"])
		self.assertFalse(decision["can_pass"])
		self.assertIn("account", decision["blocker"])
		chosen = follow_up.get_gap_decision(
			statement.transactions[0].bank_transaction, account=GAP_ACCOUNT, settle_in_full=1
		)
		self.assertTrue(chosen["can_pass"])

	def test_the_verdict_is_worked_out_now_and_says_what_a_person_may_do(self):
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		decision = follow_up.get_gap_decision(bank_line)
		self.assertEqual(decision["invoice"], self.sales)
		self.assertEqual((decision["verdict"]["kind"], flt(decision["verdict"]["gap"], 2)), ("rounding", 0.03))
		self.assertTrue(decision["can_pass"])
		self.assertEqual(decision["blocker"], "")

	def test_the_decision_names_the_party_of_the_invoice_so_that_another_way_opens_on_it(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		# « Record another way » opens the payment form: it is pointed at the customer (or supplier) of the invoice, by its
		# document name, not at the name the bank wrote on the line
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		decision = follow_up.get_gap_decision(bank_line)
		self.assertEqual(
			(decision["party_doctype"], decision["party_id"]),
			("Customer", frappe.db.get_value("Sales Invoice", self.sales, "customer")),
		)
		owed = self._owed("Purchase Invoice", self.purchase)
		statement = self._import(self._line("Purchase Invoice", self.purchase, owed - 0.03))
		decision = follow_up.get_gap_decision(statement.transactions[0].bank_transaction)
		self.assertEqual(
			(decision["party_doctype"], decision["party_id"]),
			("Supplier", frappe.db.get_value("Purchase Invoice", self.purchase, "supplier")),
		)

	def _an_overpayment(self, extra=5.0, invoice_type="Sales Invoice"):
		invoice = self.sales if invoice_type == "Sales Invoice" else self.purchase
		owed = self._owed(invoice_type, invoice)
		statement = self._import(self._line(invoice_type, invoice, flt(owed + extra, 2)))
		return statement, statement.transactions[0].bank_transaction

	def test_an_overpayment_is_offered_to_keep_the_surplus_or_to_pass_it_as_a_difference(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		_statement, bank_line = self._an_overpayment()
		decision = follow_up.get_gap_decision(bank_line)
		self.assertEqual(decision["verdict"]["kind"], "overpaid")
		self.assertTrue(decision["can_decide_surplus"])
		self.assertTrue(decision["can_pass"])
		self.assertEqual(decision["blocker"], "")
		# the account of the difference is the company's until a person picks another; keeping the surplus books nothing on it
		self.assertTrue(decision["account_editable"])
		self.assertEqual(decision["default_account"], GAP_ACCOUNT)
		self.assertEqual(decision["deductions"], [])
		passed = follow_up.get_gap_decision(bank_line, settle_in_full=1)
		self.assertTrue(passed["can_pass"])
		self.assertEqual([(row["account"], row["amount"]) for row in passed["deductions"]], [(GAP_ACCOUNT, -5.0)])

	def test_keeping_the_surplus_books_the_whole_payment_and_leaves_the_rest_open_for_a_next_invoice(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		statement, bank_line = self._an_overpayment()
		owed = self._owed("Sales Invoice", self.sales)
		answer = follow_up.decide_gap(bank_line, "passed_gap")
		entry = frappe.get_doc("Payment Entry", answer["payment_entry"])
		self.assertEqual((flt(entry.paid_amount, 2), flt(entry.unallocated_amount, 2)), (flt(owed + 5, 2), 5.0))
		self.assertEqual(len(entry.deductions), 0)
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Reconciled")
		line = follow_up.get_import_overview(statement.name)["lines"][0]
		self.assertEqual((line["state"], line["decision"], line["decided_by"]), ("handled", "passed_gap", "Administrator"))
		self.assertNotIn(bank_line, [row.bank_transaction for row in follow_up.get_lines_to_decide(self.bank_account)])

	def test_passing_the_surplus_as_a_difference_books_it_on_the_account_and_leaves_nothing_open(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		_statement, bank_line = self._an_overpayment()
		answer = follow_up.decide_gap(bank_line, "passed_gap", settle_in_full=1)
		entry = frappe.get_doc("Payment Entry", answer["payment_entry"])
		self.assertEqual([(d.account, flt(d.amount, 2)) for d in entry.deductions], [(GAP_ACCOUNT, -5.0)])
		self.assertEqual(flt(entry.unallocated_amount, 2), 0)
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Reconciled")

	def test_the_surplus_goes_to_the_account_a_person_picked(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		other = frappe.db.get_value(
			"Account",
			{"company": COMPANY, "root_type": "Income", "is_group": 0, "disabled": 0, "name": ("!=", GAP_ACCOUNT)},
			"name",
			order_by="name",
		)
		if not other:
			self.skipTest("needs a second income account")
		_statement, bank_line = self._an_overpayment()
		answer = follow_up.decide_gap(bank_line, "passed_gap", account=other, settle_in_full=1)
		entry = frappe.get_doc("Payment Entry", answer["payment_entry"])
		self.assertEqual([d.account for d in entry.deductions], [other])

	def test_passing_the_surplus_with_no_account_says_so_but_keeping_it_needs_none(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		frappe.db.set_value("Neoffice Company Settings", "AlpInnovate SA", "payment_gap_account", None)
		frappe.clear_document_cache("Company", "AlpInnovate SA")
		_statement, bank_line = self._an_overpayment()
		kept = follow_up.get_gap_decision(bank_line)
		self.assertTrue(kept["can_pass"])
		passed = follow_up.get_gap_decision(bank_line, settle_in_full=1)
		self.assertFalse(passed["can_pass"])
		self.assertIn("account", passed["blocker"])
		with self.assertRaises(frappe.ValidationError):
			follow_up.decide_gap(bank_line, "passed_gap", settle_in_full=1)
		self.assertTrue(follow_up.decide_gap(bank_line, "passed_gap")["payment_entry"])

	def test_a_surplus_paid_to_a_supplier_is_offered_the_same_two_ways(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		_statement, bank_line = self._an_overpayment(invoice_type="Purchase Invoice")
		decision = follow_up.get_gap_decision(bank_line)
		self.assertEqual(decision["verdict"]["kind"], "overpaid")
		self.assertTrue(decision["can_decide_surplus"])
		self.assertEqual(decision["default_account"], self.expense)
		answer = follow_up.decide_gap(bank_line, "passed_gap")
		entry = frappe.get_doc("Payment Entry", answer["payment_entry"])
		self.assertEqual((flt(entry.unallocated_amount, 2), len(entry.deductions)), (5.0, 0))
		self.assertEqual(self._owed("Purchase Invoice", self.purchase), 0)

	def test_a_surplus_on_an_invoice_in_another_currency_is_left_to_the_payment_window(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		_statement, bank_line = self._an_overpayment()
		frappe.db.set_value("Company", COMPANY, "default_currency", "EUR")
		frappe.clear_document_cache("Company", COMPANY)
		decision = follow_up.get_gap_decision(bank_line)
		self.assertEqual(decision["verdict"]["kind"], "overpaid")
		self.assertFalse(decision["can_decide_surplus"])
		self.assertFalse(decision["can_pass"])
		self.assertTrue(decision["blocker"])
		with self.assertRaises(frappe.ValidationError):
			follow_up.decide_gap(bank_line, "passed_gap")

	def test_a_gap_with_no_account_to_go_to_says_so_instead_of_failing(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		frappe.db.set_value("Neoffice Company Settings", "AlpInnovate SA", "payment_gap_account", None)
		frappe.db.set_value("Company", "AlpInnovate SA", "default_discount_account", None)
		frappe.clear_document_cache("Company", "AlpInnovate SA")
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		decision = follow_up.get_gap_decision(bank_line)
		self.assertFalse(decision["can_pass"])
		self.assertIn("account", decision["blocker"])
		with self.assertRaises(frappe.ValidationError):
			follow_up.decide_gap(bank_line, "passed_gap")

	# -- the decision -------------------------------------------------------------------------------------------------------

	def test_passing_the_gap_books_it_links_the_bank_line_and_notes_who_decided(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested below
		statement, bank_line = self._a_line_with_a_gap(0.03)
		owed = self._owed("Sales Invoice", self.sales)
		answer = follow_up.decide_gap(bank_line, "passed_gap")
		entry = frappe.get_doc("Payment Entry", answer["payment_entry"])
		self.assertEqual([(d.account, flt(d.amount, 2)) for d in entry.deductions], [(GAP_ACCOUNT, 0.03)])
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Reconciled")
		line = follow_up.get_import_overview(statement.name)["lines"][0]
		self.assertEqual((line["state"], line["decision"], line["decided_by"]), ("handled", "passed_gap", "Administrator"))
		self.assertTrue(line["decided_on"])
		self.assertNotIn(bank_line, [row.bank_transaction for row in follow_up.get_lines_to_decide(self.bank_account)])
		self.assertGreater(owed, 0)

	def test_a_partial_payment_is_booked_for_what_came_in_and_the_rest_stays_open(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		owed = self._owed("Sales Invoice", self.sales)
		part = flt(owed / 2, 2)
		statement = self._import(self._line("Sales Invoice", self.sales, part))
		bank_line = statement.transactions[0].bank_transaction
		self.assertEqual(follow_up.get_gap_decision(bank_line)["verdict"]["kind"], "partial")
		follow_up.decide_gap(bank_line, "passed_gap")
		self.assertEqual(self._owed("Sales Invoice", self.sales), flt(owed - part, 2))
		self.assertEqual(self._states(statement), ["handled"])

	def test_leaving_it_open_creates_nothing_and_leaves_the_list_of_what_waits(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		statement, bank_line = self._a_line_with_a_gap(0.03)
		owed = self._owed("Sales Invoice", self.sales)
		self.assertEqual(follow_up.decide_gap(bank_line, "left_open")["payment_entry"], None)
		self.assertEqual(self._owed("Sales Invoice", self.sales), owed)
		self.assertEqual(self._states(statement), ["left_open"])
		self.assertNotIn(bank_line, [row.bank_transaction for row in follow_up.get_lines_to_decide(self.bank_account)])

	def test_a_line_already_dealt_with_is_not_decided_twice(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		follow_up.decide_gap(bank_line, "passed_gap")
		with self.assertRaises(frappe.ValidationError):
			follow_up.decide_gap(bank_line, "passed_gap")
		self.assertIsNone(follow_up.get_gap_decision(bank_line))

	def test_a_line_that_did_not_come_from_an_import_has_nothing_to_decide(self):
		self.assertIsNone(follow_up.get_gap_decision(frappe.db.get_value("Bank Transaction", {"docstatus": 1})))

	# -- the account of the gap -----------------------------------------------------------------------------------------------

	def _another_account(self, **filters):
		account = frappe.db.get_value(
			"Account",
			{"company": COMPANY, "is_group": 0, "disabled": 0, "name": ("!=", GAP_ACCOUNT), **(filters or {"root_type": "Expense"})},
		)
		if not account:
			self.skipTest("no other account of that kind on this site")
		return account

	def test_the_card_previews_the_rows_of_the_account_a_person_tries_without_booking_anything(self):
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		owed = self._owed("Sales Invoice", self.sales)
		other = self._another_account()
		decision = follow_up.get_gap_decision(bank_line, account=other)
		self.assertEqual([(row["account"], row["amount"]) for row in decision["deductions"]], [(other, 0.03)])
		self.assertEqual((decision["account"], decision["default_account"]), (other, GAP_ACCOUNT))
		self.assertTrue(decision["account_editable"])
		self.assertEqual(self._owed("Sales Invoice", self.sales), owed)
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Unreconciled")

	def test_a_person_can_pass_the_gap_on_another_account(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		other = self._another_account()
		answer = follow_up.decide_gap(bank_line, "passed_gap", account=other)
		entry = frappe.get_doc("Payment Entry", answer["payment_entry"])
		self.assertEqual([(d.account, flt(d.amount, 2)) for d in entry.deductions], [(other, 0.03)])

	def test_an_account_that_cannot_take_a_gap_is_refused_and_said(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		receivable = self._another_account(account_type="Receivable")
		decision = follow_up.get_gap_decision(bank_line, account=receivable)
		self.assertFalse(decision["can_pass"])
		self.assertIn("income or expense", decision["blocker"])
		with self.assertRaises(frappe.ValidationError):
			follow_up.decide_gap(bank_line, "passed_gap", account=receivable)

	def test_a_short_payment_can_be_settled_in_full_with_the_gap_passed_on_an_account(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_who_cannot_write_the_bank_line_cannot_decide_it
		owed = self._owed("Sales Invoice", self.sales)
		part = flt(owed * 0.6, 2)
		statement = self._import(self._line("Sales Invoice", self.sales, part))
		bank_line = statement.transactions[0].bank_transaction
		decision = follow_up.get_gap_decision(bank_line, settle_in_full=1)
		self.assertTrue(decision["can_settle"])
		self.assertAlmostEqual(sum(row["amount"] for row in decision["deductions"]), flt(owed - part, 2), places=2)
		answer = follow_up.decide_gap(bank_line, "passed_gap", settle_in_full=1)
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)
		entry = frappe.get_doc("Payment Entry", answer["payment_entry"])
		self.assertEqual(flt(entry.paid_amount, 2), part)
		self.assertAlmostEqual(sum(flt(d.amount) for d in entry.deductions), flt(owed - part, 2), places=2)

	def test_settling_in_full_is_offered_for_a_partial_payment_only(self):
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		self.assertFalse(follow_up.get_gap_decision(bank_line)["can_settle"])

	# -- the rights -----------------------------------------------------------------------------------------------------------

	def test_somebody_who_cannot_write_the_bank_line_cannot_decide_it(self):
		_statement, bank_line = self._a_line_with_a_gap(0.03)
		with as_role("Guest"):
			for call in (
				lambda: follow_up.decide_gap(bank_line, "left_open"),
				lambda: follow_up.get_gap_decision(bank_line),
				lambda: follow_up.get_lines_to_decide(self.bank_account),
			):
				with self.assertRaises(frappe.PermissionError):
					call()

	# -- the window after an import ------------------------------------------------------------------------------------------

	def test_the_window_after_an_import_counts_each_kind_and_points_at_what_waits(self):
		stats = {
			"total": 30,
			"auto_matched": 22,
			"passed_with_gap": 3,
			"gap_total": 0.09,
			"to_decide": 3,
			"unreconciled": 5,
			"duplicates": 3,
			"errors": 0,
		}
		html = follow_up.result_message(stats, "CHF")
		for text in ("30 lines read", "22 passed by themselves", "3 to decide", "2 to match", "3 already in the bank"):
			self.assertIn(text, html)
		self.assertIn("Settle the 5 that wait", html)
		self.assertIn("statement-imports", html)
		quiet = follow_up.result_message({**stats, "to_decide": 0, "unreconciled": 0}, "CHF")
		self.assertNotIn("Settle the", quiet)
