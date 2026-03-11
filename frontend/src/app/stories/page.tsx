'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
    AlertCircle,
    BookOpenText,
    ChevronDown,
    ChevronUp,
    FolderPlus,
    Loader2,
    RefreshCw,
} from 'lucide-react';

import {
    storiesApi,
    type StoryClusterRecord,
    type StoryControlCenterResponse,
    type StoryGapItem,
} from '@/lib/api';
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

    const {
        data: storiesData,
        isLoading: storiesLoading,
        refetch: refetchStories,
        isRefetching: storiesRefetching,
        error: storiesError,
    } = useQuery({
        queryKey: ['stories-page-list'],
        queryFn: () => storiesApi.list({ limit: 120 }),
    });

    const {
        data: clustersData,
        isLoading: clustersLoading,
        error: clustersError,
        refetch: refetchClusters,
        isRefetching: clustersRefetching,
    } = useQuery({
        queryKey: ['stories-page-clusters', clusterHours, clusterMinSize],
        queryFn: () => storiesApi.clusters({ hours: clusterHours, min_size: clusterMinSize, limit: 20 }),
    });

    const stories = useMemo(() => storiesData?.data || [], [storiesData?.data]);
    const clusterReport = clustersData?.data;
    const clusterItems = clusterReport?.items || [];

    const filteredClusters = useMemo(() => {
        const query = clusterQuery.trim().toLowerCase();
        if (!query) {
            return clusterItems;
        }
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
        mutationFn: async (payload: { articleId: number }) => {
            setActionErr(null);
            setActionMsg(null);
            return storiesApi.createFromArticle(payload.articleId, { reuse: true });
        },
        onSuccess: (res) => {
            const story = res.data?.story;
            if (story?.id) {
                setSelectedStoryId(story.id);
                setActionMsg(`تم ربط العنصر بالقصة ${story.story_key}.`);
                refetchStories();
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
                    <p className="text-xs text-slate-400 mt-1">لوحة قيادة القصة: تغطية، فجوات، خط زمني، وإجراءات سريعة.</p>
                </div>
                <button
                    type="button"
                    onClick={() => {
                        refetchStories();
                        refetchClusters();
                    }}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 hover:text-white"
                >
                    <RefreshCw className={cn('w-4 h-4', (storiesRefetching || clustersRefetching) && 'animate-spin')} />
                    تحديث
                </button>
            </div>

            {(storiesError || clustersError) && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200 inline-flex items-center gap-2">
                    <AlertCircle className="w-4 h-4" />
                    تعذر تحميل بيانات القصص. حاول التحديث مرة أخرى.
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
                    مركز القصص
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
                    minSize={clusterMinSize}
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
                    onCreateStory={(articleId) => createStoryFromCluster.mutate({ articleId })}
                    isCreatingStory={createStoryFromCluster.isPending}
                />
            )}

            {view === 'stories' && (
                storiesLoading ? (
                    <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">جاري تحميل مركز القصص...</div>
                ) : (
                    <div className="grid grid-cols-1 gap-3">
                        {stories.length === 0 && (
                            <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">لا توجد قصص بعد. ابدأ بقصة من خبر واحد أو من مجموعة مقترحة.</div>
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
                                        <p className="text-[11px] text-slate-500 mt-1">
                                            {formatRelativeTime(story.updated_at || story.created_at || '')}
                                        </p>
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>
                )
            )}

            {selectedStoryId && (
                <StoryControlCenterDrawer storyId={selectedStoryId} onClose={() => setSelectedStoryId(null)} />
            )}
        </div>
    );
}

function StoryClustersSection({
    loading,
    report,
    items,
    hours,
    minSize,
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
    minSize: number;
    query: string;
    onQueryChange: (value: string) => void;
    onChangeHours: (value: number) => void;
    onChangeMinSize: (value: number) => void;
    expandedClusters: Set<number>;
    onToggleCluster: (clusterId: number) => void;
    onCreateStory: (articleId: number) => void;
    isCreatingStory: boolean;
}) {
    return (
        <section className="rounded-2xl border border-white/10 bg-slate-900/40 p-4 space-y-4">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div>
                    <h2 className="text-sm font-semibold text-white">مجموعات القصص المقترحة</h2>
                    <p className="text-[11px] text-slate-400">راجع المجموعة ثم أنشئ قصة بنقرة واحدة.</p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <input
                        value={query}
                        onChange={(e) => onQueryChange(e.target.value)}
                        placeholder="بحث داخل المجموعات..."
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
                        الحد الأدنى
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
                    مجموعات جديدة: <span className="text-white font-semibold">{report?.metrics?.clusters_created ?? 0}</span>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
                    متوسط حجم المجموعة: <span className="text-white font-semibold">{report?.metrics?.average_cluster_size ?? 0}</span>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
                    متوسط وقت التجميع: <span className="text-white font-semibold">{report?.metrics?.time_to_cluster_minutes ?? 'غير متاح'}</span> دقيقة
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
                            onCreateStory={(articleId) => onCreateStory(articleId)}
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
                    <p className="text-[11px] text-slate-500">
                        {cluster.latest_article_at ? formatRelativeTime(cluster.latest_article_at) : 'بدون نشاط'}
                    </p>
                    <div className="flex items-center gap-2">
                        <button
                            type="button"
                            disabled={!canCreate || isCreatingStory}
                            onClick={() => canCreate && onCreateStory(topMember.article_id)}
                            className="inline-flex items-center gap-1 rounded-lg border border-emerald-400/40 bg-emerald-500/15 px-2 py-1 text-[11px] text-emerald-100 disabled:opacity-50"
                        >
                            {isCreatingStory ? <Loader2 className="w-3 h-3 animate-spin" /> : <FolderPlus className="w-3 h-3" />}
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
                                    فتح الخبر
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

function StoryControlCenterDrawer({ storyId, onClose }: { storyId: number; onClose: () => void }) {
    const { data, isLoading, error } = useQuery({
        queryKey: ['stories-control-center', storyId],
        queryFn: () => storiesApi.controlCenter(storyId, { timeline_limit: 40 }),
    });

    const center: StoryControlCenterResponse | undefined = data?.data;
    const timeline = useMemo(() => {
        if (!center?.timeline) {
            return [];
        }
        return [...center.timeline].sort((a, b) => {
            const aValue = a.created_at ? new Date(a.created_at).getTime() : 0;
            const bValue = b.created_at ? new Date(b.created_at).getTime() : 0;
            return bValue - aValue;
        });
    }, [center?.timeline]);

    return (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex justify-end" dir="rtl">
            <div className="w-full max-w-3xl h-full overflow-y-auto border-l border-white/10 bg-slate-950 p-5">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-white">Story Control Center</h3>
                    <button onClick={onClose} className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-slate-300">إغلاق</button>
                </div>

                {isLoading && <p className="text-slate-400 text-sm">جاري تحميل لوحة القصة...</p>}
                {error && (
                    <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200 inline-flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" />
                        تعذر تحميل لوحة القصة.
                    </div>
                )}

                {center && (
                    <div className="space-y-5">
                        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                            <p className="text-xs text-cyan-300">{center.story.story_key}</p>
                            <h4 className="text-xl font-semibold text-white mt-1">{center.story.title}</h4>
                            <p className="text-xs text-slate-300 mt-2">
                                الحالة: {center.story.status} • الأولوية: {center.story.priority}
                            </p>
                        </div>

                        <section className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">Overview</h5>
                            <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                                <MetricCard label="العناصر" value={center.overview.items_total} />
                                <MetricCard label="الأخبار" value={center.overview.articles_count} />
                                <MetricCard label="المسودات" value={center.overview.drafts_count} />
                                <MetricCard label="التغطية" value={`${center.overview.coverage_score}%`} />
                                <MetricCard label="الفجوات" value={center.overview.gaps_count} />
                            </div>
                        </section>

                        <section className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">Coverage Map</h5>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                {center.coverage_map.items.map((item) => (
                                    <div
                                        key={item.key}
                                        className={cn(
                                            'rounded-xl border p-3 text-xs',
                                            item.status === 'covered'
                                                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                                                : 'border-amber-500/30 bg-amber-500/10 text-amber-100',
                                        )}
                                    >
                                        <div className="flex items-center justify-between gap-2">
                                            <p className="font-semibold">{item.label}</p>
                                            <span className="text-[11px]">{item.count}</span>
                                        </div>
                                        <p className="text-[11px] mt-1 opacity-90">{item.description}</p>
                                    </div>
                                ))}
                            </div>
                        </section>

                        <section className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">Story Gaps</h5>
                            {center.gaps.length > 0 ? (
                                <div className="space-y-2">
                                    {center.gaps.map((gap) => (
                                        <GapRow key={gap.code} gap={gap} />
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-100">
                                    لا توجد فجوات حرجة الآن. التغطية متوازنة.
                                </div>
                            )}
                        </section>

                        <section className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">الخط الزمني</h5>
                            <div className="space-y-2 max-h-[320px] overflow-y-auto pr-1">
                                {timeline.map((item) => (
                                    <div key={`${item.type}-${item.id}`} className="rounded-xl border border-white/10 bg-slate-900/60 p-3">
                                        <div className="flex items-center justify-between gap-3">
                                            <p className="text-[11px] text-cyan-300">
                                                {item.type === 'article' ? 'خبر' : 'مسودة'} #{item.id}
                                            </p>
                                            <p className="text-[11px] text-slate-500">
                                                {item.created_at ? formatRelativeTime(item.created_at) : 'بدون تاريخ'}
                                            </p>
                                        </div>
                                        <p className="text-sm text-white mt-1">{item.title}</p>
                                        <p className="text-[11px] text-slate-400 mt-1">
                                            {item.source_name ? `${item.source_name} • ` : ''}
                                            {item.status || 'بدون حالة'}
                                        </p>
                                    </div>
                                ))}
                                {timeline.length === 0 && <p className="text-xs text-slate-400">لا يوجد خط زمني متاح.</p>}
                            </div>
                        </section>

                        <section className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">قوالب القصة</h5>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                {center.templates.map((tpl) => (
                                    <div key={tpl.key} className="rounded-xl border border-white/10 bg-white/5 p-3">
                                        <p className="text-xs text-cyan-300">{tpl.label}</p>
                                        <p className="text-[11px] text-slate-400 mt-2 line-clamp-3">{tpl.sections.join(' • ')}</p>
                                    </div>
                                ))}
                            </div>
                        </section>
                    </div>
                )}
            </div>
        </div>
    );
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
    return (
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
            <p className="text-[11px] text-slate-400">{label}</p>
            <p className="text-sm font-semibold text-white mt-1">{value}</p>
        </div>
    );
}

function GapRow({ gap }: { gap: StoryGapItem }) {
    const severityClass = {
        high: 'border-red-500/30 bg-red-500/10 text-red-100',
        medium: 'border-amber-500/30 bg-amber-500/10 text-amber-100',
        low: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100',
    }[gap.severity] || 'border-white/15 bg-white/5 text-slate-100';

    const severityLabel = {
        high: 'مرتفع',
        medium: 'متوسط',
        low: 'منخفض',
    }[gap.severity] || gap.severity;

    return (
        <div className={cn('rounded-xl border p-3 text-xs', severityClass)}>
            <div className="flex items-center justify-between gap-2">
                <p className="font-semibold">{gap.title}</p>
                <span className="text-[11px]">{severityLabel}</span>
            </div>
            <p className="mt-1 opacity-95">{gap.recommendation}</p>
        </div>
    );
}
