# //// Neoffice — added file (no upstream equivalent).
# ////
# //// WHAT THE MORNING IMPORT DOES WITH A LINE THAT DOES NOT SETTLE ITS INVOICE TO THE CENT.
# ////
# //// The statement import is played on real invoices of the site, with the settings of the company set inside each
# //// test's savepoint. The decider itself is covered by test_payment_gap; here it is the import's use of it: what
# //// the line says afterwards, what the invoice owes afterwards, and what the summary tells the person.

import unittest
import uuid

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, nowdate

from mint.apis.test_payment_gap import COMPANY, GAP_ACCOUNT, LEDGER, _an_invoice

# role-check: ok the statement import is a job of the system: nobody is in front of the screen when it runs


class TestPaymentGapImport(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.sales = _an_invoice("Sales Invoice", 200, total_taxes_and_charges="> 0", scor_reference="is not null")
		cls.purchase = _an_invoice("Purchase Invoice", 100, is_proposed="= 0")
		cls.bank_account = frappe.db.get_value("Bank Account", {"company": COMPANY, "account": LEDGER})
		if not (cls.sales and cls.purchase and cls.bank_account):
			raise unittest.SkipTest("needs open invoices of the company and its bank account on the ledger account")

	def setUp(self):
		frappe.db.savepoint("payment_gap_import_test")
		self._settings()

	def tearDown(self):
		frappe.db.rollback(save_point="payment_gap_import_test")
		frappe.clear_document_cache("Company", COMPANY)

	def _settings(self, **values):
		defaults = {
			"payment_gap_automatic": 0,
			"payment_gap_partial_automatic": 0,
			"rounding_tolerance": 0.05,
			"accepted_rebate_percent": 0,
			"accepted_rebate_cap": 0,
			"payment_gap_account": GAP_ACCOUNT,
		}
		frappe.db.set_value("Neoffice Company Settings", COMPANY, {**defaults, **values})

	def _owed(self, doctype, name):
		return flt(frappe.db.get_value(doctype, name, "outstanding_amount"), 2)

	def _line(self, invoice_type, invoice, amount, remittance_reference=""):
		receiving = invoice_type == "Sales Invoice"
		party_field = "customer" if receiving else "supplier"
		party = frappe.db.get_value(invoice_type, invoice, party_field)
		reference = f"GAPTEST-{uuid.uuid4().hex[:12]}"
		return {
			"date": nowdate(),
			"amount": amount,
			"type": "Deposit" if receiving else "Withdrawal",
			"description": "gap test",
			"reference": reference,
			"unique_reference": reference,
			"party_name": party,
			"credit_debit": "CRDT" if receiving else "DBIT",
			"status": "To Process",
			"invoice_matches": str([invoice]),
			"party_match": party,
			"remittance_reference": remittance_reference,
		}

	def _import(self, *lines):
		statement = frappe.get_doc(
			{
				"doctype": "Mint Bank Statement Import",
				"bank_account": self.bank_account,
				"file_type": "XML",
				"currency": "CHF",
				"transactions": list(lines),
			}
		).insert()
		statement._submit_xml_transactions()
		statement.reload()
		return statement

	# -- what the line becomes --------------------------------------------------------------------------------------

	def test_an_exact_line_is_the_old_path_and_carries_no_verdict(self):
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed))
		line = statement.transactions[0]
		self.assertEqual(line.status, "Paid")
		self.assertFalse(line.difference_kind)
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)

	def test_a_rounding_passes_by_itself_once_the_company_switched_it_on(self):
		self._settings(payment_gap_automatic=1)
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed - 0.03))
		line = statement.transactions[0]
		self.assertEqual((line.status, line.difference_kind, flt(line.difference_amount, 2)), ("Paid", "rounding", 0.03))
		self.assertTrue(line.payment_entry)
		self.assertEqual(self._owed("Sales Invoice", self.sales), 0)
		self.assertIn("1 passed with a gap", statement.import_summary)
		# the Bank Transaction is linked to the entry, as for any other line the import passes
		linked = frappe.get_all(
			"Bank Transaction Payments", filters={"payment_entry": line.payment_entry}, pluck="parent"
		)
		self.assertEqual(len(linked), 1)
		self.assertEqual(frappe.db.get_value("Bank Transaction", linked[0], "status"), "Reconciled")

	def test_with_the_switch_off_the_line_waits_with_its_verdict(self):
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed - 0.03))
		line = statement.transactions[0]
		self.assertEqual((line.status, line.difference_kind, flt(line.difference_amount, 2)), ("Imported", "rounding", 0.03))
		self.assertFalse(line.payment_entry)
		self.assertEqual(self._owed("Sales Invoice", self.sales), owed)
		self.assertIn("1 to decide", statement.import_summary)
		self.assertNotIn("passed with a gap", statement.import_summary)

	def test_an_overpayment_is_never_passed_by_itself(self):
		self._settings(payment_gap_automatic=1, payment_gap_partial_automatic=1)
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, owed + 5))
		line = statement.transactions[0]
		self.assertEqual((line.status, line.difference_kind, flt(line.difference_amount, 2)), ("Imported", "overpaid", -5.0))
		self.assertEqual(self._owed("Sales Invoice", self.sales), owed)

	def test_a_partial_payment_is_validated_when_the_reference_is_the_invoices_own(self):
		self._settings(payment_gap_automatic=1, payment_gap_partial_automatic=1)
		owed = self._owed("Sales Invoice", self.sales)
		scor = frappe.db.get_value("Sales Invoice", self.sales, "scor_reference")
		part = flt(owed / 2, 2)
		statement = self._import(self._line("Sales Invoice", self.sales, part, remittance_reference=scor))
		line = statement.transactions[0]
		self.assertEqual((line.status, line.difference_kind), ("Paid", "partial"))
		self.assertEqual(self._owed("Sales Invoice", self.sales), flt(owed - part, 2))

	def test_a_partial_payment_without_the_reference_waits_for_a_person(self):
		self._settings(payment_gap_automatic=1, payment_gap_partial_automatic=1)
		owed = self._owed("Sales Invoice", self.sales)
		statement = self._import(self._line("Sales Invoice", self.sales, flt(owed / 2, 2)))
		line = statement.transactions[0]
		self.assertEqual((line.status, line.difference_kind), ("Imported", "partial"))
		self.assertEqual(self._owed("Sales Invoice", self.sales), owed)

	def test_a_purchase_rounding_passes_on_a_debit(self):
		self._settings(payment_gap_automatic=1)
		owed = self._owed("Purchase Invoice", self.purchase)
		statement = self._import(self._line("Purchase Invoice", self.purchase, owed - 0.03))
		line = statement.transactions[0]
		self.assertEqual((line.status, line.difference_kind), ("Paid", "rounding"))
		self.assertEqual(self._owed("Purchase Invoice", self.purchase), 0)

	def test_the_summary_counts_what_passed_and_what_waits(self):
		self._settings(payment_gap_automatic=1)
		sales_owed = self._owed("Sales Invoice", self.sales)
		purchase_owed = self._owed("Purchase Invoice", self.purchase)
		statement = self._import(
			self._line("Sales Invoice", self.sales, sales_owed - 0.02),
			self._line("Purchase Invoice", self.purchase, purchase_owed + 7),
		)
		self.assertIn("1 passed with a gap", statement.import_summary)
		self.assertIn("1 to decide", statement.import_summary)
		self.assertEqual([line.status for line in statement.transactions], ["Paid", "Imported"])
