import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Cpu,
  Droplets,
  Settings2,
  Bell,
  ShoppingBag,
  LogOut,
  Baby,
  Activity,
} from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import { useAlertStore } from "../../store/alertStore";
import { clsx } from "clsx";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/devices", label: "Devices", icon: Cpu },
  { to: "/feeding", label: "Feeding", icon: Droplets },
  { to: "/controls", label: "Controls", icon: Settings2 },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/orders", label: "Orders", icon: ShoppingBag },
  { to: "/activity", label: "Activity", icon: Activity },
];

export default function Sidebar() {
  const { user, logout } = useAuthStore();
  const unreadCount = useAlertStore((s) => s.unreadCount());

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="flex items-center gap-2 px-6 py-5 border-b border-gray-200">
        <Baby className="text-primary-600 w-7 h-7" />
        <span className="font-bold text-lg text-gray-900">BabyFeeder</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary-50 text-primary-700"
                  : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
              )
            }
          >
            <Icon className="w-5 h-5 flex-shrink-0" />
            <span>{label}</span>
            {label === "Alerts" && unreadCount > 0 && (
              <span className="ml-auto bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User */}
      <div className="px-3 py-4 border-t border-gray-200">
        <div className="px-3 py-2 text-sm text-gray-700 font-medium truncate">{user?.full_name}</div>
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-600 hover:bg-gray-100 w-full"
        >
          <LogOut className="w-5 h-5" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
