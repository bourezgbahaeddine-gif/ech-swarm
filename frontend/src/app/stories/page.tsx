'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, BookOpenText, RefreshCw } from 'lucide-react';

import { storiesApi, type StoryDossierResponse } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';

export default function StoriesPage() {
    const [selectedStoryId, setSelectedStoryId] = useState<number | null>(null);

    const { data, isLoading, refetch, isRefetching, error } = useQuery({
        queryKey: ['stories-page-list'],
        queryFn: () => storiesApi.list({ limit: 120 }),
    });

    const stories = useMemo(() => data?.data || [], [data?.data]);

    return (
        <div className="space-y-4">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white inline-flex items-center gap-2">
                        <BookOpenText className="w-6 h-6 text-cyan-300" />
                        القصص التحريرية
                    </h1>
                    <p className="text-xs text-slate-400 mt-1">متابعة القصة عبر الأخبار والمسودات في مكان واحد.</p>
                </div>
                <button
                    type="button"
                    onClick={() => refetch()}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300 hover:text-white"
                >
                    <RefreshCw className={cn('w-4 h-4', isRefetching && 'animate-spin')} />
                    تحديث
                </button>
            </div>

            {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                    فشل جلب القصص التحريرية.
                </div>
            )}

            {isLoading ? (
                <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">جاري التحميل...</div>
            ) : (
                <div className="grid grid-cols-1 gap-3">
                    {stories.length === 0 && (
                        <div className="rounded-2xl border border-white/10 bg-slate-900/40 p-6 text-slate-400">
                            لا توجد قصص بعد. أنشئ قصة من صفحة الخبر باستخدام زر "إنشاء قصة".
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
