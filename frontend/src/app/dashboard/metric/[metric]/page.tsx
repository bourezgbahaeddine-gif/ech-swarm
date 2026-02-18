'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
    dashboardApi,
    newsApi,
    sourcesApi,
    type ArticleBrief,
    type PipelineRun,
    type Source,
} from '@/lib/api';
import { cn, formatRelativeTime, getCategoryLabel, getStatusColor, truncate } from '@/lib/utils';
import { ArrowRight, Clock3, Cpu, ExternalLink, Newspaper, Rss, Sparkles, Timer } from 'lucide-react';

type MetricKind = 'news' | 'sources' | 'ai' | 'processing';

type MetricConfig = {
    title: string;
    description: string;
    kind: MetricKind;
    status?: string;
    isBreaking?: boolean;
    todayOnly?: boolean;
};

const METRICS: Record<string, MetricConfig> = {
    'total-articles': {
        title: 'إجمالي الأخبار',
        description: 'آخر الأخبار المسجلة في غرفة الأخبار.',
        kind: 'news',
    },
    'today-articles': {
        title: 'أخبار اليوم',
        description: 'الأخبار التي دخلت المنظومة اليوم.',
        kind: 'news',
        todayOnly: true,
    },
    'pending-review': {
        title: 'بانتظار المراجعة',
        description: 'الأخبار المرشحة التي تنتظر قرار التحرير.',
        kind: 'news',
        status: 'candidate',
    },
    approved: {
        title: 'تمت الموافقة',
        description: 'الأخبار التي حصلت على موافقة تحريرية.',
        kind: 'news',
        status: 'approved',
    },
    rejected: {
        title: 'تم الرفض',
        description: 'الأخبار المرفوضة من فريق التحرير.',
        kind: 'news',
        status: 'rejected',
    },
    published: {
        title: 'تم النشر',
        description: 'الأخبار المنشورة فعليًا.',
        kind: 'news',
        status: 'published',
    },
    'breaking-news': {
        title: 'الأخبار العاجلة',
        description: 'أخبار عاجلة نشطة تحتاج متابعة فورية.',
        kind: 'news',
        isBreaking: true,
    },
    'sources-active': {
        title: 'المصادر النشطة',
        description: 'حالة المصادر النشطة والمتوقفة.',
        kind: 'sources',
    },
    'ai-calls': {
        title: 'استدعاءات AI اليوم',
        description: 'استخدام الوكلاء الذكية وسجل التشغيل.',
        kind: 'ai',
    },
    'avg-processing': {
        title: 'متوسط المعالجة',
        description: 'مؤشرات زمن التشغيل عبر آخر العمليات.',
        kind: 'processing',
    },
};

function isTodayIso(dateValue: string): boolean {
    const d = new Date(dateValue);
    if (Number.isNaN(d.getTime())) return false;
    const now = new Date();
    return (
        d.getUTCFullYear() === now.getUTCFullYear() &&
        d.getUTCMonth() === now.getUTCMonth() &&
        d.getUTCDate() === now.getUTCDate()
    );
}

function pipelineDurationMs(run: PipelineRun): number | null {
    if (!run.finished_at) return null;
    const start = new Date(run.started_at).getTime();
    const end = new Date(run.finished_at).getTime();
    if (Number.isNaN(start) || Number.isNaN(end) || end < start) return null;
    return end - start;
}

export default function DashboardMetricPage() {
    const params = useParams<{ metric: string }>();
    const metricSlug = params?.metric || '';
    const metric = METRICS[metricSlug];

    const { data: statsData } = useQuery({
        queryKey: ['dashboard-stats'],
        queryFn: () => dashboardApi.stats(),
        staleTime: 30000,
    });

    const { data: newsData, isLoading: newsLoading } = useQuery({
        queryKey: ['dashboard-metric-news', metricSlug, metric?.status, metric?.isBreaking],
        queryFn: () =>
            newsApi.list({
                page: 1,
                per_page: 80,
                sort_by: 'crawled_at',
                status: metric?.status,
                is_breaking: metric?.isBreaking,
            }),
        enabled: metric?.kind === 'news',
    });

    const { data: sourcesData, isLoading: sourcesLoading } = useQuery({
        queryKey: ['dashboard-metric-sources', metricSlug],
        queryFn: () => sourcesApi.list(),
        enabled: metric?.kind === 'sources',
    });

    const { data: pipelineData, isLoading: pipelineLoading } = useQuery({
        queryKey: ['dashboard-metric-pipeline', metricSlug],
        queryFn: () => dashboardApi.pipelineRuns(30),
        enabled: metric?.kind === 'ai' || metric?.kind === 'processing',
    });

    const articles = useMemo(() => {
        const items = (newsData?.data?.items || []) as ArticleBrief[];
        if (!metric?.todayOnly) return items;
        return items.filter((item) => isTodayIso(item.crawled_at || item.created_at));
    }, [newsData?.data?.items, metric?.todayOnly]);

    const sources = useMemo(
        () => (sourcesData?.data || []) as Source[],
        [sourcesData?.data],
    );
    const activeSources = useMemo(() => sources.filter((source) => source.enabled), [sources]);
    const inactiveSources = useMemo(() => sources.filter((source) => !source.enabled), [sources]);

    const runs = useMemo(
        () => (pipelineData?.data || []) as PipelineRun[],
        [pipelineData?.data],
    );
    const runsWithDuration = useMemo(
        () => runs.map((run) => ({ ...run, durationMs: pipelineDurationMs(run) })),
        [runs],
    );

    const totalAiCalls = useMemo(
        () => runs.reduce((sum, run) => sum + (run.ai_calls || 0), 0),
        [runs],
    );

    if (!metric) {
        return (
            <div className="space-y-4">
                <h1 className="text-xl font-bold text-white">الخانة غير موجودة</h1>
                <p className="text-sm text-gray-400">هذه الخانة غير معرفة في لوحة المؤشرات.</p>
                <Link href="/" className="inline-flex items-center gap-2 text-sm text-emerald-300 hover:text-emerald-200">
                    <ArrowRight className="w-4 h-4" /> العودة إلى لوحة القيادة
                </Link>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white">{metric.title}</h1>
                    <p className="text-sm text-gray-400 mt-1">{metric.description}</p>
                </div>
                <Link
                    href="/"
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-gray-200 hover:text-white"
                >
                    <ArrowRight className="w-4 h-4" /> العودة للوحة
                </Link>
            </div>

            {metric.kind === 'news' && (
                <div className="space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 text-sm text-gray-300">
                        إجمالي العناصر المعروضة: <span className="text-white font-semibold">{articles.length}</span>
                        {metric.todayOnly && <span className="text-cyan-300 mr-2">(تصفية اليوم)</span>}
                    </div>

                    {newsLoading ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 text-center text-gray-400">جاري التحميل...</div>
                    ) : articles.length === 0 ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 text-center text-gray-400">لا توجد نتائج حالياً.</div>
                    ) : (
                        <div className="grid grid-cols-1 gap-3">
                            {articles.map((article) => (
                                <div key={article.id} className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="space-y-2" dir="rtl">
                                            <h3 className="text-sm font-semibold text-white">
                                                {article.title_ar || article.original_title}
                                            </h3>
                                            {article.summary && (
                                                <p className="text-xs text-gray-400">{truncate(article.summary, 220)}</p>
                                            )}
                                            <div className="flex flex-wrap items-center gap-2 text-[11px]">
                                                <span className={cn('px-2 py-0.5 rounded-md border', getStatusColor((article.status || '').toLowerCase()))}>
                                                    {article.status}
                                                </span>
                                                <span className="px-2 py-0.5 rounded-md border border-white/10 bg-white/5 text-gray-300">
                                                    {getCategoryLabel(article.category)}
                                                </span>
                                                <span className="text-gray-500">{formatRelativeTime(article.crawled_at || article.created_at)}</span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2 shrink-0">
                                            <a
                                                href={`/news/${article.id}`}
                                                className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/15 px-3 py-1.5 text-xs text-emerald-200"
                                            >
                                                <Newspaper className="w-3.5 h-3.5" /> التفاصيل
                                            </a>
                                            {article.original_url && (
                                                <a
                                                    href={article.original_url}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 text-xs text-gray-300"
                                                >
                                                    <ExternalLink className="w-3.5 h-3.5" /> المصدر
                                                </a>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {metric.kind === 'sources' && (
                <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 p-4">
                            <p className="text-xs text-emerald-300">المصادر النشطة</p>
                            <p className="text-3xl font-bold text-white">{activeSources.length.toLocaleString('ar-DZ')}</p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                            <p className="text-xs text-gray-300">إجمالي المصادر</p>
                            <p className="text-3xl font-bold text-white">{sources.length.toLocaleString('ar-DZ')}</p>
                        </div>
                    </div>

                    {sourcesLoading ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 text-center text-gray-400">جاري التحميل...</div>
                    ) : (
                        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                                <h2 className="text-sm font-semibold text-white mb-3">مصادر نشطة</h2>
                                <div className="space-y-2 max-h-[420px] overflow-auto">
                                    {activeSources.map((source) => (
                                        <div key={source.id} className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-gray-200" dir="rtl">
                                            <div className="flex items-center justify-between gap-2">
                                                <span className="font-semibold text-white">{source.name}</span>
                                                <span className="inline-flex items-center gap-1 text-emerald-300">
                                                    <Rss className="w-3.5 h-3.5" /> نشط
                                                </span>
                                            </div>
                                            <p className="text-gray-400 mt-1">آخر جلب: {formatRelativeTime(source.last_fetched_at)}</p>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                                <h2 className="text-sm font-semibold text-white mb-3">مصادر متوقفة</h2>
                                <div className="space-y-2 max-h-[420px] overflow-auto">
                                    {inactiveSources.length === 0 ? (
                                        <p className="text-xs text-gray-500">لا توجد مصادر متوقفة.</p>
                                    ) : (
                                        inactiveSources.map((source) => (
                                            <div key={source.id} className="rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-gray-300" dir="rtl">
                                                <div className="flex items-center justify-between gap-2">
                                                    <span className="font-semibold text-white">{source.name}</span>
                                                    <span className="text-gray-500">متوقف</span>
                                                </div>
                                                <p className="text-gray-500 mt-1">الأخطاء: {source.error_count}</p>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {metric.kind === 'ai' && (
                <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div className="rounded-2xl border border-indigo-500/30 bg-indigo-500/10 p-4">
                            <p className="text-xs text-indigo-300">استدعاءات AI اليوم</p>
                            <p className="text-3xl font-bold text-white">{(statsData?.data?.ai_calls_today || 0).toLocaleString('ar-DZ')}</p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                            <p className="text-xs text-gray-300">استدعاءات آخر 30 تشغيل</p>
                            <p className="text-3xl font-bold text-white">{totalAiCalls.toLocaleString('ar-DZ')}</p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                            <p className="text-xs text-gray-300">عدد التشغيلات</p>
                            <p className="text-3xl font-bold text-white">{runs.length.toLocaleString('ar-DZ')}</p>
                        </div>
                    </div>

                    {pipelineLoading ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 text-center text-gray-400">جاري التحميل...</div>
                    ) : (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 overflow-hidden">
                            <div className="grid grid-cols-5 gap-2 px-4 py-3 text-xs text-gray-400 border-b border-white/10">
                                <span>النوع</span>
                                <span>الحالة</span>
                                <span>العناصر</span>
                                <span>AI Calls</span>
                                <span>الوقت</span>
                            </div>
                            <div className="max-h-[460px] overflow-auto">
                                {runsWithDuration.map((run) => (
                                    <div key={run.id} className="grid grid-cols-5 gap-2 px-4 py-3 text-xs text-gray-200 border-b border-white/5">
                                        <span className="font-medium">{run.run_type}</span>
                                        <span>{run.status}</span>
                                        <span>{run.total_items}</span>
                                        <span className="inline-flex items-center gap-1"><Sparkles className="w-3.5 h-3.5 text-indigo-300" />{run.ai_calls}</span>
                                        <span>{formatRelativeTime(run.started_at)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {metric.kind === 'processing' && (
                <div className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        <div className="rounded-2xl border border-teal-500/30 bg-teal-500/10 p-4">
                            <p className="text-xs text-teal-300">متوسط المعالجة</p>
                            <p className="text-3xl font-bold text-white">
                                {statsData?.data?.avg_processing_ms ? `${Math.round(statsData.data.avg_processing_ms)}ms` : '—'}
                            </p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                            <p className="text-xs text-gray-300">تشغيلات مكتملة</p>
                            <p className="text-3xl font-bold text-white">
                                {runsWithDuration.filter((run) => run.durationMs !== null).length.toLocaleString('ar-DZ')}
                            </p>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                            <p className="text-xs text-gray-300">أطول تشغيل</p>
                            <p className="text-3xl font-bold text-white">
                                {(() => {
                                    const maxDuration = Math.max(...runsWithDuration.map((run) => run.durationMs || 0), 0);
                                    return maxDuration > 0 ? `${Math.round(maxDuration / 1000)}s` : '—';
                                })()}
                            </p>
                        </div>
                    </div>

                    {pipelineLoading ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 text-center text-gray-400">جاري التحميل...</div>
                    ) : (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 overflow-hidden">
                            <div className="grid grid-cols-5 gap-2 px-4 py-3 text-xs text-gray-400 border-b border-white/10">
                                <span>النوع</span>
                                <span>البداية</span>
                                <span>النهاية</span>
                                <span>المدة</span>
                                <span>الأخطاء</span>
                            </div>
                            <div className="max-h-[460px] overflow-auto">
                                {runsWithDuration.map((run) => (
                                    <div key={run.id} className="grid grid-cols-5 gap-2 px-4 py-3 text-xs text-gray-200 border-b border-white/5">
                                        <span className="inline-flex items-center gap-1"><Cpu className="w-3.5 h-3.5 text-teal-300" />{run.run_type}</span>
                                        <span>{formatRelativeTime(run.started_at)}</span>
                                        <span>{run.finished_at ? formatRelativeTime(run.finished_at) : 'قيد التشغيل'}</span>
                                        <span className="inline-flex items-center gap-1"><Timer className="w-3.5 h-3.5 text-teal-300" />{run.durationMs !== null ? `${Math.round(run.durationMs / 1000)}s` : '—'}</span>
                                        <span className={run.errors > 0 ? 'text-red-300' : 'text-emerald-300'}>{run.errors}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}

            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 text-xs text-gray-400" dir="rtl">
                <p className="inline-flex items-center gap-2"><Clock3 className="w-4 h-4" /> هذا العرض مباشر ومحدث تلقائياً حسب بيانات النظام.</p>
            </div>
        </div>
    );
}
