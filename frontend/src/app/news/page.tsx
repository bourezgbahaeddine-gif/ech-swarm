'use client';

import Link from 'next/link';
import { Suspense, useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { isAxiosError } from 'axios';
import { newsApi, dashboardApi, editorialApi, type ArticleBrief, type DashboardNotification } from '@/lib/api';
import { cn, formatRelativeTime, getStatusColor, getCategoryLabel, isFreshBreaking, truncate } from '@/lib/utils';
import { useAuth } from '@/lib/auth';
import { WorkflowCard } from '@/components/workflow/WorkflowCard';
import { WorkflowHelpPanel } from '@/components/workflow/WorkflowHelpPanel';
import { trackNextAction, useTrackSurfaceView } from '@/lib/ux-telemetry';
import { TutorialOverlay } from '@/components/onboarding/TutorialOverlay';
import { useTutorialState } from '@/lib/tutorial';
import {
    Newspaper, Search, ExternalLink,
    ChevronLeft, ChevronRight,
    RefreshCw,
    Rows3, TableProperties, ArrowLeft,
} from 'lucide-react';

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

function NewsPageContent() {
    const queryClient = useQueryClient();
    const searchParams = useSearchParams();
    const router = useRouter();
    const { state: tutorialState, update: updateTutorial, complete: completeTutorial, active: tutorialActive } = useTutorialState();
    const { user } = useAuth();
    const initialStatus = searchParams.get('status') || '';
    const initialCategory = searchParams.get('category') || '';
    const initialBreakingParam = searchParams.get('breaking');
    const [page, setPage] = useState(1);
    const [status, setStatus] = useState<string>(initialStatus);
    const [category, setCategory] = useState<string>(initialCategory);
    const [search, setSearch] = useState(() => searchParams.get('q') || '');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [isBreaking, setIsBreaking] = useState<boolean | null>(() => {
        if (initialBreakingParam === 'true') return true;
        if (initialBreakingParam === 'false') return false;
        return null;
    });
    const [viewMode, setViewMode] = useState<'queue' | 'table'>('queue');
    const [draftEditor, setDraftEditor] = useState<{
        articleId: number;
        action: string;
        draftId?: number;
        workId?: string;
        version?: number;
        title: string;
        body: string;
    } | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [infoMessage, setInfoMessage] = useState<string | null>(null);
    const [liveRefreshUntil, setLiveRefreshUntil] = useState<number>(0);
    const kickLiveRefresh = (seconds = 30) => setLiveRefreshUntil(Date.now() + seconds * 1000);

    useEffect(() => {
        const t = setTimeout(() => setDebouncedSearch(search.trim()), 400);
        return () => clearTimeout(t);
    }, [search]);

    useEffect(() => {
        if (tutorialActive && tutorialRole === 'journalist' && tutorialStep === 'today_open') {
            updateTutorial({ step: 'news_open' });
        }
    }, [tutorialActive, tutorialRole, tutorialStep, updateTutorial]);

    useEffect(() => {
        if (showNewsOverlay && viewMode !== 'queue') {
            setViewMode('queue');
        }
    }, [showNewsOverlay, viewMode]);

    const surfaceDetails = useMemo(
        () => ({
            role: user?.role || 'guest',
            view_mode: viewMode,
            status_filter: status || 'all',
            category_filter: category || 'all',
            breaking_filter: isBreaking === null ? 'all' : isBreaking ? 'true' : 'false',
        }),
        [category, isBreaking, status, user?.role, viewMode],
    );

    useTrackSurfaceView('news', surfaceDetails);

    const { data, isLoading } = useQuery({
        queryKey: ['news', page, status, category, debouncedSearch, isBreaking],
        queryFn: () => newsApi.list({
            page,
            per_page: 20,
            status: status || undefined,
            category: category || undefined,
            search: debouncedSearch || undefined,
            sort_by: 'created_at',
            is_breaking: isBreaking === null ? undefined : isBreaking,
            local_first: true,
        }),
        refetchInterval: () => (Date.now() < liveRefreshUntil ? 2000 : false),
        refetchOnWindowFocus: true,
    });

    const refreshPipeline = useMutation({
        mutationFn: async () => {
            // Practical flow for newsroom: one click updates ingestion + routing.
            await dashboardApi.triggerScout();
            await dashboardApi.triggerRouter();
        },
        onSuccess: async () => {
            setPage(1);
            await queryClient.invalidateQueries({ queryKey: ['news'] });
            await queryClient.invalidateQueries({ queryKey: ['news-insights'] });
            await queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
            // Keep UI hot for queued jobs so new rows appear quickly.
            kickLiveRefresh(75);
            setErrorMessage(null);
            setInfoMessage('تم تشغيل التحديث الشامل (كشاف + موجه) وجلب آخر العناصر');
        },
        onError: (err: unknown) => setErrorMessage(getApiErrorMessage(err, 'فشل تحديث الأخبار')),
    });



    const saveDraftMutation = useMutation({
        mutationFn: (payload: {
            articleId: number;
            draftId?: number;
            title?: string;
            body: string;
            source_action: string;
            version?: number;
        }) => {
            if (payload.draftId && payload.version) {
                return editorialApi.updateDraft(payload.articleId, payload.draftId, {
                    title: payload.title,
                    body: payload.body,
                    note: 'updated_from_modal',
                    version: payload.version,
                });
            }
            return editorialApi.createDraft(payload.articleId, {
                title: payload.title,
                body: payload.body,
                source_action: payload.source_action,
                note: 'created_from_modal',
            });
        },
        onSuccess: (res) => {
            setDraftEditor((prev) => prev ? {
                ...prev,
                draftId: res.data?.id || prev.draftId,
                workId: res.data?.work_id || prev.workId,
                version: res.data?.version || prev.version,
            } : prev);
            setErrorMessage(null);
        },
        onError: (err: unknown) => setErrorMessage(getApiErrorMessage(err, 'تعذر حفظ المسودة')),
    });

    const applyDraftMutation = useMutation({
        mutationFn: (payload: { articleId: number; draftId: number }) =>
            editorialApi.applyDraft(payload.articleId, payload.draftId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['news'] });
            setDraftEditor(null);
            setErrorMessage(null);
        },
        onError: (err: unknown) => setErrorMessage(getApiErrorMessage(err, 'تعذر تطبيق المسودة على الخبر')),
    });


    const refresh = () => refreshPipeline.mutate();

    const articles = useMemo<ArticleBrief[]>(() => data?.data?.items ?? [], [data?.data?.items]);
    const totalPages = data?.data?.pages || 0;
    const articleIds = useMemo(() => articles.map((a) => a.id), [articles]);

    const { data: insightsData } = useQuery({
        queryKey: ['news-insights', articleIds.join(',')],
        queryFn: () => newsApi.insights(articleIds),
        enabled: articleIds.length > 0,
        staleTime: 0,
        refetchInterval: () => (Date.now() < liveRefreshUntil ? 1500 : false),
        refetchOnWindowFocus: true,
    });

    const insightsMap = useMemo(() => {
        const map = new Map<number, { cluster_size: number; cluster_id?: number | null; relation_count: number }>();
        const items = insightsData?.data || [];
        for (const item of items) {
            map.set(item.article_id, {
                cluster_size: item.cluster_size,
                cluster_id: item.cluster_id,
                relation_count: item.relation_count,
            });
        }
        return map;
    }, [insightsData?.data]);

    const visibleArticles = useMemo(() => {
        const seenClusters = new Set<number>();
        const out: ArticleBrief[] = [];
        for (const article of articles) {
            const insight = insightsMap.get(article.id);
            const clusterSize = insight?.cluster_size || 0;
            const clusterId = insight?.cluster_id;
            if (clusterSize > 1 && clusterId) {
                if (seenClusters.has(clusterId)) {
                    continue;
                }
                seenClusters.add(clusterId);
            }
            out.push(article);
        }
        return out;
    }, [articles, insightsMap]);

    const tutorialRole = tutorialState.role;
    const tutorialStep = tutorialState.step;
    const tutorialArticle = visibleArticles[0];
    const showNewsOverlay = tutorialActive && tutorialRole === 'journalist' && tutorialStep === 'news_open';

    const handleNewsNext = () => {
        if (tutorialArticle) {
            updateTutorial({ step: 'editor_edit' });
            router.push(`/workspace-drafts?article_id=${tutorialArticle.id}`);
            return;
        }
        completeTutorial();
    };

    const { data: dailySnapshot, isLoading: dailySnapshotLoading } = useQuery({
        queryKey: ['news-daily-snapshot'],
        queryFn: async () => {
            const [handoffRes, draftRes, reservationsRes, readyRes, notificationsRes] = await Promise.all([
                newsApi.list({ page: 1, per_page: 1, status: 'approved_handoff' }),
                newsApi.list({ page: 1, per_page: 1, status: 'draft_generated' }),
                newsApi.list({ page: 1, per_page: 1, status: 'approval_request_with_reservations' }),
                newsApi.list({ page: 1, per_page: 1, status: 'ready_for_manual_publish' }),
                dashboardApi.notifications({ limit: 40 }),
            ]);

            const notifications = (notificationsRes.data?.items || []) as DashboardNotification[];
            const urgentAlerts = notifications.filter((item) => item.severity === 'high').length;

            return {
                draftsReadyForEditing: (handoffRes.data?.total || 0) + (draftRes.data?.total || 0),
                needsVerification: reservationsRes.data?.total || 0,
                readyForManualPublish: readyRes.data?.total || 0,
                totalNotifications: notifications.length,
                urgentAlerts,
            };
        },
        refetchInterval: 20000,
        refetchOnWindowFocus: true,
    });

    const statuses = [
        '',
        'new',
        'classified',
        'candidate',
        'approved_handoff',
        'draft_generated',
        'ready_for_chief_approval',
        'approval_request_with_reservations',
        'ready_for_manual_publish',
        'approved',
        'rejected',
        'published',
    ];
    const categories = ['', 'politics', 'economy', 'sports', 'technology', 'local_algeria', 'international', 'culture', 'society', 'health'];

    const getStatusLabel = (status: string) => {
        const s = (status || '').toLowerCase();
        const labels: Record<string, string> = {
            new: 'جديد',
            cleaned: 'منظف',
            classified: 'مصنف',
            candidate: 'مرشح',
            approved_handoff: 'جاهز للكاتب',
            draft_generated: 'مسودة جاهزة',
            ready_for_chief_approval: 'بانتظار اعتماد رئيس التحرير',
            approval_request_with_reservations: 'طلب اعتماد بتحفظات',
            ready_for_manual_publish: 'جاهز للنشر اليدوي',
            approved: 'مقبول',
            rejected: 'مرفوض',
            published: 'منشور',
            archived: 'مؤرشف',
        };
        return labels[s] || status;
    };

    const role = (user?.role || '').toLowerCase();
    const canApproveReject = role === 'director' || role === 'editor_chief';
    const isSocialRole = role === 'social_media';

    const getReasonForArticle = (article: ArticleBrief) => {
        const normalizedStatus = (article.status || '').toLowerCase();
        if (article.is_breaking) {
            return 'ظهرت كمادة عاجلة وتحتاج حسمًا سريعًا داخل غرفة الأخبار.';
        }
        if (normalizedStatus === 'candidate' || normalizedStatus === 'classified') {
            return 'دخلت طابور الأخبار وتنتظر بدء العمل التحريري أو التوجيه إلى المسودة.';
        }
        if (normalizedStatus === 'approved_handoff' || normalizedStatus === 'draft_generated') {
            return 'وصلت إلى مرحلة المسودة وتحتاج تحريرًا أو مراجعة قبل الإرسال للاعتماد.';
        }
        if (normalizedStatus === 'ready_for_chief_approval') {
            return canApproveReject
                ? 'وصلت إليك لأن النسخة أصبحت جاهزة لقرار رئيس التحرير.'
                : 'هذه المادة بانتظار قرار رئيس التحرير بعد انتهاء التحرير.';
        }
        if (normalizedStatus === 'approval_request_with_reservations') {
            return canApproveReject
                ? 'هذه المادة تحمل تحفظات أو ملاحظات وتحتاج قرارًا واضحًا.'
                : 'عادت هذه المادة بتحفظات أو ملاحظات وتحتاج تحديثًا ثم إعادة الإرسال.';
        }
        if (normalizedStatus === 'ready_for_manual_publish') {
            return 'اجتازت مسار الاعتماد وأصبحت جاهزة للنشر اليدوي أو التسليم للنشر.';
        }
        if (normalizedStatus === 'published') {
            return 'هذه المادة منشورة ويمكن الرجوع إلى تفاصيلها أو استثمارها في السوشيال.';
        }
        if (normalizedStatus === 'rejected') {
            return 'تم رفض هذه المادة وتحتاج مراجعة السبب قبل إعادة العمل عليها.';
        }
        return 'هذه المادة موجودة في المسار التحريري ويمكن فتحها لمعرفة تفاصيل أكثر.';
    };

    const getNextActionForArticle = (article: ArticleBrief) => {
        const normalizedStatus = (article.status || '').toLowerCase();
        if (normalizedStatus === 'candidate' || normalizedStatus === 'classified') {
            return { label: 'ابدأ التحرير', href: `/workspace-drafts?article_id=${article.id}` };
        }
        if (normalizedStatus === 'approved_handoff' || normalizedStatus === 'draft_generated') {
            return { label: 'أكمل المسودة', href: `/workspace-drafts?article_id=${article.id}` };
        }
        if (normalizedStatus === 'ready_for_chief_approval' || normalizedStatus === 'approval_request_with_reservations') {
            return canApproveReject
                ? { label: 'افتح طابور الاعتماد', href: '/editorial' }
                : { label: 'راجع في المحرر', href: `/workspace-drafts?article_id=${article.id}` };
        }
        if (normalizedStatus === 'ready_for_manual_publish') {
            return isSocialRole
                ? { label: 'راجع الجاهز للنشر', href: '/editorial' }
                : { label: 'افتح التفاصيل', href: `/news/${article.id}` };
        }
        if (normalizedStatus === 'published') {
            return { label: 'افتح التفاصيل', href: `/news/${article.id}` };
        }
        return { label: 'افتح المادة', href: `/news/${article.id}` };
    };

    const getImportanceTone = (article: ArticleBrief) => {
        if (article.is_breaking) return 'danger' as const;
        if (article.importance_score >= 8) return 'danger' as const;
        if (article.importance_score >= 6) return 'warn' as const;
        if (article.importance_score <= 3) return 'success' as const;
        return 'default' as const;
    };

    const getImportanceChip = (article: ArticleBrief) => {
        if (article.is_breaking) {
            return { label: 'أولوية عاجلة', className: 'border-rose-500/30 bg-rose-500/10 text-rose-200' };
        }
        if (article.importance_score >= 8) {
            return { label: 'أولوية عالية', className: 'border-amber-500/30 bg-amber-500/10 text-amber-200' };
        }
        if (article.importance_score >= 6) {
            return { label: 'أولوية متوسطة', className: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200' };
        }
        return { label: 'أولوية عادية', className: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' };
    };

    return (
        <div className="space-y-6">
            <TutorialOverlay
                open={showNewsOverlay}
                stepLabel="الخطوة 2 / 4"
                title="افتح المادة الأولى"
                description="هذه مادة وصلت إليك للعمل عليها. افتح المحرر للبدء الفعلي."
                targetSelector="[data-tutorial=\"news-first-edit\"]"
                primaryLabel="افتح المحرر"
                onPrimary={handleNewsNext}
                onSkip={completeTutorial}
            />
            {errorMessage && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200 flex items-center justify-between">
                    <span>{errorMessage}</span>
                    <button
                        onClick={() => setErrorMessage(null)}
                        className="px-2 py-1 rounded-md bg-white/10 hover:bg-white/20 text-xs"
                    >
                        إغلاق
                    </button>
                </div>
            )}
            {infoMessage && (
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200 flex items-center justify-between">
                    <span>{infoMessage}</span>
                    <button
                        onClick={() => setInfoMessage(null)}
                        className="px-2 py-1 rounded-md bg-white/10 hover:bg-white/20 text-xs"
                    >
                        إغلاق
                    </button>
                </div>
            )}
            <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                            <Newspaper className="w-7 h-7 text-emerald-400" />
                            الأخبار
                        </h1>
                        <p className="text-sm text-gray-500 mt-1">
                            {data?.data?.total || 0} خبر في غرفة الأخبار
                        </p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            onClick={refresh}
                            disabled={refreshPipeline.isPending}
                            className="px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-gray-300 hover:text-white hover:border-white/20 transition-colors flex items-center gap-2"
                        >
                            <RefreshCw className="w-4 h-4" />
                            {refreshPipeline.isPending ? 'جاري التحديث...' : 'تحديث'}
                        </button>
                    </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-gray-900/45 p-4 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <h2 className="text-sm font-semibold text-white">ماذا أنجز النظام لك اليوم؟</h2>
                        <span className="text-[11px] text-gray-400">
                            الوكلاء يعملون في الخلفية، وأنت تتعامل فقط مع النتائج الجاهزة للتحرير.
                        </span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2">
                        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3">
                            <p className="text-[11px] text-emerald-200/80">مسودات جاهزة للتحرير</p>
                            <p className="text-xl font-semibold text-white mt-1">
                                {dailySnapshotLoading ? '...' : (dailySnapshot?.draftsReadyForEditing || 0)}
                            </p>
                        </div>
                        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3">
                            <p className="text-[11px] text-amber-200/80">طلبات تحتاج تحقق</p>
                            <p className="text-xl font-semibold text-white mt-1">
                                {dailySnapshotLoading ? '...' : (dailySnapshot?.needsVerification || 0)}
                            </p>
                        </div>
                        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3">
                            <p className="text-[11px] text-cyan-200/80">جاهز للنشر اليدوي</p>
                            <p className="text-xl font-semibold text-white mt-1">
                                {dailySnapshotLoading ? '...' : (dailySnapshot?.readyForManualPublish || 0)}
                            </p>
                        </div>
                        <div className="rounded-xl border border-violet-500/30 bg-violet-500/10 p-3">
                            <p className="text-[11px] text-violet-200/80">تنبيهات اليوم</p>
                            <p className="text-xl font-semibold text-white mt-1">
                                {dailySnapshotLoading ? '...' : (dailySnapshot?.totalNotifications || 0)}
                            </p>
                            <p className="text-[10px] text-violet-200/80 mt-1">
                                عاجل: {dailySnapshotLoading ? '...' : (dailySnapshot?.urgentAlerts || 0)}
                            </p>
                        </div>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-gray-300">
                        المسار الأسرع للصحفي: افتح الخبر ⇦ حسّن النص ⇦ تحقق ⇦ جهّز النسخة النهائية.
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-3 p-4 rounded-2xl bg-gray-800/30 border border-white/5">
                    <div className="relative flex-1 min-w-[200px]">
                        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                        <input
                            type="text"
                            value={search}
                            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                            placeholder="ابحث في الأخبار..."
                            className="w-full h-9 pr-10 pl-4 rounded-xl bg-white/5 border border-white/5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-emerald-500/40 transition-colors"
                            dir="rtl"
                        />
                    </div>

                    <select
                        value={status}
                        onChange={(e) => { setStatus(e.target.value); setPage(1); }}
                        className="h-9 px-3 rounded-xl bg-white/5 border border-white/5 text-sm text-gray-300 focus:outline-none focus:border-emerald-500/40 appearance-none cursor-pointer"
                    >
                        <option value="">كل الحالات</option>
                        {statuses.filter(Boolean).map(s => (
                            <option key={s} value={s}>{s}</option>
                        ))}
                    </select>

                    <select
                        value={category}
                        onChange={(e) => { setCategory(e.target.value); setPage(1); }}
                        className="h-9 px-3 rounded-xl bg-white/5 border border-white/5 text-sm text-gray-300 focus:outline-none focus:border-emerald-500/40 appearance-none cursor-pointer"
                    >
                        <option value="">كل التصنيفات</option>
                        {categories.filter(Boolean).map(c => (
                            <option key={c} value={c}>{getCategoryLabel(c)}</option>
                        ))}
                    </select>

                    <div className="inline-flex items-center rounded-xl border border-white/10 bg-white/5 p-1">
                        <button
                            type="button"
                            onClick={() => setViewMode('queue')}
                            className={cn(
                                'inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-colors',
                                viewMode === 'queue'
                                    ? 'bg-emerald-500/20 text-emerald-200'
                                    : 'text-gray-300 hover:text-white',
                            )}
                        >
                            <Rows3 className="w-3.5 h-3.5" />
                            طابور العمل
                        </button>
                        <button
                            type="button"
                            onClick={() => setViewMode('table')}
                            className={cn(
                                'inline-flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs transition-colors',
                                viewMode === 'table'
                                    ? 'bg-cyan-500/20 text-cyan-200'
                                    : 'text-gray-300 hover:text-white',
                            )}
                        >
                            <TableProperties className="w-3.5 h-3.5" />
                            عرض تفصيلي
                        </button>
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <button
                        onClick={() => { setIsBreaking(null); setStatus(''); setCategory(''); setPage(1); }}
                        className={cn(
                            'px-3 py-1.5 rounded-full text-xs border transition-colors',
                            isBreaking === null && status === '' && category === ''
                                ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-200'
                                : 'border-white/10 bg-white/5 text-gray-300 hover:text-white hover:border-white/20'
                        )}
                    >
                        الكل
                    </button>

                    <button
                        onClick={() => { setIsBreaking(true); setPage(1); }}
                        className={cn(
                            'px-3 py-1.5 rounded-full text-xs border transition-colors',
                            isBreaking === true
                                ? 'border-red-500/40 bg-red-500/20 text-red-200'
                                : 'border-white/10 bg-white/5 text-gray-300 hover:text-white hover:border-white/20'
                        )}
                    >
                        عاجل فقط
                    </button>

                    <button
                        onClick={() => { setStatus('candidate'); setPage(1); }}
                        className={cn(
                            'px-3 py-1.5 rounded-full text-xs border transition-colors',
                            status === 'candidate'
                                ? 'border-amber-500/40 bg-amber-500/20 text-amber-200'
                                : 'border-white/10 bg-white/5 text-gray-300 hover:text-white hover:border-white/20'
                        )}
                    >
                        مرشحة للتحرير
                    </button>

                    {categories.filter(Boolean).map((c) => (
                        <button
                            key={c}
                            onClick={() => { setCategory(c); setPage(1); }}
                            className={cn(
                                'px-3 py-1.5 rounded-full text-xs border transition-colors',
                                category === c
                                    ? 'border-emerald-500/40 bg-emerald-500/20 text-emerald-200'
                                    : 'border-white/10 bg-white/5 text-gray-300 hover:text-white hover:border-white/20'
                            )}
                        >
                            {getCategoryLabel(c)}
                        </button>
                    ))}
                </div>
            </div>

            {isLoading ? (
                <div className={cn(viewMode === 'queue' ? 'space-y-4' : 'rounded-2xl border border-white/10 bg-gray-900/35 p-4')}>
                    {Array.from({ length: viewMode === 'queue' ? 6 : 1 }).map((_, i) => (
                        <div key={i} className={cn(viewMode === 'queue' ? 'h-44 rounded-2xl bg-gray-800/30 border border-white/5 animate-pulse' : 'h-72 rounded-2xl bg-gray-800/30 animate-pulse')} />
                    ))}
                </div>
            ) : visibleArticles.length > 0 ? (
                viewMode === 'queue' ? (
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                        {visibleArticles.map((article: ArticleBrief, index: number) => {
                            const freshBreaking = isFreshBreaking(article.is_breaking, article.crawled_at);
                            const editHref = `/workspace-drafts?article_id=${article.id}`;
                            const importanceChip = getImportanceChip(article);
                            const importanceLabel = article.is_breaking
                                ? 'عاجلة'
                                : article.importance_score >= 8
                                  ? 'عالية'
                                  : article.importance_score >= 6
                                    ? 'متوسطة'
                                    : 'عادية';

                            return (
                                <div key={article.id} className="h-full">
                                    <WorkflowCard
                                        title={article.title_ar || article.original_title}
                                        subtitle={`المصدر: ${article.source_name || 'غير محدد'}`}
                                        meta={
                                            <div className="flex flex-wrap items-center gap-2 text-slate-400">
                                                <span>الكاتب: غير معيّن</span>
                                                <span className="text-slate-600">•</span>
                                                <span>الأهمية: {importanceLabel}</span>
                                            </div>
                                        }
                                        chips={[
                                            importanceChip,
                                            ...(freshBreaking ? [{ label: 'عاجل', className: 'border-red-500/30 bg-red-500/10 text-red-200' }] : []),
                                        ]}
                                        reason={getReasonForArticle(article)}
                                        nextActionLabel={getNextActionForArticle(article).label}
                                        timestamp={article.created_at || article.crawled_at}
                                        tone={getImportanceTone(article)}
                                        compact
                                        hideReason
                                        hideNextAction
                                        actions={
                                            <div className="grid grid-cols-3 gap-2">
                                                <a
                                                    href={article.original_url || '#'}
                                                    target="_blank"
                                                    rel="noreferrer"
                                                    className={cn(
                                                        'px-3 py-2 rounded-xl border text-[11px] transition-colors flex items-center justify-center gap-2',
                                                        article.original_url
                                                            ? 'bg-white/5 border-white/10 text-gray-200 hover:text-white hover:border-white/20'
                                                            : 'bg-white/5 border-white/5 text-gray-500 cursor-not-allowed',
                                                    )}
                                                >
                                                    <ExternalLink className="w-4 h-4" />
                                                    المصدر
                                                </a>
                                                <Link
                                                    href={`/news/${article.id}`}
                                                    className="px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-[11px] text-gray-300 hover:text-white hover:border-white/20 transition-colors flex items-center justify-center"
                                                >
                                                    التفاصيل
                                                </Link>
                                                <Link
                                                    href={editHref}
                                                    data-tutorial={showNewsOverlay && index === 0 ? 'news-first-edit' : undefined}
                                                    onClick={() =>
                                                        trackNextAction('news', 'تحرير', {
                                                            ...surfaceDetails,
                                                            queue_view: 'queue',
                                                            article_id: article.id,
                                                            article_status: article.status,
                                                            target_href: editHref,
                                                        })
                                                    }
                                                    className="px-3 py-2 rounded-xl bg-cyan-500/10 border border-cyan-500/30 text-[11px] text-cyan-100 hover:bg-cyan-500/20 transition-colors flex items-center justify-center"
                                                >
                                                    التحرير
                                                </Link>
                                            </div>
                                        }
                                    />
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="overflow-hidden rounded-2xl border border-white/10 bg-gray-900/35">
                        <div className="overflow-x-auto">
                            <table className="min-w-full text-sm">
                                <thead className="bg-white/5 text-slate-300">
                                    <tr>
                                        <th className="px-4 py-3 text-right font-medium">العنوان</th>
                                        <th className="px-4 py-3 text-right font-medium">الحالة</th>
                                        <th className="px-4 py-3 text-right font-medium">المصدر</th>
                                        <th className="px-4 py-3 text-right font-medium">الأهمية</th>
                                        <th className="px-4 py-3 text-right font-medium">الوقت</th>
                                        <th className="px-4 py-3 text-right font-medium">إجراء</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {visibleArticles.map((article) => {
                                        const nextAction = getNextActionForArticle(article);
                                        return (
                                            <tr key={article.id} className="border-t border-white/5 text-slate-200">
                                                <td className="px-4 py-3 align-top">
                                                    <div className="font-semibold text-white">{truncate(article.title_ar || article.original_title, 90)}</div>
                                                    <div className="mt-1 text-[11px] text-slate-500">{formatRelativeTime(article.created_at || article.crawled_at)}</div>
                                                </td>
                                                <td className="px-4 py-3 align-top">
                                                    <span className={cn('px-2 py-0.5 rounded-md text-[10px] font-medium border', getStatusColor((article.status || '').toLowerCase()))}>
                                                        {getStatusLabel(article.status)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 align-top text-xs text-slate-300">{article.source_name || '—'}</td>
                                                <td className="px-4 py-3 align-top text-xs text-slate-300">{article.importance_score}</td>
                                                <td className="px-4 py-3 align-top text-[11px] text-slate-500">{formatRelativeTime(article.created_at || article.crawled_at)}</td>
                                                <td className="px-4 py-3 align-top">
                                                    <Link
                                                        href={nextAction.href}
                                                        onClick={() =>
                                                            trackNextAction('news', nextAction.label, {
                                                                ...surfaceDetails,
                                                                queue_view: 'table',
                                                                article_id: article.id,
                                                                article_status: article.status,
                                                                target_href: nextAction.href,
                                                            })
                                                        }
                                                        className="inline-flex items-center gap-2 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100 hover:bg-cyan-500/20"
                                                    >
                                                        {nextAction.label}
                                                        <ArrowLeft className="w-3.5 h-3.5" />
                                                    </Link>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )
            ) : (
                <div className="rounded-2xl border border-dashed border-white/10 bg-gray-900/20 px-6 py-10 text-center text-sm text-slate-400">
                    لا توجد أخبار تطابق هذا الفلتر الآن.
                </div>
            )}
            {totalPages > 1 && (
                <div className="flex items-center justify-center gap-2 px-4 py-3 border-t border-white/5">
                    <button
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page <= 1}
                        className="p-2 rounded-lg bg-white/5 text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
                    >
                        <ChevronRight className="w-4 h-4" />
                    </button>
                    <span className="text-xs text-gray-400 px-3">
                        صفحة {page} من {totalPages}
                    </span>
                    <button
                        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                        disabled={page >= totalPages}
                        className="p-2 rounded-lg bg-white/5 text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
                    >
                        <ChevronLeft className="w-4 h-4" />
                    </button>
                </div>
            )}

            {draftEditor && (
                <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setDraftEditor(null)}>
                    <div
                        className="w-full max-w-3xl rounded-2xl border border-white/10 bg-gray-900 p-4"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-semibold text-white">
                                مسودة {draftEditor.action} (#{draftEditor.articleId})
                            </h3>
                            {draftEditor.workId && (
                                <a
                                    href={`/workspace-drafts?work_id=${draftEditor.workId}`}
                                    className="text-xs text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 px-2 py-1 rounded-lg hover:bg-emerald-500/20"
                                >
                                    {draftEditor.workId}
                                </a>
                            )}
                        </div>
                        <div className="space-y-3">
                            <input
                                value={draftEditor.title}
                                onChange={(e) => setDraftEditor({ ...draftEditor, title: e.target.value })}
                                placeholder="عنوان المسودة"
                                className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="rtl"
                            />
                            <textarea
                                value={draftEditor.body}
                                onChange={(e) => setDraftEditor({ ...draftEditor, body: e.target.value })}
                                className="w-full min-h-[300px] px-3 py-2 rounded-xl bg-black/30 border border-white/10 text-sm text-gray-100"
                                dir="rtl"
                            />
                            <div className="flex items-center justify-end gap-2">
                                <button
                                    onClick={() => setDraftEditor(null)}
                                    className="px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-300 hover:text-white"
                                >
                                    إغلاق
                                </button>
                                <button
                                    onClick={() => saveDraftMutation.mutate({
                                        articleId: draftEditor.articleId,
                                        draftId: draftEditor.draftId,
                                        title: draftEditor.title,
                                        body: draftEditor.body,
                                        source_action: draftEditor.action,
                                        version: draftEditor.version,
                                    })}
                                    disabled={saveDraftMutation.isPending}
                                    className="px-3 py-2 rounded-lg bg-violet-500/20 border border-violet-500/30 text-xs text-violet-200"
                                >
                                    {draftEditor.draftId ? 'تحديث المسودة' : 'حفظ كمسودة'}
                                </button>
                                <button
                                    onClick={() => {
                                        if (!draftEditor.draftId) {
                                            setErrorMessage('احفظ المسودة أولاً قبل التطبيق');
                                            return;
                                        }
                                        applyDraftMutation.mutate({
                                            articleId: draftEditor.articleId,
                                            draftId: draftEditor.draftId,
                                        });
                                    }}
                                    disabled={applyDraftMutation.isPending}
                                    className="px-3 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-xs text-emerald-200"
                                >
                                    تطبيق على الخبر
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <WorkflowHelpPanel
                title="كيف نستخدم طابور الأخبار؟"
                items={[
                    {
                        title: 'لماذا يظهر هنا؟',
                        description: 'كل خبر يوضح سبب ظهوره في الطابور: عاجل، مرشح جديد، جاهز للاعتماد، أو مرتبط بحدث موحّد.',
                    },
                    {
                        title: 'الإجراء التالي',
                        description: 'ابدأ دائمًا بالزر الرئيسي المقترح، ثم استخدم الإجراءات الإضافية فقط عند الحاجة.',
                    },
                    {
                        title: 'إجراءات إضافية',
                        description: 'الترجمة، التلخيص، التحقق، والقرارات التحريرية بقيت موجودة لكنها لا تزاحم السطح الأول.',
                    },
                ]}
            />
        </div>
    );
}

function NewsPageShell() {
    const searchParams = useSearchParams();
    return <NewsPageContent key={searchParams.toString()} />;
}

export default function NewsPage() {
    return (
        <Suspense
            fallback={
                <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 text-center text-gray-400">
                    Loading...
                </div>
            }
        >
            <NewsPageShell />
        </Suspense>
    );
}

