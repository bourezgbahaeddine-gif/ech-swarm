'use client';

import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '@/lib/api';
import AgentControl from '@/components/dashboard/AgentControl';
import PipelineMonitor from '@/components/dashboard/PipelineMonitor';
import { Bot, Activity, Cpu, Wifi } from 'lucide-react';

export default function AgentsPage() {
    type FailedJob = {
        id: number;
        type: string;
        error: string;
        retries: number;
        created_at: string;
    };

    const { data: agentsData } = useQuery({
        queryKey: ['agents-status'],
        queryFn: () => dashboardApi.agentStatus(),
    });

    const { data: pipelineData, isLoading: pipelineLoading } = useQuery({
        queryKey: ['pipeline-runs-full'],
        queryFn: () => dashboardApi.pipelineRuns(30),
    });

    const { data: failedData } = useQuery({
        queryKey: ['failed-jobs'],
        queryFn: () => dashboardApi.failedJobs(),
    });

    const failedJobs = (failedData?.data || []) as FailedJob[];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                    <Bot className="w-7 h-7 text-indigo-400" />
                    مركز التحكم بالوكلاء
                </h1>
                <p className="text-sm text-gray-500 mt-1">إدارة وتشغيل الوكلاء الذكيون ومراقبة خط الأنابيب</p>
            </div>

            {/* System Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-2xl p-5 bg-gradient-to-br from-indigo-500/10 to-purple-500/5 border border-indigo-500/10">
                    <div className="flex items-center gap-3 mb-2">
                        <Cpu className="w-5 h-5 text-indigo-400" />
                        <h3 className="text-sm font-semibold text-white">الوكلاء النشطون</h3>
                    </div>
                    <p className="text-3xl font-bold text-white">5</p>
                    <p className="text-xs text-gray-500 mt-1">جميع الوكلاء جاهزون</p>
                </div>

                <div className="rounded-2xl p-5 bg-gradient-to-br from-emerald-500/10 to-teal-500/5 border border-emerald-500/10">
                    <div className="flex items-center gap-3 mb-2">
                        <Activity className="w-5 h-5 text-emerald-400" />
                        <h3 className="text-sm font-semibold text-white">العمليات اليوم</h3>
                    </div>
                    <p className="text-3xl font-bold text-white">{pipelineData?.data?.length || 0}</p>
                    <p className="text-xs text-gray-500 mt-1">عملية مسجّلة</p>
                </div>

                <div className="rounded-2xl p-5 bg-gradient-to-br from-red-500/10 to-orange-500/5 border border-red-500/10">
                    <div className="flex items-center gap-3 mb-2">
                        <Wifi className="w-5 h-5 text-red-400" />
                        <h3 className="text-sm font-semibold text-white">المهام الفاشلة</h3>
                    </div>
                    <p className="text-3xl font-bold text-white">{failedJobs.length}</p>
                    <p className="text-xs text-gray-500 mt-1">في صف الانتظار (DLQ)</p>
                </div>
            </div>

            {/* Controls + Pipeline */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <AgentControl agents={agentsData?.data} />
                <PipelineMonitor runs={pipelineData?.data} isLoading={pipelineLoading} />
            </div>

            {/* Failed Jobs (DLQ) */}
            {failedJobs.length > 0 && (
                <div className="rounded-2xl bg-red-500/5 border border-red-500/10 overflow-hidden">
                    <div className="flex items-center gap-2 px-5 py-3 border-b border-red-500/10">
                        <Wifi className="w-4 h-4 text-red-400" />
                        <h2 className="text-sm font-semibold text-white">Dead Letter Queue</h2>
                    </div>
                    <div className="p-3 space-y-2 max-h-[300px] overflow-y-auto">
                        {failedJobs.map((job) => (
                            <div key={job.id} className="px-4 py-3 rounded-xl bg-gray-800/30 border border-white/[0.03]">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-medium text-white">{job.type}</span>
                                    <span className="text-[10px] text-gray-500">{job.created_at}</span>
                                </div>
                                <p className="text-[11px] text-red-400 mt-1 font-mono">{job.error}</p>
                                <span className="text-[10px] text-gray-600">محاولات: {job.retries}/3</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
