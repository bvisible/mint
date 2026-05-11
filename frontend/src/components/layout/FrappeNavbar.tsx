/**
 * FrappeNavbar — Pixel-perfect React reimplementation of the Frappe Desk navbar.
 *
 * We cannot load desk.bundle.js in our website page (timing + dependency hell
 * leads to crashes in billing.bundle, nora_debug, etc.). Instead we render a
 * compatible navbar here, styled by the same CSS classes
 * (.navbar, .navbar-brand, .nav-link...) as /app/home, and fed by the
 * mini-boot returned by mint.api.boot.get_navbar_boot().
 *
 * Mirrors the exact structure of frappe/public/js/frappe/ui/toolbar/navbar.html
 * with the additions from neoffice_theme prepended to the right nav:
 * - NORA quick chat icon
 * - Real-time clock
 * - Custom calendar SVG (month/day/weekday)
 *
 * Dropdowns are pure React state (no jQuery, no Bootstrap JS).
 *
 * Source: bvisible/Construction/frontend/src/app/layout/FrappeNavbar.tsx
 */
import { useState, useEffect, useRef } from 'react'
import type { FC } from 'react'
import { t } from './i18n'

interface UserInfoEntry {
	fullname?: string
	image?: string
	abbr?: string
	color?: string
	email?: string
}

interface NavbarBoot {
	user?: { name?: string; email?: string; user_image?: string; full_name?: string }
	user_info?: Record<string, UserInfoEntry>
	app_logo_url?: string
	navbar_settings?: { help_dropdown?: unknown[]; settings_dropdown?: unknown[] }
	is_fc_site?: boolean
	developer_mode?: boolean
}

interface CalendarData {
	month: string
	day: string
	weekday: string
}

const formatTime = () =>
	new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })

/**
 * Compute the 2-letter initials from a full name the same way Frappe Desk does:
 * first letter of the first two whitespace-separated words, uppercased.
 * "Jeremy Bvisible" -> "JB", "Jeremy" -> "J", "" -> "?".
 */
const computeAbbr = (name: string): string => {
	if (!name) return '?'
	const words = name.trim().split(/\s+/).filter(Boolean)
	if (words.length === 0) return '?'
	const first = words[0]?.charAt(0) || ''
	const second = words[1]?.charAt(0) || ''
	return (first + second).toUpperCase() || '?'
}

/**
 * Hash a string into a stable HSL background color for avatar fallbacks
 * (mirrors Frappe Desk's per-user color assignment so two users with the
 * same name get the same background tint across pages).
 */
const colorFromName = (name: string): string => {
	if (!name) return '#94a3b8'
	let h = 0
	for (let i = 0; i < name.length; i++) {
		h = (h * 31 + name.charCodeAt(i)) >>> 0
	}
	return `hsl(${h % 360}, 60%, 55%)`
}

const formatCalendar = (): CalendarData => {
	const d = new Date()
	return {
		month: d.toLocaleDateString('fr-FR', { month: 'short' }).toUpperCase().replace('.', ''),
		day: String(d.getDate()).padStart(2, '0'),
		weekday: d.toLocaleDateString('fr-FR', { weekday: 'long' }),
	}
}

export const FrappeNavbar: FC = () => {
	const boot = (typeof window !== 'undefined'
		? ((window as unknown as { frappe?: { boot?: NavbarBoot } }).frappe?.boot)
		: undefined)

	const [notifOpen, setNotifOpen] = useState(false)
	const [helpOpen, setHelpOpen] = useState(false)
	const [userMenuOpen, setUserMenuOpen] = useState(false)
	const [time, setTime] = useState<string>(formatTime)
	const [calData, setCalData] = useState<CalendarData>(formatCalendar)

	useEffect(() => {
		const tick = () => setTime(formatTime())
		const interval = setInterval(tick, 60_000)
		return () => clearInterval(interval)
	}, [])

	useEffect(() => {
		const updateCal = () => setCalData(formatCalendar())
		const now = new Date()
		const tomorrow = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)
		const msUntilMidnight = tomorrow.getTime() - now.getTime()
		let dailyInterval: ReturnType<typeof setInterval> | undefined
		const timeout = setTimeout(() => {
			updateCal()
			dailyInterval = setInterval(updateCal, 86_400_000)
		}, msUntilMidnight)
		return () => {
			clearTimeout(timeout)
			if (dailyInterval) clearInterval(dailyInterval)
		}
	}, [])

	const navRef = useRef<HTMLElement>(null)
	useEffect(() => {
		const onClick = (e: MouseEvent) => {
			if (!navRef.current?.contains(e.target as Node)) {
				setNotifOpen(false)
				setHelpOpen(false)
				setUserMenuOpen(false)
			}
		}
		document.addEventListener('click', onClick)
		return () => document.removeEventListener('click', onClick)
	}, [])

	if (!boot) return null

	const logoUrl = boot.app_logo_url || '/assets/neoffice_theme/images/neoffice_logo.svg'

	// Frappe stores per-user metadata (fullname, image, sometimes abbr) in
	// `boot.user_info[<email>]`. The mini-boot trims a few keys (no `abbr`,
	// no `color`) so we compute the 2-letter initials ourselves like Frappe
	// Desk does: take the first letter of the first two whitespace-separated
	// words ("Jeremy Bvisible" -> "JB"), uppercased.
	const myEmail = boot.user?.email || boot.user?.name || ''
	const myInfo: UserInfoEntry = (boot.user_info && boot.user_info[myEmail]) || {}
	const userName = myInfo.fullname || boot.user?.full_name || boot.user?.email || ''
	const userImage = myInfo.image || boot.user?.user_image || ''
	const userAbbr = myInfo.abbr || computeAbbr(userName)
	const isMac = typeof navigator !== 'undefined' && /Mac/.test(navigator.platform)

	// Help dropdown badge — Frappe shows the count of *contextual* help
	// links for the current page (computed server-side per route by
	// frappe.www.help). We don't have that endpoint wired up here, so we
	// keep the slot in the DOM but render no badge. Zero = hidden.
	const helpCount = 0

	const goCalendar = () => {
		window.location.href = '/app/event/view/calendar/default'
	}
	const goNora = () => {
		window.location.href = '/app/nora-chat'
	}
	const goSoftphone = () => {
		// The real Softphone widget is a modal injected by desk.bundle.js. In
		// our embedded shell we just route to the Voice Call list as a
		// reasonable fallback so the icon stays clickable.
		window.location.href = '/app/voice-call'
	}

	return (
		<div className="sticky-top">
			<header ref={navRef} className="navbar navbar-expand" role="navigation">
				<div className="container">
					<button
						className="btn-reset navbar-toggle-sidebar d-sm-none"
						aria-label={t('Toggle Sidebar')}
					>
						<svg className="es-icon icon-md">
							<use href="#es-line-align-justify" />
						</svg>
					</button>

					<a className="navbar-brand navbar-home" href="/app/home">
						<img className="app-logo" src={logoUrl} alt={t('App Logo')} />
					</a>

					<ul className="nav navbar-nav d-none d-sm-flex" id="navbar-breadcrumbs"></ul>

					<div className="navbar-collapse justify-content-end" style={{ visibility: 'visible', display: 'flex' }}>
						<form
							className="form-inline fill-width justify-content-end"
							role="search"
							onSubmit={(e) => e.preventDefault()}
						>
							<div className="input-group search-bar text-muted">
								<input
									id="navbar-search"
									type="text"
									className="form-control"
									placeholder={t('Search or type a command ({0})', [isMac ? '⌘ + G' : 'Ctrl + G'])}
									aria-haspopup="true"
								/>
								<span className="search-icon">
									<svg className="icon icon-sm">
										<use href="#icon-search" />
									</svg>
								</span>
							</div>
						</form>

						<ul className="navbar-nav">
							{/* NORA quick chat (only if NORA assets exist) */}
							<li
								className="nav-item nora-quick-chat-btn"
								title={t('Ask NORA')}
								style={{ cursor: 'pointer', margin: '0 8px' }}
								onClick={goNora}
							>
								<a
									className="nav-link"
									style={{ padding: 0, display: 'flex', alignItems: 'center' }}
								>
									<img
										src="/assets/nora/images/nora_icon.svg"
										alt="NORA"
										style={{ width: 30, height: 'auto', marginTop: 2 }}
										onError={(e) => {
											(e.currentTarget as HTMLImageElement).style.display = 'none'
										}}
									/>
								</a>
							</li>

							<div
								id="timer"
								style={{
									minWidth: 42,
									textAlign: 'center',
									whiteSpace: 'nowrap',
									fontVariantNumeric: 'tabular-nums',
								}}
							>
								{time}
							</div>

							<svg
								id="navCalendar"
								style={{ width: 40, margin: '0 10px', cursor: 'pointer' }}
								xmlns="http://www.w3.org/2000/svg"
								x="0px"
								y="0px"
								viewBox="0 0 512 512"
								onClick={goCalendar}
							>
								<title>{t('See the calendar')}</title>
								<style type="text/css">{`
									.st0{fill:transparent;stroke:#667777;stroke-width:4;stroke-miterlimit:10;}
									.st1{fill:var(--primary);}
									.st2{fill:#FFFFFF;}
									.st3{font-family:var(--font-stack);}
									.st4{font-size:140px;}
									.st5{fill:var(--text-color);}
									.st6{font-size:330px;}
									.st7{font-size:90px;}
								`}</style>
								<path
									className="st0"
									d="M78.6,2.3h354.9c42.1,0,76.3,34.2,76.3,76.3v354.9c0,42.1-34.2,76.3-76.3,76.3H78.6c-42.1,0-76.3-34.2-76.3-76.3V78.7C2.2,36.5,36.4,2.3,78.6,2.3z"
								/>
								<path
									className="st1"
									d="M76.8,0.3H435c42.5,0,77,23.9,77,53.3V125H-0.2V53.6C-0.2,24.2,34.3,0.3,76.8,0.3z"
								/>
								<g>
									<text
										id="m"
										transform="matrix(1 0 0 1 32.9795 115)"
										className="st2 st3 st4"
									>
										{calData.month}
									</text>
									<text
										id="d"
										transform="matrix(1 0 0 1 31.3086 456.3828)"
										className="st5 st3 st6"
									>
										{calData.day}
									</text>
									<text
										id="w"
										transform="matrix(1 0 0 1 40.7808 190.5273)"
										className="st5 st3 st7"
									>
										{calData.weekday}
									</text>
								</g>
							</svg>

							<li
								className={`nav-item dropdown dropdown-notifications dropdown-mobile ${notifOpen ? 'show' : ''}`}
								style={{ marginLeft: 8 }}
							>
								<button
									className="btn-reset nav-link notifications-icon text-muted"
									onClick={() => setNotifOpen((o) => !o)}
									aria-haspopup="true"
									aria-expanded={notifOpen}
								>
									<span className="notifications-seen">
										<svg className="es-icon icon-sm" style={{ stroke: 'none' }}>
											<use href="#es-line-notifications" />
										</svg>
									</span>
								</button>
								{notifOpen && (
									<div
										className="dropdown-menu notifications-list dropdown-menu-right show"
										role="menu"
									>
										<div className="notification-list-header">
											<div className="header-items"></div>
											<div className="header-actions"></div>
										</div>
										<div className="notification-list-body">
											<div className="panel-notifications">{t('No notifications')}</div>
										</div>
									</div>
								)}
							</li>

							{/* Softphone (Telephony) — DOM mirrors Frappe Desk's
							    softphone-nav-item with the inline phone path SVG and
							    the green `online` status dot. The actual softphone
							    modal is desk.bundle.js territory; we just route to
							    the Voice Call list as a clickable fallback. */}
							<li
								className="nav-item softphone-nav-item"
								id="softphone-nav-icon"
							>
								<a
									className="nav-link softphone-trigger"
									href="/app/voice-call"
									title={t('Softphone')}
									onClick={(e) => {
										e.preventDefault()
										goSoftphone()
									}}
								>
									<span
										className="softphone-icon-wrapper"
										style={{ position: 'relative', display: 'inline-block' }}
									>
										<svg
											className="icon icon-md"
											viewBox="0 0 24 24"
											fill="none"
											stroke="currentColor"
											strokeWidth={2}
										>
											<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
										</svg>
										<span
											className="softphone-status-dot online"
											style={{
												position: 'absolute',
												bottom: 0,
												right: -2,
												width: 8,
												height: 8,
												borderRadius: '50%',
												background: 'var(--green-500, #22c55e)',
												border: '1.5px solid var(--navbar-bg, white)',
											}}
										/>
									</span>
								</a>
							</li>

							<li className="vertical-bar d-none d-sm-block"></li>

							<li
								className={`nav-item dropdown dropdown-help dropdown-mobile d-none d-lg-block ${helpOpen ? 'show' : ''}`}
								style={{ position: 'relative' }}
							>
								<button
									className="btn-reset nav-link"
									onClick={() => setHelpOpen((o) => !o)}
									aria-controls="toolbar-help"
									aria-label={t('Help Dropdown')}
								>
									<span>
										{t('Help')}
										<svg className="es-icon icon-xs">
											<use href="#es-line-down" />
										</svg>
									</span>
								</button>
								{/* Help count badge — mirrors Frappe Desk's
								    span.help-links-count. Hidden when zero. */}
								{helpCount > 0 && (
									<span
										className="text-muted small text-center help-links-count"
										style={{
											position: 'absolute',
											top: 2,
											left: 6,
											minWidth: 14,
											height: 14,
											padding: '0 3px',
											borderRadius: 7,
											background: 'var(--gray-200, #e5e7eb)',
											color: 'var(--text-color, #111)',
											fontSize: 10,
											lineHeight: '14px',
											fontWeight: 600,
											pointerEvents: 'none',
										}}
									>
										{helpCount}
									</span>
								)}
								{helpOpen && (
									<div
										className="dropdown-menu dropdown-menu-right show"
										id="toolbar-help"
										role="menu"
									>
										<div id="help-links"></div>
									</div>
								)}
							</li>

							<li
								className={`nav-item dropdown dropdown-navbar-user dropdown-mobile ${userMenuOpen ? 'show' : ''}`}
							>
								<button
									className="btn-reset nav-link"
									onClick={() => setUserMenuOpen((o) => !o)}
									aria-label={t('User Menu')}
								>
									{/* Mirror Frappe Desk's avatar markup. desk.bundle.css
									    only styles the cell with a userImage; the
									    initials-only fallback needs explicit inline styles
									    in our embedded shell because we don't load
									    desk.bundle.js (which sets up frappe.avatar with
									    a per-user background color). */}
									<span
										className="avatar avatar-medium"
										title={userName}
										style={{
											display: 'inline-flex',
											alignItems: 'center',
											justifyContent: 'center',
											width: 28,
											height: 28,
											borderRadius: '50%',
											background: userImage ? 'transparent' : colorFromName(userName),
											color: '#fff',
											fontSize: 12,
											fontWeight: 600,
											lineHeight: 1,
											overflow: 'hidden',
										}}
									>
										{userImage ? (
											<img
												src={userImage}
												alt={userName}
												className="avatar-frame"
												style={{ width: '100%', height: '100%', objectFit: 'cover' }}
											/>
										) : (
											userAbbr
										)}
									</span>
								</button>
								{userMenuOpen && (
									<div
										className="dropdown-menu dropdown-menu-right show"
										id="toolbar-user"
										role="menu"
									>
										<a className="dropdown-item" href="/app/user-profile">
											{t('My Settings')}
										</a>
										<a className="dropdown-item" href="/app/user-permission">
											{t('Permissions')}
										</a>
										<div className="dropdown-divider"></div>
										<a className="dropdown-item" href="/api/method/logout">
											{t('Logout')}
										</a>
									</div>
								)}
							</li>
						</ul>
					</div>
				</div>
			</header>
		</div>
	)
}
