import { forwardRef, useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { RenderState } from '@/components/shared/RenderState';
import { api } from '@/services/api';
import type { ScannerFilterOptions, ScannerRecommendation } from '@/types/api';
import { useMouseGlow } from '@/hooks/useMouseGlow';
import { Filter, X } from 'lucide-react';

const SORT_OPTIONS = [
  { value: '', label: 'Default' },
  { value: 'profit_desc', label: 'Profit ↓' },
  { value: 'profit_asc', label: 'Profit ↑' },
  { value: 'confidence_desc', label: 'Confidence ↓' },
  { value: 'roi_desc', label: 'ROI ↓' },
];

const OpportunitiesTab = forwardRef<HTMLDivElement, Record<string, never>>(function OpportunitiesTab(_props, ref) {
  const [recommendations, setRecommendations] = useState<ScannerRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const mouseGlow = useMouseGlow();

  // Filter state
  const [sort, setSort] = useState('');
  const [minConfidence, setMinConfidence] = useState(0);
  const [strategyId, setStrategyId] = useState('');
  const [limit, setLimit] = useState(50);

  const fetchData = useCallback((filters: ScannerFilterOptions) => {
    setLoading(true);
    api.getScannerRecommendations(filters)
      .then(recs => {
        setRecommendations(recs);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load opportunities');
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchData({});
  }, [fetchData]);

  const applyFilters = () => {
    fetchData({
      sort: sort || undefined,
      limit,
      min_confidence: minConfidence > 0 ? minConfidence : undefined,
      strategy_id: strategyId.trim() || undefined,
    });
  };

  const clearFilters = () => {
    setSort('');
    setMinConfidence(0);
    setStrategyId('');
    setLimit(50);
    fetchData({});
  };

  if (loading) {
    return <div ref={ref} data-testid="panel-opportunities-root"><RenderState kind="loading" message="Scanning market..." /></div>;
  }

  if (error) {
    return <div ref={ref} data-testid="panel-opportunities-root"><RenderState kind="degraded" message={error} /></div>;
  }

  return (
    <div ref={ref} className="space-y-6" data-testid="panel-opportunities-root">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold font-sans text-foreground">Market Opportunities</h2>
          <p className="text-xs text-muted-foreground">Scanner-backed recommendations based on current market data.</p>
        </div>
        <Button variant="ghost" size="sm" className="gap-1.5 text-xs" onClick={() => setShowFilters(!showFilters)}>
          <Filter className="h-3.5 w-3.5" />
          Filters
        </Button>
      </div>

      {/* Filter controls */}
      {showFilters && (
        <Card className="card-game animate-scale-fade-in">
          <CardContent className="p-4 space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs">Sort</Label>
                <Select value={sort} onValueChange={setSort}>
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue placeholder="Default" />
                  </SelectTrigger>
                  <SelectContent>
                    {SORT_OPTIONS.map(o => (
                      <SelectItem key={o.value} value={o.value || '__default'} className="text-xs">{o.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Strategy ID</Label>
                <Input
                  value={strategyId}
                  onChange={e => setStrategyId(e.target.value)}
                  placeholder="e.g. stale_listing"
                  className="h-8 text-xs font-mono"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Min Confidence: {minConfidence}%</Label>
                <Slider
                  value={[minConfidence]}
                  onValueChange={([v]) => setMinConfidence(v)}
                  min={0}
                  max={100}
                  step={5}
                  className="mt-2"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Limit</Label>
                <Input
                  type="number"
                  value={limit}
                  onChange={e => setLimit(Number(e.target.value) || 50)}
                  min={1}
                  max={500}
                  className="h-8 text-xs font-mono"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" className="text-xs h-7 btn-game" onClick={applyFilters}>Apply</Button>
              <Button size="sm" variant="ghost" className="text-xs h-7 gap-1" onClick={clearFilters}>
                <X className="h-3 w-3" /> Clear
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {recommendations.length === 0 ? (
        <RenderState kind="empty" message="No opportunities found in the latest scan." />
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {recommendations.map(r => (
            <Card key={`${r.scannerRunId}-${r.itemOrMarketKey}`} className="card-game" onMouseMove={mouseGlow}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-sans">{r.itemOrMarketKey}</CardTitle>
                  <span className="text-xs font-mono text-muted-foreground">{r.strategyId}</span>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-foreground">{r.whyItFired}</p>
                
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-secondary/30 rounded p-3 border border-border">
                  <div>
                    <p className="text-xs text-muted-foreground">Buy Plan</p>
                    <p className="text-sm font-medium text-success">{r.buyPlan}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Transform</p>
                    <p className="text-sm font-medium text-foreground">{r.transformPlan}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Exit Plan</p>
                    <p className="text-sm font-medium text-foreground">{r.exitPlan}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Expected Profit</p>
                    <p className="text-sm font-medium text-warning">{r.expectedProfitChaos !== null ? `${r.expectedProfitChaos}c` : 'N/A'}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
});

OpportunitiesTab.displayName = 'OpportunitiesTab';
export default OpportunitiesTab;
