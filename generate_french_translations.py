#!/usr/bin/env python3
"""
Script to generate French translations for Mint application.
Reads main.pot and creates fr.po with French translations.
"""

import re
from datetime import datetime

# Comprehensive translations dictionary for Mint banking application
TRANSLATIONS = {
    # A
    "Accepted": "Accepté",
    "Accepting the suggestion will reconcile both transactions.": "Accepter la suggestion rapprochera les deux transactions.",
    "Account": "Compte",
    "Account company does not match with the rule company.": "La société du compte ne correspond pas à la société de la règle.",
    "Account is required": "Le compte est requis",
    "Accounting Entries": "Écritures comptables",
    "Action": "Action",
    "Action Type": "Type d'action",
    "Actions": "Actions",
    "Active": "Actif",
    "Add": "Ajouter",
    "Add Row": "Ajouter une ligne",
    "Add Rule": "Ajouter une règle",
    "Add a charge to the payment entry with the difference amount": "Ajouter un débit/crédit à l'écriture de paiement avec le montant de la différence",
    "Add a charge to the payment entry with the unallocated amount": "Ajouter un débit/crédit à l'écriture de paiement avec le montant non alloué",
    "Add a row to with the difference amount": "Ajouter une ligne avec le montant de la différence",
    "Against Account": "Contre compte",
    "All": "Tout",
    "All rows must have an amount and a type. Missing in row {0}": "Toutes les lignes doivent avoir un montant et un type. Manquant dans la ligne {0}",
    "Allocated": "Alloué",
    "Amended From": "Amendé de",
    "Amount": "Montant",
    "Amount does not match the selected transaction": "Le montant ne correspond pas à la transaction sélectionnée",
    "Amount is required": "Le montant est requis",
    "Amount matches the selected transaction": "Le montant correspond à la transaction sélectionnée",
    "Any": "Tout",
    "Any debit transaction with the keyword 'Bank Fee'.": "Toute transaction de débit avec le mot-clé 'Frais bancaires'.",
    "Apply": "Appliquer",
    "Are you sure you want to delete this rule?": "Êtes-vous sûr de vouloir supprimer cette règle ?",
    "Are you sure you want to unreconcile this transaction?": "Êtes-vous sûr de vouloir annuler le rapprochement de cette transaction ?",
    "Automatically run rules on unreconciled transactions": "Exécuter automatiquement les règles sur les transactions non rapprochées",

    # B
    "Back to Form": "Retour au formulaire",
    "Bank": "Banque",
    "Bank Account": "Compte bancaire",
    "Bank Charges, Salary, etc.": "Frais bancaires, Salaire, etc.",
    "Bank Clearance Summary": "Résumé de compensation bancaire",
    "Bank Entries Created": "Écritures bancaires créées",
    "Bank Entry": "Écriture bancaire",
    "Bank Entry Created": "Écriture bancaire créée",
    "Bank Fee, Salary, etc.": "Frais bancaires, Salaire, etc.",
    "Bank Reconciliation": "Rapprochement bancaire",
    "Bank Reconciliation Statement": "État de rapprochement bancaire",
    "Bank Statement Balance as per General Ledger": "Solde du relevé bancaire selon le grand livre",
    "Bank Statement Processor": "Processeur de relevés bancaires",
    "Bank Statement Processor is not set in Mint Settings": "Le processeur de relevés bancaires n'est pas configuré dans les paramètres Mint",
    "Bank Transaction": "Transaction bancaire",
    "Bank Transaction {0} is already fully reconciled": "La transaction bancaire {0} est déjà complètement rapprochée",
    "Bank Transactions": "Transactions bancaires",
    "Bank Transactions between {0} and {1}": "Transactions bancaires entre {0} et {1}",
    "Below is a list of all accounting entries posted against the bank account {0} between {1} and {2}.": "Voici une liste de toutes les écritures comptables imputées au compte bancaire {0} entre {1} et {2}.",
    "Below is a list of all bank transactions imported in the system for the bank account {0} between {1} and {2}.": "Voici une liste de toutes les transactions bancaires importées dans le système pour le compte bancaire {0} entre {1} et {2}.",
    "Below is a list of all entries posted against the bank account {0} which have not been cleared till {1}.": "Voici une liste de toutes les écritures imputées au compte bancaire {0} qui n'ont pas été compensées jusqu'au {1}.",

    # C
    "Calculated Bank Statement Balance": "Solde du relevé bancaire calculé",
    "Can be \"1200 Dr\" and will be translated to 1200 in amount and \"Withdrawal\"": "Peut être \"1200 Dr\" et sera traduit en 1200 en montant et \"Retrait\"",
    "Cancel": "Annuler",
    "Check": "Chèque",
    "Checks and Deposits incorrectly cleared": "Chèques et dépôts compensés incorrectement",
    "Cheque Date": "Date du chèque",
    "Cheque/Reference Number": "Numéro de chèque/référence",
    "Classify As": "Classer comme",
    "Clearance Date": "Date de compensation",
    "Cleared": "Compensé",
    "Click to pay in full.": "Cliquer pour payer intégralement.",
    "Close": "Fermer",
    "Closing Balance as per system": "Solde de clôture selon le système",
    "Closing balance as per system": "Solde de clôture selon le système",
    "Company": "Société",
    "Company is required": "La société est requise",
    "Complete Match": "Correspondance complète",
    "Completed": "Terminé",
    "Configure match filters for vouchers": "Configurer les filtres de correspondance pour les pièces",
    "Configure settings for Mint.": "Configurer les paramètres pour Mint.",
    "Confirm": "Confirmer",
    "Confirm and Submit": "Confirmer et soumettre",
    "Contains": "Contient",
    "Copied to clipboard": "Copié dans le presse-papiers",
    "Copy to clipboard": "Copier dans le presse-papiers",
    "Cost Center": "Centre de coûts",
    "Cost Center is required": "Le centre de coûts est requis",
    "Create": "Créer",
    "Create a journal entry for expenses, income or split transactions": "Créer une écriture de journal pour les dépenses, revenus ou transactions fractionnées",
    "Create a new entry based on the rule": "Créer une nouvelle écriture basée sur la règle",
    "Create a new rule": "Créer une nouvelle règle",
    "Create a new rule to automatically classify transactions.": "Créer une nouvelle règle pour classer automatiquement les transactions.",
    "Create New {0}": "Créer un nouveau {0}",
    "Create New Bank Statement Processor": "Créer un nouveau processeur de relevés bancaires",
    "Credit": "Crédit",
    "Credits": "Crédits",
    "Currency": "Devise",
    "Custom Remarks": "Remarques personnalisées",
    "Customer": "Client",

    # D
    "Date": "Date",
    "Date Range": "Plage de dates",
    "Debit": "Débit",
    "Debits": "Débits",
    "Delete": "Supprimer",
    "Deleting rule...": "Suppression de la règle...",
    "Deposit": "Dépôt",
    "Description": "Description",
    "Description Rules": "Règles de description",
    "Difference": "Différence",
    "Disabled": "Désactivé",
    "Document": "Document",
    "Document Type": "Type de document",
    "Drag to reorder": "Glisser pour réordonner",
    "Due Date": "Date d'échéance",

    # E
    "Edit": "Modifier",
    "Edit this rule": "Modifier cette règle",
    "Enabled": "Activé",
    "Ends With": "Se termine par",
    "Ends with": "Se termine par",
    "Enter Closing Balance as per statement": "Saisir le solde de clôture selon le relevé",
    "EU": "UE",

    # F
    "Failed": "Échoué",
    "From Date": "Du",

    # I
    "Inactive": "Inactif",
    "Internal Transfer": "Virement interne",

    # J
    "Journal Entry": "Écriture de journal",
    "Journal Entry Details": "Détails de l'écriture de journal",

    # L
    "Loading...": "Chargement...",

    # M
    "Match": "Correspondance",
    "Matched": "Correspondant",

    # N
    "No transaction selected": "Aucune transaction sélectionnée",
    "No transactions found": "Aucune transaction trouvée",

    # O
    "Original amount": "Montant initial",

    # P
    "Party": "Tiers",
    "Party Type": "Type de tiers",
    "Payment": "Paiement",
    "Payment Entry": "Écriture de paiement",
    "Pending": "En attente",
    "Posting Date": "Date de comptabilisation",
    "Preview": "Aperçu",
    "Preview data is invalid. Please try again.": "Les données de l'aperçu sont invalides. Veuillez réessayer.",

    # R
    "Reconcile": "Rapprocher",
    "Reconciled": "Rapproché",
    "Record a journal entry for expenses, income or split transactions.": "Enregistrer une écriture de journal pour les dépenses, revenus ou transactions fractionnées.",
    "Reference Date": "Date de référence",
    "Reference No": "N° de référence",
    "Reference No is required": "Le numéro de référence est requis",
    "Reference Number": "Numéro de référence",
    "Remarks": "Remarques",
    "Remove": "Retirer",
    "Remove VAT": "Supprimer la TVA",
    "Rule": "Règle",
    "Rules": "Règles",

    # S
    "Save": "Enregistrer",
    "Select a transaction": "Sélectionner une transaction",
    "Select all": "Tout sélectionner",
    "Settings": "Paramètres",
    "Split amount": "Montant fractionné",
    "Submit": "Soumettre",
    "Submitting...": "Envoi en cours...",
    "Supplier": "Fournisseur",

    # T
    "To Date": "Au",
    "Total": "Total",
    "Transaction Reference": "Référence de transaction",
    "Transaction Type": "Type de transaction",
    "Transfer": "Virement",

    # U
    "Undo": "Annuler",
    "Unmatched": "Non correspondant",
    "Unreconciled": "Non rapproché",

    # V
    "VAT": "TVA",
    "Voucher Type": "Type de pièce",

    # W
    "Warning: The journal entry is not balanced. Debit and credit totals must be equal.": "Attention : L'écriture de journal n'est pas équilibrée. Les totaux débit et crédit doivent être égaux.",
    "Withdrawal": "Retrait",
    "With VAT": "Avec TVA",
}


def translate_string(msgid):
    """Translate a string from English to French."""
    if msgid in TRANSLATIONS:
        return TRANSLATIONS[msgid]

    # Try case-insensitive match
    for key, value in TRANSLATIONS.items():
        if key.lower() == msgid.lower():
            return value

    # If not found in dictionary, return empty (will need manual translation)
    return ""


def generate_french_po(pot_file, po_file):
    """Generate French .po file from .pot template."""

    with open(pot_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace header
    header = f"""# French translations for Mint.
# Copyright (C) 2025 The Commit Company (Algocode Technologies Pvt. Ltd.)
# This file is distributed under the same license as the Mint project.
# Claude Code <noreply@anthropic.com>, 2025.
#
msgid ""
msgstr ""
"Project-Id-Version: Mint VERSION\\n"
"Report-Msgid-Bugs-To: support@thecommit.company\\n"
"POT-Creation-Date: 2025-09-23 18:12+0053\\n"
"PO-Revision-Date: {datetime.now().strftime('%Y-%m-%d %H:%M+0000')}\\n"
"Last-Translator: Claude Code <noreply@anthropic.com>\\n"
"Language: fr\\n"
"Language-Team: French\\n"
"Plural-Forms: nplurals=2; plural=(n > 1);\\n"
"MIME-Version: 1.0\\n"
"Content-Type: text/plain; charset=utf-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"Generated-By: Babel 2.16.0\\n"
"""

    # Split into entries
    entries = re.split(r'\n(?=#[:\.])', content)

    # Skip the header entry (first one)
    result = [header]

    for entry in entries[1:]:
        if not entry.strip():
            continue

        # Extract msgid
        msgid_match = re.search(r'msgid "(.*?)"(?:\nmsgstr|$)', entry, re.DOTALL)
        if not msgid_match:
            # Keep the entry as is if we can't parse it
            result.append(entry)
            continue

        msgid = msgid_match.group(1)

        # Skip empty msgid (header)
        if not msgid:
            continue

        # Translate
        msgstr = translate_string(msgid)

        # Replace msgstr in entry
        new_entry = re.sub(
            r'msgstr ""',
            f'msgstr "{msgstr}"' if msgstr else 'msgstr ""',
            entry
        )

        result.append(new_entry)

    # Write output
    with open(po_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result))

    print(f"French translations generated: {po_file}")

    # Count translations
    total = len([e for e in result if 'msgid' in e and 'msgstr' in e])
    translated = len([e for e in result if 'msgstr ""' not in e and 'msgid ""' not in e and 'msgstr' in e])
    print(f"Translated: {translated}/{total} strings")


if __name__ == "__main__":
    pot_file = "mint/locale/main.pot"
    po_file = "mint/locale/fr.po"
    generate_french_po(pot_file, po_file)
