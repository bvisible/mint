# //// Neoffice — the module docstring below is ours (711dfb1); upstream's file starts at
# //// `import frappe`. It describes the context keys the Jinja template needs to render /mint
# //// inside the native Frappe chrome. (Defect: it is written in French, unlike the rest.)
"""Controller Jinja pour la page /mint (et toutes ses sous-routes).

On peuple le contexte avec :
  - boot               → window.frappe.boot pour FrappeSidebar/Navbar + frappe-react-sdk
  - csrf_token         → pour les appels POST vers /api/method/*
  - desk_css_url       → asset hashé `desk.bundle.css` (Frappe core)
  - neoffice_theme_css_url → asset `neoffice-theme.css` (theme shell)

Pattern aligné avec apps/neoconstruction/neoconstruction/www/neoconstruction.py.
"""
import frappe
import json
import frappe.sessions
import re

from frappe import _

# //// Neoffice — added (711dfb1). mint/api/boot.py is a file we added: a curated mini-boot for
# //// the embedded sidebar/navbar. Upstream imports nothing of the sort.
from mint.api.boot import get_navbar_boot

no_cache = 1

SCRIPT_TAG_PATTERN = re.compile(r"\<script[^<]*\</script\>")
CLOSING_SCRIPT_TAG_PATTERN = re.compile(r"</script\>")

# //// Neoffice — added helper (711dfb1). We serve /mint inside the native Frappe chrome
# //// WITHOUT desk.bundle.js, so the page must pull the hashed desk CSS itself; this resolves
# //// `<name>.bundle.css` through Frappe's assets map and returns "" when there is no hashed
# //// build, so get_context can fall back to the unhashed path. No upstream equivalent.

def _get_asset_url(asset_path: str) -> str:
    """Resolve `<bundle>.bundle.css|js` to its hashed URL via Frappe's assets map.

    Returns an empty string when no hashed URL is found, so the caller can fall
    back to a non-hashed path.
    """
    if ".bundle." not in asset_path:
        return ""
    try:
        from frappe.utils.jinja_globals import bundled_asset
        resolved = bundled_asset(asset_path) or ""
        if resolved and ".bundle." in resolved and resolved != asset_path:
            return resolved
        return ""
    except Exception:
        return ""


def get_context(context):
    csrf_token = frappe.sessions.get_csrf_token()
    frappe.db.commit()

    context = frappe._dict()
    context.boot = get_boot()
    context.csrf_token = csrf_token
    context.build_version = frappe.utils.get_build_version()

    # //// Neoffice — added (a822171, 711dfb1). Upstream's context stops at build_version. The
    # //// embedded shell needs the user's desk theme and the two stylesheet URLs the template
    # //// injects; loading the CSS alone is enough to render navbar and sidebar, and we
    # //// deliberately do not load desk.bundle.js (load-order and billing/nora dependency hell).
    # Get desk theme from user settings
    context.desk_theme = frappe.db.get_value("User", frappe.session.user, "desk_theme") or "Light"

    # Frappe Desk CSS bundles — same approach as neoconstruction. Loading the
    # CSS is enough to render the navbar/sidebar markup correctly; we do NOT
    # load desk.bundle.js (timing + dependency hell with billing/nora).
    context.desk_css_url = _get_asset_url("desk.bundle.css")
    context.neoffice_theme_css_url = (
        _get_asset_url("neoffice-theme.css")
        or "/assets/neoffice_theme/css/neoffice-theme.css"
    )

    return context


@frappe.whitelist(methods=['POST'], allow_guest=True)
def get_context_for_dev():
    # //// Neoffice — whitespace only: this body was reindented from tabs to 4 spaces when the file
    # //// was rewritten for the embedded shell (711dfb1). Take upstream's tabbed version.
    if not frappe.conf.developer_mode:
        frappe.throw(_('This method is only meant for developer mode'))
    return json.loads(get_boot())


def get_boot():
    try:
        # //// Neoffice — replaced frappe.sessions.get() (711dfb1). The full session boot is ~1 MB and
        # //// pulls in desk-only keys the SPA never reads; worse, it varies with the installed apps,
        # //// so the shell broke per instance. get_navbar_boot() returns a small, stable payload and
        # //// always sets the defensive keys (is_fc_site, developer_mode) the navbar reads.
        # Curated mini-boot designed for FrappeNavbar/FrappeSidebar rather than
        # the full frappe.sessions.get() payload. Keeps surface small + stable,
        # guarantees defensive keys (is_fc_site, developer_mode) are always set.
        boot = frappe._dict(get_navbar_boot())
    except Exception as e:
        raise frappe.SessionBootFailed from e

    boot_json = frappe.as_json(boot, indent=None, separators=(",", ":"))
    boot_json = SCRIPT_TAG_PATTERN.sub("", boot_json)
    boot_json = CLOSING_SCRIPT_TAG_PATTERN.sub("", boot_json)
    boot_json = json.dumps(boot_json)

    # //// Neoffice — same line as upstream, but the file now ends with a newline (upstream's does
    # //// not). Cosmetic only; take upstream's file at the merge.
    return boot_json
