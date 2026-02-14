'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { editorialApi, type WorkspaceDraft } from '@/lib/api';
import { cn, formatRelativeTime, truncate } from '@/lib/utils';
import { Search, CheckCircle2, FileText, Filter } from 'lucide-react';

export default function WorkspaceDraftsPage() {
    const queryClient = useQueryClient();
    const [status, setStatus] = useState('draft');
    const [q, setQ] = useState('');
    const [selected, setSelected] = useState<WorkspaceDraft | null>(null);
    const [error, setError] = useState<string | null>(null);

    const { data, isLoading } = useQuery({
        queryKey: ['workspace-drafts', status],
        queryFn: () => editorialApi.workspaceDrafts({ status, limit: 200 }),
    });

    const applyMutation = useMutation({
        mutationFn: (workId: string) => editorialApi.applyWorkspaceDraft(workId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['workspace-drafts'] });
            queryClient.invalidateQueries({ queryKey: ['news'] });
            setSelected(null);
            setError(null);
        },
        onError: (err: any) => setError(err?.response?.data?.detail || 'تعذر تطبيق المسودة'),
    });

    const drafts = data?.data || [];
    const filtered = useMemo(() => {
        const needle = q.trim().toLowerCase();
        if (!needle) return drafts;
        return drafts.filter((d) =>
            d.work_id.toLowerCase().includes(needle) ||
            String(d.article_id).includes(needle) ||
            (d.title || '').toLowerCase().includes(needle) ||
            (d.source_action || '').toLowerCase().includes(needle)
        );
    }, [drafts, q]);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white">Workspace Drafts</h1>
                    <p className="text-sm text-gray-400 mt-1">{filtered.length} مسودة</p>
                </div>
            </div>

            {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-200">
                    {error}
                </div>
            )}

            <div className="flex flex-wrap items-center gap-3 p-3 rounded-2xl border border-white/5 bg-gray-800/30">
                <div className="relative min-w-[260px] flex-1">
                    <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        placeholder="بحث بـ work_id أو article_id أو العنوان..."
                        className="w-full h-10 pr-10 pl-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                    />
                </div>
                <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-gray-500" />
                    <select
                        value={status}
                        onChange={(e) => setStatus(e.target.value)}
                        className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                    >
                        <option value="draft">draft</option>
                        <option value="applied">applied</option>
                        <option value="archived">archived</option>
                    </select>
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {isLoading ? (
                    Array.from({ length: 6 }).map((_, i) => (
                        <div key={i} className="h-48 rounded-2xl bg-gray-800/30 border border-white/5 animate-pulse" />
                    ))
                ) : filtered.length > 0 ? (
                    filtered.map((d) => (
                        <button
                            key={d.id}
                            onClick={() => setSelected(d)}
                            className={cn(
                                'text-right rounded-2xl border p-4 bg-gradient-to-br from-gray-800/40 to-gray-900/70 transition-colors',
                                selected?.id === d.id ? 'border-emerald-500/40' : 'border-white/10 hover:border-white/20'
                            )}
                        >
                            <div className="flex items-center justify-between gap-2 mb-2">
                                <span className="text-xs px-2 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">
                                    {d.work_id}
                                </span>
                                <span className="text-xs text-gray-400">#{d.article_id}</span>
                            </div>
                            <h3 className="text-sm font-semibold text-white line-clamp-2" dir="rtl">
                                {d.title || 'بدون عنوان'}
                            </h3>
                            <p className="text-xs text-gray-400 mt-2 line-clamp-3" dir="rtl">
                                {truncate(d.body || '', 180)}
                            </p>
                            <div className="mt-3 flex items-center justify-between text-[11px] text-gray-500">
                                <span>{d.source_action}</span>
                                <span>{formatRelativeTime(d.updated_at)}</span>
                            </div>
                        </button>
                    ))
                ) : (
                    <div className="col-span-full rounded-2xl border border-white/5 bg-gray-800/20 p-8 text-center text-gray-400">
                        لا توجد مسودات
                    </div>
                )}
            </div>

            {selected && (
                <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 text-white">
                            <FileText className="w-4 h-4 text-emerald-300" />
                            <span className="text-sm font-semibold">{selected.work_id}</span>
                        </div>
                        <button
                            onClick={() => applyMutation.mutate(selected.work_id)}
                            disabled={applyMutation.isPending || selected.status !== 'draft'}
                            className={cn(
                                'px-3 py-2 rounded-xl text-xs border flex items-center gap-2',
                                selected.status === 'draft'
                                    ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-200'
                                    : 'bg-white/5 border-white/10 text-gray-500 cursor-not-allowed'
                            )}
                        >
                            <CheckCircle2 className="w-4 h-4" />
                            تطبيق مباشر
                        </button>
                    </div>
                    <div className="text-xs text-gray-400 flex flex-wrap gap-3">
                        <span>Article: #{selected.article_id}</span>
                        <span>Status: {selected.status}</span>
                        <span>Version: {selected.version}</span>
                        <span>By: {selected.created_by}</span>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/30 p-3">
                        <h4 className="text-sm text-white font-medium mb-2" dir="rtl">{selected.title || 'بدون عنوان'}</h4>
                        <pre className="whitespace-pre-wrap text-xs text-gray-200 max-h-[360px] overflow-auto" dir="rtl">
                            {selected.body}
                        </pre>
                    </div>
                </div>
            )}
        </div>
    );
}

