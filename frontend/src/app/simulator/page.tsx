'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, BarChart3, Play, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react';

import { simApi, type SimResult } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatRelativeTime } from '@/lib/utils';

function badgeForPolicy(level: string): string {
    if (level === 'HIGH_RISK') return 'bg-red-500/20 text-red-200 border-red-500/30';
    if (level === 'REVIEW_RECOMMENDED') return 'bg-amber-500/20 text-amber-200 border-amber-500/30';
    return 'bg-emerald-500/20 text-emerald-200 border-emerald-500/30';
}

function labelForPolicy(level: string): string {
    if (level === 'HIGH_RISK') return 'خطر مرتفع';
    if (level === 'REVIEW_RECOMMENDED') return 'مراجعة مطلوبة';
    return 'مخاطر منخفضة';
}

export default function SimulatorPage() {
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canRun = ['director', 'editor_chief', 'journalist'].includes(role);

    const [headline, setHeadline] = useState('');
    const [excerpt, setExcerpt] = useState('');
    const [platform, setPlatform] = useState<'facebook' | 'x'>('facebook');
    const [mode, setMode] = useState<'fast' | 'deep'>('fast');
    const [runId, setRunId] = useState('');

    const runMutation = useMutation({
        mutationFn: () =>
            simApi.run({
                headline: headline.trim(),
                excerpt: excerpt.trim() || undefined,
                platform,
                mode,
            }),
        onSuccess: (res) => {
            setRunId(res.data.run_id);
        },
    });

    const { data: runStatusData } = useQuery({
        queryKey: ['sim-status', runId],
        queryFn: () => simApi.runStatus(runId),
        enabled: !!runId,
        refetchInterval: (q) => {
            const status = q.state.data?.data?.status;
            if (status === 'completed' || status === 'failed') return false;
            return 1600;
        },
    });

    const status = runStatusData?.data?.status;

    const { data: resultData, isFetching: resultLoading } = useQuery({
        queryKey: ['sim-result', runId],
        queryFn: () => simApi.result(runId),
        enabled: !!runId && status === 'completed',
    });
    const result: SimResult | undefined = resultData?.data;

    const { data: historyData } = useQuery({
        queryKey: ['sim-history'],
        queryFn: () => simApi.history({ limit: 12 }),
    });
    const history = historyData?.data?.items || [];

    const riskEntries = useMemo(() => Object.entries(result?.breakdown?.risk || {}), [result?.breakdown?.risk]);
    const viralityEntries = useMemo(() => Object.entries(result?.breakdown?.virality || {}), [result?.breakdown?.virality]);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white">محاكي الجمهور</h1>
                <p className="text-sm text-gray-400 mt-1">
                    اختبار تفاعل الجمهور قبل الاعتماد النهائي: مخاطر المحتوى، قابلية الانتشار، ونصائح تحسين العنوان.
                </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                <input
                    value={headline}
                    onChange={(e) => setHeadline(e.target.value)}
                    placeholder="أدخل عنوان الخبر"
                    className="w-full h-12 px-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-gray-500"
                    dir="rtl"
                />
                <textarea
                    value={excerpt}
                    onChange={(e) => setExcerpt(e.target.value)}
                    placeholder="مقتطف من الخبر (اختياري، يُحسن دقة التقييم)"
                    className="w-full min-h-[120px] px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-gray-500"
                    dir="rtl"
                />
                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                    <select
                        value={platform}
                        onChange={(e) => setPlatform(e.target.value as 'facebook' | 'x')}
                        className="h-11 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white"
                    >
                        <option value="facebook" className="bg-gray-900">Facebook</option>
                        <option value="x" className="bg-gray-900">X</option>
                    </select>
                    <select
                        value={mode}
                        onChange={(e) => setMode(e.target.value as 'fast' | 'deep')}
                        className="h-11 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white"
                    >
                        <option value="fast" className="bg-gray-900">Fast</option>
                        <option value="deep" className="bg-gray-900">Deep</option>
                    </select>
                    <button
                        onClick={() => runMutation.mutate()}
                        disabled={!canRun || runMutation.isPending || headline.trim().length < 6}
                        className="md:col-span-2 h-11 rounded-xl border border-emerald-500/30 bg-emerald-500/20 text-emerald-200 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                        {runMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                        تشغيل المحاكاة
                    </button>
                </div>
                {status && (
                    <p className="text-xs text-gray-400">
                        الحالة: <span className="text-gray-200">{status}</span>
                    </p>
                )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <p className="text-xs text-gray-400 mb-1">Risk Score</p>
                    <p className="text-3xl font-bold text-red-200">{result ? result.risk_score.toFixed(1) : '--'}</p>
                    <p className="text-xs text-gray-500 mt-1">من 10</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <p className="text-xs text-gray-400 mb-1">Virality Score</p>
                    <p className="text-3xl font-bold text-cyan-200">{result ? result.virality_score.toFixed(1) : '--'}</p>
                    <p className="text-xs text-gray-500 mt-1">من 10</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <p className="text-xs text-gray-400 mb-1">قرار الحوكمة</p>
                    <div className={`inline-flex rounded-lg border px-2 py-1 text-sm ${badgeForPolicy(result?.policy_level || 'LOW_RISK')}`}>
                        {labelForPolicy(result?.policy_level || 'LOW_RISK')}
                    </div>
                    <p className="text-xs text-gray-500 mt-2">
                        موثوقية القياس: <span className="text-gray-300">{result ? `${result.confidence_score.toFixed(1)}%` : '--'}</span>
                    </p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <ShieldAlert className="w-4 h-4 text-red-300" />
                        <h3 className="text-sm text-white font-semibold">تفكيك المخاطر</h3>
                    </div>
                    <div className="space-y-1 text-sm">
                        {riskEntries.length ? riskEntries.map(([k, v]) => (
                            <p key={k} className="text-gray-200">{k}: <span className="font-semibold">{(v * 100).toFixed(1)}%</span></p>
                        )) : <p className="text-gray-500">لا توجد بيانات بعد.</p>}
                    </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <BarChart3 className="w-4 h-4 text-cyan-300" />
                        <h3 className="text-sm text-white font-semibold">تفكيك الانتشار</h3>
                    </div>
                    <div className="space-y-1 text-sm">
                        {viralityEntries.length ? viralityEntries.map(([k, v]) => (
                            <p key={k} className="text-gray-200">{k}: <span className="font-semibold">{(v * 100).toFixed(1)}%</span></p>
                        )) : <p className="text-gray-500">لا توجد بيانات بعد.</p>}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <Sparkles className="w-4 h-4 text-emerald-300" />
                        <h3 className="text-sm text-white font-semibold">نصائح التحرير</h3>
                    </div>
                    {result ? (
                        <div className="space-y-2 text-sm text-gray-200">
                            <p>{result.advice?.summary || '—'}</p>
                            {(result.advice?.improvements || []).map((fix, idx) => (
                                <p key={`${fix}-${idx}`}>• {fix}</p>
                            ))}
                            {(result.advice?.alternative_headlines || []).length > 0 && (
                                <div className="pt-1">
                                    <p className="text-xs text-gray-400 mb-1">بدائل العنوان:</p>
                                    {(result.advice?.alternative_headlines || []).map((h, idx) => (
                                        <div key={`${h}-${idx}`} className="rounded-lg border border-white/10 bg-white/5 p-2 mb-1">{h}</div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ) : (
                        <p className="text-gray-500 text-sm">شغّل المحاكاة لعرض الاقتراحات.</p>
                    )}
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <div className="flex items-center gap-2 mb-3">
                        <AlertTriangle className="w-4 h-4 text-amber-300" />
                        <h3 className="text-sm text-white font-semibold">تعليقات الشخصيات</h3>
                    </div>
                    {result ? (
                        <div className="space-y-2 text-sm">
                            {result.reactions.map((r, idx) => (
                                <div key={`${r.persona_id}-${idx}`} className="rounded-lg border border-white/10 bg-white/5 p-2">
                                    <p className="text-gray-300 text-xs mb-1">{r.persona_label || r.persona_id} - {r.sentiment}</p>
                                    <p className="text-gray-100">{r.comment}</p>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="text-gray-500 text-sm">لا توجد تعليقات بعد.</p>
                    )}
                </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm text-white font-semibold">آخر تشغيلات المحاكي</h3>
                    <button
                        onClick={() => queryClient.invalidateQueries({ queryKey: ['sim-history'] })}
                        className="text-xs rounded-lg border border-white/10 bg-white/5 px-2 py-1 text-gray-300"
                    >
                        تحديث
                    </button>
                </div>
                <div className="space-y-2">
                    {history.length ? history.map((item) => (
                        <div key={item.run_id} className="rounded-lg border border-white/10 bg-white/5 p-2 text-sm">
                            <div className="flex items-center justify-between gap-3">
                                <p className="text-gray-100 line-clamp-1">{item.headline}</p>
                                <span className={`text-[11px] px-2 py-0.5 rounded border ${badgeForPolicy(item.policy_level || 'LOW_RISK')}`}>
                                    {labelForPolicy(item.policy_level || 'LOW_RISK')}
                                </span>
                            </div>
                            <p className="text-xs text-gray-400 mt-1">
                                {item.risk_score != null ? `Risk ${item.risk_score.toFixed(1)} / Virality ${item.virality_score?.toFixed(1)}` : 'قيد التنفيذ'} • {item.created_at ? formatRelativeTime(item.created_at) : ''}
                            </p>
                        </div>
                    )) : (
                        <p className="text-sm text-gray-500">لا توجد تشغيلات حتى الآن.</p>
                    )}
                </div>
            </div>

            {(resultLoading || runMutation.isPending) && (
                <p className="text-xs text-gray-500">يتم تجهيز النتائج...</p>
            )}
        </div>
    );
}
