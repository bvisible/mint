# //// Neoffice — added file (no upstream equivalent).
# ////
# //// THE INVOICES A BANK LINE SETTLES WHEN THE IMPORT DID NOT NAME ONE: ONE AMOUNT FOR SEVERAL INVOICES, A REFERENCE THAT
# //// DOES NOT MATCH, AND THE PAYMENT PREPARED AS A DRAFT.
# ////
# //// Played on real invoices of the site, through the import, like the other tests of the follow-up of imports.

import frappe
from frappe.tests.roles import as_role
from frappe.utils import flt

from mint.apis import line_invoices, statement_follow_up as follow_up
from mint.apis.test_payment_gap_import import GapImportCase

IBAN = "CH93 0076 2011 6238 5295 7"

class TestLineInvoices(GapImportCase):
	def _customer(self):
		return frappe.db.get_value("Sales Invoice", self.sales, "customer")

	def _sibling(self, at_least=20):
		rows = frappe.db.sql_list(
			"""select name from `tabSales Invoice` where docstatus = 1 and company = %s and customer = %s and currency = 'CHF'
			and outstanding_amount > %s and is_return = 0 and name != %s order by outstanding_amount limit 1""",
			(frappe.db.get_value("Sales Invoice", self.sales, "company"), self._customer(), at_least, self.sales),
		)
		if not rows:
			self.skipTest("needs a second open invoice of the same customer")
		return rows[0]

	def _bank_line(self, amount, invoices=(), party_match=None, party_name=None, iban=""):
		line = self._line("Sales Invoice", self.sales, amount)
		line["invoice_matches"] = str(list(invoices))
		line["party_match"] = self._customer() if party_match is None else party_match
		line["party_name"] = party_name if party_name is not None else self._customer()
		line["party_iban"] = iban
		statement = self._import(line)
		return statement.transactions[0].bank_transaction

	def _two(self):
		"""Two open invoices of the customer and what is owed on each."""
		other = self._sibling()
		a, b = self.sales, other
		owed_a = self._owed("Sales Invoice", a)
		owed_b = self._owed("Sales Invoice", b)
		return a, b, owed_a, owed_b

	# -- what the card is shown --------------------------------------------------------------------------------------------

	def test_a_line_with_no_invoice_shows_the_open_invoices_of_the_customer(self):
		owed = self._owed("Sales Invoice", self.sales)
		bank_line = self._bank_line(owed, invoices=[])
		shown = line_invoices.get_candidates(bank_line)
		self.assertEqual((shown["reason"], shown["party"], shown["party_source"], shown["show"]), ("none", self._customer(), "import", True))
		listed = {row["name"]: row for row in shown["invoices"]}
		self.assertIn(self.sales, listed)
		self.assertTrue(listed[self.sales]["same_amount"])

	def test_several_invoices_named_by_the_import_are_told_as_such(self):
		a, b, owed_a, owed_b = self._two()
		bank_line = self._bank_line(flt(owed_a + owed_b, 2), invoices=[a, b])
		shown = line_invoices.get_candidates(bank_line)
		self.assertEqual((shown["reason"], sorted(shown["recognised"])), ("several", sorted([a, b])))
		self.assertTrue(shown["show"])

	def test_the_reference_of_an_invoice_already_paid_is_told_and_its_open_sisters_offered(self):
		a, b, _owed_a, owed_b = self._two()
		# the recognised invoice is settled (as an invoice the customer already paid is)
		frappe.db.set_value("Sales Invoice", a, "outstanding_amount", 0)
		bank_line = self._bank_line(owed_b, invoices=[a])
		shown = line_invoices.get_candidates(bank_line)
		self.assertEqual((shown["reason"], shown["reference_hint"]), ("paid", a))
		# there is no gap to decide on an invoice that is no longer open: this card is the one that helps
		self.assertIsNone(follow_up.get_gap_decision(bank_line))
		self.assertTrue(shown["show"])
		listed = {row["name"]: row for row in shown["invoices"]}
		self.assertNotIn(a, listed)
		self.assertTrue(listed[b]["same_amount"])

	def test_a_payer_known_only_by_its_iban_is_found_by_it(self):
		customer = self._customer()
		owed = self._owed("Sales Invoice", self.sales)
		bank = frappe.db.get_value("Bank Account", self.bank_account, "bank")
		frappe.get_doc(
			{
				"doctype": "Bank Account",
				"account_name": f"{customer} IBAN test",
				"bank": bank,
				"is_company_account": 0,
				"party_type": "Customer",
				"party": customer,
				"iban": IBAN,
			}
		).insert()
		bank_line = self._bank_line(owed, invoices=[], party_match="", party_name="NOBODY KNOWS THIS NAME", iban=IBAN)
		shown = line_invoices.get_candidates(bank_line)
		self.assertEqual((shown["party"], shown["party_source"]), (customer, "iban"))

	def test_a_payer_nobody_knows_gets_the_search_for_the_party_when_the_reference_failed(self):
		a, _b, _owed_a, owed_b = self._two()
		frappe.db.set_value("Sales Invoice", a, "outstanding_amount", 0)
		bank_line = self._bank_line(owed_b, invoices=[a], party_match="", party_name="NOBODY KNOWS THIS NAME")
		shown = line_invoices.get_candidates(bank_line)
		# no party, so no invoice of anybody is listed: the person says who it is
		self.assertEqual((shown["reason"], shown["show"], shown["party"], shown["invoices"]), ("paid", True, None, []))
		chosen = line_invoices.get_candidates(bank_line, party=self._customer())
		self.assertEqual((chosen["party"], chosen["party_source"]), (self._customer(), "chosen"))
		self.assertIn(self.sales if self.sales != a else _b, [row["name"] for row in chosen["invoices"]])
		self.assertTrue(chosen["party_label"])

	def test_a_line_with_nobody_and_nothing_is_not_an_invoice_and_gets_no_card(self):
		# a sum paid to nothing, a fee, a private withdrawal: the buttons of the window (bank entry, transfer, payment) are for it
		owed = self._owed("Sales Invoice", self.sales)
		bank_line = self._bank_line(owed, invoices=[], party_match="", party_name="NOBODY KNOWS THIS NAME")
		shown = line_invoices.get_candidates(bank_line)
		self.assertEqual((shown["reason"], shown["party"], shown["show"]), ("none", None, False))

	def test_a_line_with_one_open_invoice_is_the_business_of_the_gap_card_not_of_this_one(self):
		# a payment that does not settle the invoice (the import passes an exact one by itself): the card of the gap is for it
		owed = self._owed("Sales Invoice", self.sales)
		bank_line = self._bank_line(flt(owed * 0.6, 2), invoices=[self.sales])
		shown = line_invoices.get_candidates(bank_line)
		self.assertEqual((shown["reason"], shown["show"]), ("open", False))

	# -- one amount, several invoices ---------------------------------------------------------------------------------------

	def test_one_payment_settles_two_invoices_as_split_and_reconciles_the_line(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_is_refused
		a, b, owed_a, owed_b = self._two()
		part_b = flt(owed_b / 2, 2)
		bank_line = self._bank_line(flt(owed_a + part_b, 2), invoices=[a, b])
		answer = line_invoices.settle(
			bank_line,
			[{"invoice": a, "amount": owed_a}, {"invoice": b, "amount": part_b}],
			self._customer(),
		)
		self.assertFalse(answer["draft"])
		entry = frappe.get_doc("Payment Entry", answer["payment_entry"])
		self.assertEqual(entry.docstatus, 1)
		self.assertEqual(
			sorted((r.reference_name, flt(r.allocated_amount, 2)) for r in entry.references),
			sorted([(a, owed_a), (b, part_b)]),
		)
		self.assertEqual(self._owed("Sales Invoice", a), 0)
		self.assertEqual(self._owed("Sales Invoice", b), flt(owed_b - part_b, 2))
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Reconciled")

	def test_the_split_must_add_up_to_the_payment_and_stay_within_what_is_owed(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_is_refused
		a, b, owed_a, owed_b = self._two()
		bank_line = self._bank_line(flt(owed_a + owed_b, 2), invoices=[a, b])
		customer = self._customer()
		with self.assertRaises(frappe.ValidationError):
			line_invoices.settle(bank_line, [{"invoice": a, "amount": owed_a}], customer)
		with self.assertRaises(frappe.ValidationError):
			line_invoices.settle(
				bank_line, [{"invoice": a, "amount": flt(owed_a + 1, 2)}, {"invoice": b, "amount": flt(owed_b - 1, 2)}], customer
			)
		with self.assertRaises(frappe.ValidationError):
			line_invoices.settle(bank_line, [{"invoice": a, "amount": owed_a}, {"invoice": a, "amount": owed_b}], customer)
		self.assertEqual(self._owed("Sales Invoice", a), owed_a)
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Unreconciled")

	def test_an_invoice_of_another_customer_is_refused(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_is_refused
		owed = self._owed("Sales Invoice", self.sales)
		bank_line = self._bank_line(owed, invoices=[])
		with self.assertRaises(frappe.ValidationError):
			line_invoices.settle(bank_line, [{"invoice": self.sales, "amount": owed}], "NOT THE CUSTOMER")

	# -- the draft -----------------------------------------------------------------------------------------------------------

	def test_a_draft_is_prepared_then_validated_and_reconciled_from_the_card(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_is_refused
		owed = self._owed("Sales Invoice", self.sales)
		bank_line = self._bank_line(owed, invoices=[])
		answer = line_invoices.settle(bank_line, [{"invoice": self.sales, "amount": owed}], self._customer(), draft=1)
		self.assertTrue(answer["draft"])
		name = answer["payment_entry"]
		self.assertEqual(frappe.db.get_value("Payment Entry", name, "docstatus"), 0)
		# nothing is booked: the invoice owes what it owed, the line waits
		self.assertEqual(self._owed("Sales Invoice", self.sales), owed)
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Unreconciled")
		shown = line_invoices.get_candidates(bank_line)
		self.assertEqual([d["name"] for d in shown["drafts"]], [name])
		self.assertEqual(shown["drafts"][0]["references"], [{"invoice": self.sales, "amount": owed}])
		self.assertTrue(shown["show"])
		line_invoices.submit_draft(bank_line, name)
		self.assertEqual(frappe.db.get_value("Payment Entry", name, "docstatus"), 1)
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Reconciled")

	def test_a_draft_validated_in_its_own_tab_is_only_reconciled(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_is_refused
		owed = self._owed("Sales Invoice", self.sales)
		bank_line = self._bank_line(owed, invoices=[])
		name = line_invoices.settle(bank_line, [{"invoice": self.sales, "amount": owed}], self._customer(), draft=1)["payment_entry"]
		frappe.get_doc("Payment Entry", name).submit()
		shown = line_invoices.get_candidates(bank_line)
		self.assertEqual(([d["name"] for d in shown["drafts"]], [d["name"] for d in shown["submitted"]]), ([], [name]))
		line_invoices.submit_draft(bank_line, name)
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Reconciled")
		self.assertEqual(frappe.db.count("Payment Entry", {"name": name, "docstatus": 1}), 1)

	def test_a_draft_is_deleted_and_only_a_draft_prepared_for_this_line(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_is_refused
		owed = self._owed("Sales Invoice", self.sales)
		bank_line = self._bank_line(owed, invoices=[])
		name = line_invoices.settle(bank_line, [{"invoice": self.sales, "amount": owed}], self._customer(), draft=1)["payment_entry"]
		other_line = self._bank_line(owed, invoices=[])
		with self.assertRaises(frappe.ValidationError):
			line_invoices.delete_draft(other_line, name)
		with self.assertRaises(frappe.ValidationError):
			line_invoices.submit_draft(other_line, name)
		self.assertTrue(line_invoices.delete_draft(bank_line, name))
		self.assertFalse(frappe.db.exists("Payment Entry", name))

	def test_a_draft_corrected_to_another_amount_is_refused_at_validation(self):  # role-check: ok the accountant's act, played as the system here; the rights are tested in test_somebody_without_the_right_is_refused
		owed = self._owed("Sales Invoice", self.sales)
		bank_line = self._bank_line(owed, invoices=[])
		name = line_invoices.settle(bank_line, [{"invoice": self.sales, "amount": owed}], self._customer(), draft=1)["payment_entry"]
		entry = frappe.get_doc("Payment Entry", name)
		entry.references[0].allocated_amount = flt(owed - 1, 2)
		entry.paid_amount = entry.received_amount = flt(owed - 1, 2)
		entry.save()
		with self.assertRaises(frappe.ValidationError):
			line_invoices.submit_draft(bank_line, name)
		self.assertEqual(frappe.db.get_value("Bank Transaction", bank_line, "status"), "Unreconciled")

	# -- the rights --------------------------------------------------------------------------------------------------------

	def test_somebody_without_the_right_is_refused(self):
		owed = self._owed("Sales Invoice", self.sales)
		bank_line = self._bank_line(owed, invoices=[])
		with as_role("Guest"):
			with self.assertRaises(frappe.PermissionError):
				line_invoices.get_candidates(bank_line)
			with self.assertRaises(frappe.PermissionError):
				line_invoices.settle(bank_line, [{"invoice": self.sales, "amount": owed}], self._customer())
