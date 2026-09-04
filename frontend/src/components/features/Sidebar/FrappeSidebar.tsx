////// Neoffice — added file (no upstream equivalent): the first hand-written copy of the Frappe
////// desk sidebar for the embedded shell (ffe2aeb). WARNING, DEAD CODE: 2c514a4 replaced it
////// with the shared NeoCockpit component and says it deleted this file, but it is still here
////// and nothing imports it. Delete it at the merge unless someone claims it.
import { useState, useEffect, useMemo } from 'react'
import {
    Briefcase,
    Users,
    FileText,
    Wrench,
    RefreshCw,
    ChevronDown,
    Circle,
    Settings,
    Headphones,
    ArrowRight,
    ArrowLeft,
    Home,
    ShoppingCart,
    Package,
    Factory,
    Calculator,
    FolderOpen,
    Tag,
    Star,
    ListOrdered,
    FileCheck,
    MapPin,
    Calendar,
    DollarSign,
    TrendingUp,
    TrendingDown,
    Filter,
    Edit,
    Plus,
    Menu,
    ExternalLink,
    Image,
    MessageSquare,
    BookOpen,
    Award,
    Target,
    Layers,
    CheckSquare,
    LayoutGrid,
    Globe,
    type LucideIcon
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Map Frappe icon names to Lucide icons
const iconMap: Record<string, LucideIcon> = {
    // Accounting & Finance
    'accounting': Calculator,
    'income': TrendingUp,
    'expenses': TrendingDown,
    'assets': Briefcase,
    'liabilities': TrendingDown,
    'receivables': ArrowRight,
    'payables': ArrowLeft,
    'money-coins-1': DollarSign,

    // Sales & CRM
    'sell': ShoppingCart,
    'selling': ShoppingCart,
    'buying': Package,
    'crm': Target,
    'customer': Users,
    'users': Users,

    // Stock & Manufacturing
    'stock': Package,
    'organization': Factory,
    'manufacturing': Factory,
    'tag': Tag,
    'change': RefreshCw,

    // HR
    'hr': Users,
    'assign': Users,
    'milestone': FileCheck,
    'non-profit': Calendar,

    // Projects
    'project': FolderOpen,
    'list': ListOrdered,
    'list-alt': ListOrdered,
    'mark-as-read': CheckSquare,

    // Support & Quality
    'support': Headphones,
    'quality': Award,

    // Settings & Tools
    'setting': Settings,
    'settings': Settings,
    'customization': Settings,
    'tool': Wrench,
    'integration': Layers,
    'getting-started': Star,

    // Files & Documents
    'file': FileText,
    'small-file': FileText,
    'folder-normal': FolderOpen,

    // Navigation & UI
    'filter': Filter,
    'edit': Edit,
    'add': Plus,
    'menu': Menu,
    'down': ChevronDown,
    'right': ArrowRight,
    'left': ArrowLeft,
    'arrow-right': ArrowRight,
    'arrow-left': ArrowLeft,
    'insert-below': Plus,
    'group-by': LayoutGrid,

    // Communication
    'message-1': MessageSquare,
    'external-link': ExternalLink,

    // Media & Content
    'image': Image,
    'image-view': Home,
    'website': Globe,
    'web': Globe,

    // Education
    'education': BookOpen,

    // Time & Status
    'refresh': RefreshCw,
    'map': MapPin,
    'star': Star,
    'unread-status': Circle,
    'primitive-dot': Circle,
    'table': LayoutGrid,

    // Default
    'default': Circle,
}

interface WorkspacePage {
    name: string
    title: string
    icon?: string
    public?: boolean | number
    app?: string
    module?: string
    parent_page?: string
}

interface AppData {
    app_name: string
    app_title: string
    app_logo_url?: string
    app_route?: string
    workspaces: string[]
}

const FrappeSidebar = () => {
    // Pinned state - when true, sidebar stays open and pushes content
    const [pinned, setPinned] = useState(() => {
        const saved = localStorage.getItem('mint-sidebar-pinned')
        return saved ? JSON.parse(saved) : false
    })
    // Hover expanded state - temporary expansion on hover
    const [hoverExpanded, setHoverExpanded] = useState(false)
    const [workspaces, setWorkspaces] = useState<WorkspacePage[]>([])
    const [apps, setApps] = useState<AppData[]>([])
    const [currentApp, setCurrentApp] = useState<string>('')
    const [appMenuOpen, setAppMenuOpen] = useState(false)

    // Sidebar is expanded if pinned OR hover expanded
    const expanded = pinned || hoverExpanded

    useEffect(() => {
        const boot = (window as any).frappe?.boot
        if (boot) {
            const pages = boot.sidebar_pages?.pages || []
            const appData = boot.app_data || []

            // Filter to parent pages only (no parent_page) and public ones
            const parentPages = pages.filter((p: WorkspacePage) =>
                !p.parent_page && (p.public === true || p.public === 1)
            )
            setWorkspaces(parentPages)
            setApps(appData)

            // Set default app - prefer one with "Accounting" workspace (for Mint finance context)
            if (appData.length > 0) {
                const financeApp = appData.find((app: AppData) =>
                    app.workspaces?.some((ws: string) =>
                        ws.toLowerCase().includes('accounting') ||
                        ws.toLowerCase().includes('finance')
                    )
                )
                if (financeApp) {
                    setCurrentApp(financeApp.app_name)
                } else {
                    // Fallback to app with most workspaces
                    const sorted = [...appData].sort((a: AppData, b: AppData) =>
                        (b.workspaces?.length || 0) - (a.workspaces?.length || 0)
                    )
                    setCurrentApp(sorted[0].app_name)
                }
            }
        }
    }, [])

    useEffect(() => {
        localStorage.setItem('mint-sidebar-pinned', JSON.stringify(pinned))
    }, [pinned])

    const getIcon = (iconName?: string): LucideIcon => {
        if (!iconName) return iconMap['default']
        return iconMap[iconName] || iconMap['default']
    }

    const currentAppData = useMemo(() => {
        return apps.find(a => a.app_name === currentApp)
    }, [apps, currentApp])

    // Filter workspaces for current app
    const filteredWorkspaces = useMemo(() => {
        if (!currentAppData?.workspaces) return workspaces.slice(0, 20)
        return workspaces.filter(w =>
            currentAppData.workspaces.includes(w.name)
        ).slice(0, 20)
    }, [workspaces, currentAppData])

    const navigateToWorkspace = (workspace: WorkspacePage) => {
        const slug = workspace.name.toLowerCase().replace(/\s+/g, '-')
        window.location.href = `/app/${slug}`
    }

    const navigateToApp = (app: AppData) => {
        setCurrentApp(app.app_name)
        setAppMenuOpen(false)
        if (app.app_route) {
            window.location.href = app.app_route
        }
    }

    const navigateToDesk = () => {
        window.location.href = '/app'
    }

    const handleCollapseClick = () => {
        if (pinned) {
            // If pinned, unpin (collapse)
            setPinned(false)
            setHoverExpanded(false)
        } else {
            // If not pinned, pin it open
            setPinned(true)
        }
    }

    // When pinned, sidebar is in normal flow and pushes content
    // When not pinned, sidebar is fixed and overlays content on hover
    if (pinned) {
        return (
            <div
                className="w-56 h-screen bg-white border-r border-gray-200 flex flex-col flex-shrink-0"
            >
                {/* App Switcher */}
                <div className="p-2 relative">
                    <button
                        onClick={() => setAppMenuOpen(!appMenuOpen)}
                        className="w-full flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100 transition-colors justify-start"
                    >
                        <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                            {currentAppData?.app_logo_url ? (
                                <img
                                    src={currentAppData.app_logo_url}
                                    alt=""
                                    className="w-8 h-8 object-contain"
                                />
                            ) : (
                                <Briefcase className="w-8 h-8 text-gray-600" strokeWidth={1.5} />
                            )}
                        </div>
                        <span className="text-sm font-medium truncate flex-1 text-left">
                            {currentAppData?.app_title || 'ERPNext'}
                        </span>
                        <ChevronDown className={cn(
                            "w-4 h-4 text-gray-400 transition-transform",
                            appMenuOpen && "rotate-180"
                        )} strokeWidth={1.5} />
                    </button>

                    {/* App Menu Dropdown */}
                    {appMenuOpen && (
                        <div className="absolute left-2 right-2 top-14 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1 max-h-80 overflow-y-auto">
                            {apps.map((app) => (
                                <button
                                    key={app.app_name}
                                    onClick={() => navigateToApp(app)}
                                    className={cn(
                                        "w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 text-left",
                                        app.app_name === currentApp && "bg-gray-50"
                                    )}
                                >
                                    <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
                                        {app.app_logo_url ? (
                                            <img src={app.app_logo_url} alt="" className="w-4 h-4 object-contain" />
                                        ) : (
                                            <Circle className="w-3 h-3" strokeWidth={1.5} />
                                        )}
                                    </div>
                                    <span className="text-sm truncate">{app.app_title}</span>
                                </button>
                            ))}
                            <div className="border-t border-gray-200 my-1" />
                            <button
                                onClick={() => { window.location.href = '/' }}
                                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 text-left"
                            >
                                <Globe className="w-4 h-4" strokeWidth={1.5} />
                                <span className="text-sm">Website</span>
                            </button>
                        </div>
                    )}
                </div>

                {/* Workspace Items */}
                <div className="flex-1 overflow-y-auto overflow-x-hidden py-1">
                    <div className="flex flex-col gap-0.5 px-2">
                        {filteredWorkspaces.map((workspace) => {
                            const Icon = getIcon(workspace.icon)
                            return (
                                <button
                                    key={workspace.name}
                                    onClick={() => navigateToWorkspace(workspace)}
                                    className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-600 hover:text-gray-900 justify-start"
                                >
                                    <Icon className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
                                    <span className="text-sm truncate">
                                        {workspace.title || workspace.name}
                                    </span>
                                </button>
                            )
                        })}
                    </div>
                </div>

                {/* Collapse Toggle - Arrow Left when pinned */}
                <div className="p-2 border-t border-gray-100">
                    <button
                        onClick={handleCollapseClick}
                        className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-400 justify-start"
                    >
                        <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
                        <span className="text-sm">Collapse</span>
                    </button>
                </div>
            </div>
        )
    }

    // Not pinned - fixed overlay behavior
    return (
        <>
            {/* Spacer for collapsed sidebar */}
            <div className="w-[50px] flex-shrink-0" />

            {/* Sidebar - fixed position, overlays content on hover */}
            <div
                className={cn(
                    "fixed left-0 top-0 h-screen bg-white border-r border-gray-200 flex flex-col transition-all duration-200 z-50",
                    expanded ? "w-56 shadow-lg" : "w-[50px]"
                )}
                onMouseEnter={() => setHoverExpanded(true)}
                onMouseLeave={() => {
                    setHoverExpanded(false)
                    setAppMenuOpen(false)
                }}
            >
                {/* App Switcher */}
                <div className="p-2 relative">
                    <button
                        onClick={() => expanded ? setAppMenuOpen(!appMenuOpen) : navigateToDesk()}
                        className={cn(
                            "w-full flex items-center gap-2 p-1.5 rounded-lg hover:bg-gray-100 transition-colors",
                            expanded ? "justify-start" : "justify-center"
                        )}
                    >
                        <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
                            {currentAppData?.app_logo_url ? (
                                <img
                                    src={currentAppData.app_logo_url}
                                    alt=""
                                    className="w-8 h-8 object-contain"
                                />
                            ) : (
                                <Briefcase className="w-8 h-8 text-gray-600" strokeWidth={1.5} />
                            )}
                        </div>
                        {expanded && (
                            <>
                                <span className="text-sm font-medium truncate flex-1 text-left">
                                    {currentAppData?.app_title || 'ERPNext'}
                                </span>
                                <ChevronDown className={cn(
                                    "w-4 h-4 text-gray-400 transition-transform",
                                    appMenuOpen && "rotate-180"
                                )} />
                            </>
                        )}
                    </button>

                    {/* App Menu Dropdown */}
                    {appMenuOpen && expanded && (
                        <div className="absolute left-2 right-2 top-14 bg-white border border-gray-200 rounded-lg shadow-lg z-50 py-1 max-h-80 overflow-y-auto">
                            {apps.map((app) => (
                                <button
                                    key={app.app_name}
                                    onClick={() => navigateToApp(app)}
                                    className={cn(
                                        "w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 text-left",
                                        app.app_name === currentApp && "bg-gray-50"
                                    )}
                                >
                                    <div className="w-5 h-5 flex items-center justify-center flex-shrink-0">
                                        {app.app_logo_url ? (
                                            <img src={app.app_logo_url} alt="" className="w-4 h-4 object-contain" />
                                        ) : (
                                            <Circle className="w-3 h-3" strokeWidth={1.5} />
                                        )}
                                    </div>
                                    <span className="text-sm truncate">{app.app_title}</span>
                                </button>
                            ))}
                            <div className="border-t border-gray-200 my-1" />
                            <button
                                onClick={() => { window.location.href = '/' }}
                                className="w-full flex items-center gap-2 px-3 py-2 hover:bg-gray-100 text-left"
                            >
                                <Globe className="w-4 h-4" strokeWidth={1.5} />
                                <span className="text-sm">Website</span>
                            </button>
                        </div>
                    )}
                </div>

                {/* Workspace Items */}
                <div className="flex-1 overflow-y-auto overflow-x-hidden py-1">
                    <div className="flex flex-col gap-0.5 px-2">
                        {filteredWorkspaces.map((workspace) => {
                            const Icon = getIcon(workspace.icon)
                            return (
                                <button
                                    key={workspace.name}
                                    onClick={() => navigateToWorkspace(workspace)}
                                    className={cn(
                                        "w-full flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-600 hover:text-gray-900",
                                        expanded ? "justify-start" : "justify-center"
                                    )}
                                >
                                    <Icon className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
                                    {expanded && (
                                        <span className="text-sm truncate">
                                            {workspace.title || workspace.name}
                                        </span>
                                    )}
                                </button>
                            )
                        })}
                    </div>
                </div>

                {/* Collapse Toggle - Arrow Right when not pinned */}
                <div className="p-2 border-t border-gray-100">
                    <button
                        onClick={handleCollapseClick}
                        className={cn(
                            "w-full flex items-center gap-2 p-2 rounded-lg hover:bg-gray-100 transition-colors text-gray-400",
                            expanded ? "justify-start" : "justify-center"
                        )}
                    >
                        <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
                        {expanded && (
                            <span className="text-sm">Collapse</span>
                        )}
                    </button>
                </div>
            </div>
        </>
    )
}

export default FrappeSidebar
