'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { dashboardApi, type AgentStatus } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
    AlertCircle,
    CheckCircle,
    Loader2,
    Navigation,
    PenTool,
    Play,
    Radio,
    Search,
} from 'lucide-react';

interface AgentControlProps {
    agents: Record<string, AgentStatus> | undefined;
}

type TriggerMethod = 'triggerScout' | 'triggerRouter' | 'triggerScribe' | 'triggerTrends';
type AgentResult = { success: boolean; message: string };

const agentConfig: Array<{
    key: string;
    label: string;
    labelEn: string;
    icon: import('react').ComponentType<{ className?: string }>;
    color: string;
    trigger: TriggerMethod;
}> = [
    { key: 'scout', label: 'الكشاف', labelEn: 'Scout', icon: Search, color: 'text-[var(--semantic-info)] bg-[var(--semantic-info-bg)] border-sky-200/70', trigger: 'triggerScout' },
    { key: 'router', label: 'الموجه', labelEn: 'Router', icon: Navigation, color: 'text-[var(--accent-blue)] bg-blue-50 border-blue-200/80', trigger: 'triggerRouter' },
    { key: 'scribe', label: 'الكاتب', labelEn: 'Scribe', icon: PenTool, color: 'text-[var(--semantic-warning)] bg-amber-50 border-amber-200/90', trigger: 'triggerScribe' },
    { key: 'trend_radar', label: 'رادار التراند', labelEn: 'Trends', icon: Radio, color: 'text-[var(--semantic-success)] bg-emerald-50 border-emerald-200/90', trigger: 'triggerTrends' },
];

export default function AgentControl({ agents }: AgentControlProps) {
    const queryClient = useQueryClient();
    const [running, setRunning] = useState<Record<string, boolean>>({});
    const [results, setResults] = useState<Record<string, AgentResult | undefined>>({});

    const handleTrigger = async (agentKey: string, triggerFn: TriggerMethod) => {
        setRunning((prev) => ({ ...prev, [agentKey]: true }));
        setResults((prev) => ({ ...prev, [agentKey]: undefined }));

        try {
            const response = await dashboardApi[triggerFn]();
            const payload = response.data as { message?: string } | undefined;

            setResults((prev) => ({
                ...prev,
                [agentKey]: {
                    success: true,
                    message: payload?.message || 'تم التنفيذ بنجاح',
                },
            }));

            const refresh = () => {
                queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
                queryClient.invalidateQueries({ queryKey: ['breaking-news'] });
                queryClient.invalidateQueries({ queryKey: ['pending-articles'] });
                queryClient.invalidateQueries({ queryKey: ['pipeline-runs'] });
                queryClient.invalidateQueries({ queryKey: ['agents-status'] });
            };
            refresh();
            setTimeout(refresh, 4000);
            setTimeout(refresh, 12000);
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : 'حدث خطأ أثناء التشغيل';
            setResults((prev) => ({
                ...prev,
                [agentKey]: { success: false, message },
            }));
        } finally {
            setRunning((prev) => ({ ...prev, [agentKey]: false }));
        }
    };

    return (
        <div className="rounded-2xl app-surface border overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-[var(--border-primary)]">
                <Play className="w-4 h-4 text-[var(--accent-blue)]" />
                <h2 className="text-sm font-semibold text-[var(--text-primary)]">التحكم بالوكلاء</h2>
                <span className="text-[10px] app-text-muted">Agent Controls</span>
            </div>

            <div className="p-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                {agentConfig.map(({ key, label, labelEn, icon: Icon, color, trigger }) => {
                    const isRunning = running[key];
                    const result = results[key];
                    const hasAgent = Boolean(agents?.[key]);

                    return (
                        <div
                            key={key}
                            role="button"
                            tabIndex={0}
                            onClick={() => !isRunning && handleTrigger(key, trigger)}
                            onKeyDown={(e) => {
                                if ((e.key === 'Enter' || e.key === ' ') && !isRunning) {
                                    e.preventDefault();
                                    handleTrigger(key, trigger);
                                }
                            }}
                            className={cn(
                                'relative rounded-xl p-4 border transition-all duration-300 cursor-pointer',
                                'app-surface',
                                isRunning ? 'border-amber-300 shadow-sm' : 'border-[var(--border-primary)] hover:border-gray-300',
                            )}
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <div className={cn('w-10 h-10 rounded-xl border flex items-center justify-center', color)}>
                                    <Icon className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-[var(--text-primary)]">{label}</h3>
                                    <p className="text-[10px] text-gray-500">{labelEn}</p>
                                </div>
                                <span
                                    className={cn(
                                        'mr-auto w-2 h-2 rounded-full',
                                        hasAgent ? 'bg-[var(--semantic-success)] animate-pulse' : 'bg-gray-400',
                                    )}
                                />
                            </div>

                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleTrigger(key, trigger);
                                }}
                                disabled={isRunning}
                                className={cn(
                                    'w-full py-2 rounded-lg text-xs font-medium transition-all duration-200 border',
                                    'flex items-center justify-between px-3',
                                    isRunning
                                        ? 'bg-amber-50 text-amber-700 border border-amber-200 cursor-wait'
                                        : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-100 hover:text-gray-900',
                                )}
                            >
                                {isRunning ? (
                                    <>
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                        جاري التنفيذ...
                                    </>
                                ) : (
                                    <>
                                        <Play className="w-3.5 h-3.5" />
                                        تشغيل
                                    </>
                                )}
                            
                                <span className={cn(
                                    'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
                                    isRunning ? 'bg-amber-400' : 'bg-[#2563EB]'
                                )}>
                                    <span className={cn(
                                        'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                                        isRunning ? 'translate-x-1' : '-translate-x-4'
                                    )} />
                                </span>
                            </button>

                            {result && (
                                <div
                                    className={cn(
                                        'mt-2 px-3 py-1.5 rounded-lg text-[10px] flex items-center gap-1.5',
                                        result.success ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200',
                                    )}
                                >
                                    {result.success ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
                                    {result.message}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
