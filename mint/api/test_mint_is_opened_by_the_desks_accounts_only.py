# //// Neoffice — added file (no upstream equivalent).
# ////
# //// MINT IS OPENED BY THE DESK'S ACCOUNTS ONLY.
# ////
# //// /mint answered a visitor not signed in with the boot it builds for its menu (system defaults, metadata, the
# //// whole dictionary: 8.8 MB, about a second of server per request), a customer of the portal with the same boot
# //// for their account, and get_context_for_dev answered anyone on a site in developer mode
# //// (neoffice-maintenance#3148). Three identities: the visitor goes to the login page and comes back to the same
# //// screen, the customer is refused, the desk's account opens Mint.

import json
from unittest.mock import patch

import frappe
from frappe.tests.roles import as_role
from frappe.tests.utils import FrappeTestCase
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from mint.api.boot import get_navbar_boot_api
from mint.www.mint import get_context, get_context_for_dev


class TestMintIsOpenedByTheDesksAccountsOnly(FrappeTestCase):
    def setUp(self):
        self.addCleanup(setattr, frappe.local.flags, "redirect_location", None)

    def page(self, path=None, query=""):
        # The page's controller as a browser calls it, without the session's token or its commit.
        request = Request(EnvironBuilder(path=path, query_string=query).get_environ()) if path else None
        with patch("frappe.sessions.get_csrf_token", return_value="token"), patch.object(
            frappe.db, "commit"
        ), patch.object(frappe.local, "request", request, create=True):
            return get_context(frappe._dict())

    def assertMethodsRefuse(self):
        with patch.dict(frappe.conf, {"developer_mode": 1}):
            for method in (get_navbar_boot_api, get_context_for_dev):
                with self.subTest(method=method.__name__):
                    self.assertRaises(frappe.PermissionError, method)

    def test_a_visitor_not_signed_in_goes_to_the_login_page_and_back_to_the_same_screen(self):
        with as_role("Guest"):
            with self.assertRaises(frappe.Redirect):
                self.page("/mint/party-reconciliation", "embed=1")
            self.assertEqual(
                frappe.local.flags.redirect_location, "/login?redirect-to=/mint/party-reconciliation%3Fembed%3D1"
            )
            with self.assertRaises(frappe.Redirect):
                self.page()
            self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=/mint")
            self.assertMethodsRefuse()

    def test_a_customer_of_the_portal_is_refused(self):
        with as_role("portal_customer") as user:
            self.assertEqual(frappe.db.get_value("User", user, "user_type"), "Website User")
            self.assertRaises(frappe.PermissionError, self.page, "/mint")
            self.assertMethodsRefuse()

    def test_an_account_of_the_desk_opens_mint(self):
        with as_role("accountant") as user:
            self.assertTrue(self.page("/mint").boot)
            self.assertEqual(get_navbar_boot_api()["user"]["name"], user)
            with patch.dict(frappe.conf, {"developer_mode": 1}):
                # The boot as the page writes it, a JSON text the dev server parses again (main.tsx).
                self.assertEqual(json.loads(get_context_for_dev())["user"]["name"], user)
