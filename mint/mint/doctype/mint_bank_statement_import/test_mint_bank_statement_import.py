# Copyright (c) 2025, The Commit Company (Algocode Technologies Pvt. Ltd.) and Contributors
# See license.txt

# //// Neoffice — imports needed by TestFindExistingPaymentEntry below (#1410, #1411): mocking
# //// frappe.db and reaching the importer module to test _find_existing_payment_entry directly.
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

# //// Neoffice — the importer module itself, so that TestFindExistingPaymentEntry reaches _find_existing_payment_entry (#1410, #1411).
from mint.mint.doctype.mint_bank_statement_import import mint_bank_statement_import as importer


class TestMintBankStatementImport(FrappeTestCase):
	pass


# //// Neoffice — added tests (#1410, #1411): how a statement line finds the Payment Entry that already stands for it.
# //// Everything below is mocked at the frappe.db boundary: it asserts WHICH questions the matcher asks the database,
# //// not what a particular site holds.
class TestFindExistingPaymentEntry(FrappeTestCase):
	DOCUMENT_NAME = "SUP-9999"  # what the statement analysis puts in `party_match`
	DISPLAY_NAME = "Fournisseur Démo AG"  # what the counterparty is called in the file and on the supplier

	def setUp(self):
		self.asked = []  # (doctype, filters) of every frappe.get_all on Payment Entry
		self.transaction = frappe._dict(
			date="2026-10-09", invoice_matches=None, party_match=self.DOCUMENT_NAME, party_name=self.DISPLAY_NAME
		)

		def get_all(doctype, *args, **kwargs):
			self.asked.append((doctype, kwargs.get("filters")))
			return [frappe._dict(name="PAY-DEMO-0001")] if doctype == "Payment Entry" else []

		def get_value(doctype, filters=None, fieldname="name", *args, **kwargs):
			# the supplier is found by its document name, never by `supplier_name` = document name
			if doctype == "Supplier" and filters == {"supplier_name": self.DOCUMENT_NAME}:
				return None
			if doctype == "Supplier" and filters == {"supplier_name": self.DISPLAY_NAME}:
				return self.DOCUMENT_NAME
			return None

		def exists(doctype, name=None, *args, **kwargs):
			return name if (doctype, name) == ("Supplier", self.DOCUMENT_NAME) else None

		for target, replacement in (
			(frappe, ("get_all", get_all)),
			(frappe.db, ("get_value", get_value)),
			(frappe.db, ("exists", exists)),
		):
			patcher = patch.object(target, replacement[0], replacement[1])
			patcher.start()
			self.addCleanup(patcher.stop)

	def _find(self, **kwargs):
		return importer._find_existing_payment_entry("BANKREF-1", self.transaction, 432.40, True, "AlpInnovate SA", **kwargs)

	def test_a_supplier_named_by_series_is_found_by_the_document_name_the_analysis_gives(self):
		self.assertEqual(self._find(), "PAY-DEMO-0001")
		filters = self.asked[-1][1]
		self.assertEqual(filters["party"], self.DOCUMENT_NAME)

	def test_a_supplier_known_by_its_display_name_is_still_found(self):
		self.transaction.party_match = None  # no analysis: only the name read in the file
		self.assertEqual(self._find(), "PAY-DEMO-0001")
		self.assertEqual(self.asked[-1][1]["party"], self.DOCUMENT_NAME)

	def test_the_lookup_is_on_validated_entries_unless_a_draft_is_asked_for(self):
		self._find()
		self.assertEqual(self.asked[-1][1]["docstatus"], 1)
		self._find(docstatus=0)
		self.assertEqual(self.asked[-1][1]["docstatus"], 0)


# //// Neoffice — added tests (#1490): the type of an import follows its file, whatever the browser saved first. Nothing is
# //// written: the document is built in memory and only its before_validate runs; the File lookup is answered here.
class TestFileTypeFollowsTheFile(FrappeTestCase):
	def setUp(self):
		self.file_names = {}  # file_url -> file_name of its File
		original = frappe.db.get_value

		def get_value(doctype, filters=None, *args, **kwargs):
			# only the File lookup is answered here; everything else (the meta of a doctype...) reaches the database
			if doctype == "File" and isinstance(filters, dict):
				return self.file_names.get(filters.get("file_url"))
			return original(doctype, filters, *args, **kwargs)

		patcher = patch.object(frappe.db, "get_value", get_value)
		patcher.start()
		self.addCleanup(patcher.stop)

	def _draft(self, file_url, saved_as="PDF"):
		doc = frappe.new_doc("Mint Bank Statement Import")
		doc.file = file_url
		doc.file_type = saved_as  # what the form saved before it read the file's name: the field's default
		doc.before_validate()
		return doc

	def test_a_camt_file_saved_as_pdf_becomes_xml(self):
		self.assertEqual(self._draft("/private/files/statement-october.xml").file_type, "XML")
		self.assertEqual(self._draft("/private/files/statement.CAMT053").file_type, "XML")

	def test_a_pdf_saved_as_xml_becomes_pdf(self):
		self.assertEqual(self._draft("/private/files/statement.pdf", saved_as="XML").file_type, "PDF")

	def test_a_url_without_a_suffix_reads_the_name_of_its_file(self):
		self.file_names["/private/files/abc123"] = "Statement November.xml"
		self.assertEqual(self._draft("/private/files/abc123").file_type, "XML")

	def test_a_name_that_says_nothing_keeps_the_type(self):
		self.assertEqual(self._draft("/private/files/statement.txt", saved_as="XML").file_type, "XML")
		self.assertEqual(importer.file_type_of(None), None)
