import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Droplets,
  Settings2,
  Bell,
  ShoppingBag,
  Activity,
  Settings,
} from "lucide-react";
import { useAlertStore } from "../../store/alertStore";
import { clsx } from "clsx";
import ProfileMenu from "./ProfileMenu";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/feeding", label: "Feeding", icon: Droplets },
  { to: "/controls", label: "Controls", icon: Settings2 },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/orders", label: "Orders", icon: ShoppingBag },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const unreadCount = useAlertStore((s) => s.unreadCount());

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col h-screen sticky top-0">
      {/* Logo */}
      <div className="flex flex-col items-center gap-2 px-5 py-5 border-b border-gray-200">
        <img
          src="/mascots/UNOVA_Logo.png"
          alt="UNOVA"
          className="w-48 h-auto"
        />
        <div className="flex items-center gap-2">
          {/* <Mascot variant="auto" size={28} /> */}
          <div className="leading-tight">
            {/* <span className="text-xs font-semibold text-gray-700 block">UNOSOL</span> */}
            <span className="text-[9px] tracking-widest text-primary-600 font-medium">
              SAFE · TRUST · PRECISE
            </span>
          </div>
        </div>
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

      {/* Profile (bottom-left) — click opens a popover: name, change password, logout */}
      <div className="px-3 py-3 border-t border-gray-200">
        <ProfileMenu />
      </div>
    </aside>
  );
}
