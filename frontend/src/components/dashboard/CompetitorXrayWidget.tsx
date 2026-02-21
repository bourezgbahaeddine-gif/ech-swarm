'use client';

import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Radar } from 'lucide-react';

import { competitorXrayApi } from '@/lib/api';
import { formatRelativeTime, truncate } from '@/lib/utils';

export default function CompetitorXrayWidget() {
    const { data, isLoading } = useQuery({
        queryKey: ['dashboard-xray-widget'],
        queryFn: () => competitorXrayApi.latest({ limit: 5, status_filter: 'new' }),
        refetchInterval: 20000,
    });
    const items = data?.data || [];

    return (
        <div className="rounded-2xl border app-surface p-4">
            <div className="flex items-center gap-2 mb-3">
                <Radar className="w-4 h-4 text-[var(--semantic-info)]" />
                <h3 className="text-sm font-semibold text-[var(--text-primary)]">كشاف المنافسين</h3>
            </div>
            {isLoading ? (
                <p className="text-xs app-text-muted">جاري التحميل...</p>
            ) : items.length === 0 ? (
                <p className="text-xs app-text-muted">لا توجد فجوات جديدة الآن.</p>
            ) : (
                <div className="space-y-2">
                    {items.map((item) => (
                        <a
                            key={item.id}
                            href="/competitor-xray"
                            className="block rounded-xl border border-white/10 bg-white/[0.03] px-2 py-2 hover:bg-white/[0.05]"
                        >
                            <div className="flex items-center justify-between gap-2">
                                <p className="text-xs text-[var(--text-primary)] line-clamp-1">{truncate(item.competitor_title, 70)}</p>
                                <span className="text-[10px] text-amber-300">{item.priority_score.toFixed(1)}</span>
                            </div>
                            <p className="text-[10px] app-text-muted mt-1 inline-flex items-center gap-1">
                                <AlertTriangle className="w-3 h-3" />
                                {item.published_at ? formatRelativeTime(item.published_at) : 'بدون وقت'} • زاوية جديدة متاحة
                            </p>
                        </a>
                    ))}
                </div>
            )}
        </div>
    );
}
