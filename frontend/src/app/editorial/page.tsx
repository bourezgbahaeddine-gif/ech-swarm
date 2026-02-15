'use client';

import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { newsApi, editorialApi, type ArticleBrief } from '@/lib/api';
import { cn, formatRelativeTime, getCategoryLabel } from '@/lib/utils';
import { useAuth } from '@/lib/auth';
import {
    UserCheck, CheckCircle, XCircle, RotateCw,
    Star, Zap, RefreshCw, Timer,
} from 'lucide-react';

export default function EditorialPage() {
    const queryClient = useQueryClient();
    const { user } = useAuth();

    const [selectedArticle, setSelectedArticle] = useState<number | null>(null);
    const [editorName] = useState(user?.full_name_ar || 'رئيس التحرير');
    const [rejectReason, setRejectReason] = useState('');
    const [search, setSearch] = useState('');
    const [selectedIds, setSelectedIds] = useState<number[]>([]);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const normalizeStatus = (status: string) => (status || '').toLowerCase();
    const role = user?.role || '';
    const canApproveReject = role === 'director' || role === 'editor_chief';
    const canRewrite = ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'].includes(role);

    const isFresh = (iso: string | null, minutes = 10) => {
        if (!iso) return false;
        const deltaMs = Date.now() - new Date(iso).getTime();
        return deltaMs >= 0 && deltaMs <= minutes * 60 * 1000;
    };
    const waitingMinutes = (iso: string | null) => {
        if (!iso) return 0;
        return Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    };
    const hasLocalSignal = (article: ArticleBrief) => {
        const text = `${article.title_ar || ''} ${article.original_title || ''} ${article.source_name || ''}`.toLowerCase();
        return ['الجزائر', 'algeria', 'algérie', 'algerie', 'aps', 'echorouk', 'el khabar', 'tsa'].some((k) => text.includes(k));
    };
    const hasTrustedSource = (article: ArticleBrief) => {
        const src = (article.source_name || '').toLowerCase();
        return ['aps', 'bbc', 'reuters', 'france24', 'le monde', 'the guardian', 'echorouk', 'el khabar'].some((k) => src.includes(k));
    };
    const priorityScore = (article: ArticleBrief) => {
        let score = article.importance_score || 0;
        if (article.is_breaking) score += 8;
        if (hasLocalSignal(article)) score += 4;
        if (hasTrustedSource(article)) score += 2;
        score += Math.min(10, Math.floor(waitingMinutes(article.created_at || article.crawled_at) / 10));
        return score;
    };

    const extractErrorDetail = (err: unknown, fallback: string): string => {
        if (typeof err === 'object' && err !== null) {
            const maybeResponse = (err as { response?: { data?: { detail?: unknown } } }).response;
            const detail = maybeResponse?.data?.detail;
            if (typeof detail === 'string' && detail.trim()) {
                return detail;
            }
        }
        return fallback;
    };

    const { data: pendingData, isLoading } = useQuery({
        queryKey: ['pending-editorial'],
        queryFn: () => newsApi.pending(50),
    });

    const decideMutation = useMutation({
        mutationFn: ({ articleId, decision, reason }: { articleId: number; decision: string; reason?: string }) =>
            editorialApi.decide(articleId, { editor_name: editorName, decision, reason }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['pending-editorial'] });
            queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
            setSelectedArticle(null);
            setRejectReason('');
            setErrorMessage(null);
            setSuccessMessage('تم تنفيذ القرار بنجاح');
        },
        onError: (err: unknown) => {
            setErrorMessage(extractErrorDetail(err, 'تعذر تنفيذ القرار'));
            setSuccessMessage(null);
        },
    });

    const bulkMutation = useMutation({
        mutationFn: async ({ ids, decision, reason }: { ids: number[]; decision: string; reason?: string }) => {
            await Promise.all(
                ids.map((articleId) =>
                    editorialApi.decide(articleId, { editor_name: editorName, decision, reason })
                )
            );
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['pending-editorial'] });
            queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
            setSelectedIds([]);
            setRejectReason('');
            setErrorMessage(null);
            setSuccessMessage('تم تنفيذ القرار الجماعي بنجاح');
        },
        onError: (err: unknown) => {
            setErrorMessage(extractErrorDetail(err, 'تعذر تنفيذ القرار الجماعي'));
            setSuccessMessage(null);
        },
    });

    const articles = useMemo(() => {
        const rows = (pendingData?.data || []) as ArticleBrief[];
        const q = search.trim().toLowerCase();
        const filtered = q ? rows.filter((a) =>
            `${a.title_ar || ''} ${a.original_title || ''} ${a.source_name || ''}`.toLowerCase().includes(q)
        ) : rows;
        return [...filtered].sort((a, b) => priorityScore(b) - priorityScore(a));
    }, [pendingData?.data, search]);

    const editorialStats = useMemo(() => {
        const urgent = articles.filter((a) => a.is_breaking || (a.importance_score || 0) >= 8).length;
        const local = articles.filter((a) => hasLocalSignal(a)).length;
        const trusted = articles.filter((a) => hasTrustedSource(a)).length;
        const slaBreached = articles.filter((a) => waitingMinutes(a.created_at || a.crawled_at) > 20).length;
        return { urgent, local, trusted, slaBreached };
    }, [articles]);

    const toggleSelected = (id: number) => {
        setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                    <UserCheck className="w-7 h-7 text-amber-400" />
                    قسم التحرير
                </h1>
                <p className="text-sm text-gray-500 mt-1">
                    {articles.length} خبر بانتظار قراركم
                </p>
            </div>

            {errorMessage && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                    {errorMessage}
                </div>
            )}
            {successMessage && (
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">
                    {successMessage}
                </div>
            )}

            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                    <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-3">
                        <p className="text-[11px] text-red-300">عاجل/مرتفع</p>
                        <p className="text-xl font-bold text-white">{editorialStats.urgent}</p>
                    </div>
                    <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3">
                        <p className="text-[11px] text-emerald-300">إشارة محلية</p>
                        <p className="text-xl font-bold text-white">{editorialStats.local}</p>
                    </div>
                    <div className="rounded-xl bg-sky-500/10 border border-sky-500/20 p-3">
                        <p className="text-[11px] text-sky-300">مصادر موثوقة</p>
                        <p className="text-xl font-bold text-white">{editorialStats.trusted}</p>
                    </div>
                    <div className="rounded-xl bg-amber-500/10 border border-amber-500/20 p-3">
                        <p className="text-[11px] text-amber-300">متجاوز SLA</p>
                        <p className="text-xl font-bold text-white">{editorialStats.slaBreached}</p>
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <input
                        type="text"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="بحث في العنوان/المصدر..."
                        className="h-10 flex-1 min-w-[220px] rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white placeholder:text-gray-500"
                        dir="rtl"
                    />
                    <button
                        onClick={() => queryClient.invalidateQueries({ queryKey: ['pending-editorial'] })}
                        className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-xs text-gray-300 hover:text-white flex items-center gap-2"
                    >
                        <RefreshCw className="w-4 h-4" />
                        تحديث
                    </button>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <button
                        disabled={!canApproveReject || bulkMutation.isPending || articles.length === 0}
                        onClick={() => {
                            const policyIds = articles
                                .filter((a) => normalizeStatus(a.status) === 'candidate')
                                .filter((a) => hasLocalSignal(a))
                                .filter((a) => hasTrustedSource(a))
                                .filter((a) => (a.importance_score || 0) >= 7 || a.is_breaking)
                                .map((a) => a.id);
                            if (policyIds.length === 0) {
                                setErrorMessage('لا توجد مواد مطابقة لسياسة الاعتماد السريع حالياً');
                                return;
                            }
                            bulkMutation.mutate({ ids: policyIds, decision: 'approve' });
                        }}
                        className="px-3 py-2 rounded-xl bg-cyan-500/20 text-cyan-200 disabled:opacity-40 text-xs"
                    >
                        اعتماد سريع حسب السياسة
                    </button>
                    <button
                        disabled={!canApproveReject || selectedIds.length === 0 || bulkMutation.isPending}
                        onClick={() => bulkMutation.mutate({ ids: selectedIds, decision: 'approve' })}
                        className="px-3 py-2 rounded-xl bg-emerald-500/20 text-emerald-300 disabled:opacity-40 text-xs"
                    >
                        موافقة جماعية ({selectedIds.length})
                    </button>
                    <button
                        disabled={!canRewrite || selectedIds.length === 0 || bulkMutation.isPending}
                        onClick={() => bulkMutation.mutate({ ids: selectedIds, decision: 'rewrite' })}
                        className="px-3 py-2 rounded-xl bg-amber-500/20 text-amber-300 disabled:opacity-40 text-xs"
                    >
                        إعادة صياغة جماعية
                    </button>
                    <button
                        disabled={!canApproveReject || selectedIds.length === 0 || bulkMutation.isPending}
                        onClick={() => bulkMutation.mutate({ ids: selectedIds, decision: 'reject', reason: rejectReason || undefined })}
                        className="px-3 py-2 rounded-xl bg-red-500/20 text-red-300 disabled:opacity-40 text-xs"
                    >
                        رفض جماعي
                    </button>
                    <input
                        type="text"
                        value={rejectReason}
                        onChange={(e) => setRejectReason(e.target.value)}
                        placeholder="سبب الرفض الجماعي (اختياري)"
                        className="h-9 min-w-[220px] rounded-xl bg-white/5 border border-white/10 px-3 text-xs text-white placeholder:text-gray-500"
                        dir="rtl"
                    />
                </div>
            </div>

            <div className="space-y-3">
                {isLoading ? (
                    Array.from({ length: 5 }).map((_, i) => (
                        <div key={i} className="h-32 rounded-2xl bg-gray-800/30 border border-white/5 animate-pulse" />
                    ))
                ) : articles.length > 0 ? (
                    articles.map((article: ArticleBrief) => (
                        <div
                            key={article.id}
                            className={cn(
                                'rounded-2xl border transition-all duration-300',
                                'bg-gradient-to-br from-gray-800/40 to-gray-900/60',
                                selectedArticle === article.id
                                    ? 'border-emerald-500/30 shadow-lg shadow-emerald-500/5'
                                    : 'border-white/5 hover:border-white/10',
                                article.is_breaking && 'border-red-500/20',
                            )}
                        >
                            <div
                                className="p-5 cursor-pointer"
                                onClick={() => setSelectedArticle(selectedArticle === article.id ? null : article.id)}
                            >
                                <div className="flex items-start gap-4">
                                    <button
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            toggleSelected(article.id);
                                        }}
                                        className={cn(
                                            'mt-1 h-5 w-5 rounded border',
                                            selectedIds.includes(article.id)
                                                ? 'border-emerald-400 bg-emerald-500/40'
                                                : 'border-white/20 bg-white/5'
                                        )}
                                        aria-label={`select-${article.id}`}
                                    />

                                    <div className={cn(
                                        'w-12 h-12 rounded-xl flex flex-col items-center justify-center flex-shrink-0',
                                        article.importance_score >= 8 ? 'bg-red-500/20 text-red-400' :
                                            article.importance_score >= 6 ? 'bg-amber-500/20 text-amber-400' :
                                                'bg-blue-500/20 text-blue-400',
                                    )}>
                                        <Star className="w-4 h-4 mb-0.5" />
                                        <span className="text-lg font-bold">{article.importance_score}</span>
                                    </div>

                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-1">
                                            {article.is_breaking && (
                                                <span className="px-2 py-0.5 rounded-full bg-red-500 text-[10px] font-bold text-white flex items-center gap-1 animate-pulse">
                                                    <Zap className="w-3 h-3" /> عاجل
                                                </span>
                                            )}
                                            {isFresh(article.created_at) && (
                                                <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-[10px] font-bold text-emerald-400">
                                                    جديد الآن
                                                </span>
                                            )}
                                            <span className="text-xs text-gray-500">{getCategoryLabel(article.category)}</span>
                                            <span className="text-[10px] text-gray-600">{article.source_name}</span>
                                            <span className="text-[10px] text-gray-600 mr-auto">
                                                {formatRelativeTime(article.created_at || article.crawled_at)}
                                            </span>
                                            {waitingMinutes(article.created_at || article.crawled_at) > 20 && (
                                                <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-[10px] font-bold text-amber-300 flex items-center gap-1">
                                                    <Timer className="w-3 h-3" /> SLA
                                                </span>
                                            )}
                                        </div>

                                        <h3 className="text-base font-semibold text-white leading-relaxed" dir="rtl">
                                            {article.title_ar || article.original_title}
                                        </h3>

                                        {article.summary && (
                                            <p className="text-sm text-gray-400 mt-2 leading-relaxed line-clamp-2" dir="rtl">
                                                {article.summary}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </div>

                            {selectedArticle === article.id && (
                                <div className="px-5 pb-5 border-t border-white/5 pt-4 animate-fade-in-up">
                                    <div className="flex flex-wrap items-center gap-3">
                                        <button
                                            onClick={() => decideMutation.mutate({ articleId: article.id, decision: 'approve' })}
                                            disabled={decideMutation.isPending || !canApproveReject || !['candidate', 'classified'].includes(normalizeStatus(article.status))}
                                            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors text-sm font-medium disabled:opacity-50"
                                        >
                                            <CheckCircle className="w-4 h-4" />
                                            موافقة
                                        </button>

                                        <button
                                            onClick={() => decideMutation.mutate({ articleId: article.id, decision: 'rewrite' })}
                                            disabled={decideMutation.isPending || !canRewrite || !['candidate', 'classified'].includes(normalizeStatus(article.status))}
                                            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 transition-colors text-sm font-medium disabled:opacity-50"
                                        >
                                            <RotateCw className="w-4 h-4" />
                                            إعادة صياغة
                                        </button>

                                        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
                                            <input
                                                type="text"
                                                value={rejectReason}
                                                onChange={(e) => setRejectReason(e.target.value)}
                                                placeholder="سبب الرفض (اختياري)..."
                                                className="flex-1 h-10 px-3 rounded-xl bg-white/5 border border-white/5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-red-500/40"
                                                dir="rtl"
                                            />
                                            <button
                                                onClick={() => decideMutation.mutate({ articleId: article.id, decision: 'reject', reason: rejectReason })}
                                                disabled={decideMutation.isPending || !canApproveReject || !['candidate', 'classified'].includes(normalizeStatus(article.status))}
                                                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors text-sm font-medium disabled:opacity-50"
                                            >
                                                <XCircle className="w-4 h-4" />
                                                رفض
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    ))
                ) : (
                    <div className="text-center py-16 rounded-2xl bg-gray-800/20 border border-white/5">
                        <CheckCircle className="w-12 h-12 text-emerald-400/30 mx-auto mb-3" />
                        <h3 className="text-lg font-semibold text-white">لا توجد أخبار بانتظار المراجعة</h3>
                        <p className="text-sm text-gray-500 mt-1">سيتم إعلامك عند وصول أخبار جديدة</p>
                    </div>
                )}
            </div>
        </div>
    );
}
