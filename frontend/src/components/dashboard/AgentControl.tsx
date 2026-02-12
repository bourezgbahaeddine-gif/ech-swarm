'use client';

import { useState } from 'react';
import { dashboardApi, type AgentStatus } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
    Search, Navigation, PenTool, Radio, Mic,
    Play, Loader2, CheckCircle, AlertCircle,
} from 'lucide-react';

interface AgentControlProps {
    agents: Record<string, AgentStatus> | undefined;
}

const agentConfig = [
    { key: 'scout', label: 'الكشّاف', labelEn: 'Scout', icon: Search, color: 'from-blue-500 to-cyan-500', trigger: 'triggerScout' as const },
    { key: 'router', label: 'الموجّه', labelEn: 'Router', icon: Navigation, color: 'from-purple-500 to-pink-500', trigger: 'triggerRouter' as const },
    { key: 'scribe', label: 'الكاتب', labelEn: 'Scribe', icon: PenTool, color: 'from-amber-500 to-orange-500', trigger: 'triggerScribe' as const },
    { key: 'trend_radar', label: 'رادار التراند', labelEn: 'Trends', icon: Radio, color: 'from-emerald-500 to-teal-500', trigger: 'triggerTrends' as const },
];

export default function AgentControl({ agents }: AgentControlProps) {
    const [running, setRunning] = useState<Record<string, boolean>>({});
    const [results, setResults] = useState<Record<string, { success: boolean; message: string }>>({});

    const handleTrigger = async (agentKey: string, triggerFn: keyof typeof dashboardApi) => {
        setRunning((prev) => ({ ...prev, [agentKey]: true }));
        setResults((prev) => ({ ...prev, [agentKey]: undefined as any }));

        try {
            const response = await dashboardApi[triggerFn]();
            setResults((prev) => ({
                ...prev,
                [agentKey]: { success: true, message: (response.data as any)?.message || 'تم التنفيذ بنجاح' },
            }));
        } catch (error: any) {
            setResults((prev) => ({
                ...prev,
                [agentKey]: { success: false, message: error.message || 'حدث خطأ' },
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
                    const agentStatus = agents?.[key];

                    return (
                        <div
                            key={key}
                            className={cn(
                                'relative rounded-xl p-4 border transition-all duration-300',
                                'bg-gradient-to-br from-gray-800/40 to-gray-900/60',
                                isRunning
                                    ? 'border-amber-500/30 shadow-lg shadow-amber-500/5'
                                    : 'border-white/5 hover:border-white/10',
                            )}
                        >
                            <div className="flex items-center gap-3 mb-3">
                                <div className={cn(
                                    'w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center shadow-lg',
                                    color,
                                )}>
                                    <Icon className="w-5 h-5 text-white" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">{label}</h3>
                                    <p className="text-[10px] text-gray-500">{labelEn}</p>
                                </div>
                                <span className="mr-auto w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                            </div>

                            <button
                                onClick={() => handleTrigger(key, trigger)}
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

                            {/* Result feedback */}
                            {result && (
                                <div className={cn(
                                    'mt-2 px-3 py-1.5 rounded-lg text-[10px] flex items-center gap-1.5',
                                    result.success ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400',
                                )}>
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
