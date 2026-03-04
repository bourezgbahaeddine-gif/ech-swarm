'use client';

import { useQuery } from '@tanstack/react-query';
import { Clock3, ShieldAlert } from 'lucide-react';

import { dashboardApi } from '@/lib/api';

function formatAgeHours(value: number | null | undefined): string {
    if (value === null || value === undefined) return '—';
    if (value < 1) return `${Math.max(1, Math.round(value * 60))}د`;
    if (value < 24) return `${value.toFixed(1)}س`;
    return `${(value / 24).toFixed(1)}ي`;
}

function formatPercent(value: number): string {
    return `${(value * 100).toFixed(1)}%`;
}

export default function TimeIntegrityWidget() {
    const { data, isLoading } = useQuery({
        queryKey: ['dashboard-time-integrity'],
        queryFn: () => dashboardApi.timeIntegrity(),
        refetchInterval: 20000,
        refetchOnWindowFocus: true,
    });

    const payload = data?.data;
    const topMissingSources = payload?.top_missing_timestamp_sources || [];
    const topSkipReasons = payload?.skip_reasons?.slice(0, 4) || [];
    const topStaleSources = payload?.top_stale_sources || [];
    const watchlistItems = payload?.source_health_watchlist?.items?.slice(0, 4) || [];

    return (
        <div className="rounded-2xl border app-surface p-4">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4 text-[var(--semantic-warning)]" />
                    Time Integrity
                </h3>
                <a href="/sources" className="text-xs text-[var(--accent-blue)] hover:underline">المصادر</a>
            </div>

            {isLoading && <p className="text-xs app-text-muted">جارِ تحميل مؤشرات الزمن...</p>}

            {!isLoading && payload && (
                <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                        <div className="rounded-lg app-surface-soft border px-2 py-1.5">
                            <p className="text-[11px] app-text-muted">أقدم مرشح</p>
                            <p className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-1">
                                <Clock3 className="w-3 h-3 text-[var(--semantic-warning)]" />
                                {formatAgeHours(payload.oldest_candidate_age_hours)}
                            </p>
                        </div>
                        <div className="rounded-lg app-surface-soft border px-2 py-1.5">
                            <p className="text-[11px] app-text-muted">أقدم انتظار رئيس التحرير</p>
                            <p className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-1">
                                <Clock3 className="w-3 h-3 text-[var(--semantic-warning)]" />
                                {formatAgeHours(payload.oldest_ready_for_chief_age_hours)}
                            </p>
                        </div>
                    </div>

                    <div className="rounded-lg app-surface-soft border px-2 py-1.5">
                        <p className="text-[11px] app-text-muted">Stale غير منشور</p>
                        <p className="text-sm font-semibold text-[var(--text-primary)]">
                            {payload.stale_non_published_total}
                        </p>
                    </div>

                    <div className="rounded-lg app-surface-soft border px-2 py-1.5">
                        <p className="text-[11px] app-text-muted mb-1">Top أسباب الرفض الزمني</p>
                        <div className="space-y-1">
                            {topSkipReasons.length === 0 && <p className="text-xs app-text-muted">لا توجد بيانات بعد.</p>}
                            {topSkipReasons.map((item) => (
                                <div key={item.reason} className="flex items-center justify-between text-xs">
                                    <span className="text-[var(--text-primary)] line-clamp-1">{item.reason}</span>
                                    <span className="app-text-muted">{item.count}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="rounded-lg app-surface-soft border px-2 py-1.5">
                        <p className="text-[11px] app-text-muted mb-1">Top Sources (Stale)</p>
                        <div className="space-y-1">
                            {topStaleSources.length === 0 && <p className="text-xs app-text-muted">No data yet.</p>}
                            {topStaleSources.slice(0, 4).map((item) => (
                                <div key={item.source} className="flex items-center justify-between text-xs">
                                    <span className="text-[var(--text-primary)] line-clamp-1">{item.source}</span>
                                    <span className="app-text-muted">{item.count}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="rounded-lg app-surface-soft border px-2 py-1.5">
                        <p className="text-[11px] app-text-muted mb-1">Source Health Watchlist</p>
                        <div className="space-y-1">
                            {watchlistItems.length === 0 && <p className="text-xs app-text-muted">No risky sources detected.</p>}
                            {watchlistItems.map((item) => (
                                <div key={item.source_key} className="text-xs">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[var(--text-primary)] line-clamp-1">{item.name}</span>
                                        <span className="app-text-muted">S{item.health_score.toFixed(1)}</span>
                                    </div>
                                    <div className="app-text-muted line-clamp-1">
                                        {(item.actions || []).join(', ') || item.health_band}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="rounded-lg app-surface-soft border px-2 py-1.5">
                        <p className="text-[11px] app-text-muted mb-1">Top مصادر Missing Timestamp</p>
                        <div className="space-y-1">
                            {topMissingSources.length === 0 && <p className="text-xs app-text-muted">لا توجد بيانات بعد.</p>}
                            {topMissingSources.slice(0, 4).map((item) => (
                                <div key={item.source} className="flex items-center justify-between text-xs">
                                    <span className="text-[var(--text-primary)] line-clamp-1">{item.source}</span>
                                    <span className="app-text-muted">{item.count}</span>
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="rounded-lg app-surface-soft border px-2 py-1.5">
                        <p className="text-[11px] app-text-muted">قبول عبر URL fallback</p>
                        <p className="text-sm font-semibold text-[var(--text-primary)]">
                            {formatPercent(payload.url_date_fallback.acceptance_ratio)}
                        </p>
                    </div>
                </div>
            )}
        </div>
    );
}

