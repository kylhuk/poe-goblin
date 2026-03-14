import { forwardRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ConfidenceBadge, CurrencyValue } from '@/components/shared/StatusIndicators';
import { api } from '@/services/api';
import type { PriceCheckResponse } from '@/types/api';
import { Search } from 'lucide-react';
import { RenderState } from '@/components/shared/RenderState';

const PriceCheckTab = forwardRef<HTMLDivElement, Record<string, never>>(function PriceCheckTab(_props, ref) {
  const [text, setText] = useState('');
  const [result, setResult] = useState<PriceCheckResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const check = async () => {
    if (!text.trim()) {
      setError('Please paste item text first');
      return;
    }
    setLoading(true);
    try {
      const r = await api.priceCheck({ itemText: text });
      setResult(r);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Price check failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6" data-testid="panel-pricecheck-root">
      <div className="space-y-3">
        <h2 className="text-lg font-semibold font-sans text-foreground">Price Check</h2>
        <p className="text-xs text-muted-foreground">Paste item text from PoE (Ctrl+C on item) and submit for price prediction.</p>
        <Textarea
          data-testid="pricecheck-input"
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={`Rarity: Rare\nGrim Bane\nHubris Circlet\n--------\nQuality: +20%\n+2 to Level of Socketed Minion Gems\n+93 to maximum Life\n...`}
          className="min-h-[160px] font-mono text-xs"
        />
        <Button data-testid="pricecheck-submit" onClick={check} disabled={loading} className="gap-2 w-full sm:w-auto">
          <Search className="h-4 w-4" />
          {loading ? 'Checking...' : 'Price Check'}
        </Button>
        {error && <RenderState kind="invalid_input" message={error} />}
      </div>

      {result && (
        <Card className="glow-gold">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-sans">Prediction</CardTitle>
              <ConfidenceBadge value={result.confidence} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-center py-4">
              <p className="text-3xl font-mono text-gold-bright font-semibold">
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

            <div>
              <p className="text-xs text-muted-foreground mb-2">Comparable Items</p>
              <div className="space-y-2">
                {result.comparables.map((c, i) => (
                  <div key={i} className="flex items-center justify-between bg-secondary/50 rounded p-2 text-xs">
                    <span className="text-foreground">{c.name}</span>
                    <CurrencyValue value={c.price} currency={c.currency} />
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
