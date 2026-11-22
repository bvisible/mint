# //// Neoffice — added file (no upstream equivalent).
# ////
# //// A MINT TAB OPENS WITHOUT BUILDING THE DESK'S BOOT AGAIN.
# ////
# //// The Finance space frames Mint in two tabs (« Bank Reconciliation », « Reconciliation »), opened as
# //// /mint?embed=1. Their page built the desk's whole boot again (some 200 queries) and carried the dictionary
# //// of every installed app (87,000 entries, 8 MB), at each opening of a tab: about a second before Mint could
# //// start (19.11.2026). Framed, the page carries who it is for and Mint's own senses, and takes the rest from
# //// the desk around it (mint.html); a page not framed is what it was, and the way back of a framed page with
# //// no desk around it (get_navbar_boot_api) gives the whole boot.

import json
from unittest.mock import patch

import frappe
from frappe.tests.roles import as_role
from frappe.tests.utils import FrappeTestCase
from frappe.translate import get_all_translations

from mint.api.boot import get_navbar_boot_api
from mint.www.mint import get_context

# What Mint reads in its boot (frontend/src: lib/permissions, lib/date, lib/currency, useCurrentCompany, main).
READ_BY_MINT = ("user", "docs", "sysdefaults", "time_zone", "lang", "sitename", "__messages")


class TestAFramedPageTakesTheDesksBoot(FrappeTestCase):
    def setUp(self):
        self.user = self.enterContext(as_role("accountant"))
        # French: a dictionary of every app to leave out, and Mint's own sense of « Transfer » to keep.
        lang = frappe.local.lang
        frappe.local.lang = "fr"
        self.addCleanup(setattr, frappe.local, "lang", lang)
        # The account speaks French too: a page not framed builds the desk's boot, and frappe's get_bootinfo
        # sets the language from the account (User.language, then the site's default). The CI's site speaks
        # English, so the page answered in English there and the test was red from its first night (19.11).
        spoken = frappe.db.get_value("User", self.user, "language")
        frappe.db.set_value("User", self.user, "language", "fr")
        self.addCleanup(frappe.db.set_value, "User", self.user, "language", spoken)

    def page(self, **query):
        # The page's controller as the frame calls it, without the session's token or its commit.
        with patch("frappe.sessions.get_csrf_token", return_value="token"), patch.object(
            frappe.db, "commit"
        ), patch.dict(frappe.local.form_dict, query, clear=True):
            context = get_context(frappe._dict())
        return context.boot, json.loads(json.loads(context.boot))

    def test_a_framed_page_carries_only_who_it_is_for_and_mints_own_senses(self):
        text, boot = self.page(embed="1")
        self.assertEqual(boot["take_desk_boot"], 1)
        self.assertEqual(boot["user"], {"name": self.user})
        self.assertEqual(boot["lang"], "fr")
        self.assertEqual(boot["__messages"], {"Transfer": frappe._("Transfer", context="Bank transfer")})
        self.assertLess(len(text), 2000)

    def test_a_framed_page_does_not_build_the_desks_boot(self):
        with patch("frappe.boot.get_bootinfo", side_effect=AssertionError("the desk's boot was built again")):
            self.page(embed="1")

    def test_a_page_not_framed_still_carries_its_whole_boot(self):
        _text, boot = self.page()
        self.assertNotIn("take_desk_boot", boot)
        self.assertLessEqual(set(get_all_translations("fr")), set(boot["__messages"]))
        self.assertEqual(boot["__messages"]["Transfer"], frappe._("Transfer", context="Bank transfer"))

    def test_the_way_back_of_a_framed_page_gives_what_mint_reads(self):
        boot = get_navbar_boot_api()
        for key in READ_BY_MINT:
            self.assertIn(key, boot)
        self.assertEqual(boot["user"]["name"], self.user)
        self.assertEqual(boot["__messages"]["Transfer"], frappe._("Transfer", context="Bank transfer"))
