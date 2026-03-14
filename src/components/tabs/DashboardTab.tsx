import React, { forwardRef, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { StatusDot, Freshness } from '@/components/shared/StatusIndicators';
import { RenderState } from '@/components/shared/RenderState';
import { api } from '@/services/api';
import type { Service, AppMessage } from '@/types/api';
import { Activity, AlertTriangle, TrendingUp, Server } from 'lucide-react';

const DashboardTab = forwardRef<HTMLDivElement, Record<string, never>>(function DashboardTab(_props, ref) {
  const [services, setServices] = useState<Service[]>([]);
  const [messages, setMessages] = useState<AppMessage[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getServices(), api.getMessages()])
      .then(([nextServices, nextMessages]) => {
        setServices(nextServices);
        setMessages(nextMessages);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Backend unavailable');
      });
  }, []);

  const running = services.filter(s => s.status === 'running').length;
  const errors = services.filter(s => s.status === 'error').length;
  const criticals = messages.filter(m => m.severity === 'critical');
  const topOpportunity = criticals[0]?.suggestedAction || 'No critical opportunities';

  return (
    <div ref={ref} className="space-y-6" data-testid="panel-dashboard-root">
      {/* Summary row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard icon={<Server className="h-5 w-5 text-primary" />} label="Services Running" value={`${running}/${services.length}`} />
        <SummaryCard icon={<AlertTriangle className="h-5 w-5 text-destructive" />} label="Errors" value={String(errors)} accent={errors > 0 ? 'destructive' : undefined} />
        <SummaryCard icon={<Activity className="h-5 w-5 text-warning" />} label="Critical Alerts" value={String(criticals.length)} accent={criticals.length > 0 ? 'warning' : undefined} />
        <SummaryCard icon={<TrendingUp className="h-5 w-5 text-success" />} label="Top Opportunity" value={topOpportunity} />
      </div>

      {/* Service health strip */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-sans font-semibold">Service Health</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {error && <RenderState kind="degraded" message={error} />}
            {services.map(s => (
              <div key={s.id} data-testid={`service-${s.id}`} className="flex items-center gap-2 bg-secondary/50 rounded px-3 py-2 text-sm">
                <StatusDot status={s.status} />
                <span className="text-foreground">{s.name}</span>
                <Freshness iso={s.lastCrawl} />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Top opportunities */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-sans font-semibold">Top Opportunities</CardTitle>
          <p className="text-xs text-muted-foreground">Sorted by expected net chaos per minute of human time</p>
        </CardHeader>
        <CardContent className="space-y-3">
          {criticals.slice(0, 3).map(m => (
            <div key={m.id} className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-secondary/30 rounded p-3 border border-border">
              <div className="flex-1">
                <span className="text-xs text-muted-foreground font-mono">{m.sourceModule}</span>
                <p className="text-sm text-foreground">{m.message}</p>
              </div>
              <div className="text-right">
                <span className="text-xs px-2 py-1 rounded bg-success/20 text-success font-medium">{m.suggestedAction}</span>
              </div>
            </div>
          ))}
          {criticals.length === 0 && <RenderState kind="empty" message="No critical opportunities right now" />}
        </CardContent>
      </Card>
    </div>
  );
});

DashboardTab.displayName = 'DashboardTab';
export default DashboardTab;

function SummaryCard({ icon, label, value, accent }: { icon: React.ReactNode; label: string; value: string; accent?: string }) {
  return (
    <Card className={accent === 'destructive' ? 'glow-destructive' : accent === 'warning' ? 'glow-gold' : ''}>
      <CardContent className="flex items-center gap-4 p-4">
        {icon}
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-xl font-semibold font-mono text-foreground">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}
