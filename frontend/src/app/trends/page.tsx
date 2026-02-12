'use client';

import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { dashboardApi, type TrendAlert } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
    TrendingUp, Radar, Flame, Lightbulb, Search,
    Loader2, ArrowUpRight, Radio,
} from 'lucide-react';

export default function TrendsPage() {
    const [trends, setTrends] = useState<TrendAlert[]>([]);

    const scanMutation = useMutation({
        mutationFn: () => dashboardApi.triggerTrends(),
        onSuccess: (response) => {
            const alerts = (response.data as any)?.alerts || [];
            setTrends(alerts);
        },
    });

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <TrendingUp className="w-7 h-7 text-emerald-400" />
                        رادار التراند
                    </h1>
                    <p className="text-sm text-gray-500 mt-1">اكتشاف الاتجاهات الصاعدة عبر التحقق المتبادل بين المصادر</p>
                </div>
                <button
                    onClick={() => scanMutation.mutate()}
                    disabled={scanMutation.isPending}
                    className={cn(
                        'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all',
                        scanMutation.isPending
                            ? 'bg-amber-500/20 text-amber-400 cursor-wait'
                            : 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white hover:shadow-lg hover:shadow-emerald-500/20',
                    )}
                >
                    {scanMutation.isPending ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            جاري المسح...
                        </>
                    ) : (
                        <>
                            <Radar className="w-4 h-4" />
                            مسح الآن
                        </>
                    )}
                </button>
            </div>

            {/* How it works */}
            <div className="rounded-2xl bg-gradient-to-br from-gray-800/30 to-gray-900/40 border border-white/5 p-5">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                    <Radio className="w-4 h-4 text-cyan-400" />
                    كيف يعمل الرادار؟
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                        { step: '1', title: 'مسح المصادر', desc: 'Google Trends + RSS + المنافسون', color: 'text-blue-400' },
                        { step: '2', title: 'التحقق المتبادل', desc: 'تأكيد الظهور في مصدرين+ مستقلين', color: 'text-purple-400' },
                        { step: '3', title: 'تحليل ذكي', desc: 'Gemini Flash يقترح زوايا تحريرية', color: 'text-emerald-400' },
                    ].map(({ step, title, desc, color }) => (
                        <div key={step} className="flex items-start gap-3">
                            <div className={cn('w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-sm font-bold flex-shrink-0', color)}>
                                {step}
                            </div>
                            <div>
                                <p className="text-sm font-medium text-white">{title}</p>
                                <p className="text-xs text-gray-500 mt-0.5">{desc}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Results */}
            {trends.length > 0 && (
                <div className="space-y-3">
                    <h3 className="text-sm font-semibold text-white">
                        🔥 {trends.length} تراند مؤكّد
                    </h3>

                    {trends.map((trend, index) => (
                        <div
                            key={index}
                            className="rounded-2xl bg-gradient-to-br from-gray-800/40 to-gray-900/60 border border-white/5 hover:border-emerald-500/20 transition-all p-5"
                            style={{ animationDelay: `${index * 100}ms` }}
                        >
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-3">
                                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center shadow-lg">
                                        <Flame className="w-5 h-5 text-white" />
                                    </div>
                                    <div>
                                        <h3 className="text-base font-bold text-white">{trend.keyword}</h3>
                                        <div className="flex items-center gap-2 mt-0.5">
                                            {trend.source_signals.map((signal, i) => (
                                                <span key={i} className="px-1.5 py-0.5 rounded bg-white/5 text-[9px] text-gray-400">{signal}</span>
                                            ))}
                                        </div>
                                    </div>
                                </div>

                                {/* Strength meter */}
                                <div className="flex items-center gap-2">
                                    <div className="flex gap-0.5">
                                        {Array.from({ length: 10 }).map((_, i) => (
                                            <div
                                                key={i}
                                                className={cn(
                                                    'w-2 h-5 rounded-sm transition-all',
                                                    i < trend.strength
                                                        ? i < 4 ? 'bg-yellow-500' : i < 7 ? 'bg-orange-500' : 'bg-red-500'
                                                        : 'bg-gray-700',
                                                )}
                                            />
                                        ))}
                                    </div>
                                    <span className="text-xs font-bold text-white">{trend.strength}/10</span>
                                </div>
                            </div>

                            {/* Reason */}
                            {trend.reason && (
                                <p className="text-sm text-gray-300 mb-3 leading-relaxed" dir="rtl">
                                    {trend.reason}
                                </p>
                            )}

                            {/* Suggested Angles */}
                            {trend.suggested_angles.length > 0 && (
                                <div className="mb-3">
                                    <h4 className="text-xs font-semibold text-amber-400 mb-2 flex items-center gap-1">
                                        <Lightbulb className="w-3.5 h-3.5" />
                                        مقترحات العناوين
                                    </h4>
                                    <div className="space-y-1">
                                        {trend.suggested_angles.map((angle, i) => (
                                            <div key={i} className="flex items-center gap-2 text-sm text-gray-300">
                                                <ArrowUpRight className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                                                {angle}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Archive Keywords */}
                            {trend.archive_matches.length > 0 && (
                                <div className="flex items-center gap-2 flex-wrap">
                                    <Search className="w-3.5 h-3.5 text-gray-500" />
                                    {trend.archive_matches.map((kw, i) => (
                                        <span key={i} className="px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 text-[10px]">
                                            {kw}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Empty state */}
            {!scanMutation.isPending && trends.length === 0 && (
                <div className="text-center py-20 rounded-2xl bg-gray-800/20 border border-white/5">
                    <Radar className="w-16 h-16 text-gray-700 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-white">اضغط &quot;مسح الآن&quot; للبدء</h3>
                    <p className="text-sm text-gray-500 mt-1">سيقوم الرادار بفحص Google Trends، المنافسون، ومصادر RSS</p>
                </div>
            )}
        </div>
    );
}
