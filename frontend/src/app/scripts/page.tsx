'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, RefreshCw, ScrollText, CheckCircle2, XCircle } from 'lucide-react';
import { useSearchParams } from 'next/navigation';

import { scriptsApi, type ScriptProjectRecord } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatRelativeTime } from '@/lib/utils';

type ScriptTypeFilter = 'all' | 'story_script' | 'video_script' | 'bulletin_daily' | 'bulletin_weekly';
type ScriptStatusFilter = 'all' | 'new' | 'generating' | 'ready_for_review' | 'approved' | 'rejected' | 'archived';

export default function ScriptsPage() {
    return (
        <Suspense
            fallback={
                <div className="space-y-4" dir="rtl">
                    <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">جاري تحميل استوديو السكربت...</div>
                </div>
            }
        >
            <ScriptsPageClient />
        </Suspense>
    );
}

function ScriptsPageClient() {
    const searchParams = useSearchParams();
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const [typeFilter, setTypeFilter] = useState<ScriptTypeFilter>('all');
    const [statusFilter, setStatusFilter] = useState<ScriptStatusFilter>('all');
    const [selectedScriptId, setSelectedScriptId] = useState<number | null>(null);
    const [message, setMessage] = useState<string>('');

    const [dailyMaxItems, setDailyMaxItems] = useState(8);
    const [dailyDuration, setDailyDuration] = useState(5);
    const [dailyGeo, setDailyGeo] = useState('ALL');
    const [dailyCategory, setDailyCategory] = useState('all');

    const [weeklyMaxItems, setWeeklyMaxItems] = useState(12);
    const [weeklyDuration, setWeeklyDuration] = useState(8);

    useEffect(() => {
        const raw = searchParams.get('script_id');
        const scriptId = Number(raw || 0);
        if (scriptId > 0) {
            setSelectedScriptId(scriptId);
        }
    }, [searchParams]);

    const listQuery = useQuery({
        queryKey: ['scripts-list', typeFilter, statusFilter],
        queryFn: () =>
            scriptsApi.list({
                limit: 120,
                type: typeFilter === 'all' ? undefined : typeFilter,
                status: statusFilter === 'all' ? undefined : statusFilter,
            }),
        refetchInterval: 20000,
    });

    const createDailyMutation = useMutation({
        mutationFn: () =>
            scriptsApi.generateDailyBulletin(
                {
                    max_items: dailyMaxItems,
                    duration_minutes: dailyDuration,
                    desks: [],
                    language: 'ar',
                    tone: 'neutral',
                },
                { geo: dailyGeo, category: dailyCategory },
            ),
        onSuccess: (res) => {
            setMessage(`تم إنشاء مشروع نشرة يومية: ${res.data.script.title}`);
            queryClient.invalidateQueries({ queryKey: ['scripts-list'] });
            setSelectedScriptId(res.data.script.id);
        },
        onError: () => setMessage('تعذر إنشاء النشرة اليومية حالياً.'),
    });

    const createWeeklyMutation = useMutation({
        mutationFn: () =>
            scriptsApi.generateWeeklyBulletin(
                {
                    max_items: weeklyMaxItems,
                    duration_minutes: weeklyDuration,
                    desks: [],
                    language: 'ar',
                    tone: 'neutral',
                },
                { geo: 'ALL', category: 'all' },
            ),
        onSuccess: (res) => {
            setMessage(`تم إنشاء مشروع نشرة أسبوعية: ${res.data.script.title}`);
            queryClient.invalidateQueries({ queryKey: ['scripts-list'] });
            setSelectedScriptId(res.data.script.id);
        },
        onError: () => setMessage('تعذر إنشاء النشرة الأسبوعية حالياً.'),
    });

    const projects = useMemo(() => listQuery.data?.data || [], [listQuery.data?.data]);
    const canReview = user?.role === 'editor_chief' || user?.role === 'director';

    return (
        <div className="space-y-4" dir="rtl">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white inline-flex items-center gap-2">
                        <ScrollText className="w-6 h-6 text-cyan-300" />
                        استوديو السكربت
                    </h1>
                    <p className="text-xs text-slate-400 mt-1">توليد سكربت القصة، باقة الفيديو، والنشرة اليومية/الأسبوعية مع مراجعة بشرية إلزامية.</p>
                </div>
                <button
                    type="button"
                    onClick={() => listQuery.refetch()}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 hover:text-white"
                >
                    <RefreshCw className={cn('w-4 h-4', listQuery.isRefetching && 'animate-spin')} />
                    تحديث
                </button>
            </div>

            {message && (
                <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-sm text-cyan-100">
                    {message}
                </div>
            )}

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4 space-y-3 xl:col-span-2">
                    <h2 className="text-sm font-semibold text-white">مشاريع السكربت</h2>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                        <select
                            value={typeFilter}
                            onChange={(e) => setTypeFilter(e.target.value as ScriptTypeFilter)}
                            className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
                        >
                            <option value="all">كل الأنواع</option>
                            <option value="story_script">Story Script</option>
                            <option value="video_script">Video Script</option>
                            <option value="bulletin_daily">Bulletin Daily</option>
                            <option value="bulletin_weekly">Bulletin Weekly</option>
                        </select>
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value as ScriptStatusFilter)}
                            className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
                        >
                            <option value="all">كل الحالات</option>
                            <option value="new">new</option>
                            <option value="generating">generating</option>
                            <option value="ready_for_review">ready_for_review</option>
                            <option value="approved">approved</option>
                            <option value="rejected">rejected</option>
                            <option value="archived">archived</option>
                        </select>
                        <div className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-300 flex items-center">
                            العدد: {projects.length}
                        </div>
                    </div>

                    <div className="space-y-2 max-h-[520px] overflow-y-auto">
                        {listQuery.isLoading && (
                            <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-sm text-slate-400">جاري التحميل...</div>
                        )}
                        {!listQuery.isLoading && projects.length === 0 && (
                            <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
                                لا توجد مشاريع سكربت ضمن هذا الفلتر.
                            </div>
                        )}
                        {projects.map((project) => (
                            <button
                                key={project.id}
                                type="button"
                                onClick={() => setSelectedScriptId(project.id)}
                                className="w-full text-right rounded-xl border border-white/10 bg-slate-900/70 p-3 hover:border-cyan-400/40 transition-colors"
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <div>
                                        <p className="text-xs text-cyan-300">{project.type}</p>
                                        <p className="text-sm text-white font-medium mt-1">{project.title}</p>
                                    </div>
                                    <span className="text-[11px] rounded-md border border-white/15 bg-white/5 px-2 py-1 text-slate-200">
                                        {project.status}
                                    </span>
                                </div>
                                <p className="text-[11px] text-slate-400 mt-2">
                                    آخر تحديث: {project.updated_at ? formatRelativeTime(project.updated_at) : '-'}
                                </p>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-4 space-y-4">
                    <h2 className="text-sm font-semibold text-white">توليد النشرات</h2>

                    <div className="space-y-2">
                        <p className="text-xs text-slate-300">النشرة اليومية</p>
                        <div className="grid grid-cols-2 gap-2">
                            <input
                                type="number"
                                min={1}
                                max={20}
                                value={dailyMaxItems}
                                onChange={(e) => setDailyMaxItems(Number(e.target.value) || 8)}
                                className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-white"
                                placeholder="max items"
                            />
                            <input
                                type="number"
                                min={1}
                                max={30}
                                value={dailyDuration}
                                onChange={(e) => setDailyDuration(Number(e.target.value) || 5)}
                                className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-white"
                                placeholder="minutes"
                            />
                            <select
                                value={dailyGeo}
                                onChange={(e) => setDailyGeo(e.target.value)}
                                className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
                            >
                                <option value="ALL">ALL</option>
                                <option value="DZ">DZ</option>
                                <option value="WORLD">WORLD</option>
                            </select>
                            <select
                                value={dailyCategory}
                                onChange={(e) => setDailyCategory(e.target.value)}
                                className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
                            >
                                <option value="all">all</option>
                                <option value="politics">politics</option>
                                <option value="economy">economy</option>
                                <option value="sports">sports</option>
                                <option value="technology">technology</option>
                                <option value="local_algeria">local_algeria</option>
                                <option value="international">international</option>
                            </select>
                        </div>
                        <button
                            type="button"
                            onClick={() => createDailyMutation.mutate()}
                            disabled={createDailyMutation.isPending}
                            className="w-full h-10 rounded-xl border border-emerald-500/30 bg-emerald-500/15 text-sm text-emerald-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                        >
                            {createDailyMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                            توليد النشرة اليومية
                        </button>
                    </div>

                    <div className="space-y-2">
                        <p className="text-xs text-slate-300">النشرة الأسبوعية</p>
                        <div className="grid grid-cols-2 gap-2">
                            <input
                                type="number"
                                min={1}
                                max={20}
                                value={weeklyMaxItems}
                                onChange={(e) => setWeeklyMaxItems(Number(e.target.value) || 12)}
                                className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-white"
                                placeholder="max items"
                            />
                            <input
                                type="number"
                                min={1}
                                max={30}
                                value={weeklyDuration}
                                onChange={(e) => setWeeklyDuration(Number(e.target.value) || 8)}
                                className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-white"
                                placeholder="minutes"
                            />
                        </div>
                        <button
                            type="button"
                            onClick={() => createWeeklyMutation.mutate()}
                            disabled={createWeeklyMutation.isPending}
                            className="w-full h-10 rounded-xl border border-sky-500/30 bg-sky-500/15 text-sm text-sky-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                        >
                            {createWeeklyMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                            توليد النشرة الأسبوعية
                        </button>
                    </div>
                </div>
            </div>

            {selectedScriptId && (
                <ScriptViewerDrawer
                    scriptId={selectedScriptId}
                    canReview={canReview}
                    onClose={() => setSelectedScriptId(null)}
                />
            )}
        </div>
    );
}

function ScriptViewerDrawer({
    scriptId,
    canReview,
    onClose,
}: {
    scriptId: number;
    canReview: boolean;
    onClose: () => void;
}) {
    const queryClient = useQueryClient();
    const [rejectReason, setRejectReason] = useState('');

    const scriptQuery = useQuery({
        queryKey: ['script-project', scriptId],
        queryFn: () => scriptsApi.get(scriptId),
        refetchInterval: 10000,
    });
    const outputsQuery = useQuery({
        queryKey: ['script-outputs', scriptId],
        queryFn: () => scriptsApi.outputs(scriptId),
        refetchInterval: 10000,
    });

    const approveMutation = useMutation({
        mutationFn: () => scriptsApi.approve(scriptId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['script-project', scriptId] });
            queryClient.invalidateQueries({ queryKey: ['scripts-list'] });
        },
    });
    const rejectMutation = useMutation({
        mutationFn: () => scriptsApi.reject(scriptId, { reason: rejectReason }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['script-project', scriptId] });
            queryClient.invalidateQueries({ queryKey: ['scripts-list'] });
        },
    });

    const project: ScriptProjectRecord | undefined = scriptQuery.data?.data;
    const outputs = outputsQuery.data?.data || [];
    const latestOutput = outputs[0];

    return (
        <div className="fixed inset-0 z-[85] bg-black/70 backdrop-blur-sm flex justify-end" dir="rtl">
            <div className="w-full max-w-3xl h-full overflow-y-auto border-l border-white/10 bg-slate-950 p-5 space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-white">عارض السكربت</h3>
                    <button onClick={onClose} className="rounded-lg border border-white/20 px-3 py-1.5 text-xs text-slate-300">إغلاق</button>
                </div>

                {(scriptQuery.isLoading || outputsQuery.isLoading) && <p className="text-sm text-slate-400">جاري التحميل...</p>}
                {(scriptQuery.error || outputsQuery.error) && <p className="text-sm text-red-300">تعذر تحميل بيانات السكربت.</p>}

                {project && (
                    <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-2">
                        <p className="text-xs text-cyan-300">{project.type}</p>
                        <h4 className="text-lg text-white font-semibold">{project.title}</h4>
                        <p className="text-xs text-slate-300">
                            الحالة: {project.status} • آخر تحديث: {project.updated_at ? formatRelativeTime(project.updated_at) : '-'}
                        </p>

                        {canReview && project.status === 'ready_for_review' && (
                            <div className="border-t border-white/10 pt-3 mt-3 space-y-2">
                                <div className="flex flex-wrap gap-2">
                                    <button
                                        type="button"
                                        onClick={() => approveMutation.mutate()}
                                        disabled={approveMutation.isPending}
                                        className="h-9 px-3 rounded-lg border border-emerald-500/30 bg-emerald-500/15 text-xs text-emerald-200 inline-flex items-center gap-2 disabled:opacity-60"
                                    >
                                        <CheckCircle2 className="w-4 h-4" />
                                        اعتماد السكربت
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => rejectMutation.mutate()}
                                        disabled={rejectMutation.isPending || !rejectReason.trim()}
                                        className="h-9 px-3 rounded-lg border border-red-500/30 bg-red-500/15 text-xs text-red-200 inline-flex items-center gap-2 disabled:opacity-60"
                                    >
                                        <XCircle className="w-4 h-4" />
                                        رفض السكربت
                                    </button>
                                </div>
                                <textarea
                                    value={rejectReason}
                                    onChange={(e) => setRejectReason(e.target.value)}
                                    placeholder="سبب الرفض (إلزامي عند الرفض)"
                                    className="w-full min-h-[84px] rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white"
                                />
                            </div>
                        )}
                    </div>
                )}

                {latestOutput && (
                    <div className="space-y-3">
                        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                            <p className="text-xs text-slate-300">النسخة: v{latestOutput.version} • {latestOutput.format}</p>
                        </div>

                        {latestOutput.quality_issues?.length > 0 && (
                            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 space-y-1">
                                <p className="text-xs text-amber-200">ملاحظات الجودة</p>
                                {latestOutput.quality_issues.map((issue, idx) => (
                                    <p key={`${issue.code}-${idx}`} className="text-xs text-amber-100">
                                        [{issue.severity}] {issue.message}
                                    </p>
                                ))}
                            </div>
                        )}

                        <pre className="rounded-xl border border-white/10 bg-black/25 p-3 text-xs text-slate-100 whitespace-pre-wrap overflow-x-auto">
                            {latestOutput.content_json
                                ? JSON.stringify(latestOutput.content_json, null, 2)
                                : latestOutput.content_text || 'لا يوجد محتوى.'}
                        </pre>
                    </div>
                )}
            </div>
        </div>
    );
}
