import React from 'react';
import type { PoeItem } from '@/types/api';
import { cn } from '@/lib/utils';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import ItemTooltip from './ItemTooltip';

const FRAME_TYPE_BORDER: Record<number, string> = {
  0: 'border-muted-foreground/30',
  1: 'border-info/50',
  2: 'border-exalt/50',
  3: 'border-chaos/60',
  4: 'border-divine/50',
  5: 'border-gold/40',
  6: 'border-divine/40',
  9: 'border-[hsl(15,70%,50%)]/50',
};

const EVAL_BG: Record<string, string> = {
  well_priced: 'bg-success/15',
  could_be_better: 'bg-warning/15',
  mispriced: 'bg-destructive/20',
};

interface StashItemCellProps {
  item: PoeItem;
  isQuad?: boolean;
  style?: React.CSSProperties;
  className?: string;
}

export default function StashItemCell({ item, isQuad, style, className }: StashItemCellProps) {
  const evalBg = item.priceEvaluation ? EVAL_BG[item.priceEvaluation] : '';
  const borderClass = FRAME_TYPE_BORDER[item.frameType] ?? 'border-muted-foreground/20';
  const displayName = item.name || item.typeLine;

  return (
    <HoverCard openDelay={80} closeDelay={50}>
      <HoverCardTrigger asChild>
        <div
          className={cn(
            'stash-item-cell group relative flex flex-col items-center justify-center overflow-hidden',
            evalBg,
            className,
          )}
          style={style}
        >
          {/* Official icon */}
          {item.icon && (
            <img
              src={item.icon}
              alt={displayName}
              className={cn(
                'max-w-full max-h-full object-contain pointer-events-none select-none',
                'transition-all group-hover:brightness-125',
              )}
              loading="lazy"
              draggable={false}
            />
          )}

          {/* Stack size badge */}
          {item.stackSize != null && item.stackSize > 1 && (
            <span className={cn(
              'absolute top-0 left-0.5 font-mono font-bold text-foreground drop-shadow-[0_1px_2px_rgba(0,0,0,0.9)]',
              isQuad ? 'text-[6px]' : 'text-[9px]',
            )}>
              {item.stackSize}
            </span>
          )}

          {/* Fallback name if no icon */}
          {!item.icon && (
            <span className={cn(
              'leading-tight text-center truncate w-full px-0.5 text-muted-foreground',
              isQuad ? 'text-[5px]' : 'text-[7px]',
            )}>
              {displayName}
            </span>
          )}

          {/* Price tag */}
          {item.estimatedPrice != null && !isQuad && (
            <span className="absolute bottom-0 right-0.5 text-[6px] font-mono text-gold-bright/60">
              {item.estimatedPrice}{item.currency === 'div' ? 'd' : 'c'}
            </span>
          )}
        </div>
      </HoverCardTrigger>
      <HoverCardContent side="right" className="w-64 p-0 bg-card border-gold-dim/50 shadow-lg shadow-black/50">
        <ItemTooltip item={item} />
      </HoverCardContent>
    </HoverCard>
  );
}
