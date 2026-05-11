/**
 * FrappeSidebar — Pixel-perfect React reimplementation of the Frappe Desk
 * sidebar (`/app/home`), styled by the same CSS classes as `desk.bundle.css`
 * (.body-sidebar, .standard-sidebar-section, .sidebar-item-container...) and
 * fed by the mini-boot returned by `mint.api.boot.get_navbar_boot()`.
 *
 * Mirrors the exact DOM produced by:
 *   - frappe/public/js/frappe/ui/sidebar.html       (outer skeleton)
 *   - frappe/public/js/frappe/ui/sidebar.js         (workspace + module sections)
 *   - frappe/public/js/frappe/ui/apps_switcher.html (app switcher dropdown)
 *
 * Same approach as FrappeNavbar.tsx: we do NOT load desk.bundle.js, so we
 * render React markup that mimics the markup Frappe itself would produce, and
 * we let neoffice_theme CSS take care of styling.
 *
 * The hover-expand behaviour (collapsed by default, overlay-expand on hover)
 * is normally injected at runtime by neoffice-theme.js. Since we don't load
 * that bundle either, the equivalent CSS rules are added inline in the
 * frontend/index.html template inside a <style> tag.
 *
 * Source pattern: bvisible/mint/frontend/src/components/layout/FrappeSidebar.tsx
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import type { FC } from 'react'
import { t } from './i18n'

interface SidebarPage {
	name: string
	title: string
	label?: string
	public?: number | boolean
	parent_page?: string | null
	icon?: string
	indicator_color?: string
	sequence_id?: number
	is_hidden?: number
	app?: string
	module?: string
}

interface AppEntry {
	app_name: string
	app_title: string
	app_logo_url?: string
	app_route?: string
	workspaces?: string[]
	sort_order?: number
}

interface SidebarBoot {
	app_data?: AppEntry[]
	app_logo_url?: string
	sidebar_pages?: { pages?: SidebarPage[] }
	allowed_workspaces?: SidebarPage[]
	workspace_to_app_map?: Record<string, string>
	module_app?: Record<string, string>
}

const slugify = (s: string): string =>
	s.toLowerCase().replace(/\s+/g, '-').replace(/[()&]/g, '')

const FALLBACK_LOGO = '/assets/neoffice_theme/images/neoffice_logo.svg'

export const FrappeSidebar: FC = () => {
	const boot = (typeof window !== 'undefined'
		? ((window as unknown as { frappe?: { boot?: SidebarBoot } }).frappe?.boot)
		: undefined)

	// Pinned (persistent) state — `sidebar_expanded` matches the localStorage
	// key shape used by neoffice_theme so a Desk session and our SPA stay in
	// sync if the user toggles either.
	const [expanded, setExpanded] = useState<boolean>(() => {
		if (typeof window === 'undefined') return false
		const v = window.localStorage.getItem('sidebar_expanded')
		return v === 'true'
	})
	const togglePin = () => {
		setExpanded((prev) => {
			const next = !prev
			window.localStorage.setItem('sidebar_expanded', String(next))
			return next
		})
	}

	// Hover-expand state — temporary overlay on mouseenter (100ms debounce).
	const [hoverExpanded, setHoverExpanded] = useState(false)
	const hoverTimerRef = useRef<number | null>(null)

	const onMouseEnter = () => {
		if (expanded) return
		if (hoverTimerRef.current !== null) {
			window.clearTimeout(hoverTimerRef.current)
		}
		hoverTimerRef.current = window.setTimeout(() => {
			setHoverExpanded(true)
		}, 100)
	}

	const onMouseLeave = () => {
		if (hoverTimerRef.current !== null) {
			window.clearTimeout(hoverTimerRef.current)
			hoverTimerRef.current = null
		}
		setHoverExpanded(false)
	}

	useEffect(() => {
		return () => {
			if (hoverTimerRef.current !== null) {
				window.clearTimeout(hoverTimerRef.current)
			}
		}
	}, [])

	// App switcher dropdown
	const [switcherOpen, setSwitcherOpen] = useState(false)
	const sidebarRef = useRef<HTMLDivElement>(null)
	useEffect(() => {
		const handler = (e: MouseEvent) => {
			if (!sidebarRef.current?.contains(e.target as Node)) {
				setSwitcherOpen(false)
			}
		}
		document.addEventListener('click', handler)
		return () => document.removeEventListener('click', handler)
	}, [])

	// Resolve apps + current app
	const apps: AppEntry[] = useMemo(() => boot?.app_data || [], [boot])
	const sortedApps = useMemo(
		() =>
			[...apps].sort((a, b) => {
				const sa = a.sort_order ?? 999
				const sb = b.sort_order ?? 999
				if (sa !== sb) return sa - sb
				return (a.app_title || a.app_name).localeCompare(b.app_title || b.app_name)
			}),
		[apps],
	)

	// Mirror the Frappe Desk dropdown layout: the apps with sort_order < 70
	// are "primary" (Commercial, Opérations, Finance, RH...). sort_order 70
	// is conventionally "Site web" and 90+ is "Paramètres" — both rendered
	// as standalone links separated by dividers + the controls block.
	const primaryApps = useMemo(
		() => sortedApps.filter((a) => (a.sort_order ?? 999) < 70),
		[sortedApps],
	)
	const websiteApp = useMemo(
		() =>
			sortedApps.find((a) =>
				a.app_name === 'Website' || a.app_name?.toLowerCase() === 'website' || (a.sort_order ?? 0) === 70,
			),
		[sortedApps],
	)
	const settingsApp = useMemo(
		() =>
			sortedApps.find((a) =>
				a.app_name === 'Paramètres' || a.app_name?.toLowerCase() === 'settings' || (a.sort_order ?? 0) >= 90,
			),
		[sortedApps],
	)

	// Pick the "current" app:
	//   1. The app whose name matches "mint" (we're inside /mint).
	//   2. Else: the app with the most workspaces (heuristic from sidebar.js).
	//   3. Else: first sorted app.
	//   4. Else: synthetic "Workspaces" entry.
	const currentApp: AppEntry = useMemo(() => {
		const fallback: AppEntry = {
			app_name: 'frappe',
			app_title: 'Workspaces',
			app_logo_url: boot?.app_logo_url || FALLBACK_LOGO,
			app_route: '/app',
			sort_order: 999,
		}
		if (apps.length === 0) return fallback
		const mintApp = apps.find((a) => a.app_name === 'mint')
		if (mintApp) return mintApp
		const byWsCount = [...apps].sort(
			(a, b) => (b.workspaces?.length || 0) - (a.workspaces?.length || 0),
		)
		return byWsCount[0] ?? apps[0] ?? fallback
	}, [apps, boot])

	const allPages: SidebarPage[] = useMemo(
		() => boot?.sidebar_pages?.pages || boot?.allowed_workspaces || [],
		[boot],
	)

	// Visible workspaces for the current app (parents only, non-hidden).
	// Mirrors `make_sidebar` in frappe/public/js/frappe/ui/sidebar.js.
	const visibleWorkspaces = useMemo(() => {
		const parents = allPages.filter((p) => !p.parent_page && !p.is_hidden)
		if (currentApp.app_name === 'private') {
			return parents.filter((p) => !p.public)
		}
		const appWs = currentApp.workspaces || []
		if (appWs.length === 0) {
			return parents.filter((p) => p.public).slice(0, 20)
		}
		return parents.filter((p) => p.public && appWs.includes(p.name))
	}, [allPages, currentApp])

	// Active workspace — derived from current URL pathname `/app/<slug>`.
	const activeWorkspace = useMemo(() => {
		if (typeof window === 'undefined') return ''
		const match = window.location.pathname.match(/^\/app\/([^/?#]+)/)
		if (!match) return ''
		const slug = match[1]
		const found = allPages.find((p) => slugify(p.name) === slug)
		return found?.name || ''
	}, [allPages])

	if (!boot) return null

	const containerClass = [
		'body-sidebar-container',
		expanded ? 'expanded' : '',
		hoverExpanded ? 'hover-expanded' : '',
	]
		.filter(Boolean)
		.join(' ')

	const navigateApp = (e: React.MouseEvent, app: AppEntry) => {
		e.preventDefault()
		if (app.app_route) {
			window.location.href = app.app_route
		}
	}

	const renderWorkspaceIcon = (ws: SidebarPage) => {
		if (ws.icon) {
			return (
				<svg className="icon icon-md">
					<use href={`#icon-${ws.icon}`} />
				</svg>
			)
		}
		return <span className={`indicator ${ws.indicator_color || 'gray'}`} />
	}

	return (
		<div
			ref={sidebarRef}
			className={containerClass}
			onMouseEnter={onMouseEnter}
			onMouseLeave={onMouseLeave}
		>
			<div className="body-sidebar-placeholder" />
			<div className="body-sidebar">
				{/* App switcher button (always visible at the top) */}
				<a
					className="app-switcher-dropdown"
					style={{ textDecoration: 'none', cursor: 'pointer' }}
					onClick={(e) => {
						e.stopPropagation()
						setSwitcherOpen((o) => !o)
					}}
				>
					<div className="standard-sidebar-item">
						<div className="d-flex">
							<div className="sidebar-item-icon app-logo-container">
								<img
									className="app-logo"
									src={currentApp.app_logo_url || boot.app_logo_url || FALLBACK_LOGO}
									alt={currentApp.app_title}
								/>
							</div>
							<div className="sidebar-item-label app-title" style={{ marginLeft: 10 }}>
								<div className="app-title-name">{currentApp.app_title}</div>
								<div className="app-title-subtitle">{t('Active Module')}</div>
							</div>
						</div>
						<div className="sidebar-item-control">
							<button
								className="btn-reset drop-icon show-in-edit-mode"
								aria-label={t('Open app switcher')}
							>
								<svg
									className="es-icon es-line icon-sm"
									style={{ display: 'block', margin: 'auto' }}
									aria-hidden="true"
								>
									<use href="#es-line-down" />
								</svg>
							</button>
						</div>
					</div>
				</a>

				{/* App switcher menu — mirrors the structure Frappe Desk renders
				    in /app/home (apps_switcher.html + neoffice_theme controls):
				    primary apps → Site web link → Mobile apps link → controls
				    block (interface mode + theme + fullscreen + calculator +
				    form width) → Paramètres link. */}
				<div className={`app-switcher-menu ${switcherOpen ? 'show' : 'hidden'}`} role="menu">
					{primaryApps.map((app) => (
						<AppMenuItem
							key={app.app_name}
							app={app}
							active={currentApp.app_name === app.app_name}
							onNavigate={navigateApp}
						/>
					))}

					{websiteApp && (
						<>
							<div className="divider" />
							<AppMenuItem
								app={websiteApp}
								active={currentApp.app_name === websiteApp.app_name}
								onNavigate={navigateApp}
							/>
						</>
					)}

					<div className="divider" />
					<MobileAppsMenuItem />

					<div className="divider" />
					<AppSwitcherControls />

					{settingsApp && (
						<>
							<div className="divider" />
							<AppMenuItem
								app={settingsApp}
								active={currentApp.app_name === settingsApp.app_name}
								onNavigate={navigateApp}
							/>
						</>
					)}
				</div>

				{/* Top scroll area : "Navigation" + "All Modules" sections */}
				<div className="body-sidebar-top">
					<div className="sidebar-items">
						{/* Section 1 — Navigation (workspaces of current app) */}
						<div className="standard-sidebar-section nested-container" data-title="All">
							<div className="standard-sidebar-label">{t('Navigation')}</div>
							{visibleWorkspaces.map((ws) => {
								const slug = slugify(ws.name)
								const isActive = activeWorkspace === ws.name
								// Workspace.title is stored in English in the DocType
								// (e.g. "Selling", "Stock", "Buying"); Frappe Desk runs
								// it through __() at render time. Mirror that so the
								// label, the <a title> tooltip and the item-title attr
								// are all localized like /app/home.
								const wsLabel = t(ws.title || ws.label || ws.name)
								return (
									<div
										key={ws.name}
										className={`sidebar-item-container ${isActive ? 'active-sidebar' : ''}`}
										item-name={ws.name}
										item-title={wsLabel}
										item-public={ws.public ? '1' : '0'}
										item-is-hidden={ws.is_hidden ? '1' : '0'}
									>
										<div className={`standard-sidebar-item ${isActive ? 'selected' : ''}`}>
											<a
												href={`/app/${slug}`}
												className="item-anchor"
												title={wsLabel}
											>
												<span
													className="sidebar-item-icon"
													item-icon={ws.icon || 'folder-normal'}
												>
													{renderWorkspaceIcon(ws)}
												</span>
												<span className="sidebar-item-label">{wsLabel}</span>
											</a>
											<div className="sidebar-item-control" />
										</div>
										<div className="sidebar-child-item nested-container" />
									</div>
								)
							})}
						</div>

						{/* Section 2 — All Modules (mirror of app switcher, with active highlight) */}
						<div className="standard-sidebar-section modules-section" data-title="Modules">
							<div className="standard-sidebar-label">{t('All Modules')}</div>
							{sortedApps.map((app) => {
								const isActiveApp = currentApp.app_name === app.app_name
								return (
									<div
										key={app.app_name}
										className={`sidebar-item-container module-item ${isActiveApp ? 'active-sidebar active-module' : ''}`}
										data-app-name={app.app_name}
										data-app-route={app.app_route}
									>
										<div className="standard-sidebar-item">
											<a
												className="item-anchor"
												href={app.app_route || '/app'}
												title={app.app_title}
												onClick={(e) => navigateApp(e, app)}
											>
												<span className="sidebar-item-icon app-logo-container">
													<img
														className="app-logo"
														src={app.app_logo_url || FALLBACK_LOGO}
														alt={app.app_title}
													/>
												</span>
												<span className="sidebar-item-label">{app.app_title}</span>
											</a>
										</div>
									</div>
								)
							})}
						</div>
					</div>
				</div>

				{/* Bottom — collapse / expand pin toggle */}
				<div className="body-sidebar-bottom">
					<a
						className="collapse-sidebar-link"
						onClick={togglePin}
						style={{ cursor: 'pointer' }}
					>
						<svg className="icon icon-sm" style={{ marginTop: -2 }}>
							<use
								href={
									expanded ? '#es-line-arrow-left' : '#es-line-arrow-right'
								}
							/>
						</svg>
						<span className="collapse-sidebar-label">
							{' '}{expanded ? t('Collapse') : t('Expand')}
						</span>
					</a>
				</div>
			</div>

			{/* Mobile overlay (kept for parity, MVP focuses on desktop) */}
			<div className="overlay" style={{ zIndex: 1021 }} />
		</div>
	)
}

/* -------------------------------------------------------------------------- */
/*  App switcher dropdown sub-components                                      */
/* -------------------------------------------------------------------------- */

/**
 * Standard app entry inside the app-switcher dropdown menu — matches
 * frappe/public/js/frappe/ui/apps_switcher.html. The class names align with
 * desk.bundle.css and neoffice-theme.css so we don't need inline styles.
 */
const AppMenuItem: FC<{
	app: AppEntry
	active: boolean
	onNavigate: (e: React.MouseEvent, app: AppEntry) => void
}> = ({ app, active, onNavigate }) => (
	<div
		className={`app-item ${active ? 'active' : ''}`}
		data-app-name={app.app_name}
		data-app-route={app.app_route}
	>
		<a
			href={app.app_route || '/app'}
			onClick={(e) => onNavigate(e, app)}
		>
			<div className="sidebar-item-icon">
				<img
					className="app-logo"
					src={app.app_logo_url || FALLBACK_LOGO}
					alt={app.app_title}
				/>
			</div>
			<span className="app-item-title">{app.app_title}</span>
		</a>
	</div>
)

/**
 * Synthetic "Applications Mobiles" link (Frappe Desk hardcodes it in the
 * neoffice-theme app-switcher). Routes to the Mobile App settings page.
 */
const MobileAppsMenuItem: FC = () => (
	<div className="app-item">
		<a href="/app/mobile-app">
			<div className="sidebar-item-icon">
				<img
					className="app-logo"
					src="/assets/frappe/images/mobile-app.svg"
					alt={t('Mobile Apps')}
				/>
			</div>
			<span className="app-item-title">{t('Mobile Apps')}</span>
		</a>
	</div>
)

/**
 * App-switcher controls block (interface mode + theme + fullscreen +
 * calculator + form width). Mirrors the markup neoffice-theme.js injects in
 * /app/home so desk.bundle.css + neoffice-theme.css style it identically.
 *
 * Persistence is local-only (localStorage). The "Calculatrice" button is a
 * placeholder — the real Frappe calculator widget lives in desk.bundle.js
 * which we don't load in the embedded shell.
 */
const AppSwitcherControls: FC = () => {
	type Mode = 'Simple' | 'Advanced'
	type Width = 'S' | 'M' | 'L'

	const [mode, setMode] = useState<Mode>(() => {
		if (typeof window === 'undefined') return 'Advanced'
		return (window.localStorage.getItem('interface_mode') as Mode) || 'Advanced'
	})
	const [theme, setTheme] = useState<'light' | 'dark'>(() => {
		if (typeof window === 'undefined') return 'light'
		return document.body.classList.contains('dark') ? 'dark' : 'light'
	})
	const [width, setWidth] = useState<Width>(() => {
		if (typeof window === 'undefined') return 'L'
		return (window.localStorage.getItem('form_width_preference') as Width) || 'L'
	})

	const updateMode = (next: Mode) => {
		setMode(next)
		window.localStorage.setItem('interface_mode', next)
	}
	const toggleTheme = () => {
		const next = theme === 'dark' ? 'light' : 'dark'
		setTheme(next)
		document.body.classList.remove('light', 'dark')
		document.body.classList.add(next)
		window.localStorage.setItem('desk_theme', next)
	}
	const toggleFullscreen = () => {
		if (document.fullscreenElement) {
			document.exitFullscreen?.()
		} else {
			document.documentElement.requestFullscreen?.()
		}
	}
	const updateWidth = (next: Width) => {
		setWidth(next)
		window.localStorage.setItem('form_width_preference', next)
	}
	const openCalculator = () => {
		// Real calculator lives in desk.bundle.js; route to a fallback page so
		// the click is not a no-op for the user.
		window.location.href = '/app/calculator'
	}

	return (
		<div className="app-switcher-controls" onClick={(e) => e.stopPropagation()}>
			{/* Interface mode toggle */}
			<div className="interface-mode-switch app-switcher-interface-toggle">
				<div className="interface-switch-label">{t("Interface Mode")}</div>
				<div className="switches-container-apps">
					<input
						type="radio"
						id="appsSwitchSimple"
						name="apps-interface-switch"
						value="Simple"
						checked={mode === 'Simple'}
						onChange={() => updateMode('Simple')}
					/>
					<input
						type="radio"
						id="appsSwitchAdvanced"
						name="apps-interface-switch"
						value="Advanced"
						checked={mode === 'Advanced'}
						onChange={() => updateMode('Advanced')}
					/>
					<label htmlFor="appsSwitchSimple">{t('Simple')}</label>
					<label htmlFor="appsSwitchAdvanced">{t('Advanced')}</label>
					<div className="switch-wrapper">
						<div className="neoswitch-apps">
							<div>{t('Simple')}</div>
							<div>{t('Advanced')}</div>
						</div>
					</div>
				</div>
			</div>

			{/* Quick actions row 1: theme toggle + fullscreen */}
			<div className="app-switcher-quick-actions">
				<button
					className="quick-action-btn"
					id="appsSwitcherThemeToggle"
					title={theme === 'dark' ? t('Switch to Light Mode') : t('Switch to Dark Mode')}
					onClick={toggleTheme}
				>
					<span className="quick-action-icon">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							width="18"
							height="18"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							strokeWidth="2"
							strokeLinecap="round"
							strokeLinejoin="round"
						>
							{theme === 'dark' ? (
								<>
									<circle cx="12" cy="12" r="5" />
									<line x1="12" y1="1" x2="12" y2="3" />
									<line x1="12" y1="21" x2="12" y2="23" />
									<line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
									<line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
									<line x1="1" y1="12" x2="3" y2="12" />
									<line x1="21" y1="12" x2="23" y2="12" />
									<line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
									<line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
								</>
							) : (
								<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
							)}
						</svg>
					</span>
					<span className="quick-action-label">
						{theme === 'dark' ? t('Light') : t('Dark')}
					</span>
				</button>
				<button
					className="quick-action-btn quick-action-icon-only"
					id="appsSwitcherFullscreen"
					title={t('Toggle Fullscreen')}
					onClick={toggleFullscreen}
				>
					<span className="quick-action-icon">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							width="18"
							height="18"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							strokeWidth="2"
							strokeLinecap="round"
							strokeLinejoin="round"
						>
							<polyline points="15 3 21 3 21 9" />
							<polyline points="9 21 3 21 3 15" />
							<line x1="21" y1="3" x2="14" y2="10" />
							<line x1="3" y1="21" x2="10" y2="14" />
						</svg>
					</span>
				</button>
			</div>

			{/* Quick actions row 2: calculator */}
			<div className="app-switcher-quick-actions app-switcher-tools-row">
				<button
					className="quick-action-btn"
					id="appsSwitcherCalculator"
					title={t('Calculator')}
					onClick={openCalculator}
				>
					<span className="quick-action-icon">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							width="18"
							height="18"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							strokeWidth="2"
							strokeLinecap="round"
							strokeLinejoin="round"
						>
							<rect x="4" y="2" width="16" height="20" rx="2" />
							<line x1="8" y1="6" x2="16" y2="6" />
							<line x1="8" y1="10" x2="10" y2="10" />
							<line x1="12" y1="10" x2="14" y2="10" />
							<line x1="16" y1="10" x2="16" y2="10" />
							<line x1="8" y1="14" x2="10" y2="14" />
							<line x1="12" y1="14" x2="14" y2="14" />
							<line x1="16" y1="14" x2="16" y2="14" />
							<line x1="8" y1="18" x2="10" y2="18" />
							<line x1="12" y1="18" x2="14" y2="18" />
							<line x1="16" y1="18" x2="16" y2="18" />
						</svg>
					</span>
					<span className="quick-action-label">{t('Calculator')}</span>
				</button>
			</div>

			{/* Form width segments S/M/L */}
			<div className="form-width-switch app-switcher-interface-toggle">
				<div className="interface-switch-label">{t('Form Width')}</div>
				<div
					className="form-width-segments"
					role="radiogroup"
					aria-label={t('Form Width')}
				>
					{(['S', 'M', 'L'] as Width[]).map((w) => (
						<button
							key={w}
							type="button"
							className={`form-width-segment ${width === w ? 'active' : ''}`}
							onClick={() => updateWidth(w)}
						>
							{w}
						</button>
					))}
				</div>
			</div>
		</div>
	)
}
