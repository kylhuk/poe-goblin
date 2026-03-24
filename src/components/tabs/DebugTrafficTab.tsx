import { forwardRef, useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { RenderState } from '@/components/shared/RenderState';
import { supabase } from '@/integrations/supabase/client';
import { RefreshCw, Search, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TrafficRow {
  id: string;
  created_at: string;
  method: string;
  path: string;
  request_headers: Record<string, string> | null;
  request_body: string | null;
  response_status: number | null;
  response_headers: Record<string, string> | null;
  response_body: string | null;
}

function statusBadgeClass(status: number | null): string {
  if (!status) return 'bg-muted text-muted-foreground';
  if (status >= 200 && status < 300) return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
  if (status >= 400 && status < 500) return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
  return 'bg-destructive/20 text-destructive border-destructive/30';
}

function methodColor(method: string): string {
  switch (method) {
    case 'GET': return 'text-emerald-400';
    case 'POST': return 'text-sky-400';
    case 'PUT': case 'PATCH': return 'text-amber-400';
    case 'DELETE': return 'text-destructive';
    default: return 'text-muted-foreground';
  }
}

function formatJson(raw: string | null): string {
  if (!raw) return '';
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ago`;
}

const DebugTrafficTab = forwardRef<HTMLDivElement, Record<string, never>>(function DebugTrafficTab(_props, ref) {
  const [rows, setRows] = useState<TrafficRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState('');
  const [selectedRow, setSelectedRow] = useState<TrafficRow | null>(null);
  const [detailTab, setDetailTab] = useState<'response' | 'request'>('response');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) throw new Error('Not authenticated');

      const projectId = import.meta.env.VITE_SUPABASE_PROJECT_ID;
      const url = `https://${projectId}.supabase.co/functions/v1/api-proxy`;
      const res = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
          'x-proxy-path': '/api/v1/ops/debug-traffic',
        },
      });

      // Fallback: if backend doesn't have that endpoint, query directly
      if (!res.ok) {
        // Use the edge function to query
        const directRes = await fetch(`https://${projectId}.supabase.co/rest/v1/debug_traffic?order=created_at.desc&limit=100`, {
          headers: {
            'apikey': import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
            'Authorization': `Bearer ${token}`,
          },
        });
        if (!directRes.ok) throw new Error(`Failed to load traffic: ${directRes.status}`);
        const data = await directRes.json();
        setRows(data as TrafficRow[]);
        setError(null);
        return;
      }
      const data = await res.json();
      setRows(data as TrafficRow[]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load traffic');
    } finally {
      setLoading(false);
    }
  }, []);

  // Direct Supabase query since debug_traffic has service_role only RLS
  const loadDirect = useCallback(async () => {
    try {
      setLoading(true);
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) throw new Error('Not authenticated');

      const projectId = import.meta.env.VITE_SUPABASE_PROJECT_ID;
      // Use edge function to read debug traffic
      const res = await fetch(`https://${projectId}.supabase.co/functions/v1/debug-traffic-reader`, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
      });
      if (!res.ok) throw new Error(`Failed: ${res.status}`);
      const data = await res.json();
      setRows(data.rows as TrafficRow[]);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load traffic');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadDirect(); }, [loadDirect]);

  const filtered = filter
    ? rows.filter(r => r.path.toLowerCase().includes(filter.toLowerCase()) || r.method.includes(filter.toUpperCase()))
    : rows;

  if (loading && rows.length === 0) {
    return <div ref={ref}><RenderState kind="loading" message="Loading traffic log..." /></div>;
  }

  return (
    <div ref={ref} className="space-y-4" data-testid="panel-debug-traffic">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold font-sans text-foreground">API Traffic Log</h2>
          <p className="text-xs text-muted-foreground">{rows.length} captured requests</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input
              value={filter}
              onChange={e => setFilter(e.target.value)}
              placeholder="Filter by path..."
              className="h-8 pl-8 text-xs w-48"
            />
          </div>
          <Button variant="outline" size="sm" className="gap-1.5 h-8" onClick={loadDirect} disabled={loading}>
            <RefreshCw className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {error && <RenderState kind="degraded" message={error} />}

      <div className="space-y-1">
        {filtered.map(row => (
          <button
            key={row.id}
            type="button"
            onClick={() => { setSelectedRow(row); setDetailTab('response'); }}
            className="w-full text-left rounded border border-border bg-card/60 px-3 py-2 hover:bg-secondary/40 transition-colors"
          >
            <div className="flex items-center gap-3">
              <span className={cn("font-mono text-xs font-bold w-12", methodColor(row.method))}>{row.method}</span>
              <Badge className={cn("text-[10px] px-1.5 py-0", statusBadgeClass(row.response_status))}>
                {row.response_status ?? '?'}
              </Badge>
              <span className="font-mono text-xs text-foreground truncate flex-1">{row.path}</span>
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">{timeAgo(row.created_at)}</span>
              <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                {row.response_body ? `${(row.response_body.length / 1024).toFixed(1)}kb` : '—'}
              </span>
            </div>
          </button>
        ))}
        {filtered.length === 0 && !error && (
          <RenderState kind="empty" message={filter ? "No matching traffic" : "No traffic captured yet"} />
        )}
      </div>

      {/* Detail dialog */}
      <Dialog open={!!selectedRow} onOpenChange={open => { if (!open) setSelectedRow(null); }}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-mono text-sm">
              <span className={methodColor(selectedRow?.method ?? '')}>{selectedRow?.method}</span>
              <Badge className={cn("text-[10px]", statusBadgeClass(selectedRow?.response_status ?? null))}>
                {selectedRow?.response_status}
              </Badge>
              <span className="truncate">{selectedRow?.path}</span>
            </DialogTitle>
          </DialogHeader>

          <div className="flex gap-1 border-b border-border pb-1">
            <Button
              variant={detailTab === 'response' ? 'default' : 'ghost'}
              size="sm"
              className="h-7 text-xs"
              onClick={() => setDetailTab('response')}
            >
              Response Body
            </Button>
            <Button
              variant={detailTab === 'request' ? 'default' : 'ghost'}
              size="sm"
              className="h-7 text-xs"
              onClick={() => setDetailTab('request')}
            >
              Request
            </Button>
          </div>

          <div className="flex-1 overflow-auto">
            {detailTab === 'response' && (
              <pre className="text-[11px] font-mono text-muted-foreground whitespace-pre-wrap break-all p-3 bg-background rounded border border-border">
                {formatJson(selectedRow?.response_body ?? null) || 'No response body'}
              </pre>
            )}
            {detailTab === 'request' && (
              <div className="space-y-3 p-3">
                <div>
                  <p className="text-xs font-medium text-foreground mb-1">Headers</p>
                  <pre className="text-[11px] font-mono text-muted-foreground whitespace-pre-wrap break-all bg-background rounded border border-border p-2">
                    {selectedRow?.request_headers ? JSON.stringify(selectedRow.request_headers, null, 2) : 'None'}
                  </pre>
                </div>
                {selectedRow?.request_body && (
                  <div>
                    <p className="text-xs font-medium text-foreground mb-1">Body</p>
                    <pre className="text-[11px] font-mono text-muted-foreground whitespace-pre-wrap break-all bg-background rounded border border-border p-2">
                      {formatJson(selectedRow.request_body)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
});

DebugTrafficTab.displayName = 'DebugTrafficTab';
export default DebugTrafficTab;
