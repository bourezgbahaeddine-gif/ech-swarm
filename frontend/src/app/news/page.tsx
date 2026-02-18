'use client';

import { Suspense, useState, useEffect, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter, useSearchParams } from 'next/navigation';
import { isAxiosError } from 'axios';
import { newsApi, dashboardApi, editorialApi, type ArticleBrief, type DashboardNotification } from '@/lib/api';
import { cn, formatRelativeTime, getStatusColor, getCategoryLabel, isFreshBreaking, truncate } from '@/lib/utils';
import { useAuth } from '@/lib/auth';
import {
    Newspaper, Search, Zap, ExternalLink,
    Clock, ChevronLeft, ChevronRight, Star,
    RefreshCw,
    CheckCircle, XCircle, RotateCw, Copy,
} from 'lucide-react';

function getApiErrorMessage(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) {
            return detail;
        }
    }
    return fallback;
}

function NewsPageContent() {
    const queryClient = useQueryClient();
    const router = useRouter();
    const searchParams = useSearchParams();
    const { user } = useAuth();
    const [page, setPage] = useState(1);
    const [status, setStatus] = useState<string>('');
    const [category, setCategory] = useState<string>('');
    const [search, setSearch] = useState(() => searchParams.get('q') || '');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [isBreaking, setIsBreaking] = useState<boolean | null>(null);
    const [selectedArticle, setSelectedArticle] = useState<number | null>(null);
    const [rejectReason, setRejectReason] = useState('');
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
    const editorName = user?.full_name_ar || 'رئيس التحرير';
    const kickLiveRefresh = (seconds = 30) => setLiveRefreshUntil(Date.now() + seconds * 1000);

    useEffect(() => {
        const t = setTimeout(() => setDebouncedSearch(search.trim()), 400);
        return () => clearTimeout(t);
    }, [search]);

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

    const decideMutation = useMutation({
        mutationFn: async ({
            articleId,
            decision,
            reason,
        }: {
            articleId: number;
            decision: string;
            reason?: string;
        }) => {
            if (decision === 'approve') {
                const draftRes = await editorialApi.handoff(articleId);
                return { workId: draftRes.data?.work_id || null };
            }
            await editorialApi.decide(articleId, { editor_name: editorName, decision, reason });
            return { workId: null };
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['news'] });
            queryClient.invalidateQueries({ queryKey: ['pending-editorial'] });
            queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
            setSelectedArticle(null);
            setRejectReason('');
        },
        onError: (err: unknown) => setErrorMessage(getApiErrorMessage(err, 'تعذر تنفيذ القرار')),
    });

    const processMutation = useMutation({
        mutationFn: ({ articleId, action }: { articleId: number; action: string }) =>
            editorialApi.process(articleId, { action }),
        onSuccess: (res, vars) => {
            const resultText = typeof res.data?.result === 'string' ? res.data.result : '';
            const draft = res.data?.draft;
            setDraftEditor({
                articleId: vars.articleId,
                action: vars.action,
                draftId: typeof draft?.id === 'number' ? draft.id : undefined,
                workId: typeof draft?.work_id === 'string' ? draft.work_id : undefined,
                version: typeof draft?.version === 'number' ? draft.version : undefined,
                title: typeof draft?.title === 'string' && draft.title.trim() ? draft.title : '',
                body: draft?.body || resultText || 'تم تنفيذ الإجراء بنجاح',
            });
            queryClient.invalidateQueries({ queryKey: ['news'] });
        },
        onError: (err: unknown) => setErrorMessage(getApiErrorMessage(err, 'تعذرت معالجة الخبر')),
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

    const socialVariantsMutation = useMutation({
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
                    setInfoMessage(`تم نسخ نسخ السوشيال للخبر #${articleId}`);
                    setErrorMessage(null);
                    return;
                }
            } catch {
                // Fallback: expose text in info banner.
            }
            setInfoMessage(text);
            setErrorMessage(null);
        },
        onError: (err: unknown) => setErrorMessage(getApiErrorMessage(err, 'تعذر جلب نسخ السوشيال')),
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

    const categoryColor = (cat?: string | null) => {
        switch (cat) {
            case 'politics': return 'border-blue-500/30 text-blue-300 bg-blue-500/10';
            case 'economy': return 'border-emerald-500/30 text-emerald-300 bg-emerald-500/10';
            case 'sports': return 'border-amber-500/30 text-amber-300 bg-amber-500/10';
            case 'technology': return 'border-violet-500/30 text-violet-300 bg-violet-500/10';
            case 'local_algeria': return 'border-sky-500/30 text-sky-300 bg-sky-500/10';
            case 'international': return 'border-rose-500/30 text-rose-300 bg-rose-500/10';
            case 'culture': return 'border-fuchsia-500/30 text-fuchsia-300 bg-fuchsia-500/10';
            case 'society': return 'border-lime-500/30 text-lime-300 bg-lime-500/10';
            case 'health': return 'border-teal-500/30 text-teal-300 bg-teal-500/10';
            default: return 'border-white/10 text-gray-300 bg-white/5';
        }
    };
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
    const canRewrite = ['director', 'editor_chief', 'journalist', 'print_editor'].includes(role);
    const canProcess = canRewrite;
    const isSocialRole = role === 'social_media';

    return (
        <div className="space-y-6">
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

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {isLoading ? (
                    Array.from({ length: 9 }).map((_, i) => (
                        <div key={i} className="h-56 rounded-2xl bg-gray-800/30 border border-white/5 animate-pulse" />
                    ))
                ) : visibleArticles.length > 0 ? (
                    visibleArticles.map((article: ArticleBrief) => {
                        const normalizedStatus = (article.status || '').toLowerCase();
                        const canReview = normalizedStatus === 'candidate' || normalizedStatus === 'classified';
                        const freshBreaking = isFreshBreaking(article.is_breaking, article.crawled_at);
                        const insight = insightsMap.get(article.id);

                        return (
                            <div
                                key={article.id}
                                className={cn(
                                    'rounded-2xl border border-white/5 bg-gradient-to-br from-gray-800/40 to-gray-900/70 p-4 transition-all',
                                    'hover:border-white/10 hover:shadow-lg hover:shadow-black/30',
                                    freshBreaking && 'ring-1 ring-red-500/30'
                                )}
                            >
                                <div className="flex items-start gap-3">
                                    <div className={cn(
                                        'w-12 h-12 rounded-xl flex flex-col items-center justify-center flex-shrink-0',
                                        article.importance_score >= 8 ? 'bg-red-500/20 text-red-400' :
                                            article.importance_score >= 6 ? 'bg-amber-500/20 text-amber-400' :
                                                'bg-gray-500/20 text-gray-400',
                                    )}>
                                        <Star className="w-4 h-4 mb-0.5" />
                                        <span className="text-lg font-bold">{article.importance_score}</span>
                                    </div>

                                    <div className="flex-1">
                                        <div className="flex items-center gap-2 mb-2">
                                            {freshBreaking && (
                                                <span className="px-2 py-0.5 rounded-full bg-red-500 text-[10px] font-bold text-white flex items-center gap-1 animate-pulse">
                                                    <Zap className="w-3 h-3" /> عاجل
                                                </span>
                                            )}
                                            <span className="text-[10px] text-gray-400">{article.source_name || '—'}</span>
                                            <span className="text-[10px] text-gray-500 mr-auto flex items-center gap-1">
                                                <Clock className="w-3 h-3" />
                                                {formatRelativeTime(article.created_at || article.crawled_at)}
                                            </span>
                                        </div>

                                        <h3 className="text-sm font-semibold text-white leading-relaxed line-clamp-2" dir="rtl">
                                            {article.title_ar || article.original_title}
                                        </h3>

                                        {article.summary && (
                                            <p className="text-xs text-gray-400 mt-2 line-clamp-2" dir="rtl">
                                                {truncate(article.summary, 140)}
                                            </p>
                                        )}
                                    </div>
                                </div>

                                <div className="mt-4 flex flex-wrap items-center gap-2">
                                    <span className={cn('px-2 py-0.5 rounded-md text-[10px] font-medium border', getStatusColor((article.status || '').toLowerCase()))}>
                                        {getStatusLabel(article.status)}
                                    </span>
                                    <span className={cn('px-2 py-0.5 rounded-md text-[10px] font-medium border', categoryColor(article.category))}>
                                        {getCategoryLabel(article.category)}
                                    </span>
                                    {(insight?.cluster_size || 0) > 1 && (
                                        <span className="px-2 py-0.5 rounded-md text-[10px] font-medium border border-cyan-500/30 text-cyan-300 bg-cyan-500/10">
                                            حدث موحّد: {insight?.cluster_size}
                                        </span>
                                    )}
                                    {(insight?.relation_count || 0) > 0 && (
                                        <span className="px-2 py-0.5 rounded-md text-[10px] font-medium border border-fuchsia-500/30 text-fuchsia-300 bg-fuchsia-500/10">
                                            علاقات: {insight?.relation_count}
                                        </span>
                                    )}
                                </div>

                                <div className="mt-4 grid grid-cols-2 gap-2">
                                    <a
                                        href={article.original_url || '#'}
                                        target="_blank"
                                        rel="noreferrer"
                                        className={cn(
                                            'px-3 py-2 rounded-xl border text-xs transition-colors flex items-center justify-center gap-2',
                                            article.original_url
                                                ? 'bg-white/5 border-white/10 text-gray-200 hover:text-white hover:border-white/20'
                                                : 'bg-white/5 border-white/5 text-gray-500 cursor-not-allowed'
                                        )}
                                    >
                                        <ExternalLink className="w-4 h-4" />
                                        المصدر
                                    </a>
                                    <a
                                        href={`/news/${article.id}`}
                                        className="px-3 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-xs text-emerald-300 hover:bg-emerald-500/25 transition-colors flex items-center justify-center"
                                    >
                                        التفاصيل
                                    </a>
                                </div>
                                <div className="mt-2">
                                    <a
                                        href={`/workspace-drafts?article_id=${article.id}`}
                                        className="block w-full px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-gray-300 hover:text-white hover:border-white/20 transition-colors text-center"
                                    >
                                        فتح في Workspace
                                    </a>
                                </div>

                                {isSocialRole && ['ready_for_manual_publish', 'published'].includes(normalizedStatus) && (
                                    <div className="mt-2">
                                        <button
                                            onClick={() => socialVariantsMutation.mutate(article.id)}
                                            disabled={socialVariantsMutation.isPending}
                                            className="w-full px-3 py-2 rounded-xl bg-cyan-500/15 border border-cyan-500/30 text-xs text-cyan-200 hover:bg-cyan-500/25 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                                        >
                                            <Copy className="w-3.5 h-3.5" /> نسخ نسخ السوشيال الجاهزة
                                        </button>
                                    </div>
                                )}

                                <div className="mt-3 grid grid-cols-3 gap-2">
                                    <button
                                        onClick={() =>
                                            decideMutation.mutate(
                                                {
                                                    articleId: article.id,
                                                    decision: 'approve',
                                                },
                                                {
                                                    onSuccess: (result) => {
                                                        const target = result?.workId
                                                            ? `/workspace-drafts?article_id=${article.id}&work_id=${result.workId}`
                                                            : `/workspace-drafts?article_id=${article.id}`;
                                                        router.push(target);
                                                    },
                                                },
                                            )
                                        }
                                        disabled={decideMutation.isPending || !canReview || !canApproveReject}
                                        className={cn(
                                            'px-2 py-2 rounded-xl border text-[10px] flex items-center justify-center gap-1 transition-colors',
                                            canReview && canApproveReject
                                                ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/25'
                                                : 'bg-white/5 border-white/10 text-gray-500 cursor-not-allowed'
                                        )}
                                    >
                                        <CheckCircle className="w-3 h-3" /> موافقة
                                    </button>
                                    <button
                                        onClick={() => decideMutation.mutate({ articleId: article.id, decision: 'rewrite' })}
                                        disabled={decideMutation.isPending || !canReview || !canRewrite}
                                        className={cn(
                                            'px-2 py-2 rounded-xl border text-[10px] flex items-center justify-center gap-1 transition-colors',
                                            canReview && canRewrite
                                                ? 'bg-amber-500/15 border-amber-500/30 text-amber-300 hover:bg-amber-500/25'
                                                : 'bg-white/5 border-white/10 text-gray-500 cursor-not-allowed'
                                        )}
                                    >
                                        <RotateCw className="w-3 h-3" /> إعادة
                                    </button>
                                    <button
                                        onClick={() => setSelectedArticle(article.id)}
                                        disabled={!canReview || !canApproveReject}
                                        className={cn(
                                            'px-2 py-2 rounded-xl border text-[10px] flex items-center justify-center gap-1 transition-colors',
                                            canReview && canApproveReject
                                                ? 'bg-red-500/15 border-red-500/30 text-red-300 hover:bg-red-500/25'
                                                : 'bg-white/5 border-white/10 text-gray-500 cursor-not-allowed'
                                        )}
                                    >
                                        <XCircle className="w-3 h-3" /> رفض
                                    </button>
                                </div>

                                {selectedArticle === article.id && canReview && (
                                    <div className="mt-3 flex items-center gap-2">
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
                                            className="px-4 py-2 rounded-xl bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-colors text-xs font-medium"
                                        >
                                            تأكيد الرفض
                                        </button>
                                    </div>
                                )}

                                <div className="mt-2 grid grid-cols-3 gap-2">
                                    <button
                                        onClick={() => processMutation.mutate({ articleId: article.id, action: 'summarize' })}
                                        disabled={processMutation.isPending || !canProcess}
                                        className={cn(
                                            'px-2 py-2 rounded-xl border text-[10px] transition-colors',
                                            canProcess
                                                ? 'bg-sky-500/15 border-sky-500/30 text-sky-300 hover:bg-sky-500/25'
                                                : 'bg-white/5 border-white/10 text-gray-500 cursor-not-allowed'
                                        )}
                                    >
                                        تلخيص
                                    </button>
                                    <button
                                        onClick={() => processMutation.mutate({ articleId: article.id, action: 'translate' })}
                                        disabled={processMutation.isPending || !canProcess}
                                        className={cn(
                                            'px-2 py-2 rounded-xl border text-[10px] transition-colors',
                                            canProcess
                                                ? 'bg-violet-500/15 border-violet-500/30 text-violet-300 hover:bg-violet-500/25'
                                                : 'bg-white/5 border-white/10 text-gray-500 cursor-not-allowed'
                                        )}
                                    >
                                        ترجمة
                                    </button>
                                    <button
                                        onClick={() => processMutation.mutate({ articleId: article.id, action: 'fact_check' })}
                                        disabled={processMutation.isPending || !canProcess}
                                        className={cn(
                                            'px-2 py-2 rounded-xl border text-[10px] transition-colors',
                                            canProcess
                                                ? 'bg-fuchsia-500/15 border-fuchsia-500/30 text-fuchsia-300 hover:bg-fuchsia-500/25'
                                                : 'bg-white/5 border-white/10 text-gray-500 cursor-not-allowed'
                                        )}
                                    >
                                        تحقق
                                    </button>
                                </div>
                            </div>
                        );
                    })
                ) : (
                    <div className="col-span-full text-center py-16 rounded-2xl bg-gray-800/20 border border-white/5">
                        لا توجد أخبار حالياً
                    </div>
                )}
            </div>

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
        </div>
    );
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
            <NewsPageContent />
        </Suspense>
    );
}

