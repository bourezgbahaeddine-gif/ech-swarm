'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { newsApi, editorialApi, type ArticleBrief } from '@/lib/api';
import { cn, formatRelativeTime, getCategoryLabel } from '@/lib/utils';
import {
    UserCheck, CheckCircle, XCircle, RotateCw,
    Star, Zap,
} from 'lucide-react';

export default function EditorialPage() {
    const queryClient = useQueryClient();
    const [selectedArticle, setSelectedArticle] = useState<number | null>(null);
    const [editorName] = useState('رئيس التحرير');
    const [rejectReason, setRejectReason] = useState('');
    const now = Date.now();

    const isFresh = (iso: string | null, minutes = 10) => {
        if (!iso) return false;
        const deltaMs = now - new Date(iso).getTime();
        return deltaMs >= 0 && deltaMs <= minutes * 60 * 1000;
    };

    const { data: pendingData, isLoading } = useQuery({
        queryKey: ['pending-editorial'],
        queryFn: () => newsApi.pending(30),
    });

    const decideMutation = useMutation({
        mutationFn: ({ articleId, decision, reason }: { articleId: number; decision: string; reason?: string }) =>
            editorialApi.decide(articleId, { editor_name: editorName, decision, reason }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['pending-editorial'] });
            queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
            setSelectedArticle(null);
            setRejectReason('');
        },
    });

    const articles = pendingData?.data || [];

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
                                            disabled={decideMutation.isPending}
                                            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors text-sm font-medium"
                                        >
                                            <CheckCircle className="w-4 h-4" />
                                            موافقة
                                        </button>

                                        <button
                                            onClick={() => decideMutation.mutate({ articleId: article.id, decision: 'rewrite' })}
                                            disabled={decideMutation.isPending}
                                            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500/20 text-amber-400 hover:bg-amber-500/30 transition-colors text-sm font-medium"
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
                                                disabled={decideMutation.isPending}
                                                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors text-sm font-medium"
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
