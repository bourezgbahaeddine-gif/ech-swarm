'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
    AlertCircle,
    ArrowLeftCircle,
    BookOpenText,
    ChevronDown,
    ChevronUp,
    ClipboardList,
    FolderPlus,
    Loader2,
    Sparkles,
    RefreshCw,
} from 'lucide-react';

import {
    editorialApi,
    storiesApi,
    type StoryClusterRecord,
    type StoryControlCenterResponse,
    type StoryGapItem,
    type StoryRecord,
} from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { WorkflowCard, WorkflowSection } from '@/components/workflow/WorkflowCard';

export default function StoriesPage() {
    const router = useRouter();
    const [selectedStoryId, setSelectedStoryId] = useState<number | null>(null);
    const [clusterHours, setClusterHours] = useState<number>(24);
    const [clusterMinSize, setClusterMinSize] = useState<number>(2);
    const [view, setView] = useState<'queues' | 'clusters'>('queues');
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
    const clusterItems = useMemo(() => clusterReport?.items || [], [clusterReport?.items]);

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

    const storyDeskRows = useMemo(() => {
        return [...stories]
            .sort((a, b) => storyActionScore(b) - storyActionScore(a))
            .slice(0, 20);
    }, [stories]);

    const storyQueues = useMemo(() => {
        const active: StoryRecord[] = [];
        const needsUpdate: StoryRecord[] = [];
        const lostMomentum: StoryRecord[] = [];
        const needsNewAngle: StoryRecord[] = [];

        storyDeskRows.forEach((story) => {
            const bucket = classifyStoryQueue(story);
            if (bucket === 'lost_momentum') {
                lostMomentum.push(story);
                return;
            }
            if (bucket === 'new_angle') {
                needsNewAngle.push(story);
                return;
            }
            if (bucket === 'update') {
                needsUpdate.push(story);
                return;
            }
            active.push(story);
        });

        return {
            active,
            needsUpdate,
            lostMomentum,
            needsNewAngle,
        };
    }, [storyDeskRows]);

    const topPriorityStory = useMemo(() => {
        return (
            storyQueues.needsUpdate[0] ||
            storyQueues.active[0] ||
            storyQueues.needsNewAngle[0] ||
            storyQueues.lostMomentum[0] ||
            null
        );
    }, [storyQueues]);

    const {
        data: topStoryCenterData,
        isLoading: topStoryCenterLoading,
    } = useQuery({
        queryKey: ['stories-top-control-center', topPriorityStory?.id],
        queryFn: () => storiesApi.controlCenter(topPriorityStory!.id, { timeline_limit: 20 }),
        enabled: view === 'queues' && Boolean(topPriorityStory?.id),
        staleTime: 60_000,
    });
    const topStoryCenter = topStoryCenterData?.data;
    const topStoryNextGap = useMemo(() => (topStoryCenter?.gaps || [])[0] || null, [topStoryCenter?.gaps]);
    const topStoryNextMode = useMemo<'followup' | 'analysis' | 'background'>(() => {
        if (!topStoryNextGap) return 'followup';
        const mapped = mapGapToTask(topStoryNextGap);
        return mapped === 'source' ? 'followup' : mapped;
    }, [topStoryNextGap]);

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

    const runTopStoryNextAction = useMutation({
        mutationFn: async () => {
            if (!topStoryCenter) throw new Error('top_story_not_ready');
            return editorialApi.createManualWorkspaceDraft({
                title: buildStoryDraftTitle(topStoryCenter.story.title, topStoryNextMode),
                body: buildStoryDraftBody(topStoryCenter, topStoryNextMode),
                summary: `مسودة ${storyDraftModeLabel(topStoryNextMode)} مرتبطة بالقصة ${topStoryCenter.story.story_key}`,
                category: topStoryCenter.story.category || undefined,
                urgency: 'medium',
                source_action: `story_next_${topStoryNextMode}`,
            });
        },
        onSuccess: (res) => {
            const workId = res.data?.work_id;
            if (!workId) {
                setActionErr('تم إنشاء المسودة لكن بدون Work ID.');
                return;
            }
            setActionErr(null);
            setActionMsg(`تم تنفيذ الإجراء التالي: ${storyDraftModeLabel(topStoryNextMode)} وفتح المسودة.`);
            router.push(`/workspace-drafts?work_id=${encodeURIComponent(workId)}`);
        },
        onError: () => setActionErr('تعذر تنفيذ الإجراء التالي للقصة الآن.'),
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
                    onClick={() => setView('queues')}
                    className={cn(
                        'rounded-lg border px-3 py-1.5 text-xs transition-colors',
                        view === 'queues'
                            ? 'border-cyan-400/60 bg-cyan-500/20 text-cyan-100'
                            : 'border-white/10 bg-white/5 text-slate-300',
                    )}
                >
                    متابعة القصص
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

            {view === 'queues' && (
                storiesLoading ? (
                    <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">جاري تحميل طوابير القصص...</div>
                ) : (
                    <StoryQueuesSection
                        stories={storyDeskRows}
                        totalStories={stories.length}
                        queues={storyQueues}
                        topStory={topPriorityStory}
                        topStoryGaps={topStoryCenter?.gaps || []}
                        topStoryCoverage={topStoryCenter?.overview.coverage_score ?? null}
                        topStoryGapsLoading={topStoryCenterLoading}
                        topStoryNextActionLabel={storyDraftModeLabel(topStoryNextMode)}
                        nextActionPending={runTopStoryNextAction.isPending}
                        onRunNextAction={() => runTopStoryNextAction.mutate()}
                        onOpenStory={(storyId) => setSelectedStoryId(storyId)}
                    />
                )
            )}

            {selectedStoryId && (
                <StoryControlCenterDrawer storyId={selectedStoryId} onClose={() => setSelectedStoryId(null)} />
            )}
        </div>
    );
}

function StoryQueuesSection({
    stories,
    totalStories,
    queues,
    topStory,
    topStoryGaps,
    topStoryCoverage,
    topStoryGapsLoading,
    topStoryNextActionLabel,
    nextActionPending,
    onRunNextAction,
    onOpenStory,
}: {
    stories: StoryRecord[];
    totalStories: number;
    queues: {
        active: StoryRecord[];
        needsUpdate: StoryRecord[];
        lostMomentum: StoryRecord[];
        needsNewAngle: StoryRecord[];
    };
    topStory: StoryRecord | null;
    topStoryGaps: StoryGapItem[];
    topStoryCoverage: number | null;
    topStoryGapsLoading: boolean;
    topStoryNextActionLabel: string;
    nextActionPending: boolean;
    onRunNextAction: () => void;
    onOpenStory: (storyId: number) => void;
}) {
    const quickActionStories = useMemo(
        () => [...queues.needsUpdate, ...queues.active, ...queues.needsNewAngle].slice(0, 5),
        [queues],
    );

    return (
        <WorkflowSection
            title="طبقة متابعة القصص"
            hint="نرى فقط ما يحتاج متابعة فعلية: القصص النشطة، ما يحتاج تحديثًا، ما فقد الزخم، وما يحتاج زاوية جديدة."
            icon={<ClipboardList className="w-4 h-4 text-cyan-300" />}
            count={stories.length}
        >
            <div>
                <p className="text-[11px] text-slate-400">قرار سريع: ما القصة الأهم الآن، ما الذي ينقصها، وما الإجراء التالي؟</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs">
                <MetricCard label="إجمالي القصص" value={totalStories} />
                <MetricCard label="قصص نشطة" value={queues.active.length} />
                <MetricCard label="تحتاج تحديثًا" value={queues.needsUpdate.length} />
                <MetricCard label="فقدت الزخم" value={queues.lostMomentum.length} />
            </div>

            {stories.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">
                    لا توجد قصص بعد. ابدأ بقصة من خبر واحد أو من مجموعة مقترحة.
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 space-y-2">
                            <p className="text-xs font-semibold text-cyan-100">القصة الأهم الآن</p>
                            {topStory ? (
                                <>
                                    <p className="text-sm text-white line-clamp-2">{topStory.title}</p>
                                    <p className="text-[11px] text-cyan-100/90">{storyQueueReason(topStory)}</p>
                                    <p className="text-[10px] text-slate-300">
                                        التغطية: {topStoryCoverage ?? '-'}% • آخر تحديث: {formatRelativeTime(topStory.updated_at || topStory.created_at || '')}
                                    </p>
                                </>
                            ) : (
                                <p className="text-[11px] text-slate-300">لا توجد قصة نشطة الآن.</p>
                            )}
                        </div>

                        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 space-y-2">
                            <p className="text-xs font-semibold text-amber-100">ما الذي ينقص؟</p>
                            {topStoryGapsLoading ? (
                                <p className="text-[11px] text-slate-300">جاري تحليل الفجوات...</p>
                            ) : topStoryGaps.length > 0 ? (
                                topStoryGaps.slice(0, 3).map((gap) => (
                                    <div key={`desk-gap-${gap.code}`} className="rounded-lg border border-white/10 bg-black/20 p-2">
                                        <p className="text-[11px] text-white">{gap.title}</p>
                                        <p className="text-[10px] text-slate-400 mt-1">{mapGapTaskLabel(gap)}</p>
                                    </div>
                                ))
                            ) : (
                                <p className="text-[11px] text-emerald-100">لا توجد فجوات حرجة في القصة الأولى.</p>
                            )}
                        </div>

                        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 space-y-2">
                            <p className="text-xs font-semibold text-emerald-100">الإجراء التالي</p>
                            {topStory ? (
                                <>
                                    <p className="text-[11px] text-emerald-100/90">الإجراء المقترح: {topStoryNextActionLabel}</p>
                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            type="button"
                                            onClick={onRunNextAction}
                                            disabled={nextActionPending}
                                            className="inline-flex items-center gap-1 rounded-lg border border-emerald-300/40 bg-emerald-500/25 px-2.5 py-1.5 text-[11px] text-emerald-100 disabled:opacity-50"
                                        >
                                            {nextActionPending ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                                            نفّذ الإجراء الآن
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => onOpenStory(topStory.id)}
                                            className="inline-flex items-center gap-1 rounded-lg border border-emerald-300/40 bg-emerald-500/20 px-2.5 py-1.5 text-[11px] text-emerald-100"
                                        >
                                            فتح لوحة القرار
                                            <ArrowLeftCircle className="w-3 h-3" />
                                        </button>
                                    </div>
                                </>
                            ) : (
                                <p className="text-[11px] text-slate-300">لا توجد إجراءات حالية.</p>
                            )}
                        </div>
                    </div>

                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
                        <StoryQueueCard
                            title="قصص نشطة"
                            hint="يجري عليها العمل الآن أو شهدت تحديثًا حديثًا."
                            tone="cyan"
                            stories={queues.active}
                            onOpenStory={onOpenStory}
                        />
                        <StoryQueueCard
                            title="تحتاج تحديثًا"
                            hint="قصص تحتاج متابعة أو استكمالًا قبل أن تبرد."
                            tone="amber"
                            stories={queues.needsUpdate}
                            onOpenStory={onOpenStory}
                        />
                        <StoryQueueCard
                            title="فقدت الزخم"
                            hint="قصص ذات قيمة لكنها ابتعدت زمنيًا وتحتاج قرارًا: تنشيط أم إغلاق؟"
                            tone="rose"
                            stories={queues.lostMomentum}
                            onOpenStory={onOpenStory}
                        />
                        <StoryQueueCard
                            title="تحتاج زاوية جديدة"
                            hint="القصة اكتسبت مواد كافية لكن تحتاج مدخلًا أو زاوية متابعة جديدة."
                            tone="emerald"
                            stories={queues.needsNewAngle}
                            onOpenStory={onOpenStory}
                        />
                    </div>

                    <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                        <p className="text-xs text-slate-300 mb-2">أقرب 5 قصص لإجراء سريع</p>
                        <div className="space-y-2">
                            {quickActionStories.length > 0 ? quickActionStories.map((story) => (
                                <WorkflowCard
                                    key={`desk-row-${story.id}`}
                                    title={story.title}
                                    subtitle={`${story.story_key} • ${story.category || 'غير مصنف'}`}
                                    statusLabel={story.status}
                                    chips={[{ label: classifyStoryQueueLabel(story) }]}
                                    reason={storyQueueReason(story)}
                                    nextActionLabel={storyNextActionLabel(story)}
                                    timestamp={story.updated_at || story.created_at || ''}
                                    actions={
                                        <div className="flex justify-end">
                                            <button
                                                type="button"
                                                onClick={() => onOpenStory(story.id)}
                                                className="inline-flex items-center gap-1 rounded-lg border border-cyan-400/40 bg-cyan-500/15 px-2 py-1 text-[10px] text-cyan-100"
                                            >
                                                فتح
                                                <ArrowLeftCircle className="w-3 h-3" />
                                            </button>
                                        </div>
                                    }
                                />
                            )) : (
                                <p className="text-[11px] text-emerald-100">لا توجد قصص حرجة حاليًا.</p>
                            )}
                        </div>
                    </div>
                </>
            )}
        </WorkflowSection>
    );
}

function StoryQueueCard({
    title,
    hint,
    tone,
    stories,
    onOpenStory,
}: {
    title: string;
    hint: string;
    tone: 'cyan' | 'amber' | 'rose' | 'emerald';
    stories: StoryRecord[];
    onOpenStory: (storyId: number) => void;
}) {
    const toneClasses = {
        cyan: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100',
        amber: 'border-amber-500/30 bg-amber-500/10 text-amber-100',
        rose: 'border-rose-500/30 bg-rose-500/10 text-rose-100',
        emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100',
    }[tone];

    return (
        <section className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-3">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <h3 className={cn('text-sm font-semibold', toneClasses)}>{title}</h3>
                    <p className="text-[11px] text-slate-400 mt-1">{hint}</p>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-300">{stories.length}</span>
            </div>

            {stories.length === 0 ? (
                <div className="rounded-lg border border-dashed border-white/10 bg-white/5 px-3 py-4 text-[11px] text-slate-500">
                    لا توجد قصص في هذا المسار الآن.
                </div>
            ) : (
                <div className="space-y-2">
                    {stories.slice(0, 4).map((story) => (
                        <WorkflowCard
                            key={`${title}-${story.id}`}
                            title={story.title}
                            subtitle={`${story.story_key} • ${story.category || 'غير مصنف'}`}
                            statusLabel={story.status}
                            chips={[{ label: title, className: toneClasses }]}
                            reason={storyQueueReason(story)}
                            nextActionLabel={storyNextActionLabel(story)}
                            timestamp={story.updated_at || story.created_at || ''}
                            actions={
                                <div className="flex justify-end">
                                    <button
                                        type="button"
                                        onClick={() => onOpenStory(story.id)}
                                        className="inline-flex items-center gap-1 rounded-lg border border-white/15 bg-white/5 px-2 py-1 text-[10px] text-slate-200"
                                    >
                                        فتح القصة
                                        <ArrowLeftCircle className="w-3 h-3" />
                                    </button>
                                </div>
                            }
                        />
                    ))}
                </div>
            )}
        </section>
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
    const router = useRouter();
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [taskMsg, setTaskMsg] = useState<string | null>(null);
    const [taskErr, setTaskErr] = useState<string | null>(null);

    const { data, isLoading, error } = useQuery({
        queryKey: ['stories-control-center', storyId],
        queryFn: () => storiesApi.controlCenter(storyId, { timeline_limit: 40 }),
    });

    const center: StoryControlCenterResponse | undefined = data?.data;
    const centerTimeline = useMemo(() => center?.timeline || [], [center?.timeline]);
    const timeline = useMemo(() => {
        return [...centerTimeline].sort((a, b) => storyTimestamp(b.created_at) - storyTimestamp(a.created_at));
    }, [centerTimeline]);

    const lastSeenAt = useMemo(() => {
        if (typeof window === 'undefined') return null;
        return window.localStorage.getItem(`story_last_seen_${storyId}`);
    }, [storyId]);

    const lastSeenMs = useMemo(() => storyTimestamp(lastSeenAt), [lastSeenAt]);
    const updatesSinceLastSeen = useMemo(() => {
        if (!lastSeenMs) return timeline.slice(0, 2);
        return timeline.filter((item) => storyTimestamp(item.created_at) > lastSeenMs);
    }, [timeline, lastSeenMs]);

    const whatChangedLine = useMemo(() => {
        if (!lastSeenMs) return 'هذه أول زيارة لهذه القصة. ابدأ من الإجراء التالي مباشرة.';
        if (updatesSinceLastSeen.length === 0) return 'لا جديد منذ آخر زيارة.';
        return `تمت إضافة ${updatesSinceLastSeen.length} مادة منذ آخر زيارة.`;
    }, [lastSeenMs, updatesSinceLastSeen.length]);

    const topMaterials = useMemo(() => timeline.slice(0, 5), [timeline]);
    const taskGaps = useMemo(() => (center?.gaps || []).slice(0, 3), [center?.gaps]);
    const nextBestTask = useMemo(() => (taskGaps.length > 0 ? taskGaps[0] : null), [taskGaps]);
    const storyMode = useMemo(() => (center ? classifyStoryType(center) : null), [center]);

    const createStoryDraft = useMutation({
        mutationFn: async (mode: 'followup' | 'analysis' | 'background') => {
            if (!center) throw new Error('story_not_loaded');
            return editorialApi.createManualWorkspaceDraft({
                title: buildStoryDraftTitle(center.story.title, mode),
                body: buildStoryDraftBody(center, mode),
                summary: `مسودة ${mode === 'analysis' ? 'تحليل' : mode === 'background' ? 'خلفية' : 'متابعة'} مرتبطة بالقصة ${center.story.story_key}`,
                category: center.story.category || undefined,
                urgency: 'medium',
                source_action: `story_${mode}`,
            });
        },
        onSuccess: (res, mode) => {
            const workId = res.data?.work_id;
            if (!workId) {
                setTaskErr('تم إنشاء المسودة لكن بدون Work ID.');
                return;
            }
            setTaskErr(null);
            setTaskMsg(
                mode === 'analysis'
                    ? 'تم إنشاء مسودة تحليل وفتحها.'
                    : mode === 'background'
                      ? 'تم إنشاء مسودة خلفية وفتحها.'
                      : 'تم إنشاء مسودة متابعة وفتحها.',
            );
            router.push(`/workspace-drafts?work_id=${encodeURIComponent(workId)}`);
        },
        onError: () => setTaskErr('تعذر تنفيذ الإجراء. حاول مرة أخرى.'),
    });

    const runGapTask = (gap: StoryGapItem) => {
        setTaskMsg(null);
        setTaskErr(null);
        const task = mapGapToTask(gap);
        if (task === 'source') {
            const link = topMaterials.find((item) => Boolean(item.url))?.url;
            if (link && typeof window !== 'undefined') {
                window.open(link, '_blank', 'noopener,noreferrer');
                setTaskMsg('تم فتح مصدر مرجعي. أضف الإسناد ثم ارجع لإغلاق الفجوة.');
                return;
            }
            createStoryDraft.mutate('followup');
            return;
        }
        if (task === 'analysis') {
            createStoryDraft.mutate('analysis');
            return;
        }
        if (task === 'background') {
            createStoryDraft.mutate('background');
            return;
        }
        createStoryDraft.mutate('followup');
    };

    const runNextBestAction = () => {
        if (nextBestTask) {
            runGapTask(nextBestTask);
            return;
        }
        createStoryDraft.mutate('followup');
    };

    const closeDrawer = () => {
        if (typeof window !== 'undefined') {
            window.localStorage.setItem(`story_last_seen_${storyId}`, new Date().toISOString());
        }
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex justify-end" dir="rtl">
            <div className="w-full max-w-3xl h-full overflow-y-auto border-l border-white/10 bg-slate-950 p-5">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-white">مركز قرار القصة</h3>
                    <button onClick={closeDrawer} className="rounded-lg border border-white/15 px-3 py-1.5 text-xs text-slate-300">إغلاق</button>
                </div>

                {isLoading && <p className="text-slate-400 text-sm">جاري تحميل لوحة القصة...</p>}
                {error && (
                    <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200 inline-flex items-center gap-2">
                        <AlertCircle className="w-4 h-4" />
                        تعذر تحميل لوحة القصة.
                    </div>
                )}

                {center && (
                    <div className="space-y-4">
                        <section className="rounded-xl border border-white/10 bg-white/5 p-4">
                            <p className="text-xs text-cyan-300">{center.story.story_key}</p>
                            <h4 className="text-xl font-semibold text-white mt-1">{center.story.title}</h4>
                            <p className="text-xs text-slate-300 mt-2 line-clamp-2">
                                {center.highlights.latest_titles[0] || 'لا يوجد ملخص جاهز. استخدم الخطوة التالية لبدء المتابعة.'}
                            </p>
                            <p className="text-[11px] text-slate-400 mt-2">
                                الحالة: {center.story.status} • الأولوية: {center.story.priority} • آخر نشاط:{' '}
                                {center.overview.last_activity_at ? formatRelativeTime(center.overview.last_activity_at) : 'غير متاح'}
                            </p>
                            <p className="text-[11px] text-slate-400 mt-1">
                                نوع القصة: {storyMode?.label || 'غير محدد'} • لماذا مهمة الآن: {storyMode?.whyNow || 'نشاط تحريري مستمر'}
                            </p>
                        </section>

                        <section className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-4 space-y-3">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <p className="text-xs font-semibold text-cyan-100">ما الجديد منذ آخر مرة؟</p>
                                    <p className="text-[11px] text-cyan-100/90 mt-1">{whatChangedLine}</p>
                                </div>
                                <button
                                    type="button"
                                    onClick={runNextBestAction}
                                    disabled={createStoryDraft.isPending}
                                    className="inline-flex items-center gap-1 rounded-lg border border-cyan-300/40 bg-cyan-500/20 px-3 py-1.5 text-xs text-cyan-100 disabled:opacity-50"
                                >
                                    <Sparkles className="w-3.5 h-3.5" />
                                    {nextBestTask ? `الإجراء التالي: ${mapGapTaskLabel(nextBestTask)}` : 'إنشاء متابعة الآن'}
                                </button>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                                <MetricCard label="التغطية" value={`${center.overview.coverage_score}%`} />
                                <MetricCard label="الفجوات" value={center.overview.gaps_count} />
                                <MetricCard label="مواد القصة" value={center.overview.items_total} />
                                <MetricCard label="المسودات" value={center.overview.drafts_count} />
                            </div>
                        </section>

                        {taskMsg && (
                            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">{taskMsg}</div>
                        )}
                        {taskErr && (
                            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">{taskErr}</div>
                        )}

                        <section className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">الفجوات كمهام تنفيذية</h5>
                            {taskGaps.length > 0 ? (
                                <div className="space-y-2">
                                    {taskGaps.map((gap) => (
                                        <div key={gap.code} className="rounded-xl border border-white/10 bg-white/5 p-3">
                                            <div className="flex items-start justify-between gap-2">
                                                <div className="min-w-0">
                                                    <p className="text-xs text-white font-semibold">{gap.title}</p>
                                                    <p className="text-[11px] text-slate-300 mt-1">{gap.recommendation}</p>
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={() => runGapTask(gap)}
                                                    disabled={createStoryDraft.isPending}
                                                    className="shrink-0 rounded-lg border border-white/15 bg-white/10 px-2 py-1 text-[11px] text-slate-100 disabled:opacity-50"
                                                >
                                                    {mapGapTaskLabel(gap)}
                                                </button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-100">
                                    لا توجد فجوات حرجة. يمكنك إنشاء متابعة قصيرة أو إغلاق القصة.
                                </div>
                            )}
                        </section>

                        <section className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">مواد جاهزة للاستخدام (5 عناصر)</h5>
                            <div className="space-y-2">
                                {topMaterials.map((item) => (
                                    <div key={`${item.type}-${item.id}`} className="rounded-xl border border-white/10 bg-slate-900/60 p-3">
                                        <div className="flex items-center justify-between gap-3">
                                            <p className="text-[11px] text-cyan-300">{item.type === 'article' ? 'خبر' : 'مسودة'} #{item.id}</p>
                                            <p className="text-[11px] text-slate-500">{item.created_at ? formatRelativeTime(item.created_at) : 'بدون تاريخ'}</p>
                                        </div>
                                        <p className="text-sm text-white mt-1">{item.title}</p>
                                        <p className="text-[11px] text-slate-400 mt-1">
                                            {item.source_name ? `${item.source_name} • ` : ''}
                                            {item.status || 'بدون حالة'}
                                        </p>
                                        <div className="mt-2 flex flex-wrap items-center gap-2">
                                            {item.type === 'article' && (
                                                <a href={`/news/${item.id}`} className="text-[11px] text-cyan-300" target="_blank" rel="noreferrer">فتح الخبر</a>
                                            )}
                                            {item.work_id && (
                                                <a
                                                    href={`/workspace-drafts?work_id=${encodeURIComponent(item.work_id)}`}
                                                    className="text-[11px] text-emerald-300"
                                                    target="_blank"
                                                    rel="noreferrer"
                                                >
                                                    فتح المسودة
                                                </a>
                                            )}
                                            {item.url && <a href={item.url} className="text-[11px] text-sky-300" target="_blank" rel="noreferrer">المصدر</a>}
                                        </div>
                                    </div>
                                ))}
                                {topMaterials.length === 0 && <p className="text-xs text-slate-400">لا توجد مواد مرتبطة كافية بعد.</p>}
                            </div>
                        </section>

                        <section className="rounded-xl border border-white/10 bg-black/20 p-3">
                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={() => createStoryDraft.mutate('followup')}
                                    disabled={createStoryDraft.isPending}
                                    className="rounded-lg border border-white/15 bg-white/10 px-2.5 py-1 text-[11px] text-slate-100 disabled:opacity-50"
                                >
                                    إنشاء متابعة
                                </button>
                                <button
                                    type="button"
                                    onClick={() => createStoryDraft.mutate('analysis')}
                                    disabled={createStoryDraft.isPending}
                                    className="rounded-lg border border-white/15 bg-white/10 px-2.5 py-1 text-[11px] text-slate-100 disabled:opacity-50"
                                >
                                    إنشاء تحليل
                                </button>
                                <button
                                    type="button"
                                    onClick={() => createStoryDraft.mutate('background')}
                                    disabled={createStoryDraft.isPending}
                                    className="rounded-lg border border-white/15 bg-white/10 px-2.5 py-1 text-[11px] text-slate-100 disabled:opacity-50"
                                >
                                    إنشاء خلفية
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setShowAdvanced((prev) => !prev)}
                                    className="rounded-lg border border-white/15 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300"
                                >
                                    {showAdvanced ? 'إخفاء التفاصيل المتقدمة' : 'عرض التفاصيل المتقدمة'}
                                </button>
                            </div>
                        </section>

                        {showAdvanced && (
                            <section className="space-y-2 rounded-xl border border-white/10 bg-black/20 p-3">
                                <h5 className="text-sm font-semibold text-white">تفاصيل متقدمة</h5>
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
                                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                                    {center.templates.map((tpl) => (
                                        <div key={tpl.key} className="rounded-xl border border-white/10 bg-white/5 p-3">
                                            <p className="text-xs text-cyan-300">{tpl.label}</p>
                                            <p className="text-[11px] text-slate-400 mt-2 line-clamp-3">{tpl.sections.join(' • ')}</p>
                                        </div>
                                    ))}
                                </div>
                            </section>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}

function storyTimestamp(value?: string | null) {
    if (!value) return 0;
    const ts = new Date(value).getTime();
    return Number.isFinite(ts) ? ts : 0;
}

function classifyStoryType(center: StoryControlCenterResponse): { key: string; label: string; whyNow: string } {
    const hoursSinceActivity = center.overview.last_activity_at
        ? Math.max(0, (Date.now() - storyTimestamp(center.overview.last_activity_at)) / 3_600_000)
        : 999;

    if (hoursSinceActivity <= 2 && center.overview.items_total <= 6) {
        return {
            key: 'breaking_expansion',
            label: 'Breaking Expansion',
            whyNow: 'تحديثات سريعة خلال الساعات الأخيرة',
        };
    }
    if (center.overview.items_total >= 10 && center.overview.coverage_score < 70) {
        return {
            key: 'running_story',
            label: 'Running Story',
            whyNow: 'القصة ممتدة وتحتاج سد فجوات التغطية',
        };
    }
    if (center.overview.coverage_score >= 75 && center.overview.gaps_count <= 1) {
        return {
            key: 'background_file',
            label: 'Background File',
            whyNow: 'التغطية مكتملة نسبيًا وتصلح كمرجع',
        };
    }
    return {
        key: 'issue_tracking',
        label: 'Issue Tracking',
        whyNow: 'قضية مستمرة تحتاج متابعة دورية',
    };
}

function storyHoursSinceLastUpdate(story: StoryRecord) {
    const ts = storyTimestamp(story.updated_at || story.created_at);
    if (!ts) return 999;
    return Math.max(0, (Date.now() - ts) / 3_600_000);
}

function classifyStoryQueue(story: StoryRecord): 'active' | 'update' | 'lost_momentum' | 'new_angle' {
    const hours = storyHoursSinceLastUpdate(story);
    const itemCount = story.items?.length || 0;
    const priority = story.priority || 0;
    const status = (story.status || '').toLowerCase();

    if (hours >= 48 || (hours >= 36 && priority >= 7)) {
        return 'lost_momentum';
    }
    if (itemCount >= 6 && hours >= 18 && Boolean(story.summary)) {
        return 'new_angle';
    }
    if (!story.summary || status.includes('draft') || hours >= 12) {
        return 'update';
    }
    return 'active';
}

function classifyStoryQueueLabel(story: StoryRecord) {
    const bucket = classifyStoryQueue(story);
    if (bucket === 'lost_momentum') return 'فقدت الزخم';
    if (bucket === 'new_angle') return 'تحتاج زاوية جديدة';
    if (bucket === 'update') return 'تحتاج تحديثًا';
    return 'قصة نشطة';
}

function storyActionScore(story: StoryRecord) {
    const status = (story.status || '').toLowerCase();
    const hours = storyHoursSinceLastUpdate(story);
    let score = Math.min(story.priority || 0, 10) * 4;
    if (hours <= 2) score += 35;
    else if (hours <= 6) score += 25;
    else if (hours <= 12) score += 15;
    if (['draft', 'active', 'in_progress', 'open'].some((item) => status.includes(item))) score += 18;
    if (!story.summary) score += 8;
    return score;
}

function storyQueueReason(story: StoryRecord) {
    const bucket = classifyStoryQueue(story);
    if (bucket === 'lost_momentum') {
        return 'القصة ابتعدت زمنيًا عن آخر تحديث وتحتاج قرارًا واضحًا: إعادة تنشيط أو إغلاق مؤقت.';
    }
    if (bucket === 'new_angle') {
        return 'القصة جمعت مواد كافية، لكن قيمتها الآن في زاوية جديدة أو معالجة أعمق.';
    }
    if (bucket === 'update') {
        if (!story.summary) {
            return 'القصة موجودة لكن ما زالت تحتاج ملخصًا واضحًا وزاوية متابعة قبل أن تصبح سهلة التداول.';
        }
        return 'مرّ وقت كافٍ منذ آخر تحديث، ومن الأفضل دفع متابعة جديدة أو استكمال الفجوات.';
    }
    return 'هناك نشاط حديث أو أولوية قائمة تجعل هذه القصة ضمن المتابعة الجارية الآن.';
}

function storyNextActionLabel(story: StoryRecord) {
    const bucket = classifyStoryQueue(story);
    const status = (story.status || '').toLowerCase();
    if (bucket === 'lost_momentum') return 'حسم قرار التنشيط أو الإغلاق';
    if (bucket === 'new_angle') return 'إنشاء زاوية أو معالجة جديدة';
    if (status.includes('draft')) return 'إنهاء المتابعة الحالية';
    if (!story.summary) return 'إضافة ملخص وزاوية';
    if ((story.priority || 0) >= 8) return 'إنشاء متابعة قصيرة';
    return 'مراجعة الفجوات';
}

function mapGapToTask(gap: StoryGapItem): 'followup' | 'analysis' | 'background' | 'source' {
    const text = `${gap.code} ${gap.title} ${gap.recommendation}`.toLowerCase();
    if (text.includes('تحليل') || text.includes('analysis')) return 'analysis';
    if (text.includes('خلفي') || text.includes('background') || text.includes('timeline')) return 'background';
    if (text.includes('مصدر') || text.includes('source') || text.includes('تصريح') || text.includes('quote')) return 'source';
    return 'followup';
}

function mapGapTaskLabel(gap: StoryGapItem) {
    const task = mapGapToTask(gap);
    if (task === 'analysis') return 'إنشاء تحليل';
    if (task === 'background') return 'إضافة خلفية';
    if (task === 'source') return 'فتح مصدر';
    return 'إنشاء متابعة';
}

function storyDraftModeLabel(mode: 'followup' | 'analysis' | 'background') {
    if (mode === 'analysis') return 'تحليل';
    if (mode === 'background') return 'خلفية';
    return 'متابعة';
}

function buildStoryDraftTitle(storyTitle: string, mode: 'followup' | 'analysis' | 'background') {
    if (mode === 'analysis') return `${storyTitle} — تحليل`;
    if (mode === 'background') return `${storyTitle} — خلفية`;
    return `${storyTitle} — متابعة`;
}

function buildStoryDraftBody(center: StoryControlCenterResponse, mode: 'followup' | 'analysis' | 'background') {
    const latest = center.timeline.slice(0, 3);
    const latestLines = latest
        .map((item, idx) => `${idx + 1}. ${item.title}${item.source_name ? ` (${item.source_name})` : ''}`)
        .join('\n');
    const gapLines = center.gaps.slice(0, 3).map((gap) => `- ${gap.title}`).join('\n');
    if (mode === 'analysis') {
        return `مقدمة تحليلية:\n\nالخلفية:\n${latestLines || '- لا توجد مواد بعد'}\n\nقراءة وتأثيرات:\n\nما الذي ينقص:\n${gapLines || '- لا توجد فجوات حرجة'}\n\nخلاصة:\n`;
    }
    if (mode === 'background') {
        return `خلفية القصة:\n\nالتسلسل:\n${latestLines || '- لا توجد مواد بعد'}\n\nالسياق الأوسع:\n\nنقاط يجب توضيحها:\n${gapLines || '- لا توجد فجوات حرجة'}\n`;
    }
    return `تحديث جديد على القصة:\n\nأهم المستجدات:\n${latestLines || '- لا توجد مواد بعد'}\n\nما الجديد عن التغطية السابقة:\n\nالخطوة التالية:\n`;
}

function MetricCard({ label, value }: { label: string; value: string | number }) {
    return (
        <div className="rounded-xl border border-white/10 bg-white/5 p-3 text-slate-200">
            <p className="text-[11px] text-slate-400">{label}</p>
            <p className="text-sm font-semibold text-white mt-1">{value}</p>
        </div>
    );
}
