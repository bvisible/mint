# //// Neoffice — added file (no upstream equivalent).
# ////
# //// THE COCKPIT OF /mint READS WHAT THE DESK'S COCKPIT READS.
# ////
# //// /mint boots from a list of keys (mint.api.boot.NAVBAR_BOOT_KEYS). On 07.10 the desk
# //// listed the spaces (two-level menu) while /mint drew the old one-level menu: the keys
# //// neoffice_theme sets for that menu were not on the list. A desk user now gets every
# //// key the theme sets for its chrome; an account without a desk gets nothing more.

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from mint.api.boot import NAVBAR_BOOT_KEYS, get_navbar_boot

STAFF = "mint-boot-staff@yopmail.com"
CUSTOMER = "mint-boot-portal@yopmail.com"
THEME_PREFIXES = ("neo_", "neocockpit_", "neoffice_")


def _user(email, desk):
    if not frappe.db.exists("User", email):
        frappe.get_doc(
            {"doctype": "User", "email": email, "first_name": "Mint boot", "send_welcome_email": 0}
        ).insert(ignore_permissions=True)
    doc = frappe.get_doc("User", email)
    # user_type is derived from the roles: a desk role makes the desk user.
    if desk and "System Manager" not in {r.role for r in doc.roles}:
        doc.append("roles", {"role": "System Manager"})
        doc.save(ignore_permissions=True)


class TestTheThemeChromeReachesMint(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _user(STAFF, desk=True)
        _user(CUSTOMER, desk=False)
        # Each fixture is what its test says it is, or the test proves nothing.
        assert frappe.db.get_value("User", STAFF, "user_type") == "System User"
        assert frappe.db.get_value("User", CUSTOMER, "user_type") == "Website User"

    def tearDown(self):
        frappe.set_user("Administrator")

    def boot(self, user):
        frappe.set_user(user)
        with patch.dict(frappe.conf, {"neocockpit_two_levels": 1}):
            return get_navbar_boot()

    def test_a_desk_user_gets_the_two_level_menu(self):
        if "neoffice_theme" not in frappe.get_installed_apps():
            self.skipTest("neoffice_theme sets the keys of the two-level menu")
        boot = self.boot(STAFF)
        self.assertEqual(boot.get("neocockpit_two_levels"), 1)
        for key in ("neo_tabbed_apps", "neo_settings_app", "neo_my_space"):
            self.assertIn(key, boot)

    def test_an_account_without_a_desk_gets_no_more_than_the_list(self):
        boot = self.boot(CUSTOMER)
        extra = {key for key in boot if key.startswith(THEME_PREFIXES)} - set(NAVBAR_BOOT_KEYS)
        self.assertEqual(extra, set())
