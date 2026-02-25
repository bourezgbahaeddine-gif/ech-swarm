'use client';

import { useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    ArrowRight,
    ExternalLink,
    Clock,
    Tag,
    ShieldCheck,
    Sparkles,
    Wand2,
    Clipboard,
    FileCheck2,
    Languages,
    Send,
    CircleHelp,
    RotateCcw,
    Link2,
    BookOpenText,
    Loader2,
    Film,
    ScrollText,
} from 'lucide-react';
import { constitutionApi } from '@/lib/constitution-api';
import { editorialApi, newsApi, scriptsApi, storiesApi, type StoryDossierResponse, type StorySuggestion } from '@/lib/api';
import { formatDate, formatRelativeTime, getCategoryLabel, getStatusColor, cn } from '@/lib/utils';

type NewsGuideType = 'welcome' | 'action';
type NewsActionId = 'open_editor' | 'handoff' | 'summarize' | 'fact_check' | 'translate' | 'copy_output';

const NEWS_HELP_KEY = 'news_details_help_seen_v1';
const NEWS_ACTION_HELP_PREFIX = 'news_details_action_help_seen_v1_';

const NEWS_ACTION_HELP: Record<NewsActionId, { title: string; description: string }> = {
    open_editor: { title: 'فتح في المحرر الذكي', description: 'ينقلك لمسار التحرير الكامل لإنتاج النسخة النهائية.' },
    handoff: { title: 'ترشيح للتحرير', description: 'يسجل الخبر في دورة التحرير ويربطه برقم عمل.' },
    summarize: { title: 'تلخيص سريع', description: 'ينتج ملخصًا عمليًا لتقييم الخبر بسرعة قبل التحرير.' },
    fact_check: { title: 'تحقق أولي', description: 'يجري فحصًا أوليًا للتناسق والادعاءات قبل الاعتماد.' },
    translate: { title: 'ترجمة', description: 'ينتج نسخة مترجمة بنفس المعنى التحريري دون تهويل.' },
    copy_output: { title: 'نسخ النتيجة', description: 'ينسخ مخرج الأداة الحالي لاستخدامه في المحرر أو التقارير.' },
};

function sanitizeToolText(text: string): string {
    return (text || '')
        .replace(/```[\s\S]*?```/g, '')
        .replace(/^\s*(note|notes|explanation|comment)\s*:.*$/gim, '')
        .replace(/^\s*(ملاحظة|شرح|تعليق)\s*:.*$/gim, '')
        .trim();
}


function normalizeArticleHtml(input: string): string {
    let html = String(input || '').trim();
    if (!html) return '';
    const bodyMatch = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
    if (bodyMatch?.[1]) html = bodyMatch[1];
    html = html
        .replace(/<script[\s\S]*?<\/script>/gi, '')
        .replace(/<style[\s\S]*?<\/style>/gi, '')
        .replace(/<\/?(html|head|body|meta|title|link|doctype)[^>]*>/gi, '');
    return html.trim();
}

function actionKey(action: NewsActionId): string {
    return `${NEWS_ACTION_HELP_PREFIX}${action}`;
}

export default function NewsDetailsPage() {
    const params = useParams<{ id: string }>();
    const router = useRouter();
    const queryClient = useQueryClient();
    const id = useMemo(() => Number(params?.id || 0), [params?.id]);

    const [actionMessage, setActionMessage] = useState<string>('');
    const [toolOutput, setToolOutput] = useState<string>('');
    const [toolLabel, setToolLabel] = useState<string>('');
    const [tipSeed, setTipSeed] = useState(0);
    const [storyPanelOpen, setStoryPanelOpen] = useState(false);
    const [activeDossierStoryId, setActiveDossierStoryId] = useState<number | null>(null);
    const [linkedStoryId, setLinkedStoryId] = useState<number | null>(null);

    const [guideOpen, setGuideOpen] = useState(false);
    const [guideType, setGuideType] = useState<NewsGuideType>('welcome');
    const [guideAction, setGuideAction] = useState<NewsActionId | null>(null);
    const pendingActionRef = useRef<null | (() => void)>(null);

    const { data, isLoading, isError } = useQuery({
        queryKey: ['news-details', id],
        queryFn: () => newsApi.get(id),
        enabled: Number.isFinite(id) && id > 0,
    });

    const { data: tipsData } = useQuery({
        queryKey: ['constitution-tips-news-page'],
        queryFn: () => constitutionApi.tips(),
    });

    const handoffMutation = useMutation({
        mutationFn: () => editorialApi.handoff(id),
        onSuccess: (res) => {
            const workId = res.data?.work_id;
            setActionMessage(workId ? `تم ترشيح الخبر للتحرير. رقم العمل: ${workId}` : 'تم ترشيح الخبر للتحرير.');
        },
        onError: () => setActionMessage('تعذر ترشيح الخبر حالياً.'),
    });

    const toolMutation = useMutation({
        mutationFn: (action: 'summarize' | 'fact_check' | 'translate') =>
            editorialApi.process(id, { action }),
        onSuccess: (res, action) => {
            const resultText = sanitizeToolText(
                String(res.data?.result || res.data?.draft?.body || ''),
            );
            const labels: Record<string, string> = {
                summarize: 'ملخص سريع',
                fact_check: 'تحقق أولي',
                translate: 'ترجمة',
            };
            setToolLabel(labels[action] || 'نتيجة الأداة');
            setToolOutput(resultText || 'لا توجد نتيجة نصية متاحة من الأداة.');
        },
        onError: () => {
            setToolLabel('نتيجة الأداة');
            setToolOutput('تعذر تنفيذ الأداة حالياً.');
        },
    });

    const createStoryMutation = useMutation({
        mutationFn: () => storiesApi.createFromArticle(id, { reuse: true }),
        onSuccess: (res) => {
            const payload = res.data;
            setActionMessage(
                payload.reused
                    ? `تم استخدام القصة الحالية ${payload.story.story_key} وربط الخبر بها مسبقاً.`
                    : `تم إنشاء قصة جديدة ${payload.story.story_key} وربط الخبر بها.`,
            );
            setLinkedStoryId(payload.story.id);
            setActiveDossierStoryId(payload.story.id);
            queryClient.invalidateQueries({ queryKey: ['stories-page-list'] });
        },
        onError: () => setActionMessage('تعذر إنشاء القصة من هذا الخبر حالياً.'),
    });

    const generateStoryScriptMutation = useMutation({
        mutationFn: () =>
            scriptsApi.createFromArticle(id, {
                type: 'story_script',
                tone: 'neutral',
                language: 'ar',
                length_seconds: 90,
                style_constraints: [],
            }),
        onSuccess: (res) => {
            setActionMessage(`تم إرسال سكربت القصة للتوليد: ${res.data.script.title}`);
            router.push(`/scripts?script_id=${res.data.script.id}`);
        },
        onError: () => setActionMessage('تعذر إرسال مهمة Story Script حالياً.'),
    });

    const generateVideoPackageMutation = useMutation({
        mutationFn: () =>
            scriptsApi.createFromArticle(id, {
                type: 'video_script',
                tone: 'neutral',
                language: 'ar',
                length_seconds: 75,
                style_constraints: [],
            }),
        onSuccess: (res) => {
            setActionMessage(`تم إرسال باقة الفيديو للتوليد: ${res.data.script.title}`);
            router.push(`/scripts?script_id=${res.data.script.id}`);
        },
        onError: () => setActionMessage('تعذر إرسال مهمة Video Package حالياً.'),
    });

    const { data: suggestionsData, isFetching: suggestionsLoading } = useQuery({
        queryKey: ['story-suggestions', id, storyPanelOpen],
        queryFn: () => storiesApi.suggest(id, { limit: 10 }),
        enabled: storyPanelOpen && Number.isFinite(id) && id > 0,
    });
    const suggestions = (suggestionsData?.data || []) as StorySuggestion[];

    const linkToStoryMutation = useMutation({
        mutationFn: (storyId: number) => storiesApi.linkArticle(storyId, id),
        onSuccess: (_res, storyId) => {
            setActionMessage('تم ربط الخبر بالقصة بنجاح.');
            setLinkedStoryId(storyId);
            setActiveDossierStoryId(storyId);
            setStoryPanelOpen(false);
            queryClient.invalidateQueries({ queryKey: ['stories-page-list'] });
            queryClient.invalidateQueries({ queryKey: ['story-suggestions', id, true] });
        },
        onError: () => setActionMessage('تعذر ربط الخبر بالقصة المحددة.'),
    });

    function openWelcomeGuide() {
        setGuideType('welcome');
        setGuideAction(null);
        setGuideOpen(true);
    }

    function closeGuide() {
        setGuideOpen(false);
        setGuideAction(null);
        pendingActionRef.current = null;
    }

    function runWithGuide(action: NewsActionId, callback: () => void) {
        if (typeof window === 'undefined') return callback();
        if (window.localStorage.getItem(actionKey(action))) return callback();
        pendingActionRef.current = callback;
        setGuideType('action');
        setGuideAction(action);
        setGuideOpen(true);
    }

    function confirmGuide() {
        if (typeof window !== 'undefined') {
            if (guideType === 'welcome') window.localStorage.setItem(NEWS_HELP_KEY, '1');
            if (guideType === 'action' && guideAction) window.localStorage.setItem(actionKey(guideAction), '1');
        }
        const next = pendingActionRef.current;
        closeGuide();
        if (next) next();
    }

    const article = data?.data;
    const tips = (tipsData?.data?.tips || []) as string[];
    const currentTip = tips.length ? tips[Math.abs(tipSeed) % tips.length] : 'تحقق من الادعاءات قبل أي اعتماد نهائي.';

    if (isLoading) {
        return <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-6 animate-pulse h-72" />;
    }

    if (isError || !article) {
        return (
            <div className="space-y-4" dir="rtl">
                <Link
                    href="/news"
                    className="inline-flex items-center gap-2 text-sm text-emerald-300 hover:text-emerald-200"
                >
                    <ArrowRight className="w-4 h-4" />
                    العودة إلى الأخبار
                </Link>
                <div className="rounded-2xl border border-red-500/20 bg-red-500/5 p-5 text-red-300">
                    تعذر تحميل تفاصيل الخبر.
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-5" dir="rtl">
            <div className="flex items-center justify-between gap-3">
                <Link href="/news" className="inline-flex items-center gap-2 text-sm text-emerald-300 hover:text-emerald-200">
                    <ArrowRight className="w-4 h-4" />
                    العودة إلى الأخبار
                </Link>

                <a
                    href={article.original_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 text-sm px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-gray-200 hover:text-white hover:border-white/20"
                >
                    <ExternalLink className="w-4 h-4" />
                    المصدر الأصلي
                </a>
            </div>

            {actionMessage && (
                <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-sm text-cyan-100">
                    {actionMessage}
                </div>
            )}

            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
                <article className="xl:col-span-8 rounded-2xl border border-white/5 bg-gray-900/40 p-6 space-y-5">
                    <header className="space-y-3">
                        <h1 className="text-2xl font-bold text-white leading-relaxed">
                            {article.title_ar || article.original_title}
                        </h1>
                        <div className="flex flex-wrap items-center gap-2 text-xs text-gray-400">
                            <span className={cn('px-2 py-1 rounded-md border', getStatusColor(article.status))}>
                                {article.status}
                            </span>
                            <span className="px-2 py-1 rounded-md border border-white/10 bg-white/5 text-gray-300 inline-flex items-center gap-1">
                                <Tag className="w-3 h-3" />
                                {getCategoryLabel(article.category)}
                            </span>
                            <span className="px-2 py-1 rounded-md border border-white/10 bg-white/5 text-gray-300 inline-flex items-center gap-1">
                                <Clock className="w-3 h-3" />
                                {formatRelativeTime(article.created_at)}
                            </span>
                            <span className="px-2 py-1 rounded-md border border-white/10 bg-white/5 text-gray-300">
                                {article.source_name || 'غير معروف'}
                            </span>
                            {typeof article.truth_score === 'number' && (
                                <span className="px-2 py-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 inline-flex items-center gap-1">
                                    <ShieldCheck className="w-3 h-3" />
                                    وثوقية: {article.truth_score.toFixed(2)}
                                </span>
                            )}
                        </div>
                    </header>

                    {article.summary && (
                        <section className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                            <h2 className="text-sm text-gray-300 mb-2">الملخص</h2>
                            <p className="text-sm text-gray-200 leading-7">{article.summary}</p>
                        </section>
                    )}

                    <section className="space-y-3">
                        <h2 className="text-sm text-gray-300">المحتوى</h2>
                        {article.body_html ? (
                            <div
                                className="prose prose-invert max-w-none prose-p:leading-8 prose-p:text-gray-200"
                                dangerouslySetInnerHTML={{ __html: normalizeArticleHtml(article.body_html) }}
                            />
                        ) : (
                            <p className="text-sm text-gray-400 leading-7 whitespace-pre-wrap">
                                {article.original_content || 'لا يوجد محتوى متاح لهذا الخبر.'}
                            </p>
                        )}
                    </section>

                    <footer className="text-xs text-gray-500 border-t border-white/5 pt-4 space-y-1">
                        <div>نشر في المصدر: {article.published_at ? formatDate(article.published_at) : 'غير متاح'}</div>
                        <div>تمت إضافته: {formatDate(article.created_at)}</div>
                        <div>آخر تحديث: {formatDate(article.updated_at)}</div>
                    </footer>
                </article>

                <aside className="xl:col-span-4 space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-3">
                        <div className="flex items-center justify-between gap-2">
                            <h3 className="text-sm font-semibold text-white inline-flex items-center gap-2">
                                <Wand2 className="w-4 h-4 text-emerald-400" />
                                أدوات التعامل مع الخبر
                            </h3>
                            <button
                                onClick={openWelcomeGuide}
                                className="inline-flex items-center gap-1 rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-[11px] text-cyan-200"
                            >
                                <CircleHelp className="w-3.5 h-3.5" /> دليل
                            </button>
                        </div>
                        <div className="grid grid-cols-1 gap-2">
                            <button
                                onClick={() => createStoryMutation.mutate()}
                                disabled={createStoryMutation.isPending}
                                className="h-10 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-sm text-emerald-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                {createStoryMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <BookOpenText className="w-4 h-4" />}
                                إنشاء قصة
                            </button>
                            <button
                                onClick={() => setStoryPanelOpen(true)}
                                className="h-10 rounded-xl border border-sky-500/30 bg-sky-500/15 text-sm text-sky-200 inline-flex items-center justify-center gap-2"
                            >
                                <Link2 className="w-4 h-4" /> ربط مع قصة
                            </button>
                            <button
                                onClick={() => generateStoryScriptMutation.mutate()}
                                disabled={generateStoryScriptMutation.isPending}
                                className="h-10 rounded-xl border border-indigo-500/30 bg-indigo-500/15 text-sm text-indigo-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                {generateStoryScriptMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <ScrollText className="w-4 h-4" />}
                                Generate Story Script
                            </button>
                            <button
                                onClick={() => generateVideoPackageMutation.mutate()}
                                disabled={generateVideoPackageMutation.isPending}
                                className="h-10 rounded-xl border border-fuchsia-500/30 bg-fuchsia-500/15 text-sm text-fuchsia-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                {generateVideoPackageMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Film className="w-4 h-4" />}
                                Turn into Video
                            </button>
                            {linkedStoryId && (
                                <button
                                    onClick={() => setActiveDossierStoryId(linkedStoryId)}
                                    className="h-10 rounded-xl border border-cyan-500/30 bg-cyan-500/15 text-sm text-cyan-200 inline-flex items-center justify-center gap-2"
                                >
                                    <BookOpenText className="w-4 h-4" /> عرض ملف القصة
                                </button>
                            )}
                            <button
                                onClick={() => runWithGuide('open_editor', () => router.push(`/workspace-drafts?article_id=${article.id}`))}
                                className="h-10 rounded-xl border border-emerald-500/30 bg-emerald-500/15 text-sm text-emerald-200 flex items-center justify-center gap-2"
                            >
                                <FileCheck2 className="w-4 h-4" /> فتح في المحرر الذكي
                            </button>
                            <button
                                onClick={() => runWithGuide('handoff', () => handoffMutation.mutate())}
                                disabled={handoffMutation.isPending}
                                className="h-10 rounded-xl border border-cyan-500/30 bg-cyan-500/15 text-sm text-cyan-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                <Send className="w-4 h-4" />
                                {handoffMutation.isPending ? 'جاري الترشيح...' : 'ترشيح للتحرير'}
                            </button>
                            <button
                                onClick={() => runWithGuide('summarize', () => toolMutation.mutate('summarize'))}
                                disabled={toolMutation.isPending}
                                className="h-10 rounded-xl border border-violet-500/30 bg-violet-500/15 text-sm text-violet-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                <Sparkles className="w-4 h-4" /> تلخيص سريع
                            </button>
                            <button
                                onClick={() => runWithGuide('fact_check', () => toolMutation.mutate('fact_check'))}
                                disabled={toolMutation.isPending}
                                className="h-10 rounded-xl border border-amber-500/30 bg-amber-500/15 text-sm text-amber-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                <ShieldCheck className="w-4 h-4" /> تحقق أولي
                            </button>
                            <button
                                onClick={() => runWithGuide('translate', () => toolMutation.mutate('translate'))}
                                disabled={toolMutation.isPending}
                                className="h-10 rounded-xl border border-fuchsia-500/30 bg-fuchsia-500/15 text-sm text-fuchsia-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                <Languages className="w-4 h-4" /> ترجمة
                            </button>
                        </div>
                    </div>

                    <div className="rounded-2xl border border-indigo-500/30 bg-indigo-500/10 p-4 space-y-3">
                        <p className="text-sm font-semibold text-indigo-100 inline-flex items-center gap-2">
                            <CircleHelp className="w-4 h-4" /> نصيحة من الدستور
                        </p>
                        <p className="text-sm text-indigo-50 leading-7">{currentTip}</p>
                        <button
                            type="button"
                            onClick={() => setTipSeed((s) => s + 1)}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg bg-white/10 border border-white/20 text-white hover:bg-white/20"
                        >
                            <RotateCcw className="w-3 h-3" /> نصيحة أخرى
                        </button>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-2">
                        <div className="flex items-center justify-between">
                            <h3 className="text-sm font-semibold text-white">نتيجة الأداة</h3>
                            {toolOutput && (
                                <button
                                    className="text-xs text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1"
                                    onClick={() => runWithGuide('copy_output', () => navigator.clipboard.writeText(toolOutput))}
                                >
                                    <Clipboard className="w-3.5 h-3.5" /> نسخ
                                </button>
                            )}
                        </div>
                        {toolLabel && <p className="text-xs text-gray-400">{toolLabel}</p>}
                        <div className="rounded-xl border border-white/10 bg-black/20 p-3 max-h-[320px] overflow-auto">
                            <p className="text-sm text-gray-100 whitespace-pre-wrap leading-7">
                                {toolOutput || 'شغّل إحدى الأدوات لعرض نتيجة مباشرة هنا.'}
                            </p>
                        </div>
                    </div>
                </aside>
            </div>

            {guideOpen && (
                <NewsGuideModal
                    type={guideType}
                    action={guideAction}
                    onClose={closeGuide}
                    onConfirm={confirmGuide}
                />
            )}

            {storyPanelOpen && (
                <StorySuggestionPanel
                    suggestions={suggestions}
                    loading={suggestionsLoading}
                    onClose={() => setStoryPanelOpen(false)}
                    onLink={(storyId) => linkToStoryMutation.mutate(storyId)}
                    linking={linkToStoryMutation.isPending}
                />
            )}

            {activeDossierStoryId && (
                <StoryDossierDrawer
                    storyId={activeDossierStoryId}
                    onClose={() => setActiveDossierStoryId(null)}
                />
            )}
        </div>
    );
}

function NewsGuideModal({
    type,
    action,
    onClose,
    onConfirm,
}: {
    type: NewsGuideType;
    action: NewsActionId | null;
    onClose: () => void;
    onConfirm: () => void;
}) {
    return (
        <div className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" dir="rtl">
            <div className="w-full max-w-xl rounded-2xl border border-white/10 bg-gray-950 p-5 space-y-4">
                {type === 'welcome' ? (
                    <>
                        <h2 className="text-lg font-semibold text-white">دليل سريع لصفحة الخبر</h2>
                        <div className="text-sm text-gray-300 space-y-2">
                            <p>- استخدم الأزرار الجانبية لفحص الخبر بسرعة قبل التحرير الكامل.</p>
                            <p>- ابدأ عادةً بـ «تحقق أولي» ثم «تلخيص سريع» ثم افتح المحرر الذكي.</p>
                            <p>- أي مخرج من الأدوات يظهر في «نتيجة الأداة» ويمكن نسخه مباشرة.</p>
                        </div>
                    </>
                ) : (
                    <>
                        <h2 className="text-lg font-semibold text-white">{action ? NEWS_ACTION_HELP[action].title : 'شرح الأداة'}</h2>
                        <p className="text-sm text-gray-300">{action ? NEWS_ACTION_HELP[action].description : 'شرح غير متاح.'}</p>
                    </>
                )}

                <div className="flex items-center justify-end gap-2">
                    <button onClick={onClose} className="rounded-xl border border-white/20 px-4 py-2 text-sm text-gray-300">إغلاق</button>
                    <button onClick={onConfirm} className="rounded-xl bg-emerald-500/25 border border-emerald-400/40 px-4 py-2 text-sm text-emerald-100">
                        {type === 'welcome' ? 'فهمت، ابدأ' : 'فهمت، نفّذ'}
                    </button>
                </div>
            </div>
        </div>
    );
}

function StorySuggestionPanel({
    suggestions,
    loading,
    onClose,
    onLink,
    linking,
}: {
    suggestions: StorySuggestion[];
    loading: boolean;
    onClose: () => void;
    onLink: (storyId: number) => void;
    linking: boolean;
}) {
    return (
        <div className="fixed inset-0 z-[75] bg-black/70 backdrop-blur-sm flex justify-end" dir="rtl">
            <div className="w-full max-w-xl h-full overflow-y-auto border-l border-white/10 bg-slate-950 p-5 space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-white">اقتراحات ربط القصة</h3>
                    <button onClick={onClose} className="rounded-lg border border-white/20 px-3 py-1.5 text-xs text-slate-300">إغلاق</button>
                </div>

                {loading && <p className="text-sm text-slate-400">جاري تحليل القصص المناسبة...</p>}

                {!loading && suggestions.length === 0 && (
                    <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-sm text-slate-300">
                        لا توجد اقتراحات كافية حالياً. يمكنك إنشاء قصة جديدة مباشرة.
                    </div>
                )}

                <div className="space-y-2">
                    {suggestions.map((item) => (
                        <div key={item.story_id} className="rounded-xl border border-white/10 bg-slate-900/60 p-3 space-y-2">
                            <div className="flex items-center justify-between gap-2">
                                <div>
                                    <p className="text-xs text-cyan-300">{item.story_key}</p>
                                    <p className="text-sm text-white font-medium">{item.title}</p>
                                </div>
                                <span className="text-xs rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-emerald-200">
                                    Score: {item.score}
                                </span>
                            </div>
                            <p className="text-[11px] text-slate-400">
                                {item.reasons.join(' • ') || 'بدون تفاصيل إضافية'}
                            </p>
                            <button
                                onClick={() => onLink(item.story_id)}
                                disabled={linking}
                                className="w-full h-9 rounded-lg border border-sky-500/30 bg-sky-500/15 text-sm text-sky-200 disabled:opacity-60"
                            >
                                ربط الخبر بهذه القصة
                            </button>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

function StoryDossierDrawer({
    storyId,
    onClose,
}: {
    storyId: number;
    onClose: () => void;
}) {
    const { data, isLoading, error } = useQuery({
        queryKey: ['story-dossier-news-page', storyId],
        queryFn: () => storiesApi.dossier(storyId, { timeline_limit: 20 }),
    });
    const dossier: StoryDossierResponse | undefined = data?.data;

    return (
        <div className="fixed inset-0 z-[85] bg-black/70 backdrop-blur-sm flex justify-end" dir="rtl">
            <div className="w-full max-w-2xl h-full overflow-y-auto border-l border-white/10 bg-slate-950 p-5 space-y-4">
                <div className="flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-white">ملف القصة</h3>
                    <button onClick={onClose} className="rounded-lg border border-white/20 px-3 py-1.5 text-xs text-slate-300">إغلاق</button>
                </div>

                {isLoading && <p className="text-sm text-slate-400">جاري تحميل الملف...</p>}
                {error && <p className="text-sm text-red-300">تعذر تحميل ملف القصة.</p>}

                {dossier && (
                    <div className="space-y-4">
                        <div className="rounded-xl border border-white/10 bg-white/5 p-4">
                            <p className="text-xs text-cyan-300">{dossier.story.story_key}</p>
                            <h4 className="text-xl text-white font-semibold mt-1">{dossier.story.title}</h4>
                            <p className="text-xs text-slate-400 mt-2">
                                الحالة: {dossier.story.status} • آخر نشاط: {dossier.stats.last_activity_at ? formatRelativeTime(dossier.stats.last_activity_at) : 'غير متاح'}
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-xs">
                            <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-slate-200">العناصر: {dossier.stats.items_total}</div>
                            <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-slate-200">الأخبار: {dossier.stats.articles_count}</div>
                            <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-slate-200">المسودات: {dossier.stats.drafts_count}</div>
                            <div className="rounded-lg border border-white/10 bg-white/5 p-3 text-slate-200">الملاحظات: {dossier.highlights.notes_count}</div>
                        </div>

                        <div className="space-y-2">
                            <h5 className="text-sm font-semibold text-white">الخط الزمني</h5>
                            <div className="space-y-2">
                                {dossier.timeline.map((item) => (
                                    <div key={`${item.type}-${item.id}`} className="rounded-lg border border-white/10 bg-slate-900/60 p-3">
                                        <p className="text-xs text-cyan-300">{item.type === 'article' ? 'خبر' : 'مسودة'} #{item.id}</p>
                                        <p className="text-sm text-white mt-1">{item.title}</p>
                                        <p className="text-[11px] text-slate-400 mt-1">
                                            {item.source_name ? `${item.source_name} • ` : ''}
                                            {item.status || 'بدون حالة'}
                                        </p>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
