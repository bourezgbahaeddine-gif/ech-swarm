'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, BookOpenText, RefreshCw } from 'lucide-react';

import { storiesApi, type StoryClusterRecord, type StoryDossierResponse } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';

export default function StoriesPage() {
    const [selectedStoryId, setSelectedStoryId] = useState<number | null>(null);
    const [clusterHours, setClusterHours] = useState<number>(24);
    const [clusterMinSize, setClusterMinSize] = useState<number>(2);

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
        queryFn: () => storiesApi.clusters({ hours: clusterHours, min_size: clusterMinSize, limit: 20 }),
    });

    const stories = useMemo(() => data?.data || [], [data?.data]);
    const clusterReport = clustersData?.data;
    const clusterItems = clusterReport?.items || [];

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

            <StoryClustersSection
                loading={clustersLoading}
                report={clusterReport}
                items={clusterItems}
                hours={clusterHours}
                minSize={clusterMinSize}
                onChangeHours={setClusterHours}
                onChangeMinSize={setClusterMinSize}
            />

            {isLoading ? (
                <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">جاري التحميل...</div>
            ) : (
                <div className="grid grid-cols-1 gap-3">
                    {stories.length === 0 && (
                        <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">
                            لا توجد قصص بعد. أنشئ قصة من صفحة الخبر باستخدام زر &quot;إنشاء قصة&quot;.
                        </div>
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
            )}

            {selectedStoryId && (
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
    minSize,
    onChangeHours,
    onChangeMinSize,
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
    onChangeHours: (value: number) => void;
    onChangeMinSize: (value: number) => void;
}) {
    return (
        <section className="rounded-2xl border border-white/10 bg-slate-900/40 p-4 space-y-4">
            <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-white">Story Clusters</h2>
                <div className="flex items-center gap-2">
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
                    Clusters Created: <span className="text-white font-semibold">{report?.metrics?.clusters_created ?? 0}</span>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
                    Avg Cluster Size: <span className="text-white font-semibold">{report?.metrics?.average_cluster_size ?? 0}</span>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
                    Avg Time To Cluster: <span className="text-white font-semibold">{report?.metrics?.time_to_cluster_minutes ?? 'n/a'} min</span>
                </div>
            </div>

            {loading ? (
                <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-4 text-xs text-slate-400">جاري تحميل المجموعات...</div>
            ) : (
                <div className="space-y-2">
                    {items.map((cluster) => (
                        <ClusterCard key={cluster.cluster_id} cluster={cluster} />
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

function ClusterCard({ cluster }: { cluster: StoryClusterRecord }) {
    return (
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 space-y-2">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <p className="text-[11px] text-cyan-300">{cluster.cluster_key}</p>
                    <p className="text-sm text-white font-medium">{cluster.label || `Cluster #${cluster.cluster_id}`}</p>
                    <p className="text-[11px] text-slate-400 mt-1">
                        {cluster.category || 'uncategorized'} • {cluster.geography || 'n/a'} • members: {cluster.cluster_size}
                    </p>
                </div>
                <p className="text-[11px] text-slate-500">{cluster.latest_article_at ? formatRelativeTime(cluster.latest_article_at) : 'no activity'}</p>
            </div>
            <div className="flex flex-wrap gap-1">
                {cluster.top_entities.slice(0, 4).map((entity) => (
                    <span key={`${cluster.cluster_id}-entity-${entity.entity}`} className="rounded-full bg-cyan-500/15 px-2 py-0.5 text-[10px] text-cyan-100">
                        {entity.entity} ({entity.count})
                    </span>
                ))}
                {cluster.top_topics.slice(0, 4).map((topic) => (
                    <span key={`${cluster.cluster_id}-topic-${topic.topic}`} className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-100">
                        #{topic.topic}
                    </span>
                ))}
            </div>
            <div className="space-y-1">
                {cluster.members.slice(0, 5).map((member) => (
                    <p key={`${cluster.cluster_id}-${member.article_id}`} className="text-[11px] text-slate-200">
                        • {member.title} <span className="text-slate-500">({member.source_name || 'unknown'})</span>
                    </p>
                ))}
                {cluster.members.length === 0 && <p className="text-[11px] text-slate-500">لا توجد عناصر.</p>}
            </div>
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
