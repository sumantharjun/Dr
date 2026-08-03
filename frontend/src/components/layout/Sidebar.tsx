import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Droplets,
  Settings2,
  ShoppingBag,
  Activity,
  Settings,
} from "lucide-react";
import { clsx } from "clsx";
import ProfileMenu from "./ProfileMenu";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/feeding", label: "Feeding", icon: Droplets },
  { to: "/controls", label: "Controls", icon: Settings2 },
  { to: "/orders", label: "Shopping", icon: ShoppingBag },
  { to: "/activity", label: "Activity", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

interface SidebarProps {
  /** Whether the off-canvas drawer is open (mobile only). */
  open: boolean;
  /** Close the drawer — called on backdrop tap, nav tap, and the close button. */
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  return (
    <>
      {/* Backdrop — only rendered/visible on mobile when the drawer is open. */}
      <div
        onClick={onClose}
        aria-hidden="true"
        className={clsx(
          "fixed inset-0 z-40 bg-black/40 lg:hidden transition-opacity",
          open ? "opacity-100" : "opacity-0 pointer-events-none"
        )}
      />

      <aside
        className={clsx(
          // Mobile: fixed off-canvas drawer that slides in from the left.
          // Desktop (lg+): static, sticky in-flow sidebar — no transform.
          "fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200 flex flex-col h-screen",
          "transition-transform duration-300 ease-in-out lg:sticky lg:top-0 lg:z-auto lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
      {/* Logo */}
      <div className="relative flex flex-col items-center gap-2 px-5 py-5 border-b border-gray-200">
        <img
          src="/mascots/UNOBOT_Logo.png"
          alt="UNOBOT"
          className="w-48 h-auto"
        />
        {/* <div className="flex items-center gap-2">
          <div className="leading-tight">
            <span className="text-[9px] tracking-widest text-primary-600 font-medium">
              SAFE · TRUSTWORTHY · PRECISE
            </span>
          </div>
        </div> */}
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onClose}
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
          </NavLink>
        ))}
      </nav>

      {/* Profile (bottom-left) — click opens a popover: name, change password, logout */}
      <div className="px-3 py-3 border-t border-gray-200">
        <ProfileMenu />
      </div>
      </aside>
    </>
  );
}
