import { useState } from 'react';
import { useAuth } from '@/services/auth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import { Settings, Eye, EyeOff, Save, Trash2, CheckCircle2, XCircle, AlertCircle, ExternalLink, Loader2 } from 'lucide-react';
import { API_BASE } from '@/services/config';
import { toast } from 'sonner';

const UserMenu = () => {
  const { user, login, logout, sessionState, isLoading } = useAuth();
  const [value, setValue] = useState('');
  const [showValue, setShowValue] = useState(false);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (!value.trim()) return;
    setSaving(true);
    const success = await login(value.trim());
    setSaving(false);
    if (success) {
      toast.success('Connected successfully');
      setValue('');
      setOpen(false);
    } else {
      toast.error('Login failed — check your POESESSID');
    }
  };

  const handleClear = () => {
    setValue('');
    logout();
  };

  const handleOAuthLogin = () => {
    window.location.href = `${API_BASE}/api/v1/auth/login`;
  };

  if (isLoading) return null;

  const connected = sessionState === 'connected' && !!user;

  return (
    <div className="flex items-center gap-2">
      {connected && (
        <span className="text-xs font-mono text-foreground" data-testid="auth-connected">
          {user.accountName}
        </span>
      )}
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="icon" className="h-8 w-8 gear-spin" data-testid="settings-trigger">
            <Settings className="h-4 w-4" />
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-72 space-y-3 border-primary/30 animate-scale-fade-in">
          <div className="flex items-center gap-2 text-xs">
            {sessionState === 'connected' && user ? (
              <><CheckCircle2 className="h-3.5 w-3.5 text-primary" /><span className="text-muted-foreground">Connected as <strong className="text-foreground">{user.accountName}</strong></span></>
            ) : sessionState === 'session_expired' ? (
              <><AlertCircle className="h-3.5 w-3.5 text-warning" /><span className="text-muted-foreground">Session expired</span></>
            ) : (
              <><XCircle className="h-3.5 w-3.5 text-destructive" /><span className="text-muted-foreground">Not connected</span></>
            )}
          </div>

          {/* OAuth Login */}
          {!connected && (
            <>
              <Button size="sm" className="w-full gap-2 text-xs h-8 btn-game" onClick={handleOAuthLogin}>
                <ExternalLink className="h-3.5 w-3.5" />
                Login with PoE Account
              </Button>
              <div className="flex items-center gap-2">
                <Separator className="flex-1" />
                <span className="text-xs text-muted-foreground">or</span>
                <Separator className="flex-1" />
              </div>
            </>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="poesessid" className="text-xs">POESESSID</Label>
            <div className="relative">
              <Input
                id="poesessid"
                type={showValue ? 'text' : 'password'}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="Paste your POESESSID"
                className="pr-8 text-xs h-8 font-mono focus:shadow-[0_0_12px_-3px_hsl(38,55%,42%,0.3)]"
              />
              <button
                type="button"
                onClick={() => setShowValue(!showValue)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showValue ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
          </div>

          <div className="flex gap-2">
            <Button size="sm" className="flex-1 gap-1 text-xs h-7 btn-game" onClick={handleSave} disabled={!value.trim() || saving}>
              {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Save className="h-3 w-3" />} Save
            </Button>
            <Button size="sm" variant="destructive" className="gap-1 text-xs h-7 btn-game" onClick={handleClear}>
              <Trash2 className="h-3 w-3" /> Clear
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
};

export default UserMenu;
