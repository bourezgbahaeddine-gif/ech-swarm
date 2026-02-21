'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { AlertTriangle, Loader2, Play, Radar, RefreshCw, Sparkles } from 'lucide-react';

import { competitorXrayApi, type CompetitorXrayBrief, type CompetitorXrayItem } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatRelativeTime } from '@/lib/utils';

const RUN_ROLES = new Set(['director', 'editor_chief', 'journalist', 'social_media', 'print_editor']);
const MANAGE_ROLES = new Set(['director', 'editor_chief']);

function getError(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) return detail;
    }
    return fallback;
}

export default function CompetitorXrayPage() {
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canRun = RUN_ROLES.has(role);
    const canManage = MANAGE_ROLES.has(role);
    const qc = useQueryClient();

    const [limitPerSource, setLimitPerSource] = useState(8);
    const [hoursWindow, setHoursWindow] = useState(48);
    const [runId, setRunId] = useState('');
    const [query, setQuery] = useState('');
    const [brief, setBrief] = useState<CompetitorXrayBrief | null>(null);
    const [error, setError] = useState<string | null>(null);

    const runMutation = useMutation({
        mutationFn: () => competitorXrayApi.run({ limit_per_source: limitPerSource, hours_window: hoursWindow }),
        onSuccess: (res) => {
            setRunId(res.data.run_id);
            setBrief(null);
            setError(null);
            qc.invalidateQueries({ queryKey: ['xray-latest'] });
        },
        onError: (err) => setError(getError(err, 'تعذر تشغيل كشاف المنافسين.')),
    });

    const seedMutation = useMutation({
        mutationFn: () => competitorXrayApi.seedSources(),
        onSuccess: async () => {
            await qc.invalidateQueries({ queryKey: ['xray-sources'] });
        },
        onError: (err) => setError(getError(err, 'تعذر تهيئة مصادر المنافسين.')),
    });

    const statusQuery = useQuery({
        queryKey: ['xray-status', runId],
        queryFn: () => competitorXrayApi.runStatus(runId),
        enabled: !!runId,
        refetchInterval: (q) => {
            const status = q.state.data?.data?.status;
            if (!status || status === 'completed' || status === 'failed') return false;
            return 1500;
        },
    });

    const latestQuery = useQuery({
        queryKey: ['xray-latest', query],
        queryFn: () => competitorXrayApi.latest({ limit: 30, q: query.trim() || undefined }),
        refetchInterval: 20000,
    });

    const sourcesQuery = useQuery({
        queryKey: ['xray-sources'],
        queryFn: () => competitorXrayApi.sources(false),
        enabled: canManage,
    });

    const markUsedMutation = useMutation({
        mutationFn: ({ id, status }: { id: number; status: 'used' | 'ignored' | 'new' }) => competitorXrayApi.markUsed(id, status),
        onSuccess: async () => {
            await qc.invalidateQueries({ queryKey: ['xray-latest'] });
        },
    });

    const briefMutation = useMutation({
        mutationFn: (itemId: number) => competitorXrayApi.brief({ item_id: itemId, tone: 'newsroom' }),
        onSuccess: (res) => {
            setBrief(res.data);
            setError(null);
        },
        onError: (err) => setError(getError(err, 'تعذر إنشاء brief.')),
    });

    const statusLabel = useMemo(() => {
        const st = statusQuery.data?.data?.status;
        if (!st) return 'لم يبدأ';
        if (st === 'queued') return 'قيد الانتظار';
        if (st === 'running') return 'جاري المسح';
        if (st === 'completed') return 'مكتمل';
        if (st === 'failed') return 'فشل';
        return st;
    }, [statusQuery.data?.data?.status]);

    const items: CompetitorXrayItem[] = latestQuery.data?.data || [];

    return (
        <div className="space-y-5 app-theme-shell" dir="rtl">
            <div>
                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                    <Radar className="w-6 h-6 text-cyan-400" />
                    كشاف زوايا المنافسين
                </h1>
                <p className="text-sm text-gray-400 mt-1">يرصد فجوات التغطية عند المنافسين ويقترح زاوية هجومية عملية للشروق.</p>
            </div>

            {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}

            <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                    <input
                        type="number"
                        min={1}
                        max={30}
                        value={limitPerSource}
                        onChange={(e) => setLimitPerSource(Number(e.target.value || 8))}
                        className="h-11 px-3 rounded-xl bg-white/5 border border-white/10 text-white"
                        placeholder="عدد العناصر لكل منافس"
                    />
                    <input
                        type="number"
                        min={6}
                        max={120}
                        value={hoursWindow}
                        onChange={(e) => setHoursWindow(Number(e.target.value || 48))}
                        className="h-11 px-3 rounded-xl bg-white/5 border border-white/10 text-white"
                        placeholder="نافذة الساعات"
                    />
                    <button
                        onClick={() => runMutation.mutate()}
                        disabled={!canRun || runMutation.isPending}
                        className="h-11 rounded-xl border border-emerald-500/30 bg-emerald-500/20 text-emerald-200 disabled:opacity-50 inline-flex items-center justify-center gap-2"
                    >
                        {runMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                        تشغيل الآن
                    </button>
                    {canManage ? (
                        <button
                            onClick={() => seedMutation.mutate()}
                            disabled={seedMutation.isPending}
                            className="h-11 rounded-xl border border-cyan-500/30 bg-cyan-500/20 text-cyan-200 disabled:opacity-50 inline-flex items-center justify-center gap-2"
                        >
                            {seedMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                            تهيئة المصادر
                        </button>
                    ) : (
                        <div className="h-11 rounded-xl border border-white/10 bg-white/5 text-gray-400 flex items-center justify-center text-sm">
                            إدارة المصادر للمدير/رئيس التحرير
                        </div>
                    )}
                </div>

                <div className="text-xs text-gray-400">
                    الحالة: <span className="text-gray-200">{statusLabel}</span>
                    {statusQuery.data?.data ? (
                        <span className="mr-2">• ممسوح: {statusQuery.data.data.total_scanned} • فجوات: {statusQuery.data.data.total_gaps}</span>
                    ) : null}
                </div>
            </section>

            <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                <div className="flex flex-wrap gap-2">
                    <input
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        placeholder="ابحث في العنوان أو الزاوية المقترحة..."
                        className="flex-1 h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-gray-500"
                    />
                    <button
                        onClick={() => qc.invalidateQueries({ queryKey: ['xray-latest'] })}
                        className="h-10 px-3 rounded-xl border border-white/10 bg-white/5 text-gray-200 text-sm"
                    >
                        تحديث
                    </button>
                </div>

                <div className="space-y-2">
                    {items.length === 0 ? (
                        <p className="text-sm text-gray-500">لا توجد فجوات حالياً.</p>
                    ) : (
                        items.map((item) => (
                            <div key={item.id} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                                <div className="flex items-start justify-between gap-2">
                                    <a href={item.competitor_url} target="_blank" rel="noreferrer" className="text-sm text-cyan-300 hover:underline line-clamp-1">
                                        {item.competitor_title}
                                    </a>
                                    <span className="text-xs text-amber-300">أولوية {item.priority_score.toFixed(1)}</span>
                                </div>
                                <p className="text-xs text-gray-400 mt-1">
                                    {item.published_at ? formatRelativeTime(item.published_at) : 'تاريخ غير متاح'} • الحالة: {item.status}
                                </p>
                                {item.angle_title ? <p className="text-sm text-emerald-200 mt-2">{item.angle_title}</p> : null}
                                {item.angle_rationale ? <p className="text-xs text-gray-300 mt-1 line-clamp-3">{item.angle_rationale}</p> : null}
                                {(item.angle_questions_json || []).length > 0 ? (
                                    <div className="mt-2 space-y-1">
                                        {(item.angle_questions_json || []).slice(0, 3).map((qText, idx) => (
                                            <p key={`${item.id}-q-${idx}`} className="text-xs text-gray-200">• {qText}</p>
                                        ))}
                                    </div>
                                ) : null}
                                <div className="mt-3 flex flex-wrap gap-2">
                                    <button
                                        onClick={() => markUsedMutation.mutate({ id: item.id, status: 'used' })}
                                        className="px-2 py-1 rounded-lg border border-emerald-500/30 bg-emerald-500/15 text-emerald-200 text-xs"
                                    >
                                        تم الاعتماد
                                    </button>
                                    <button
                                        onClick={() => markUsedMutation.mutate({ id: item.id, status: 'ignored' })}
                                        className="px-2 py-1 rounded-lg border border-red-500/30 bg-red-500/15 text-red-200 text-xs"
                                    >
                                        تجاهل
                                    </button>
                                    <button
                                        onClick={() => briefMutation.mutate(item.id)}
                                        className="px-2 py-1 rounded-lg border border-cyan-500/30 bg-cyan-500/15 text-cyan-200 text-xs inline-flex items-center gap-1"
                                    >
                                        <Sparkles className="w-3.5 h-3.5" />
                                        توليد Brief
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </section>

            {brief ? (
                <section className="rounded-2xl border border-cyan-500/30 bg-cyan-500/10 p-4 space-y-2">
                    <h2 className="text-sm text-cyan-100 font-semibold inline-flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4" />
                        Brief جاهز للصحفي
                    </h2>
                    <p className="text-sm text-white">{brief.title}</p>
                    <p className="text-sm text-cyan-100">{brief.counter_angle}</p>
                    <p className="text-xs text-cyan-200">{brief.why_it_wins}</p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="rounded-xl border border-white/20 bg-black/20 p-3">
                            <p className="text-xs text-gray-400 mb-2">خطة التنفيذ</p>
                            {brief.newsroom_plan.map((s, idx) => (
                                <p key={`${s}-${idx}`} className="text-xs text-gray-100 mb-1">• {s}</p>
                            ))}
                        </div>
                        <div className="rounded-xl border border-white/20 bg-black/20 p-3">
                            <p className="text-xs text-gray-400 mb-2">مصادر البداية</p>
                            {brief.starter_sources.map((s, idx) => (
                                <p key={`${s}-${idx}`} className="text-xs text-gray-100 mb-1">• {s}</p>
                            ))}
                        </div>
                    </div>
                </section>
            ) : null}

            {canManage && (
                <section className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <h2 className="text-sm text-white font-semibold mb-3">مصادر المنافسين النشطة</h2>
                    <div className="space-y-2">
                        {(sourcesQuery.data?.data || []).map((source) => (
                            <div key={source.id} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs">
                                <div className="flex items-center justify-between gap-2">
                                    <span className="text-gray-100">{source.name}</span>
                                    <span className={source.enabled ? 'text-emerald-300' : 'text-red-300'}>
                                        {source.enabled ? 'نشط' : 'موقوف'}
                                    </span>
                                </div>
                                <p className="text-gray-400 mt-1 line-clamp-1">{source.feed_url}</p>
                            </div>
                        ))}
                    </div>
                </section>
            )}
        </div>
    );
}
