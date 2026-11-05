//// Neoffice — added file (no upstream equivalent). The menu of a right click on a row.
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"

export type MenuItem = { label: string, onSelect: () => void }
export type MenuState = { x: number, y: number, items: MenuItem[] } | null

type Props = { menu: MenuState, onClose: () => void }

/** A menu at the pointer: the dropdown is anchored on an empty point put where the click was. */
const RowMenu = ({ menu, onClose }: Props) => (
    <DropdownMenu open={menu !== null} onOpenChange={(open) => { if (!open) onClose() }}>
        <DropdownMenuTrigger asChild>
            <span aria-hidden style={{ position: "fixed", left: menu?.x ?? 0, top: menu?.y ?? 0, width: 0, height: 0 }} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start">
            {menu?.items.map((item) => (
                <DropdownMenuItem key={item.label} onSelect={item.onSelect}>{item.label}</DropdownMenuItem>
            ))}
        </DropdownMenuContent>
    </DropdownMenu>
)

export default RowMenu
