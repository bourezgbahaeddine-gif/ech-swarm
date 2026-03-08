'use client';

import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    AlertTriangle,
    Bot,
    CheckCircle2,
    ExternalLink,
    Loader2,
    Play,
    RefreshCw,
    ShieldCheck,
} from 'lucide-react';
import { dashboardApi, jobsApi, type QueueSlaItem } from '@/lib/api';
import PipelineMonitor from '@/components/dashboard/PipelineMonitor';
import { formatRelativeTime } from '@/lib/utils';
import { useAuth } from '@/lib/auth';

type TriggerMethod = 'triggerScout' | 'triggerRouter' | 'triggerScribe' | 'triggerTrends';

const emergencyActions: Array<{ id: TriggerMethod; label: string }> = [
    { id: 'triggerScout', label: 'إعادة تشغيل الكشاف' },
    { id: 'triggerRouter', label: 'إعادة تشغيل الموجّه' },
    { id: 'triggerScribe', label: 'إعادة تشغيل الكاتب' },
    { id: 'triggerTrends', label: 'تحديث رادار التراند' },
];

const FLOWER_BASE_URL = process.env.NEXT_PUBLIC_FLOWER_URL || 'http://127.0.0.1:5555';

export default function AgentsPage() {
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const role = (user?.role || '').toLowerCase();
    const isDirector = role === 'director';

    const { data: agentsData, isLoading: agentsLoading } = useQuery({
        queryKey: ['agents-status'],
        queryFn: () => dashboardApi.agentStatus(),
        enabled: isDirector,
        refetchInterval: 20000,
    });

    const { data: pipelineData, isLoading: pipelineLoading } = useQuery({
        queryKey: ['pipeline-runs-full'],
        queryFn: () => dashboardApi.pipelineRuns(30),
        enabled: isDirector,
        refetchInterval: 15000,
    });

    const { data: failedData } = useQuery({
        queryKey: ['failed-jobs'],
        queryFn: () => dashboardApi.failedJobs(),
        enabled: isDirector,
        refetchInterval: 15000,
    });

    const { data: jobsSlaData, isLoading: jobsSlaLoading } = useQuery({
        queryKey: ['jobs-sla'],
        queryFn: () => jobsApi.getSla({ lookback_hours: 24 }),
        enabled: isDirector,
        refetchInterval: 15000,
    });

    const runEmergencyAction = useMutation({
        mutationFn: async (method: TriggerMethod) => {
            if (method === 'triggerTrends') {
                return dashboardApi.triggerTrends({ geo: 'DZ', category: 'all' });
            }
            return dashboardApi[method]();
        },
        onSuccess: async () => {
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ['agents-status'] }),
                queryClient.invalidateQueries({ queryKey: ['pipeline-runs-full'] }),
                queryClient.invalidateQueries({ queryKey: ['pipeline-runs'] }),
                queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] }),
                queryClient.invalidateQueries({ queryKey: ['breaking-news'] }),
                queryClient.invalidateQueries({ queryKey: ['pending-articles'] }),
                queryClient.invalidateQueries({ queryKey: ['jobs-sla'] }),
            ]);
        },
    });

    const recoverStaleJobs = useMutation({
        mutationFn: async () => jobsApi.recoverStale({ stale_running_minutes: 15, stale_queued_minutes: 30 }),
        onSuccess: async () => {
            await Promise.all([
                queryClient.invalidateQueries({ queryKey: ['jobs-sla'] }),
                queryClient.invalidateQueries({ queryKey: ['failed-jobs'] }),
                queryClient.invalidateQueries({ queryKey: ['pipeline-runs-full'] }),
            ]);
        },
    });

    if (!isDirector) {
        return (
            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 space-y-4">
                <div className="flex items-center gap-2 text-white">
                    <ShieldCheck className="w-5 h-5 text-cyan-300" />
                    <h1 className="text-lg font-semibold">مراقبة النظام</h1>
                </div>
                <p className="text-sm text-gray-300 leading-7">
                    هذه الصفحة تشغيلية للمدير فقط. متابعة العمل التحريري اليومي تتم من صفحة الأخبار والمحرر الذكي.
                </p>
                <Link
                    href="/news"
                    className="inline-flex items-center rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200"
                >
                    العودة إلى الأخبار
                </Link>
            </div>
        );
    }

    const failedJobs = (failedData?.data || []) as Array<{ id: number }>;
    const pipelineRuns = pipelineData?.data || [];
    const agentEntries = Object.entries(agentsData?.data || {});
    const healthyAgents = agentEntries.filter(([, v]) => v?.status === 'healthy' || v?.status === 'running').length;
    const totalAgents = agentEntries.length;
    const lastRun = pipelineRuns[0]?.started_at;
    const queueSlaRows = (jobsSlaData?.data?.queues || []) as QueueSlaItem[];
    const breachedQueues = queueSlaRows.filter((row) => row.SLA_breached);
    const driftQueues = queueSlaRows.filter((row) => row.state_drift_suspected);
    const totalDepth = queueSlaRows.reduce((sum, row) => sum + Math.max(0, row.depth || 0), 0);
    const worstQueue = [...queueSlaRows].sort(
        (a, b) =>
            Number(b.SLA_breached) - Number(a.SLA_breached) ||
            (b.depth || 0) - (a.depth || 0) ||
            (b.oldest_task_age || 0) - (a.oldest_task_age || 0)
    )[0];

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Bot className="w-6 h-6 text-cyan-300" />
                        مراقبة النظام
                    </h1>
                    <p className="text-sm text-gray-400 mt-1">
                        تشغيل الوكلاء يتم تلقائياً في الخلفية. الإجراءات اليدوية هنا للطوارئ فقط.
                    </p>
                </div>
                <button
                    onClick={() => {
                        queryClient.invalidateQueries({ queryKey: ['agents-status'] });
                        queryClient.invalidateQueries({ queryKey: ['pipeline-runs-full'] });
                        queryClient.invalidateQueries({ queryKey: ['failed-jobs'] });
                        queryClient.invalidateQueries({ queryKey: ['jobs-sla'] });
                    }}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs text-gray-200 hover:text-white"
                >
                    <RefreshCw className="w-3.5 h-3.5" />
                    تحديث الحالة
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
                    <p className="text-xs text-emerald-200/80">سلامة الوكلاء</p>
                    <p className="text-2xl font-semibold text-white mt-1">
                        {agentsLoading ? '...' : `${healthyAgents}/${totalAgents || 0}`}
                    </p>
                </div>
                <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4">
                    <p className="text-xs text-cyan-200/80">آخر تشغيل</p>
                    <p className="text-sm text-white mt-2">
                        {lastRun ? formatRelativeTime(lastRun) : 'لا يوجد تشغيل مسجل'}
                    </p>
                </div>
                <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-4">
                    <p className="text-xs text-red-200/80">مهام فاشلة (DLQ)</p>
                    <p className="text-2xl font-semibold text-white mt-1">{failedJobs.length}</p>
                </div>
            </div>

            <section className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <h2 className="text-sm font-semibold text-white">Jobs Health (Queue SLA)</h2>
                        <p className="text-xs text-gray-400 mt-1">
                            مراقبة مباشرة للطوابير مع روابط Flower وخطوات المعالجة السريعة.
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => recoverStaleJobs.mutate()}
                            disabled={recoverStaleJobs.isPending}
                            className="inline-flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200 hover:text-amber-100 disabled:opacity-60"
                        >
                            {recoverStaleJobs.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                            Recover Stale Jobs
                        </button>
                        <a
                            href={FLOWER_BASE_URL}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200 hover:text-cyan-100"
                        >
                            فتح Flower
                            <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div className="rounded-xl border border-amber-500/25 bg-amber-500/10 p-3">
                        <p className="text-[11px] text-amber-200/80">SLA Breaches</p>
                        <p className="text-xl font-semibold text-white mt-1">{breachedQueues.length}</p>
                    </div>
                    <div className="rounded-xl border border-blue-500/25 bg-blue-500/10 p-3">
                        <p className="text-[11px] text-blue-200/80">إجمالي عمق الطوابير</p>
                        <p className="text-xl font-semibold text-white mt-1">{totalDepth}</p>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/5 p-3">
                        <p className="text-[11px] text-gray-300">أسوأ Queue حالياً</p>
                        <p className="text-sm font-semibold text-white mt-1">{worstQueue?.queue_name || '—'}</p>
                        {driftQueues.length > 0 && (
                            <p className="text-[10px] text-amber-300 mt-1">state_drift: {driftQueues.length}</p>
                        )}
                    </div>
                </div>

                {recoverStaleJobs.isSuccess && (
                    <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-[11px] text-emerald-200">
                        stale recovery done: running_failed={recoverStaleJobs.data?.data?.running_failed ?? 0}, queued_failed={recoverStaleJobs.data?.data?.queued_failed ?? 0}
                    </div>
                )}

                <div className="overflow-x-auto rounded-xl border border-white/10">
                    <table className="min-w-full text-xs text-right">
                        <thead className="bg-white/5 text-gray-300">
                            <tr>
                                <th className="px-3 py-2">Queue</th>
                                <th className="px-3 py-2">Depth</th>
                                <th className="px-3 py-2">DB Active</th>
                                <th className="px-3 py-2">Oldest (min)</th>
                                <th className="px-3 py-2">Runtime (min)</th>
                                <th className="px-3 py-2">Failure 24h</th>
                                <th className="px-3 py-2">SLA Target</th>
                                <th className="px-3 py-2">الحالة</th>
                                <th className="px-3 py-2">Flower</th>
                            </tr>
                        </thead>
                        <tbody>
                            {jobsSlaLoading && (
                                <tr>
                                    <td colSpan={9} className="px-3 py-4 text-center text-gray-400">
                                        جاري تحميل مؤشرات SLA...
                                    </td>
                                </tr>
                            )}
                            {!jobsSlaLoading &&
                                queueSlaRows.map((row) => (
                                    <tr
                                        key={row.queue_name}
                                        className={row.SLA_breached ? 'border-t border-red-500/20 bg-red-500/5' : 'border-t border-white/10'}
                                    >
                                        <td className="px-3 py-2 text-white">{row.queue_name}</td>
                                        <td className="px-3 py-2 text-gray-200">
                                            {row.depth}/{row.depth_limit}
                                        </td>
                                        <td className="px-3 py-2 text-gray-200">
                                            {(row.active_running_jobs || 0) + (row.active_queued_jobs || 0)} ({row.active_running_jobs || 0}/{row.active_queued_jobs || 0})
                                        </td>
                                        <td className="px-3 py-2 text-gray-200">{Number(row.oldest_task_age || 0).toFixed(1)}</td>
                                        <td className="px-3 py-2 text-gray-200">{Number(row.mean_runtime || 0).toFixed(1)}</td>
                                        <td className="px-3 py-2 text-gray-200">
                                            {Number(row.failure_rate_24h || 0).toFixed(1)}%
                                            {(row.stale_failures_excluded_24h || 0) > 0 && (
                                                <span className="mr-1 text-[10px] text-amber-300">
                                                    (stale:{row.stale_failures_excluded_24h})
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-3 py-2 text-gray-200">{row.SLA_target_minutes}m</td>
                                        <td className="px-3 py-2">
                                            {row.state_drift_suspected ? (
                                                <span className="inline-flex rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-200">
                                                    Drift
                                                </span>
                                            ) : row.SLA_breached ? (
                                                <span className="inline-flex rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1 text-[11px] text-red-200">
                                                    Breached
                                                </span>
                                            ) : (
                                                <span className="inline-flex rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-200">
                                                    OK
                                                </span>
                                            )}
                                        </td>
                                        <td className="px-3 py-2">
                                            <a
                                                href={`${FLOWER_BASE_URL}?queue=${encodeURIComponent(row.queue_name)}`}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="inline-flex items-center gap-1 text-cyan-300 hover:text-cyan-200"
                                            >
                                                فتح
                                                <ExternalLink className="w-3 h-3" />
                                            </a>
                                        </td>
                                    </tr>
                                ))}
                            {!jobsSlaLoading && queueSlaRows.length === 0 && (
                                <tr>
                                    <td colSpan={9} className="px-3 py-4 text-center text-gray-500">
                                        لا توجد بيانات SLA حالياً.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>

                <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-[11px] text-amber-100 space-y-1">
                    <p>إجراءات سريعة عند وجود Breach:</p>
                    <p>1) إذا depth مرتفع: زِد عدد الـ workers أو خفّض الطلبات اليدوية مؤقتاً.</p>
                    <p>2) إذا failure rate مرتفع: راجع المهام الفاشلة في Flower ثم أصلح سبب الفشل المتكرر.</p>
                    <p>3) إذا oldest task age مرتفع: نفّذ `/api/v1/jobs/recover/stale` بعد التحقق من السجل.</p>
                </div>
            </section>

            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle className="w-4 h-4 text-amber-300" />
                    <h2 className="text-sm font-semibold text-white">إجراءات طوارئ (اختياري)</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {emergencyActions.map((action) => (
                        <button
                            key={action.id}
                            onClick={() => runEmergencyAction.mutate(action.id)}
                            disabled={runEmergencyAction.isPending}
                            className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs text-gray-200 hover:text-white disabled:opacity-60"
                        >
                            {runEmergencyAction.isPending ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                                <Play className="w-3.5 h-3.5" />
                            )}
                            {action.label}
                        </button>
                    ))}
                </div>
                <p className="text-[11px] text-gray-500 mt-3">
                    استخدم هذه الأزرار فقط عند توقف مهام الخلفية أو بطء واضح في دورة الأخبار.
                </p>
                {runEmergencyAction.isSuccess && (
                    <div className="mt-2 inline-flex items-center gap-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-200">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        تم تنفيذ الإجراء بنجاح.
                    </div>
                )}
            </div>

            <PipelineMonitor runs={pipelineRuns} isLoading={pipelineLoading} />
        </div>
    );
}
