# //// Neoffice — added file (no upstream equivalent): keeps the DocType-context entries of locale/fr.po alive.
"""Translation entries that live in a DocType JSON, anchored here so the POT keeps them.

The desk translates a DocType label as `__(label, null, <DocType name>)` and a Select option as
`__(option, null, <DocType name>)`: it looks `"<text>:<DocType name>"` up first and falls back to the bare text.
The extractor that reads DocType JSON files writes the bare text only, never the context. A
`msgctxt "<DocType name>"` entry in `locale/fr.po` that nothing in the code mentions is therefore dropped as
obsolete the next time `bench update-po-files` runs, and the screen silently falls back to the bare word.

This function is NEVER called. It exists so that `bench generate-pot-file` finds the strings.
"""

from frappe import _


def _i18n_anchors():
    """Never called. See the module docstring."""
    # Label of the `check` Select of Mint Bank Transaction Description Rules: how a rule tests a bank
    # description (Contains / Starts With / Ends With / Regex). The bare word `Check` is a tick box in
    # frappe, LMS and our apps; it is not a bank cheque.
    _("Check", context="Mint Bank Transaction Description Rules")
    # Option of the `classify_as` Select of Mint Bank Transaction Rule: a bank transfer. The bare word
    # `Transfer` is a transfer of assets, shares or a call elsewhere.
    _("Transfer", context="Mint Bank Transaction Rule")
