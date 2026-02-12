'use client';

import { type PipelineRun } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { Activity, CheckCircle2, XCircle, Loader2 } from 'lucide-react';

interface PipelineMonitorProps {
    runs: PipelineRun[] | undefined;
    isLoading: boolean;
}

function RunRow({ run }: { run: PipelineRun }) {
    const statusIcon = {
        success: <CheckCircle2 className="w-4 h-4 text-emerald-400" />,
        failed: <XCircle className="w-4 h-4 text-red-400" />,
        running: <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />,
    }[run.status] || <Activity className="w-4 h-4 text-gray-400" />;

    const runTypeLabels: Record<string, string> = {
        scout: '🔍 كشّاف',
        router: '🧭 موجّه',
        scribe: '✍️ كاتب',
        trends: '📡 تراند',
        audio: '🎙️ مذيع',
    };

    return (
        <div className={cn(
            'flex items-center gap-3 px-4 py-3 rounded-xl transition-colors',
            'hover:bg-white/[0.03]',
            run.status === 'running' && 'bg-amber-500/5 border border-amber-500/10',
        )}>
            {statusIcon}

            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white">
                        {runTypeLabels[run.run_type] || run.run_type}
                    </span>
                    <span className={cn(
                        'px-1.5 py-0.5 rounded text-[9px] font-bold uppercase',
                        run.status === 'success' && 'bg-emerald-500/20 text-emerald-400',
                        run.status === 'failed' && 'bg-red-500/20 text-red-400',
                        run.status === 'running' && 'bg-amber-500/20 text-amber-400',
                    )}>
                        {run.status}
                    </span>
                </div>
                <p className="text-[10px] text-gray-500 mt-0.5">
                    {formatRelativeTime(run.started_at)}
                </p>
            </div>

            <div className="flex items-center gap-4 text-[10px] text-gray-500">
                <div className="text-center">
                    <p className="text-xs font-semibold text-white">{run.new_items}</p>
                    <p>جديد</p>
                </div>
                <div className="text-center">
                    <p className="text-xs font-semibold text-gray-400">{run.duplicates}</p>
                    <p>مكرر</p>
                </div>
                <div className="text-center">
                    <p className={cn('text-xs font-semibold', run.errors > 0 ? 'text-red-400' : 'text-gray-400')}>
                        {run.errors}
                    </p>
                    <p>أخطاء</p>
                </div>
            </div>
        </div>
    );
}

export default function PipelineMonitor({ runs, isLoading }: PipelineMonitorProps) {
    return (
        <div className="rounded-2xl bg-gray-800/20 border border-white/5 overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5">
                <Activity className="w-4 h-4 text-cyan-400" />
                <h2 className="text-sm font-semibold text-white">سجل خط الأنابيب</h2>
                <span className="text-[10px] text-gray-500">Pipeline Monitor</span>
            </div>

            <div className="p-2 space-y-1 max-h-[400px] overflow-y-auto">
                {isLoading ? (
                    Array.from({ length: 5 }).map((_, i) => (
                        <div key={i} className="h-16 rounded-xl bg-gray-800/30 animate-pulse" />
                    ))
                ) : runs && runs.length > 0 ? (
                    runs.map((run) => <RunRow key={run.id} run={run} />)
                ) : (
                    <div className="text-center py-8 text-gray-500 text-sm">
                        لا توجد عمليات سابقة
                    </div>
                )}
            </div>
        </div>
    );
}
