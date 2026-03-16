import { forwardRef, useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { RenderState } from '../shared/RenderState';
import { Button } from '../ui/button';
import { api } from '../../services/api';
import type {
  ScannerRecommendation,
  ScannerRecommendationsRequest,
  ScannerRecommendationsResponse,
} from '../../types/api';
import { useMouseGlow } from '../../hooks/useMouseGlow';

type ScannerSort = 'expected_profit_chaos' | 'expected_profit_per_minute_chaos';

const SORT_OPTIONS: Array<{ value: ScannerSort; label: string; testId: string }> = [
  {
    value: 'expected_profit_chaos',
    label: 'Profit',
    testId: 'scanner-sort-profit',
  },
  {
    value: 'expected_profit_per_minute_chaos',
    label: 'Profit / min',
    testId: 'scanner-sort-profit-per-minute',
  },
];

const QA_SCANNER_RECOMMENDATIONS_PAGE_SIZE = (() => {
  const rawValue = import.meta.env.VITE_SCANNER_RECOMMENDATIONS_PAGE_SIZE;
  if (typeof rawValue !== 'string' || rawValue.trim() === '') {
    return undefined;
  }
  const parsedValue = Number.parseInt(rawValue, 10);
  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : undefined;
})();

function createEmptyResponse(): ScannerRecommendationsResponse {
  return {
    recommendations: [],
    meta: {
      nextCursor: null,
      hasMore: false,
    },
  };
}

function formatChaos(value: number | null): string {
  return value !== null ? `${value}c` : 'N/A';
}

function scannerRecommendationsRequest(sort: ScannerSort, cursor?: string): ScannerRecommendationsRequest {
  const request: ScannerRecommendationsRequest = { sort };
  if (QA_SCANNER_RECOMMENDATIONS_PAGE_SIZE !== undefined) {
    request.limit = QA_SCANNER_RECOMMENDATIONS_PAGE_SIZE;
  }
  if (cursor) {
    request.cursor = cursor;
  }
  return request;
}

const OpportunitiesTab = forwardRef<HTMLDivElement, Record<string, never>>(function OpportunitiesTab(_props, ref) {
  const [recommendationResponse, setRecommendationResponse] = useState<ScannerRecommendationsResponse>(createEmptyResponse);
  const [sort, setSort] = useState<ScannerSort>('expected_profit_chaos');
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mouseGlow = useMouseGlow();
  const requestVersionRef = useRef(0);

  useEffect(() => {
    const requestVersion = ++requestVersionRef.current;

    setLoading(true);
    setLoadingMore(false);
    setError(null);
    setRecommendationResponse(createEmptyResponse());

    api.getScannerRecommendations(scannerRecommendationsRequest(sort))
      .then(nextResponse => {
        if (requestVersionRef.current !== requestVersion) {
          return;
        }
        setRecommendationResponse(nextResponse);
      })
      .catch((err: unknown) => {
        if (requestVersionRef.current !== requestVersion) {
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load opportunities');
      })
      .finally(() => {
        if (requestVersionRef.current === requestVersion) {
          setLoading(false);
        }
      });
  }, [sort]);

  const loadMore = async () => {
    const nextCursor = recommendationResponse.meta.nextCursor;
    if (loading || loadingMore || !recommendationResponse.meta.hasMore || !nextCursor) {
      return;
    }

    const requestVersion = requestVersionRef.current;
    setLoadingMore(true);
    setError(null);

    try {
      const nextResponse = await api.getScannerRecommendations(scannerRecommendationsRequest(sort, nextCursor));
      if (requestVersionRef.current !== requestVersion) {
        return;
      }
      setRecommendationResponse(previousResponse => {
        if (!previousResponse.meta.hasMore || previousResponse.meta.nextCursor !== nextCursor) {
          return previousResponse;
        }
        return {
          recommendations: [...previousResponse.recommendations, ...nextResponse.recommendations],
          meta: nextResponse.meta,
        };
      });
    } catch (err: unknown) {
      if (requestVersionRef.current !== requestVersion) {
        return;
      }
      setError(err instanceof Error ? err.message : 'Failed to load opportunities');
    } finally {
      if (requestVersionRef.current === requestVersion) {
        setLoadingMore(false);
      }
    }
  };

  const recommendations = recommendationResponse.recommendations;
  const canLoadMore = recommendationResponse.meta.hasMore && recommendationResponse.meta.nextCursor;

  if (loading) {
    return <div ref={ref} data-testid="panel-opportunities-root"><RenderState kind="loading" message="Scanning market..." /></div>;
  }

  if (error) {
    return <div ref={ref} data-testid="panel-opportunities-root"><RenderState kind="degraded" message={error} /></div>;
  }

  return (
    <div ref={ref} className="space-y-6" data-testid="panel-opportunities-root">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold font-sans text-foreground">Market Opportunities</h2>
          <p className="text-xs text-muted-foreground">Scanner-backed recommendations with profit and time-efficiency signals.</p>
        </div>
        <div className="flex items-center gap-2 rounded-md border border-border bg-secondary/30 p-1">
          {SORT_OPTIONS.map(option => (
            <Button
              key={option.value}
              data-testid={option.testId}
              type="button"
              size="sm"
              variant={sort === option.value ? 'default' : 'outline'}
              className="h-8 px-3 text-xs btn-game"
              onClick={() => setSort(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>
      </div>

      {recommendations.length === 0 ? (
        <RenderState kind="empty" message="No opportunities found in the latest scan." />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4">
            {recommendations.map(r => (
              <OpportunityCard key={`${r.scannerRunId}-${r.itemOrMarketKey}`} recommendation={r} mouseGlow={mouseGlow} />
            ))}
          </div>
          {canLoadMore ? (
            <div className="flex justify-center">
              <Button
                data-testid="scanner-load-more"
                type="button"
                variant="outline"
                className="min-w-40 btn-game"
                disabled={loadingMore}
                onClick={() => {
                  void loadMore();
                }}
              >
                {loadingMore ? 'Loading...' : 'Load More'}
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
});

OpportunitiesTab.displayName = 'OpportunitiesTab';
export default OpportunitiesTab;

function OpportunityCard({
  recommendation,
  mouseGlow,
}: {
  recommendation: ScannerRecommendation;
  mouseGlow: (event: React.MouseEvent<HTMLElement>) => void;
}) {
  return (
    <Card className="card-game" onMouseMove={mouseGlow}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-sm font-sans">{recommendation.itemOrMarketKey}</CardTitle>
          <span className="text-xs font-mono text-muted-foreground">{recommendation.strategyId}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-foreground">{recommendation.whyItFired}</p>

        <div className="grid grid-cols-2 gap-4 rounded border border-border bg-secondary/30 p-3 sm:grid-cols-3 xl:grid-cols-6">
          <div>
            <p className="text-xs text-muted-foreground">Buy Plan</p>
            <p className="text-sm font-medium text-success">{recommendation.buyPlan}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Transform</p>
            <p className="text-sm font-medium text-foreground">{recommendation.transformPlan}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Exit Plan</p>
            <p className="text-sm font-medium text-foreground">{recommendation.exitPlan}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Expected Profit</p>
            <p className="text-sm font-medium text-warning">{formatChaos(recommendation.expectedProfitChaos)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Profit / min</p>
            <p className="text-sm font-medium text-primary">{formatChaos(recommendation.expectedProfitPerMinuteChaos)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Hold Window</p>
            <p className="text-sm font-medium text-foreground">{recommendation.expectedHoldTime || 'N/A'}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
