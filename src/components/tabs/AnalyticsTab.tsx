import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Freshness, ConfidenceBadge, CurrencyValue, GradeBadge } from '@/components/shared/StatusIndicators';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import type { FairValueItem, StaleListingOpp, GemState, HeistDrop, ShipmentRecommendation, GoldShadowData, SessionRecommendation, GearSwapResult } from '@/types/api';
import { LineChart, Line, ResponsiveContainer, YAxis } from 'recharts';
import { CheckCircle, XCircle, ArrowRight } from 'lucide-react';

export default function AnalyticsTab() {
  return (
    <Tabs defaultValue="fairvalue" className="space-y-4">
      <TabsList className="flex-wrap h-auto gap-1 bg-secondary/50 p-1">
        <TabsTrigger data-testid="analytics-tab-fairvalue" value="fairvalue" className="text-xs">Ingestion</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-stale" value="stale" className="text-xs">Scanner</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-gem" value="gem" className="text-xs">Alerts</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-heist" value="heist" className="text-xs">Backtests</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-shipment" value="shipment" className="text-xs">ML</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-gold" value="gold" className="text-xs">Reports</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-session" value="session" className="text-xs">Session</TabsTrigger>
        <TabsTrigger data-testid="analytics-tab-gear" value="gear" className="text-xs">Diagnostics</TabsTrigger>
      </TabsList>

      <TabsContent data-testid="analytics-panel-fairvalue" value="fairvalue"><FairValuePanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-stale" value="stale"><StaleListingPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-gem" value="gem"><GemValuePanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-heist" value="heist"><HeistRouterPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-shipment" value="shipment"><ShipmentPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-gold" value="gold"><GoldShadowPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-session" value="session"><SessionPanel /></TabsContent>
      <TabsContent data-testid="analytics-panel-gear" value="gear"><GearSwapPanel /></TabsContent>
    </Tabs>
  );
}

function FairValuePanel() {
  const [items, setItems] = useState<FairValueItem[]>([]);
  useEffect(() => { api.getFairValueItems().then(setItems).catch(() => setItems([])); }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {items.map(item => (
        <Card key={item.id}>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-sans">{item.itemName}</CardTitle>
              <ConfidenceBadge value={item.confidence} />
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="h-12">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={item.sparkline}>
                  <YAxis domain={['auto', 'auto']} hide />
                  <Line type="monotone" dataKey="value" stroke="hsl(40 60% 50%)" strokeWidth={1.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div><span className="text-muted-foreground">Fair Value</span><p><CurrencyValue value={item.fairValue} /></p></div>
              <div><span className="text-muted-foreground">Stash Floor</span><p><CurrencyValue value={item.publicStashFloor} /></p></div>
              <div><span className="text-muted-foreground">Exchange Mid</span><p><CurrencyValue value={item.exchangeImpliedMid} /></p></div>
            </div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Spread: <span className="text-foreground font-mono">{item.spread}%</span></span>
              <span className={`capitalize px-2 py-0.5 rounded text-xs ${item.liquidity === 'high' ? 'bg-success/20 text-success' : item.liquidity === 'medium' ? 'bg-warning/20 text-warning' : 'bg-destructive/20 text-destructive'}`}>{item.liquidity} liq</span>
              <Freshness iso={item.updatedAt} />
            </div>
            {item.publicStashFloor < item.fairValue * 0.95 && (
              <div className="text-xs bg-success/10 border border-success/20 rounded p-2 text-success">
                ⚡ Floor {((1 - item.publicStashFloor / item.fairValue) * 100).toFixed(1)}% below fair — buy & relist if turnover is fast
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function StaleListingPanel() {
  const [items, setItems] = useState<StaleListingOpp[]>([]);
  useEffect(() => { api.getStaleListings().then(setItems).catch(() => setItems([])); }, []);

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">Scanner and recommendation rollup by backend status group.</p>
      {items.map(item => (
        <Card key={item.id} className={item.grade === 'green' ? 'glow-success border-success/20' : item.grade === 'yellow' ? 'border-warning/20' : 'opacity-50'}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <GradeBadge grade={item.grade} />
                <span className="text-sm font-medium text-foreground">{item.itemName}</span>
              </div>
              <span className="text-xs bg-secondary px-2 py-0.5 rounded font-mono">{item.route}</span>
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-xs">
              <div><span className="text-muted-foreground">Ask</span><p><CurrencyValue value={item.askPrice} /></p></div>
              <div><span className="text-muted-foreground">Fair</span><p><CurrencyValue value={item.fairValue} /></p></div>
              <div><span className="text-muted-foreground">Discount</span><p className="font-mono text-success">{item.discountPct}%</p></div>
              <div><span className="text-muted-foreground">Dormancy</span><p className="font-mono">{item.sellerDormancyScore}</p></div>
              <div><span className="text-muted-foreground">Net Margin</span><p><CurrencyValue value={item.expectedNetMargin} /></p></div>
              <div><span className="text-muted-foreground">Sale Time</span><p className="font-mono">{item.expectedSaleTime}</p></div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function GemValuePanel() {
  const [gems, setGems] = useState<GemState[]>([]);
  useEffect(() => { api.getGemStates().then(setGems).catch(() => setGems([])); }, []);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {gems.map(g => (
        <Card key={g.id}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-sans">{g.gemName}</CardTitle>
            <p className="text-xs text-muted-foreground font-mono">
              L{g.level}/Q{g.quality} {g.corrupted ? '⚠ Corrupted' : ''} {g.vaalState ?? ''}
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div><span className="text-muted-foreground">Ask</span><p><CurrencyValue value={g.currentAsk} /></p></div>
              <div><span className="text-muted-foreground">Model Fair</span><p><CurrencyValue value={g.modelFairValue} /></p></div>
              <div><span className="text-muted-foreground">Anomaly</span><p><ConfidenceBadge value={g.anomalyScore} /></p></div>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">Comparables ({g.comparables.length})</p>
              <div className="flex flex-wrap gap-1">
                {g.comparables.map((c, i) => (
                  <span key={i} className="text-xs bg-secondary px-2 py-0.5 rounded font-mono">{c.state}: {c.price}div</span>
                ))}
              </div>
              {g.comparables.length < 3 && <p className="text-xs text-warning mt-1">⚠ Low comparable density — manual review only</p>}
            </div>
            <Freshness iso={g.updatedAt} />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function HeistRouterPanel() {
  const [drops, setDrops] = useState<HeistDrop[]>([]);
  useEffect(() => { api.getHeistDrops().then(setDrops).catch(() => setDrops([])); }, []);

  const bins: Record<string, string> = {
    'sell fast': 'bg-success/20 text-success border-success/30',
    'premium bin': 'bg-divine/20 text-divine border-divine/30',
    'run': 'bg-warning/20 text-warning border-warning/30',
    'ignore': 'bg-secondary text-muted-foreground border-border',
  };

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">Backtest status summary sourced from research history.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {drops.map(d => (
          <div key={d.id} className={`rounded border p-3 ${bins[d.bin]}`}>
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-sm">{d.itemName}</span>
              <span className="text-xs uppercase font-semibold">{d.bin}</span>
            </div>
            <p className="text-xs opacity-80">{d.itemClass} · {d.estimatedValueBand}</p>
            <p className="text-xs opacity-70 mt-1">{d.reason}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function ShipmentPanel() {
  const [s, setS] = useState<ShipmentRecommendation | null>(null);
  const [automation, setAutomation] = useState<Record<string, unknown> | null>(null);
  useEffect(() => { api.getShipmentRecommendation().then(setS).catch(() => setS(null)); }, []);
  useEffect(() => { api.getMlAutomationStatus().then(setAutomation).catch(() => setAutomation(null)); }, []);
  if (!s) return null;

  return (
    <Card className="glow-gold">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-sans">Recommended Shipment</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
          <div><span className="text-muted-foreground">Port</span><p className="text-foreground font-medium">{s.chosenPort}</p></div>
          <div><span className="text-muted-foreground">EV</span><p><CurrencyValue value={s.expectedValue} /></p></div>
          <div><span className="text-muted-foreground">EV/hr</span><p><CurrencyValue value={s.expectedValuePerHour} /></p></div>
          <div><span className="text-muted-foreground">Risk Loss</span><p className="font-mono text-destructive">{s.expectedRiskLoss} div</p></div>
          <div><span className="text-muted-foreground">Dust</span><p className="font-mono">{s.dustToAdd}</p></div>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1">Resource Mix</p>
          <div className="flex flex-wrap gap-1">
            {Object.entries(s.resourceMix).map(([k, v]) => (
              <span key={k} className="text-xs bg-secondary px-2 py-0.5 rounded">{k}: {v}</span>
            ))}
          </div>
        </div>
        <div className="text-xs bg-primary/10 border border-primary/20 rounded p-2 text-foreground">
          💡 {s.whyThisWon}
        </div>
        {automation && (
          <div className="text-xs bg-secondary/40 border border-border rounded p-2" data-testid="ml-automation-card">
            <p>Status: {String(automation.status || 'unknown')}</p>
            <p>Promotion: {String(automation.promotionVerdict || 'n/a')}</p>
          </div>
        )}
        <Freshness iso={s.updatedAt} />
      </CardContent>
    </Card>
  );
}

function GoldShadowPanel() {
  const [g, setG] = useState<GoldShadowData | null>(null);
  useEffect(() => { api.getGoldShadowPrice().then(setG).catch(() => setG(null)); }, []);
  if (!g) return null;

  return (
    <Card className="border-primary/30">
      <CardContent className="p-4 flex flex-col sm:flex-row items-start sm:items-center gap-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">🪙</span>
          <div>
            <p className="text-xs text-muted-foreground">Chaos per Gold</p>
            <p className="text-xl font-mono text-gold-bright">{g.chaosPerGold}</p>
          </div>
        </div>
        <div>
          <p className="text-xs text-muted-foreground">Exchange Fee</p>
          <p className="text-lg font-mono text-warning">{g.feeInChaos}c</p>
        </div>
        <div className="flex-1 text-xs bg-info/10 border border-info/20 rounded p-2 text-info">
          💡 {g.denominationHint}
        </div>
        <Freshness iso={g.updatedAt} />
      </CardContent>
    </Card>
  );
}

function SessionPanel() {
  const [s, setS] = useState<SessionRecommendation | null>(null);
  useEffect(() => { api.getSessionRecommendation().then(setS).catch(() => setS(null)); }, []);
  if (!s) return null;

  return (
    <Card className="glow-gold">
      <CardContent className="p-6 text-center space-y-3">
        <p className="text-xs text-muted-foreground uppercase tracking-wider">Recommended Activity</p>
        <p className="text-2xl font-display text-primary capitalize">{s.recommended}</p>
        <div className="flex items-center justify-center gap-2">
          <ArrowRight className="h-4 w-4 text-primary" />
          <p className="text-sm text-foreground">{s.triggerReason}</p>
        </div>
        <Freshness iso={s.updatedAt} />
      </CardContent>
    </Card>
  );
}

function GearSwapPanel() {
  const [candidateText, setCandidateText] = useState('');
  const [result, setResult] = useState<GearSwapResult | null>(null);
  const [loading, setLoading] = useState(false);

  const simulate = async () => {
    setLoading(true);
    const r = await api.simulateGearSwap(candidateText);
    setResult(r);
    setLoading(false);
  };

  const stats: (keyof GearSwapResult['current'])[] = ['fireRes', 'coldRes', 'lightningRes', 'chaosRes', 'spellSuppression', 'life', 'str', 'dex', 'int'];
  const labels: Record<string, string> = { fireRes: '🔥 Fire', coldRes: '❄️ Cold', lightningRes: '⚡ Light', chaosRes: '☠️ Chaos', spellSuppression: '🛡 Suppress', life: '❤️ Life', str: 'STR', dex: 'DEX', int: 'INT' };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Textarea
          placeholder="Paste candidate item text here..."
          value={candidateText}
          onChange={e => setCandidateText(e.target.value)}
          className="min-h-[80px] font-mono text-xs"
        />
        <Button onClick={simulate} disabled={loading} className="self-end">
          {loading ? 'Simulating...' : 'Simulate'}
        </Button>
      </div>

      {result && (
        <Card>
          <CardContent className="p-4 space-y-3">
            <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 text-xs">
              <div className="font-medium text-muted-foreground">Stat</div>
              <div className="font-medium text-muted-foreground">Current</div>
              <div className="font-medium text-muted-foreground">After</div>
              <div className="font-medium text-muted-foreground hidden sm:block">Δ</div>
              <div className="font-medium text-muted-foreground hidden sm:block">Status</div>
              {stats.map(s => {
                const cur = result.current[s] as number;
                const sim = result.simulated[s] as number;
                const diff = sim - cur;
                return (
                  <div key={s} className="contents">
                    <span>{labels[s] || s}</span>
                    <span className="font-mono">{cur}</span>
                    <span className="font-mono">{sim}</span>
                    <span className={`font-mono hidden sm:block ${diff > 0 ? 'text-success' : diff < 0 ? 'text-destructive' : ''}`}>{diff > 0 ? '+' : ''}{diff}</span>
                    <span className="hidden sm:block">{s.includes('Res') && sim < 75 ? '🔴' : '🟢'}</span>
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className={result.simulated.evasionMasteryActive ? 'text-success' : 'text-destructive'}>
                {result.simulated.evasionMasteryActive ? '🟢' : '🔴'} Evasion Mastery
              </span>
              <span className={result.simulated.auraFit ? 'text-success' : 'text-destructive'}>
                {result.simulated.auraFit ? '🟢' : '🔴'} Aura Fit
              </span>
            </div>
            {result.failStates.length > 0 && (
              <div className="space-y-1">
                {result.failStates.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-destructive bg-destructive/10 rounded p-2 border border-destructive/20">
                    <XCircle className="h-3.5 w-3.5 shrink-0" /> {f}
                  </div>
                ))}
              </div>
            )}
            {result.passStates.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {result.passStates.map((p, i) => (
                  <span key={i} className="flex items-center gap-1 text-xs text-success bg-success/10 rounded px-2 py-0.5">
                    <CheckCircle className="h-3 w-3" /> {p}
                  </span>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
