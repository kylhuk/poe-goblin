import React, { forwardRef, useCallback, useEffect, useState } from 'react';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { api } from '@/services/api';
import type {
  StashItem,
  StashItemHistoryResponse,
  StashScanStatus,
  StashStatus,
  StashTab,
  StashTabMeta,
  PriceEvaluation,
  SpecialLayout,
} from '@/types/api';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import {
  Coins, Diamond, CircleDot, FlaskConical, Sword, ShieldHalf,
  FileText, Shirt, HardHat, Crown, ChevronDown, Copy, Loader2, History, type LucideIcon,
} from 'lucide-react';
import { RenderState } from '@/components/shared/RenderState';
import NormalGrid from '@/components/stash/NormalGrid';
import SpecialLayoutGrid from '@/components/stash/SpecialLayoutGrid';

const API_SCHEMA = `{
  "scanId": "string | null",
  "publishedAt": "ISO-8601 | null",
  "isStale": false,
  "scanStatus": {
    "status": "idle | running | publishing | published | failed"
  },
  "stashTabs": []
}`;

const EMPTY_SCAN_STATUS: StashScanStatus = {
  status: 'idle',
  activeScanId: null,
  publishedScanId: null,
  startedAt: null,
  updatedAt: null,
  publishedAt: null,
  error: null,
  progress: {
    tabsProcessed: 0,
    tabsTotal: 0,
    itemsProcessed: 0,
    itemsTotal: 0,
  },
};

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
  const [tabsMeta, setTabsMeta] = useState<StashTabMeta[]>([]);
  const [activeTab, setActiveTab] = useState<StashTab | null>(null);
  const [activeTabIndex, setActiveTabIndex] = useState(0);
  const [tabLoading, setTabLoading] = useState(false);
  const [tabMismatch, setTabMismatch] = useState<string | null>(null);
  const [status, setStatus] = useState<StashStatus['status'] | 'loading' | 'degraded'>('loading');
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [publishedScanId, setPublishedScanId] = useState<string | null>(null);
  const [publishedAt, setPublishedAt] = useState<string | null>(null);
  const [scanStatus, setScanStatus] = useState<StashScanStatus>(EMPTY_SCAN_STATUS);
  const [scanBusy, setScanBusy] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyPayload, setHistoryPayload] = useState<StashItemHistoryResponse | null>(null);

  const loadTab = useCallback(async (tabIndex: number) => {
    setTabLoading(true);
    setTabMismatch(null);
    try {
      const payload = await api.getStashTabs(tabIndex);
      if (payload.stashTabs.length > 0) {
        const returned = payload.stashTabs[0];
        setActiveTab(returned);
        // Detect mismatch: backend returned a different tab than requested
        if (returned.returnedIndex != null && returned.returnedIndex !== tabIndex) {
          setTabMismatch(`Requested tab index ${tabIndex}, but backend returned index ${returned.returnedIndex} ("${returned.name}")`);
        }
      } else {
        setActiveTab(null);
      }
      // Update tabsMeta if returned (first load or refresh)
      if (payload.tabsMeta.length > 0) {
        setTabsMeta(payload.tabsMeta);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to load tab');
    } finally {
      setTabLoading(false);
    }
  }, []);

  const pollStatus = useCallback(async () => {
    const stashStatus = await api.getStashStatus();
    setStatus(stashStatus.status);
    setPublishedScanId(stashStatus.publishedScanId ?? null);
    setPublishedAt(stashStatus.publishedAt ?? null);
    setScanStatus(stashStatus.scanStatus ?? EMPTY_SCAN_STATUS);
    if (!stashStatus.connected) {
      setActiveTab(null);
      setTabsMeta([]);
    }
    setError(null);
    return stashStatus;
  }, []);

  const initialLoadDone = React.useRef(false);

  useEffect(() => {
    if (initialLoadDone.current) return;
    initialLoadDone.current = true;
    (async () => {
      try {
        const stashStatus = await pollStatus();
        if (stashStatus.connected) {
          await loadTab(0);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Stash feature unavailable');
        setStatus('degraded');
      }
    })();
  }, [pollStatus, loadTab]);

  useEffect(() => {
    if (!scanBusy) {
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getStashScanStatus();
        setScanStatus(next);
        if (next.status === 'published') {
          window.clearInterval(timer);
          setScanBusy(false);
          await loadTab(activeTabIndex);
        }
        if (next.status === 'failed') {
          window.clearInterval(timer);
          setScanBusy(false);
          if (next.error) {
            toast.error(next.error);
          }
        }
      } catch (err) {
        window.clearInterval(timer);
        setScanBusy(false);
        toast.error(err instanceof Error ? err.message : 'Failed to fetch scan status');
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [scanBusy, loadTab, activeTabIndex]);

  const startScan = useCallback(async () => {
    try {
      const next = await api.startStashScan();
      setScanStatus((current) => ({
        ...current,
        status: 'running',
        activeScanId: next.scanId,
        startedAt: next.startedAt,
        updatedAt: next.startedAt,
        error: null,
      }));
      setScanBusy(true);
      toast.success(next.deduplicated ? 'Scan already running' : 'Scan started');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to start scan');
    }
  }, []);

  const openHistory = useCallback(async (item: StashItem) => {
    if (!item.fingerprint) {
      return;
    }
    setHistoryLoading(true);
    setHistoryOpen(true);
    try {
      const payload = await api.getStashItemHistory(item.fingerprint);
      setHistoryPayload(payload);
    } catch (err) {
      setHistoryOpen(false);
      toast.error(err instanceof Error ? err.message : 'Failed to load history');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const activeTabRef = React.useRef(activeTab);
  activeTabRef.current = activeTab;
  const activeTabIndexRef = React.useRef(activeTabIndex);
  activeTabIndexRef.current = activeTabIndex;

  useEffect(() => {
    const iv = window.setInterval(async () => {
      try {
        const st = await pollStatus();
        // If connected but no tab loaded yet, retry loading
        if (st.connected && !activeTabRef.current) {
          await loadTab(activeTabIndexRef.current);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Stash feature unavailable');
        setStatus('degraded');
      }
    }, 5_000);
    return () => clearInterval(iv);
  }, [pollStatus, loadTab]);

  const tab = activeTab;
  const specialLayout = tab ? getSpecialLayout(tab) : null;
  const isGrid = tab && !specialLayout;
  const gridSize = (() => {
    if (!tab) return 12;
    if (tab.quadLayout || tab.type === 'quad') return 24;
    const maxCoord = tab.items.reduce((max, item) => Math.max(max, item.x + item.w, item.y + item.h), 0);
    return maxCoord > 12 ? 24 : 12;
  })();
  const runningScan = scanBusy || scanStatus.status === 'running' || scanStatus.status === 'publishing';

  return (
    <div ref={ref} className="space-y-3" data-testid="panel-stash-root">
      <div className="flex flex-col gap-3 rounded border border-gold-dim/20 bg-card/60 p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-semibold text-foreground">Private Stash</p>
          <p className="text-xs text-muted-foreground">
            {publishedScanId ? `Published ${publishedScanId}` : 'No published scan yet'}
            {publishedAt ? ` · ${publishedAt}` : ''}
          </p>
          {(runningScan || scanStatus.error) && (
            <p className="text-xs text-muted-foreground">
              {scanStatus.status === 'failed'
                ? `Last scan failed${scanStatus.error ? `: ${scanStatus.error}` : ''}`
                : tab
                  ? `Scan ${scanStatus.status} — showing last available stash data`
                  : `Scan ${scanStatus.status}: ${scanStatus.progress.tabsProcessed}/${scanStatus.progress.tabsTotal} tabs · ${scanStatus.progress.itemsProcessed}/${scanStatus.progress.itemsTotal} items`}
            </p>
          )}
        </div>
        <Button onClick={startScan} disabled={runningScan} className="gap-2" aria-label="Scan">
          {runningScan ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <History className="h-3.5 w-3.5" />}
          Scan
        </Button>
      </div>

      <div className="flex items-end gap-0 flex-wrap">
        {tabsMeta.map((t, i) => (
          <button
            type="button"
            data-testid={`stash-tab-${t.id}`}
            key={t.id}
            onClick={() => {
              setActiveTabIndex(t.tabIndex);
              loadTab(t.tabIndex);
            }}
            className={cn(
              'px-4 py-1.5 text-xs font-display tracking-wide border border-b-0 transition-all relative -mb-px',
              t.tabIndex === activeTabIndex
                ? 'bg-gold-dim/30 text-gold-bright border-gold-dim z-10'
                : 'bg-card text-muted-foreground border-gold-dim/30 hover:text-gold hover:bg-gold-dim/10'
            )}
          >
            {t.name}
            {t.type === 'QuadStash' && <span className="ml-1 text-[9px] opacity-50">(Q)</span>}
          </button>
        ))}
      </div>

      {/* Status states */}
      {error && <RenderState kind="degraded" message={error} />}
      {!error && status === 'disconnected' && <RenderState kind="disconnected" message="Connect account to view stash" />}
      {!error && status === 'session_expired' && <RenderState kind="session_expired" message="Session expired, login again" />}
      {!error && status === 'feature_unavailable' && <RenderState kind="feature_unavailable" message="Stash feature unavailable" />}
      {!error && tabsMeta.length === 0 && !tab && status === 'connected_empty' && <RenderState kind="empty" message="Connected but stash is empty" />}
      {tabLoading && <RenderState kind="loading" message="Loading tab..." />}
      {tabMismatch && (
        <div className="rounded border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning" data-testid="tab-mismatch-warning">
          ⚠ {tabMismatch}
        </div>
      )}
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

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{historyPayload?.item.name || 'Item history'}</DialogTitle>
            <DialogDescription>
              {historyPayload?.item.itemClass || ''}
            </DialogDescription>
          </DialogHeader>
          {historyLoading && <p className="text-sm text-muted-foreground">Loading history...</p>}
          {!historyLoading && historyPayload && (
            <div className="space-y-3">
              {historyPayload.history.map(entry => (
                <div key={`${entry.scanId}-${entry.pricedAt}`} className="rounded border border-border p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">{entry.predictedValue}{entry.currency === 'div' ? ' div' : ' c'}</span>
                    <span className="text-xs text-muted-foreground">{entry.pricedAt}</span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Confidence {entry.confidence}% · p10 {entry.interval.p10 ?? 'n/a'} · p90 {entry.interval.p90 ?? 'n/a'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
});

StashViewerTab.displayName = 'StashViewerTab';

export default StashViewerTab;
