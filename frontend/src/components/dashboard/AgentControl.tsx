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
    { key: 'scout', label: 'الكشاف', labelEn: 'Scout', icon: Search, color: 'from-blue-500 to-cyan-500', trigger: 'triggerScout' },
    { key: 'router', label: 'الموجه', labelEn: 'Router', icon: Navigation, color: 'from-purple-500 to-pink-500', trigger: 'triggerRouter' },
    { key: 'scribe', label: 'الكاتب', labelEn: 'Scribe', icon: PenTool, color: 'from-amber-500 to-orange-500', trigger: 'triggerScribe' },
    { key: 'trend_radar', label: 'رادار التراند', labelEn: 'Trends', icon: Radio, color: 'from-emerald-500 to-teal-500', trigger: 'triggerTrends' },
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
        <div className="rounded-2xl bg-gray-800/20 border border-white/5 overflow-hidden">
            <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5">
                <Play className="w-4 h-4 text-emerald-400" />
                <h2 className="text-sm font-semibold text-white">التحكم بالوكلاء</h2>
                <span className="text-[10px] text-gray-500">Agent Controls</span>
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
                                'bg-gradient-to-br from-gray-800/40 to-gray-900/60',
                                isRunning ? 'border-amber-500/30 shadow-lg shadow-amber-500/5' : 'border-white/5 hover:border-white/10',
                            )}
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <div className={cn('w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center shadow-lg', color)}>
                                    <Icon className="w-5 h-5 text-white" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">{label}</h3>
                                    <p className="text-[10px] text-gray-500">{labelEn}</p>
                                </div>
                                <span
                                    className={cn(
                                        'mr-auto w-2 h-2 rounded-full',
                                        hasAgent ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500/60',
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
                                    'w-full py-2 rounded-lg text-xs font-medium transition-all duration-200',
                                    'flex items-center justify-center gap-2',
                                    isRunning
                                        ? 'bg-amber-500/20 text-amber-400 cursor-wait'
                                        : 'bg-white/5 text-gray-300 hover:bg-emerald-500/20 hover:text-emerald-400',
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
                            </button>

                            {result && (
                                <div
                                    className={cn(
                                        'mt-2 px-3 py-1.5 rounded-lg text-[10px] flex items-center gap-1.5',
                                        result.success ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400',
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
