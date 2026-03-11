'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { AlertCircle, BookOpenText, RefreshCw, FolderPlus, ChevronDown, ChevronUp } from 'lucide-react';

import { storiesApi, type StoryClusterRecord, type StoryDossierResponse } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';

export default function StoriesPage() {
    const [selectedStoryId, setSelectedStoryId] = useState<number | null>(null);
    const [clusterHours, setClusterHours] = useState<number>(24);
    const [clusterMinSize, setClusterMinSize] = useState<number>(2);
    const [view, setView] = useState<'stories' | 'clusters'>('stories');
    const [clusterQuery, setClusterQuery] = useState<string>('');
    const [expandedClusters, setExpandedClusters] = useState<Set<number>>(new Set());
    const [actionMsg, setActionMsg] = useState<string | null>(null);
    const [actionErr, setActionErr] = useState<string | null>(null);

    const { data, isLoading, refetch, isRefetching, error } = useQuery({
        queryKey: ['stories-page-list'],
        queryFn: () => storiesApi.list({ limit: 120 }),
    });
    const {
        data: clustersData,
        isLoading: clustersLoading,
        error: clustersError,
        refetch: refetchClusters,
        isRefetching: isClustersRefetching,
    } = useQuery({
        queryKey: ['stories-page-clusters', clusterHours, clusterMinSize],
        queryFn: () => storiesApi.clusters({ hours: clusterHours, ?????_size: clusterMinSize, limit: 20 }),
    });

    const stories = useMemo(() => data?.data || [], [data?.data]);
    const clusterReport = clustersData?.data;
    const clusterItems = clusterReport?.items || [];
    const filteredClusters = useMemo(() => {
        const query = clusterQuery.trim().toLowerCase();
        if (!query) return clusterItems;
        return clusterItems.filter((cluster) => {
            const haystack = [
                cluster.label,
                cluster.cluster_key,
                cluster.category,
                cluster.geography,
                ...cluster.top_entities.map((entity) => entity.entity),
                ...cluster.top_topics.map((topic) => topic.topic),
                ...cluster.members.map((member) => member.title),
            ]
                .filter(Boolean)
                .join(' ')
                .toLowerCase();
            return haystack.includes(query);
        });
    }, [clusterItems, clusterQuery]);

    const createStoryFromCluster = useMutation({
        mutationFn: async (payload: { clusterId: number; articleId: number }) => {
            setActionErr(null);
            setActionMsg(null);
            return storiesApi.createFromArticle(payload.articleId, { reuse: true });
        },
        onSuccess: (res) => {
            const story = res.data?.story;
            if (story?.id) {
                setSelectedStoryId(story.id);
                setActionMsg(`تم الربط مع القصة ${story.story_key}.`);
            } else {
                setActionMsg('تم إنشاء القصة وربطها.');
            }
        },
        onError: () => setActionErr('تعذر إنشاء قصة من هذه المجموعة.'),
    });

    return (
        <div className="space-y-4" dir="rtl">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white inline-flex items-center gap-2">
                        <BookOpenText className="w-6 h-6 text-cyan-300" />
                        القصص التحريرية
                    </h1>
                    <p className="text-xs text-slate-400 mt-1">متابعة القصص ومجموعات الأحداث في مكان واحد.</p>
                </div>
                <button
                    type="button"
                    onClick={() => {
                        refetch();
                        refetchClusters();
                    }}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 hover:text-white"
                >
                    <RefreshCw className={cn('w-4 h-4', (isRefetching || isClustersRefetching) && 'animate-spin')} />
                    تحديث
                </button>
            </div>

            {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                    فشل جلب القصص التحريرية.
                </div>
            )}
            {clustersError && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                    فشل جلب مجموعات القصص.
                </div>
            )}


            {actionMsg && (
                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-100">
                    {actionMsg}
                </div>
            )}
            {actionErr && (
                <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-xs text-rose-100">
                    {actionErr}
                </div>
            )}

            <div className="flex items-center gap-2">
                <button
                    type="button"
                    onClick={() => setView('stories')}
                    className={cn(
                        'rounded-lg border px-3 py-1.5 text-xs transition-colors',
                        view === 'stories'
                            ? 'border-cyan-400/60 bg-cyan-500/20 text-cyan-100'
                            : 'border-white/10 bg-white/5 text-slate-300',
                    )}
                >
                    القصص المنشأة
                </button>
                <button
                    type="button"
                    onClick={() => setView('clusters')}
                    className={cn(
                        'rounded-lg border px-3 py-1.5 text-xs transition-colors',
                        view === 'clusters'
                            ? 'border-emerald-400/60 bg-emerald-500/20 text-emerald-100'
                            : 'border-white/10 bg-white/5 text-slate-300',
                    )}
                >
                    مجموعات مقترحة
                </button>
            </div>
            {view === 'clusters' && (
                <StoryClustersSection
                    loading={clustersLoading}
                    report={clusterReport}
                    items={filteredClusters}
                    hours={clusterHours}
                    ?????Size={clusterMinSize}
                    query={clusterQuery}
                    onQueryChange={setClusterQuery}
                    onChangeHours={setClusterHours}
                    onChangeMinSize={setClusterMinSize}
                    expandedClusters={expandedClusters}
                    onToggleCluster={(clusterId) => {
                        setExpandedClusters((prev) => {
                            const next = new Set(prev);
                            if (next.has(clusterId)) {
                                next.delete(clusterId);
                            } else {
                                next.add(clusterId);
                            }
                            return next;
                        });
                    }}
                    onCreateStory={(clusterId, articleId) => createStoryFromCluster.mutate({ clusterId, articleId })}
                    isCreatingStory={createStoryFromCluster.isPending}
                />
            )}
            {view === 'stories' && (
                isLoading ? (
                    <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">جاري التحميل...</div>
                ) : (
                    <div className="grid grid-cols-1 gap-3">
                        {stories.length === 0 && (
                            <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">لا توجد قصص بعد. أنشئ قصة من صفحة الخبر.</div>
                        )}
                        {stories.map((story) => (
                            <button
                                key={story.id}
                                type="button"
                                onClick={() => setSelectedStoryId(story.id)}
                                className="text-right rounded-2xl border border-white/10 bg-slate-900/40 p-4 hover:border-cyan-400/40 hover:bg-slate-900/65 transition-colors"
                            >
                                <div className="flex items-center justify-between gap-3">
                                    <div>
                                        <p className="text-sm text-cyan-300 font-medium">{story.story_key}</p>
                                        <h2 className="text-lg font-semibold text-white mt-1">{story.title}</h2>
                                        <p className="text-xs text-slate-400 mt-2 line-clamp-2">{story.summary || 'بدون ملخص'}</p>
                                    </div>
                                    <div className="text-left shrink-0">
                                        <p className="text-xs text-slate-300">{story.status}</p>
                                        <p className="text-[11px] text-slate-500 mt-1">{formatRelativeTime(story.updated_at || story.created_at || '')}</p>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                )
            )}

            {selectedStoryId &&
 (
                <StoryDossierDrawer storyId={selectedStoryId} onClose={() => setSelectedStoryId(null)} />
            )}
        </div>
    );
}

function StoryClustersSection({
    loading,
    report,
    items,
    hours,
    ?????Size,
    query,
    onQueryChange,
    onChangeHours,
    onChangeMinSize,
    expandedClusters,
    onToggleCluster,
    onCreateStory,
    isCreatingStory,
}: {
    loading: boolean;
    report?: {
        metrics?: {
            clusters_created?: number;
            average_cluster_size?: number;
            time_to_cluster_minutes?: number | null;
        };
    };
    items: StoryClusterRecord[];
    hours: number;
    ?????Size: number;
    query: string;
    onQueryChange: (value: string) => void;
    onChangeHours: (value: number) => void;
    onChangeMinSize: (value: number) => void;
    expandedClusters: Set<number>;
    onToggleCluster: (clusterId: number) => void;
    onCreateStory: (clusterId: number, articleId: number) => void;
    isCreatingStory: boolean;
}) {
    return (
        <section className="rounded-2xl border border-white/10 bg-slate-900/40 p-4 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div>
                    <h2 className="text-sm font-semibold text-white">مجموعات القصص</h2>
                    <p className="text-[11px] text-slate-400">اختر مجموعة، راجع العناصر، ثم أنشئ قصة.</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <input
                        value={query}
                        onChange={(e) => onQueryChange(e.target.value)}
                        placeholder="بحث سريع داخل المجموعات..."
                        className="rounded-lg border border-white/15 bg-black/20 px-2 py-1 text-xs text-white placeholder:text-slate-500"
                    />
                    <label className="text-xs text-slate-300 inline-flex items-center gap-1">
                        النافذة
                        <select
                            value={hours}
                            onChange={(e) => onChangeHours(Number(e.target.value) || 24)}
                            className="rounded-lg border border-white/15 bg-black/20 px-2 py-1 text-xs text-white"
                        >
                            <option value={6}>6h</option>
                            <option value={12}>12h</option>
                            <option value={24}>24h</option>
                            <option value={48}>48h</option>
                        </select>
                    </label>
                    <label className="text-xs text-slate-300 inline-flex items-center gap-1">
                        حد الحجم
                        <select
                            value={minSize}
                            onChange={(e) => onChangeMinSize(Number(e.target.value) || 2)}
                            className="rounded-lg border border-white/15 bg-black/20 px-2 py-1 text-xs text-white"
                        >
                            <option value={2}>2</option>
                            <option value={3}>3</option>
                            <option value={5}>5</option>
                        </select>
                    </label>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">

                <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
                    ????????? ???????: <span className="text-white font-semibold">{report?.metrics?.clusters_created ?? 0}</span>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
                    ????? ??? ????????: <span className="text-white font-semibold">{report?.metrics?.average_cluster_size ?? 0}</span>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
                    ????? ??? ???????: <span className="text-white font-semibold">{report?.metrics?.time_to_cluster_minutes ?? '??? ????'} ?????</span>
                </div>
            </div>

            {loading ? (
                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-4 text-xs text-slate-400">جاري تحميل المجموعات...</div>
            ) : (
                <div className="space-y-2">
                    {items.map((cluster) => (
                        <ClusterCard
                        key={cluster.cluster_id}
                        cluster={cluster}
                        expanded={expandedClusters.has(cluster.cluster_id)}
                        onToggle={() => onToggleCluster(cluster.cluster_id)}
                        onCreateStory={(articleId) => onCreateStory(cluster.cluster_id, articleId)}
                        isCreatingStory={isCreatingStory}
                    />
                    ))}
                    {items.length === 0 && (
                        <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-4 text-xs text-slate-400">
                            لا توجد مجموعات نشطة وفق الفلاتر الحالية.
                        </div>
                    )}
                </div>
            )}
        </section>
    );
}



function ClusterCard({
    cluster,
    expanded,
    onToggle,
    onCreateStory,
    isCreatingStory,
}: {
    cluster: StoryClusterRecord;
    expanded: boolean;
    onToggle: () => void;
    onCreateStory: (articleId: number) => void;
    isCreatingStory: boolean;
}) {
    const topMember = cluster.members[0];
    const canCreate = Boolean(topMember?.article_id);
    return (
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 space-y-3">
            <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                    <p className="text-[11px] text-cyan-300">{cluster.cluster_key}</p>
                    <p className="text-sm text-white font-medium line-clamp-1">{cluster.label || `مجموعة #${cluster.cluster_id}`}</p>
                    <p className="text-[11px] text-slate-400">
                        {cluster.category || 'غير مصنف'} • {cluster.geography || 'غير محدد'} • الأعضاء: {cluster.cluster_size}
                    </p>
                </div>
                <div className="flex flex-col items-end gap-2">
                    <p className="text-[11px] text-slate-500">{cluster.latest_article_at ? formatRelativeTime(cluster.latest_article_at) : 'لا توجد نشاطات'}</p>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            disabled={!canCreate || isCreatingStory}
                            onClick={() => canCreate && onCreateStory(topMember.article_id)}
                            className="inline-flex items-center gap-1 rounded-lg border border-emerald-400/40 bg-emerald-500/15 px-2 py-1 text-[11px] text-emerald-100 disabled:opacity-50"
                        >
                            <FolderPlus className="w-3 h-3" />
                            إنشاء قصة
                        </button>
                        <button
                            type="button"
                            onClick={onToggle}
                            className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-[11px] text-slate-300"
                        >
                            {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                            {expanded ? 'إخفاء' : 'تفاصيل'}
                        </button>
                    </div>
                </div>
            </div>

            <div className="space-y-1">
                {cluster.members.slice(0, 2).map((member) => (
                    <p key={`${cluster.cluster_id}-${member.article_id}`} className="text-[11px] text-slate-200 line-clamp-1">
                        - {member.title} <span className="text-slate-500">({member.source_name || 'unknown'})</span>
                    </p>
                ))}
            </div>

            {expanded && (
                <div className="space-y-3 pt-1">
                    <div className="flex flex-wrap gap-1">
                        {cluster.top_entities.slice(0, 6).map((entity) => (
                            <span key={`${cluster.cluster_id}-entity-${entity.entity}`} className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[10px] text-cyan-100">
                                {entity.entity} ({entity.count})
                            </span>
                        ))}
                        {cluster.top_topics.slice(0, 6).map((topic) => (
                            <span key={`${cluster.cluster_id}-topic-${topic.topic}`} className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-100">
                                #{topic.topic}
                            </span>
                        ))}
                    </div>
                    <div className="space-y-1">
                        {cluster.members.slice(0, 6).map((member) => (
                            <div key={`${cluster.cluster_id}-member-${member.article_id}`} className="flex items-center justify-between text-[11px] text-slate-200">
                                <span className="line-clamp-1">- {member.title}</span>
                                <a
                                    href={`/news/${member.article_id}`}
                                    className="text-[11px] text-cyan-300"
                                    target="_blank"
                                    rel="noreferrer"
                                >
                                    فتح
                                </a>
                            </div>
                        ))}
                        {cluster.members.length === 0 && <p className="text-[11px] text-slate-500">لا توجد عناصر.</p>}
                    </div>
                </div>
            )}
        </div>
    );
}

function StoryDossierDrawer({ storyId, onClose }: { storyId: number; onClose: () => void }) {
    const { data, isLoading, error } = useQuery({
        queryKey: ['stories-dossier', storyId],
        queryFn: () => storiesApi.dossier(storyId, { timeline_limit: 20 }),
    });

    const dossier: StoryDossierResponse | undefined = data?.data;

    return (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex justify-end" dir="rtl">
            <div className="w-full max-w-2xl h-full overflow-y-auto border-l border-white/10 bg-slate-950 p-5">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-white">ملف القصة</h3>
                    <button onClick={onClose} className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-slate-300">إغلاق</button>
                </div>

                {isLoading && <p className="text-slate-400 text-sm">جاري تحميل ملف القصة...</p>}
                {error && (
                    <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200 inline-flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" />
                        تعذّر تحميل ملف القصة.
                    </div>
                )}

                {dossier && (
                    <div className="space-y-5">
                        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                            <p className="text-xs text-cyan-300">{dossier.story.story_key}</p>
                            <h4 className="text-xl font-semibold text-white mt-1">{dossier.story.title}</h4>
                            <p className="text-xs text-slate-300 mt-2">
                                الحالة: {dossier.story.status} • الأولوية: {dossier.story.priority}
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-xs">
                            <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">إجمالي العناصر: {dossier.stats.items_total}</div>
                            <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">الأخبار: {dossier.stats.articles_count}</div>
                            <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">المسودات: {dossier.stats.drafts_count}</div>
                            <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
                                آخر نشاط: {dossier.stats.last_activity_at ? formatRelativeTime(dossier.stats.last_activity_at) : 'غير متاح'}
                            </div>
                        </div>

                        <section className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">أحدث العناوين</h5>
                            <div className="space-y-2">
                                {dossier.highlights.latest_titles.map((title, index) => (
                                    <div key={`${title}-${index}`} className="rounded-lg border border-white/10 bg-white/5 p-2 text-sm text-slate-100">{title}</div>
                                ))}
                                {dossier.highlights.latest_titles.length === 0 && (
                                    <p className="text-xs text-slate-400">لا توجد عناوين بعد.</p>
                                )}
                            </div>
                        </section>

                        <section className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">الخط الزمني</h5>
                            <div className="space-y-2">
                                {dossier.timeline.map((item) => (
                                    <div key={`${item.type}-${item.id}`} className="rounded-xl border border-white/10 bg-slate-900/60 p-3">
                                        <p className="text-[11px] text-cyan-300">{item.type === 'article' ? 'خبر' : 'مسودة'} #{item.id}</p>
                                        <p className="text-sm text-white mt-1">{item.title}</p>
                                        <p className="text-[11px] text-slate-400 mt-1">
                                            {item.source_name ? `${item.source_name} • ` : ''}
                                            {item.status || 'بدون حالة'} • {item.created_at ? formatRelativeTime(item.created_at) : 'بدون تاريخ'}
                                        </p>
                                    </div>
                                ))}
                                {dossier.timeline.length === 0 && (
                                    <p className="text-xs text-slate-400">لا يوجد خط زمني متاح.</p>
                                )}
                            </div>
                        </section>
                    </div>
                )}
            </div>
        </div>
    );
}
