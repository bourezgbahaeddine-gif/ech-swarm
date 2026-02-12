'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sourcesApi, type Source } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { useState } from 'react';
import {
    Rss, Plus, Globe, CheckCircle, XCircle,
    AlertTriangle, Clock, ExternalLink, Trash2,
    ToggleLeft, ToggleRight,
} from 'lucide-react';

export default function SourcesPage() {
    const queryClient = useQueryClient();
    const [showAdd, setShowAdd] = useState(false);
    const [newSource, setNewSource] = useState({ name: '', url: '', category: 'general', priority: 5 });

    const { data: sourcesData, isLoading } = useQuery({
        queryKey: ['sources'],
        queryFn: () => sourcesApi.list(),
    });

    const { data: statsData } = useQuery({
        queryKey: ['sources-stats'],
        queryFn: () => sourcesApi.stats(),
    });

    const createMutation = useMutation({
        mutationFn: (data: Partial<Source>) => sourcesApi.create(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['sources'] });
            setShowAdd(false);
            setNewSource({ name: '', url: '', category: 'general', priority: 5 });
        },
    });

    const toggleMutation = useMutation({
        mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => sourcesApi.update(id, { enabled }),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
    });

    const deleteMutation = useMutation({
        mutationFn: (id: number) => sourcesApi.delete(id),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
    });

    const sources = sourcesData?.data || [];

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <Rss className="w-7 h-7 text-orange-400" />
                        المصادر
                    </h1>
                    <p className="text-sm text-gray-500 mt-1">
                        {sources.length} مصدر مسجّل — {sources.filter(s => s.enabled).length} نشط
                    </p>
                </div>
                <button
                    onClick={() => setShowAdd(!showAdd)}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors text-sm font-medium"
                >
                    <Plus className="w-4 h-4" />
                    إضافة مصدر
                </button>
            </div>

            {/* Add Source Form */}
            {showAdd && (
                <div className="rounded-2xl bg-gray-800/30 border border-emerald-500/20 p-5 animate-fade-in-up">
                    <h3 className="text-sm font-semibold text-white mb-4">مصدر جديد</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                            placeholder="اسم المصدر"
                            value={newSource.name}
                            onChange={(e) => setNewSource(p => ({ ...p, name: e.target.value }))}
                            className="h-10 px-4 rounded-xl bg-white/5 border border-white/5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-emerald-500/40"
                            dir="rtl"
                        />
                        <input
                            placeholder="رابط RSS"
                            value={newSource.url}
                            onChange={(e) => setNewSource(p => ({ ...p, url: e.target.value }))}
                            className="h-10 px-4 rounded-xl bg-white/5 border border-white/5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-emerald-500/40"
                            dir="ltr"
                        />
                        <select
                            value={newSource.category}
                            onChange={(e) => setNewSource(p => ({ ...p, category: e.target.value }))}
                            className="h-10 px-3 rounded-xl bg-white/5 border border-white/5 text-sm text-gray-300 focus:outline-none"
                        >
                            <option value="general">عام</option>
                            <option value="official">رسمي</option>
                            <option value="media_dz">إعلام جزائري</option>
                            <option value="international">دولي</option>
                            <option value="sports">رياضة</option>
                            <option value="economy">اقتصاد</option>
                            <option value="culture">ثقافة</option>
                        </select>
                        <div className="flex gap-2">
                            <button
                                onClick={() => createMutation.mutate(newSource)}
                                disabled={!newSource.name || !newSource.url || createMutation.isPending}
                                className="flex-1 h-10 rounded-xl bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-30 transition-colors"
                            >
                                حفظ
                            </button>
                            <button
                                onClick={() => setShowAdd(false)}
                                className="h-10 px-4 rounded-xl bg-white/5 text-gray-400 text-sm hover:text-white transition-colors"
                            >
                                إلغاء
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Sources Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {isLoading ? (
                    Array.from({ length: 9 }).map((_, i) => (
                        <div key={i} className="h-32 rounded-2xl bg-gray-800/30 border border-white/5 animate-pulse" />
                    ))
                ) : (
                    sources.map((source: Source) => (
                        <div
                            key={source.id}
                            className={cn(
                                'rounded-2xl p-4 border transition-all duration-200',
                                'bg-gradient-to-br from-gray-800/40 to-gray-900/60',
                                source.enabled ? 'border-white/5 hover:border-white/10' : 'border-white/[0.02] opacity-50',
                            )}
                        >
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-2">
                                    <Globe className="w-4 h-4 text-gray-500" />
                                    <h3 className="text-sm font-semibold text-white">{source.name}</h3>
                                </div>
                                <button
                                    onClick={() => toggleMutation.mutate({ id: source.id, enabled: !source.enabled })}
                                    className="text-gray-400 hover:text-white transition-colors"
                                >
                                    {source.enabled ? (
                                        <ToggleRight className="w-5 h-5 text-emerald-400" />
                                    ) : (
                                        <ToggleLeft className="w-5 h-5" />
                                    )}
                                </button>
                            </div>

                            <div className="space-y-1.5 text-[11px]">
                                <div className="flex items-center gap-2 text-gray-500">
                                    <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-400">{source.category}</span>
                                    <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-400">{source.language}</span>
                                    <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-400">P{source.priority}</span>
                                </div>

                                <div className="flex items-center justify-between text-gray-500">
                                    <span className="flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {source.last_fetched_at ? formatRelativeTime(source.last_fetched_at) : 'لم يُجلب بعد'}
                                    </span>
                                    {source.error_count > 0 && (
                                        <span className="flex items-center gap-1 text-red-400">
                                            <AlertTriangle className="w-3 h-3" />
                                            {source.error_count} أخطاء
                                        </span>
                                    )}
                                </div>

                                <div className="flex items-center gap-2 mt-2">
                                    <div className="flex-1 h-1.5 rounded-full bg-gray-700 overflow-hidden">
                                        <div
                                            className="h-full rounded-full bg-emerald-400 transition-all"
                                            style={{ width: `${source.trust_score * 100}%` }}
                                        />
                                    </div>
                                    <span className="text-[10px] text-gray-500">{Math.round(source.trust_score * 100)}%</span>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/[0.03]">
                                <a
                                    href={source.url}
                                    target="_blank"
                                    rel="noopener"
                                    className="text-[10px] text-gray-500 hover:text-emerald-400 flex items-center gap-1 transition-colors"
                                >
                                    <ExternalLink className="w-3 h-3" /> RSS
                                </a>
                                <button
                                    onClick={() => deleteMutation.mutate(source.id)}
                                    className="text-gray-600 hover:text-red-400 transition-colors mr-auto"
                                >
                                    <Trash2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
