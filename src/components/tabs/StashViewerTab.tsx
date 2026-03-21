import React, { forwardRef, useCallback, useEffect, useState } from 'react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import type { StashTab, SpecialLayout } from '@/types/api';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { ChevronDown, Copy } from 'lucide-react';
import { RenderState } from '@/components/shared/RenderState';
import NormalGrid from '@/components/stash/NormalGrid';
import SpecialLayoutGrid from '@/components/stash/SpecialLayoutGrid';

const API_SCHEMA = `{
  "stashTabs": [
    {
      "id": "string",
      "name": "string",
      "type": "normal | quad | currency | fragment | ...",
      "items": [
        {
          "id": "string",
          "name": "string",
          "typeLine": "string",
          "icon": "https://web.poecdn.com/...",
          "x": 0, "y": 0, "w": 1, "h": 1,
          "frameType": 3,
          "stackSize": 1,
          "properties": [...],
          "explicitMods": [...],
          "sockets": [{ "group": 0, "sColour": "R" }],
          "estimatedPrice": 120,
          "priceEvaluation": "well_priced | could_be_better | mispriced"
        }
      ],
      "currencyLayout": { "sections": [...], "layout": { "0": { "x": 10, "y": 10, "w": 47, "h": 47 } } }
    }
  ]
}`;

function getSpecialLayout(tab: StashTab): SpecialLayout | null {
  return tab.currencyLayout
    ?? tab.fragmentLayout
    ?? tab.essenceLayout
    ?? tab.deliriumLayout
    ?? tab.blightLayout
    ?? tab.ultimatumLayout
    ?? tab.mapLayout
    ?? tab.divinationLayout
    ?? tab.uniqueLayout
    ?? tab.delveLayout
    ?? tab.metamorphLayout
    ?? null;
}

const StashViewerTab = forwardRef<HTMLDivElement, Record<string, never>>(function StashViewerTab(_props, ref) {
  const [tabs, setTabs] = useState<StashTab[]>([]);
  const [status, setStatus] = useState<string>('loading');
  const [activeTab, setActiveTab] = useState(0);
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
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

  useEffect(() => {
    load();
    const iv = setInterval(load, 5_000);
    return () => clearInterval(iv);
  }, [load]);

  const tab = tabs[activeTab];
  const specialLayout = tab ? getSpecialLayout(tab) : null;
  const isGrid = tab && !specialLayout;
  const gridSize = tab?.quadLayout ? 24 : 12;

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
                : 'bg-card text-muted-foreground border-gold-dim/30 hover:text-gold hover:bg-gold-dim/10'
            )}
          >
            {t.name}
            {t.type === 'quad' && <span className="ml-1 text-[9px] opacity-50">(Q)</span>}
          </button>
        ))}
      </div>

      {/* Status states */}
      {error && <RenderState kind="degraded" message={error} />}
      {!error && status === 'disconnected' && <RenderState kind="disconnected" message="Connect account to view stash" />}
      {!error && status === 'session_expired' && <RenderState kind="session_expired" message="Session expired, login again" />}
      {!error && status === 'feature_unavailable' && <RenderState kind="feature_unavailable" message="Stash feature unavailable" />}
      {!error && tabs.length === 0 && status === 'connected_empty' && <RenderState kind="empty" message="Connected but stash is empty" />}

      {/* Grid / Special layout rendering */}
      {tab && specialLayout && (
        <SpecialLayoutGrid items={tab.items} layout={specialLayout} />
      )}
      {tab && isGrid && (
        <NormalGrid items={tab.items} gridSize={gridSize} />
      )}

      {/* Legend */}
      {tab && (
        <div className="flex items-center gap-4 mt-2 px-1 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-success/30" /> Well priced</span>
          <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-warning/30" /> Could be better</span>
          <span className="flex items-center gap-1"><span className="w-3 h-2 rounded-sm bg-destructive/30" /> Mispriced</span>
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
            <pre className="bg-background border border-gold-dim/20 rounded p-4 text-[11px] font-mono text-muted-foreground overflow-x-auto whitespace-pre">
              {API_SCHEMA}
            </pre>
          </div>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
});

StashViewerTab.displayName = 'StashViewerTab';
export default StashViewerTab;
