'use client';

import { Suspense, type ReactNode, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, RefreshCw, ScrollText, CheckCircle2, XCircle, AlertTriangle, GitCompare, RotateCw, CopyPlus } from 'lucide-react';
import { useSearchParams } from 'next/navigation';

import { scriptsApi, type ScriptOutputRecord, type ScriptProjectRecord } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatRelativeTime } from '@/lib/utils';

type ScriptTypeFilter = 'all' | 'story_script' | 'video_script' | 'bulletin_daily' | 'bulletin_weekly';
type ScriptStatusFilter = 'all' | 'new' | 'generating' | 'failed' | 'ready_for_review' | 'approved' | 'rejected' | 'archived';

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
    const [inboxFocus, setInboxFocus] = useState<'all' | 'regenerated'>('all');
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
    const displayedProjects = useMemo(() => {
        if (inboxFocus === 'regenerated') {
            return projects.filter((item) => (item.output_count || 0) > 1);
        }
        return projects;
    }, [inboxFocus, projects]);
    const inboxSections = useMemo(() => {
        const needsReview = projects.filter((item) => item.status === 'ready_for_review');
        const failed = projects.filter((item) => item.status === 'failed');
        const regenerated = projects.filter((item) => (item.output_count || 0) > 1);
        const approved = projects.filter((item) => item.status === 'approved');
        const rejected = projects.filter((item) => item.status === 'rejected');
        return [
            { key: 'ready_for_review', label: 'يحتاج مراجعة', tone: 'cyan', count: needsReview.length },
            { key: 'failed', label: 'فشل', tone: 'red', count: failed.length },
            { key: 'regenerated', label: 'معاد توليده', tone: 'amber', count: regenerated.length },
            { key: 'approved', label: 'معتمد', tone: 'emerald', count: approved.length },
            { key: 'rejected', label: 'مرفوض', tone: 'violet', count: rejected.length },
        ] as const;
    }, [projects]);
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

            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                {inboxSections.map((section) => (
                    <button
                        key={section.key}
                        type="button"
                        onClick={() => {
                            if (section.key === 'regenerated') {
                                setInboxFocus('regenerated');
                                setStatusFilter('all');
                                return;
                            }
                            setInboxFocus('all');
                            setStatusFilter(section.key as ScriptStatusFilter);
                        }}
                        className={cn(
                            'rounded-xl border px-3 py-2 text-right transition-colors',
                            section.tone === 'red' && 'border-red-500/30 bg-red-500/10 hover:bg-red-500/15',
                            section.tone === 'cyan' && 'border-cyan-500/30 bg-cyan-500/10 hover:bg-cyan-500/15',
                            section.tone === 'amber' && 'border-amber-500/30 bg-amber-500/10 hover:bg-amber-500/15',
                            section.tone === 'emerald' && 'border-emerald-500/30 bg-emerald-500/10 hover:bg-emerald-500/15',
                            section.tone === 'violet' && 'border-violet-500/30 bg-violet-500/10 hover:bg-violet-500/15',
                        )}
                    >
                        <p className="text-[11px] text-slate-300">{section.label}</p>
                        <p className="text-xl font-semibold text-white">{section.count}</p>
                    </button>
                ))}
            </div>

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
                            onChange={(e) => {
                                setInboxFocus('all');
                                setStatusFilter(e.target.value as ScriptStatusFilter);
                            }}
                            className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
                        >
                            <option value="all">كل الحالات</option>
                            <option value="new">new</option>
                            <option value="generating">generating</option>
                            <option value="failed">failed</option>
                            <option value="ready_for_review">ready_for_review</option>
                            <option value="approved">approved</option>
                            <option value="rejected">rejected</option>
                            <option value="archived">archived</option>
                        </select>
                        <div className="h-10 rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-300 flex items-center">
                            العدد: {displayedProjects.length}
                        </div>
                    </div>

                    <div className="space-y-2 max-h-[520px] overflow-y-auto">
                        {listQuery.isLoading && (
                            <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-sm text-slate-400">جاري التحميل...</div>
                        )}
                        {!listQuery.isLoading && displayedProjects.length === 0 && (
                            <div className="rounded-xl border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
                                لا توجد مشاريع سكربت ضمن هذا الفلتر.
                            </div>
                        )}
                        {displayedProjects.map((project) => (
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
                                <div className="mt-2 flex flex-wrap items-center gap-2">
                                    <span className="text-[10px] rounded-md border border-white/15 bg-white/5 px-2 py-0.5 text-slate-300">
                                        versions: {project.output_count || 0}
                                    </span>
                                    <span className="text-[10px] rounded-md border border-white/15 bg-white/5 px-2 py-0.5 text-slate-300">
                                        blockers: {project.latest_quality_blockers || 0}
                                    </span>
                                    <span className="text-[10px] rounded-md border border-white/15 bg-white/5 px-2 py-0.5 text-slate-300">
                                        warnings: {project.latest_quality_warnings || 0}
                                    </span>
                                </div>
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
    const [actionMessage, setActionMessage] = useState('');
    const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
    const [fromVersion, setFromVersion] = useState<number | null>(null);
    const [toVersion, setToVersion] = useState<number | null>(null);

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
    const recoveryHintsQuery = useQuery({
        queryKey: ['script-recovery-hints', scriptId],
        queryFn: () => scriptsApi.recoveryHints(scriptId),
        refetchInterval: 10000,
    });

    const outputs = outputsQuery.data?.data || [];

    useEffect(() => {
        if (!outputs.length) return;
        if (selectedVersion === null) {
            setSelectedVersion(outputs[0].version);
        }
        if (fromVersion === null) {
            setFromVersion(outputs[0].version);
        }
        if (toVersion === null) {
            setToVersion((outputs[1] || outputs[0]).version);
        }
    }, [outputs, selectedVersion, fromVersion, toVersion]);

    const diffQuery = useQuery({
        queryKey: ['script-version-diff', scriptId, fromVersion, toVersion],
        queryFn: () => scriptsApi.versionsDiff(scriptId, fromVersion as number, toVersion as number),
        enabled: Boolean(fromVersion && toVersion && fromVersion !== toVersion),
    });

    const refreshDrawerData = () => {
        queryClient.invalidateQueries({ queryKey: ['script-project', scriptId] });
        queryClient.invalidateQueries({ queryKey: ['script-outputs', scriptId] });
        queryClient.invalidateQueries({ queryKey: ['script-recovery-hints', scriptId] });
        queryClient.invalidateQueries({ queryKey: ['scripts-list'] });
    };

    const approveMutation = useMutation({
        mutationFn: () => scriptsApi.approve(scriptId),
        onSuccess: () => {
            setActionMessage('تم اعتماد السكربت.');
            refreshDrawerData();
        },
    });
    const rejectMutation = useMutation({
        mutationFn: () => scriptsApi.reject(scriptId, { reason: rejectReason }),
        onSuccess: () => {
            setActionMessage('تم رفض السكربت.');
            refreshDrawerData();
        },
    });
    const regenerateMutation = useMutation({
        mutationFn: () => scriptsApi.regenerate(scriptId),
        onSuccess: (res) => {
            setActionMessage(`تمت إعادة التوليد (v${res.data.job?.target_version ?? '-'})`);
            refreshDrawerData();
        },
        onError: () => setActionMessage('تعذر إعادة التوليد حالياً.'),
    });
    const duplicateMutation = useMutation({
        mutationFn: (sourceVersion?: number) => scriptsApi.duplicateVersion(scriptId, sourceVersion ? { source_version: sourceVersion } : {}),
        onSuccess: (res) => {
            setActionMessage(`تم إنشاء نسخة جديدة v${res.data.output.version}`);
            setSelectedVersion(res.data.output.version);
            refreshDrawerData();
        },
        onError: () => setActionMessage('تعذر نسخ الإصدار.'),
    });

    const project: ScriptProjectRecord | undefined = scriptQuery.data?.data;
    const recoveryData = recoveryHintsQuery.data?.data;
    const selectedOutput = outputs.find((row) => row.version === selectedVersion) || outputs[0];

    return (
        <div className="fixed inset-0 z-[85] bg-black/70 backdrop-blur-sm flex justify-end" dir="rtl">
            <div className="w-full max-w-3xl h-full overflow-y-auto border-l border-white/10 bg-slate-950 p-5 space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-white">عارض السكربت</h3>
                    <button onClick={onClose} className="rounded-lg border border-white/20 px-3 py-1.5 text-xs text-slate-300">إغلاق</button>
                </div>

                {(scriptQuery.isLoading || outputsQuery.isLoading) && <p className="text-sm text-slate-400">جاري التحميل...</p>}
                {(scriptQuery.error || outputsQuery.error) && <p className="text-sm text-red-300">تعذر تحميل بيانات السكربت.</p>}
                {actionMessage && (
                    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-xs text-cyan-100">
                        {actionMessage}
                    </div>
                )}

                {project && (
                    <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-2">
                        <p className="text-xs text-cyan-300">{project.type}</p>
                        <h4 className="text-lg text-white font-semibold">{project.title}</h4>
                        <p className="text-xs text-slate-300">
                            الحالة: {project.status} • آخر تحديث: {project.updated_at ? formatRelativeTime(project.updated_at) : '-'}
                        </p>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 pt-2">
                            <button
                                type="button"
                                onClick={() => regenerateMutation.mutate()}
                                disabled={regenerateMutation.isPending}
                                className="h-9 rounded-lg border border-cyan-500/30 bg-cyan-500/15 text-xs text-cyan-200 inline-flex items-center justify-center gap-1.5 disabled:opacity-60"
                            >
                                <RotateCw className={cn('w-3.5 h-3.5', regenerateMutation.isPending && 'animate-spin')} />
                                إعادة التوليد
                            </button>
                            <button
                                type="button"
                                onClick={() => duplicateMutation.mutate(selectedOutput?.version)}
                                disabled={!selectedOutput || duplicateMutation.isPending}
                                className="h-9 rounded-lg border border-violet-500/30 bg-violet-500/15 text-xs text-violet-200 inline-flex items-center justify-center gap-1.5 disabled:opacity-60"
                            >
                                <CopyPlus className="w-3.5 h-3.5" />
                                نسخ كإصدار جديد
                            </button>
                            <button
                                type="button"
                                onClick={() => recoveryHintsQuery.refetch()}
                                disabled={recoveryHintsQuery.isFetching}
                                className="h-9 rounded-lg border border-amber-500/30 bg-amber-500/15 text-xs text-amber-200 inline-flex items-center justify-center gap-1.5 disabled:opacity-60"
                            >
                                <AlertTriangle className="w-3.5 h-3.5" />
                                استرجاع الفشل
                            </button>
                            <button
                                type="button"
                                onClick={() => diffQuery.refetch()}
                                disabled={!fromVersion || !toVersion || fromVersion === toVersion || diffQuery.isFetching}
                                className="h-9 rounded-lg border border-white/15 bg-white/5 text-xs text-slate-200 inline-flex items-center justify-center gap-1.5 disabled:opacity-60"
                            >
                                <GitCompare className="w-3.5 h-3.5" />
                                مقارنة النسخ
                            </button>
                        </div>

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

                {recoveryData?.hints?.length ? (
                    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 space-y-2">
                        <p className="text-xs text-amber-200">
                            {recoveryData.latest_failed_job ? 'إرشادات معالجة آخر فشل' : 'إرشادات تشغيل سريعة'}
                        </p>
                        {recoveryData.hints.map((hint) => (
                            <div key={hint.code} className="rounded-lg border border-amber-500/30 bg-black/20 p-2">
                                <p className="text-xs text-amber-100">{hint.title}</p>
                                <p className="text-[11px] text-slate-300 mt-1">{hint.action}</p>
                            </div>
                        ))}
                        {recoveryData.latest_failed_job?.error ? (
                            <details className="rounded-lg border border-white/10 bg-black/20 p-2">
                                <summary className="cursor-pointer text-[11px] text-slate-300">عرض الخطأ الخام</summary>
                                <pre className="mt-2 whitespace-pre-wrap text-[11px] text-slate-200 overflow-x-auto">
                                    {recoveryData.latest_failed_job.error}
                                </pre>
                            </details>
                        ) : null}
                    </div>
                ) : null}

                {selectedOutput && (
                    <div className="space-y-3">
                        {outputs.length > 0 && (
                            <div className="rounded-xl border border-white/10 bg-white/5 p-3 space-y-2">
                                <p className="text-xs text-slate-300">الإصدارات المتاحة ({outputs.length})</p>
                                <div className="flex flex-wrap gap-2">
                                    {outputs.map((output) => (
                                        <button
                                            key={output.id}
                                            type="button"
                                            onClick={() => setSelectedVersion(output.version)}
                                            className={cn(
                                                'h-7 px-2 rounded-md border text-xs',
                                                selectedOutput.version === output.version
                                                    ? 'border-cyan-400/60 bg-cyan-500/15 text-cyan-100'
                                                    : 'border-white/15 bg-white/5 text-slate-300',
                                            )}
                                        >
                                            v{output.version}
                                        </button>
                                    ))}
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 pt-1">
                                    <select
                                        value={fromVersion ?? ''}
                                        onChange={(e) => setFromVersion(Number(e.target.value))}
                                        className="h-9 rounded-lg border border-white/10 bg-black/20 px-3 text-xs text-slate-200"
                                    >
                                        {outputs.map((output) => (
                                            <option key={`from-${output.id}`} value={output.version}>
                                                من v{output.version}
                                            </option>
                                        ))}
                                    </select>
                                    <select
                                        value={toVersion ?? ''}
                                        onChange={(e) => setToVersion(Number(e.target.value))}
                                        className="h-9 rounded-lg border border-white/10 bg-black/20 px-3 text-xs text-slate-200"
                                    >
                                        {outputs.map((output) => (
                                            <option key={`to-${output.id}`} value={output.version}>
                                                إلى v{output.version}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                        )}

                        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                            <p className="text-xs text-slate-300">النسخة: v{selectedOutput.version} • {selectedOutput.format}</p>
                        </div>

                        {selectedOutput.quality_issues?.length > 0 && (
                            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 space-y-1">
                                <p className="text-xs text-amber-200">ملاحظات الجودة</p>
                                {selectedOutput.quality_issues.map((issue, idx) => (
                                    <p key={`${issue.code}-${idx}`} className="text-xs text-amber-100">
                                        [{issue.severity}] {issue.message}
                                    </p>
                                ))}
                            </div>
                        )}

                        {diffQuery.data?.data?.diff_lines?.length ? (
                            <details className="rounded-xl border border-white/10 bg-black/20 p-3">
                                <summary className="cursor-pointer text-xs text-slate-300">
                                    مقارنة v{fromVersion} → v{toVersion} ( +{diffQuery.data.data.added_lines} / -{diffQuery.data.data.removed_lines} )
                                </summary>
                                <pre className="mt-2 whitespace-pre-wrap text-[11px] text-slate-200 overflow-x-auto max-h-64 overflow-y-auto">
                                    {diffQuery.data.data.diff_lines.join('\n')}
                                </pre>
                            </details>
                        ) : null}

                        <StructuredScriptOutput projectType={project?.type} output={selectedOutput} />
                    </div>
                )}
            </div>
        </div>
    );
}

function StructuredScriptOutput({
    projectType,
    output,
}: {
    projectType: string | undefined;
    output: ScriptOutputRecord;
}) {
    const content = toObject(output.content_json);

    if (!content) {
        return (
            <pre className="rounded-xl border border-white/10 bg-black/25 p-3 text-xs text-slate-100 whitespace-pre-wrap overflow-x-auto">
                {output.content_text || 'No script content available.'}
            </pre>
        );
    }

    if (projectType === 'story_script') return <StoryScriptView data={content} output={output} />;
    if (projectType === 'video_script') return <VideoScriptView data={content} output={output} />;
    if (projectType === 'bulletin_daily' || projectType === 'bulletin_weekly') {
        return <BulletinScriptView data={content} output={output} />;
    }

    return (
        <pre className="rounded-xl border border-white/10 bg-black/25 p-3 text-xs text-slate-100 whitespace-pre-wrap overflow-x-auto">
            {JSON.stringify(content, null, 2)}
        </pre>
    );
}

function StoryScriptView({ data, output }: { data: Record<string, unknown>; output: ScriptOutputRecord }) {
    const quotes = toObjectArray(data.quotes);
    const timeline = toObjectArray(data.timeline);

    return (
        <div className="space-y-3">
            <SectionCard title="Hook">{toText(data.hook) || '-'}</SectionCard>
            <SectionCard title="Context">{toText(data.context) || '-'}</SectionCard>
            <SectionCard title="What Happened">{toText(data.what_happened) || '-'}</SectionCard>
            <SectionCard title="Why It Matters">{toText(data.why_it_matters) || '-'}</SectionCard>
            <SectionCard title="Known / Unknown">{toText(data.known_unknown) || '-'}</SectionCard>

            <SectionCard title={`Quotes (${quotes.length})`}>
                {quotes.length === 0 ? (
                    <p className="text-xs text-slate-400">No quotes.</p>
                ) : (
                    <div className="space-y-2">
                        {quotes.map((quote, idx) => (
                            <div key={`q-${idx}`} className="rounded-lg border border-white/10 bg-black/20 p-2">
                                <p className="text-sm text-slate-100">{toText(quote.text) || '-'}</p>
                                <p className="mt-1 text-xs text-cyan-300">Source: {toText(quote.source) || 'unknown'}</p>
                            </div>
                        ))}
                    </div>
                )}
            </SectionCard>

            <SectionCard title={`Timeline (${timeline.length})`}>
                {timeline.length === 0 ? (
                    <p className="text-xs text-slate-400">No timeline events.</p>
                ) : (
                    <div className="space-y-2">
                        {timeline.map((item, idx) => (
                            <div key={`t-${idx}`} className="rounded-lg border border-white/10 bg-black/20 p-2">
                                <p className="text-xs text-cyan-300">{toText(item.time) || `Step ${idx + 1}`}</p>
                                <p className="text-sm text-slate-100">{toText(item.event) || '-'}</p>
                            </div>
                        ))}
                    </div>
                )}
            </SectionCard>

            <SectionCard title="Close">{toText(data.close) || '-'}</SectionCard>
            <SectionCard title="Social Short">{toText(data.social_short) || '-'}</SectionCard>
            <SectionCard title="Anchor Notes">{toText(data.anchor_notes) || '-'}</SectionCard>

            <RawOutputDetails output={output} />
        </div>
    );
}

function VideoScriptView({ data, output }: { data: Record<string, unknown>; output: ScriptOutputRecord }) {
    const scenes = toObjectArray(data.scenes);
    const assets = toObjectArray(data.assets_list);
    const ideas = toStringArray(data.thumbnail_ideas);

    return (
        <div className="space-y-3">
            <SectionCard title="VO Script">{toText(data.vo_script) || '-'}</SectionCard>

            <SectionCard title={`Scenes (${scenes.length})`}>
                {scenes.length === 0 ? (
                    <p className="text-xs text-slate-400">No scenes.</p>
                ) : (
                    <div className="space-y-2">
                        {scenes.map((scene, idx) => (
                            <div key={`scene-${idx}`} className="rounded-lg border border-white/10 bg-black/20 p-2 space-y-1">
                                <p className="text-xs text-cyan-300">
                                    Scene #{toText(scene.idx) || String(idx + 1)} - {toText(scene.duration_s) || '0'}s
                                </p>
                                <p className="text-sm text-slate-100">Visual: {toText(scene.visual) || '-'}</p>
                                <p className="text-sm text-slate-200">On-screen: {toText(scene.on_screen_text) || '-'}</p>
                                <p className="text-sm text-slate-300">VO: {toText(scene.vo_line) || '-'}</p>
                            </div>
                        ))}
                    </div>
                )}
            </SectionCard>

            <SectionCard title="Captions (SRT)">
                <pre className="whitespace-pre-wrap text-xs text-slate-200">{toText(data.captions_srt) || '-'}</pre>
            </SectionCard>

            <SectionCard title={`Assets (${assets.length})`}>
                {assets.length === 0 ? (
                    <p className="text-xs text-slate-400">No assets listed.</p>
                ) : (
                    <div className="space-y-2">
                        {assets.map((asset, idx) => (
                            <div key={`asset-${idx}`} className="rounded-lg border border-white/10 bg-black/20 p-2">
                                <p className="text-xs text-cyan-300">{toText(asset.type) || 'asset'}</p>
                                <p className="text-sm text-slate-100">{toText(asset.hint) || '-'}</p>
                            </div>
                        ))}
                    </div>
                )}
            </SectionCard>

            <SectionCard title={`Thumbnail Ideas (${ideas.length})`}>
                {ideas.length === 0 ? (
                    <p className="text-xs text-slate-400">No ideas.</p>
                ) : (
                    <ul className="list-disc pr-5 text-sm text-slate-100 space-y-1">
                        {ideas.map((idea, idx) => (
                            <li key={`idea-${idx}`}>{idea}</li>
                        ))}
                    </ul>
                )}
            </SectionCard>

            <RawOutputDetails output={output} />
        </div>
    );
}

function BulletinScriptView({ data, output }: { data: Record<string, unknown>; output: ScriptOutputRecord }) {
    const headlines = toStringArray(data.headlines);
    const segments = toObjectArray(data.segments);
    const transitions = toStringArray(data.transitions);

    return (
        <div className="space-y-3">
            <SectionCard title="Opening">{toText(data.opening) || '-'}</SectionCard>

            <SectionCard title={`Headlines (${headlines.length})`}>
                {headlines.length === 0 ? (
                    <p className="text-xs text-slate-400">No headlines.</p>
                ) : (
                    <ul className="list-disc pr-5 text-sm text-slate-100 space-y-1">
                        {headlines.map((headline, idx) => (
                            <li key={`h-${idx}`}>{headline}</li>
                        ))}
                    </ul>
                )}
            </SectionCard>

            <SectionCard title={`Segments (${segments.length})`}>
                {segments.length === 0 ? (
                    <p className="text-xs text-slate-400">No segments.</p>
                ) : (
                    <div className="space-y-2">
                        {segments.map((segment, idx) => (
                            <div key={`seg-${idx}`} className="rounded-lg border border-white/10 bg-black/20 p-2 space-y-1">
                                <p className="text-xs text-cyan-300">
                                    {toText(segment.title) || `Segment ${idx + 1}`} - {toText(segment.duration_s) || '0'}s
                                </p>
                                <p className="text-sm text-slate-100">{toText(segment.vo) || '-'}</p>
                            </div>
                        ))}
                    </div>
                )}
            </SectionCard>

            <SectionCard title={`Transitions (${transitions.length})`}>
                {transitions.length === 0 ? (
                    <p className="text-xs text-slate-400">No transitions.</p>
                ) : (
                    <ul className="list-disc pr-5 text-sm text-slate-100 space-y-1">
                        {transitions.map((transition, idx) => (
                            <li key={`tr-${idx}`}>{transition}</li>
                        ))}
                    </ul>
                )}
            </SectionCard>

            <SectionCard title="Closing">{toText(data.closing) || '-'}</SectionCard>
            <SectionCard title="Social Summary">{toText(data.social_summary) || '-'}</SectionCard>

            <RawOutputDetails output={output} />
        </div>
    );
}

function RawOutputDetails({ output }: { output: ScriptOutputRecord }) {
    return (
        <details className="rounded-xl border border-white/10 bg-black/20 p-3">
            <summary className="cursor-pointer text-xs text-slate-300">Raw JSON</summary>
            <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-200 overflow-x-auto">
                {output.content_json ? JSON.stringify(output.content_json, null, 2) : output.content_text || '-'}
            </pre>
        </details>
    );
}

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
    return (
        <section className="rounded-xl border border-white/10 bg-white/5 p-3 space-y-2">
            <h5 className="text-xs font-semibold text-cyan-300 uppercase tracking-wide">{title}</h5>
            <div className="text-sm text-slate-100">{children}</div>
        </section>
    );
}

function toObject(value: unknown): Record<string, unknown> | null {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    return value as Record<string, unknown>;
}

function toObjectArray(value: unknown): Array<Record<string, unknown>> {
    if (!Array.isArray(value)) return [];
    return value
        .map((item) => toObject(item))
        .filter((item): item is Record<string, unknown> => Boolean(item));
}

function toStringArray(value: unknown): string[] {
    if (!Array.isArray(value)) return [];
    return value.map((item) => toText(item)).filter((item) => item.length > 0);
}

function toText(value: unknown): string {
    if (typeof value === 'string') return value.trim();
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    return '';
}
