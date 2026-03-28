
'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { isAxiosError } from 'axios';
import {
    editorialApi,
    memoryApi,
    newsApi,
    type ArticleBrief,
    type ChiefPendingItem,
    type SocialApprovedItem,
} from '@/lib/api';
import { formatRelativeTime, getCategoryLabel, truncate } from '@/lib/utils';
import { useAuth } from '@/lib/auth';
import { AlertTriangle, CheckCircle2, RotateCcw, Send, ShieldCheck } from 'lucide-react';
import { WorkflowCard } from '@/components/workflow/WorkflowCard';
import { WorkflowHelpPanel } from '@/components/workflow/WorkflowHelpPanel';
import { TutorialOverlay } from '@/components/onboarding/TutorialOverlay';
import { useTutorialState } from '@/lib/tutorial';
import { MemoryQuickCaptureModal } from '@/components/memory/MemoryQuickCaptureModal';
import { ActionDialog } from '@/components/ui/ActionDialog';
import { getWorkflowStatusLabel } from '@/lib/workflow-language';
import { trackNextAction, useTrackSurfaceView } from '@/lib/ux-telemetry';

type EditorialTabKey = 'pending' | 'returned' | 'reservations' | 'manual';
type PendingChiefDecision = {
    item: ChiefPendingItem;
    decision: 'approve' | 'approve_with_reservations' | 'send_back' | 'reject' | 'return_for_revision';
    blockersPreview: string[];
};

function normalizeStatus(status: string | null | undefined): string {
    return (status || '').toLowerCase();
}

function getApiErrorMessage(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) {
            return detail;
        }
        if (detail && typeof detail === 'object') {
            const message = (detail as { message?: unknown }).message;
            if (typeof message === 'string' && message.trim()) {
                return message;
            }
        }
        const message = error.response?.data?.error?.message;
        if (typeof message === 'string' && message.trim()) {
            return message;
        }
    }
    return fallback;
}

function getArticleReason(article: ArticleBrief): string {
    const status = normalizeStatus(article.status);
    if (article.is_breaking) return 'ظهر هنا لأنه خبر عاجل يحتاج متابعة تحريرية سريعة.';
    if (status === 'draft_generated') return 'ظهر هنا لأنه عاد إلى مسار التحرير ويحتاج استكمالًا أو إعادة إرسال.';
    if (status === 'approval_request_with_reservations') return 'ظهر هنا لأن المادة تحتوي تحفظات أو ملاحظات قبل الاعتماد النهائي.';
    if (status === 'ready_for_manual_publish') return 'ظهر هنا لأنه اجتاز الاعتماد وأصبح جاهزًا للنشر اليدوي أو النسخ الرقمية.';
    return 'ظهر هنا لأنه دخل نطاق التحرير اليوم ويحتاج خطوة تشغيلية تالية.';
}

function getArticlePrimaryAction(article: ArticleBrief): { label: string; href?: string } {
    const status = normalizeStatus(article.status);
    if (status === 'ready_for_manual_publish') return { label: 'افتح الجاهز للنشر', href: `/news?status=ready_for_manual_publish` };
    if (status === 'approval_request_with_reservations') return { label: 'راجع التحفظات', href: `/workspace-drafts?article_id=${article.id}` };
    if (status === 'draft_generated') return { label: 'أكمل التحرير', href: `/workspace-drafts?article_id=${article.id}` };
    return { label: 'افتح في المحرر', href: `/workspace-drafts?article_id=${article.id}` };
}

function getChiefReason(item: ChiefPendingItem): string {
    const status = normalizeStatus(item.status);
    if (status === 'approval_request_with_reservations') return 'ظهرت لك لأن وكيل السياسة اعتمد المادة بتحفظات وتنتظر قرارك النهائي.';
    if (item.is_breaking) return 'ظهرت لك لأنها مادة عاجلة وصلت إلى بوابة الاعتماد النهائي.';
    return 'ظهرت لك لأنها جاهزة لقرار رئيس التحرير قبل السماح بالنشر اليدوي.';
}

function EmptyState({ message }: { message: string }) {
    return <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 text-center text-gray-400">{message}</div>;
}

function QueueTabButton({ active, label, count, onClick }: { active: boolean; label: string; count: number; onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className={`rounded-2xl border px-4 py-3 text-right transition ${active ? 'border-cyan-400/40 bg-cyan-500/15 text-white' : 'border-white/10 bg-white/5 text-gray-300 hover:bg-white/10 hover:text-white'}`}
            dir="rtl"
        >
            <div className="text-sm font-semibold">{label}</div>
            <div className="mt-1 text-xs text-gray-400">{count} عنصر</div>
        </button>
    );
}

export default function EditorialPage() {
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const router = useRouter();
    const { state: tutorialState, update: updateTutorial, complete: completeTutorial, active: tutorialActive } = useTutorialState();

    const role = (user?.role || '').toLowerCase();
    const isChief = role === 'director' || role === 'editor_chief';
    const isSocial = role === 'social_media';
    const canNominate = role === 'journalist' || role === 'social_media' || role === 'director' || role === 'editor_chief';

    useEffect(() => {
        if (tutorialActive && tutorialState.role === 'editor_chief' && tutorialState.step === 'chief_today') {
            updateTutorial({ step: 'chief_editorial' });
        }
    }, [tutorialActive, tutorialState.role, tutorialState.step, updateTutorial]);

    const [activeTab, setActiveTab] = useState<EditorialTabKey>('pending');
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [notesMap, setNotesMap] = useState<Record<number, string>>({});
    const [memoryCaptureArticle, setMemoryCaptureArticle] = useState<ArticleBrief | ChiefPendingItem | null>(null);
    const [pendingChiefDecision, setPendingChiefDecision] = useState<PendingChiefDecision | null>(null);
    const surfaceDetails = useMemo(
        () => ({
            role: role || 'guest',
            active_tab: activeTab,
            chief_flow: isChief,
        }),
        [activeTab, isChief, role],
    );

    useTrackSurfaceView('editorial', surfaceDetails);

    const decisionRequiresReason: Record<string, boolean> = {
        approve: false,
        approve_with_reservations: true,
        send_back: false,
        reject: true,
        return_for_revision: false,
    };

    const decisionLabel: Record<string, string> = {
        approve: 'اعتماد نهائي',
        approve_with_reservations: 'اعتماد بتحفظات',
        send_back: 'إرجاع للمراجعة',
        reject: 'رفض',
        return_for_revision: 'إرجاع للمراجعة',
    };

    const chiefQueueQuery = useQuery({
        queryKey: ['chief-pending-queue'],
        queryFn: () => editorialApi.chiefPending(120),
        enabled: isChief,
        refetchInterval: 30000,
    });

    const pendingCandidatesQuery = useQuery({
        queryKey: ['pending-candidates-journalist'],
        queryFn: () => newsApi.pending(80),
        enabled: !isChief,
        refetchInterval: 30000,
    });

    const draftGeneratedQuery = useQuery({
        queryKey: ['editorial-draft-generated'],
        queryFn: async () => (await newsApi.list({ page: 1, per_page: 80, status: 'draft_generated' })).data.items,
        refetchInterval: 30000,
    });

    const reservationsQuery = useQuery({
        queryKey: ['editorial-reservations'],
        queryFn: async () => (await newsApi.list({ page: 1, per_page: 80, status: 'approval_request_with_reservations' })).data.items,
        enabled: !isChief,
        refetchInterval: 30000,
    });

    const readyForManualQuery = useQuery({
        queryKey: ['editorial-ready-manual'],
        queryFn: async () => (await newsApi.list({ page: 1, per_page: 80, status: 'ready_for_manual_publish' })).data.items,
        refetchInterval: 30000,
    });

    const socialFeedQuery = useQuery({
        queryKey: ['social-approved-feed'],
        queryFn: () => editorialApi.socialApprovedFeed(80),
        enabled: isSocial,
        refetchInterval: 30000,
    });

    const quickCaptureMutation = useMutation({
        mutationFn: (payload: {
            memory_type: 'operational' | 'knowledge' | 'session';
            memory_subtype: string;
            title: string;
            content: string;
            tags: string[];
            importance: number;
            freshness_status: 'stable' | 'review_soon' | 'expired';
            valid_until: string | null;
            note: string | null;
        }) =>
            memoryApi.quickCapture({
                ...payload,
                article_id: memoryCaptureArticle?.id || null,
                source_type: 'editorial_queue',
                source_ref: memoryCaptureArticle ? `editorial:${memoryCaptureArticle.id}` : 'editorial',
            }),
        onSuccess: async () => {
            setSuccessMessage('تم حفظ الملاحظة في الذاكرة التحريرية.');
            setErrorMessage(null);
            setMemoryCaptureArticle(null);
            await queryClient.invalidateQueries({ queryKey: ['memory-items'] });
            await queryClient.invalidateQueries({ queryKey: ['memory-overview'] });
        },
        onError: (err) => setErrorMessage(getApiErrorMessage(err, 'تعذر حفظ الملاحظة في الذاكرة التحريرية.')),
    });

    const nominateMutation = useMutation({
        mutationFn: (articleId: number) => editorialApi.handoff(articleId),
        onSuccess: (res, articleId) => {
            const workId = res.data?.work_id;
            setSuccessMessage('تم ترشيح الخبر وفتحه في المحرر الذكي.');
            setErrorMessage(null);
            queryClient.invalidateQueries({ queryKey: ['pending-candidates-journalist'] });
            const target = workId ? `/workspace-drafts?article_id=${articleId}&work_id=${workId}` : `/workspace-drafts?article_id=${articleId}`;
            router.push(target);
        },
        onError: (err: unknown) => {
            setErrorMessage(getApiErrorMessage(err, 'تعذر ترشيح الخبر.'));
            setSuccessMessage(null);
        },
    });

    const chiefDecisionMutation = useMutation({
        mutationFn: ({ articleId, decision, notes }: { articleId: number; decision: 'approve' | 'approve_with_reservations' | 'send_back' | 'reject' | 'return_for_revision'; notes?: string }) =>
            editorialApi.chiefFinalDecision(articleId, { decision, notes }),
        onSuccess: (res) => {
            const message = res.data?.message || 'تم تطبيق القرار.';
            const overridden = (res.data?.overridden_blockers || []).filter(Boolean);
            if (overridden.length > 0) {
                const rendered = overridden.slice(0, 5).map((item) => `- ${item}`).join('\n');
                setSuccessMessage(`${message}\n\nتم تجاوز العوائق التالية:\n${rendered}`);
            } else {
                setSuccessMessage(message);
            }
            setErrorMessage(null);
            if (tutorialActive && tutorialState.role === 'editor_chief' && tutorialState.step === 'chief_decision') {
                completeTutorial();
            }
            queryClient.invalidateQueries({ queryKey: ['chief-pending-queue'] });
            queryClient.invalidateQueries({ queryKey: ['editorial-draft-generated'] });
            queryClient.invalidateQueries({ queryKey: ['editorial-reservations'] });
            queryClient.invalidateQueries({ queryKey: ['editorial-ready-manual'] });
        },
        onError: (err: unknown) => {
            setErrorMessage(getApiErrorMessage(err, 'فشل تطبيق قرار رئيس التحرير.'));
            setSuccessMessage(null);
        },
    });

    const socialCopyMutation = useMutation({
        mutationFn: (articleId: number) => editorialApi.socialVariantsForArticle(articleId),
        onSuccess: async (res, articleId) => {
            const variants = res.data?.variants || {};
            const text = [`Facebook: ${variants.facebook || '-'}`, `X: ${variants.x || '-'}`, `Push: ${variants.push || '-'}`, `Breaking: ${variants.breaking_alert || '-'}`].join('\n\n');
            try {
                if (typeof navigator !== 'undefined' && navigator.clipboard) {
                    await navigator.clipboard.writeText(text);
                    setSuccessMessage(`تم نسخ النسخ الجاهزة للخبر #${articleId}`);
                    setErrorMessage(null);
                    return;
                }
            } catch {
                // fallback below
            }
            setSuccessMessage(text);
            setErrorMessage(null);
        },
        onError: (err: unknown) => setErrorMessage(getApiErrorMessage(err, 'تعذر جلب نسخ السوشيال.')),
    });
    const chiefItems = useMemo(() => (chiefQueueQuery.data?.data || []) as ChiefPendingItem[], [chiefQueueQuery.data?.data]);
    const pendingCandidates = useMemo(() => (pendingCandidatesQuery.data?.data || []) as ArticleBrief[], [pendingCandidatesQuery.data?.data]);
    const draftGeneratedItems = useMemo(() => (draftGeneratedQuery.data || []) as ArticleBrief[], [draftGeneratedQuery.data]);
    const reservationsItems = useMemo(() => (reservationsQuery.data || []) as ArticleBrief[], [reservationsQuery.data]);
    const readyForManualItems = useMemo(() => (readyForManualQuery.data || []) as ArticleBrief[], [readyForManualQuery.data]);
    const socialItems = useMemo(() => (socialFeedQuery.data?.data || []) as SocialApprovedItem[], [socialFeedQuery.data?.data]);

    const chiefPendingItems = useMemo(() => chiefItems.filter((item) => normalizeStatus(item.status) !== 'approval_request_with_reservations'), [chiefItems]);
    const chiefReservationItems = useMemo(() => chiefItems.filter((item) => normalizeStatus(item.status) === 'approval_request_with_reservations'), [chiefItems]);

    const tutorialRole = tutorialState.role;
    const tutorialStep = tutorialState.step;
    const showChiefOverlay = tutorialActive && tutorialRole === 'editor_chief' && tutorialStep === 'chief_editorial';
    const tutorialChiefItem = chiefPendingItems[0];

    const tabs = useMemo(
        () => [
            {
                key: 'pending' as const,
                label: isChief ? 'بانتظار الاعتماد' : 'بانتظارك الآن',
                count: isChief ? chiefPendingItems.length : pendingCandidates.length,
                helper: isChief ? 'مواد وصلت إلى قرار رئيس التحرير.' : 'مواد دخلت نطاقك وتحتاج بدء العمل.',
            },
            {
                key: 'returned' as const,
                label: 'عاد للمراجعة',
                count: draftGeneratedItems.length,
                helper: 'مواد في مسار التحرير وتحتاج متابعة أو إعادة إرسال.',
            },
            {
                key: 'reservations' as const,
                label: 'بتحفظات',
                count: isChief ? chiefReservationItems.length : reservationsItems.length,
                helper: 'مواد فيها ملاحظات أو تحفظات قبل الإقفال النهائي.',
            },
            {
                key: 'manual' as const,
                label: 'جاهز للنشر اليدوي',
                count: readyForManualItems.length,
                helper: 'مواد اجتازت الاعتماد وأصبحت جاهزة للنشر أو التسليم.',
            },
        ],
        [chiefPendingItems.length, chiefReservationItems.length, draftGeneratedItems.length, isChief, pendingCandidates.length, readyForManualItems.length, reservationsItems.length],
    );

    const activeTabMeta = tabs.find((tab) => tab.key === activeTab) || tabs[0];

    const submitChiefDecision = (item: ChiefPendingItem, decision: 'approve' | 'approve_with_reservations' | 'send_back' | 'reject' | 'return_for_revision') => {
        const note = (notesMap[item.id] || '').trim();
        if (tutorialActive && tutorialState.role === 'editor_chief' && tutorialState.step === 'chief_editorial') {
            updateTutorial({ step: 'chief_decision' });
        }
        if (decisionRequiresReason[decision] && !note) {
            setErrorMessage(`سبب القرار مطلوب عند اختيار: ${decisionLabel[decision]}`);
            setSuccessMessage(null);
            return;
        }
        const blockersPreview = decision === 'approve_with_reservations'
            ? [...(item.decision_card?.quality_issues || []), ...(item.decision_card?.claims_issues || [])].slice(0, 3)
            : [];
        setPendingChiefDecision({ item, decision, blockersPreview });
    };

    const handleChiefNext = () => {
        if (!tutorialChiefItem) {
            completeTutorial();
            return;
        }
        updateTutorial({ step: 'chief_decision' });
        submitChiefDecision(tutorialChiefItem, 'approve');
    };

    const confirmChiefDecision = () => {
        if (!pendingChiefDecision) return;
        const { item, decision } = pendingChiefDecision;
        const note = (notesMap[item.id] || '').trim();
        trackNextAction('editorial', decisionLabel[decision], {
            ...surfaceDetails,
            queue_view: normalizeStatus(item.status) === 'approval_request_with_reservations' ? 'reservations' : 'pending',
            article_id: item.id,
            current_status: item.status,
        });
        chiefDecisionMutation.mutate(
            { articleId: item.id, decision, notes: note || undefined },
            {
                onSettled: () => setPendingChiefDecision(null),
            },
        );
    };

    const renderChiefCard = (item: ChiefPendingItem) => {
        const hasReservations = normalizeStatus(item.status) === 'approval_request_with_reservations';
        const note = notesMap[item.id] || '';
        const blockers = [
            ...(item.policy?.reasons || []),
            ...(item.decision_card?.quality_issues || []),
            ...(item.decision_card?.claims_issues || []),
        ].filter(Boolean);

        return (
            <WorkflowCard
                key={item.id}
                title={item.title_ar || item.original_title}
                subtitle={`${item.source_name || 'بدون مصدر'} • ${getCategoryLabel(item.category)}`}
                statusLabel={getWorkflowStatusLabel(item.status || 'ready_for_chief_approval')}
                chips={[
                    {
                        label: hasReservations ? 'تحفظات معلقة' : 'قرار نهائي مطلوب',
                        className: hasReservations ? 'border-orange-500/40 bg-orange-500/20 text-orange-200' : 'border-cyan-500/40 bg-cyan-500/20 text-cyan-200',
                    },
                ]}
                reason={getChiefReason(item)}
                nextActionLabel={hasReservations ? 'حسم التحفظات' : 'اتخذ القرار'}
                timestamp={item.updated_at}
                blockers={blockers}
                tone={hasReservations ? 'warn' : item.is_breaking ? 'danger' : 'default'}
                actions={
                    <div className="space-y-3">
                        {!!item.decision_card && (
                            <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-gray-200" dir="rtl">
                                <div className="flex flex-wrap items-center gap-2">
                                    <span className={`rounded-md border px-2 py-1 ${item.decision_card.risk_level === 'high' ? 'border-red-500/40 bg-red-500/10 text-red-200' : item.decision_card.risk_level === 'low' ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-200' : 'border-amber-500/40 bg-amber-500/10 text-amber-200'}`}>
                                        مستوى المخاطر: {item.decision_card.risk_level}
                                    </span>
                                    <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-cyan-200">جودة: {item.decision_card.quality_score ?? '-'}</span>
                                    <span className="rounded-md border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-violet-200">ادعاءات: {item.decision_card.claims_score ?? '-'}</span>
                                </div>
                            </div>
                        )}

                        <div className="grid grid-cols-1 gap-2 md:grid-cols-6">
                            <a href={item.work_id ? `/workspace-drafts?article_id=${item.id}&work_id=${item.work_id}` : `/workspace-drafts?article_id=${item.id}`} className="rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-center text-xs text-gray-200 hover:text-white">افتح في المحرر</a>
                            <button
                                onClick={() => submitChiefDecision(item, 'approve')}
                                disabled={chiefDecisionMutation.isPending}
                                data-tutorial={showChiefOverlay && tutorialChiefItem?.id === item.id ? 'chief-approve' : undefined}
                                className="flex items-center justify-center gap-1 rounded-xl border border-emerald-500/30 bg-emerald-500/20 px-3 py-2 text-xs text-emerald-200"
                            >
                                <CheckCircle2 className="h-4 w-4" /> اعتماد نهائي
                            </button>
                            <button onClick={() => submitChiefDecision(item, 'approve_with_reservations')} disabled={chiefDecisionMutation.isPending} className="rounded-xl border border-orange-500/30 bg-orange-500/20 px-3 py-2 text-xs text-orange-200">اعتماد بتحفظات</button>
                            <button onClick={() => submitChiefDecision(item, 'send_back')} disabled={chiefDecisionMutation.isPending} className="flex items-center justify-center gap-1 rounded-xl border border-amber-500/30 bg-amber-500/20 px-3 py-2 text-xs text-amber-200"><RotateCcw className="h-4 w-4" /> إعادة للمراجعة</button>
                            <button onClick={() => submitChiefDecision(item, 'reject')} disabled={chiefDecisionMutation.isPending} className="rounded-xl border border-red-500/30 bg-red-500/20 px-3 py-2 text-xs text-red-200">رفض</button>
                            <button onClick={() => setMemoryCaptureArticle(item)} className="rounded-xl border border-amber-500/30 bg-amber-500/20 px-3 py-2 text-xs text-amber-200">حفظ في الذاكرة</button>
                        </div>

                        <input type="text" value={note} onChange={(e) => setNotesMap((prev) => ({ ...prev, [item.id]: e.target.value }))} placeholder="سبب القرار (إلزامي للتحفظات أو الرفض)..." className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white placeholder:text-gray-500" dir="rtl" />
                    </div>
                }
            />
        );
    };

    const renderArticleCard = (article: ArticleBrief, options?: { nomination?: boolean; socialCopy?: boolean }) => {
        const action = getArticlePrimaryAction(article);

        return (
            <WorkflowCard
                key={article.id}
                title={article.title_ar || article.original_title}
                subtitle={`${article.source_name || 'بدون مصدر'} • ${getCategoryLabel(article.category)} • ${formatRelativeTime(article.created_at || article.crawled_at)}`}
                statusLabel={getWorkflowStatusLabel(article.status)}
                chips={article.is_breaking ? [{ label: 'عاجل', className: 'border-red-500/30 bg-red-500/10 text-red-200' }] : []}
                reason={getArticleReason(article)}
                nextActionLabel={action.label}
                timestamp={article.created_at || article.crawled_at}
                tone={article.is_breaking ? 'danger' : 'default'}
                primaryAction={
                    action.href
                        ? {
                              label: action.label,
                              href: action.href,
                              onClick: () =>
                                  trackNextAction('editorial', action.label, {
                                      ...surfaceDetails,
                                      article_id: article.id,
                                      article_status: article.status,
                                      target_href: action.href,
                                  }),
                          }
                        : undefined
                }
                actions={
                    <div className="space-y-3">
                        {article.summary && (
                            <div className="text-xs text-gray-300" dir="rtl">{truncate(article.summary, 220)}</div>
                        )}
                        <div className="grid grid-cols-1 gap-2 md:grid-cols-4">
                            {action.href ? <a href={action.href} className="rounded-xl border border-cyan-500/30 bg-cyan-500/20 px-3 py-2 text-center text-xs text-cyan-200">{action.label}</a> : null}
                            {options?.nomination ? (
                                <button onClick={() => nominateMutation.mutate(article.id)} disabled={!canNominate || nominateMutation.isPending} className="flex items-center justify-center gap-1 rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-xs text-gray-200 disabled:opacity-50"><Send className="h-4 w-4" /> ترشيح للتحرير</button>
                            ) : (
                                <a href={`/news/${article.id}`} className="rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-center text-xs text-gray-200 hover:text-white">افتح التفاصيل</a>
                            )}
                            {options?.socialCopy ? (
                                <button onClick={() => socialCopyMutation.mutate(article.id)} disabled={socialCopyMutation.isPending} className="rounded-xl border border-emerald-500/30 bg-emerald-500/20 px-3 py-2 text-xs text-emerald-200">نسخ النسخ الجاهزة</button>
                            ) : (
                                <a href={article.original_url || '#'} target="_blank" rel="noreferrer" className="rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-center text-xs text-gray-300 hover:text-white">المصدر</a>
                            )}
                            <button onClick={() => setMemoryCaptureArticle(article)} className="rounded-xl border border-amber-500/30 bg-amber-500/20 px-3 py-2 text-xs text-amber-200">حفظ في الذاكرة</button>
                        </div>
                    </div>
                }
            />
        );
    };
    const renderSocialCard = (item: SocialApprovedItem) => (
        <WorkflowCard
            key={item.article_id}
            title={item.title}
            subtitle={`${item.source_name || 'بدون مصدر'} • ${formatRelativeTime(item.updated_at)}`}
            statusLabel={getWorkflowStatusLabel('ready_for_manual_publish')}
            chips={[{ label: 'جاهز للتغطية الرقمية', className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' }]}
            reason="المادة معتمدة وجاهزة للاستخدام الرقمي أو النسخ لمنصات النشر."
            nextActionLabel="نسخ النسخ الجاهزة"
            timestamp={item.updated_at}
            tone="success"
            actions={
                <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                    <button onClick={() => socialCopyMutation.mutate(item.article_id)} disabled={socialCopyMutation.isPending} className="rounded-xl border border-cyan-500/30 bg-cyan-500/20 px-3 py-2 text-xs text-cyan-200">نسخ النسخ الجاهزة</button>
                    <a href={`/news/${item.article_id}`} className="rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-center text-xs text-gray-200">افتح المادة</a>
                    <a href={`/digital?article_id=${item.article_id}`} className="rounded-xl border border-white/20 bg-white/5 px-3 py-2 text-center text-xs text-gray-200">افتح التغطية الرقمية</a>
                </div>
            }
        />
    );

    const renderActiveTab = () => {
        if (isChief) {
            if (activeTab === 'pending') {
                if (chiefQueueQuery.isLoading) return <EmptyState message="جاري تحميل طابور الاعتماد..." />;
                if (!chiefPendingItems.length) return <EmptyState message="لا توجد مواد بانتظار اعتماد رئيس التحرير الآن." />;
                return <div className="space-y-3">{chiefPendingItems.map(renderChiefCard)}</div>;
            }

            if (activeTab === 'reservations') {
                if (chiefQueueQuery.isLoading) return <EmptyState message="جاري تحميل المواد ذات التحفظات..." />;
                if (!chiefReservationItems.length) return <EmptyState message="لا توجد مواد معلقة بتحفظات الآن." />;
                return <div className="space-y-3">{chiefReservationItems.map(renderChiefCard)}</div>;
            }

            if (activeTab === 'returned') {
                if (draftGeneratedQuery.isLoading) return <EmptyState message="جاري تحميل المواد العائدة للمراجعة..." />;
                if (!draftGeneratedItems.length) return <EmptyState message="لا توجد مواد في مسار المراجعة الآن." />;
                return (
                    <div className="space-y-3">
                        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-100" dir="rtl">هذه المواد عادت إلى مسار التحرير وهي تحت المتابعة قبل أن تعود إلى الاعتماد.</div>
                        {draftGeneratedItems.map((item) => renderArticleCard(item))}
                    </div>
                );
            }

            if (readyForManualQuery.isLoading) return <EmptyState message="جاري تحميل المواد الجاهزة للنشر اليدوي..." />;
            if (!readyForManualItems.length) return <EmptyState message="لا توجد مواد جاهزة للنشر اليدوي الآن." />;
            return <div className="space-y-3">{readyForManualItems.map((item) => renderArticleCard(item))}</div>;
        }

        if (activeTab === 'pending') {
            if (pendingCandidatesQuery.isLoading) return <EmptyState message="جاري تحميل المواد التي وصلت إلى نطاقك..." />;
            if (!pendingCandidates.length) return <EmptyState message="لا توجد مواد جديدة بانتظارك الآن." />;
            return <div className="space-y-3">{pendingCandidates.map((item) => renderArticleCard(item, { nomination: true }))}</div>;
        }

        if (activeTab === 'returned') {
            if (draftGeneratedQuery.isLoading) return <EmptyState message="جاري تحميل المواد العائدة للمراجعة..." />;
            if (!draftGeneratedItems.length) return <EmptyState message="لا توجد مواد عائدة للمراجعة الآن." />;
            return <div className="space-y-3">{draftGeneratedItems.map((item) => renderArticleCard(item))}</div>;
        }

        if (activeTab === 'reservations') {
            if (reservationsQuery.isLoading) return <EmptyState message="جاري تحميل المواد ذات التحفظات..." />;
            if (!reservationsItems.length) return <EmptyState message="لا توجد مواد بتحفظات الآن." />;
            return <div className="space-y-3">{reservationsItems.map((item) => renderArticleCard(item))}</div>;
        }

        if (readyForManualQuery.isLoading || (isSocial && socialFeedQuery.isLoading)) {
            return <EmptyState message="جاري تحميل المواد الجاهزة للنشر اليدوي..." />;
        }

        if (isSocial && socialItems.length > 0) {
            return <div className="space-y-3">{socialItems.map(renderSocialCard)}</div>;
        }

        if (!readyForManualItems.length) {
            return <EmptyState message="لا توجد مواد جاهزة للنشر اليدوي الآن." />;
        }

        return <div className="space-y-3">{readyForManualItems.map((item) => renderArticleCard(item, { socialCopy: isSocial }))}</div>;
    };

    return (
        <div className="space-y-6">
            <TutorialOverlay
                open={showChiefOverlay}
                stepLabel="الخطوة 2 / 2"
                title="اتخذ القرار"
                description="اقرأ الملخص سريعًا ثم اعتمد المادة الآن."
                targetSelector="[data-tutorial=\"chief-approve\"]"
                primaryLabel="اعتماد نهائي"
                onPrimary={handleChiefNext}
                onSkip={completeTutorial}
            />
            <div>
                <h1 className="text-2xl font-bold text-white">الاعتماد والمراجعة</h1>
                <p className="mt-1 text-sm text-gray-400">
                    {isChief
                        ? 'هذه الصفحة أصبحت طابور قرار واضح: ماذا ينتظر اعتمادك، ما عاد للمراجعة، وما أصبح جاهزًا للنشر اليدوي.'
                        : isSocial
                            ? 'هذه الصفحة تجمع لك المواد التي دخلت مسار التحرير، ما عاد للمراجعة، وما أصبح جاهزًا للنشر أو النسخ الرقمية.'
                            : 'هذه الصفحة تجمع لك ما دخل نطاقك الآن، ما عاد للمراجعة، وما يحتاج الإرسال أو الاستكمال قبل الاعتماد.'}
                </p>
            </div>

            {errorMessage && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{errorMessage}</div>}
            {successMessage && <div className="whitespace-pre-wrap rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">{successMessage}</div>}

            <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
                {tabs.map((tab) => (
                    <QueueTabButton key={tab.key} active={activeTab === tab.key} label={tab.label} count={tab.count} onClick={() => setActiveTab(tab.key)} />
                ))}
            </div>

            <div className="rounded-2xl border border-white/10 bg-black/20 p-4" dir="rtl">
                <div className="flex items-start gap-3">
                    <AlertTriangle className="mt-0.5 h-4 w-4 text-cyan-300" />
                    <div className="text-xs text-gray-300">
                        <p className="font-semibold text-white">{activeTabMeta.label}</p>
                        <p className="mt-1 text-gray-400">{activeTabMeta.helper}</p>
                    </div>
                </div>
            </div>

            {renderActiveTab()}

            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 text-xs text-gray-300" dir="rtl">
                <p className="flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-300" /> السياسة التشغيلية: لا يوجد نشر تلقائي. كل مادة تمر عبر الاعتماد التحريري ثم تصبح جاهزة للنشر اليدوي فقط بعد اجتياز البوابة.</p>
            </div>

            <WorkflowHelpPanel
                title="كيف نستخدم الاعتماد والمراجعة؟"
                items={[
                    {
                        title: 'بانتظار الاعتماد',
                        description: 'مواد دخلت القرار النهائي عند رئيس التحرير، ولا تنتقل للنشر إلا بعد الحسم.',
                    },
                    {
                        title: 'عاد للمراجعة',
                        description: 'مواد رجعت إلى التحرير وتحتاج استكمالًا أو إعادة إرسال قبل العودة للاعتماد.',
                    },
                    {
                        title: 'جاهز للنشر اليدوي',
                        description: 'مواد اجتازت البوابة التحريرية وأصبحت جاهزة للتسليم أو النشر اليدوي فقط.',
                    },
                ]}
            />

            {memoryCaptureArticle && (
                <MemoryQuickCaptureModal
                    open={Boolean(memoryCaptureArticle)}
                    onClose={() => setMemoryCaptureArticle(null)}
                    onSubmit={(payload) => quickCaptureMutation.mutate(payload)}
                    isSubmitting={quickCaptureMutation.isPending}
                    articleTitle={memoryCaptureArticle.title_ar || memoryCaptureArticle.original_title || null}
                    sourceLabel={memoryCaptureArticle.source_name || null}
                    suggestedSubtype="editorial_decision"
                />
            )}
            <ActionDialog
                open={Boolean(pendingChiefDecision)}
                title={pendingChiefDecision ? `تأكيد ${decisionLabel[pendingChiefDecision.decision]}` : 'تأكيد القرار'}
                description={
                    pendingChiefDecision ? (
                        <div className="space-y-3">
                            <p>
                                المادة:
                                <span className="mr-2 font-semibold text-white">
                                    {pendingChiefDecision.item.title_ar || pendingChiefDecision.item.original_title}
                                </span>
                            </p>
                            {pendingChiefDecision.blockersPreview.length ? (
                                <div className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-100">
                                    <p className="font-semibold">سيتم تجاوز هذه الملاحظات أو التحفظات:</p>
                                    <ul className="mt-2 list-disc space-y-1 pr-4">
                                        {pendingChiefDecision.blockersPreview.map((blocker) => (
                                            <li key={blocker}>{blocker}</li>
                                        ))}
                                    </ul>
                                </div>
                            ) : (
                                <p className="text-slate-300">سيُسجَّل القرار فورًا ضمن المسار التحريري ويُحدَّث وضع المادة.</p>
                            )}
                        </div>
                    ) : undefined
                }
                tone={
                    pendingChiefDecision?.decision === 'reject'
                        ? 'danger'
                        : pendingChiefDecision?.decision === 'approve_with_reservations'
                            ? 'warn'
                            : 'default'
                }
                confirmLabel={pendingChiefDecision ? decisionLabel[pendingChiefDecision.decision] : 'تأكيد'}
                isSubmitting={chiefDecisionMutation.isPending}
                onClose={() => setPendingChiefDecision(null)}
                onConfirm={confirmChiefDecision}
            />
        </div>
    );
}
