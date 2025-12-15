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
		document_status: DF.Literal["Draft", "Submitted", "Cancelled"]
		error: DF.Code | None
		file: DF.Attach | None
		file_type: DF.Literal["PDF"]
		ocr_status: DF.Literal["", "Pending", "Processing", "Completed", "Failed"]
		status: DF.Literal["Not Started", "Completed", "Error"]
		transactions: DF.Table[MintBankStatementImportTransactions]
	# end: auto-generated types

	def update_document_status(self):
		"""Update document_status field based on docstatus."""
		status_map = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
		self.document_status = status_map.get(self.docstatus, "Draft")

	def before_validate(self):
		# Update document_status based on docstatus
		self.update_document_status()
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
		# Update document_status to Submitted
		self.db_set("document_status", "Submitted")

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

		# Update linked Document Scan status to Processed
		if self.document_scan_name:
			frappe.db.set_value("Document Scan", self.document_scan_name, "status", "Processed")
