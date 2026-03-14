import { useAuth } from '@/services/auth';
import { Button } from '@/components/ui/button';
import { LogIn, LogOut, User } from 'lucide-react';

const UserMenu = () => {
  const { user, login, logout, isLoading } = useAuth();

  if (isLoading) return null;

  if (!user) {
    return (
      <Button variant="outline" size="sm" onClick={login} className="gap-1.5 text-xs">
        <LogIn className="h-3.5 w-3.5" />
        Login via PoE
      </Button>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-1.5 text-xs text-foreground">
        <User className="h-3.5 w-3.5 text-primary" />
        <span className="font-mono">{user.accountName}</span>
      </div>
      <Button variant="ghost" size="sm" onClick={logout} className="gap-1 text-xs text-muted-foreground hover:text-destructive">
        <LogOut className="h-3.5 w-3.5" />
        Logout
      </Button>
    </div>
  );
};

export default UserMenu;
