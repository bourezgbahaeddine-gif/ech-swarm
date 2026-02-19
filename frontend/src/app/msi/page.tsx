'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, Gauge, Play, RefreshCw } from 'lucide-react';
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { msiApi, type MsiReport } from '@/lib/api';
import { useAuth } from '@/lib/auth';

type Mode = 'daily' | 'weekly';

function levelLabel(level: string): string {
    if (level === 'GREEN') return 'مستقر';
    if (level === 'YELLOW') return 'مراقبة';
    if (level === 'ORANGE') return 'حساس';
    if (level === 'RED') return 'مضطرب';
    return level;
}

function levelColor(level: string): string {
    if (level === 'GREEN') return 'text-emerald-300 border-emerald-500/30 bg-emerald-500/10';
    if (level === 'YELLOW') return 'text-amber-300 border-amber-500/30 bg-amber-500/10';
    if (level === 'ORANGE') return 'text-orange-300 border-orange-500/30 bg-orange-500/10';
    if (level === 'RED') return 'text-red-300 border-red-500/30 bg-red-500/10';
    return 'text-gray-300 border-white/10 bg-white/5';
}

export default function MsiPage() {
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canRun = ['director', 'editor_chief', 'journalist'].includes(role);
    const canManageWatchlist = ['director', 'editor_chief'].includes(role);
    const apiBase = (process.env.NEXT_PUBLIC_API_URL || '/api/v1').replace(/\/$/, '');

    const [profileId, setProfileId] = useState('institution_presidency');
    const [entity, setEntity] = useState('');
    const [mode, setMode] = useState<Mode>('daily');
    const [runId, setRunId] = useState('');
    const [liveEvents, setLiveEvents] = useState<string[]>([]);
    const [watchEntity, setWatchEntity] = useState('');

    const { data: profilesData } = useQuery({
        queryKey: ['msi-profiles'],
        queryFn: () => msiApi.profiles(),
    });
    const profiles = profilesData?.data || [];

    const runMutation = useMutation({
        mutationFn: () =>
            msiApi.run({
                profile_id: profileId,
                entity: entity.trim(),
                mode,
            }),
        onSuccess: (res) => {
            setRunId(res.data.run_id);
            setLiveEvents([]);
        },
    });

    const { data: runStatusData } = useQuery({
        queryKey: ['msi-run-status', runId],
        queryFn: () => msiApi.runStatus(runId),
        enabled: !!runId,
        refetchInterval: (q) => {
            const status = q.state.data?.data?.status;
            if (status === 'completed' || status === 'failed') return false;
            return 1800;
        },
    });

    const status = runStatusData?.data?.status || '';

    useEffect(() => {
        if (!runId) return;
        const source = new EventSource(`${apiBase}/msi/live?run_id=${encodeURIComponent(runId)}`);
        source.onmessage = (event) => {
            try {
                const payload = JSON.parse(event.data || '{}');
                const line = `${payload.node || 'node'}: ${payload.event_type || 'update'}`;
                setLiveEvents((prev) => [line, ...prev].slice(0, 12));
            } catch {
                // ignore malformed events
            }
        };
        source.onerror = () => source.close();
        return () => source.close();
    }, [runId, apiBase]);

    const { data: reportData, isFetching: reportLoading } = useQuery({
        queryKey: ['msi-report', runId],
        queryFn: () => msiApi.report(runId),
        enabled: !!runId && status === 'completed',
    });

    const report: MsiReport | undefined = reportData?.data;

    const { data: timeseriesData, isFetching: timeseriesLoading } = useQuery({
        queryKey: ['msi-timeseries', profileId, entity, mode],
        queryFn: () =>
            msiApi.timeseries({
                profile_id: profileId,
                entity: entity.trim(),
                mode,
                limit: 30,
            }),
        enabled: !!profileId && !!entity.trim(),
    });
    const points = useMemo(() => timeseriesData?.data?.points || [], [timeseriesData?.data?.points]);

    const { data: topDailyData } = useQuery({
        queryKey: ['msi-top-daily'],
        queryFn: () => msiApi.top({ mode: 'daily', limit: 5 }),
    });
    const { data: topWeeklyData } = useQuery({
        queryKey: ['msi-top-weekly'],
        queryFn: () => msiApi.top({ mode: 'weekly', limit: 5 }),
    });

    const { data: watchlistData } = useQuery({
        queryKey: ['msi-watchlist'],
        queryFn: () => msiApi.watchlist(),
        enabled: canManageWatchlist,
    });

    const addWatchMutation = useMutation({
        mutationFn: () =>
            msiApi.addWatchlist({
                profile_id: profileId,
                entity: watchEntity.trim(),
                run_daily: true,
                run_weekly: true,
                enabled: true,
            }),
        onSuccess: async () => {
            setWatchEntity('');
            await queryClient.invalidateQueries({ queryKey: ['msi-watchlist'] });
        },
    });

    const statusText = useMemo(() => {
        if (status === 'running') return 'التحليل قيد التنفيذ...';
        if (status === 'completed') return 'اكتمل التحليل.';
        if (status === 'failed') return `فشل التحليل: ${runStatusData?.data?.error || 'خطأ غير معروف'}`;
        if (runMutation.isPending) return 'تم إطلاق التحليل...';
        return 'جاهز للتشغيل';
    }, [status, runStatusData?.data?.error, runMutation.isPending]);

    const chartData = useMemo(
        () =>
            points.map((p) => ({
                ts: new Date(p.ts).toLocaleDateString('ar-DZ', { month: '2-digit', day: '2-digit' }),
                msi: Number(p.msi || 0),
            })),
        [points]
    );

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white">مؤشر الاستقرار الإعلامي MSI</h1>
                <p className="text-sm text-gray-400 mt-1">قياس يومي/أسبوعي لاستقرار التغطية الإعلامية للكيانات.</p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-black/20 p-4 grid grid-cols-1 lg:grid-cols-12 gap-3">
                <select
                    value={profileId}
                    onChange={(e) => setProfileId(e.target.value)}
                    className="lg:col-span-3 h-11 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white"
                >
                    {profiles.map((p) => (
                        <option key={p.id} value={p.id} className="bg-gray-900">
                            {p.display_name}
                        </option>
                    ))}
                </select>
                <input
                    value={entity}
                    onChange={(e) => setEntity(e.target.value)}
                    placeholder="اسم الكيان (مثال: عبد المجيد تبون)"
                    className="lg:col-span-4 h-11 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                    dir="rtl"
                />
                <div className="lg:col-span-3 flex gap-2">
                    <button
                        onClick={() => setMode('daily')}
                        className={`flex-1 h-11 rounded-xl border text-sm ${mode === 'daily' ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-200' : 'border-white/10 bg-white/5 text-gray-300'}`}
                    >
                        يومي
                    </button>
                    <button
                        onClick={() => setMode('weekly')}
                        className={`flex-1 h-11 rounded-xl border text-sm ${mode === 'weekly' ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-200' : 'border-white/10 bg-white/5 text-gray-300'}`}
                    >
                        أسبوعي
                    </button>
                </div>
                <button
                    onClick={() => runMutation.mutate()}
                    disabled={!canRun || runMutation.isPending || !entity.trim()}
                    className="lg:col-span-2 h-11 rounded-xl border border-emerald-500/30 bg-emerald-500/20 text-emerald-200 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {runMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    تشغيل الآن
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className={`rounded-2xl border p-4 ${levelColor(report?.level || 'GREEN')}`}>
                    <p className="text-xs mb-1">نتيجة MSI الحالية</p>
                    <p className="text-3xl font-bold">{report ? report.msi.toFixed(1) : '--'}</p>
                    <p className="text-sm mt-1">{report ? levelLabel(report.level) : 'لم يتم التحليل بعد'}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <p className="text-xs text-gray-400 mb-1">حالة التشغيل</p>
                    <p className="text-sm text-gray-200">{statusText || 'جاهز للتشغيل'}</p>
                    <div className="mt-2 space-y-1 max-h-24 overflow-auto text-xs text-gray-400">
                        {liveEvents.length === 0 ? <p>لا توجد أحداث حالياً.</p> : liveEvents.map((e, i) => <p key={`${e}-${i}`}>• {e}</p>)}
                    </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <p className="text-xs text-gray-400 mb-1">أبرز الدوافع</p>
                    <div className="space-y-1 text-sm">
                        {(report?.drivers || []).slice(0, 4).map((d) => (
                            <p key={d.name} className="text-gray-200">{d.name}: <span className="text-white font-semibold">{d.value}%</span></p>
                        ))}
                        {!report && <p className="text-gray-500">شغّل التحليل لعرض الدوافع.</p>}
                    </div>
                </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="flex items-center gap-2 mb-3">
                    <Gauge className="w-4 h-4 text-cyan-300" />
                    <h3 className="text-sm font-semibold text-white">منحنى MSI (آخر 30 نقطة)</h3>
                </div>
                <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                            <XAxis dataKey="ts" stroke="#94a3b8" fontSize={11} />
                            <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={11} />
                            <Tooltip
                                contentStyle={{ background: '#0f172a', border: '1px solid #334155', borderRadius: 10 }}
                                labelStyle={{ color: '#cbd5e1' }}
                            />
                            <Line type="monotone" dataKey="msi" stroke="#34d399" strokeWidth={2} dot={false} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
                {(timeseriesLoading || reportLoading) && <p className="text-xs text-gray-500 mt-2">جاري تحديث البيانات...</p>}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <h3 className="text-sm font-semibold text-white mb-2">الأكثر اضطراباً اليوم</h3>
                    <div className="space-y-2 text-sm">
                        {(topDailyData?.data?.items || []).map((item) => (
                            <div key={`${item.profile_id}-${item.entity}-${item.period_end}`} className="flex items-center justify-between rounded-xl bg-white/5 border border-white/10 px-3 py-2">
                                <span className="text-gray-200">{item.entity}</span>
                                <span className="text-red-300 font-semibold">{item.msi.toFixed(1)}</span>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <h3 className="text-sm font-semibold text-white mb-2">الأكثر اضطراباً هذا الأسبوع</h3>
                    <div className="space-y-2 text-sm">
                        {(topWeeklyData?.data?.items || []).map((item) => (
                            <div key={`${item.profile_id}-${item.entity}-${item.period_end}`} className="flex items-center justify-between rounded-xl bg-white/5 border border-white/10 px-3 py-2">
                                <span className="text-gray-200">{item.entity}</span>
                                <span className="text-orange-300 font-semibold">{item.msi.toFixed(1)}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <h3 className="text-sm font-semibold text-white mb-2">التفسير</h3>
                    <p className="text-sm text-gray-300 leading-7">{report?.explanation || 'بعد التشغيل ستظهر أسباب تغير المؤشر وأهم الدوافع.'}</p>
                    <div className="mt-3">
                        <h4 className="text-xs text-gray-400 mb-2">أكثر مواد ضغطاً</h4>
                        <div className="space-y-2 max-h-52 overflow-auto">
                            {(report?.top_negative_items || []).slice(0, 10).map((item, idx) => (
                                <a
                                    key={`${item.url}-${idx}`}
                                    href={item.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="block rounded-xl bg-white/5 border border-white/10 px-3 py-2 hover:border-white/20"
                                >
                                    <p className="text-sm text-gray-200 line-clamp-2">{item.title}</p>
                                    <p className="text-xs text-gray-500 mt-1">{item.source || '-'}</p>
                                </a>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <h3 className="text-sm font-semibold text-white mb-2">قائمة المراقبة (Pinned Entities)</h3>
                    {canManageWatchlist ? (
                        <>
                            <div className="flex gap-2 mb-3">
                                <input
                                    value={watchEntity}
                                    onChange={(e) => setWatchEntity(e.target.value)}
                                    placeholder="أدخل اسم كيان لإضافته"
                                    className="flex-1 h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white"
                                    dir="rtl"
                                />
                                <button
                                    onClick={() => addWatchMutation.mutate()}
                                    disabled={!watchEntity.trim() || addWatchMutation.isPending}
                                    className="h-10 px-4 rounded-xl border border-cyan-500/30 bg-cyan-500/20 text-cyan-200 text-sm disabled:opacity-50"
                                >
                                    إضافة
                                </button>
                            </div>
                            <div className="space-y-2 max-h-56 overflow-auto">
                                {(watchlistData?.data || []).map((item) => (
                                    <div key={item.id} className="rounded-xl bg-white/5 border border-white/10 px-3 py-2">
                                        <p className="text-sm text-gray-200">{item.entity}</p>
                                        <p className="text-xs text-gray-500 mt-1">{item.profile_id} • {item.enabled ? 'مفعل' : 'معطل'}</p>
                                    </div>
                                ))}
                            </div>
                        </>
                    ) : (
                        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4" />
                            إدارة قائمة المراقبة متاحة للمدير/رئيس التحرير.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
