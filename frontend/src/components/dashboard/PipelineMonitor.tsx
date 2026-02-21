'use client';

import { useRouter } from 'next/navigation';
import { type PipelineRun } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { Activity, CheckCircle2, XCircle, Loader2 } from 'lucide-react';

interface PipelineMonitorProps {
    runs: PipelineRun[] | undefined;
    isLoading: boolean;
}

function getRunTarget(runType: string) {
    const t = (runType || '').toLowerCase();
    if (t === 'trends') return '/trends';
    if (t === 'scout' || t === 'router' || t === 'scribe') return '/agents';
    return '/agents';
}

function RunRow({ run, onOpen }: { run: PipelineRun; onOpen: (href: string) => void }) {
    const statusIcon = {
        success: <CheckCircle2 className="w-4 h-4 text-emerald-600" />,
        failed: <XCircle className="w-4 h-4 text-red-600" />,
        running: <Loader2 className="w-4 h-4 text-amber-600 animate-spin" />,
    }[run.status] || <Activity className="w-4 h-4 text-gray-500" />;

    const runTypeLabels: Record<string, string> = {
        scout: 'كشّاف',
        router: 'موجّه',
        scribe: 'كاتب',
        trends: 'تراند',
        audio: 'مذيع',
    };

    return (
        <button
            onClick={() => onOpen(getRunTarget(run.run_type))}
            className={cn(
                'w-full text-right flex items-center gap-3 px-4 py-3 rounded-xl transition-colors',
                'hover:bg-gray-100 cursor-pointer',
                run.status === 'running' && 'bg-amber-50 border border-amber-200',
            )}
        >
            {statusIcon}

            <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-[var(--text-primary)]">{runTypeLabels[run.run_type] || run.run_type}</span>
                    <span
                        className={cn(
                            'px-1.5 py-0.5 rounded text-[9px] font-bold uppercase',
                            run.status === 'success' && 'bg-emerald-50 text-emerald-700',
                            run.status === 'failed' && 'bg-red-50 text-red-700',
                            run.status === 'running' && 'bg-amber-50 text-amber-700',
                        )}
                    >
                        {run.status}
                    </span>
                </div>
                <p className="text-[10px] app-text-muted mt-0.5">{formatRelativeTime(run.started_at)}</p>
            </div>

            <div className="flex items-center gap-4 text-[10px] app-text-muted">
                <div className="text-center">
                    <p className="text-xs font-semibold text-[var(--text-primary)]">{run.new_items}</p>
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
        </button>
    );
}

export default function PipelineMonitor({ runs, isLoading }: PipelineMonitorProps) {
    const router = useRouter();

    return (
        <div className="rounded-2xl app-surface border overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-[var(--border-primary)]">
                <Activity className="w-4 h-4 text-[var(--semantic-info)]" />
                <h2 className="text-sm font-semibold text-[var(--text-primary)]">سجل خط الأنابيب</h2>
                <span className="text-[10px] text-gray-500">Pipeline Monitor</span>
            </div>

            <div className="p-2 space-y-1 max-h-[400px] overflow-y-auto">
                {isLoading ? (
                    Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 rounded-xl app-surface-soft border animate-pulse" />)
                ) : runs && runs.length > 0 ? (
                    runs.map((run) => <RunRow key={run.id} run={run} onOpen={(href) => router.push(href)} />)
                ) : (
                    <div className="text-center py-8 app-text-muted text-sm">لا توجد عمليات سابقة</div>
                )}
            </div>
        </div>
    );
}
