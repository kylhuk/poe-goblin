import { forwardRef, useCallback, useEffect, useState } from 'react';
import { Slider } from '@/components/ui/slider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Freshness } from '@/components/shared/StatusIndicators';
import { CheckCircle2, XCircle } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { 
  getAnalyticsIngestion, 
  getAnalyticsScanner, 
  getAnalyticsAlerts, 
  getAnalyticsBacktests, 
  getAnalyticsMl, 
  getAnalyticsPricingOutliers,
  getAnalyticsReport,
  getAnalyticsSearchHistory,
  getAnalyticsSearchSuggestions,
  type IngestionRow, 
  type ScannerRow, 
  type AlertRow, 
  type BacktestAnalytics, 
  type MlAnalytics, 
  type MlStatus,
  type MlRouteHotspot,
  type ReportAnalytics,
  type ReportData,
} from '@/services/api';
import { api } from '@/services/api';
import type { MlAutomationStatus, MlAutomationHistory, PricingOutliersResponse, SearchHistoryResponse, SearchSuggestion } from '@/types/api';
import { RenderState } from '@/components/shared/RenderState';

interface AnalyticsTabProps {
  subtab?: string;
  onSubtabChange?: (subtab: string) => void;
}

const AnalyticsTab = forwardRef<HTMLDivElement, AnalyticsTabProps>(function AnalyticsTab({ subtab, onSubtabChange }, ref) {
  const activeSubtab = subtab || "ingestion";
  const handleSubtabChange = (value: string) => {
    if (onSubtabChange) onSubtabChange(value);
  };
  return (
    <div ref={ref}>
    <Tabs value={activeSubtab} onValueChange={handleSubtabChange} className="space-y-4">
      <TabsList className="flex-wrap h-auto gap-1 bg-secondary/50 p-1">
        <TabsTrigger data-testid="analytics-tab-ingestion" value="ingestion" className="tab-game text-xs">Ingestion</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-scanner" value="scanner" className="tab-game text-xs">Scanner</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-alerts" value="alerts" className="tab-game text-xs">Alerts</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-backtests" value="backtests" className="tab-game text-xs">Backtests</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-ml" value="ml" className="tab-game text-xs">ML</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-reports" value="reports" className="tab-game text-xs">Reports</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-search" value="search" className="tab-game text-xs">Search</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-outliers" value="outliers" className="tab-game text-xs">Outliers</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-session" value="session" className="tab-game text-xs">Session</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-diagnostics" value="diagnostics" className="tab-game text-xs">Diagnostics</TabsTrigger>
      </TabsList>

      <TabsContent data-testid="analytics-panel-ingestion" value="ingestion"><IngestionPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-scanner" value="scanner"><ScannerPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-alerts" value="alerts"><AlertsPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-backtests" value="backtests"><BacktestsPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-ml" value="ml"><MlPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-reports" value="reports"><ReportsPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-search" value="search"><SearchHistoryPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-outliers" value="outliers"><PricingOutliersPanel /></TabsContent>
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
  const load = useCallback(() => {
    getAnalyticsIngestion()
      .then(setItems)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load ingestion analytics'));
  }, []);
  useEffect(() => { load(); const iv = setInterval(load, 5_000); return () => clearInterval(iv); }, [load]);

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
  const load = useCallback(() => {
    getAnalyticsScanner()
      .then(setItems)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load scanner analytics'));
  }, []);
  useEffect(() => { load(); const iv = setInterval(load, 5_000); return () => clearInterval(iv); }, [load]);

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
  const load = useCallback(() => {
    getAnalyticsAlerts()
      .then(setItems)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load alerts analytics'));
  }, []);
  useEffect(() => { load(); const iv = setInterval(load, 5_000); return () => clearInterval(iv); }, [load]);

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
  const load = useCallback(() => {
    getAnalyticsBacktests()
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load backtests analytics'));
  }, []);
  useEffect(() => { load(); const iv = setInterval(load, 5_000); return () => clearInterval(iv); }, [load]);

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
  if (!status || status === 'unknown' || status === 'no_runs') return 'bg-muted text-muted-foreground border-border';
  if (status === 'completed' || status.startsWith('passed') || status === 'promoted' || status === 'succeeded' || status === 'ready') {
    return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
  }
  if (status === 'running' || status.includes('running') || status === 'in_progress') {
    return 'bg-sky-500/20 text-sky-400 border-sky-500/30';
  }
  if (status === 'hold' || status.includes('hold') || status === 'failed_gates' || status === 'stopped_budget' || status === 'stopped_no_improvement') {
    return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
  }
  return 'bg-destructive/20 text-destructive border-destructive/30';
}

function verdictColor(verdict: string): string {
  if (!verdict || verdict === 'unknown' || verdict === 'none') return 'bg-muted text-muted-foreground border-border';
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
  const [automationStatus, setAutomationStatus] = useState<MlAutomationStatus | null>(null);
  const [automationHistory, setAutomationHistory] = useState<MlAutomationHistory | null>(null);
  const [automationError, setAutomationError] = useState<string | null>(null);

  const load = useCallback(() => {
    getAnalyticsMl()
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load ML analytics'));

    Promise.all([api.getMlAutomationStatus(), api.getMlAutomationHistory()])
      .then(([status, history]) => {
        setAutomationStatus(status);
        setAutomationHistory(history);
      })
      .catch(err => setAutomationError(err instanceof Error ? err.message : 'Failed to load automation data'));
  }, []);
  useEffect(() => { load(); const iv = setInterval(load, 5_000); return () => clearInterval(iv); }, [load]);

  if (error) return <RenderState kind="degraded" message={error} />;
  if (!data?.status) {
    return <RenderState kind="empty" message="No ML data available" />;
  }

  const s = data.status as MlStatus;
  const cmp = s.candidate_vs_incumbent ?? null;

  return (
    <div className="space-y-4">
      {/* Warmup notice */}
      {s.warmup && (
        <Card className="card-game border-sky-500/30">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 text-xs">
              <Badge className="bg-sky-500/20 text-sky-400 border-sky-500/30">Warmup</Badge>
              <span className="text-muted-foreground">{s.warmup.message || 'Model warming up'}</span>
              {s.warmup.runs_needed != null && s.warmup.runs_completed != null && (
                <span className="font-mono text-foreground ml-auto">
                  {s.warmup.runs_completed}/{s.warmup.runs_needed} runs
                </span>
              )}
            </div>
          </CardContent>
        </Card>
      )}

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
            <div className="col-span-2 sm:col-span-3">
              <p className="text-[11px] text-muted-foreground">
                Status reflects whether training and evaluation finished. Verdict shows whether the latest candidate replaced the incumbent model.
              </p>
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
            <p className="text-lg font-mono text-foreground">{s.latest_avg_mdape != null ? (s.latest_avg_mdape * 100).toFixed(1) : '—'}%</p>
          </CardContent>
        </Card>
        <Card className="card-game">
          <CardContent className="p-4 text-center">
            <span className="text-xs text-muted-foreground">Interval Coverage</span>
            <p className="text-lg font-mono text-foreground">{s.latest_avg_interval_coverage != null ? (s.latest_avg_interval_coverage * 100).toFixed(1) : '—'}%</p>
          </CardContent>
        </Card>
      </div>

      {/* Promotion Policy */}
      {s.promotion_policy && (
        <Card className="card-game">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-sans">Promotion Gates</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-2 text-xs">
              {s.promotion_policy.mdape_ceiling != null && (
                <div>
                  <span className="text-muted-foreground">MDAPE Ceiling</span>
                  <p className="font-mono text-foreground">{(s.promotion_policy.mdape_ceiling * 100).toFixed(1)}%</p>
                </div>
              )}
              {s.promotion_policy.coverage_floor != null && (
                <div>
                  <span className="text-muted-foreground">Coverage Floor</span>
                  <p className="font-mono text-foreground">{(s.promotion_policy.coverage_floor * 100).toFixed(1)}%</p>
                </div>
              )}
              {s.promotion_policy.min_rows != null && (
                <div>
                  <span className="text-muted-foreground">Min Rows</span>
                  <p className="font-mono text-foreground">{s.promotion_policy.min_rows.toLocaleString()}</p>
                </div>
              )}
              {Object.entries(s.promotion_policy)
                .filter(([k]) => !['mdape_ceiling', 'coverage_floor', 'min_rows', 'mdapeCeiling', 'coverageFloor', 'minRows'].includes(k))
                .map(([k, v]) => (
                  <div key={k}>
                    <span className="text-muted-foreground">{humanize(k)}</span>
                    <p className="font-mono text-foreground">{typeof v === 'number' ? (v < 1 ? (v * 100).toFixed(1) + '%' : v.toLocaleString()) : String(v ?? '—')}</p>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      )}

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
                  <TableCell className="text-xs font-mono truncate max-w-[140px]">{cmp.candidate_run_id || '—'}</TableCell>
                  <TableCell className="text-xs font-mono truncate max-w-[140px]">{cmp.incumbent_run_id || '—'}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="text-xs text-muted-foreground">Avg MDAPE</TableCell>
                  <TableCell className="text-xs font-mono">{cmp.candidate_avg_mdape != null ? (cmp.candidate_avg_mdape * 100).toFixed(1) + '%' : '—'}</TableCell>
                  <TableCell className="text-xs font-mono">{cmp.incumbent_avg_mdape != null ? (cmp.incumbent_avg_mdape * 100).toFixed(1) + '%' : '—'}</TableCell>
                </TableRow>
                <TableRow>
                  <TableCell className="text-xs text-muted-foreground">Interval Coverage</TableCell>
                  <TableCell className="text-xs font-mono">{cmp.candidate_avg_interval_coverage != null ? (cmp.candidate_avg_interval_coverage * 100).toFixed(1) + '%' : '—'}</TableCell>
                  <TableCell className="text-xs font-mono">{cmp.incumbent_avg_interval_coverage != null ? (cmp.incumbent_avg_interval_coverage * 100).toFixed(1) + '%' : '—'}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <div className="flex items-center gap-6 px-4 py-3 border-t border-border text-xs">
              <span className="text-muted-foreground">MDAPE Δ: <span className="font-mono text-foreground">{cmp.mdape_improvement != null ? (cmp.mdape_improvement * 100).toFixed(1) + '%' : '—'}</span></span>
              <span className="text-muted-foreground">Coverage Δ: <span className="font-mono text-foreground">{cmp.coverage_delta != null ? (cmp.coverage_delta * 100).toFixed(1) + '%' : '—'}</span></span>
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
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Route</TableHead>
                  <TableHead className="text-xs">MDAPE</TableHead>
                  <TableHead className="text-xs">Coverage</TableHead>
                  <TableHead className="text-xs">Samples</TableHead>
                  <TableHead className="text-xs">Anomaly</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {s.route_hotspots.map((h: MlRouteHotspot, i: number) => (
                  <TableRow key={i}>
                    <TableCell className="text-xs font-mono">{h.route ?? '—'}</TableCell>
                    <TableCell className="text-xs font-mono">{h.avg_mdape != null ? (h.avg_mdape * 100).toFixed(1) + '%' : '—'}</TableCell>
                    <TableCell className="text-xs font-mono">{h.avg_interval_coverage != null ? (h.avg_interval_coverage * 100).toFixed(1) + '%' : '—'}</TableCell>
                    <TableCell className="text-xs font-mono">{h.sample_count?.toLocaleString() ?? '—'}</TableCell>
                    <TableCell className="text-xs">
                      {h.anomaly === true
                        ? <Badge className="bg-amber-500/20 text-amber-400 border-amber-500/30 text-[10px]">Yes</Badge>
                        : h.anomaly === false
                          ? <span className="text-muted-foreground">No</span>
                          : <span className="text-muted-foreground">—</span>}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : (
        <p className="text-xs text-muted-foreground text-center py-2">No route hotspots</p>
      )}

      {/* ML Automation Section */}
      <MlAutomationPanel status={automationStatus} history={automationHistory} error={automationError} />
    </div>
  );
}

function MlAutomationPanel({ status, history, error }: { status: MlAutomationStatus | null; history: MlAutomationHistory | null; error: string | null }) {
  if (error) {
    return (
      <Card className="card-game">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-sans">ML Automation</CardTitle>
        </CardHeader>
        <CardContent>
          <RenderState kind="degraded" message={error} />
        </CardContent>
      </Card>
    );
  }

  const summary = history?.summary ?? null;
  const qualityTrend = history?.qualityTrend ?? [];
  const trainingCadence = history?.trainingCadence ?? [];
  const routeMetrics = history?.routeMetrics ?? [];
  const datasetCoverage = history?.datasetCoverage ?? null;
  const promotions = history?.promotions ?? [];
  const runs = history?.history ?? [];
  const mdapeTrendData = qualityTrend
    .filter((point) => point.avgMdape != null)
    .map((point, index) => ({
      label: point.updatedAt ? formatMiniDate(point.updatedAt) : `Run ${index + 1}`,
      value: point.avgMdape != null ? Number((point.avgMdape * 100).toFixed(2)) : null,
    }));
  const coverageTrendData = qualityTrend
    .filter((point) => point.avgIntervalCoverage != null)
    .map((point, index) => ({
      label: point.updatedAt ? formatMiniDate(point.updatedAt) : `Run ${index + 1}`,
      value: point.avgIntervalCoverage != null ? Number((point.avgIntervalCoverage * 100).toFixed(2)) : null,
    }));
  const cadenceData = trainingCadence.map((point) => ({
    label: point.date.slice(5),
    runs: point.runs,
  }));
  const deltaLabel = summary?.mdapeDeltaVsPrevious != null
    ? `${summary.mdapeDeltaVsPrevious >= 0 ? '+' : ''}${(summary.mdapeDeltaVsPrevious * 100).toFixed(1)} pts`
    : '—';

  return (
    <div className="space-y-4">
      {status && (
        <Card className="card-game">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-sans">Automation Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-3 text-xs">
              <div>
                <span className="text-muted-foreground">League</span>
                <p className="font-mono text-foreground">{status.league}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Active Model</span>
                <p className="font-mono text-foreground">{status.activeModelVersion ?? 'None'}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Status</span>
                <div className="mt-0.5">
                  <Badge className={status.status ? statusColor(status.status) : 'bg-muted text-muted-foreground border-border'}>
                    {status.status ? humanize(status.status) : 'Unknown'}
                  </Badge>
                </div>
              </div>
              <div>
                <span className="text-muted-foreground">Verdict</span>
                <div className="mt-0.5">
                  <Badge className={status.promotionVerdict ? verdictColor(status.promotionVerdict) : 'bg-muted text-muted-foreground border-border'}>
                    {status.promotionVerdict ? humanize(status.promotionVerdict) : 'Unknown'}
                  </Badge>
                </div>
              </div>
              {status.latestRun && (
                <div className="col-span-2 sm:col-span-4">
                  <span className="text-muted-foreground">Latest Run</span>
                  <div className="flex flex-wrap items-center gap-3 mt-1">
                    <span className="font-mono text-foreground truncate">{status.latestRun.runId ?? '—'}</span>
                    <Badge className={status.latestRun.status ? statusColor(status.latestRun.status) : 'bg-muted text-muted-foreground border-border'}>
                      {status.latestRun.status ? humanize(status.latestRun.status) : 'Unknown'}
                    </Badge>
                    <span className="text-muted-foreground">{status.latestRun.updatedAt ? formatDateTimeShort(status.latestRun.updatedAt) : '—'}</span>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {summary && (
        <>
          <div className="grid grid-cols-2 xl:grid-cols-5 gap-4">
            <MlSummaryMetricCard label="Runs / 7d" value={String(summary.runsLast7d)} />
            <MlSummaryMetricCard label="Runs / 30d" value={String(summary.runsLast30d)} />
            <MlSummaryMetricCard label="Median cadence" value={summary.medianHoursBetweenRuns != null ? `${summary.medianHoursBetweenRuns.toFixed(1)}h` : '—'} />
            <MlSummaryMetricCard label="Best MDAPE" value={formatPct(summary.bestAvgMdape)} />
            <MlSummaryMetricCard label="Trend" value={humanize(summary.trendDirection)} detail={deltaLabel} />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <MlLineChartCard title="MDAPE trend" data={mdapeTrendData} emptyMessage="No completed evaluations yet" suffix="%" />
            <MlLineChartCard title="Coverage trend" data={coverageTrendData} emptyMessage="No interval coverage history yet" suffix="%" />
            <MlBarChartCard title="Training cadence" data={cadenceData} emptyMessage="No training cadence history yet" />
          </div>

          {datasetCoverage && (
            <Card className="card-game">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-sans">Dataset coverage</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 xl:grid-cols-4 gap-4 text-xs">
                  <div>
                    <span className="text-muted-foreground">Total Rows</span>
                    <p className="font-mono text-foreground">{formatCompact(datasetCoverage.totalRows)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Supported Rows</span>
                    <p className="font-mono text-foreground">{formatCompact(datasetCoverage.supportedRows)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Coverage Ratio</span>
                    <p className="font-mono text-foreground">{formatPct(datasetCoverage.coverageRatio)}</p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Base Types</span>
                    <p className="font-mono text-foreground">{datasetCoverage.baseTypeCount != null ? formatCompact(datasetCoverage.baseTypeCount) : '—'}</p>
                  </div>
                </div>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">Route</TableHead>
                      <TableHead className="text-xs text-right">Rows</TableHead>
                      <TableHead className="text-xs text-right">Share</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {datasetCoverage.routes.map((route) => (
                      <TableRow key={route.route ?? 'unknown'}>
                        <TableCell className="text-xs font-mono">{route.route ?? 'unknown'}</TableCell>
                        <TableCell className="text-xs font-mono text-right">{formatCompact(route.rows)}</TableCell>
                        <TableCell className="text-xs font-mono text-right">{formatPct(route.share)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          <Card className="card-game">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-sans">Route metrics</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Route</TableHead>
                    <TableHead className="text-xs text-right">Samples</TableHead>
                    <TableHead className="text-xs text-right">MDAPE</TableHead>
                    <TableHead className="text-xs text-right">Coverage</TableHead>
                    <TableHead className="text-xs text-right">Abstain</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {routeMetrics.map((route) => (
                    <TableRow key={route.route ?? 'unknown'}>
                      <TableCell className="text-xs font-mono">{route.route ?? 'unknown'}</TableCell>
                      <TableCell className="text-xs font-mono text-right">{route.sampleCount != null ? formatCompact(route.sampleCount) : '—'}</TableCell>
                      <TableCell className="text-xs font-mono text-right">{formatPct(route.avgMdape)}</TableCell>
                      <TableCell className="text-xs font-mono text-right">{formatPct(route.avgIntervalCoverage)}</TableCell>
                      <TableCell className="text-xs font-mono text-right">{formatPct(route.avgAbstainRate)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card className="card-game">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-sans">Model promotions</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Model</TableHead>
                    <TableHead className="text-xs">Promoted At</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {promotions.length > 0 ? promotions.map((row) => (
                    <TableRow key={`${row.modelVersion ?? 'unknown'}-${row.promotedAt ?? 'none'}`}>
                      <TableCell className="text-xs font-mono">{row.modelVersion ?? '—'}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{row.promotedAt ? formatDateTimeShort(row.promotedAt) : '—'}</TableCell>
                    </TableRow>
                  )) : (
                    <TableRow>
                      <TableCell className="text-xs text-muted-foreground" colSpan={2}>No promoted model history</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}

      {runs.length > 0 && (
        <Card className="card-game">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-sans">Run History</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="text-xs">Run ID</TableHead>
                  <TableHead className="text-xs">Status</TableHead>
                  <TableHead className="text-xs">Verdict</TableHead>
                  <TableHead className="text-xs text-right">Rows</TableHead>
                  <TableHead className="text-xs text-right">MDAPE</TableHead>
                  <TableHead className="text-xs text-right">Coverage</TableHead>
                  <TableHead className="text-xs">Updated</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {runs.map((run) => (
                  <TableRow key={run.runId ?? 'unknown'}>
                    <TableCell className="text-xs font-mono truncate max-w-[160px]">{run.runId ?? '—'}</TableCell>
                    <TableCell><Badge className={`text-xs ${run.status ? statusColor(run.status) : 'bg-muted text-muted-foreground border-border'}`}>{run.status ? humanize(run.status) : 'Unknown'}</Badge></TableCell>
                    <TableCell><Badge className={`text-xs ${run.verdict ? verdictColor(run.verdict) : 'bg-muted text-muted-foreground border-border'}`}>{run.verdict ? humanize(run.verdict) : 'Unknown'}</Badge></TableCell>
                    <TableCell className="text-xs font-mono text-right">{run.rowsProcessed != null ? formatCompact(run.rowsProcessed) : '—'}</TableCell>
                    <TableCell className="text-xs font-mono text-right">{formatPct(run.avgMdape)}</TableCell>
                    <TableCell className="text-xs font-mono text-right">{formatPct(run.avgIntervalCoverage)}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{run.updatedAt ? formatDateTimeShort(run.updatedAt) : '—'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function MlSummaryMetricCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <Card className="card-game">
      <CardContent className="p-4">
        <span className="text-xs text-muted-foreground">{label}</span>
        <p className="text-lg font-mono text-foreground">{value}</p>
        {detail ? <p className="text-[11px] text-muted-foreground mt-1">{detail}</p> : null}
      </CardContent>
    </Card>
  );
}

function MlLineChartCard({ title, data, emptyMessage, suffix }: { title: string; data: Array<{ label: string; value: number | null }>; emptyMessage: string; suffix?: string }) {
  return (
    <Card className="card-game">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-sans">{title}</CardTitle>
      </CardHeader>
      <CardContent className="h-56">
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/40" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={16} />
              <YAxis tick={{ fontSize: 11 }} width={40} />
              <RechartsTooltip formatter={(value: number) => [`${value.toFixed(1)}${suffix ?? ''}`, title]} />
              <Line type="monotone" dataKey="value" stroke="#60a5fa" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <RenderState kind="empty" message={emptyMessage} />
        )}
      </CardContent>
    </Card>
  );
}

function MlBarChartCard({ title, data, emptyMessage }: { title: string; data: Array<{ label: string; runs: number }>; emptyMessage: string }) {
  return (
    <Card className="card-game">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-sans">{title}</CardTitle>
      </CardHeader>
      <CardContent className="h-56">
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-border/40" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} minTickGap={12} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} width={32} />
              <RechartsTooltip formatter={(value: number) => [value, 'Runs']} />
              <Bar dataKey="runs" fill="#34d399" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <RenderState kind="empty" message={emptyMessage} />
        )}
      </CardContent>
    </Card>
  );
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return '—';
  return `${(value * 100).toFixed(1)}%`;
}

function formatCompact(value: number): string {
  return Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

function formatDateTimeShort(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function formatMiniDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return `${parsed.getMonth() + 1}/${parsed.getDate()}`;
}

const GOLD_LABELS: { key: keyof ReportData; label: string }[] = [
  { key: 'gold_currency_ref_hour_rows', label: 'Currency Ref' },
  { key: 'gold_listing_ref_hour_rows', label: 'Listing Ref' },
  { key: 'gold_liquidity_ref_hour_rows', label: 'Liquidity Ref' },
  { key: 'gold_bulk_premium_hour_rows', label: 'Bulk Premium' },
  { key: 'gold_set_ref_hour_rows', label: 'Set Ref' },
];

function ReportsPanel() {
  const [data, setData] = useState<ReportAnalytics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    getAnalyticsReport()
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Failed to load report analytics'));
  }, []);
  useEffect(() => { load(); const iv = setInterval(load, 5_000); return () => clearInterval(iv); }, [load]);

  if (error) return <RenderState kind="degraded" message={error} />;
  if (!data || data.status === 'empty') return <RenderState kind="empty" message="No report data available" />;

  const r = data.report as ReportData;

  return (
    <div className="space-y-4">
      {/* Header: League + PnL */}
      <Card className="card-game">
        <CardContent className="p-4 flex items-center justify-between">
          <div className="text-xs">
            <span className="text-muted-foreground">League</span>
            <p className="font-mono text-foreground">{r.league}</p>
          </div>
          <div className="text-right">
            <span className="text-xs text-muted-foreground">Realized PnL</span>
            <p className="text-lg font-mono text-foreground">
              {r.realized_pnl_chaos.toLocaleString()}<span className="text-xs text-muted-foreground ml-1">chaos</span>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Activity Counts */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {([
          ['Recommendations', r.recommendations],
          ['Alerts', r.alerts],
          ['Journal Events', r.journal_events],
          ['Journal Positions', r.journal_positions],
        ] as const).map(([label, val]) => (
          <Card key={label} className="card-game">
            <CardContent className="p-4 text-center">
              <span className="text-xs text-muted-foreground">{label}</span>
              <p className="text-lg font-mono text-foreground">{val}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Backtest Counts */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="card-game">
          <CardContent className="p-4 text-center">
            <span className="text-xs text-muted-foreground">Backtest Summary Rows</span>
            <p className="text-lg font-mono text-foreground">{r.backtest_summary_rows}</p>
          </CardContent>
        </Card>
        <Card className="card-game">
          <CardContent className="p-4 text-center">
            <span className="text-xs text-muted-foreground">Backtest Detail Rows</span>
            <p className="text-lg font-mono text-foreground">{r.backtest_detail_rows}</p>
          </CardContent>
        </Card>
      </div>

      {/* Gold Reference Data */}
      <Card className="card-game">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-sans">Gold Reference Data</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-x-6 gap-y-3 text-xs">
            {GOLD_LABELS.map(({ key, label }) => (
              <div key={key}>
                <span className="text-muted-foreground">{label}</span>
                <p className="font-mono text-foreground">{(r[key] as number).toLocaleString()} rows</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}


type HistogramBucket = {
  bucketStart: number | string;
  bucketEnd: number | string;
  count: number;
};

function SearchHistoryPanel() {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [data, setData] = useState<SearchHistoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [league, setLeague] = useState('');
  const [sort, setSort] = useState('added_on');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [priceMin, setPriceMin] = useState<number | undefined>();
  const [priceMax, setPriceMax] = useState<number | undefined>();
  const [committedPriceMin, setCommittedPriceMin] = useState<number | undefined>();
  const [committedPriceMax, setCommittedPriceMax] = useState<number | undefined>();
  const [timeFrom, setTimeFrom] = useState<string | undefined>();
  const [timeTo, setTimeTo] = useState<string | undefined>();
  const [committedTimeFrom, setCommittedTimeFrom] = useState<string | undefined>();
  const [committedTimeTo, setCommittedTimeTo] = useState<string | undefined>();

  useEffect(() => {
    const normalizedQuery = query.trim();
    if (normalizedQuery.length < 2) {
      setSuggestions([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      getAnalyticsSearchSuggestions(normalizedQuery)
        .then(payload => {
          if (!cancelled) {
            setSuggestions(payload.suggestions);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setSuggestions([]);
          }
        });
    }, 150);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    const normalizedQuery = query.trim();
    if (normalizedQuery.length < 2) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const timer = window.setTimeout(() => {
      getAnalyticsSearchHistory({
        query: normalizedQuery,
        league,
        sort,
        order,
        priceMin: committedPriceMin,
        priceMax: committedPriceMax,
        timeFrom: committedTimeFrom,
        timeTo: committedTimeTo,
        limit: 100,
      })
        .then(payload => {
          if (!cancelled) {
            setData(payload);
            setError(null);
          }
        })
        .catch(err => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : 'Failed to load search history');
          }
        })
        .finally(() => { if (!cancelled) setLoading(false); });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, league, sort, order, committedPriceMin, committedPriceMax, committedTimeFrom, committedTimeTo]);

  const priceFloor = data?.filters.price.min ?? 0;
  const priceCeiling = Math.max(data?.filters.price.max ?? 0, priceFloor);
  const priceStep = calculateStep(priceFloor, priceCeiling);

  const timeRangeMin = toUnixMs(data?.filters.datetime.min);
  const timeRangeMax = toUnixMs(data?.filters.datetime.max);
  const hasTimeRange = timeRangeMin !== null && timeRangeMax !== null && timeRangeMax >= timeRangeMin;
  const timeStep = hasTimeRange && timeRangeMin !== null && timeRangeMax !== null
    ? calculateStep(timeRangeMin, timeRangeMax)
    : 1;

  const applyHistorySort = (nextSort: string) => {
    if (sort === nextSort) {
      setOrder(current => current === 'asc' ? 'desc' : 'asc');
      return;
    }
    setSort(nextSort);
    setOrder(nextSort === 'added_on' ? 'desc' : 'asc');
  };

  const resetFilters = () => {
    setLeague('');
    setPriceMin(undefined);
    setPriceMax(undefined);
    setCommittedPriceMin(undefined);
    setCommittedPriceMax(undefined);
    setTimeFrom(undefined);
    setTimeTo(undefined);
    setCommittedTimeFrom(undefined);
    setCommittedTimeTo(undefined);
    setSort('added_on');
    setOrder('desc');
  };

  return (
    <div className="space-y-4">
      <Card className="card-game">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-sans">Global Item Search</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,2fr)_minmax(180px,1fr)_auto] items-end">
            <label className="text-xs text-muted-foreground space-y-1">
              <span>Item name</span>
              <input
                data-testid="search-history-input"
                list="search-history-item-suggestions"
                value={query}
                onChange={event => setQuery(event.target.value)}
                placeholder="Start typing an item name"
                title="Suggestions come from ClickHouse and help you choose the exact item name."
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
              <datalist id="search-history-item-suggestions">
                {suggestions.map(suggestion => (
                  <option key={`${suggestion.itemKind}-${suggestion.itemName}`} value={suggestion.itemName}>
                    {`${suggestion.itemKind} · ${suggestion.matchCount}`}
                  </option>
                ))}
              </datalist>
            </label>

            <label className="text-xs text-muted-foreground space-y-1">
              <span>League</span>
              <select
                data-testid="search-history-league"
                value={league}
                onChange={event => setLeague(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="">All leagues</option>
                {(data?.filters.leagueOptions ?? []).map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
              </select>
            </label>

            <Button type="button" variant="outline" className="w-full lg:w-auto" onClick={resetFilters}>
              Reset filters
            </Button>
          </div>

          {suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {suggestions.map(suggestion => (
                <button
                  key={`${suggestion.itemKind}-${suggestion.itemName}`}
                  type="button"
                  title={`${suggestion.itemKind} · ${suggestion.matchCount} matches`}
                  className="rounded-full border border-border px-3 py-1 text-xs text-foreground hover:bg-secondary"
                  onClick={() => setQuery(suggestion.itemName)}
                >
                  {suggestion.itemName}
                </button>
              ))}
            </div>
          )}

          <p className="text-xs text-muted-foreground">
            Every filter change is sent back to the backend as SQL parameters so ClickHouse does the heavy work and the frontend only renders the returned rows and histograms.
          </p>
        </CardContent>
      </Card>

      {error && <RenderState kind="degraded" message={error} />}
      {loading && <RenderState kind="loading" message="Querying ClickHouse…" />}
      {!error && !loading && !data && (
        <RenderState kind="empty" message="Type at least two characters to search the historical listings index." />
      )}

      {data && (
        <>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card className="card-game">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-sans">Listed Price Distribution</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <MiniHistogram
                  dataTestId="search-history-price-histogram"
                  title="Listed price"
                  buckets={data.histograms.price}
                  formatLabel={value => typeof value === 'number' ? `${value.toFixed(1)}c` : String(value)}
                />
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>{(priceMin ?? priceFloor).toFixed(1)}c</span>
                    <span>{(priceMax ?? priceCeiling).toFixed(1)}c</span>
                  </div>
                  <Slider
                    min={priceFloor}
                    max={priceCeiling}
                    step={priceStep}
                    value={[priceMin ?? priceFloor, priceMax ?? priceCeiling]}
                    onValueChange={([lo, hi]) => { setPriceMin(lo); setPriceMax(hi); }}
                    onValueCommit={([lo, hi]) => { setCommittedPriceMin(lo); setCommittedPriceMax(hi); }}
                    disabled={priceFloor === priceCeiling}
                  />
                </div>
              </CardContent>
            </Card>

            <Card className="card-game">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-sans">Added On Distribution</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <MiniHistogram
                  dataTestId="search-history-time-histogram"
                  title="Added on"
                  buckets={data.histograms.datetime}
                  formatLabel={value => formatShortDate(String(value))}
                />
                {hasTimeRange ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-muted-foreground gap-3">
                      <span>{formatShortDate(new Date(toUnixMs(timeFrom) ?? timeRangeMin!).toISOString())}</span>
                      <span>{formatShortDate(new Date(toUnixMs(timeTo) ?? timeRangeMax!).toISOString())}</span>
                    </div>
                    <Slider
                      min={timeRangeMin!}
                      max={timeRangeMax!}
                      step={timeStep}
                      value={[toUnixMs(timeFrom) ?? timeRangeMin!, toUnixMs(timeTo) ?? timeRangeMax!]}
                      onValueChange={([lo, hi]) => {
                        setTimeFrom(new Date(lo).toISOString());
                        setTimeTo(new Date(hi).toISOString());
                      }}
                      onValueCommit={([lo, hi]) => {
                        setCommittedTimeFrom(new Date(lo).toISOString());
                        setCommittedTimeTo(new Date(hi).toISOString());
                      }}
                      disabled={timeRangeMin === timeRangeMax}
                    />
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">No datetime buckets available for the current search.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="card-game" data-testid="search-history-results">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="text-sm font-sans">Historical Results</CardTitle>
                <span className="text-xs text-muted-foreground">{data.rows.length} rows · {order.toUpperCase()}</span>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">
                      <button type="button" onClick={() => applyHistorySort('item_name')}>Item Name{sort === 'item_name' ? ` ${sortArrow(order)}` : ''}</button>
                    </TableHead>
                    <TableHead className="text-xs">
                      <button type="button" onClick={() => applyHistorySort('league')}>League{sort === 'league' ? ` ${sortArrow(order)}` : ''}</button>
                    </TableHead>
                    <TableHead className="text-xs">
                      <button type="button" onClick={() => applyHistorySort('listed_price')}>Listed Price{sort === 'listed_price' ? ` ${sortArrow(order)}` : ''}</button>
                    </TableHead>
                    <TableHead className="text-xs">
                      <button type="button" onClick={() => applyHistorySort('added_on')}>Added On{sort === 'added_on' ? ` ${sortArrow(order)}` : ''}</button>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.rows.map((row, index) => (
                    <TableRow key={`${row.itemName}-${row.addedOn}-${index}`}>
                      <TableCell className="text-xs font-medium text-foreground">{row.itemName}</TableCell>
                      <TableCell className="text-xs">{row.league}</TableCell>
                      <TableCell className="text-xs font-mono">{row.listedPrice} {row.currency}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">{formatDisplayDate(row.addedOn)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function PricingOutliersPanel() {
  const [query, setQuery] = useState('');
  const [league, setLeague] = useState('');
  const [sort, setSort] = useState('items_total');
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [minTotal, setMinTotal] = useState(25);
  const [data, setData] = useState<PricingOutliersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      getAnalyticsPricingOutliers({
        query: query.trim() || undefined,
        league: league.trim() || undefined,
        sort,
        order,
        minTotal,
        limit: 100,
      })
        .then(payload => {
          if (!cancelled) {
            setData(payload);
            setError(null);
          }
        })
        .catch(err => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : 'Failed to load pricing outliers');
          }
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query, league, sort, order, minTotal]);

  return (
    <div className="space-y-4">
      <Card className="card-game">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-sans">Too Cheap Analysis</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,2fr)_180px_180px_180px] items-end">
            <label className="text-xs text-muted-foreground space-y-1">
              <span>Item filter</span>
              <input
                value={query}
                onChange={event => setQuery(event.target.value)}
                placeholder="Optional item name filter"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </label>
            <label className="text-xs text-muted-foreground space-y-1">
              <span>League</span>
              <input
                value={league}
                onChange={event => setLeague(event.target.value)}
                placeholder="Default league"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </label>
            <label className="text-xs text-muted-foreground space-y-1">
              <span>Sort</span>
              <select
                value={sort}
                onChange={event => setSort(event.target.value)}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="items_total">Items total</option>
                <option value="items_per_week">Items / week</option>
                <option value="p10">10 percentile</option>
                <option value="median">Median</option>
                <option value="p90">90 percentile</option>
                <option value="item_name">Item name</option>
              </select>
            </label>
            <label className="text-xs text-muted-foreground space-y-1">
              <span>Minimum sample size</span>
              <input
                type="number"
                min={1}
                value={minTotal}
                onChange={event => setMinTotal(Math.max(1, Number(event.target.value) || 1))}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              />
            </label>
          </div>

          <p className="text-xs text-muted-foreground">
            Rows below the 10 percentile are treated as too cheap. The backend calculates per-item and per-affix percentiles so the frontend only renders the returned summary tables and weekly counts.
          </p>
        </CardContent>
      </Card>

      {error && <RenderState kind="degraded" message={error} />}
      {!error && !data && <RenderState kind="loading" message="Loading too-cheap pricing analysis…" />}

      {data && (
        <>
          <Card className="card-game">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-sans">Too Cheap per Week</CardTitle>
            </CardHeader>
            <CardContent>
              <MiniHistogram
                dataTestId="pricing-outliers-weekly-chart"
                title="Items per week below the 10 percentile"
                buckets={data.weekly.map(entry => ({
                  bucketStart: entry.weekStart,
                  bucketEnd: entry.weekStart,
                  count: entry.tooCheapCount,
                }))}
                formatLabel={value => formatShortDate(String(value))}
              />
            </CardContent>
          </Card>

          <Card className="card-game" data-testid="pricing-outliers-results">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="text-sm font-sans">Outlier Results</CardTitle>
                <span className="text-xs text-muted-foreground">{data.rows.length} rows · {order.toUpperCase()}</span>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs"><button type="button" onClick={() => { if (sort === 'item_name') setOrder(o => o === 'asc' ? 'desc' : 'asc'); else { setSort('item_name'); setOrder('asc'); } }}>Item Name{sort === 'item_name' ? ` ${sortArrow(order)}` : ''}</button></TableHead>
                    <TableHead className="text-xs">Affix Analyzed</TableHead>
                    <TableHead className="text-xs"><button type="button" onClick={() => { if (sort === 'p10') setOrder(o => o === 'asc' ? 'desc' : 'asc'); else { setSort('p10'); setOrder('asc'); } }}>p10{sort === 'p10' ? ` ${sortArrow(order)}` : ''}</button></TableHead>
                    <TableHead className="text-xs"><button type="button" onClick={() => { if (sort === 'median') setOrder(o => o === 'asc' ? 'desc' : 'asc'); else { setSort('median'); setOrder('asc'); } }}>Median{sort === 'median' ? ` ${sortArrow(order)}` : ''}</button></TableHead>
                    <TableHead className="text-xs"><button type="button" onClick={() => { if (sort === 'p90') setOrder(o => o === 'asc' ? 'desc' : 'asc'); else { setSort('p90'); setOrder('asc'); } }}>p90{sort === 'p90' ? ` ${sortArrow(order)}` : ''}</button></TableHead>
                    <TableHead className="text-xs"><button type="button" onClick={() => { if (sort === 'items_per_week') setOrder(o => o === 'asc' ? 'desc' : 'asc'); else { setSort('items_per_week'); setOrder('desc'); } }}>Items/wk{sort === 'items_per_week' ? ` ${sortArrow(order)}` : ''}</button></TableHead>
                    <TableHead className="text-xs"><button type="button" onClick={() => { if (sort === 'items_total') setOrder(o => o === 'asc' ? 'desc' : 'asc'); else { setSort('items_total'); setOrder('desc'); } }}>Items total{sort === 'items_total' ? ` ${sortArrow(order)}` : ''}</button></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.rows.map((row, index) => (
                    <TableRow key={`${row.itemName}-${row.affixAnalyzed ?? 'base'}-${index}`}>
                      <TableCell className="text-xs font-medium text-foreground">{row.itemName}</TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        <div className="flex items-center gap-2">
                          <span>{row.affixAnalyzed ?? 'All item rolls'}</span>
                          <Badge variant="outline" className="text-[10px] uppercase tracking-wide">{row.analysisLevel}</Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs font-mono">{row.p10.toFixed(2)}</TableCell>
                      <TableCell className="text-xs font-mono">{row.median.toFixed(2)}</TableCell>
                      <TableCell className="text-xs font-mono">{row.p90.toFixed(2)}</TableCell>
                      <TableCell className="text-xs font-mono">{row.itemsPerWeek.toFixed(2)}</TableCell>
                      <TableCell className="text-xs font-mono">{row.itemsTotal}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function MiniHistogram({
  title,
  buckets,
  formatLabel,
  dataTestId,
}: {
  title: string;
  buckets: HistogramBucket[];
  formatLabel: (value: number | string) => string;
  dataTestId: string;
}) {
  if (buckets.length === 0) {
    return <p className="text-xs text-muted-foreground">No histogram data available.</p>;
  }
  const maxCount = buckets.reduce((current, bucket) => Math.max(current, bucket.count), 1);
  return (
    <div className="space-y-2" data-testid={dataTestId}>
      <p className="text-xs text-muted-foreground">{title}</p>
      <div className="flex items-end gap-1 h-32">
        {buckets.map((bucket, index) => (
          <div key={`${String(bucket.bucketStart)}-${index}`} className="flex-1 h-full flex items-end">
            <div
              title={`${formatLabel(bucket.bucketStart)} → ${formatLabel(bucket.bucketEnd)} · ${bucket.count}`}
              className="w-full rounded-t bg-primary/60 border border-primary/20"
              style={{ height: `${Math.max(12, (bucket.count / maxCount) * 100)}%` }}
            />
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between gap-2 text-[10px] text-muted-foreground">
        <span>{formatLabel(buckets[0].bucketStart)}</span>
        <span>{formatLabel(buckets[buckets.length - 1].bucketEnd)}</span>
      </div>
    </div>
  );
}

function calculateStep(minValue: number, maxValue: number): number {
  const distance = Math.max(maxValue - minValue, 1);
  return Math.max(Math.floor(distance / 100), 1);
}

function clampNumber(value: number, minValue: number, maxValue: number): number {
  if (maxValue < minValue) {
    return minValue;
  }
  return Math.min(Math.max(value, minValue), maxValue);
}

function toUnixMs(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? null : parsed;
}

function formatDisplayDate(value: string | null | undefined): string {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function formatShortDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString();
}

function sortArrow(order: 'asc' | 'desc'): string {
  return order === 'asc' ? '↑' : '↓';
}
