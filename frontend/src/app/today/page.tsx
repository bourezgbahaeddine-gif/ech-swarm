'use client';

import Link from 'next/link';
import { useMemo, type ComponentType } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
    AlertTriangle,
    ArrowLeft,
    CheckCircle2,
    Clock3,
    Inbox,
    LayoutDashboard,
    RefreshCw,
    Send,
    ShieldAlert,
    Zap,
} from 'lucide-react';

import {
    dashboardApi,
    editorialApi,
    newsApi,
    type ArticleBrief,
    type ChiefPendingItem,
    type DashboardNotification,
} from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatRelativeTime, getStatusColor, truncate } from '@/lib/utils';

type Role =
    | 'director'
    | 'editor_chief'
    | 'journalist'
    | 'social_media'
    | 'print_editor'
    | 'fact_checker'
    | 'observer';

type QueueTone = 'default' | 'warn' | 'danger' | 'success';

type QueueItem = {
    id: string;
    title: string;
    subtitle: string;
    workflowLabel: string;
    reason: string;
    nextAction: string;
    href: string;
    status: string;
    timestamp?: string | null;
    blockers?: string[];
    tone?: QueueTone;
};

type SummaryCardData = {
    label: string;
    value: number;
    hint: string;
    tone?: QueueTone;
};

function normalizeRole(role: string): Role | null {
    const value = (role || '').trim().toLowerCase();
    if (value === 'chief_editor' || value === 'editor_in_chief' || value === 'editor-chief') {
        return 'editor_chief';
    }
    const allowed: Role[] = [
        'director',
        'editor_chief',
        'journalist',
        'social_media',
        'print_editor',
        'fact_checker',
        'observer',
    ];
    return allowed.includes(value as Role) ? (value as Role) : null;
}

function articleTitle(article: ArticleBrief): string {
    return article.title_ar || article.original_title || `مادة #${article.id}`;
}

function articleTimestamp(article: ArticleBrief): string | null {
    return article.created_at || article.crawled_at || null;
}

function ageInHours(value?: string | null): number {
    if (!value) return 0;
    const time = new Date(value).getTime();
    if (!Number.isFinite(time)) return 0;
    return Math.max(0, (Date.now() - time) / 3_600_000);
}

function articleToQueueItem(
    article: ArticleBrief,
    config: {
        workflowLabel: string;
        reason: string;
        nextAction: string;
        href: string;
        tone?: QueueTone;
        blockers?: string[];
    },
): QueueItem {
    return {
        id: `article-${article.id}-${article.status}`,
        title: articleTitle(article),
        subtitle: `${article.source_name || 'بدون مصدر ظاهر'} · ${article.status || 'غير محدد'}`,
        workflowLabel: config.workflowLabel,
        reason: config.reason,
        nextAction: config.nextAction,
        href: config.href,
        status: article.status || 'unknown',
        timestamp: articleTimestamp(article),
        blockers: config.blockers || [],
        tone: config.tone,
    };
}

function chiefItemToQueueItem(
    item: ChiefPendingItem,
    config?: {
        workflowLabel?: string;
        nextAction?: string;
        href?: string;
        reason?: string;
        tone?: QueueTone;
    },
): QueueItem {
    const blockers = [
        ...(item.decision_card?.quality_issues || []),
        ...(item.decision_card?.claims_issues || []),
        ...(item.policy?.required_fixes || []),
    ].filter(Boolean);

    return {
        id: `chief-${item.id}-${item.status || 'unknown'}`,
        title: item.title_ar || item.original_title || `مادة #${item.id}`,
        subtitle: `${item.source_name || 'بدون مصدر ظاهر'} · ${item.status || 'بانتظار القرار'}`,
        workflowLabel: config?.workflowLabel || 'بانتظار اعتماد رئيس التحرير',
        reason:
            config?.reason ||
            (blockers[0]
                ? `وصلت إليك لأن المادة دخلت مرحلة الاعتماد ومعها تنبيه واضح: ${blockers[0]}`
                : 'وصلت إليك لأن المادة دخلت مرحلة اعتماد رئيس التحرير وتحتاج قرارًا نهائيًا.'),
        nextAction: config?.nextAction || 'اتخذ القرار',
        href: config?.href || (item.work_id ? `/workspace-drafts?article_id=${item.id}&work_id=${encodeURIComponent(item.work_id)}` : '/editorial'),
        status: item.status || 'ready_for_chief_approval',
        timestamp: item.updated_at,
        blockers,
        tone: config?.tone || (item.is_breaking ? 'danger' : blockers.length ? 'warn' : 'default'),
    };
}

function notificationToQueueItem(item: DashboardNotification): QueueItem {
    return {
        id: `notification-${item.id}`,
        title: item.title,
        subtitle: item.type,
        workflowLabel: 'تنبيه غرفة الأخبار',
        reason: item.message,
        nextAction: item.article_id ? 'افتح الخبر المرتبط' : 'افتح طابور اليوم',
        href: item.article_id ? `/news/${item.article_id}` : '/today',
        status: item.severity,
        timestamp: item.created_at,
        tone: item.severity === 'high' ? 'danger' : item.severity === 'medium' ? 'warn' : 'default',
    };
}

function SummaryCard({ label, value, hint, tone = 'default' }: SummaryCardData) {
    const toneClasses =
        tone === 'danger'
            ? 'border-rose-500/30 bg-rose-500/10 text-rose-100'
            : tone === 'warn'
              ? 'border-amber-500/30 bg-amber-500/10 text-amber-100'
              : tone === 'success'
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                : 'border-white/10 bg-white/5 text-white';

    return (
        <div className={cn('rounded-2xl border p-4', toneClasses)}>
            <div className="text-xs opacity-80">{label}</div>
            <div className="mt-2 text-3xl font-bold">{value}</div>
            <div className="mt-2 text-xs opacity-80">{hint}</div>
        </div>
    );
}

function WorkflowStrip({ items }: { items: Array<{ label: string; count: number; hint: string }> }) {
    return (
        <section className="rounded-3xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-2 text-white mb-3">
                <LayoutDashboard className="w-4 h-4 text-cyan-300" />
                <h2 className="text-sm font-semibold">المسار الحالي</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {items.map((item) => (
                    <div key={item.label} className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                        <div className="text-xs text-slate-400">{item.label}</div>
                        <div className="mt-2 text-2xl font-semibold text-white">{item.count}</div>
                        <div className="mt-2 text-xs text-slate-400 leading-6">{item.hint}</div>
                    </div>
                ))}
            </div>
        </section>
    );
}

function QueueSection({
    title,
    hint,
    icon: Icon,
    items,
    emptyLabel,
}: {
    title: string;
    hint: string;
    icon: ComponentType<{ className?: string }>;
    items: QueueItem[];
    emptyLabel: string;
}) {
    return (
        <section className="rounded-3xl border border-white/10 bg-[rgba(15,23,42,0.55)] p-4">
            <div className="flex items-center justify-between gap-3 mb-3">
                <div>
                    <div className="flex items-center gap-2 text-white">
                        <Icon className="w-4 h-4 text-cyan-300" />
                        <h2 className="text-lg font-semibold">{title}</h2>
                    </div>
                    <p className="text-xs text-slate-400 mt-1">{hint}</p>
                </div>
                <div className="text-xs text-slate-500">{items.length} عنصر</div>
            </div>

            {items.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-white/10 px-4 py-6 text-center text-sm text-slate-400">
                    {emptyLabel}
                </div>
            ) : (
                <div className="space-y-3">
                    {items.map((item) => (
                        <div
                            key={item.id}
                            className={cn(
                                'rounded-2xl border px-4 py-4',
                                item.tone === 'danger'
                                    ? 'border-rose-500/25 bg-rose-500/10'
                                    : item.tone === 'warn'
                                      ? 'border-amber-500/25 bg-amber-500/10'
                                      : item.tone === 'success'
                                        ? 'border-emerald-500/25 bg-emerald-500/10'
                                        : 'border-white/10 bg-white/5',
                            )}
                        >
                            <div className="flex items-start justify-between gap-4">
                                <div className="min-w-0">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h3 className="text-sm font-semibold text-white leading-6">{item.title}</h3>
                                        <span className={cn('px-2 py-0.5 rounded-md text-[10px] font-medium border', getStatusColor((item.status || '').toLowerCase()))}>
                                            {item.status}
                                        </span>
                                        <span className="rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-300">
                                            {item.workflowLabel}
                                        </span>
                                    </div>
                                    <div className="mt-1 text-xs text-slate-400">{item.subtitle}</div>
                                    <div className="mt-3 text-sm text-slate-200 leading-6">{truncate(item.reason, 180)}</div>
                                    <div className="mt-2 text-xs text-cyan-200">
                                        الإجراء التالي: <span className="font-semibold">{item.nextAction}</span>
                                    </div>
                                    {item.blockers && item.blockers.length > 0 && (
                                        <div className="mt-3 flex flex-wrap gap-1.5">
                                            {item.blockers.slice(0, 2).map((blocker) => (
                                                <span
                                                    key={`${item.id}-${blocker}`}
                                                    className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-100"
                                                >
                                                    عائق: {truncate(blocker, 80)}
                                                </span>
                                            ))}
                                        </div>
                                    )}
                                </div>

                                <div className="flex shrink-0 flex-col items-end gap-3">
                                    {item.timestamp && (
                                        <div className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                                            <Clock3 className="w-3.5 h-3.5" />
                                            {formatRelativeTime(item.timestamp)}
                                        </div>
                                    )}
                                    <Link
                                        href={item.href}
                                        className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100 hover:bg-cyan-500/20"
                                    >
                                        <span>{item.nextAction}</span>
                                        <ArrowLeft className="w-3.5 h-3.5" />
                                    </Link>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </section>
    );
}

export default function TodayPage() {
    const { user } = useAuth();
    const role = normalizeRole(user?.role || '');
    const isChiefFlow = role === 'editor_chief' || role === 'director';
    const isAuthorFlow = !isChiefFlow;

    const pendingCandidatesQuery = useQuery({
        queryKey: ['today-pending-candidates'],
        queryFn: async () => (await newsApi.pending(12)).data,
        enabled: isAuthorFlow,
        refetchInterval: 30_000,
    });

    const draftGeneratedQuery = useQuery({
        queryKey: ['today-draft-generated'],
        queryFn: async () => (await newsApi.list({ page: 1, per_page: 12, status: 'draft_generated' })).data.items,
        enabled: role !== 'observer',
        refetchInterval: 30_000,
    });

    const reservationsQuery = useQuery({
        queryKey: ['today-reservations'],
        queryFn: async () => (await newsApi.list({ page: 1, per_page: 12, status: 'approval_request_with_reservations' })).data.items,
        enabled: role !== 'observer',
        refetchInterval: 30_000,
    });

    const readyManualPublishQuery = useQuery({
        queryKey: ['today-ready-manual-publish'],
        queryFn: async () => (await newsApi.list({ page: 1, per_page: 12, status: 'ready_for_manual_publish' })).data.items,
        enabled: isChiefFlow,
        refetchInterval: 30_000,
    });

    const chiefPendingQuery = useQuery({
        queryKey: ['today-chief-pending'],
        queryFn: async () => (await editorialApi.chiefPending(12)).data,
        enabled: isChiefFlow,
        refetchInterval: 30_000,
    });

    const breakingQuery = useQuery({
        queryKey: ['today-breaking'],
        queryFn: async () => (await newsApi.breaking(6)).data,
        enabled: role !== 'observer',
        refetchInterval: 20_000,
    });

    const notificationsQuery = useQuery({
        queryKey: ['today-notifications'],
        queryFn: async () => (await dashboardApi.notifications({ limit: 12 })).data.items,
        enabled: role !== 'observer',
        refetchInterval: 20_000,
    });

    const pendingCandidates = useMemo(() => pendingCandidatesQuery.data || [], [pendingCandidatesQuery.data]);
    const draftGenerated = useMemo(() => draftGeneratedQuery.data || [], [draftGeneratedQuery.data]);
    const reservations = useMemo(() => reservationsQuery.data || [], [reservationsQuery.data]);
    const readyManualPublish = useMemo(() => readyManualPublishQuery.data || [], [readyManualPublishQuery.data]);
    const chiefPending = useMemo(() => chiefPendingQuery.data || [], [chiefPendingQuery.data]);
    const breaking = useMemo(() => breakingQuery.data || [], [breakingQuery.data]);
    const notifications = useMemo(() => notificationsQuery.data || [], [notificationsQuery.data]);

    const journalistNow = useMemo(() => {
        const returned = reservations.slice(0, 3).map((article) =>
            articleToQueueItem(article, {
                workflowLabel: 'عاد من الاعتماد بتحفظات',
                reason: 'ظهرت لك الآن لأن المادة رجعت من رئيس التحرير مع ملاحظات واضحة وتحتاج تعديلًا سريعًا قبل إعادة الإرسال.',
                nextAction: 'افتح المسودة وعدّل',
                href: `/workspace-drafts?article_id=${article.id}`,
                tone: 'warn',
            }),
        );
        const urgentBreaking = breaking
            .filter((article) => article.status === 'candidate' || article.status === 'classified')
            .slice(0, 3)
            .map((article) =>
                articleToQueueItem(article, {
                    workflowLabel: 'مرشّح عاجل في طابور الأخبار',
                    reason: 'دخلت هذه المادة نطاقك لأن النظام رصدها كمادة عاجلة وتحتاج قرارًا تحريريًا سريعًا.',
                    nextAction: 'افتح طابور الأخبار',
                    href: '/news?status=candidate',
                    tone: 'danger',
                }),
            );
        return [...returned, ...urgentBreaking].slice(0, 6);
    }, [breaking, reservations]);

    const journalistNext = useMemo(() => {
        const followUps = draftGenerated.slice(0, 6).map((article) =>
            articleToQueueItem(article, {
                workflowLabel: 'مسودة قيد الاستكمال',
                reason: 'المادة موجودة في مرحلة draft_generated؛ أي أنها دخلت مساحة التحرير وتحتاج استكمالًا أو فحصًا سريعًا ثم إرسالًا للاعتماد.',
                nextAction: 'أكمل في المحرر',
                href: `/workspace-drafts?article_id=${article.id}`,
            }),
        );
        const freshCandidates = pendingCandidates.slice(0, Math.max(0, 6 - followUps.length)).map((article) =>
            articleToQueueItem(article, {
                workflowLabel: 'مرشّح جديد في طابور الأخبار',
                reason: 'دخلت المادة حديثًا إلى قائمة الأخبار وتنتظر بدء العمل التحريري عليها.',
                nextAction: 'افتح قائمة الأخبار',
                href: '/news?status=candidate',
            }),
        );
        return [...followUps, ...freshCandidates].slice(0, 6);
    }, [draftGenerated, pendingCandidates]);

    const journalistRisk = useMemo(() => {
        const staleDrafts = draftGenerated
            .filter((article) => ageInHours(articleTimestamp(article)) >= 4)
            .slice(0, 4)
            .map((article) =>
                articleToQueueItem(article, {
                    workflowLabel: 'مسودة متأخرة',
                    reason: 'هذه المادة بقيت في draft_generated أكثر من اللازم، ما يعني أنها قد تتأخر عن المسار الطبيعي إذا لم تُستكمل الآن.',
                    nextAction: 'استكملها الآن',
                    href: `/workspace-drafts?article_id=${article.id}`,
                    tone: 'warn',
                }),
            );
        const criticalNotifications = notifications
            .filter((item) => item.severity === 'high')
            .slice(0, Math.max(0, 4 - staleDrafts.length))
            .map(notificationToQueueItem);
        return [...staleDrafts, ...criticalNotifications].slice(0, 4);
    }, [draftGenerated, notifications]);

    const chiefNow = useMemo(() => {
        return chiefPending
            .slice()
            .sort((a, b) => Number(b.is_breaking) - Number(a.is_breaking) || b.importance_score - a.importance_score)
            .slice(0, 6)
            .map((item) =>
                chiefItemToQueueItem(item, {
                    workflowLabel: 'بانتظار قرار رئيس التحرير',
                    nextAction: 'اتخذ القرار',
                    reason: item.is_breaking
                        ? 'المادة عاجلة ووصلت الآن إلى مرحلة الاعتماد النهائي، لذلك تحتاج حسمًا مباشرًا.'
                        : undefined,
                }),
            );
    }, [chiefPending]);

    const chiefNext = useMemo(() => {
        const readyItems = readyManualPublish.slice(0, 3).map((article) =>
            articleToQueueItem(article, {
                workflowLabel: 'جاهز للنشر اليدوي',
                reason: 'اجتازت المادة الاعتماد وأصبحت في ready_for_manual_publish، أي أنها جاهزة للتسليم أو النشر اليدوي.',
                nextAction: 'راجع الجاهز للنشر',
                href: '/news?status=ready_for_manual_publish',
                tone: 'success',
            }),
        );
        const reservationItems = reservations.slice(0, Math.max(0, 6 - readyItems.length)).map((article) =>
            articleToQueueItem(article, {
                workflowLabel: 'اعتماد بتحفظات',
                reason: 'هذه المواد ما زالت في حالة تحفظات؛ تحتاج متابعة حتى لا تبقى عالقة بين التحرير والاعتماد.',
                nextAction: 'راجع التحفظات',
                href: '/editorial',
                tone: 'warn',
            }),
        );
        return [...readyItems, ...reservationItems].slice(0, 6);
    }, [readyManualPublish, reservations]);

    const chiefRisk = useMemo(() => {
        const staleApprovals = chiefPending
            .filter((item) => ageInHours(item.updated_at) >= 2)
            .slice(0, 4)
            .map((item) =>
                chiefItemToQueueItem(item, {
                    workflowLabel: 'اعتماد متأخر',
                    nextAction: 'احسم القرار الآن',
                    reason: 'هذه المادة بقيت في طابور الاعتماد أكثر من الحد المرغوب، وقد تعطل المسار إن لم تُحسم الآن.',
                    tone: 'danger',
                }),
            );
        const criticalNotifications = notifications
            .filter((item) => item.severity === 'high')
            .slice(0, Math.max(0, 4 - staleApprovals.length))
            .map(notificationToQueueItem);
        return [...staleApprovals, ...criticalNotifications].slice(0, 4);
    }, [chiefPending, notifications]);

    const summaryCards = useMemo<SummaryCardData[]>(() => {
        if (isChiefFlow) {
            const overdue = chiefPending.filter((item) => ageInHours(item.updated_at) >= 2).length;
            return [
                {
                    label: 'بانتظارك',
                    value: chiefPending.length,
                    hint: 'مواد دخلت مرحلة قرار رئيس التحرير.',
                },
                {
                    label: 'متأخر',
                    value: overdue,
                    hint: 'مواد تحتاج حسمًا سريعًا حتى لا يتعطل المسار.',
                    tone: overdue > 0 ? 'danger' : 'default',
                },
                {
                    label: 'جاهز اليوم',
                    value: readyManualPublish.length,
                    hint: 'مواد جاهزة للنشر اليدوي بعد الاعتماد.',
                    tone: readyManualPublish.length > 0 ? 'success' : 'default',
                },
            ];
        }

        return [
            {
                label: 'جديد لك',
                value: pendingCandidates.length,
                hint: 'مواد دخلت طابور الأخبار وتحتاج بدء العمل.',
            },
            {
                label: 'قيد الكتابة',
                value: draftGenerated.length,
                hint: 'مواد في draft_generated وتحتاج استكمالًا أو إرسالًا للاعتماد.',
                tone: draftGenerated.length > 6 ? 'warn' : 'default',
            },
            {
                label: 'عاد للمراجعة',
                value: reservations.length,
                hint: 'مواد رجعت بتحفظات أو ملاحظات.',
                tone: reservations.length > 0 ? 'warn' : 'default',
            },
        ];
    }, [draftGenerated.length, isChiefFlow, pendingCandidates.length, chiefPending, readyManualPublish.length, reservations.length]);

    const workflowItems = useMemo(() => {
        if (isChiefFlow) {
            return [
                {
                    label: 'بانتظار الاعتماد',
                    count: chiefPending.length,
                    hint: 'المواد التي دخلت نطاق قرار رئيس التحرير الآن.',
                },
                {
                    label: 'بتحفظات',
                    count: reservations.length,
                    hint: 'مواد تحتاج متابعة بعد قرار بتحفظات.',
                },
                {
                    label: 'جاهز للنشر اليدوي',
                    count: readyManualPublish.length,
                    hint: 'مواد اجتازت الاعتماد ويمكن تسليمها للنشر.',
                },
            ];
        }

        return [
            {
                label: 'مرشّح جديد',
                count: pendingCandidates.length,
                hint: 'مواد دخلت الأخبار وتنتظر بدء العمل.',
            },
            {
                label: 'draft_generated',
                count: draftGenerated.length,
                hint: 'مواد داخل التحرير وتحتاج استكمالًا أو فحصًا سريعًا.',
            },
            {
                label: 'عاد بتحفظات',
                count: reservations.length,
                hint: 'مواد رجعت من الاعتماد وتحتاج تعديلًا قبل إعادة الإرسال.',
            },
        ];
    }, [draftGenerated.length, isChiefFlow, pendingCandidates.length, chiefPending.length, readyManualPublish.length, reservations.length]);

    const isLoading =
        pendingCandidatesQuery.isLoading ||
        draftGeneratedQuery.isLoading ||
        reservationsQuery.isLoading ||
        readyManualPublishQuery.isLoading ||
        chiefPendingQuery.isLoading ||
        breakingQuery.isLoading ||
        notificationsQuery.isLoading;

    return (
        <div className="space-y-6" dir="rtl">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-white inline-flex items-center gap-2">
                        <LayoutDashboard className="w-6 h-6 text-cyan-300" />
                        اليوم
                    </h1>
                    <p className="text-sm text-slate-400 mt-2 max-w-3xl leading-7">
                        {isChiefFlow
                            ? 'هذه الصفحة تعرض ما دخل نطاق قرارك الآن، ولماذا وصل إليك، وما الخطوة التالية داخل مسار الاعتماد والنشر اليدوي.'
                            : 'هذه الصفحة تعرض ما دخل نطاق عملك الآن، ولماذا ظهر لك، وما الخطوة التالية داخل مسار الأخبار والتحرير.'}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Link href={isChiefFlow ? '/editorial' : '/news'} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 hover:text-white">
                        <Inbox className="w-4 h-4" />
                        {isChiefFlow ? 'فتح طابور الاعتماد' : 'فتح طابور الأخبار'}
                    </Link>
                    <Link href="/workspace-drafts" className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100 hover:bg-cyan-500/20">
                        <Send className="w-4 h-4" />
                        فتح المسودات
                    </Link>
                </div>
            </div>

            <WorkflowStrip items={workflowItems} />

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {summaryCards.map((card) => (
                    <SummaryCard key={card.label} {...card} />
                ))}
            </div>

            {isLoading ? (
                <div className="rounded-3xl border border-white/10 bg-[rgba(15,23,42,0.55)] p-8 text-center text-slate-400">
                    <RefreshCw className="w-5 h-5 animate-spin inline-block ml-2" />
                    جاري تجهيز طابور اليوم...
                </div>
            ) : (
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                    <QueueSection
                        title={isChiefFlow ? 'دخل نطاقك الآن' : 'ابدأ الآن'}
                        hint={isChiefFlow ? 'المواد التي تحتاج قرارًا مباشرًا من رئيس التحرير.' : 'أهم ما دخل نطاقك الآن ويحتاج بدء العمل أو تصحيحًا سريعًا.'}
                        icon={Zap}
                        items={isChiefFlow ? chiefNow : journalistNow}
                        emptyLabel={isChiefFlow ? 'لا توجد مواد حرجة بانتظار القرار الآن.' : 'لا توجد عناصر عاجلة الآن.'}
                    />

                    <QueueSection
                        title="الخطوة التالية في المسار"
                        hint={isChiefFlow ? 'العناصر التالية بعد حسم العاجل: جاهز للنشر اليدوي أو يحتاج متابعة بتحفظات.' : 'المواد التالية في مسار الأخبار والتحرير بعد إنهاء العاجل.'}
                        icon={CheckCircle2}
                        items={isChiefFlow ? chiefNext : journalistNext}
                        emptyLabel="لا توجد عناصر إضافية في هذه اللحظة."
                    />

                    <QueueSection
                        title="ما الذي يعيق التقدم؟"
                        hint={isChiefFlow ? 'مواد متأخرة أو عالية الخطورة قد تعطل الاعتماد.' : 'مواد قد تتأخر أو تنبيهات تستحق الانتباه قبل أن تتعطل.'}
                        icon={isChiefFlow ? ShieldAlert : AlertTriangle}
                        items={isChiefFlow ? chiefRisk : journalistRisk}
                        emptyLabel="لا توجد عناصر متعثرة حاليًا."
                    />
                </div>
            )}

            <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
                <h2 className="text-sm font-semibold text-white mb-2">كيف نقرأ هذه الصفحة؟</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-300">
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                        <div className="font-semibold text-white mb-1">ما الذي دخل نطاقي؟</div>
                        <div>كل بطاقة مرتبطة بحالة حقيقية في الـ workflow مثل draft_generated أو ready_for_manual_publish أو بانتظار الاعتماد.</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                        <div className="font-semibold text-white mb-1">لماذا ظهرت لي؟</div>
                        <div>كل عنصر يشرح سبب ظهوره الآن حتى لا نترك المستخدم يفسّر الحالة بنفسه أو يضيع بين الصفحات.</div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                        <div className="font-semibold text-white mb-1">ما الذي يمنع التقدم؟</div>
                        <div>العناصر المتأخرة أو التي تحمل تحفظات أو عوائق تظهر منفصلة حتى لا تضيع داخل القوائم العامة.</div>
                    </div>
                </div>
            </div>
        </div>
    );
}
