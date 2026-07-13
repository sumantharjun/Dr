import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Droplets,
  Settings2,
  Bell,
  ShoppingBag,
  Activity,
  Settings,
  Menu,
} from "lucide-react";
import { useAlertStore } from "../../store/alertStore";
import { clsx } from "clsx";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/feeding", label: "Feeding", icon: Droplets },
  { to: "/controls", label: "Controls", icon: Settings2 },
  { to: "/alerts", label: "Alerts", icon: Bell },
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
 * sidebar drawer is closed. Labels reveal on hover/focus as tooltips.
 */
export default function MiniSidebar({ onExpand }: MiniSidebarProps) {
  const unreadCount = useAlertStore((s) => s.unreadCount());

  return (
    <aside className="lg:hidden fixed inset-y-0 left-0 z-30 w-14 bg-white border-r border-gray-200 flex flex-col items-center py-3 gap-1">
      <button
        onClick={onExpand}
        aria-label="Open menu"
        className="group relative flex items-center justify-center w-10 h-10 rounded-lg text-gray-500 hover:bg-gray-100 mb-2"
      >
        <Menu className="w-5 h-5" />
        <Tooltip label="Menu" />
      </button>

      <nav className="flex-1 flex flex-col items-center gap-1 w-full">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            aria-label={label}
            className={({ isActive }) =>
              clsx(
                "group relative flex items-center justify-center w-10 h-10 rounded-lg transition-colors",
                isActive
                  ? "bg-primary-50 text-primary-700"
                  : "text-gray-500 hover:bg-gray-100 hover:text-gray-900"
              )
            }
          >
            <Icon className="w-5 h-5" />
            {label === "Alerts" && unreadCount > 0 && (
              <span className="absolute top-0.5 right-0.5 bg-red-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
            <Tooltip label={label} />
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

function Tooltip({ label }: { label: string }) {
  return (
    <span
      className={clsx(
        "pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2",
        "whitespace-nowrap rounded-md bg-gray-900 px-2 py-1 text-xs font-medium text-white",
        "opacity-0 scale-95 transition-all duration-150",
        "group-hover:opacity-100 group-hover:scale-100 group-focus-visible:opacity-100 group-focus-visible:scale-100"
      )}
    >
      {label}
    </span>
  );
}
