'use client';

import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    AlertTriangle,
    Bot,
    CheckCircle2,
    Loader2,
    Play,
    RefreshCw,
    ShieldCheck,
} from 'lucide-react';
import { dashboardApi } from '@/lib/api';
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
