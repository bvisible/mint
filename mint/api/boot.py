# //// Neoffice — added file (no upstream equivalent): the curated mini-boot the embedded
# //// Frappe chrome runs on (711dfb1, 7e7e34c, 16eec35, 46cc218, 19d0c21, 2dae000, f3cec27).
# //// /mint renders the native sidebar and navbar WITHOUT desk.bundle.js, so nothing fills
# //// frappe.boot; this builds a small, stable subset instead of the ~150 KB session payload
# //// whose shape moves with the installed apps. Read by mint/www/mint.py.
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
    "surface_apps",
    "neoffice_wiki_url",
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
    # `docs` carries the metadocs (DocType/Role/User/etc.) preloaded by Frappe.
    # main.tsx calls `frappe.model.sync(frappe.boot.docs)` so this MUST be set
    # — otherwise React never mounts (Object.sync throws on undefined.docs).
    "docs",
)


def _load_ui_translations() -> dict:
    """Load translations for the apps whose strings the embedded Frappe shell
    uses (sidebar + navbar labels). Without `desk.bundle.js`, Frappe never
    pushes these strings into `frappe._messages` — we have to bake them in
    the mini-boot ourselves, otherwise `__("Help")` etc. always return EN.
    """
    from frappe.translate import get_all_translations

    try:
        # `get_all_translations(lang)` returns the merged dict for ALL apps
        # in the user's language. It's cached internally by Frappe, so the
        # cost is paid once per worker.
        return get_all_translations(frappe.local.lang) or {}
    except Exception:
        return {}


def _apply_neoffice_theme_filters(bootinfo) -> None:
    """Apply neoffice_theme's `extend_bootinfo` filters explicitly.

    extend_bootinfo hooks normally run inside `frappe.boot.get_bootinfo()`,
    but in the website-page context the bootinfo we get back here is missing
    the filters that Desk would normally have applied. Calling them by hand
    ensures `/mint` shows the SAME app_data + workspaces + form_width as
    `/app/home` (no Mode simplifié, no Fiduciary, etc.).

    Fail open: if neoffice_theme is missing or any filter throws, return the
    bootinfo unmodified rather than break the SPA boot.
    """
    try:
        from neoffice_theme.boot_override import (
            filter_apps_by_interface_mode,
            filter_apps_by_user_visibility,
            filter_workspaces_by_interface_mode,
            inject_user_form_width,
            apply_workspace_custom_titles,
            fix_module_wise_workspaces,
            inject_instance_config,
        )
    except Exception:
        return

    # Order matches neoffice_theme/hooks.py::extend_bootinfo so the SPA
    # payload is byte-identical to /app/home. Filters first, then the
    # title remap (else we'd rename entries about to be filtered out),
    # then the breadcrumb cross-reference fix last.
    for fn in (
        filter_apps_by_interface_mode,
        filter_apps_by_user_visibility,
        filter_workspaces_by_interface_mode,
        inject_user_form_width,
        apply_workspace_custom_titles,
        fix_module_wise_workspaces,
        inject_instance_config,
    ):
        try:
            fn(bootinfo)
        except Exception:
            continue

    _translate_sidebar_labels(bootinfo)


def _translate_sidebar_labels(bootinfo) -> None:
    """Translate sidebar_pages/app_data titles server-side via frappe._().

    Defensive layer: even though Mint ships a full __messages dict and the
    React shell calls __() on render, applying server-side translation here
    keeps the data shape identical to /app/home and protects against any
    React render path that forgets to wrap a label in __(). Uses the
    existing FR/DE/IT .po entries — zero new strings.
    """
    from frappe import _

    def _xlate(s):
        return _(s) if isinstance(s, str) and s else s

    sp = getattr(bootinfo, "sidebar_pages", None)
    if isinstance(sp, dict):
        pages = sp.get("pages") or []
    elif isinstance(sp, list):
        pages = sp
    else:
        pages = []
    for p in pages:
        if isinstance(p, dict) and p.get("title"):
            p["title"] = _xlate(p["title"])

    for app in getattr(bootinfo, "app_data", None) or []:
        if isinstance(app, dict):
            if app.get("app_title"):
                app["app_title"] = _xlate(app["app_title"])
            if app.get("title"):
                app["title"] = _xlate(app["title"])


def get_navbar_boot() -> dict:
    """Return the curated bootinfo subset used by FrappeNavbar/FrappeSidebar.

    Always sets `is_fc_site` and `developer_mode` (even if missing upstream)
    so that downstream JS bundles never see `undefined` on a defensive read.

    Bakes the UI translations directly into `__messages` so the embedded
    shell's `__()` calls resolve in the user's language without needing
    desk.bundle.js.

    Re-applies neoffice_theme's `extend_bootinfo` filters explicitly so
    `app_data`, `workspaces` and form-width preferences match /app/home.
    """
    from frappe.boot import get_bootinfo

    full = get_bootinfo()

    # Apply neoffice_theme's app/workspace filters explicitly so /mint
    # matches /app/home (extend_bootinfo runs in get_bootinfo() but does not
    # always reach the website-page payload — see boot_override.py).
    _apply_neoffice_theme_filters(full)

    boot = {k: full.get(k) for k in NAVBAR_BOOT_KEYS}
    boot.setdefault("is_fc_site", False)
    boot.setdefault("developer_mode", bool(frappe.conf.get("developer_mode")))
    # Merge boot's stock `__messages` (country names, etc.) with the full
    # translation dict of every installed app so the embedded shell can
    # translate any UI string it ships.
    messages = dict(full.get("__messages") or {})
    messages.update(_load_ui_translations())
    boot["__messages"] = messages
    return boot


@frappe.whitelist()
def get_navbar_boot_api() -> dict:
    """HTTP endpoint to refresh navbar boot from the SPA (post settings change)."""
    return get_navbar_boot()
