import { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { api } from '@/services/api';
import type { StashTab, StashItem } from '@/types/api';
import { cn } from '@/lib/utils';

function getGridSize(type: StashTab['type']) {
  return type === 'quad' ? 24 : 12;
}

export default function StashViewerTab() {
  const [tabs, setTabs] = useState<StashTab[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  useEffect(() => { api.getStashTabs().then(setTabs); }, []);

  const tab = tabs[activeTab];
  const grid = tab ? getGridSize(tab.type) : 12;
  const isQuad = tab?.type === 'quad';

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <h2 className="text-lg font-semibold font-sans text-foreground">Stash Viewer</h2>
        <div className="flex gap-1">
          {tabs.map((t, i) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(i)}
              className={cn(
                'px-3 py-1 text-xs rounded border transition-colors',
                i === activeTab ? 'bg-primary text-primary-foreground border-primary' : 'bg-secondary text-muted-foreground border-border hover:text-foreground'
              )}
            >
              {t.name}
              {t.type === 'quad' && <span className="ml-1 text-[9px] opacity-60">(Q)</span>}
            </button>
          ))}
        </div>
      </div>

      {tab && (
        <Card>
          <CardContent className="p-4">
            <div
              className="grid gap-px bg-border/50 rounded overflow-hidden"
              style={{
                gridTemplateColumns: `repeat(${grid}, 1fr)`,
                gridTemplateRows: `repeat(${grid}, 1fr)`,
              }}
            >
              {Array.from({ length: grid * grid }).map((_, i) => {
                const gx = i % grid;
                const gy = Math.floor(i / grid);
                const item = tab.items.find(it => gx >= it.x && gx < it.x + it.w && gy >= it.y && gy < it.y + it.h);

                if (item && gx === item.x && gy === item.y) {
                  return (
                    <StashCell
                      key={item.id}
                      item={item}
                      isQuad={isQuad}
                      style={{
                        gridColumn: `${item.x + 1} / span ${item.w}`,
                        gridRow: `${item.y + 1} / span ${item.h}`,
                      }}
                    />
                  );
                }
                if (item && (gx !== item.x || gy !== item.y)) return null;

                return <div key={i} className={cn('bg-background/50', isQuad ? 'min-h-[20px]' : 'min-h-[40px]')} />;
              })}
            </div>

            <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-success/30 border border-success/50" /> Well priced</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-warning/30 border border-warning/50" /> Could be better</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-sm bg-destructive/30 border border-destructive/50" /> Mispriced</span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function StashCell({ item, isQuad, style }: { item: StashItem; isQuad: boolean; style: React.CSSProperties }) {
  const healthColor = {
    good: 'bg-success/15 border-success/30 hover:bg-success/25',
    ok: 'bg-warning/15 border-warning/30 hover:bg-warning/25',
    bad: 'bg-destructive/15 border-destructive/30 hover:bg-destructive/25',
  };

  const rarityColor = {
    normal: 'text-muted-foreground',
    magic: 'text-info',
    rare: 'text-exalt',
    unique: 'text-chaos',
  };

  const rarityLabel = { normal: 'Normal', magic: 'Magic', rare: 'Rare', unique: 'Unique' };

  const delta = item.listedPrice ? item.estimatedValue - item.listedPrice : null;
  const deltaPct = item.listedPrice ? ((delta! / item.listedPrice) * 100).toFixed(1) : null;
  const cur = item.currency === 'div' ? 'div' : 'c';

  const healthLabel = { good: 'Well Priced', ok: 'Could Be Better', bad: 'Mispriced' };
  const healthDot = { good: 'bg-success', ok: 'bg-warning', bad: 'bg-destructive' };

  return (
    <HoverCard openDelay={100} closeDelay={50}>
      <HoverCardTrigger asChild>
        <div
          className={cn(
            'border flex flex-col items-center justify-center p-0.5 cursor-pointer transition-colors',
            healthColor[item.priceHealth],
            isQuad ? 'min-h-[20px]' : 'min-h-[40px]'
          )}
          style={style}
        >
          <span className={cn('leading-tight text-center truncate w-full', rarityColor[item.rarity], isQuad ? 'text-[7px]' : 'text-[10px]')}>
            {item.name}
          </span>
          <span className={cn('font-mono text-gold-bright', isQuad ? 'text-[6px]' : 'text-[9px]')}>
            {item.estimatedValue}{cur}
          </span>
        </div>
      </HoverCardTrigger>
      <HoverCardContent side="right" className="w-56 p-3 space-y-2 bg-card border-border">
        <div className="space-y-1">
          <p className={cn('font-semibold text-sm', rarityColor[item.rarity])}>{item.name}</p>
          <span className={cn('text-[10px] px-1.5 py-0.5 rounded border', rarityColor[item.rarity], 'border-current/20 opacity-80')}>
            {rarityLabel[item.rarity]}
          </span>
        </div>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-muted-foreground">Estimated</span>
            <span className="font-mono text-gold-bright">{item.estimatedValue} {cur}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-muted-foreground">Listed</span>
            <span className="font-mono">{item.listedPrice != null ? `${item.listedPrice} ${cur}` : 'N/A'}</span>
          </div>
          {delta != null && (
            <div className="flex justify-between">
              <span className="text-muted-foreground">Delta</span>
              <span className={cn('font-mono', delta > 0 ? 'text-success' : delta < 0 ? 'text-destructive' : 'text-muted-foreground')}>
                {delta > 0 ? '+' : ''}{delta.toFixed(1)} {cur} ({deltaPct}%)
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5 pt-1 border-t border-border">
          <span className={cn('w-2 h-2 rounded-full', healthDot[item.priceHealth])} />
          <span className="text-xs text-muted-foreground">{healthLabel[item.priceHealth]}</span>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}
