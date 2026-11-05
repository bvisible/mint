# //// Neoffice — added file (no upstream equivalent).
# ////
# //// A PAYMENT ENTRY MADE FROM A BANK LINE BOOKS THE RATE OF THE DAY, NOT 1.
# ////
# //// Mint built the Payment Entry of a bank line with source_exchange_rate = target_exchange_rate = 1 and
# //// the base amounts equal to the amount of the line, the bulk path in the server, the single path in the
# //// SPA's own defaults. With a CHF bank line and a customer account in EUR that books 210.53 EUR as
# //// 210.53 CHF, and nothing ever shows the exchange gain or loss. ERPNext fixed it in v16
# //// (frappe/erpnext#59144, set_multi_currency_amounts); v15-hotfix did not receive it.
# //// Played on real data: a CHF bank account of the site, a EUR customer account, a rate the test creates.

import unittest

import frappe
from frappe.tests.roles import as_role
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from mint.apis import bank_reconciliation

RATE = 0.95
CUSTOMER = "MINT FX TEST CUSTOMER"


class TestPaymentEntryOfABankLineKeepsItsCurrency(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		line = cls._an_unreconciled_line("deposit")
		if not line:
			raise unittest.SkipTest("no unreconciled bank line on this site")
		cls.company = line.company
		company_currency = frappe.get_cached_value("Company", cls.company, "default_currency")
		bank_currency = frappe.get_cached_value("Account", cls._bank_account_of(line), "account_currency")
		cls.eur_account = frappe.get_all(
			"Account",
			filters={"company": cls.company, "account_currency": "EUR", "account_type": "Receivable", "is_group": 0},
			pluck="name",
			limit=1,
		)
		if not cls.eur_account or company_currency != "CHF" or bank_currency != "CHF":
			raise unittest.SkipTest("needs a CHF company and bank account and a EUR receivable account")
		cls.eur_account = cls.eur_account[0]
		if not frappe.db.exists("Customer", CUSTOMER):
			frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": CUSTOMER,
					"customer_group": frappe.get_all("Customer Group", filters={"is_group": 0}, pluck="name", limit=1)[0],
					"territory": frappe.get_all("Territory", filters={"is_group": 0}, pluck="name", limit=1)[0],
				}
			).insert()

	@staticmethod
	def _bank_account_of(line):
		return frappe.get_cached_value("Bank Account", line.bank_account, "account")

	@staticmethod
	def _an_unreconciled_line(side):
		rows = frappe.get_all(
			"Bank Transaction",
			filters={"docstatus": 1, "status": "Unreconciled", side: [">", 0]},
			fields=["name", "bank_account", "company", "date", "unallocated_amount", side],
			order_by="date desc",
			limit=1,
		)
		return rows[0] if rows else None

	def _a_line(self, side):
		"""A bank line nobody has reconciled yet, with the rate of its day: one per test, a test uses its line up."""
		frappe.set_user("Administrator")
		line = self._an_unreconciled_line(side)
		if not line:
			self.skipTest(f"no unreconciled {side} left on this site")
		frappe.get_doc(
			{
				"doctype": "Currency Exchange",
				"date": line.date,
				"from_currency": "EUR",
				"to_currency": "CHF",
				"exchange_rate": RATE,
				"for_buying": 1,
				"for_selling": 1,
			}
		).insert(ignore_if_duplicate=True)
		return line

	def _make(self, line):
		with as_role("accountant"):
			return bank_reconciliation.create_bulk_payment_entry_and_reconcile(
				[line.name], "Customer", CUSTOMER, self.eur_account
			)[0]["payment_entry"]

	def test_a_eur_customer_paying_into_a_chf_account_is_booked_at_the_rate_of_the_day(self):
		line = self._a_line("deposit")
		pe = self._make(line)
		amount = flt(line.unallocated_amount)
		self.assertEqual(pe.payment_type, "Receive")
		self.assertEqual(flt(pe.source_exchange_rate), RATE)  # the EUR receivable, to CHF
		self.assertEqual(flt(pe.target_exchange_rate), 1)  # the CHF bank account
		self.assertEqual(flt(pe.received_amount), amount)  # what the bank says, in CHF
		self.assertEqual(flt(pe.paid_amount), flt(amount / RATE, 2))  # what the customer paid, in EUR
		self.assertAlmostEqual(flt(pe.base_paid_amount), amount, delta=0.01)

	def test_a_refund_from_a_chf_account_to_a_eur_customer_is_booked_at_the_rate_of_the_day(self):
		line = self._a_line("withdrawal")
		pe = self._make(line)
		amount = flt(line.unallocated_amount)
		self.assertEqual(pe.payment_type, "Pay")
		self.assertEqual(flt(pe.source_exchange_rate), 1)  # the CHF bank account
		self.assertEqual(flt(pe.target_exchange_rate), RATE)  # the EUR receivable, to CHF
		self.assertEqual(flt(pe.paid_amount), amount)  # what the bank says, in CHF
		self.assertEqual(flt(pe.received_amount), flt(amount / RATE, 2))  # what the customer gets, in EUR
		self.assertAlmostEqual(flt(pe.base_received_amount), amount, delta=0.01)

	def test_the_single_path_with_the_defaults_the_spa_posts_is_booked_at_the_rate_of_the_day(self):
		line = self._a_line("deposit")
		amount = flt(line.unallocated_amount)
		# What RecordPaymentModal posts: both rates 1, and every amount the amount of the line.
		payload = {
			"payment_type": "Receive",
			"company": line.company,
			"party_type": "Customer",
			"party": CUSTOMER,
			"bank_account": line.bank_account,
			"paid_from": self.eur_account,
			"paid_to": self._bank_account_of(line),
			"paid_amount": amount,
			"base_paid_amount": amount,
			"received_amount": amount,
			"base_received_amount": amount,
			"target_exchange_rate": 1,
			"source_exchange_rate": 1,
			"posting_date": line.date,
			"reference_date": line.date,
			"reference_no": "MINT-FX",
			"references": [],
		}
		with as_role("accountant"):
			pe = bank_reconciliation.create_payment_entry_and_reconcile(line.name, payload)["payment_entry"]
		self.assertEqual(flt(pe.source_exchange_rate), RATE)
		self.assertEqual(flt(pe.received_amount), amount)
		self.assertEqual(flt(pe.paid_amount), flt(amount / RATE, 2))

	def test_the_line_is_reconciled_with_the_entry_it_made(self):
		deposit = self._a_line("deposit")
		made = self._make(deposit)
		line = frappe.get_doc("Bank Transaction", deposit.name)
		self.assertEqual([row.payment_entry for row in line.payment_entries], [made.name])
		self.assertEqual(line.status, "Reconciled")


class TestSetMultiCurrencyAmounts(unittest.TestCase):
	"""The helper alone, off the database: the currencies and the rate are stood in for."""

	CURRENCIES = {"Company": "CHF", "bank-chf": "CHF", "party-chf": "CHF", "bank-eur": "EUR", "party-eur": "EUR"}

	def _run(self, **entry):
		from types import SimpleNamespace
		from unittest.mock import patch

		pe = SimpleNamespace(company="Company", posting_date="2026-03-10", precision=lambda field: 2, **entry)
		with (
			patch.object(frappe, "get_cached_value", lambda doctype, name, field: self.CURRENCIES[name if doctype == "Account" else doctype]),
			patch("erpnext.setup.utils.get_exchange_rate", return_value=self.rate),
		):
			bank_reconciliation.set_multi_currency_amounts(pe)
		return pe

	rate = RATE

	def test_everything_in_the_currency_of_the_company_is_left_exactly_as_posted(self):
		# the SPA posts the amounts of a payment with deductions: they differ, and must stay so
		pe = self._run(payment_type="Receive", paid_from="party-chf", paid_to="bank-chf", paid_amount=100.0, received_amount=98.0, source_exchange_rate=1, target_exchange_rate=1)
		self.assertEqual((pe.paid_amount, pe.received_amount, pe.source_exchange_rate, pe.target_exchange_rate), (100.0, 98.0, 1, 1))

	def test_two_accounts_in_the_same_foreign_currency_get_its_rate_and_keep_their_amounts(self):
		pe = self._run(payment_type="Pay", paid_from="bank-eur", paid_to="party-eur", paid_amount=100.0, received_amount=100.0)
		self.assertEqual((pe.source_exchange_rate, pe.target_exchange_rate), (RATE, RATE))
		self.assertEqual((pe.paid_amount, pe.received_amount), (100.0, 100.0))

	def test_a_missing_rate_does_not_divide_by_zero(self):
		self.rate = 0
		try:
			pe = self._run(payment_type="Receive", paid_from="party-eur", paid_to="bank-chf", paid_amount=200.0, received_amount=200.0)
		finally:
			self.rate = RATE
		self.assertEqual(pe.paid_amount, 200.0)  # untouched: Payment Entry refuses a zero rate by itself

	def test_an_entry_without_accounts_is_left_alone(self):
		pe = self._run(payment_type="Receive", paid_from=None, paid_to=None, paid_amount=5.0, received_amount=5.0)
		self.assertFalse(hasattr(pe, "source_exchange_rate"))
