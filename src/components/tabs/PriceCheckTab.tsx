import { forwardRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ConfidenceBadge } from '@/components/shared/StatusIndicators';
import { api } from '@/services/api';
import type { PriceCheckResponse } from '@/types/api';
import { Brain } from 'lucide-react';
import { RenderState } from '@/components/shared/RenderState';
import { useMouseGlow } from '@/hooks/useMouseGlow';

const PriceCheckTab = forwardRef<HTMLDivElement, Record<string, never>>(function PriceCheckTab(_props, ref) {
  const [text, setText] = useState('');
  const [result, setResult] = useState<PriceCheckResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mouseGlow = useMouseGlow();

  const check = async () => {
    if (!text.trim()) {
      setError('Please paste item text first');
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const nextResult = await api.priceCheck({ itemText: text });
      setResult(nextResult);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Price prediction failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div ref={ref} className="max-w-4xl mx-auto space-y-6" data-testid="panel-pricecheck-root">
      <div className="space-y-3">
        <h2 className="text-lg font-semibold font-sans text-foreground">ML Price Check</h2>
        <p className="text-xs text-muted-foreground">
          Paste PoE clipboard text. The backend runs the trained price model and returns recent market comparables from the synchronized dataset.
        </p>

        <Textarea
          data-testid="pricecheck-input"
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={`Rarity: Rare
Grim Bane
Hubris Circlet
--------
Quality: +20%
+2 to Level of Socketed Minion Gems
+93 to maximum Life
...`}
          className="min-h-[160px] font-mono text-xs focus:shadow-[0_0_12px_-3px_hsl(38,55%,42%,0.3)] transition-shadow"
        />
        <Button data-testid="pricecheck-submit" onClick={check} disabled={loading} className="gap-2 w-full sm:w-auto btn-game">
          <Brain className="h-4 w-4" />
          {loading ? 'Checking...' : 'Check Price'}
        </Button>
        {error && <RenderState kind="invalid_input" message={error} />}
      </div>

      {result && (
        <Card className="glow-gold card-game animate-scale-fade-in" onMouseMove={mouseGlow}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="text-sm font-sans">ML Prediction</CardTitle>
              <ConfidenceBadge value={result.confidence} />
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="text-center py-4">
              <p className="text-3xl font-mono font-semibold gold-shimmer-text">
                {result.predictedValue} <span className="text-lg text-muted-foreground">{result.currency}</span>
              </p>
              {result.interval && (
                <p className="text-xs text-muted-foreground mt-1 font-mono">
                  p10 {result.interval.p10 ?? 'n/a'} - p90 {result.interval.p90 ?? 'n/a'}
                </p>
              )}
              {typeof result.saleProbabilityPercent === 'number' && (
                <p className="text-xs text-muted-foreground mt-1">
                  Sale Probability: {result.saleProbabilityPercent}%
                </p>
              )}
              {result.fallbackReason && (
                <p className="text-xs text-warning mt-1">Fallback: {result.fallbackReason}</p>
              )}
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Recent Comparables</h3>
                <span className="text-xs text-muted-foreground">{result.comparables.length} rows</span>
              </div>

              {result.comparables.length > 0 ? (
                <div className="rounded-md border border-border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Item Name</TableHead>
                        <TableHead className="text-xs">Price</TableHead>
                        <TableHead className="text-xs">Currency</TableHead>
                        <TableHead className="text-xs">League</TableHead>
                        <TableHead className="text-xs">Added On</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {result.comparables.map((row, index) => (
                        <TableRow key={`${row.name}-${row.price}-${index}`}>
                          <TableCell className="text-xs font-medium text-foreground">{row.name}</TableCell>
                          <TableCell className="text-xs font-mono">{row.price}</TableCell>
                          <TableCell className="text-xs font-mono">{row.currency}</TableCell>
                          <TableCell className="text-xs">{row.league ?? '—'}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">{formatComparableDate(row.addedOn)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  No recent comparables were found for this parsed base type in the selected league.
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
});

function formatComparableDate(value: string | null | undefined): string {
  if (!value) {
    return '—';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

PriceCheckTab.displayName = 'PriceCheckTab';
export default PriceCheckTab;
