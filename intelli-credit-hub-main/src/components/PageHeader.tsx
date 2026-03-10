import { Bell, User } from "lucide-react";
import { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  children?: ReactNode;
  showNotifications?: boolean;
  showAvatar?: boolean;
  userName?: string;
  userRole?: string;
  leftContent?: ReactNode;
}

export function PageHeader({ title, children, showNotifications = true, showAvatar = true, userName, userRole, leftContent }: PageHeaderProps) {
  return (
    <header className="flex items-center justify-between py-4 px-6 bg-card border-b border-border">
      <div className="flex items-center gap-3">
        {leftContent}
        <h1 className="text-lg font-bold">{title}</h1>
      </div>
      <div className="flex items-center gap-3">
        {children}
        {showNotifications && (
          <button className="relative p-2 rounded-full hover:bg-muted transition-colors">
            <Bell className="w-5 h-5" />
          </button>
        )}
        {showAvatar && (
          <div className="flex items-center gap-2">
            {userName && (
              <div className="text-right hidden sm:block">
                <p className="text-sm font-medium">{userName}</p>
                {userRole && <p className="text-xs text-muted-foreground">{userRole}</p>}
              </div>
            )}
            <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
              <User className="w-4 h-4 text-muted-foreground" />
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
