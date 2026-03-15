import { forwardRef, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Freshness } from '@/components/shared/StatusIndicators';
import { CheckCircle2, XCircle } from 'lucide-react';
import { 
  getAnalyticsIngestion, 
  getAnalyticsScanner, 
  getAnalyticsAlerts, 
  getAnalyticsBacktests, 
  getAnalyticsMl, 
  getAnalyticsReport,
  type IngestionRow, 
  type ScannerRow, 
  type AlertRow, 
  type BacktestAnalytics, 
  type MlAnalytics, 
  type MlStatus,
  type ReportAnalytics 
} from '@/services/api';
import { RenderState } from '@/components/shared/RenderState';

const AnalyticsTab = forwardRef<HTMLDivElement, Record<string, never>>(function AnalyticsTab(_props, ref) {
  return (
    <div ref={ref}>
    <Tabs defaultValue="ingestion" className="space-y-4">
      <TabsList className="flex-wrap h-auto gap-1 bg-secondary/50 p-1">
        <TabsTrigger data-testid="analytics-tab-ingestion" value="ingestion" className="tab-game text-xs">Ingestion</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-scanner" value="scanner" className="tab-game text-xs">Scanner</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-alerts" value="alerts" className="tab-game text-xs">Alerts</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-backtests" value="backtests" className="tab-game text-xs">Backtests</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-ml" value="ml" className="tab-game text-xs">ML</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-reports" value="reports" className="tab-game text-xs">Reports</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-session" value="session" className="tab-game text-xs">Session</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-diagnostics" value="diagnostics" className="tab-game text-xs">Diagnostics</TabsTrigger>
      </TabsList>

      <TabsContent data-testid="analytics-panel-ingestion" value="ingestion"><IngestionPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-scanner" value="scanner"><ScannerPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-alerts" value="alerts"><AlertsPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-backtests" value="backtests"><BacktestsPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-ml" value="ml"><MlPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-reports" value="reports"><ReportsPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-session" value="session"><RenderState kind="feature_unavailable" message="Session analytics not supported by backend contract" /></TabsContent>
      <TabsContent data-testid="analytics-panel-diagnostics" value="diagnostics"><RenderState kind="feature_unavailable" message="Diagnostics not supported by backend contract" /></TabsContent>
    </Tabs>
    </div>
  );
});

AnalyticsTab.displayName = 'AnalyticsTab';
export default AnalyticsTab;

function IngestionPanel() {
  const [items, setItems] = useState<IngestionRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { 
    getAnalyticsIngestion()
      .then(setItems)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load ingestion analytics')); 
  }, []);

  if (error) return <RenderState kind="degraded" message={error} />;
  if (items.length === 0) return <RenderState kind="empty" message="No ingestion data available" />;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {items.map((item, i) => (
        <Card key={i} className="card-game">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-sans">{item.queue_key}</CardTitle>
              <span className="text-xs bg-secondary px-2 py-0.5 rounded">{item.feed_kind}</span>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Status: <span className="text-foreground font-mono">{item.status}</span></span>
              <Freshness iso={item.last_ingest_at} />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ScannerPanel() {
  const [items, setItems] = useState<ScannerRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { 
    getAnalyticsScanner()
      .then(setItems)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load scanner analytics')); 
  }, []);

  if (error) return <RenderState kind="degraded" message={error} />;
  if (items.length === 0) return <RenderState kind="empty" message="No scanner data available" />;

  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <Card key={i} className="card-game">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">{item.strategy_id}</span>
              <span className="text-xs text-muted-foreground">Recommendations: <span className="font-mono text-foreground">{item.recommendation_count}</span></span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function AlertsPanel() {
  const [items, setItems] = useState<AlertRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { 
    getAnalyticsAlerts()
      .then(setItems)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load alerts analytics')); 
  }, []);

  if (error) return <RenderState kind="degraded" message={error} />;
  if (items.length === 0) return <RenderState kind="empty" message="No alerts data available" />;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {items.map((item, i) => (
        <Card key={i} className="card-game">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-sans">{item.item_or_market_key}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Status: <span className="text-foreground font-mono">{item.status}</span></span>
              <Freshness iso={item.recorded_at} />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function BacktestsPanel() {
  const [data, setData] = useState<BacktestAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { 
    getAnalyticsBacktests()
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load backtests analytics')); 
  }, []);

  if (error) return <RenderState kind="degraded" message={error} />;
  if (!data || data.rows.length === 0) return <RenderState kind="empty" message="No backtest data available" />;

  return (
    <div className="space-y-4">
      <Card className="card-game">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-sans">Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {data.summaryRows.map((row, i) => (
              <div key={i} className="text-xs">
                <span className="text-muted-foreground">{row.status}</span>
                <p className="font-mono text-foreground">{row.count}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card className="card-game">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-sans">Details</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {data.detailRows.map((row, i) => (
              <div key={i} className="text-xs">
                <span className="text-muted-foreground">{row.status}</span>
                <p className="font-mono text-foreground">{row.count}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function statusColor(status: string): string {
  if (status.startsWith('passed') || status === 'promoted') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
  if (status === 'hold' || status.includes('hold')) return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
  return 'bg-destructive/20 text-destructive border-destructive/30';
}

function verdictColor(verdict: string): string {
  if (verdict === 'promote') return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
  if (verdict === 'hold') return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
  return 'bg-destructive/20 text-destructive border-destructive/30';
}

function humanize(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function MlPanel() {
  const [data, setData] = useState<MlAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { 
    getAnalyticsMl()
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load ML analytics')); 
  }, []);

  if (error) return <RenderState kind="degraded" message={error} />;
  if (!data) return <RenderState kind="empty" message="No ML data available" />;

  const s = data.status as MlStatus;
  const cmp = s.candidate_vs_incumbent;

  return (
    <div className="space-y-4">
      {/* Status Header */}
      <Card className="card-game">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-sans">Training Run</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-3 text-xs">
            <div>
              <span className="text-muted-foreground">League</span>
              <p className="font-mono text-foreground">{s.league}</p>
            </div>
            <div className="sm:col-span-2">
              <span className="text-muted-foreground">Run ID</span>
              <p className="font-mono text-foreground truncate">{s.run}</p>
            </div>
            <div>
              <span className="text-muted-foreground">Status</span>
              <div className="mt-0.5"><Badge className={statusColor(s.status)}>{humanize(s.status)}</Badge></div>
            </div>
            <div>
              <span className="text-muted-foreground">Verdict</span>
              <div className="mt-0.5"><Badge className={verdictColor(s.promotion_verdict)}>{humanize(s.promotion_verdict)}</Badge></div>
            </div>
            <div>
              <span className="text-muted-foreground">Active Model</span>
              <p className="font-mono text-foreground">{s.active_model_version ?? 'None'}</p>
            </div>
            <div className="col-span-2 sm:col-span-3">
              <span className="text-muted-foreground">Stop Reason</span>
              <p className="font-mono text-foreground">{humanize(s.stop_reason)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="card-game">
          <CardContent className="p-4 text-center">
            <span className="text-xs text-muted-foreground">Avg MDAPE</span>
            <p className="text-lg font-mono text-foreground">{(s.latest_avg_mdape * 100).toFixed(1)}%</p>
          </CardContent>
        </Card>
        <Card className="card-game">
          <CardContent className="p-4 text-center">
            <span className="text-xs text-muted-foreground">Interval Coverage</span>
            <p className="text-lg font-mono text-foreground">{(s.latest_avg_interval_coverage * 100).toFixed(1)}%</p>
          </CardContent>
        </Card>
      </div>

      {/* Candidate vs Incumbent */}
      {cmp && (
        <Card className="card-game">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-sans">Candidate vs Incumbent</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Metric</TableHead>
                  <TableHead className="text-xs">Candidate</TableHead>
                  <TableHead className="text-xs">Incumbent</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell className="text-xs text-muted-foreground">Run ID</TableCell>
                  <TableCell className="text-xs font-mono truncate max-w-[140px]">{cmp.candidate_run_id}</TableCell>
                  <TableCell className="text-xs font-mono truncate max-w-[140px]">{cmp.incumbent_run_id}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="text-xs text-muted-foreground">Avg MDAPE</TableCell>
                  <TableCell className="text-xs font-mono">{(cmp.candidate_avg_mdape * 100).toFixed(1)}%</TableCell>
                  <TableCell className="text-xs font-mono">{(cmp.incumbent_avg_mdape * 100).toFixed(1)}%</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="text-xs text-muted-foreground">Interval Coverage</TableCell>
                  <TableCell className="text-xs font-mono">{(cmp.candidate_avg_interval_coverage * 100).toFixed(1)}%</TableCell>
                  <TableCell className="text-xs font-mono">{(cmp.incumbent_avg_interval_coverage * 100).toFixed(1)}%</TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <div className="flex items-center gap-6 px-4 py-3 border-t border-border text-xs">
              <span className="text-muted-foreground">MDAPE Δ: <span className="font-mono text-foreground">{(cmp.mdape_improvement * 100).toFixed(1)}%</span></span>
              <span className="text-muted-foreground">Coverage Δ: <span className="font-mono text-foreground">{(cmp.coverage_delta * 100).toFixed(1)}%</span></span>
              <span className="text-muted-foreground flex items-center gap-1">
                Floor OK: {cmp.coverage_floor_ok
                  ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                  : <XCircle className="h-3.5 w-3.5 text-destructive" />}
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Route Hotspots */}
      {s.route_hotspots.length > 0 ? (
        <Card className="card-game">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-sans">Route Hotspots</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap break-all">
              {JSON.stringify(s.route_hotspots, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : (
        <p className="text-xs text-muted-foreground text-center py-2">No route hotspots</p>
      )}
    </div>
  );
}

function ReportsPanel() {
  const [data, setData] = useState<ReportAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { 
    getAnalyticsReport()
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load report analytics')); 
  }, []);

  if (error) return <RenderState kind="degraded" message={error} />;
  if (!data || data.status === 'empty') return <RenderState kind="empty" message="No report data available" />;

  return (
    <Card className="card-game">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-sans">Daily Report</CardTitle>
      </CardHeader>
      <CardContent>
        <pre className="text-xs font-mono text-muted-foreground whitespace-pre-wrap break-all">
          {JSON.stringify(data.report, null, 2)}
        </pre>
      </CardContent>
    </Card>
  );
}
