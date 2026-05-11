"""Mini-boot for the Frappe Desk shell (sidebar + navbar) embedded in /mint.

Frappe Desk bundles (billing.bundle.js, nora_debug.js, etc.) expect certain
keys on `frappe.boot` at `$(document).ready` time. Since we do NOT load those
bundles in our website page (pattern copied from Builder/CRM/LMS + the
neoconstruction integration), we instead inject a curated subset of the
bootinfo just large enough for the navbar/sidebar to render correctly and for
defensive reads to never hit `undefined`.

The full `frappe.sessions.get()` payload is ~150 KB and can change shape
between Frappe versions; this curated view is ~10-20 KB and exposes a stable
contract the React components depend on.
"""
from __future__ import annotations

import frappe


# Curated boot keys consumed by FrappeNavbar / FrappeSidebar React components.
# Anything not listed here is dropped from `frappe.boot` to keep the payload
# small and the contract stable. Add new keys here whenever the UI needs them.
NAVBAR_BOOT_KEYS = (
    "user",
    "user_info",
    "navbar_settings",
    "desk_settings",
    "sysdefaults",
    "sitename",
    "lang",
    "letter_heads",
    "app_data",
    "apps_data",
    "allowed_workspaces",
    "home_page",
    "notification_settings",
    "energy_points_enabled",
    "points",
    "app_logo_url",
    "changelog_feed",
    "time_zone",
    "timezone_info",
    "is_fc_site",
    "developer_mode",
    "lang_dict",
    # Sidebar-specific keys (consumed by FrappeSidebar React component).
    # `sidebar_pages` carries the workspace tree (parent_page, public flag,
    # icon, indicator_color, sequence_id, is_hidden, ...).
    "sidebar_pages",
    "workspace_to_app_map",
    "module_app",
    # NoraLearn integration relies on these keys when the popup is mounted.
    "neoffice_settings",
)


def get_navbar_boot() -> dict:
    """Return the curated bootinfo subset used by FrappeNavbar/FrappeSidebar.

    Always sets `is_fc_site` and `developer_mode` (even if missing upstream)
    so that downstream JS bundles never see `undefined` on a defensive read.
    """
    from frappe.boot import get_bootinfo

    full = get_bootinfo()
    boot = {k: full.get(k) for k in NAVBAR_BOOT_KEYS}
    boot.setdefault("is_fc_site", False)
    boot.setdefault("developer_mode", bool(frappe.conf.get("developer_mode")))
    # Preserve `__messages` so frappe._messages remains populated for `__()`.
    if "__messages" in full:
        boot["__messages"] = full["__messages"]
    return boot


@frappe.whitelist()
def get_navbar_boot_api() -> dict:
    """HTTP endpoint to refresh navbar boot from the SPA (post settings change)."""
    return get_navbar_boot()
