# //// Neoffice — added file (no upstream equivalent).
# ////
# //// THE RULE OF A CUSTOMER WHO PAYS LESS THAN THE INVOICE: ITS GUARDS, ITS CONFIRMATIONS AND WHAT THE IMPORT DOES WITH IT.
# ////
# //// Played on real invoices of the site through the import and the calls of the bank reconciliation. The import acts by
# //// itself only when EVERY condition holds (level, confirmations, usual share, invoice recognised without doubt, the
# //// company's switch); each missing one is played apart and must leave the line to a person.

from unittest.mock import patch

import frappe
from frappe.tests.roles import as_role
from frappe.utils import flt, nowdate

from mint.apis import gap_credit_note, gap_rule, statement_follow_up as follow_up
from mint.apis.test_gap_credit_note import _only_for
from mint.apis.test_payment_gap_import import COMPANY, GAP_ACCOUNT, GapImportCase



class TestGapRule(GapImportCase):
	def _customer(self):
		return frappe.db.get_value("Sales Invoice", self.sales, "customer")

	def _share(self, part):
		return flt(part) / flt(frappe.db.get_value("Sales Invoice", self.sales, "grand_total"))

	def _scor(self):
		return frappe.db.get_value("Sales Invoice", self.sales, "scor_reference")

	def _partial(self, share=0.6, sure=False):
		owed = self._owed("Sales Invoice", self.sales)
		part = flt(owed * share, 2)
		line = self._line("Sales Invoice", self.sales, part, remittance_reference=self._scor() if sure else "")
		statement = self._import(line)
		return statement, statement.transactions[0], owed, part

	def _rule(self, part, **values):
		defaults = {
			"doctype": "Payment Gap Rule",
			"company": COMPANY,
			"customer": self._customer(),
			"action": "credit_note",
			"mode": "suggest",
			"share": flt(self._share(part) * 100, 1),
			"account": GAP_ACCOUNT,
			"confirmed_times": 0,
		}
		return frappe.get_doc({**defaults, **values}).insert()

	def _owed_part(self, share=0.6):
		owed = self._owed("Sales Invoice", self.sales)
		return owed, flt(owed * share, 2)

	# -- the document ------------------------------------------------------------------------------------------------------

	def test_one_rule_per_customer_and_company(self):
		_owed, part = self._owed_part()
		self._rule(part)
		with self.assertRaises(frappe.ValidationError):
			self._rule(part)

	def test_automatic_is_refused_until_a_person_confirmed_three_times(self):
		_owed, part = self._owed_part()
		with self.assertRaises(frappe.ValidationError):
			self._rule(part, mode="automatic", confirmed_times=2)
		rule = self._rule(part, mode="automatic", confirmed_times=gap_rule.AUTO_AFTER)
		self.assertEqual(rule.mode, "automatic")

	def test_a_rule_that_acts_by_itself_or_prepares_a_draft_needs_the_usual_share(self):
		_owed, part = self._owed_part()
		for mode in ("draft", "automatic"):
			with self.subTest(mode=mode), self.assertRaises(frappe.ValidationError):
				self._rule(part, mode=mode, share=0, confirmed_times=gap_rule.AUTO_AFTER)

	def test_the_account_of_a_credit_note_rule_is_an_income_account_of_the_company(self):
		_owed, part = self._owed_part()
		expense = frappe.db.get_value("Account", {"company": COMPANY, "root_type": "Expense", "is_group": 0, "disabled": 0})
		if not expense:
			self.skipTest("no expense account on this site")
		with self.assertRaises(frappe.ValidationError):
			self._rule(part, account=expense)

	# -- making it from the card -------------------------------------------------------------------------------------------

	def test_a_person_makes_the_rule_from_the_card_and_it_takes_the_share_of_the_payment(self):
		_statement, line, _owed, part = self._partial()
		answer = follow_up.set_gap_rule(line.bank_transaction, "suggest", account=GAP_ACCOUNT)
		self.assertEqual((answer["exists"], answer["mode"], answer["action"]), (True, "suggest", "credit_note"))
		self.assertAlmostEqual(answer["share"], flt(self._share(part) * 100, 1), places=1)
		decision = follow_up.get_gap_decision(line.bank_transaction)
		self.assertTrue(decision["rule"]["exists"])
		self.assertEqual(decision["rule_proposal"], "credit_note")

	def test_a_new_rule_takes_the_confirmations_the_history_of_the_customer_already_gives_it(self):
		_statement, line, _owed, _part = self._partial()
		habit = {"considered": 5, "same_share": 4, "closed_by_credit": 3, "share": 60.0, "proposal": "credit_note"}
		with patch.object(gap_credit_note, "history", return_value=habit):
			answer = follow_up.set_gap_rule(line.bank_transaction, "suggest")
		self.assertEqual((answer["confirmed_times"], answer["can_automatic"]), (3, True))
		again = follow_up.set_gap_rule(line.bank_transaction, "automatic")
		self.assertEqual(again["mode"], "automatic")

	def test_automatic_is_refused_for_a_customer_whose_handling_nobody_confirmed(self):
		_statement, line, _owed, _part = self._partial()
		habit = {"considered": 0, "same_share": 0, "closed_by_credit": 0, "share": 60.0, "proposal": None}
		with patch.object(gap_credit_note, "history", return_value=habit):
			with self.assertRaises(frappe.ValidationError):
				follow_up.set_gap_rule(line.bank_transaction, "automatic")
			self.assertIsNone(gap_rule.get(COMPANY, self._customer()))

	def test_the_share_counts_what_the_customer_already_paid_on_the_invoice(self):
		# an advance of half of what is owed, then 60 % of the rest: the customer has paid 80 % of the invoice in all (as the
		# invoices it settled before say), not the 30 % that this payment alone is of the invoice
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

		owed = self._owed("Sales Invoice", self.sales)
		with as_role("accountant"):
			advance = get_payment_entry("Sales Invoice", self.sales, party_amount=flt(owed * 0.5, 2))
			advance.reference_no = f"ADV-{frappe.generate_hash(length=8)}"
			advance.reference_date = nowdate()
			advance.insert()
			advance.submit()
		_statement, line, owed_now, part = self._partial(0.6)
		total = flt(frappe.db.get_value("Sales Invoice", self.sales, "grand_total"))
		answer = follow_up.set_gap_rule(line.bank_transaction, "suggest", account=GAP_ACCOUNT)
		self.assertAlmostEqual(answer["share"], flt((total - owed_now + part) / total * 100, 1), places=1)
		self.assertGreater(answer["share"] - flt(part / total * 100, 1), 10)

	def test_a_rule_is_for_a_short_payment_of_a_customer(self):
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, flt(owed - 0.03, 2)))
		with self.assertRaises(frappe.ValidationError):
			follow_up.set_gap_rule(statement.transactions[0].bank_transaction, "suggest")

	# -- the confirmations -------------------------------------------------------------------------------------------------

	def test_a_persons_decision_at_the_usual_share_is_one_more_confirmation(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_rule
		_statement, line, _owed, part = self._partial()
		rule = self._rule(part)
		follow_up.decide_gap(line.bank_transaction, "passed_gap", credit_note=1)
		rule.reload()
		self.assertEqual((rule.confirmed_times, str(rule.last_confirmed_on)), (1, nowdate()))

	def test_a_decision_at_another_share_confirms_nothing(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_rule
		_statement, line, _owed, part = self._partial(0.6)
		rule = self._rule(part, share=80.0)
		follow_up.decide_gap(line.bank_transaction, "passed_gap", credit_note=1)
		rule.reload()
		self.assertEqual(rule.confirmed_times, 0)

	# -- what the import does ----------------------------------------------------------------------------------------------

	def _automatic_rule(self, part, **values):
		return self._rule(part, mode="automatic", confirmed_times=gap_rule.AUTO_AFTER, **values)

	def test_the_import_makes_the_credit_note_by_itself_when_every_condition_holds(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_rule
		owed, part = self._owed_part()
		rule = self._automatic_rule(part)
		self._settings(payment_gap_automatic=1)
		with _only_for("tabSales Invoice Item` it", []):
			statement, line, _o, _p = self._partial(sure=True)
		overview = follow_up.get_import_overview(statement.name)["lines"][0]
		self.assertEqual((line.status, line.payment_gap_rule), ("Paid", rule.name))
		self.assertEqual(overview["state"], "passed_alone")
		self.assertEqual(overview["rule"], rule.name)
		self.assertTrue(line.credit_note)
		self.assertEqual(flt(frappe.db.get_value("Sales Invoice", line.credit_note, "grand_total"), 2), -flt(owed - part, 2))
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)
		self.assertIn("1 passed with a gap", statement.import_summary)

	def test_the_import_leaves_the_line_to_a_person_when_one_condition_is_missing(self):
		owed, part = self._owed_part()
		rule = self._automatic_rule(part)
		self._settings(payment_gap_automatic=1)
		cases = {
			"the company has not switched it on": lambda: self._settings(payment_gap_automatic=0),
			"the invoice is not recognised without doubt": lambda: None,
			"the confirmations are not there": lambda: frappe.db.set_value("Payment Gap Rule", rule.name, "confirmed_times", 1),
			"the payment is not at the usual share": lambda: frappe.db.set_value("Payment Gap Rule", rule.name, "share", 80.0),
			"the rule is disabled": lambda: frappe.db.set_value("Payment Gap Rule", rule.name, "disabled", 1),
		}
		for label, spoil in cases.items():
			with self.subTest(label):
				frappe.db.savepoint("rule_case")
				try:
					spoil()
					with _only_for("tabSales Invoice Item` it", []):
						_statement, line, _o, _p = self._partial(sure=label != "the invoice is not recognised without doubt")
					self.assertEqual(line.status, "Imported")
					self.assertFalse(line.credit_note)
					self.assertEqual(self._owed("Sales Invoice", self.sales), owed)
				finally:
					frappe.db.rollback(save_point="rule_case")

	def test_a_suggest_rule_does_nothing_at_the_import_and_is_proposed_by_the_card(self):
		owed, part = self._owed_part()
		self._rule(part, mode="suggest")
		self._settings(payment_gap_automatic=1)
		_statement, line, _o, _p = self._partial(sure=True)
		self.assertEqual((line.status, line.credit_note), ("Imported", None))
		self.assertEqual(self._owed("Sales Invoice", self.sales), owed)
		self.assertEqual(follow_up.get_gap_decision(line.bank_transaction)["rule_proposal"], "credit_note")

	def test_a_draft_rule_prepares_the_credit_note_and_the_card_validates_that_very_draft(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_rule
		owed, part = self._owed_part()
		rule = self._rule(part, mode="draft")
		with _only_for("tabSales Invoice Item` it", []):
			statement, line, _o, _p = self._partial()
		self.assertEqual((line.status, line.payment_gap_rule), ("Imported", rule.name))
		draft = line.credit_note
		self.assertEqual(frappe.db.get_value("Sales Invoice", draft, "docstatus"), 0)
		self.assertEqual(self._owed("Sales Invoice", self.sales), owed)
		decision = follow_up.get_gap_decision(line.bank_transaction)
		self.assertEqual(decision["draft"], {"name": draft, "total": flt(owed - part, 2)})
		with _only_for("tabSales Invoice Item` it", []):
			answer = follow_up.decide_gap(line.bank_transaction, "passed_gap", credit_note=1)
		self.assertEqual(answer["credit_note"], draft)
		self.assertEqual(frappe.db.get_value("Sales Invoice", draft, "docstatus"), 1)
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)

	def test_a_draft_that_is_out_of_date_is_replaced(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_rule
		owed, part = self._owed_part()
		self._rule(part, mode="draft")
		with _only_for("tabSales Invoice Item` it", []):
			_statement, line, _o, _p = self._partial()
			stale = line.credit_note
			frappe.db.set_value("Sales Invoice", stale, "grand_total", -1.0)
			answer = follow_up.decide_gap(line.bank_transaction, "passed_gap", credit_note=1)
		# Frappe hands the name of a deleted numbered document to the next one: what proves the stale draft is gone is that
		# the credit note which settled the invoice is submitted and carries the right amount, not the stale one
		made = frappe.db.get_value("Sales Invoice", answer["credit_note"], ["docstatus", "grand_total"], as_dict=True)
		self.assertEqual((made.docstatus, flt(made.grand_total, 2)), (1, -flt(owed - part, 2)))
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)
		self.assertEqual(frappe.db.count("Mint Bank Statement Import Transactions", {"credit_note": ("is", "set")}) >= 1, True)

	def test_the_account_of_the_rule_is_the_one_of_the_card_and_of_the_validation(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_cannot_make_a_rule
		# the company has no gap account of its own: only the rule names the account, and nobody picks it again
		_owed, part = self._owed_part()
		income = frappe.db.get_value("Account", {"company": COMPANY, "root_type": "Income", "is_group": 0, "disabled": 0})
		self._settings(payment_gap_account=None)
		self._rule(part, mode="suggest", account=income)
		with _only_for("tabSales Invoice Item` it", []):
			_statement, line, _o, _p = self._partial()
			decision = follow_up.get_gap_decision(line.bank_transaction, credit_note=1)
			self.assertEqual((decision["blocker"], decision["account"], decision["can_pass"]), ("", income, True))
			answer = follow_up.decide_gap(line.bank_transaction, "passed_gap", credit_note=1)
		self.assertEqual(frappe.db.get_value("Sales Invoice Item", {"parent": answer["credit_note"]}, "income_account"), income)
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)

	# -- what Nora reads and does ------------------------------------------------------------------------------------------

	def _paid(self, *shares, closed=True):
		"""Invoices of the customer as if each had been paid at these shares (the latest first); `closed`: the rest was closed by
		something else than a payment (a credit note), else it is still owed."""
		return [
			frappe._dict(name=f"INV-{i}", grand_total=100.0, outstanding_amount=0.0 if closed else 100.0 * (1 - share), paid=100.0 * share)
			for i, share in enumerate(shares)
		]

	def test_the_usual_share_is_the_one_most_invoices_agree_on(self):
		with patch.object(gap_credit_note, "_paid_invoices", return_value=self._paid(0.8, 0.5, 0.79, 1.0, 0.81, 1.0)):
			share = gap_credit_note.usual_share(COMPANY, self._customer())
		self.assertAlmostEqual(share, 0.8, places=1)
		# invoices paid in full say nothing about a customer who pays less; no invoice at all says nothing either
		with patch.object(gap_credit_note, "_paid_invoices", return_value=self._paid(1.0, 1.0)):
			self.assertIsNone(gap_credit_note.usual_share(COMPANY, self._customer()))
		with patch.object(gap_credit_note, "_paid_invoices", return_value=[]):
			self.assertIsNone(gap_credit_note.usual_share(COMPANY, self._customer()))

	def test_the_overview_tells_the_rule_the_habit_and_the_credit_note(self):
		with patch.object(gap_credit_note, "_paid_invoices", return_value=self._paid(0.8, 0.8, 0.8, 0.5)):
			told = gap_rule.overview(COMPANY, self._customer())
		self.assertFalse(told["rule"]["exists"])
		self.assertEqual((told["habit"]["share"], told["habit"]["same_share"]), (80.0, 3))
		self.assertIn("account", told["credit_note"])

	def test_the_plan_takes_the_share_of_the_habit_and_refuses_what_the_document_would_refuse(self):
		customer = self._customer()
		with patch.object(gap_credit_note, "_paid_invoices", return_value=self._paid(0.8, 0.8, 0.8, closed=False)):
			fine = gap_rule.plan(COMPANY, customer, "draft", "credit_note", account=GAP_ACCOUNT)
			# the rest of those invoices is still owed: nothing confirms the handling yet, so no level by itself
			refused = gap_rule.plan(COMPANY, customer, "automatic", "credit_note", account=GAP_ACCOUNT)
		self.assertEqual((fine["change"], fine["share"], fine["share_from_habit"], fine["problems"]), ("create", 80.0, True, []))
		self.assertEqual((fine["habit"]["same_share"], fine["habit"]["closed_by_credit"]), (3, 0))
		self.assertTrue(refused["problems"])
		self.assertFalse(refused["automatic_available"])
		with patch.object(gap_credit_note, "_paid_invoices", return_value=self._paid(0.8, 0.8, 0.8, closed=True)):
			# three invoices at that share that ended as a credit note: the handling was confirmed three times by the office
			allowed = gap_rule.plan(COMPANY, customer, "automatic", "credit_note", account=GAP_ACCOUNT)
		self.assertEqual((allowed["problems"], allowed["automatic_available"], allowed["confirmed_times"]), ([], True, 3))
		bad = gap_rule.plan(COMPANY, customer, "teleport", "credit_note")
		self.assertTrue(bad["problems"])
		self.assertFalse(frappe.db.exists("Payment Gap Rule", {"customer": customer}))

	def test_apply_makes_the_rule_and_changes_it_and_the_share_said_replaces_the_usual_one(self):
		with patch.object(gap_credit_note, "_paid_invoices", return_value=self._paid(0.8, 0.8, 0.8)):
			made = gap_rule.apply(COMPANY, self._customer(), "suggest", "credit_note", account=GAP_ACCOUNT)
			self.assertEqual((made["mode"], made["share"]), ("suggest", 80.0))
			changed = gap_rule.apply(COMPANY, self._customer(), "draft", "credit_note", share=75)
		self.assertEqual((changed["mode"], changed["share"]), ("draft", 75.0))
		self.assertEqual(frappe.db.count("Payment Gap Rule", {"customer": self._customer()}), 1)

	def test_apply_without_a_share_and_without_a_habit_is_refused_in_a_sentence(self):
		with patch.object(gap_credit_note, "_paid_invoices", return_value=[]):
			with self.assertRaises(frappe.ValidationError):
				gap_rule.apply(COMPANY, self._customer(), "draft", "credit_note")
		self.assertFalse(frappe.db.exists("Payment Gap Rule", {"customer": self._customer()}))

	# -- the rights --------------------------------------------------------------------------------------------------------

	def test_somebody_without_the_right_cannot_make_a_rule(self):
		_statement, line, _owed, _part = self._partial()
		with as_role("Guest"):
			with self.assertRaises(frappe.PermissionError):
				follow_up.set_gap_rule(line.bank_transaction, "suggest")
