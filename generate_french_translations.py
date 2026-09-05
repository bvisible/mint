#!/usr/bin/env python3
# //// Neoffice — added file (no upstream equivalent): one-shot generator that turned
# //// mint's main.pot into the French mint/locale/fr.po we ship (upstream ships EN + DE
# //// only). Not imported by the app; kept so the catalogue can be regenerated.
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

    # Additional translations for remaining strings
    "Can be \"1200 Dr\" and will be translated to 1200 in amount and \"Withdrawal\"": "Peut être \"1200 Dr\" et sera traduit en 1200 en montant et \"Retrait\"",
    "Entries below have a posting date after {0} but the clearance date is before {1}.": "Les écritures ci-dessous ont une date de comptabilisation après {0} mais la date de compensation est avant {1}.",
    "Error": "Erreur",
    "Expense Claim": "Note de frais",
    "Failed to create document processor": "Échec de la création du processeur de documents",
    "Failed to create processor": "Échec de la création du processeur",
    "Failed to delete rule.": "Échec de la suppression de la règle.",
    "Failed to run rules evaluation": "Échec de l'exécution de l'évaluation des règles",
    "Failed to update auto classify transactions settings": "Échec de la mise à jour des paramètres de classification automatique des transactions",
    "Failed to update rule priorities": "Échec de la mise à jour des priorités des règles",
    "File": "Fichier",
    "File Type": "Type de fichier",
    "Filter by amount": "Filtrer par montant",
    "For example, if set to 4, Mint will try to find matching transactions in other banks 4 days before and after the transaction date. This is because transactions can clear on different days on different bank accounts.": "Par exemple, si défini à 4, Mint essaiera de trouver des transactions correspondantes dans d'autres banques 4 jours avant et après la date de transaction. Ceci parce que les transactions peuvent être compensées à des dates différentes sur différents comptes bancaires.",
    "Force Evaluate All": "Forcer l'évaluation de toutes",
    "Force re-evaluate all unreconciled transactions, even if they were previously evaluated": "Forcer la réévaluation de toutes les transactions non rapprochées, même si elles ont été précédemment évaluées",
    "GL Account": "Compte du grand livre",
    "General": "Général",
    "Google APIs are not enabled. Please enable them in Mint Settings.": "Les API Google ne sont pas activées. Veuillez les activer dans les paramètres Mint.",
    "Google Document AI": "Google Document AI",
    "Google Document Processor - Bank Statement": "Processeur de documents Google - Relevé bancaire",
    "Google Document Processor Location": "Emplacement du processeur de documents Google",
    "Google Processor Location": "Emplacement du processeur Google",
    "Google Project ID": "ID de projet Google",
    "Google Project ID is not set in Mint Settings": "L'ID de projet Google n'est pas défini dans les paramètres Mint",
    "Google Project ID is not set. Please set it in the Mint Settings.": "L'ID de projet Google n'est pas défini. Veuillez le définir dans les paramètres Mint.",
    "Google Service Account JSON Key": "Clé JSON du compte de service Google",
    "Google Service Account JSON Key is not set in Mint Settings": "La clé JSON du compte de service Google n'est pas définie dans les paramètres Mint",
    "Grand Total": "Total général",
    "If checked, this job will run every 30 minutes": "Si coché, cette tâche s'exécutera toutes les 30 minutes",
    "If rule matches, then:": "Si la règle correspond, alors :",
    "If your bank statement shows a different closing balance, it is because all transactions have not reconciled yet.": "Si votre relevé bancaire affiche un solde de clôture différent, c'est parce que toutes les transactions n'ont pas encore été rapprochées.",
    "Imported": "Importé",
    "Incorrectly Cleared Entries": "Écritures compensées incorrectement",
    "Incorrectly cleared entries as per the report.": "Écritures compensées incorrectement selon le rapport.",
    "Invalid file type": "Type de fichier invalide",
    "Invalid regex pattern.": "Modèle regex invalide.",
    "Invoice No": "N° de facture",
    "Invoices": "Factures",
    "It takes into account all the transactions that have been posted and subtracts the transactions that have not cleared yet.": "Il prend en compte toutes les transactions qui ont été comptabilisées et soustrait les transactions qui n'ont pas encore été compensées.",
    "It's all good!": "Tout est bon !",
    "Last Fiscal Year": "Dernier exercice fiscal",
    "Last Month": "Mois dernier",
    "Last Quarter": "Dernier trimestre",
    "Last Synced Transaction": "Dernière transaction synchronisée",
    "Last Week": "Semaine dernière",
    "Last Year": "Année dernière",
    "Loading": "Chargement",
    "Location where the document processor is run.": "Emplacement où le processeur de documents est exécuté.",
    "Match Transfers across (days)": "Faire correspondre les virements sur (jours)",
    "Match and Reconcile": "Faire correspondre et rapprocher",
    "Match or Create": "Faire correspondre ou créer",
    "Matched by rule": "Correspondance par règle",
    "Max Amount": "Montant maximum",
    "Maximum Amount": "Montant maximum",
    "Min Amount": "Montant minimum",
    "Min amount cannot be greater than max amount.": "Le montant minimum ne peut pas être supérieur au montant maximum.",
    "Minimum Amount": "Montant minimum",
    "Mint Bank Statement Import": "Import de relevé bancaire Mint",
    "Mint Bank Statement Import Transactions": "Transactions d'import de relevé bancaire Mint",
    "Mint Bank Transaction Description Rules": "Règles de description de transaction bancaire Mint",
    "Mint Bank Transaction Rule": "Règle de transaction bancaire Mint",
    "Mint Settings": "Paramètres Mint",
    "Mode of Payment": "Mode de paiement",
    "New Rule": "Nouvelle règle",
    "No Match": "Aucune correspondance",
    "No accounts found.": "Aucun compte trouvé.",
    "No entries found": "Aucune écriture trouvée",
    "No results found.": "Aucun résultat trouvé.",
    "No rules found": "Aucune règle trouvée",
    "No vouchers found for this transaction": "Aucune pièce trouvée pour cette transaction",
    "Not Cleared": "Non compensé",
    "Not Reconciled": "Non rapproché",
    "Not Started": "Non commencé",
    "Number of Days to Match Transfers": "Nombre de jours pour faire correspondre les virements",
    "Number of days to consider for transfer matching across bank accounts.": "Nombre de jours à considérer pour faire correspondre les virements entre comptes bancaires.",
    "Opening Balance": "Solde d'ouverture",
    "Outstanding": "En attente",
    "Outstanding Checks and Deposits to clear": "Chèques et dépôts en attente de compensation",
    "PDF": "PDF",
    "Paid From": "Payé depuis",
    "Paid From (GL Account)": "Payé depuis (compte GL)",
    "Paid To": "Payé à",
    "Paid To (GL Account)": "Payé à (compte GL)",
    "Paid to": "Payé à",
    "Partial Match": "Correspondance partielle",
    "Partially Reconciled": "Partiellement rapproché",
    "Party is required": "Le tiers est requis",
    "Party is required create a payment entry.": "Le tiers est requis pour créer une écriture de paiement.",
    "Party type is required to create a payment entry.": "Le type de tiers est requis pour créer une écriture de paiement.",
    "Paste the Service Key (JSON) from the Google Cloud Console.": "Coller la clé de service (JSON) depuis la console Google Cloud.",
    "Payment Document": "Document de paiement",
    "Payment Entry Created": "Écriture de paiement créée",
    "Payment Recorded": "Paiement enregistré",
    "Please select a bank account to view the bank clearance summary.": "Veuillez sélectionner un compte bancaire pour afficher le résumé de compensation bancaire.",
    "Please select a bank account to view the bank reconciliation statement.": "Veuillez sélectionner un compte bancaire pour afficher l'état de rapprochement bancaire.",
    "Please select a bank and set the date range": "Veuillez sélectionner une banque et définir la plage de dates",
    "Please select dates to view the bank clearance summary.": "Veuillez sélectionner des dates pour afficher le résumé de compensation bancaire.",
    "Please select dates to view the bank reconciliation statement.": "Veuillez sélectionner des dates pour afficher l'état de rapprochement bancaire.",
    "Please upload a file": "Veuillez télécharger un fichier",
    "Posted On": "Comptabilisé le",
    "Posting Date does not match the transaction date": "La date de comptabilisation ne correspond pas à la date de transaction",
    "Posting Date matches the transaction date": "La date de comptabilisation correspond à la date de transaction",
    "Priority": "Priorité",
    "Purchase Invoice": "Facture d'achat",
    "Q1": "T1",
    "Q2": "T2",
    "Q3": "T3",
    "Q4": "T4",
    "Received": "Reçu",
    "Received from": "Reçu de",
    "Recommended Action": "Action recommandée",
    "Reconciliation Type": "Type de rapprochement",
    "Reconciling": "Rapprochement en cours",
    "Record Payment": "Enregistrer un paiement",
    "Record a bank journal entry for expenses, income or split transactions": "Enregistrer une écriture de journal bancaire pour les dépenses, revenus ou transactions fractionnées",
    "Record a journal entry for expenses, income or split transactions": "Enregistrer une écriture de journal pour les dépenses, revenus ou transactions fractionnées",
    "Record a payment entry against a customer or supplier": "Enregistrer une écriture de paiement contre un client ou un fournisseur",
    "Record an internal transfer to another bank/credit card/cash account": "Enregistrer un virement interne vers un autre compte bancaire/carte de crédit/espèces",
    "Record an internal transfer to another bank/credit card/cash account.": "Enregistrer un virement interne vers un autre compte bancaire/carte de crédit/espèces.",
    "Ref": "Réf",
    "Reference": "Référence",
    "Reference #": "Référence #",
    "Reference Date does not match the transaction date": "La date de référence ne correspond pas à la date de transaction",
    "Reference Date is required": "La date de référence est requise",
    "Reference Date matches the transaction date": "La date de référence correspond à la date de transaction",
    "Reference Document": "Document de référence",
    "Reference does not match the selected transaction": "La référence ne correspond pas à la transaction sélectionnée",
    "Reference matches the selected transaction": "La référence correspond à la transaction sélectionnée",
    "Reference matches the selected transaction partially": "La référence correspond partiellement à la transaction sélectionnée",
    "Regex": "Regex",
    "Reset Clearing Date": "Réinitialiser la date de compensation",
    "Rule Description": "Description de la règle",
    "Rule Name": "Nom de la règle",
    "Rule created successfully": "Règle créée avec succès",
    "Rule deleted.": "Règle supprimée.",
    "Rule matched based on transaction description and other criteria.": "Règle correspondante basée sur la description de transaction et autres critères.",
    "Rule name is required": "Le nom de la règle est requis",
    "Rule priorities updated": "Priorités des règles mises à jour",
    "Rule updated.": "Règle mise à jour.",
    "Rules evaluation completed": "Évaluation des règles terminée",
    "Rules evaluation started": "Évaluation des règles démarrée",
    "Rules to match against the transaction description": "Règles à faire correspondre avec la description de transaction",
    "Run Rules": "Exécuter les règles",
    "Run on new transactions": "Exécuter sur les nouvelles transactions",
    "Run rules automatically": "Exécuter les règles automatiquement",
    "Run rules on unreconciled transactions that haven't been evaluated yet": "Exécuter les règles sur les transactions non rapprochées qui n'ont pas encore été évaluées",
    "Running...": "Exécution en cours...",
    "Sales Invoice": "Facture de vente",
    "Scheduled job disabled. Transactions will not be auto classified.": "Tâche planifiée désactivée. Les transactions ne seront pas classées automatiquement.",
    "Scheduled job enabled. Transactions will be auto classified.": "Tâche planifiée activée. Les transactions seront classées automatiquement.",
    "Search": "Rechercher",
    "Search Results": "Résultats de recherche",
    "Search account...": "Rechercher un compte...",
    "Search transactions": "Rechercher des transactions",
    "Select Account": "Sélectionner un compte",
    "Select Location": "Sélectionner un emplacement",
    "Select Processor": "Sélectionner un processeur",
    "Select a bank account to reconcile": "Sélectionner un compte bancaire à rapprocher",
    "Select a transaction to match and reconcile with vouchers": "Sélectionner une transaction à faire correspondre et rapprocher avec des pièces",
    "Select row {0}": "Sélectionner la ligne {0}",
    "Set up rules to automatically classify transactions. Drag and drop rules to reorder their priority.": "Configurer des règles pour classer automatiquement les transactions. Glisser-déposer les règles pour réorganiser leur priorité.",
    "Settings updated": "Paramètres mis à jour",
    "Show Only Exact Amount": "Afficher uniquement le montant exact",
    "Spent": "Dépensé",
    "Starts With": "Commence par",
    "Starts with": "Commence par",
    "Status": "Statut",
    "String Amount": "Montant en chaîne",
    "Suggest creating a": "Suggérer de créer un",
    "Suggested": "Suggéré",
    "Suggested Transfer to {0}": "Virement suggéré vers {0}",
    "System Manager": "Gestionnaire système",
    "The Google Project ID is used to authenticate with the Google Cloud Platform.": "L'ID de projet Google est utilisé pour s'authentifier avec Google Cloud Platform.",
    "The invoice is not fully allocated as there is a difference of {0}.": "La facture n'est pas entièrement allouée car il y a une différence de {0}.",
    "The system found a mirror transaction ({0}) in another account with the same amount and date.": "Le système a trouvé une transaction miroir ({0}) dans un autre compte avec le même montant et la même date.",
    "There are no accounting entries in the system for the selected account and dates.": "Il n'y a aucune écriture comptable dans le système pour le compte et les dates sélectionnés.",
    "There are no entries in the system where the clearance date is before the posting date.": "Il n'y a aucune écriture dans le système où la date de compensation est avant la date de comptabilisation.",
    "There are no transactions in the system for the selected bank account and dates.": "Il n'y a aucune transaction dans le système pour le compte bancaire et les dates sélectionnés.",
    "There was an error while performing the action.": "Une erreur s'est produite lors de l'exécution de l'action.",
    "There was an error.": "Une erreur s'est produite.",
    "This Fiscal Year": "Cet exercice fiscal",
    "This Month": "Ce mois-ci",
    "This Quarter": "Ce trimestre",
    "This Week": "Cette semaine",
    "This Year": "Cette année",
    "This is required": "Ceci est requis",
    "This is what the system expects the closing balance to be in your bank statement.": "C'est ce que le système s'attend à ce que le solde de clôture soit dans votre relevé bancaire.",
    "This report shows all entries in the system where the <strong>clearance date is before the posting date</strong> which is incorrect.": "Ce rapport affiche toutes les écritures dans le système où la <strong>date de compensation est avant la date de comptabilisation</strong>, ce qui est incorrect.",
    "This transaction has been reconciled with the following document(s):": "Cette transaction a été rapprochée avec le(s) document(s) suivant(s) :",
    "This will be auto-populated if not set.": "Ceci sera automatiquement rempli s'il n'est pas défini.",
    "This will just suggest creating a new entry, and will not automatically create it.": "Ceci suggérera simplement de créer une nouvelle écriture, et ne la créera pas automatiquement.",
    "Toggle Sidebar": "Basculer la barre latérale",
    "Total Amount": "Montant total",
    "Transaction Matching Rules": "Règles de correspondance de transaction",
    "Transaction Unreconciled": "Transaction non rapprochée",
    "Transactions": "Transactions",
    "Transfer Recorded": "Virement enregistré",
    "Transferred Out": "Transféré sortant",
    "Transferred from": "Transféré depuis",
    "Transferred to": "Transféré vers",
    "Type": "Type",
    "Type of check": "Type de chèque",
    "US": "US",
    "Unallocated": "Non alloué",
    "Undo Transaction Reconciliation": "Annuler le rapprochement de transaction",
    "Unreconcile": "Annuler le rapprochement",
    "Unreconciled Transactions": "Transactions non rapprochées",
    "Updating...": "Mise à jour...",
    "Use Suggestion": "Utiliser la suggestion",
    "Value": "Valeur",
    "View": "Voir",
    "You can reset the clearing dates of these entries here.": "Vous pouvez réinitialiser les dates de compensation de ces écritures ici.",
    "Your Progress": "Votre progression",
    "e.g. Bank Charges": "p. ex. Frais bancaires",
    "transaction selected": "transaction sélectionnée",
    "transactions selected": "transactions sélectionnées",
    "us": "us",
    "{0} {1} does not exist": "{0} {1} n'existe pas",
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
