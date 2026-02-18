'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { isAxiosError } from 'axios';
import { editorialApi, newsApi, type ArticleBrief, type ChiefPendingItem, type SocialApprovedItem } from '@/lib/api';
import { formatRelativeTime, getCategoryLabel, truncate } from '@/lib/utils';
import { useAuth } from '@/lib/auth';
import { CheckCircle2, RotateCcw, Send, ShieldCheck } from 'lucide-react';

function normalizeStatus(status: string | null | undefined): string {
    return (status || '').toLowerCase();
}

function getApiErrorMessage(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) {
            return detail;
        }
    }
    return fallback;
}

export default function EditorialPage() {
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const router = useRouter();

    const role = (user?.role || '').toLowerCase();
    const isChief = role === 'director' || role === 'editor_chief';
    const isSocial = role === 'social_media';
    const canNominate = role === 'journalist' || role === 'director' || role === 'editor_chief';

    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [notesMap, setNotesMap] = useState<Record<number, string>>({});

    const chiefQueueQuery = useQuery({
        queryKey: ['chief-pending-queue'],
        queryFn: () => editorialApi.chiefPending(120),
        enabled: isChief,
        refetchInterval: 30000,
    });

    const pendingCandidatesQuery = useQuery({
        queryKey: ['pending-candidates-journalist'],
        queryFn: () => newsApi.pending(80),
        enabled: !isChief && !isSocial,
        refetchInterval: 30000,
    });

    const socialFeedQuery = useQuery({
        queryKey: ['social-approved-feed'],
        queryFn: () => editorialApi.socialApprovedFeed(80),
        enabled: isSocial,
        refetchInterval: 30000,
    });

    const nominateMutation = useMutation({
        mutationFn: (articleId: number) => editorialApi.handoff(articleId),
        onSuccess: (res, articleId) => {
            const workId = res.data?.work_id;
            setSuccessMessage('تم ترشيح الخبر وفتحه في المحرر الذكي.');
            setErrorMessage(null);
            queryClient.invalidateQueries({ queryKey: ['pending-candidates-journalist'] });
            const target = workId
                ? `/workspace-drafts?article_id=${articleId}&work_id=${workId}`
                : `/workspace-drafts?article_id=${articleId}`;
            router.push(target);
        },
        onError: (err: unknown) => {
            setErrorMessage(getApiErrorMessage(err, 'تعذر ترشيح الخبر.'));
            setSuccessMessage(null);
        },
    });

    const chiefDecisionMutation = useMutation({
        mutationFn: ({ articleId, decision, notes }: { articleId: number; decision: 'approve' | 'return_for_revision'; notes?: string }) =>
            editorialApi.chiefFinalDecision(articleId, { decision, notes }),
        onSuccess: (res) => {
            setSuccessMessage(res.data?.message || 'تم تنفيذ القرار.');
            setErrorMessage(null);
            queryClient.invalidateQueries({ queryKey: ['chief-pending-queue'] });
        },
        onError: (err: unknown) => {
            setErrorMessage(getApiErrorMessage(err, 'تعذر تنفيذ قرار رئيس التحرير.'));
            setSuccessMessage(null);
        },
    });

    const socialCopyMutation = useMutation({
        mutationFn: (articleId: number) => editorialApi.socialVariantsForArticle(articleId),
        onSuccess: async (res, articleId) => {
            const variants = res.data?.variants || {};
            const text = [
                `Facebook: ${variants.facebook || '-'}`,
                `X: ${variants.x || '-'}`,
                `Push: ${variants.push || '-'}`,
                `Breaking: ${variants.breaking_alert || '-'}`,
            ].join('\n\n');
            try {
                if (typeof navigator !== 'undefined' && navigator.clipboard) {
                    await navigator.clipboard.writeText(text);
                    setSuccessMessage(`تم نسخ نسخ السوشيال للخبر #${articleId}`);
                    setErrorMessage(null);
                    return;
                }
            } catch {
                // fallback below
            }
            setSuccessMessage(text);
            setErrorMessage(null);
        },
        onError: (err: unknown) => setErrorMessage(getApiErrorMessage(err, 'تعذر جلب نسخ السوشيال')),
    });

    const chiefItems = useMemo(() => (chiefQueueQuery.data?.data || []) as ChiefPendingItem[], [chiefQueueQuery.data?.data]);
    const pendingCandidates = useMemo(() => (pendingCandidatesQuery.data?.data || []) as ArticleBrief[], [pendingCandidatesQuery.data?.data]);
    const socialItems = useMemo(() => (socialFeedQuery.data?.data || []) as SocialApprovedItem[], [socialFeedQuery.data?.data]);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-white">قسم التحرير</h1>
                <p className="text-sm text-gray-400 mt-1">
                    {isChief
                        ? 'طابور اعتماد رئيس التحرير بعد فحص وكيل السياسة التحريرية'
                        : isSocial
                            ? 'نسخ السوشيال الجاهزة من الأخبار المعتمدة'
                            : 'متابعة الأخبار المرشحة وترشيحها للتحرير'}
                </p>
            </div>

            {errorMessage && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{errorMessage}</div>}
            {successMessage && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200 whitespace-pre-wrap">{successMessage}</div>}

            {isChief ? (
                <div className="space-y-3">
                    {chiefQueueQuery.isLoading ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 text-center text-gray-400">جاري تحميل طابور الاعتماد...</div>
                    ) : chiefItems.length === 0 ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 text-center text-gray-400">لا توجد طلبات اعتماد حالياً.</div>
                    ) : (
                        chiefItems.map((item) => {
                            const hasReservations = normalizeStatus(item.status) === 'approval_request_with_reservations';
                            const note = notesMap[item.id] || '';
                            return (
                                <div key={item.id} className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-3">
                                    <div className="flex items-start justify-between gap-3" dir="rtl">
                                        <div>
                                            <h3 className="text-base text-white font-semibold">{item.title_ar || item.original_title}</h3>
                                            <p className="text-xs text-gray-400 mt-1">{item.source_name || 'بدون مصدر'} • {getCategoryLabel(item.category)}</p>
                                            <p className="text-xs text-gray-500 mt-1">آخر تحديث: {formatRelativeTime(item.updated_at)}</p>
                                        </div>
                                        <span className={`px-2 py-1 rounded-lg text-[11px] border ${hasReservations ? 'border-orange-500/40 bg-orange-500/20 text-orange-200' : 'border-cyan-500/40 bg-cyan-500/20 text-cyan-200'}`}>
                                            {hasReservations ? 'تحفظات من وكيل السياسة' : 'مقبول من وكيل السياسة'}
                                        </span>
                                    </div>

                                    {!!item.policy?.reasons?.length && (
                                        <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-gray-200" dir="rtl">
                                            <p className="text-gray-400 mb-1">أسباب/ملاحظات الوكيل:</p>
                                            {item.policy.reasons.map((r, idx) => (
                                                <p key={`${item.id}-r-${idx}`}>- {r}</p>
                                            ))}
                                        </div>
                                    )}

                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                        <a
                                            href={item.work_id ? `/workspace-drafts?article_id=${item.id}&work_id=${item.work_id}` : `/workspace-drafts?article_id=${item.id}`}
                                            className="px-3 py-2 rounded-xl border border-white/20 bg-white/5 text-center text-xs text-gray-200 hover:text-white"
                                        >
                                            فتح النسخة في المحرر
                                        </a>
                                        <button
                                            onClick={() => chiefDecisionMutation.mutate({ articleId: item.id, decision: 'approve', notes: note || undefined })}
                                            disabled={chiefDecisionMutation.isPending}
                                            className="px-3 py-2 rounded-xl border border-emerald-500/30 bg-emerald-500/20 text-xs text-emerald-200 flex items-center justify-center gap-1"
                                        >
                                            <CheckCircle2 className="w-4 h-4" /> اعتماد نهائي
                                        </button>
                                        <button
                                            onClick={() => chiefDecisionMutation.mutate({ articleId: item.id, decision: 'return_for_revision', notes: note || undefined })}
                                            disabled={chiefDecisionMutation.isPending}
                                            className="px-3 py-2 rounded-xl border border-amber-500/30 bg-amber-500/20 text-xs text-amber-200 flex items-center justify-center gap-1"
                                        >
                                            <RotateCcw className="w-4 h-4" /> إعادة للمراجعة
                                        </button>
                                    </div>

                                    <input
                                        type="text"
                                        value={note}
                                        onChange={(e) => setNotesMap((prev) => ({ ...prev, [item.id]: e.target.value }))}
                                        placeholder="ملاحظة اختيارية مع القرار..."
                                        className="w-full rounded-xl bg-white/5 border border-white/10 px-3 py-2 text-xs text-white placeholder:text-gray-500"
                                        dir="rtl"
                                    />
                                </div>
                            );
                        })
                    )}
                </div>
            ) : isSocial ? (
                <div className="space-y-3">
                    {socialFeedQuery.isLoading ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 text-center text-gray-400">جاري تحميل الأخبار المعتمدة...</div>
                    ) : socialItems.length === 0 ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 text-center text-gray-400">لا توجد أخبار معتمدة حالياً.</div>
                    ) : (
                        socialItems.map((item) => (
                            <div key={item.article_id} className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-2" dir="rtl">
                                <h3 className="text-base text-white font-semibold">{item.title}</h3>
                                <p className="text-xs text-gray-400">{item.source_name || 'بدون مصدر'} • {formatRelativeTime(item.updated_at)}</p>
                                <button
                                    onClick={() => socialCopyMutation.mutate(item.article_id)}
                                    disabled={socialCopyMutation.isPending}
                                    className="px-3 py-2 rounded-xl border border-cyan-500/30 bg-cyan-500/20 text-xs text-cyan-200"
                                >
                                    نسخ النسخ الجاهزة
                                </button>
                            </div>
                        ))
                    )}
                </div>
            ) : (
                <div className="space-y-3">
                    {pendingCandidatesQuery.isLoading ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 text-center text-gray-400">جاري تحميل الأخبار المرشحة...</div>
                    ) : pendingCandidates.length === 0 ? (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 text-center text-gray-400">لا توجد أخبار مرشحة حالياً.</div>
                    ) : (
                        pendingCandidates.map((article) => (
                            <div key={article.id} className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-3" dir="rtl">
                                <div>
                                    <h3 className="text-base text-white font-semibold">{article.title_ar || article.original_title}</h3>
                                    <p className="text-xs text-gray-400 mt-1">{article.source_name || 'بدون مصدر'} • {getCategoryLabel(article.category)} • {formatRelativeTime(article.created_at || article.crawled_at)}</p>
                                    {article.summary && <p className="text-xs text-gray-300 mt-2">{truncate(article.summary, 220)}</p>}
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                    <a
                                        href={`/workspace-drafts?article_id=${article.id}`}
                                        className="px-3 py-2 rounded-xl border border-white/20 bg-white/5 text-center text-xs text-gray-200 hover:text-white"
                                    >
                                        فتح في المحرر
                                    </a>
                                    <button
                                        onClick={() => nominateMutation.mutate(article.id)}
                                        disabled={!canNominate || nominateMutation.isPending}
                                        className="px-3 py-2 rounded-xl border border-cyan-500/30 bg-cyan-500/20 text-xs text-cyan-200 flex items-center justify-center gap-1 disabled:opacity-50"
                                    >
                                        <Send className="w-4 h-4" /> ترشيح للتحرير
                                    </button>
                                    <a
                                        href={article.original_url || '#'}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="px-3 py-2 rounded-xl border border-white/20 bg-white/5 text-center text-xs text-gray-300 hover:text-white"
                                    >
                                        المصدر
                                    </a>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            )}

            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 text-xs text-gray-300" dir="rtl">
                <p className="flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-emerald-300" /> السياسة التشغيلية: لا نشر تلقائي. كل خبر يمر على وكيل السياسة ثم اعتماد رئيس التحرير.</p>
            </div>
        </div>
    );
}
