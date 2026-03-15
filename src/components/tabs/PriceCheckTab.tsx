import { forwardRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ConfidenceBadge, CurrencyValue } from '@/components/shared/StatusIndicators';
import { api } from '@/services/api';
import type { PriceCheckResponse, MlPredictOneResponse } from '@/types/api';
import { Search, Brain } from 'lucide-react';
import { RenderState } from '@/components/shared/RenderState';
import { useMouseGlow } from '@/hooks/useMouseGlow';

const PriceCheckTab = forwardRef<HTMLDivElement, Record<string, never>>(function PriceCheckTab(_props, ref) {
  const [text, setText] = useState('');
  const [result, setResult] = useState<PriceCheckResponse | null>(null);
  const [mlResult, setMlResult] = useState<MlPredictOneResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<'price-check' | 'ml-predict'>('price-check');
  const mouseGlow = useMouseGlow();

  const check = async () => {
    if (!text.trim()) {
      setError('Please paste item text first');
      return;
    }
    setLoading(true);
    setResult(null);
    setMlResult(null);
    try {
      if (mode === 'ml-predict') {
        const r = await api.mlPredictOne({ clipboard: text });
        setMlResult(r);
      } else {
        const r = await api.priceCheck({ itemText: text });
        setResult(r);
      }
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Price check failed');
    } finally {
      setLoading(false);
    }
  };

  const activeResult = mode === 'ml-predict' ? mlResult : result;

  return (
    <div ref={ref} className="max-w-2xl mx-auto space-y-6" data-testid="panel-pricecheck-root">
      <div className="space-y-3">
        <h2 className="text-lg font-semibold font-sans text-foreground">Price Check</h2>

        <Tabs value={mode} onValueChange={v => { setMode(v as 'price-check' | 'ml-predict'); setResult(null); setMlResult(null); setError(null); }}>
          <TabsList className="h-8 bg-secondary/50">
            <TabsTrigger value="price-check" className="text-xs gap-1.5 tab-game">
              <Search className="h-3 w-3" /> Ops Price Check
            </TabsTrigger>
            <TabsTrigger value="ml-predict" className="text-xs gap-1.5 tab-game">
              <Brain className="h-3 w-3" /> ML Predict
            </TabsTrigger>
          </TabsList>

          <TabsContent value="price-check">
            <p className="text-xs text-muted-foreground">Paste item text from PoE (Ctrl+C on item) and submit for price prediction.</p>
          </TabsContent>
          <TabsContent value="ml-predict">
            <p className="text-xs text-muted-foreground">Paste raw clipboard text. Uses the ML model's direct prediction endpoint for fastest results.</p>
          </TabsContent>
        </Tabs>

        <Textarea
          data-testid="pricecheck-input"
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder={`Rarity: Rare\nGrim Bane\nHubris Circlet\n--------\nQuality: +20%\n+2 to Level of Socketed Minion Gems\n+93 to maximum Life\n...`}
          className="min-h-[160px] font-mono text-xs focus:shadow-[0_0_12px_-3px_hsl(38,55%,42%,0.3)] transition-shadow"
        />
        <Button data-testid="pricecheck-submit" onClick={check} disabled={loading} className="gap-2 w-full sm:w-auto btn-game">
          {mode === 'ml-predict' ? <Brain className="h-4 w-4" /> : <Search className="h-4 w-4" />}
          {loading ? 'Checking...' : mode === 'ml-predict' ? 'ML Predict' : 'Price Check'}
        </Button>
        {error && <RenderState kind="invalid_input" message={error} />}
      </div>

      {activeResult && (
        <Card className="glow-gold card-game animate-scale-fade-in" onMouseMove={mouseGlow}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-sans">
                {mode === 'ml-predict' ? 'ML Prediction' : 'Prediction'}
              </CardTitle>
              <ConfidenceBadge value={activeResult.confidence} />
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="text-center py-4">
              <p className="text-3xl font-mono font-semibold gold-shimmer-text">
                {activeResult.predictedValue} <span className="text-lg text-muted-foreground">{activeResult.currency}</span>
              </p>
              {activeResult.interval && (
                <p className="text-xs text-muted-foreground mt-1 font-mono">
                  p10 {activeResult.interval.p10 ?? 'n/a'} - p90 {activeResult.interval.p90 ?? 'n/a'}
                </p>
              )}
              {typeof activeResult.saleProbabilityPercent === 'number' && (
                <p className="text-xs text-muted-foreground mt-1">
                  Sale Probability: {activeResult.saleProbabilityPercent}%
                </p>
              )}
              {activeResult.fallbackReason && (
                <p className="text-xs text-warning mt-1">Fallback: {activeResult.fallbackReason}</p>
              )}
            </div>

            {/* Comparables only for ops price-check */}
            {mode === 'price-check' && result && (
              <div>
                <p className="text-xs text-muted-foreground mb-2">Comparable Items</p>
                {result.comparables && result.comparables.length > 0 ? (
                  <div className="space-y-2">
                    {result.comparables.map((c) => (
                      <div key={`${c.name}-${c.price}-${c.currency}`} className="flex items-center justify-between bg-secondary/50 rounded p-2 text-xs transition-colors hover:bg-secondary">
                        <span className="text-foreground">{c.name}</span>
                        <CurrencyValue value={c.price} currency={c.currency} />
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground italic">No comparables available</p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
});

PriceCheckTab.displayName = 'PriceCheckTab';
export default PriceCheckTab;
