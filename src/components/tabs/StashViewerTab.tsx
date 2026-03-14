import { forwardRef, useEffect, useState } from 'react';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import type { StashTab, StashItem, PriceEvaluation } from '@/types/api';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import {
  Coins, Diamond, CircleDot, FlaskConical, Sword, ShieldHalf,
  FileText, Shirt, HardHat, Crown, ChevronDown, Copy, type LucideIcon,
} from 'lucide-react';
import { RenderState } from '@/components/shared/RenderState';

const ITEM_CLASS_ICONS: Record<string, LucideIcon> = {
  Currency: Coins, Gem: Diamond, Jewel: CircleDot, Flask: FlaskConical,
  Weapon: Sword, Shield: ShieldHalf, 'Body Armour': Shirt, Helmet: HardHat,
  Blueprint: FileText, Amulet: Crown, Belt: Crown,
};

const RARITY_COLOR: Record<string, string> = {
  normal: 'text-muted-foreground', magic: 'text-info', rare: 'text-exalt', unique: 'text-chaos',
};

const RARITY_GLOW: Record<string, string> = {
  normal: '', magic: 'drop-shadow-[0_0_4px_hsl(210,60%,50%,0.4)]',
  rare: 'drop-shadow-[0_0_4px_hsl(45,80%,60%,0.4)]', unique: 'drop-shadow-[0_0_6px_hsl(35,90%,55%,0.5)]',
};

const EVAL_BG: Record<PriceEvaluation, string> = {
  well_priced: 'bg-[hsl(140,60%,15%,0.3)]',
  could_be_better: 'bg-[hsl(35,80%,15%,0.3)]',
  mispriced: 'bg-[hsl(0,60%,15%,0.4)]',
};

const EVAL_LABEL: Record<PriceEvaluation, string> = {
  well_priced: 'Well Priced', could_be_better: 'Could Be Better', mispriced: 'Mispriced',
};

function getGridSize(type: StashTab['type']) {
  return type === 'quad' ? 24 : 12;
}

const API_SCHEMA = `{
  "stashTabs": [
    {
      "id": "string",
      "name": "string",
      "type": "normal | quad | currency | map",
      "items": [
        {
          "id": "string",
          "name": "string",
          "x": 0,
          "y": 0,
          "w": 1,
          "h": 1,
          "itemClass": "Currency | Gem | Weapon | Shield | Body Armour | Helmet | Flask | Jewel | Amulet | Belt | Blueprint",
          "rarity": "normal | magic | rare | unique",
          "listedPrice": 100,
          "estimatedPrice": 120,
          "estimatedPriceConfidence": 85,
          "priceDeltaChaos": 20,
          "priceDeltaPercent": 20.0,
          "priceEvaluation": "well_priced | could_be_better | mispriced",
          "currency": "chaos | div",
          "iconUrl": "https://web.poecdn.com/..."
        }
      ]
    }
  ]
}`;

const StashViewerTab = forwardRef<HTMLDivElement, Record<string, never>>(function StashViewerTab(_props, ref) {
  const [tabs, setTabs] = useState<StashTab[]>([]);
  const [status, setStatus] = useState<string>('loading');
  const [activeTab, setActiveTab] = useState(0);
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.getStashStatus()
      .then(async (stashStatus) => {
        setStatus(stashStatus.status);
        if (stashStatus.connected) {
          const rows = await api.getStashTabs();
          setTabs(rows);
        } else {
          setTabs([]);
        }
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Stash feature unavailable');
        setStatus('degraded');
      });
  }, []);

  const tab = tabs[activeTab];
  const grid = tab ? getGridSize(tab.type) : 12;

  return (
    <div ref={ref} className="space-y-3" data-testid="panel-stash-root">
      {/* PoE-style tab bar */}
      <div className="flex items-end gap-0">
        {tabs.map((t, i) => (
          <button
            data-testid={`stash-tab-${t.id}`}
            key={t.id}
            onClick={() => setActiveTab(i)}
            className={cn(
              'px-4 py-1.5 text-xs font-display tracking-wide border border-b-0 transition-all relative -mb-px',
              i === activeTab
                ? 'bg-gold-dim/30 text-gold-bright border-gold-dim z-10'
                : 'bg-[hsl(220,14%,8%)] text-muted-foreground border-gold-dim/30 hover:text-gold hover:bg-gold-dim/10'
            )}
          >
            {t.name}
            {t.type === 'quad' && <span className="ml-1 text-[9px] opacity-50">(Q)</span>}
          </button>
        ))}
      </div>

      {/* Stash grid */}
      {error && <RenderState kind="degraded" message={error} />}
      {!error && status === 'disconnected' && <RenderState kind="disconnected" message="Connect account to view stash" />}
      {!error && status === 'session_expired' && <RenderState kind="session_expired" message="Session expired, login again" />}
      {!error && status === 'feature_unavailable' && <RenderState kind="feature_unavailable" message="Stash feature unavailable" />}
      {!error && tabs.length === 0 && status === 'connected_empty' && <RenderState kind="empty" message="Connected but stash is empty" />}
      {tab && (
        <div className="stash-frame" data-testid="stash-panel-grid">
          <div
            className="stash-grid"
            style={{
              gridTemplateColumns: `repeat(${grid}, minmax(0, 1fr))`,
              gridTemplateRows: `repeat(${grid}, minmax(0, 1fr))`,
            }}
          >
            {/* Empty cell background for every position */}
            {Array.from({ length: grid * grid }).map((_, i) => (
              <div
                key={`e${i}`}
                className="stash-empty-cell"
                style={{
                  gridColumn: (i % grid) + 1,
                  gridRow: Math.floor(i / grid) + 1,
                }}
              />
            ))}
            {/* Items layered on top */}
            {tab.items.map(item => (
              <StashCell
                key={item.id}
                item={item}
                gridSize={grid}
                style={{
                  gridColumn: `${item.x + 1} / span ${item.w}`,
                  gridRow: `${item.y + 1} / span ${item.h}`,
                  zIndex: 1,
                }}
              />
            ))}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 mt-2 px-1 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-[hsl(140,60%,15%,0.5)]" /> Well priced</span>
            <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-[hsl(35,80%,15%,0.5)]" /> Could be better</span>
            <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-[hsl(0,60%,15%,0.6)]" /> Mispriced</span>
          </div>
        </div>
      )}

      {/* API JSON Schema */}
      <Collapsible open={schemaOpen} onOpenChange={setSchemaOpen}>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="text-xs text-muted-foreground gap-1.5">
            <ChevronDown className={cn('h-3 w-3 transition-transform', schemaOpen && 'rotate-180')} />
            API JSON Schema
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="relative mt-2">
            <Button
              variant="outline"
              size="sm"
              className="absolute top-2 right-2 h-7 text-[10px] gap-1"
              onClick={() => { navigator.clipboard.writeText(API_SCHEMA); toast.success('Schema copied'); }}
            >
              <Copy className="h-3 w-3" /> Copy
            </Button>
            <pre className="bg-[hsl(220,14%,6%)] border border-gold-dim/20 rounded p-4 text-[11px] font-mono text-muted-foreground overflow-x-auto whitespace-pre">
              {API_SCHEMA}
            </pre>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

function StashCell({ item, gridSize, style }: { item: StashItem; gridSize: number; style: React.CSSProperties }) {
  const isQuad = gridSize === 24;
  const IconComp = item.itemClass ? ITEM_CLASS_ICONS[item.itemClass] : null;
  const iconSize = isQuad ? 10 : 18;
  const cur = item.currency === 'div' ? 'div' : 'c';

  return (
    <HoverCard openDelay={80} closeDelay={50}>
      <HoverCardTrigger asChild>
        <div
          className={cn('stash-item-cell group', EVAL_BG[item.priceEvaluation])}
          style={style}
        >
          {/* Icon */}
          {IconComp && (
            <IconComp
              size={iconSize}
              className={cn(
                'transition-all shrink-0',
                RARITY_COLOR[item.rarity],
                RARITY_GLOW[item.rarity],
                'opacity-70 group-hover:opacity-100'
              )}
            />
          )}

          {/* Visible name */}
          <span className={cn(
            'leading-tight text-center truncate w-full px-0.5',
            RARITY_COLOR[item.rarity],
            isQuad ? 'text-[5px]' : 'text-[7px]'
          )}>
            {item.name}
          </span>

          {/* Tiny price */}
          {!isQuad && (
            <span className="absolute bottom-0.5 left-0.5 text-[6px] font-mono text-gold-bright/50">
              {item.estimatedPrice}{cur}
            </span>
          )}
        </div>
      </HoverCardTrigger>
      <HoverCardContent side="right" className="w-56 p-3 space-y-2 bg-card border-gold-dim/40">
        <div className="space-y-1">
          <div className="flex items-center gap-1.5">
            {IconComp && <IconComp size={14} className={RARITY_COLOR[item.rarity]} />}
            <p className={cn('font-semibold text-sm', RARITY_COLOR[item.rarity])}>{item.name}</p>
          </div>
          {item.itemClass && (
            <span className="text-[10px] text-muted-foreground">{item.itemClass}</span>
          )}
        </div>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Estimated</span>
            <span className="font-mono text-gold-bright">{item.estimatedPrice} {cur}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Confidence</span>
            <span className="font-mono">{item.estimatedPriceConfidence}%</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Listed</span>
            <span className="font-mono">{item.listedPrice != null ? `${item.listedPrice} ${cur}` : 'N/A'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Delta</span>
            <span className={cn('font-mono', item.priceDeltaChaos > 0 ? 'text-success' : item.priceDeltaChaos < 0 ? 'text-destructive' : 'text-muted-foreground')}>
              {item.priceDeltaChaos > 0 ? '+' : ''}{item.priceDeltaChaos}c ({item.priceDeltaPercent > 0 ? '+' : ''}{item.priceDeltaPercent}%)
            </span>
          </div>
        </div>
        <div className={cn('flex items-center gap-1.5 pt-1 border-t border-border text-xs text-muted-foreground')}>
          <span className={cn('w-3 h-2 rounded-sm', EVAL_BG[item.priceEvaluation])} />
          {EVAL_LABEL[item.priceEvaluation]}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}
