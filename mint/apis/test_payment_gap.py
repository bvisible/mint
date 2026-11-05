# //// Neoffice — added file (no upstream equivalent).
# ////
# //// WHAT A PAYMENT IS TO THE INVOICE IT SETTLES: THE VERDICTS, WHEN THEY MAY BE PASSED BY THEMSELVES, AND THE ENTRY.
# ////
# //// Played on real invoices of the site, with the settings of the company set in the test's transaction. The
# //// entries are made the way the bank statement import makes them: by the system, nobody in front of the screen
# //// (hence the `role-check` on the tests that book).

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, flt, nowdate

from mint.apis import payment_gap

COMPANY = "AlpInnovate SA"
LEDGER = "1020 - Compte courant Banques CHF - pri"
GAP_ACCOUNT = "3295 - Pertes sur clients, variation de prix - pri"
FREE_OF_TERMS = (
	"not exists (select 1 from `tabPayment Schedule` ps where ps.parent = inv.name and ps.discount > 0)"
)


def _an_invoice(doctype: str, at_least: float, **extra):
	conditions = [
		"inv.docstatus = 1",
		f"inv.outstanding_amount >= {at_least}",
		f"inv.company = '{COMPANY}'",
		"inv.currency = 'CHF'",
		FREE_OF_TERMS,
	] + [f"inv.{field} {condition}" for field, condition in extra.items()]
	rows = frappe.db.sql(
		f"select inv.name from `tab{doctype}` inv where {' and '.join(conditions)} order by inv.creation desc limit 1"
	)
	return rows[0][0] if rows else None


class TestPaymentGap(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.sales = _an_invoice("Sales Invoice", 200, total_taxes_and_charges="> 0", scor_reference="is not null")
		cls.purchase = _an_invoice("Purchase Invoice", 100, is_proposed="= 0")
		if not (cls.sales and cls.purchase):
			raise unittest.SkipTest("needs an open sales invoice with VAT and a SCOR reference and an open purchase invoice")

	def setUp(self):
		# Each test has the invoices as the site has them: what one books, the next does not see.
		frappe.db.savepoint("payment_gap_test")
		self._settings()

	def tearDown(self):
		frappe.db.rollback(save_point="payment_gap_test")
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

	def _outstanding(self, doctype, name):
		return flt(frappe.db.get_value(doctype, name, "outstanding_amount"), 2)

	def _judge(self, doctype, name, amount, reference=None):
		return payment_gap.judge(doctype, name, amount, nowdate(), reference)

	# -- the verdicts ---------------------------------------------------------------------------------------------

	def test_to_the_cent_is_exact_and_always_automatic(self):
		owed = self._outstanding("Sales Invoice", self.sales)
		for amount in (owed, owed - 0.01, owed + 0.01):
			verdict = self._judge("Sales Invoice", self.sales, amount)
			self.assertEqual((verdict.kind, verdict.automatic), ("exact", True))

	def test_a_few_centimes_either_way_are_a_rounding(self):
		owed = self._outstanding("Sales Invoice", self.sales)
		for amount in (owed - 0.03, owed + 0.04):
			self.assertEqual(self._judge("Sales Invoice", self.sales, amount).kind, "rounding")
		self.assertEqual(self._judge("Sales Invoice", self.sales, owed - 0.06).kind, "partial")

	def test_more_than_owed_is_never_passed_by_itself(self):
		self._settings(payment_gap_automatic=1, payment_gap_partial_automatic=1)
		verdict = self._judge("Sales Invoice", self.sales, self._outstanding("Sales Invoice", self.sales) + 9.25)
		self.assertEqual((verdict.kind, verdict.automatic), ("overpaid", False))
		self.assertTrue(verdict.reason)

	def test_nothing_is_automatic_until_the_company_switches_it_on(self):
		owed = self._outstanding("Sales Invoice", self.sales)
		off = self._judge("Sales Invoice", self.sales, owed - 0.03)
		self.assertEqual((off.kind, off.automatic), ("rounding", False))
		self._settings(payment_gap_automatic=1)
		self.assertTrue(self._judge("Sales Invoice", self.sales, owed - 0.03).automatic)

	def test_a_rebate_is_accepted_within_the_percentage_and_the_cap_on_sales_only(self):
		self._settings(payment_gap_automatic=1, accepted_rebate_percent=5, accepted_rebate_cap=500)
		owed = self._outstanding("Sales Invoice", self.sales)
		four_percent = flt(owed * 0.96, 2)
		verdict = self._judge("Sales Invoice", self.sales, four_percent)
		self.assertEqual((verdict.kind, verdict.automatic), ("accepted_rebate", True))
		# beyond the percentage, beyond the cap, and a setting left at 0: a partial payment
		self.assertEqual(self._judge("Sales Invoice", self.sales, flt(owed * 0.90, 2)).kind, "partial")
		self._settings(payment_gap_automatic=1, accepted_rebate_percent=5, accepted_rebate_cap=1)
		self.assertEqual(self._judge("Sales Invoice", self.sales, four_percent).kind, "partial")
		self._settings(payment_gap_automatic=1, accepted_rebate_percent=5, accepted_rebate_cap=0)
		self.assertEqual(self._judge("Sales Invoice", self.sales, four_percent).kind, "partial")
		# a supplier is never granted a rebate by us
		self._settings(payment_gap_automatic=1, accepted_rebate_percent=5, accepted_rebate_cap=500)
		owed_purchase = self._outstanding("Purchase Invoice", self.purchase)
		self.assertEqual(self._judge("Purchase Invoice", self.purchase, flt(owed_purchase * 0.96, 2)).kind, "partial")

	def test_a_partial_payment_is_validated_by_itself_only_when_the_invoice_is_certain(self):
		self._settings(payment_gap_automatic=1, payment_gap_partial_automatic=1)
		half = flt(self._outstanding("Sales Invoice", self.sales) / 2, 2)
		scor = frappe.db.get_value("Sales Invoice", self.sales, "scor_reference")
		sure = self._judge("Sales Invoice", self.sales, half, reference=scor)
		self.assertEqual((sure.kind, sure.sure, sure.automatic), ("partial", True, True))
		# the name of the invoice in the text of the line is not a certainty
		by_name = self._judge("Sales Invoice", self.sales, half, reference=f"Payment {self.sales}")
		self.assertEqual((by_name.sure, by_name.automatic), (False, False))
		# a person's switch left off
		self._settings(payment_gap_automatic=1, payment_gap_partial_automatic=0)
		self.assertFalse(self._judge("Sales Invoice", self.sales, half, reference=scor).automatic)

	def test_the_early_discount_of_the_terms_is_recognised_inside_its_window(self):
		invoice = self._with_a_discount(self.purchase, percent=3, days=10)
		owed = self._outstanding("Purchase Invoice", invoice)
		net = flt(owed * 0.97, 2)
		self._settings(payment_gap_automatic=1)
		no_account = self._judge("Purchase Invoice", invoice, net)
		self.assertEqual((no_account.kind, no_account.automatic), ("early_discount", False))
		frappe.db.set_value("Company", COMPANY, "default_discount_account", GAP_ACCOUNT)
		frappe.clear_document_cache("Company", COMPANY)
		verdict = self._judge("Purchase Invoice", invoice, net)
		self.assertEqual((verdict.kind, verdict.automatic), ("early_discount", True))
		self.assertAlmostEqual(verdict.discount, flt(owed - net, 2), places=2)
		# the same sum a day after the window is a partial payment
		late = payment_gap.judge("Purchase Invoice", invoice, net, add_days(nowdate(), 30))
		self.assertEqual(late.kind, "partial")

	def _with_a_discount(self, name, percent, days):
		"""The invoice, with a payment term that grants `percent` % within `days` days (in the test's transaction)."""
		row = frappe.get_all("Payment Schedule", filters={"parent": name}, pluck="name", limit=1)
		if not row:
			self.skipTest("the invoice has no payment schedule")
		frappe.db.set_value(
			"Payment Schedule",
			row[0],
			{"discount_type": "Percentage", "discount": percent, "discount_date": add_days(nowdate(), days)},
		)
		return name

	# -- the entry --------------------------------------------------------------------------------------------------

	def _book(self, doctype, name, amount, reference="REF-1"):
		verdict = payment_gap.judge(doctype, name, amount, nowdate(), reference)
		entry = payment_gap.book(verdict, doctype, name, LEDGER, nowdate(), reference, "gap test")
		return frappe.get_doc("Payment Entry", entry), verdict

	def test_a_rounding_on_a_sale_settles_the_invoice_with_the_gap_as_a_deduction(self):  # role-check: ok the import runs as the system
		self._settings(payment_gap_automatic=1)
		owed = self._outstanding("Sales Invoice", self.sales)
		entry, verdict = self._book("Sales Invoice", self.sales, owed - 0.03)
		self.assertEqual(flt(entry.paid_amount), flt(owed - 0.03, 2))
		self.assertEqual(self._outstanding("Sales Invoice", self.sales), 0)
		self.assertEqual([(d.account, flt(d.amount, 2)) for d in entry.deductions], [(GAP_ACCOUNT, 0.03)])

	def test_a_rounding_on_a_sale_paid_a_little_too_much_is_a_negative_deduction(self):  # role-check: ok the import runs as the system
		self._settings(payment_gap_automatic=1)
		owed = self._outstanding("Sales Invoice", self.sales)
		entry, _verdict = self._book("Sales Invoice", self.sales, owed + 0.04)
		self.assertEqual(self._outstanding("Sales Invoice", self.sales), 0)
		self.assertEqual([flt(d.amount, 2) for d in entry.deductions], [-0.04])

	def test_a_rounding_on_a_purchase_settles_the_invoice_too(self):  # role-check: ok the import runs as the system
		self._settings(payment_gap_automatic=1)
		owed = self._outstanding("Purchase Invoice", self.purchase)
		entry, _verdict = self._book("Purchase Invoice", self.purchase, owed - 0.03)
		self.assertEqual(entry.payment_type, "Pay")
		self.assertEqual(flt(entry.paid_amount), flt(owed - 0.03, 2))
		self.assertEqual(self._outstanding("Purchase Invoice", self.purchase), 0)
		self.assertEqual([flt(d.amount, 2) for d in entry.deductions], [-0.03])

	def test_an_accepted_rebate_settles_the_invoice_and_cuts_the_vat_from_the_account(self):  # role-check: ok the import runs as the system
		self._settings(payment_gap_automatic=1, accepted_rebate_percent=5, accepted_rebate_cap=500)
		owed = self._outstanding("Sales Invoice", self.sales)
		paid = flt(owed * 0.96, 2)
		entry, verdict = self._book("Sales Invoice", self.sales, paid)
		self.assertEqual(verdict.kind, "accepted_rebate")
		self.assertEqual(flt(entry.paid_amount), paid)
		self.assertEqual(self._outstanding("Sales Invoice", self.sales), 0)
		# the net of the gap and its VAT make the whole gap
		self.assertAlmostEqual(sum(flt(d.amount) for d in entry.deductions), flt(owed - paid, 2), places=2)
		self.assertEqual(entry.deductions[0].account, GAP_ACCOUNT)

	def test_a_partial_payment_is_recorded_for_what_came_in_and_the_rest_stays_open(self):  # role-check: ok the import runs as the system
		self._settings(payment_gap_automatic=1, payment_gap_partial_automatic=1)
		owed = self._outstanding("Sales Invoice", self.sales)
		half = flt(owed / 2, 2)
		scor = frappe.db.get_value("Sales Invoice", self.sales, "scor_reference")
		entry, verdict = self._book("Sales Invoice", self.sales, half, reference=scor)
		self.assertEqual(verdict.kind, "partial")
		self.assertEqual(flt(entry.paid_amount), half)
		self.assertEqual(self._outstanding("Sales Invoice", self.sales), flt(owed - half, 2))
		self.assertEqual(len(entry.deductions), 0)

	def test_the_early_discount_is_taken_once_and_the_entry_pays_what_the_bank_moved(self):  # role-check: ok the import runs as the system
		invoice = self._with_a_discount(self.purchase, percent=3, days=10)
		frappe.db.set_value("Company", COMPANY, "default_discount_account", GAP_ACCOUNT)
		frappe.clear_document_cache("Company", COMPANY)
		self._settings(payment_gap_automatic=1)
		owed = self._outstanding("Purchase Invoice", invoice)
		net = flt(owed * 0.97, 2)
		entry, verdict = self._book("Purchase Invoice", invoice, net)
		self.assertEqual(verdict.kind, "early_discount")
		# ERPNext keeps four decimals on the entry; the ledger posts the cent
		self.assertAlmostEqual(flt(entry.paid_amount), net, delta=0.01)
		self.assertEqual(self._outstanding("Purchase Invoice", invoice), 0)
		self.assertEqual([d.account for d in entry.deductions], [GAP_ACCOUNT])

	def test_what_is_not_automatic_is_not_booked(self):  # role-check: ok the import runs as the system, and here it books nothing
		owed = self._outstanding("Sales Invoice", self.sales)
		with self.assertRaises(frappe.ValidationError):
			self._book("Sales Invoice", self.sales, owed - 0.03)  # nothing switched on
		self._settings(payment_gap_automatic=1)
		with self.assertRaises(frappe.ValidationError):
			self._book("Sales Invoice", self.sales, owed + 9.25)  # overpaid
