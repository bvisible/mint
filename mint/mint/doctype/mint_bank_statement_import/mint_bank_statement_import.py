# Copyright (c) 2025, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MintBankStatementImport(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from mint.mint.doctype.mint_bank_statement_import_transactions.mint_bank_statement_import_transactions import MintBankStatementImportTransactions

		amended_from: DF.Link | None
		bank_account: DF.Link
		document_scan_name: DF.Link | None
		error: DF.Code | None
		file: DF.Attach | None
		file_type: DF.Literal["PDF"]
		ocr_status: DF.Literal["", "Pending", "Processing", "Completed", "Failed"]
		status: DF.Literal["Not Started", "Completed", "Error"]
		transactions: DF.Table[MintBankStatementImportTransactions]
	# end: auto-generated types

	def before_validate(self):
		# For all string amounts, compute the actual amount and type
		for transaction in self.transactions:
			if transaction.string_amount:
				amount, tx_type = self.parse_string_amount(transaction.string_amount)
				transaction.amount = amount
				transaction.type = tx_type

	def parse_string_amount(self, string_amount: str):
		"""
		Parse the string amount and return the amount and type
		"""
		# If the string has "cr" - then it's a deposit. Else it's a withdrawal
		if "cr" in string_amount.lower():
			return string_amount.lower().replace("cr", "").replace(" ", ""), "Deposit"
		else:
			return string_amount.lower().replace("dr", "").replace(" ", ""), "Withdrawal"

	@frappe.whitelist()
	def process_file(self):
		"""
		Start async OCR processing for the PDF.
		Returns immediately - use check_processing_status() to poll for completion.
		"""
		if not self.file:
			frappe.throw(_("Please upload a file"))

		if self.file_type != "PDF":
			frappe.throw(_("Invalid file type"))

		# Start async processing
		return self.start_ocr_processing()

	@frappe.whitelist()
	def start_ocr_processing(self):
		"""
		Start async OCR processing via Document Scan.
		Returns immediately with status.
		"""
		from mint.apis.nora_ocr import create_document_scan_for_bank_statement

		if not self.file:
			frappe.throw(_("Please upload a file"))

		# Create Document Scan for bank statement (OCR runs in background)
		result = create_document_scan_for_bank_statement(self.file)

		if result.get("success"):
			self.document_scan_name = result.get("document_scan_name")
			self.ocr_status = "Processing"
			self.save()
			return {
				"status": "Processing",
				"document_scan_name": result.get("document_scan_name"),
				"message": _("OCR processing started")
			}
		else:
			self.ocr_status = "Failed"
			self.error = result.get("message")
			self.save()
			frappe.throw(result.get("message"))

	@frappe.whitelist()
	def check_processing_status(self):
		"""
		Check OCR processing status and populate transactions if completed.
		Called by frontend polling.
		"""
		from mint.apis.nora_ocr import check_document_scan_status

		if not self.document_scan_name:
			return {"status": "Not Started"}

		result = check_document_scan_status(self.document_scan_name)

		if result.get("status") == "Completed":
			# Populate transactions table
			transactions = result.get("transactions", [])
			self._populate_transactions(transactions)
			self.ocr_status = "Completed"
			self.status = "Completed"
			self.save()
			return {
				"status": "Completed",
				"count": len(transactions),
				"message": _("{0} transactions extracted").format(len(transactions))
			}

		elif result.get("status") == "Failed":
			self.ocr_status = "Failed"
			self.error = result.get("error")
			self.status = "Error"
			self.save()
			return {
				"status": "Failed",
				"error": result.get("error")
			}

		else:
			# Still processing
			return {"status": "Processing"}

	def _populate_transactions(self, transactions: list):
		"""
		Populate the transactions child table from extracted data.
		"""
		# Order the transactions by date
		transactions.sort(key=lambda x: frappe.utils.getdate(x.get("date")) if x.get("date") else frappe.utils.today())
		self.transactions = []
		for transaction in transactions:
			self.append("transactions", {
				"date": transaction.get("date"),
				"amount": transaction.get("amount"),
				"type": transaction.get("type"),
				"description": transaction.get("description")
			})
	
	def before_submit(self):
		# Validate all rows have an amount and a type
		for transaction in self.transactions:
			if not transaction.get("amount") or not transaction.get("type"):
				frappe.throw(_("All rows must have an amount and a type. Missing in row {0}").format(transaction.get("idx")))
		
	def on_submit(self):
		if not self.transactions:
			frappe.throw(_("No transactions found"))
		
		for transaction in self.transactions:
			bank_tx = frappe.get_doc({
				"doctype": "Bank Transaction",
				"date": transaction.get("date"),
				"status": "Unreconciled",
				"bank_account": self.bank_account,
				"withdrawal": transaction.get("amount") if transaction.get("type") == "Withdrawal" else 0,
				"deposit": transaction.get("amount") if transaction.get("type") == "Deposit" else 0,
				"description": transaction.get("description"),
				"reference_number": transaction.get("reference"),
			})
			bank_tx.insert()
			bank_tx.submit()
			transaction.imported = 1


		
