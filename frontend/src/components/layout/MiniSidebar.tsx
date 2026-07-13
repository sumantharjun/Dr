import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Droplets,
  Settings2,
  ShoppingBag,
  Activity,
  Settings,
  Menu,
} from "lucide-react";
import { clsx } from "clsx";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/feeding", label: "Feeding", icon: Droplets },
  { to: "/controls", label: "Controls", icon: Settings2 },
  { to: "/orders", label: "Shopping", icon: ShoppingBag },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

interface MiniSidebarProps {
  /** Expand into the full off-canvas drawer (mobile only). */
  onExpand: () => void;
}

/**
 * Slim icon-only rail shown on mobile/tablet (below `lg`) whenever the full
 * sidebar drawer is closed.
 */
export default function MiniSidebar({ onExpand }: MiniSidebarProps) {
  return (
    <aside className="lg:hidden fixed inset-y-0 left-0 z-30 w-14 bg-white border-r border-gray-200 flex flex-col items-center py-3 gap-1">
      <button
        onClick={onExpand}
        aria-label="Open menu"
        className="flex items-center justify-center w-10 h-10 rounded-lg text-gray-500 hover:bg-gray-100 mb-2"
      >
        <Menu className="w-5 h-5" />
      </button>

      <nav className="flex-1 flex flex-col items-center gap-1 w-full">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            aria-label={label}
            className={({ isActive }) =>
              clsx(
                "flex items-center justify-center w-10 h-10 rounded-lg transition-colors",
                isActive
                  ? "bg-primary-50 text-primary-700"
                  : "text-gray-500 hover:bg-gray-100 hover:text-gray-900"
              )
            }
          >
            <Icon className="w-5 h-5" />
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
