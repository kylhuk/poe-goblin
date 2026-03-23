// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ButtonHTMLAttributes, HTMLAttributes } from 'react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import StashViewerTab from './StashViewerTab';

const {
  getStashStatusMock,
  getStashTabsMock,
  startStashScanMock,
  getStashScanStatusMock,
  getStashItemHistoryMock,
} = vi.hoisted(() => ({
  getStashStatusMock: vi.fn(),
  getStashTabsMock: vi.fn(),
  startStashScanMock: vi.fn(),
  getStashScanStatusMock: vi.fn(),
  getStashItemHistoryMock: vi.fn(),
}));

vi.mock('../shared/RenderState', () => ({
  RenderState: ({ kind, message }: { kind: string; message?: string }) => (
    <div data-testid={`state-${kind}`}>{message ?? kind}</div>
  ),
}));

vi.mock('../ui/button', () => ({
  Button: ({ children, className, size: _size, variant: _variant, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { size?: string; variant?: string }) => (
    <button className={className} {...props}>{children}</button>
  ),
}));

vi.mock('../ui/hover-card', () => ({
  HoverCard: ({ children }: HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
  HoverCardTrigger: ({ children }: HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
  HoverCardContent: ({ children }: HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
}));

vi.mock('../ui/collapsible', () => ({
  Collapsible: ({ children }: HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
  CollapsibleTrigger: ({ children }: HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
  CollapsibleContent: ({ children }: HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
}));

vi.mock('../ui/dialog', () => ({
  Dialog: ({ children }: HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
  DialogContent: ({ children }: HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
  DialogHeader: ({ children }: HTMLAttributes<HTMLDivElement>) => <div>{children}</div>,
  DialogTitle: ({ children }: HTMLAttributes<HTMLHeadingElement>) => <h2>{children}</h2>,
  DialogDescription: ({ children }: HTMLAttributes<HTMLParagraphElement>) => <p>{children}</p>,
}));

vi.mock('../../services/api', () => ({
  api: {
    getStashStatus: getStashStatusMock,
    getStashTabs: getStashTabsMock,
    startStashScan: startStashScanMock,
    getStashScanStatus: getStashScanStatusMock,
    getStashItemHistory: getStashItemHistoryMock,
  },
}));

const publishedTabsPayload = {
  scanId: 'scan-1',
  publishedAt: '2026-03-21T12:00:00Z',
  isStale: false,
  scanStatus: null,
  stashTabs: [
    {
      id: 'tab-2',
      name: 'Currency',
      type: 'currency',
      items: [
        {
          id: 'item-1',
          fingerprint: 'sig:item-1',
          name: 'Grim Bane',
          x: 0,
          y: 0,
          w: 1,
          h: 1,
          itemClass: 'Helmet',
          rarity: 'rare',
          listedPrice: 40,
          estimatedPrice: 45,
          estimatedPriceConfidence: 82,
          priceDeltaChaos: 5,
          priceDeltaPercent: 12.5,
          priceEvaluation: 'mispriced',
          currency: 'chaos',
          iconUrl: 'https://web.poecdn.com/item.png',
          interval: { p10: 39, p90: 51 },
        },
      ],
    },
    {
      id: 'tab-9',
      name: 'Dump',
      type: 'quad',
      items: [],
    },
  ],
};

beforeEach(() => {
  getStashStatusMock.mockResolvedValue({
    status: 'connected_populated',
    connected: true,
    tabCount: 2,
    itemCount: 1,
    session: { accountName: 'qa-exile', expiresAt: '2099-01-01T00:00:00Z' },
    publishedScanId: 'scan-1',
    publishedAt: '2026-03-21T12:00:00Z',
    scanStatus: null,
  });
  getStashTabsMock.mockResolvedValue(publishedTabsPayload);
  startStashScanMock.mockResolvedValue({
    scanId: 'scan-2',
    status: 'running',
    startedAt: '2026-03-21T12:01:00Z',
    accountName: 'qa-exile',
    league: 'Mirage',
    realm: 'pc',
  });
  getStashItemHistoryMock.mockResolvedValue({
    fingerprint: 'sig:item-1',
    item: {
      name: 'Grim Bane',
      itemClass: 'Helmet',
      rarity: 'rare',
      iconUrl: 'https://web.poecdn.com/item.png',
    },
    history: [
      {
        scanId: 'scan-2',
        pricedAt: '2026-03-21T12:00:00Z',
        predictedValue: 45,
        listedPrice: 40,
        currency: 'chaos',
        confidence: 82,
        interval: { p10: 39, p90: 51 },
        priceRecommendationEligible: true,
        estimateTrust: 'normal',
        estimateWarning: '',
        fallbackReason: '',
      },
    ],
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.useRealTimers();
});

describe('StashViewerTab', () => {
  test('keeps rendering the last published stash while a new scan is running', async () => {
    getStashScanStatusMock.mockResolvedValue({
      status: 'running',
      activeScanId: 'scan-2',
      publishedScanId: 'scan-1',
      startedAt: '2026-03-21T12:01:00Z',
      updatedAt: '2026-03-21T12:02:00Z',
      publishedAt: null,
      progress: { tabsTotal: 8, tabsProcessed: 3, itemsTotal: 120, itemsProcessed: 44 },
      error: null,
    });

    render(<StashViewerTab />);

    expect(await screen.findByTestId('stash-panel-grid')).toBeInTheDocument();
    vi.useFakeTimers();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /scan/i }));
      await Promise.resolve();
      await Promise.resolve();
    });

    await act(async () => {
      vi.advanceTimersByTime(1600);
      await Promise.resolve();
    });

    expect(screen.getByTestId('stash-panel-grid')).toBeInTheDocument();
    expect(getStashScanStatusMock).toHaveBeenCalled();
  });

  test('renders tabs in backend order and opens history details for an item', async () => {
    render(<StashViewerTab />);

    await waitFor(() => {
      const tabs = screen.getAllByTestId(/stash-tab-/);
      expect(tabs[0]).toHaveTextContent('Currency');
      expect(tabs[1]).toHaveTextContent('Dump');
    });

    fireEvent.click(screen.getByTestId('stash-item-history-sig:item-1'));

    await waitFor(() => {
      expect(getStashItemHistoryMock).toHaveBeenCalledWith('sig:item-1');
    });

    expect(await screen.findByText('Grim Bane')).toBeInTheDocument();
    expect(screen.getByText('Helmet')).toBeInTheDocument();
  });

  test('starts a scan, polls status, and refreshes once the scan publishes', async () => {
    getStashScanStatusMock
      .mockResolvedValueOnce({
        status: 'running',
        activeScanId: 'scan-2',
        publishedScanId: 'scan-1',
        startedAt: '2026-03-21T12:01:00Z',
        updatedAt: '2026-03-21T12:02:00Z',
        publishedAt: null,
        progress: { tabsTotal: 8, tabsProcessed: 4, itemsTotal: 120, itemsProcessed: 60 },
        error: null,
      })
      .mockResolvedValueOnce({
        status: 'published',
        activeScanId: null,
        publishedScanId: 'scan-2',
        startedAt: '2026-03-21T12:01:00Z',
        updatedAt: '2026-03-21T12:03:00Z',
        publishedAt: '2026-03-21T12:03:00Z',
        progress: { tabsTotal: 8, tabsProcessed: 8, itemsTotal: 120, itemsProcessed: 120 },
        error: null,
      });
    getStashTabsMock
      .mockResolvedValueOnce(publishedTabsPayload)
      .mockResolvedValueOnce({
        ...publishedTabsPayload,
        scanId: 'scan-2',
        publishedAt: '2026-03-21T12:03:00Z',
      });

    render(<StashViewerTab />);
    expect(await screen.findByTestId('stash-panel-grid')).toBeInTheDocument();
    vi.useFakeTimers();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /scan/i }));
      await Promise.resolve();
      await Promise.resolve();
    });

    await act(async () => {
      vi.advanceTimersByTime(1600);
      await Promise.resolve();
      vi.advanceTimersByTime(1600);
      await Promise.resolve();
    });

    expect(getStashTabsMock).toHaveBeenCalledTimes(2);
  });
});
