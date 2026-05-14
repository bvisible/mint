# Copyright (c) 2025, The Commit Company (Algocode Technologies Pvt. Ltd.) and contributors
# For license information, please see license.txt

import hashlib
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
		bank_statement_id: DF.Data | None
		closing_balance: DF.Currency | None
		content_hash: DF.Data | None
		currency: DF.Link | None
		document_scan_name: DF.Link | None
		document_status: DF.Literal["Draft", "Submitted", "Cancelled"]
		error: DF.Code | None
		file: DF.Attach | None
		file_type: DF.Literal["PDF", "XML"]
		import_summary: DF.SmallText | None
		ocr_status: DF.Literal["", "Pending", "Processing", "Completed", "Failed"]
		opening_balance: DF.Currency | None
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
		# Set currency from bank account (upstream fix)
		if self.bank_account and not self.currency:
			account = frappe.get_cached_value("Bank Account", self.bank_account, "account")
			if account:
				self.currency = frappe.get_cached_value("Account", account, "account_currency")
		# For PDF: compute actual amount and type from string amounts
		if self.file_type == "PDF":
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
		# Filter out transactions without a valid date (mandatory field)
		transactions = [tx for tx in transactions if tx.get("date")]
		# Order the transactions by date
		transactions.sort(key=lambda x: frappe.utils.getdate(x.get("date")))
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
			# No transactions at all — mark as completed
			self.db_set("status", "Completed")
			self.db_set("import_summary", _("No transactions to import"))
			return

		if self.file_type == "XML":
			self._submit_xml_transactions()
		else:
			self._submit_pdf_transactions()

	def _submit_pdf_transactions(self):
		"""Original PDF import flow — creates Bank Transactions directly."""
		for transaction in self.transactions:
			bank_tx = frappe.get_doc({
				"doctype": "Bank Transaction",
				"date": transaction.get("date"),
				"status": "Unreconciled",
				"bank_account": self.bank_account,
				"currency": self.currency,
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

		# Trigger the Mint rule engine so freshly imported transactions are
		# evaluated immediately (mirrors the CSV/XLSX flow in
		# mint.apis.statement_import.import_statement). Without this, they sit
		# with is_rule_evaluated=0 until the hourly scheduler picks them up.
		from mint.apis.rules import run_rule_evaluation
		run_rule_evaluation()

	def _submit_xml_transactions(self):
		"""XML import flow — creates Bank Transactions and Payment Entries automatically."""
		# Get company and account from bank account
		company = frappe.get_cached_value("Bank Account", self.bank_account, "company")
		account = frappe.get_cached_value("Bank Account", self.bank_account, "account")

		stats = {
			"total": 0,
			"created": 0,
			"duplicates": 0,
			"auto_matched": 0,
			"unreconciled": 0,
			"errors": 0,
		}

		for transaction in self.transactions:
			stats["total"] += 1
			is_withdrawal = transaction.credit_debit == "DBIT"
			amount = float(transaction.amount or 0)
			reference = transaction.unique_reference or transaction.reference or ""

			try:
				# Check for exact duplicates by reference (same batch reference = true duplicate)
				existing_bt = _find_existing_bank_transaction(
					self.bank_account,
					transaction.date,
					reference,
					amount,
					is_withdrawal,
				)
				if existing_bt:
					transaction.db_set("status", "Existing")
					transaction.db_set("existing_bank_transaction", existing_bt)
					stats["duplicates"] += 1
					continue

				# Create Bank Transaction
				bank_tx = frappe.get_doc({
					"doctype": "Bank Transaction",
					"date": transaction.date,
					"status": "Unreconciled",
					"bank_account": self.bank_account,
					"currency": self.currency,
					"withdrawal": amount if is_withdrawal else 0,
					"deposit": amount if not is_withdrawal else 0,
					"description": transaction.description,
					"reference_number": reference,
				})
				bank_tx.insert()
				bank_tx.submit()
				stats["created"] += 1

				# First: check if a Payment Entry already exists
				# (e.g. created by Payment Proposal before bank confirmation)
				existing_pe = _find_existing_payment_entry(
					reference, transaction, amount, is_withdrawal, company
				)

				if existing_pe:
					# PE already exists — link it (with clearance_date posting)
					bank_tx.reload()
					_link_payment_entry_to_bt(bank_tx, existing_pe, reconciliation_type="Matched")
					stats["auto_matched"] += 1
					transaction.db_set("status", "Paid")
					transaction.db_set("imported", 1)
					continue

				# Try to auto-create Payment Entry from invoice matches
				invoice_matches = transaction.invoice_matches
				party_match = transaction.party_match
				if invoice_matches and party_match:
					try:
						import ast
						matches = ast.literal_eval(invoice_matches) if isinstance(invoice_matches, str) else invoice_matches
						if matches and len(matches) == 1:
							# Single invoice match — auto-create PE only if exact amount
							invoice_name = matches[0]
							if not is_withdrawal:
								# Customer payment (CRDT)
								sinv = frappe.get_doc("Sales Invoice", invoice_name)
								if abs(amount - sinv.outstanding_amount) <= 0.01 and not frappe.db.exists("Payment Entry", {"reference_no": reference, "paid_amount": amount, "docstatus": 1}):
									pe = frappe.get_doc({
										"doctype": "Payment Entry",
										"payment_type": "Receive",
										"party_type": "Customer",
										"party": sinv.customer,
										"posting_date": transaction.date,
										"paid_to": account,
										"paid_amount": amount,
										"received_amount": amount,
										"reference_no": reference,
										"reference_date": transaction.date,
										"remarks": _("{0} - Payment for {1}").format(transaction.party_name or party_match, invoice_name),
										"references": [{
											"reference_doctype": "Sales Invoice",
											"reference_name": invoice_name,
											"allocated_amount": min(amount, sinv.outstanding_amount),
										}],
									})
									pe.insert()
									pe.submit()

									# Link PE to Bank Transaction (with clearance_date posting)
									bank_tx.reload()
									_link_payment_entry_to_bt(bank_tx, pe.name, reconciliation_type="Voucher Created")
									stats["auto_matched"] += 1
									transaction.db_set("status", "Paid")
									transaction.db_set("imported", 1)
									continue
							else:
								# Supplier payment (DBIT) — create PE if invoice has outstanding
								pinv = frappe.get_doc("Purchase Invoice", invoice_name)
								if pinv.outstanding_amount > 0 and not frappe.db.exists("Payment Entry", {"reference_no": reference, "paid_amount": amount, "docstatus": 1}):
									pe = frappe.get_doc({
										"doctype": "Payment Entry",
										"payment_type": "Pay",
										"party_type": "Supplier",
										"party": pinv.supplier,
										"posting_date": transaction.date,
										"paid_from": account,
										"paid_amount": amount,
										"received_amount": amount,
										"reference_no": reference,
										"reference_date": transaction.date,
										"remarks": _("{0} - Payment for {1}").format(transaction.party_name or party_match, invoice_name),
										"references": [{
											"reference_doctype": "Purchase Invoice",
											"reference_name": invoice_name,
											"allocated_amount": min(amount, pinv.outstanding_amount),
										}],
									})
									pe.insert()
									pe.submit()

									bank_tx.reload()
									_link_payment_entry_to_bt(bank_tx, pe.name, reconciliation_type="Voucher Created")
									stats["auto_matched"] += 1
									transaction.db_set("status", "Paid")
									transaction.db_set("imported", 1)
									continue
					except Exception as e:
						frappe.log_error("Auto Payment Entry creation failed", str(e))

				# No auto-match — mark as unreconciled for Mint
				transaction.db_set("status", "Imported")
				transaction.db_set("imported", 1)
				stats["unreconciled"] += 1

			except Exception as e:
				transaction.db_set("status", "Error")
				frappe.log_error("Bank Transaction import error", str(e))
				stats["errors"] += 1

		# Build summary
		summary_parts = [
			_("{0} transactions processed").format(stats["total"]),
			_("{0} created").format(stats["created"]),
		]
		if stats["duplicates"]:
			summary_parts.append(_("{0} duplicates skipped").format(stats["duplicates"]))
		if stats["auto_matched"]:
			summary_parts.append(_("{0} auto-matched").format(stats["auto_matched"]))
		if stats["unreconciled"]:
			summary_parts.append(_("{0} to review in Mint").format(stats["unreconciled"]))
		if stats["errors"]:
			summary_parts.append(_("{0} errors").format(stats["errors"]))

		summary = " | ".join(summary_parts)
		self.db_set("import_summary", summary)
		self.db_set("status", "Completed")

		frappe.msgprint(
			summary,
			title=_("XML Import Complete"),
			indicator="green" if stats["errors"] == 0 else "orange",
		)

		# Trigger the Mint rule engine so freshly imported transactions are
		# evaluated immediately (mirrors the CSV/XLSX flow in
		# mint.apis.statement_import.import_statement). Without this, they sit
		# with is_rule_evaluated=0 until the hourly scheduler picks them up.
		from mint.apis.rules import run_rule_evaluation
		run_rule_evaluation()


def _link_payment_entry_to_bt(bank_tx, payment_entry_name: str, reconciliation_type: str = "Matched"):
	"""Link a Payment Entry to a (submitted) Bank Transaction with full ERPNext machinery.

	Mirrors the manual reconcile_vouchers flow: appends with allocated_amount=0
	so ERPNext's allocate_payment_entries() handles the proper allocation AND
	calls clear_linked_payment_entry() which posts the clearance_date on the PE.

	If we append with allocated_amount=amount directly, ERPNext's
	allocate_payment_entries() skips the row (its loop ignores rows where
	allocated_amount != 0) → clearance_date is never posted → the PE stays
	"Non compensé" in the Bank Clearance Summary.
	"""
	bank_tx.append("payment_entries", {
		"payment_document": "Payment Entry",
		"payment_entry": payment_entry_name,
		"allocated_amount": 0.0,
		"reconciliation_type": reconciliation_type,
	})
	bank_tx.validate_duplicate_references()
	bank_tx.allocate_payment_entries()
	bank_tx.update_allocated_amount()
	bank_tx.set_status()
	bank_tx.save()


def _fail_with_context(doc, title: str, message: str):
	"""Persist a user-visible error on the MBSI doc, add a timeline comment,
	then throw with the same message.

	Surfaces the failure reason directly on the document (error field, status,
	and Activity timeline) so users don't have to dig through the global Error
	Log to understand why an import failed.
	"""
	if doc and doc.name and doc.docstatus == 0:
		doc.db_set("error", message)
		doc.db_set("status", "Error")
		doc.add_comment(
			"Comment",
			f"<strong>{frappe.utils.escape_html(title)}</strong><br>"
			f"{frappe.utils.escape_html(message).replace(chr(10), '<br>')}"
		)
		frappe.db.commit()
	frappe.throw(message, title=title)


@frappe.whitelist()
def parse_xml_content(docname):
	"""Parse CAMT XML file and populate transactions child table."""
	from erpnextswiss.erpnextswiss.page.bank_wizard.bank_wizard import (
		read_camt053_meta,
		read_camt053,
	)

	doc = frappe.get_doc("Mint Bank Statement Import", docname)

	if doc.docstatus != 0:
		_fail_with_context(doc, _("Document cannot be parsed"), _("Cannot parse a submitted or cancelled document"))

	if not doc.file:
		_fail_with_context(doc, _("Missing file"), _("Please attach an XML file first"))

	if doc.file_type != "XML":
		_fail_with_context(doc, _("Wrong file type"), _("File type must be XML"))

	# Read file content
	file_content = _read_file_content(doc.file)

	if not file_content:
		_fail_with_context(doc, _("Cannot read file"), _("Could not read file content"))

	# Calculate content hash for file-level dedup
	if isinstance(file_content, bytes):
		content_hash = hashlib.md5(file_content).hexdigest()
		xml_string = file_content.decode("utf-8", errors="replace")
	else:
		content_hash = hashlib.md5(file_content.encode("utf-8")).hexdigest()
		xml_string = file_content

	# Parse meta information
	meta = read_camt053_meta(xml_string)

	# Auto-detect bank account from IBAN
	iban = meta.get("iban", "")
	detected_bank_account = None
	if iban and iban != "n/a":
		detected_bank_account = _find_bank_account_by_iban(iban)

	# If bank_account is set, validate IBAN match
	if doc.bank_account and detected_bank_account and doc.bank_account != detected_bank_account:
		frappe.msgprint(
			_("IBAN in XML ({0}) points to {1}, but {2} is selected. Using selected account.").format(
				iban, detected_bank_account, doc.bank_account
			),
			indicator="orange",
		)
	elif not doc.bank_account and detected_bank_account:
		doc.bank_account = detected_bank_account

	if not doc.bank_account:
		_fail_with_context(doc, _("Missing IBAN"), _("Please check your IBAN. It is missing: {0}").format(iban))

	# Get the linked Account for read_camt053
	account = frappe.get_cached_value("Bank Account", doc.bank_account, "account")

	# Parse transactions
	result = read_camt053(xml_string, account)
	transactions = result.get("transactions", [])

	# Update document fields
	doc.content_hash = content_hash
	doc.bank_statement_id = meta.get("msgid", "")
	doc.currency = meta.get("currency", "")
	doc.opening_balance = meta.get("opening_balance", 0)
	doc.closing_balance = meta.get("closing_balance", 0)

	# Clear existing transactions and populate with parsed data
	doc.transactions = []
	stats = {"total": 0, "to_process": 0, "duplicates": 0}

	for txn in transactions:
		is_debit = txn.get("credit_debit") == "DBIT"
		amount = float(txn.get("amount", 0))
		reference = txn.get("unique_reference", "")
		stats["total"] += 1

		# Check for existing Bank Transaction (pre-dedup)
		existing_bt = None
		status = "To Process"
		if reference and doc.bank_account:
			existing_bt = _find_existing_bank_transaction(
				doc.bank_account, txn.get("date"), reference, amount, is_debit
			)
			if existing_bt:
				status = "Existing"
				stats["duplicates"] += 1
			else:
				stats["to_process"] += 1

		# Invoice matching info from bank_wizard parser
		invoice_matches = txn.get("invoice_matches")
		party_match = txn.get("party_match", "")
		matched_amount = float(txn.get("matched_amount", 0))

		doc.append("transactions", {
			"date": txn.get("date"),
			"amount": amount,
			"type": "Withdrawal" if is_debit else "Deposit",
			"description": _build_description(txn),
			"reference": reference,
			"unique_reference": reference,
			"party_name": txn.get("party_name", ""),
			"party_iban": txn.get("party_iban", ""),
			"credit_debit": txn.get("credit_debit", ""),
			"status": status,
			"existing_bank_transaction": existing_bt or "",
			"invoice_matches": str(invoice_matches) if invoice_matches else "",
			"party_match": party_match or "",
			"matched_amount": matched_amount,
		})

	# Auto-submit when there are no new transactions to process
	if stats["to_process"] == 0:
		doc.status = "Completed"
		doc.import_summary = _("No new transactions to import")
		doc.save()
		doc.submit()
	else:
		doc.save()

	return {
		"success": True,
		"transaction_count": stats["total"],
		"new_count": stats["to_process"],
		"duplicate_count": stats["duplicates"],
		"bank_account": doc.bank_account,
		"currency": doc.currency,
		"opening_balance": doc.opening_balance,
		"closing_balance": doc.closing_balance,
	}


def _find_existing_payment_entry(reference, transaction, amount, is_withdrawal, company):
	"""Find existing Payment Entry that matches this bank transaction.
	Covers: Payment Proposal PEs, manually created PEs, etc."""
	from datetime import timedelta

	# 1. Match by exact reference_no + amount
	pe = frappe.db.get_value("Payment Entry",
		{"reference_no": reference, "paid_amount": amount, "docstatus": 1, "company": company}, "name")
	if pe:
		# Verify not already linked to another Bank Transaction
		already_linked = frappe.db.exists("Bank Transaction Payments",
			{"payment_entry": pe})
		if not already_linked:
			return pe

	# 2. Match by invoice name in reference_no
	if transaction.invoice_matches:
		try:
			import ast as _ast
			inv_list = _ast.literal_eval(transaction.invoice_matches) if isinstance(transaction.invoice_matches, str) else transaction.invoice_matches
			if inv_list:
				for inv_name in inv_list:
					pe = frappe.db.get_value("Payment Entry",
						{"reference_no": inv_name, "docstatus": 1, "company": company}, "name")
					if pe:
						return pe
		except:
			pass

	# 3. Match by party + amount + date range (±5 days)
	party_name = transaction.party_match or transaction.party_name
	if party_name and amount > 0:
		from frappe.utils import getdate, add_days
		tx_date = getdate(transaction.date)
		date_from = add_days(tx_date, -5)
		date_to = add_days(tx_date, 5)

		payment_type = "Pay" if is_withdrawal else "Receive"
		party_type = "Supplier" if is_withdrawal else "Customer"

		# Find party
		party = None
		if is_withdrawal:
			party = frappe.db.get_value("Supplier", {"supplier_name": party_name}, "name")
		else:
			party = frappe.db.get_value("Customer", {"customer_name": party_name}, "name")

		if party:
			pes = frappe.get_all("Payment Entry",
				filters={
					"docstatus": 1,
					"payment_type": payment_type,
					"party_type": party_type,
					"party": party,
					"paid_amount": amount,
					"posting_date": ["between", [str(date_from), str(date_to)]],
					"company": company,
				},
				fields=["name"],
			)
			# Only auto-match if exactly one PE found
			if len(pes) == 1:
				# Check it's not already linked to another Bank Transaction
				already_linked = frappe.db.exists("Bank Transaction Payments",
					{"payment_entry": pes[0].name})
				if not already_linked:
					return pes[0].name

	return None


def _find_existing_bank_transaction_by_description(bank_account, date, description, amount, is_withdrawal):
	"""Find existing Bank Transaction by description + date + amount (fallback dedup)."""
	if not description:
		return None

	filters = {
		"bank_account": bank_account,
		"date": date,
		"description": description,
		"docstatus": ["<", 2],
	}

	if is_withdrawal:
		filters["withdrawal"] = amount
	else:
		filters["deposit"] = amount

	return frappe.db.get_value("Bank Transaction", filters, "name")


def _find_existing_bank_transaction(bank_account, date, reference_number, amount, is_withdrawal):
	"""Find the existing Bank Transaction name if it exists (for dedup tracking)."""
	if not reference_number:
		return None

	filters = {
		"bank_account": bank_account,
		"date": date,
		"reference_number": reference_number,
		"docstatus": ["<", 2],
	}

	if is_withdrawal:
		filters["withdrawal"] = amount
	else:
		filters["deposit"] = amount

	return frappe.db.get_value("Bank Transaction", filters, "name")


def _read_file_content(file_url):
	"""Read content from an attached file."""
	if not file_url:
		return None

	# Try by exact file_url first
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		# Fallback: read directly from filesystem
		import os
		site_path = frappe.get_site_path()
		file_path = os.path.join(site_path, file_url.lstrip("/"))
		if os.path.exists(file_path):
			with open(file_path, "rb") as f:
				return f.read()
		return None

	file_doc = frappe.get_doc("File", file_name)
	return file_doc.get_content()


def _find_bank_account_by_iban(iban):
	"""Find a Bank Account by IBAN."""
	clean_iban = iban.replace(" ", "")
	# Search in Account (IBAN is on Account, not Bank Account)
	accounts = frappe.db.sql("""
		SELECT ba.name
		FROM `tabBank Account` ba
		INNER JOIN `tabAccount` acc ON ba.account = acc.name
		WHERE REPLACE(acc.iban, ' ', '') = %s
		AND ba.is_company_account = 1
		LIMIT 1
	""", clean_iban, as_dict=True)

	if accounts:
		return accounts[0].name
	return None


def _build_description(txn):
	"""Build a human-readable description from CAMT transaction data.

	Priority order (joined with newlines, deduplicated):
	  1. <AddtlNtryInf> — the bank's own multi-line summary of the entry
	     (e.g. "Paiement Revolut Bank UAB\nKonstitucijos ave. 21B, ...\nDaniel Moret, CH")
	  2. <RmtInf><Ustrd> / ESR ref / end-to-end ID (via transaction_reference)
	  3. <AcctSvcrRef> as last-resort unique_reference fallback
	"""
	addtl = (txn.get("entry_addtl_info") or "").strip()
	tx_ref = (txn.get("transaction_reference") or "").strip()
	remarks = (txn.get("remarks") or "").strip()
	unique_ref = (txn.get("unique_reference") or "").strip()

	lines = []
	if addtl:
		lines.append(addtl)
	if remarks and remarks not in addtl:
		lines.append(remarks)
	if tx_ref and tx_ref not in addtl and tx_ref != remarks:
		lines.append(tx_ref)
	if not lines and unique_ref:
		lines.append(unique_ref)

	return "\n".join(lines)
