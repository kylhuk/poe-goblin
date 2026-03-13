import { useEffect, useState } from 'react';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { api } from '@/services/api';
import type { StashTab, StashItem } from '@/types/api';
import { cn } from '@/lib/utils';
import {
  Coins, Diamond, CircleDot, FlaskConical, Sword, ShieldHalf,
  FileText, Shirt, HardHat, Crown, type LucideIcon,
} from 'lucide-react';

const ITEM_CLASS_ICONS: Record<string, LucideIcon> = {
  Currency: Coins,
  Gem: Diamond,
  Jewel: CircleDot,
  Flask: FlaskConical,
  Weapon: Sword,
  Shield: ShieldHalf,
  'Body Armour': Shirt,
  Helmet: HardHat,
  Blueprint: FileText,
  Amulet: Crown,
  Belt: Crown,
};

const RARITY_COLOR: Record<string, string> = {
  normal: 'text-muted-foreground',
  magic: 'text-info',
  rare: 'text-exalt',
  unique: 'text-chaos',
};

const RARITY_GLOW: Record<string, string> = {
  normal: '',
  magic: 'drop-shadow-[0_0_4px_hsl(210,60%,50%,0.4)]',
  rare: 'drop-shadow-[0_0_4px_hsl(45,80%,60%,0.4)]',
  unique: 'drop-shadow-[0_0_6px_hsl(35,90%,55%,0.5)]',
};

const HEALTH_DOT: Record<string, string> = {
  good: 'bg-success',
  ok: 'bg-warning',
  bad: 'bg-destructive',
};

function getGridSize(type: StashTab['type']) {
  return type === 'quad' ? 24 : 12;
}

export default function StashViewerTab() {
  const [tabs, setTabs] = useState<StashTab[]>([]);
  const [activeTab, setActiveTab] = useState(0);
  useEffect(() => { api.getStashTabs().then(setTabs); }, []);

  const tab = tabs[activeTab];
  const grid = tab ? getGridSize(tab.type) : 12;

  return (
    <div className="space-y-3">
      {/* PoE-style tab bar */}
      <div className="flex items-end gap-0">
        {tabs.map((t, i) => (
          <button
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
      {tab && (
        <div className="stash-frame">
          <div
            className="stash-grid"
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
                    gridSize={grid}
                    style={{
                      gridColumn: `${item.x + 1} / span ${item.w}`,
                      gridRow: `${item.y + 1} / span ${item.h}`,
                    }}
                  />
                );
              }
              if (item && (gx !== item.x || gy !== item.y)) return null;

              return <div key={i} className="stash-empty-cell" />;
            })}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 mt-2 px-1 text-[10px] text-muted-foreground">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-success" /> Well priced</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-warning" /> Could be better</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-destructive" /> Mispriced</span>
          </div>
        </div>
      )}
    </div>
  );
}

function StashCell({ item, gridSize, style }: { item: StashItem; gridSize: number; style: React.CSSProperties }) {
  const isQuad = gridSize === 24;
  const IconComp = item.itemClass ? ITEM_CLASS_ICONS[item.itemClass] : null;
  const iconSize = isQuad ? 12 : 20;

  const delta = item.listedPrice ? item.estimatedValue - item.listedPrice : null;
  const deltaPct = item.listedPrice ? ((delta! / item.listedPrice) * 100).toFixed(1) : null;
  const cur = item.currency === 'div' ? 'div' : 'c';

  const rarityLabel = { normal: 'Normal', magic: 'Magic', rare: 'Rare', unique: 'Unique' };
  const healthLabel = { good: 'Well Priced', ok: 'Could Be Better', bad: 'Mispriced' };

  return (
    <HoverCard openDelay={80} closeDelay={50}>
      <HoverCardTrigger asChild>
        <div
          className="stash-item-cell group"
          style={style}
        >
          {/* Price health dot */}
          <span className={cn('absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full opacity-80', HEALTH_DOT[item.priceHealth])} />

          {/* Icon */}
          {IconComp && (
            <IconComp
              size={iconSize}
              className={cn(
                'transition-all',
                RARITY_COLOR[item.rarity],
                RARITY_GLOW[item.rarity],
                'opacity-70 group-hover:opacity-100'
              )}
            />
          )}

          {/* Tiny price in corner */}
          {!isQuad && (
            <span className="absolute bottom-0.5 left-0.5 text-[7px] font-mono text-gold-bright/60 group-hover:text-gold-bright/90">
              {item.estimatedValue}{cur}
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
          <div className="flex items-center gap-1.5">
            <span className={cn('text-[10px] px-1.5 py-0.5 rounded border', RARITY_COLOR[item.rarity], 'border-current/20 opacity-80')}>
              {rarityLabel[item.rarity]}
            </span>
            {item.itemClass && (
              <span className="text-[10px] text-muted-foreground">{item.itemClass}</span>
            )}
          </div>
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
          <span className={cn('w-2 h-2 rounded-full', HEALTH_DOT[item.priceHealth])} />
          <span className="text-xs text-muted-foreground">{healthLabel[item.priceHealth]}</span>
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}
