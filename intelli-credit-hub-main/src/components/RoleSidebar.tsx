import { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { LogOut } from "lucide-react";

interface SidebarItem {
  icon: ReactNode;
  label: string;
  path: string;
}

interface RoleSidebarProps {
  items: SidebarItem[];
  logo?: ReactNode;
  onLogout?: () => void;
}

export function RoleSidebar({ items, logo, onLogout }: RoleSidebarProps) {
  const location = useLocation();

  return (
    <aside className="w-[240px] min-h-screen bg-primary flex flex-col p-4 shrink-0">
      <div className="flex items-center gap-2 px-3 py-4 mb-6">
        {logo || (
          <div className="w-9 h-9 rounded-lg bg-primary-foreground flex items-center justify-center text-primary font-extrabold text-sm">
            IC
          </div>
        )}
        <span className="text-primary-foreground font-bold text-lg">Intelli-Credit</span>
      </div>
      <nav className="flex-1 flex flex-col gap-1">
        {items.map((item) => {
          const active = location.pathname === item.path || location.pathname.startsWith(item.path + "/");
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                  : "text-primary-foreground/70 hover:text-primary-foreground hover:bg-sidebar-accent/50"
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <button
        onClick={onLogout || (() => (window.location.href = "/auth/login"))}
        className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-primary-foreground/70 hover:text-primary-foreground hover:bg-sidebar-accent/50 transition-colors mt-auto"
      >
        <LogOut className="w-4 h-4" />
        <span>Logout</span>
      </button>
    </aside>
  );
}
