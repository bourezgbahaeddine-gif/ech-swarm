'use client';
/* eslint-disable @typescript-eslint/no-explicit-any, react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

import { Suspense, type ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import NextLink from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { EditorContent, useEditor } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import Highlight from '@tiptap/extension-highlight';
import {
    AlertTriangle,
    CheckCircle2,
    CircleHelp,
    Clock3,
    Loader2,
    Save,
    SearchCheck,
    ShieldCheck,
    Sparkles,
} from 'lucide-react';

import { editorialApi, msiApi, simApi } from '@/lib/api';
import { constitutionApi } from '@/lib/constitution-api';
import { cn, formatRelativeTime, truncate } from '@/lib/utils';

type SaveState = 'saved' | 'saving' | 'unsaved' | 'error';
type RightTab = 'evidence' | 'quality' | 'seo' | 'social' | 'context' | 'msi' | 'simulator';
type GuideType = 'welcome' | 'action';
type ActionId = 'quick_check' | 'verify' | 'improve' | 'headlines' | 'seo' | 'social' | 'quality' | 'publish_gate' | 'apply' | 'save' | 'manual_draft' | 'audience_test';

const TABS: Array<{ id: RightTab; label: string }> = [
    { id: 'evidence', label: 'التحقق والأدلة' },
    { id: 'quality', label: 'تقييم الجودة' },
    { id: 'seo', label: 'أدوات SEO' },
    { id: 'social', label: 'نسخ السوشيال' },
    { id: 'context', label: 'السياق والنسخ' },
    { id: 'msi', label: 'MSI السياقي' },
    { id: 'simulator', label: 'محاكي الجمهور' },
];

const HELP_KEY = 'smart_editor_help_seen_v1';
const ACTION_HELP_PREFIX = 'smart_editor_action_help_seen_v1_';

const ACTION_HELP: Record<ActionId, { title: string; description: string }> = {
    quick_check: { title: 'زر الفحص السريع', description: 'يشغل التحقق + الجودة + بوابة النشر دفعة واحدة ليعطيك حالة جاهزية سريعة.' },
    verify: { title: 'زر التحقق', description: 'يستخرج الادعاءات ويعرض درجة الثقة قبل النشر.' },
    improve: { title: 'زر التحسين', description: 'يولد اقتراح تحسين كفرق (Diff) قابل للقبول أو الرفض.' },
    headlines: { title: 'زر العناوين', description: 'يولد 5 عناوين متنوعة للاستخدام التحريري.' },
    seo: { title: 'زر SEO', description: 'يولد عنوان SEO والوصف والكلمات المفتاحية والوسوم.' },
    social: { title: 'زر السوشيال', description: 'ينشئ نسخ Facebook وX وPush والتنبيه العاجل.' },
    quality: { title: 'زر الجودة', description: 'يقيم وضوح وبنية وحياد النص مع توصيات عملية.' },
    publish_gate: { title: 'زر بوابة النشر', description: 'يفحص الجاهزية النهائية ويمنع النشر عند وجود موانع.' },
    apply: { title: 'زر إرسال الاعتماد', description: 'يرسل النسخة النهائية إلى رئيس التحرير بعد فحص وكيل السياسة التحريرية.' },
    save: { title: 'زر الحفظ', description: 'يحفظ التعديلات فورياً ويحدّث النسخ.' },
    manual_draft: { title: 'زر مسودة جديدة', description: 'ينشئ مسودة خاصة لموضوع غير وارد من المصادر الآلية.' },
    audience_test: { title: 'زر محاكي الجمهور', description: 'يحاكي ردود الجمهور المتوقعة ويعرض مخاطر المحتوى وقابلية الانتشار قبل الاعتماد.' },
};

const STAGE_LABELS: Record<string, string> = {
    FACT_CHECK: 'التحقق من الادعاءات',
    SEO_TECH: 'التدقيق التقني',
    READABILITY: 'قابلية القراءة',
    QUALITY_SCORE: 'جودة التحرير',
};

const METRIC_LABELS: Record<string, string> = {
    clarity: 'الوضوح',
    structure: 'البنية',
    inverted_pyramid: 'الهرم المقلوب',
    redundancy: 'عدم التكرار',
    length_suitability: 'ملاءمة الطول',
    tone_neutrality: 'الحياد',
    sources_attribution: 'الإسناد للمصادر',
    word_count: 'عدد الكلمات',
};

function cleanText(value: string): string {
    if (!value) return '';
    return value
        .replace(/```[\s\S]*?```/g, '')
        .replace(/^\s*(حسنًا|حسنا|ملاحظات|ملاحظة|يمكنني|آمل|إذا كان لديك)\b.*$/gim, '')
        .replace(/^\s*(note|notes|explanation|comment)\s*:\s*.*$/gim, '')
        .replace(/\[[^\]\n]{2,120}\]/g, '')
        .replace(/\?{3,}/g, '')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

function htmlToReadableText(value: string): string {
    if (!value) return '';
    if (typeof window !== 'undefined') {
        const parsed = new window.DOMParser().parseFromString(value, 'text/html');
        return cleanText(parsed.body.textContent || '');
    }
    return cleanText(value.replace(/<[^>]+>/g, ' '));
}

function normalizeDiffOutput(value: string): string {
    if (!value) return '';
    const hasHtml = /<[^>]+>/.test(value);
    return hasHtml ? htmlToReadableText(value) : cleanText(value);
}

function normalizeForMatch(value: string): string {
    return cleanText(value || '')
        .replace(/[^\u0600-\u06FFa-zA-Z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase();
}

function entityMatchesContext(entity: string, contextText: string): boolean {
    const entityNorm = normalizeForMatch(entity);
    const contextNorm = normalizeForMatch(contextText);
    if (!entityNorm || !contextNorm) return false;
    const tokens = entityNorm.split(' ').filter((t) => t.length >= 3);
    if (!tokens.length) return false;
    return tokens.every((t) => contextNorm.includes(t));
}

function actionKey(action: ActionId): string {
    return `${ACTION_HELP_PREFIX}${action}`;
}

function WorkspaceDraftsPageContent() {
    const queryClient = useQueryClient();
    const search = useSearchParams();
    const articleId = search.get('article_id');
    const initialWork = search.get('work_id');
    const articleNumericId = useMemo(() => {
        if (!articleId) return null;
        const parsed = Number(articleId);
        return Number.isFinite(parsed) ? parsed : null;
    }, [articleId]);
    const autoCreateAttemptRef = useRef(false);

    const [workId, setWorkId] = useState<string | null>(initialWork || null);
    const [title, setTitle] = useState('');
    const [bodyHtml, setBodyHtml] = useState('');
    const [baseVersion, setBaseVersion] = useState(1);
    const [saveState, setSaveState] = useState<SaveState>('saved');
    const [activeTab, setActiveTab] = useState<RightTab>('evidence');
    const [err, setErr] = useState<string | null>(null);
    const [ok, setOk] = useState<string | null>(null);
    const [claims, setClaims] = useState<any[]>([]);
    const [quality, setQuality] = useState<any | null>(null);
    const [seoPack, setSeoPack] = useState<any | null>(null);
    const [social, setSocial] = useState<any | null>(null);
    const [simResult, setSimResult] = useState<any | null>(null);
    const [readiness, setReadiness] = useState<any | null>(null);
    const [headlines, setHeadlines] = useState<any[]>([]);
    const [suggestion, setSuggestion] = useState<any | null>(null);
    const [showTechnicalDiff, setShowTechnicalDiff] = useState(false);
    const [diffView, setDiffView] = useState('');
    const [cmpFrom, setCmpFrom] = useState<number | null>(null);
    const [cmpTo, setCmpTo] = useState<number | null>(null);
    const [newDraftOpen, setNewDraftOpen] = useState(false);
    const [manualTitle, setManualTitle] = useState('');
    const [manualBody, setManualBody] = useState('');
    const [manualSummary, setManualSummary] = useState('');
    const [manualCategory, setManualCategory] = useState('local_algeria');
    const [manualUrgency, setManualUrgency] = useState('medium');

    const [guideOpen, setGuideOpen] = useState(false);
    const [guideType, setGuideType] = useState<GuideType>('welcome');
    const [guideAction, setGuideAction] = useState<ActionId | null>(null);
    const pendingActionRef = useRef<null | (() => void)>(null);

    const { data: listData, isLoading: listLoading } = useQuery({
        queryKey: ['smart-editor-list', articleId],
        queryFn: () => editorialApi.workspaceDrafts({ status: 'draft', limit: 200, article_id: articleNumericId || undefined }),
    });
    const drafts = listData?.data || [];

    useEffect(() => {
        if (typeof window === 'undefined') return;
        if (window.localStorage.getItem(HELP_KEY)) return;
        setGuideType('welcome');
        setGuideAction(null);
        setGuideOpen(true);
    }, []);

    useEffect(() => {
        autoCreateAttemptRef.current = false;
    }, [articleNumericId]);

    useEffect(() => {
        if (workId || drafts.length === 0) return;
        setWorkId(initialWork || drafts[0].work_id);
    }, [workId, drafts, initialWork]);

    const { data: contextData, isLoading: contextLoading } = useQuery({
        queryKey: ['smart-editor-context', workId],
        queryFn: () => editorialApi.smartContext(workId!),
        enabled: !!workId,
    });
    const { data: versionsData } = useQuery({
        queryKey: ['smart-editor-versions', workId],
        queryFn: () => editorialApi.draftVersions(workId!),
        enabled: !!workId,
    });
    const { data: constitutionTipsData } = useQuery({
        queryKey: ['smart-editor-constitution-tips'],
        queryFn: () => constitutionApi.tips(),
    });

    const context = contextData?.data;
    const versions = versionsData?.data || [];
    const constitutionTips = constitutionTipsData?.data?.tips || [];
    const { data: msiTopDailyData } = useQuery({
        queryKey: ['smart-editor-msi-top-daily'],
        queryFn: () => msiApi.top({ mode: 'daily', limit: 10 }),
    });
    const { data: msiTopWeeklyData } = useQuery({
        queryKey: ['smart-editor-msi-top-weekly'],
        queryFn: () => msiApi.top({ mode: 'weekly', limit: 10 }),
    });
    const msiTopDaily = msiTopDailyData?.data?.items || [];
    const msiTopWeekly = msiTopWeeklyData?.data?.items || [];
    const msiContextText = useMemo(
        () =>
            `${context?.draft?.title || ''} ${context?.article?.title_ar || ''} ${context?.article?.original_title || ''}`,
        [context?.draft?.title, context?.article?.title_ar, context?.article?.original_title]
    );
    const msiContextHit = useMemo(() => {
        const all = [...msiTopDaily, ...msiTopWeekly];
        return all.find((item: any) => entityMatchesContext(item?.entity || '', msiContextText)) || null;
    }, [msiTopDaily, msiTopWeekly, msiContextText]);

    const editor = useEditor({
        extensions: [
            StarterKit.configure({ link: false }),
            Highlight,
            Link.configure({ openOnClick: false }),
            Placeholder.configure({ placeholder: 'ابدأ كتابة الخبر هنا...' }),
        ],
        content: '',
        immediatelyRender: false,
        editorProps: {
            attributes: { class: 'smart-editor-content min-h-[520px] p-6 text-[15px] leading-8 text-white focus:outline-none', dir: 'rtl' },
        },
        onUpdate({ editor: ed }) {
            setBodyHtml(ed.getHTML());
            setSaveState('unsaved');
        },
    });

    useEffect(() => {
        const draft = context?.draft;
        if (!draft || !editor) return;
        setTitle(cleanText(draft.title || ''));
        setBodyHtml(draft.body || '');
        editor.commands.setContent(draft.body || '<p></p>', { emitUpdate: false });
        setBaseVersion(draft.version || 1);
        setSaveState('saved');
        setSuggestion(null);
        setSimResult(null);
    }, [context?.draft?.id, editor]);

    useEffect(() => {
        if (!versions.length) return;
        if (!cmpTo) setCmpTo(versions[0].version);
        if (!cmpFrom && versions.length > 1) setCmpFrom(versions[1].version);
    }, [versions, cmpFrom, cmpTo]);

    const autosave = useMutation({
        mutationFn: () => editorialApi.autosaveWorkspaceDraft(workId!, { title, body: bodyHtml, based_on_version: baseVersion, note: 'autosave_smart_editor' }),
        onSuccess: (res) => {
            setSaveState('saved');
            setBaseVersion(res.data?.draft?.version || baseVersion);
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
        },
        onError: (e: any) => { setSaveState('error'); setErr(e?.response?.data?.detail || 'تعذر الحفظ التلقائي'); },
    });

    useEffect(() => {
        if (!workId || saveState !== 'unsaved') return;
        const t = window.setTimeout(() => { setSaveState('saving'); autosave.mutate(); }, 1200);
        return () => window.clearTimeout(t);
    }, [saveState, workId, title, bodyHtml]);

    const rewrite = useMutation({ mutationFn: () => editorialApi.aiRewriteSuggestion(workId!, { mode: 'formal' }), onSuccess: (r) => { setSuggestion(r.data?.suggestion || null); setActiveTab('quality'); } });
    const applySuggestion = useMutation({
        mutationFn: () => editorialApi.applyAiSuggestion(workId!, { title: suggestion?.title, body: suggestion?.body_html || '', based_on_version: baseVersion, suggestion_tool: 'rewrite' }),
        onSuccess: (r) => {
            const d = r.data?.draft;
            if (d && editor) {
                setTitle(cleanText(d.title || ''));
                setBodyHtml(d.body || '');
                editor.commands.setContent(d.body || '<p></p>', { emitUpdate: false });
                setBaseVersion(d.version);
            }
            setSuggestion(null);
            setShowTechnicalDiff(false);
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
        },
    });

    const runVerifier = useMutation({ mutationFn: () => editorialApi.verifyClaims(workId!, 0.7), onSuccess: (r) => { setClaims(r.data?.claims || []); setActiveTab('evidence'); } });
    const runQuality = useMutation({ mutationFn: () => editorialApi.qualityScore(workId!), onSuccess: (r) => { setQuality(r.data); setActiveTab('quality'); } });
    const runSeo = useMutation({ mutationFn: () => editorialApi.aiSeoSuggestion(workId!), onSuccess: (r) => { setSeoPack(r.data); setActiveTab('seo'); } });
    const runSocial = useMutation({ mutationFn: () => editorialApi.aiSocialVariants(workId!), onSuccess: (r) => { setSocial(r.data?.variants || null); setActiveTab('social'); } });
    const runHeadlines = useMutation({ mutationFn: () => editorialApi.aiHeadlineSuggestion(workId!, 5), onSuccess: (r) => { setHeadlines(r.data?.headlines || []); setActiveTab('seo'); } });
    const runReadiness = useMutation({ mutationFn: () => editorialApi.publishReadiness(workId!), onSuccess: (r) => { setReadiness(r.data); setActiveTab('quality'); } });
    const runQuickCheck = useMutation({
        mutationFn: async () => {
            const verifyRes = await editorialApi.verifyClaims(workId!, 0.7);
            const qualityRes = await editorialApi.qualityScore(workId!);
            const readinessRes = await editorialApi.publishReadiness(workId!);
            return { verifyRes, qualityRes, readinessRes };
        },
        onSuccess: ({ verifyRes, qualityRes, readinessRes }) => {
            setClaims(verifyRes.data?.claims || []);
            setQuality(qualityRes.data);
            setReadiness(readinessRes.data);
            setActiveTab('quality');
            setErr(null);
            setOk('اكتمل الفحص السريع: تم تحديث التحقق والجودة وحالة الجاهزية.');
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || 'تعذر تنفيذ الفحص السريع'),
    });
    const runAudienceSimulation = useMutation({
        mutationFn: async () => {
            const headline = cleanText(title || context?.article?.title_ar || context?.article?.original_title || '');
            const excerpt = htmlToReadableText(bodyHtml || context?.draft?.body || '').slice(0, 1800);
            if (!headline || headline.length < 6) {
                throw new Error('العنوان غير كافٍ لتشغيل محاكي الجمهور.');
            }
            const runRes = await simApi.run({
                headline,
                excerpt,
                platform: 'facebook',
                mode: 'fast',
                article_id: context?.article?.id,
                draft_id: context?.draft?.id,
            });
            const runId = runRes.data.run_id;
            for (let i = 0; i < 30; i += 1) {
                const statusRes = await simApi.runStatus(runId);
                const status = statusRes.data?.status;
                if (status === 'completed') {
                    const resultRes = await simApi.result(runId);
                    return { runId, result: resultRes.data };
                }
                if (status === 'failed') {
                    throw new Error(statusRes.data?.error || 'فشل تشغيل محاكي الجمهور.');
                }
                await new Promise((resolve) => setTimeout(resolve, 1500));
            }
            throw new Error('انتهت مهلة انتظار نتيجة محاكي الجمهور.');
        },
        onSuccess: ({ runId, result }) => {
            setSimResult({ ...result, run_id: runId });
            setActiveTab('simulator');
            setErr(null);
            setOk('تم تحديث نتائج محاكي الجمهور بنجاح.');
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تشغيل محاكي الجمهور'),
    });
    const runDiff = useMutation({ mutationFn: () => editorialApi.draftDiff(workId!, cmpFrom!, cmpTo!), onSuccess: (r) => setDiffView(r.data?.diff || '') });
    const restoreVersion = useMutation({ mutationFn: (v: number) => editorialApi.restoreWorkspaceDraftVersion(workId!, v), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] }); queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] }); } });
    const applyToArticle = useMutation({
        mutationFn: () => editorialApi.submitWorkspaceDraftForChief(workId!),
        onSuccess: (res) => {
            const data = res.data || {};
            if (data?.status_message) {
                setOk(`تم الإرسال: ${data.status_message}`);
            } else {
                setOk('تم إرسال النسخة إلى رئيس التحرير.');
            }
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
        },
    });
    const createManualDraft = useMutation({
        mutationFn: () =>
            editorialApi.createManualWorkspaceDraft({
                title: manualTitle,
                body: manualBody,
                summary: manualSummary || undefined,
                category: manualCategory,
                urgency: manualUrgency,
                source_action: 'manual_topic',
            }),
        onSuccess: (res) => {
            const nextWorkId = res.data?.work_id;
            if (!nextWorkId) return;
            setWorkId(nextWorkId);
            setOk('تم إنشاء مسودة جديدة وفتحها في المحرر.');
            setErr(null);
            setNewDraftOpen(false);
            setManualTitle('');
            setManualBody('');
            setManualSummary('');
            queryClient.invalidateQueries({ queryKey: ['smart-editor-list'] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', nextWorkId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', nextWorkId] });
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || 'تعذر إنشاء المسودة الجديدة'),
    });
    const createDraftFromArticle = useMutation({
        mutationFn: () => editorialApi.handoff(articleNumericId!),
        onSuccess: (res) => {
            const nextWorkId = res.data?.work_id;
            if (!nextWorkId) {
                setErr('تم ترشيح الخبر ولكن لم يتم إنشاء Work ID. أعد المحاولة.');
                return;
            }
            setWorkId(nextWorkId);
            setErr(null);
            setOk('تم إنشاء المسودة من الخبر وفتحها في المحرر.');
            queryClient.invalidateQueries({ queryKey: ['smart-editor-list', articleId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', nextWorkId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', nextWorkId] });
        },
        onError: (e: any) => {
            setErr(e?.response?.data?.detail || 'تعذر إنشاء مسودة الخبر. حاول مرة أخرى.');
        },
    });

    useEffect(() => {
        if (!articleNumericId || listLoading || workId || drafts.length > 0) return;
        if (autoCreateAttemptRef.current) return;
        autoCreateAttemptRef.current = true;
        createDraftFromArticle.mutate();
    }, [articleNumericId, listLoading, workId, drafts.length, createDraftFromArticle]);

    const saveNode = useMemo(() => {
        if (saveState === 'saved') return <span className="text-emerald-300 flex items-center gap-1"><CheckCircle2 className="w-4 h-4" />محفوظ</span>;
        if (saveState === 'saving') return <span className="text-sky-300 flex items-center gap-1"><Loader2 className="w-4 h-4 animate-spin" />جاري الحفظ...</span>;
        if (saveState === 'unsaved') return <span className="text-amber-300 flex items-center gap-1"><Clock3 className="w-4 h-4" />غير محفوظ</span>;
        return <span className="text-red-300 flex items-center gap-1"><AlertTriangle className="w-4 h-4" />خطأ في الحفظ</span>;
    }, [saveState]);

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

    function runWithGuide(action: ActionId, callback: () => void) {
        setErr(null);
        setOk(null);
        if (typeof window === 'undefined') return callback();
        if (window.localStorage.getItem(actionKey(action))) return callback();
        pendingActionRef.current = callback;
        setGuideType('action');
        setGuideAction(action);
        setGuideOpen(true);
    }

    function confirmGuide() {
        if (typeof window !== 'undefined') {
            if (guideType === 'welcome') window.localStorage.setItem(HELP_KEY, '1');
            if (guideType === 'action' && guideAction) window.localStorage.setItem(actionKey(guideAction), '1');
        }
        const next = pendingActionRef.current;
        closeGuide();
        if (next) next();
    }

    if (listLoading) return <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 text-center text-gray-300">جاري تحميل المسودات...</div>;
    if (!drafts.length) {
        return (
            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 space-y-4" dir="rtl">
                <h2 className="text-lg text-white font-semibold">لا توجد مسودة جاهزة الآن</h2>
                <p className="text-sm text-gray-300">
                    {articleNumericId
                        ? 'هذا الخبر لا يملك مسودة بعد. يمكنك إنشاء مسودة فورية من الخبر الحالي.'
                        : 'ابدأ بإنشاء مسودة جديدة لموضوعك أو افتح خبرًا من صفحة الأخبار.'}
                </p>
                <div className="flex flex-wrap gap-2">
                    {articleNumericId && (
                        <button
                            onClick={() => createDraftFromArticle.mutate()}
                            disabled={createDraftFromArticle.isPending}
                            className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200 disabled:opacity-60"
                        >
                            {createDraftFromArticle.isPending ? 'جاري إنشاء المسودة...' : 'إنشاء مسودة من الخبر'}
                        </button>
                    )}
                    <button
                        onClick={() => setNewDraftOpen(true)}
                        className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-200"
                    >
                        إنشاء مسودة موضوع خاص
                    </button>
                    <NextLink
                        href="/news"
                        className="rounded-xl border border-white/20 bg-white/5 px-4 py-2 text-sm text-gray-200 hover:text-white"
                    >
                        العودة إلى الأخبار
                    </NextLink>
                </div>
                {err && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{err}</div>}
                {newDraftOpen && (
                    <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                        <input
                            value={manualTitle}
                            onChange={(e) => setManualTitle(cleanText(e.target.value))}
                            className="w-full rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="عنوان الموضوع"
                        />
                        <textarea
                            value={manualBody}
                            onChange={(e) => setManualBody(e.target.value)}
                            className="w-full min-h-[160px] rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="متن المسودة الأولي"
                        />
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <select value={manualCategory} onChange={(e) => setManualCategory(e.target.value)} className="rounded-xl bg-white/10 px-3 py-2 text-sm text-gray-100">
                                <option value="local_algeria">محلي الجزائر</option>
                                <option value="politics">سياسة</option>
                                <option value="economy">اقتصاد</option>
                                <option value="society">مجتمع</option>
                                <option value="technology">تكنولوجيا</option>
                                <option value="international">دولي</option>
                                <option value="sports">رياضة</option>
                            </select>
                            <select value={manualUrgency} onChange={(e) => setManualUrgency(e.target.value)} className="rounded-xl bg-white/10 px-3 py-2 text-sm text-gray-100">
                                <option value="low">منخفض</option>
                                <option value="medium">متوسط</option>
                                <option value="high">عالٍ</option>
                                <option value="breaking">عاجل</option>
                            </select>
                        </div>
                        <div className="flex items-center justify-end gap-2">
                            <button
                                onClick={() => setNewDraftOpen(false)}
                                className="rounded-xl border border-white/20 px-4 py-2 text-sm text-gray-300"
                            >
                                إلغاء
                            </button>
                            <button
                                onClick={() => createManualDraft.mutate()}
                                disabled={createManualDraft.isPending || manualTitle.trim().length < 5 || manualBody.trim().length < 30}
                                className="rounded-xl bg-emerald-500/25 border border-emerald-400/40 px-4 py-2 text-sm text-emerald-100 disabled:opacity-50"
                            >
                                {createManualDraft.isPending ? 'جاري الإنشاء...' : 'إنشاء المسودة'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                        <h1 className="text-xl font-semibold text-white">المحرر الذكي لغرفة الشروق</h1>
                        <p className="text-xs text-gray-400">كتابة عربية احترافية + اقتراحات AI + تحقق + بوابة نشر</p>
                    </div>
                    <div className="flex items-center gap-3">
                        <NextLink
                            href="/services/multimedia"
                            className="inline-flex items-center gap-1 rounded-xl border border-violet-400/30 bg-violet-500/10 px-3 py-2 text-xs text-violet-200"
                        >
                            أدوات الوسائط
                        </NextLink>
                        <button
                            onClick={() => runWithGuide('manual_draft', () => setNewDraftOpen(true))}
                            className="inline-flex items-center gap-1 rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200"
                        >
                            مسودة جديدة
                        </button>
                        <button onClick={openWelcomeGuide} className="inline-flex items-center gap-1 rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200"><CircleHelp className="w-4 h-4" />دليل الاستخدام</button>
                        <div className="text-xs">{saveNode}</div>
                    </div>
                </div>

                <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2">
                    <div className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-100">
                        الذكاء الاصطناعي يقترح فقط. لا يوجد تعديل تلقائي للنص بدون موافقتك.
                    </div>
                    <div className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
                        كل تعديل يُحفظ كنسخة مستقلة ويمكن الرجوع له من تبويب «السياق والنسخ».
                    </div>
                </div>

                <div className="mt-3 flex flex-wrap gap-2">
                    <button
                        onClick={() => runWithGuide('quick_check', () => runQuickCheck.mutate())}
                        disabled={runQuickCheck.isPending}
                        className="px-3 py-2 rounded-xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-100 text-xs flex items-center gap-2 disabled:opacity-60"
                    >
                        <ShieldCheck className="w-4 h-4" />
                        فحص سريع
                    </button>
                    <button onClick={() => runWithGuide('verify', () => runVerifier.mutate())} className="px-3 py-2 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-200 text-xs flex items-center gap-2"><SearchCheck className="w-4 h-4" />تحقق</button>
                    <button onClick={() => runWithGuide('improve', () => rewrite.mutate())} className="px-3 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-200 text-xs flex items-center gap-2"><Sparkles className="w-4 h-4" />تحسين</button>
                    <button onClick={() => runWithGuide('headlines', () => runHeadlines.mutate())} className="px-3 py-2 rounded-xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-200 text-xs">عناوين</button>
                    <button onClick={() => runWithGuide('seo', () => runSeo.mutate())} className="px-3 py-2 rounded-xl bg-fuchsia-500/20 border border-fuchsia-500/30 text-fuchsia-200 text-xs">SEO</button>
                    <button onClick={() => runWithGuide('social', () => runSocial.mutate())} className="px-3 py-2 rounded-xl bg-sky-500/20 border border-sky-500/30 text-sky-200 text-xs">سوشيال</button>
                    <button onClick={() => runWithGuide('quality', () => runQuality.mutate())} className="px-3 py-2 rounded-xl bg-violet-500/20 border border-violet-500/30 text-violet-200 text-xs">جودة</button>
                    <button onClick={() => runWithGuide('audience_test', () => runAudienceSimulation.mutate())} className="px-3 py-2 rounded-xl bg-rose-500/20 border border-rose-500/30 text-rose-100 text-xs">
                        محاكي الجمهور
                    </button>
                    <button onClick={() => runWithGuide('publish_gate', () => runReadiness.mutate())} className="px-3 py-2 rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-200 text-xs">بوابة النشر</button>
                    <button onClick={() => runWithGuide('apply', () => applyToArticle.mutate())} className="px-3 py-2 rounded-xl bg-white/10 border border-white/15 text-gray-200 text-xs">إرسال لاعتماد رئيس التحرير</button>
                    <button onClick={() => runWithGuide('save', () => { setSaveState('saving'); autosave.mutate(); })} className="px-3 py-2 rounded-xl bg-white/10 border border-white/15 text-gray-200 text-xs flex items-center gap-2"><Save className="w-4 h-4" />حفظ</button>
                </div>

                {(err || ok) && <div className={cn('mt-3 rounded-xl px-3 py-2 text-xs', err ? 'bg-red-500/15 text-red-200 border border-red-500/30' : 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/30')}>{err || ok}</div>}
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
                <aside className="xl:col-span-3 space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                        <h2 className="text-sm text-white mb-2">المسودات</h2>
                        <div className="space-y-2 max-h-[260px] overflow-auto">
                            {drafts.map((d) => (
                                <button key={`${d.work_id}-${d.id}`} onClick={() => setWorkId(d.work_id)} className={cn('w-full text-right rounded-xl border p-2', workId === d.work_id ? 'border-emerald-400/40 bg-emerald-500/10' : 'border-white/10 bg-white/5')}>
                                    <div className="text-xs text-gray-200">{truncate(cleanText(d.title || 'بدون عنوان'), 58)}</div>
                                    <div className="text-[10px] text-gray-500 mt-1">{formatRelativeTime(d.updated_at)}</div>
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                        <h2 className="text-sm text-white mb-2">المصدر والبيانات</h2>
                        {contextLoading ? <p className="text-xs text-gray-500">جاري التحميل...</p> : (
                            <div className="text-xs space-y-2" dir="rtl">
                                <p className="text-gray-200">{cleanText(context?.article?.original_title || 'لا يوجد عنوان مصدر')}</p>
                                <p className="text-gray-400">{cleanText(context?.article?.router_rationale || 'لا يوجد تفسير توجيه')}</p>
                                <div className="rounded-xl border border-white/10 bg-black/25 p-2 text-gray-300 max-h-56 overflow-auto">{cleanText(context?.article?.summary || context?.article?.original_content || 'لا يوجد نص مصدر متاح')}</div>
                            </div>
                        )}
                    </div>
                </aside>

                <main className="xl:col-span-6 space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 overflow-hidden">
                        <div className="border-b border-white/10 p-4">
                            <input value={title} onChange={(e) => { setTitle(cleanText(e.target.value)); setSaveState('unsaved'); }} className="w-full rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white text-lg" dir="rtl" />
                            <p className="text-xs text-gray-500 mt-2">معرف العمل: {workId} • الإصدار v{baseVersion}</p>
                        </div>
                        {editor && (
                            <BubbleMenu editor={editor}>
                                <div className="rounded-xl bg-gray-950/95 border border-white/20 p-1 flex gap-1 text-xs">
                                    <button onClick={() => editor.chain().focus().toggleBold().run()} className="px-2 py-1 rounded bg-white/10">عريض</button>
                                    <button onClick={() => editor.chain().focus().toggleItalic().run()} className="px-2 py-1 rounded bg-white/10">مائل</button>
                                    <button onClick={() => editor.chain().focus().toggleHighlight().run()} className="px-2 py-1 rounded bg-white/10">تمييز</button>
                                </div>
                            </BubbleMenu>
                        )}
                        <EditorContent editor={editor} />
                    </div>

                    {suggestion && (
                        <div className="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4 space-y-2">
                            <h3 className="text-sm text-amber-200">اقتراح التحسين بصيغة واضحة</h3>
                            <div className="rounded-xl border border-amber-300/30 bg-black/25 p-3 text-xs text-amber-100 space-y-1" dir="rtl">
                                <p>العنوان المقترح: {cleanText(suggestion.title || title || 'بدون عنوان')}</p>
                                <p>التعديل: +{suggestion?.diff_stats?.added || 0} / -{suggestion?.diff_stats?.removed || 0}</p>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                                    <p className="text-[11px] text-gray-400 mb-1">قبل التحسين</p>
                                    <p className="text-sm leading-8 text-gray-100 whitespace-pre-wrap max-h-96 overflow-auto">
                                        {cleanText(suggestion?.preview?.before_text || htmlToReadableText(bodyHtml))}
                                    </p>
                                </div>
                                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-2">
                                    <p className="text-[11px] text-emerald-200 mb-1">بعد التحسين</p>
                                    <p className="text-sm leading-8 text-emerald-50 whitespace-pre-wrap max-h-96 overflow-auto">
                                        {cleanText(suggestion?.preview?.after_text || suggestion?.body_text || htmlToReadableText(suggestion?.body_html || ''))}
                                    </p>
                                </div>
                            </div>
                            <button
                                onClick={() => setShowTechnicalDiff((v) => !v)}
                                className="px-2 py-1 rounded-lg bg-white/10 text-gray-200 text-[11px]"
                            >
                                {showTechnicalDiff ? 'إخفاء الفرق التقني' : 'عرض الفرق التقني'}
                            </button>
                            {showTechnicalDiff && (
                                <pre className="max-h-56 overflow-auto text-xs text-amber-50 bg-black/25 rounded-xl p-2" dir="ltr">
                                    {normalizeDiffOutput(suggestion.diff || suggestion.diff_html || '') || 'لا يوجد فرق تقني'}
                                </pre>
                            )}
                            <div className="flex gap-2">
                                <button onClick={() => applySuggestion.mutate()} className="px-3 py-2 rounded-xl bg-emerald-500/30 text-emerald-100 text-xs">قبول كنسخة جديدة</button>
                                <button onClick={() => { setSuggestion(null); setShowTechnicalDiff(false); }} className="px-3 py-2 rounded-xl bg-white/10 text-gray-300 text-xs">رفض</button>
                            </div>
                        </div>
                    )}
                </main>

                <aside className="xl:col-span-3 space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                        <div className="flex flex-wrap gap-2">
                            {TABS.map((t) => (
                                <button key={t.id} onClick={() => setActiveTab(t.id)} className={cn('px-2 py-1 rounded-lg text-[11px]', activeTab === t.id ? 'bg-emerald-500/20 text-emerald-200' : 'bg-white/10 text-gray-300')}>{t.label}</button>
                            ))}
                        </div>
                    </div>

                    {activeTab === 'evidence' && (
                        <Panel title="نتائج التحقق">
                            {claims.length ? claims.map((c) => <Row key={c.id} text={cleanText(c.text || '')} danger={c.blocking} title={`${Math.round((c.confidence || 0) * 100)}% ثقة`} />) : <Empty text="اضغط زر «تحقق» لعرض الادعاءات." />}
                        </Panel>
                    )}

                    {activeTab === 'quality' && (
                        <Panel title="تقييم الجودة">
                            {quality ? (
                                <div className="space-y-2 text-xs text-gray-200">
                                    <div className="rounded-xl border border-white/10 bg-white/5 p-2">الدرجة الكلية: <span className="font-semibold">{quality.score ?? '-'}/100</span></div>
                                    {Object.entries(quality.metrics || {}).map(([k, v]) => (
                                        <div key={k} className="flex items-center justify-between rounded-lg bg-black/20 px-2 py-1 text-gray-300"><span>{METRIC_LABELS[k] || k}</span><span>{String(v)}</span></div>
                                    ))}
                                    {!!quality.actionable_fixes?.length && <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 p-2 text-amber-100">{quality.actionable_fixes.map((f: string, i: number) => <p key={`${f}-${i}`}>- {cleanText(f)}</p>)}</div>}
                                </div>
                            ) : <Empty text="اضغط زر «جودة» للحصول على التقرير." />}
                            {readiness && (
                                <div className="mt-2 space-y-2 text-xs">
                                    <div className={cn('rounded-xl border p-2', readiness.ready_for_publish ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100' : 'border-red-500/30 bg-red-500/10 text-red-100')}>
                                        {readiness.ready_for_publish ? 'جاهز للنشر بعد المراجعة البشرية.' : 'غير جاهز للنشر. توجد موانع.'}
                                    </div>
                                    {!readiness.ready_for_publish && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-2 text-red-100">{(readiness.blocking_reasons || []).map((r: string, i: number) => <p key={`${r}-${i}`}>- {cleanText(r)}</p>)}</div>}
                                    <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-gray-300 space-y-1">
                                        {Object.entries(readiness.reports || {}).map(([stage, report]: any) => (
                                            <div key={stage} className="flex items-center justify-between"><span>{STAGE_LABELS[stage] || stage}</span><span className={report?.passed ? 'text-emerald-300' : 'text-red-300'}>{report?.passed ? 'ناجح' : 'فشل'}</span></div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </Panel>
                    )}

                    {activeTab === 'seo' && (
                        <Panel title="نتائج SEO">
                            {seoPack ? (
                                <div className="space-y-2 text-xs text-gray-200">
                                    <InfoBlock label="عنوان SEO" value={seoPack.seo_title} />
                                    <InfoBlock label="الوصف التعريفي" value={seoPack.meta_description} />
                                    <InfoBlock label="العبارة المفتاحية الرئيسية" value={seoPack.focus_keyphrase} />
                                    <InfoBlock label="عبارات مفتاحية ثانوية" value={(seoPack.secondary_keyphrases || []).join('، ')} />
                                    <InfoBlock label="الكلمات المفتاحية" value={(seoPack.keywords || []).join('، ')} />
                                    <InfoBlock label="الوسوم" value={(seoPack.tags || []).join('، ')} />
                                    <InfoBlock label="Slug" value={seoPack.slug} />
                                    <InfoBlock label="OG Title" value={seoPack.og_title} />
                                    <InfoBlock label="OG Description" value={seoPack.og_description} />
                                    <InfoBlock label="Twitter Title" value={seoPack.twitter_title} />
                                    <InfoBlock label="Twitter Description" value={seoPack.twitter_description} />
                                    <div className={cn(
                                        'rounded-lg border p-2 text-[11px]',
                                        seoPack?.yoast?.meta_ok && seoPack?.yoast?.title_ok
                                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                                            : 'border-amber-500/30 bg-amber-500/10 text-amber-100'
                                    )}>
                                        <p>جاهزية Yoast:</p>
                                        <p>- طول Meta: {seoPack?.yoast?.meta_length ?? 0} (المطلوب 140-155)</p>
                                        <p>- طول SEO Title: {seoPack?.yoast?.title_length ?? 0} (الموصى به 40-60)</p>
                                    </div>
                                </div>
                            ) : <Empty text="اضغط زر «SEO» لاستخراج المقترحات." />}
                            {!!headlines.length && <div className="mt-2 rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-200"><p className="text-gray-400 mb-1">العناوين المقترحة</p>{headlines.map((h: any, i: number) => <p key={`${h?.label || 'h'}-${i}`}>- {cleanText(h?.headline || '')}</p>)}</div>}
                        </Panel>
                    )}

                    {activeTab === 'social' && (
                        <Panel title="نسخ السوشيال">
                            {social ? (
                                <div className="space-y-2 text-xs text-gray-200">
                                    <InfoBlock label="فيسبوك" value={social.facebook} />
                                    <InfoBlock label="X" value={social.x} />
                                    <InfoBlock label="Push" value={social.push} />
                                    <InfoBlock label="ملخص 120 كلمة" value={social.summary_120} />
                                    <InfoBlock label="تنبيه عاجل" value={social.breaking_alert} />
                                </div>
                            ) : <Empty text="اضغط زر «سوشيال» لإنشاء النسخ." />}
                        </Panel>
                    )}

                    {activeTab === 'msi' && (
                        <Panel title="MSI السياقي">
                            {msiContextHit ? (
                                <div className={cn('rounded-xl border p-2 text-xs', Number(msiContextHit.msi || 100) < 60 ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-amber-500/30 bg-amber-500/10 text-amber-100')}>
                                    <p className="font-semibold mb-1">تنبيه سياقي مرتبط بالكيان: {cleanText(msiContextHit.entity || '')}</p>
                                    <p>المؤشر الحالي: {Number(msiContextHit.msi || 0).toFixed(1)} / 100</p>
                                    <p>التصنيف: {cleanText(msiContextHit.level || '-')}</p>
                                    <p className="mt-1 text-[11px] opacity-90">عند انخفاض المؤشر، شدّد على التحقق من الادعاءات والمصادر قبل الإرسال النهائي.</p>
                                </div>
                            ) : (
                                <Empty text="لا يوجد تطابق MSI مباشر مع موضوع المسودة الحالية." />
                            )}
                            <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-300 mt-2 space-y-1">
                                <p className="text-gray-400 mb-1">الأكثر اضطراباً اليوم</p>
                                {(msiTopDaily || []).slice(0, 5).map((item: any) => (
                                    <div key={`msi-d-${item.profile_id}-${item.entity}-${item.period_end}`} className="flex items-center justify-between">
                                        <span className="line-clamp-1">{cleanText(item.entity || '-')}</span>
                                        <span className="text-red-300">{Number(item.msi || 0).toFixed(1)}</span>
                                    </div>
                                ))}
                            </div>
                            <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-300 space-y-1">
                                <p className="text-gray-400 mb-1">الأكثر اضطراباً أسبوعياً</p>
                                {(msiTopWeekly || []).slice(0, 5).map((item: any) => (
                                    <div key={`msi-w-${item.profile_id}-${item.entity}-${item.period_end}`} className="flex items-center justify-between">
                                        <span className="line-clamp-1">{cleanText(item.entity || '-')}</span>
                                        <span className="text-orange-300">{Number(item.msi || 0).toFixed(1)}</span>
                                    </div>
                                ))}
                            </div>
                        </Panel>
                    )}

                    {activeTab === 'simulator' && (
                        <Panel title="محاكي الجمهور">
                            {simResult ? (
                                <div className="space-y-2 text-xs text-gray-200">
                                    <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                                        <p>مخاطر المحتوى: <span className="font-semibold text-red-200">{Number(simResult.risk_score || 0).toFixed(1)}/10</span></p>
                                        <p>قابلية الانتشار: <span className="font-semibold text-cyan-200">{Number(simResult.virality_score || 0).toFixed(1)}/10</span></p>
                                        <p>تصنيف الحوكمة: <span className="font-semibold text-amber-200">{cleanText(simResult.policy_level || '-')}</span></p>
                                        <p>موثوقية القياس: <span className="font-semibold text-gray-100">{Number(simResult.confidence_score || 0).toFixed(1)}%</span></p>
                                    </div>
                                    <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                                        <p className="text-gray-400 mb-1">ردود الشخصيات</p>
                                        {(simResult.reactions || []).map((rx: any, idx: number) => (
                                            <p key={`${rx.persona_id || 'persona'}-${idx}`}>
                                                - {cleanText(rx.persona_label || rx.persona_id || 'شخصية')}: {cleanText(rx.comment || '')}
                                            </p>
                                        ))}
                                    </div>
                                    <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                                        <p className="text-gray-400 mb-1">نصائح التحرير</p>
                                        <p>{cleanText(simResult?.advice?.summary || '') || '—'}</p>
                                        {(simResult?.advice?.improvements || []).map((fix: string, idx: number) => (
                                            <p key={`${fix}-${idx}`}>- {cleanText(fix)}</p>
                                        ))}
                                    </div>
                                </div>
                            ) : (
                                <Empty text="اضغط زر «محاكي الجمهور» لتقييم العنوان قبل الاعتماد." />
                            )}
                        </Panel>
                    )}

                    {activeTab === 'context' && (
                        <Panel title="السياق والنسخ">
                            <div className="space-y-1 max-h-32 overflow-auto">
                                {versions.map((v) => <button key={v.id} onClick={() => restoreVersion.mutate(v.version)} className="w-full text-right rounded bg-white/5 px-2 py-1 text-xs text-gray-200">الإصدار v{v.version} • {v.change_origin || 'يدوي'}</button>)}
                            </div>
                            <div className="flex gap-2 mt-2">
                                <select value={cmpFrom || ''} onChange={(e) => setCmpFrom(Number(e.target.value))} className="flex-1 bg-white/10 rounded px-2 py-1 text-xs">{versions.map((v) => <option key={`f-${v.id}`} value={v.version}>من v{v.version}</option>)}</select>
                                <select value={cmpTo || ''} onChange={(e) => setCmpTo(Number(e.target.value))} className="flex-1 bg-white/10 rounded px-2 py-1 text-xs">{versions.map((v) => <option key={`t-${v.id}`} value={v.version}>إلى v{v.version}</option>)}</select>
                                <button onClick={() => runDiff.mutate()} className="px-2 py-1 rounded bg-white/10 text-xs">فرق</button>
                            </div>
                            <pre className="max-h-36 overflow-auto text-[11px] text-gray-200 whitespace-pre-wrap mt-2" dir="ltr">{diffView || 'لا يوجد فرق معروض بعد.'}</pre>
                            <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-300"><p className="text-gray-400 mb-1">الخط الزمني المرتبط</p>{(context?.story_context?.timeline || []).slice(0, 5).map((item: any) => <p key={item.id}>- {cleanText(item.title || 'بدون عنوان')}</p>)}</div>
                            <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-2 text-xs text-cyan-100 space-y-1">
                                <p className="text-cyan-200">تلميحات الدستور أثناء التحرير</p>
                                {(constitutionTips || []).slice(0, 4).map((tip: string, idx: number) => (
                                    <p key={`${tip}-${idx}`}>- {cleanText(tip)}</p>
                                ))}
                            </div>
                        </Panel>
                    )}
                </aside>
            </div>

            {newDraftOpen && (
                <div className="fixed inset-0 z-[82] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-gray-950 p-5 space-y-4" dir="rtl">
                        <h2 className="text-lg text-white font-semibold">إنشاء مسودة جديدة لموضوع خاص</h2>
                        <p className="text-xs text-gray-400">استخدم هذا النموذج عندما لا يكون الموضوع واردًا من مصادر النظام.</p>
                        <input
                            value={manualTitle}
                            onChange={(e) => setManualTitle(cleanText(e.target.value))}
                            className="w-full rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="عنوان الموضوع"
                        />
                        <textarea
                            value={manualSummary}
                            onChange={(e) => setManualSummary(cleanText(e.target.value))}
                            className="w-full min-h-[70px] rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="ملخص اختياري"
                        />
                        <textarea
                            value={manualBody}
                            onChange={(e) => setManualBody(e.target.value)}
                            className="w-full min-h-[220px] rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="متن المسودة الأولي"
                        />
                        <div className="grid grid-cols-2 gap-2">
                            <select value={manualCategory} onChange={(e) => setManualCategory(e.target.value)} className="rounded-xl bg-white/10 px-3 py-2 text-sm text-gray-100">
                                <option value="local_algeria">محلي الجزائر</option>
                                <option value="politics">سياسة</option>
                                <option value="economy">اقتصاد</option>
                                <option value="society">مجتمع</option>
                                <option value="technology">تكنولوجيا</option>
                                <option value="international">دولي</option>
                                <option value="sports">رياضة</option>
                            </select>
                            <select value={manualUrgency} onChange={(e) => setManualUrgency(e.target.value)} className="rounded-xl bg-white/10 px-3 py-2 text-sm text-gray-100">
                                <option value="low">منخفض</option>
                                <option value="medium">متوسط</option>
                                <option value="high">عالٍ</option>
                                <option value="breaking">عاجل</option>
                            </select>
                        </div>
                        <div className="flex items-center justify-end gap-2">
                            <button
                                onClick={() => setNewDraftOpen(false)}
                                className="rounded-xl border border-white/20 px-4 py-2 text-sm text-gray-300"
                            >
                                إلغاء
                            </button>
                            <button
                                onClick={() => createManualDraft.mutate()}
                                disabled={createManualDraft.isPending || manualTitle.trim().length < 5 || manualBody.trim().length < 30}
                                className="rounded-xl bg-emerald-500/25 border border-emerald-400/40 px-4 py-2 text-sm text-emerald-100 disabled:opacity-50"
                            >
                                {createManualDraft.isPending ? 'جاري الإنشاء...' : 'إنشاء المسودة'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {guideOpen && <GuideModal type={guideType} action={guideAction} onClose={closeGuide} onConfirm={confirmGuide} />}
        </div>
    );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
    return <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-2"><h3 className="text-sm text-white">{title}</h3>{children}</div>;
}

function Empty({ text }: { text: string }) {
    return <p className="text-xs text-gray-500">{text}</p>;
}

function Row({ title, text, danger }: { title: string; text: string; danger?: boolean }) {
    return <div className={cn('rounded-xl border p-2 text-xs', danger ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100')} dir="rtl"><p className="font-semibold mb-1">{title}</p><p>{text || 'بدون نص ادعاء'}</p></div>;
}

function InfoBlock({ label, value }: { label: string; value?: string }) {
    return <div className="rounded-xl border border-white/10 bg-black/20 p-2"><p className="text-gray-400 mb-1 text-xs">{label}</p><p className="text-xs text-gray-200">{cleanText(value || '-')}</p></div>;
}

function GuideModal({ type, action, onClose, onConfirm }: { type: GuideType; action: ActionId | null; onClose: () => void; onConfirm: () => void }) {
    return (
        <div className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="w-full max-w-2xl rounded-2xl border border-white/10 bg-gray-950 p-5 space-y-4" dir="rtl">
                {type === 'welcome' ? (
                    <>
                        <h2 className="text-lg font-semibold text-white">مرحباً بك في المحرر الذكي</h2>
                        <div className="text-sm text-gray-300 space-y-2">
                            <p>هذا دليل سريع للمحرر المبتدئ.</p>
                            <p>- النظام لا يكتب مكانك تلقائياً، كل شيء يأتي كمقترح قابل للقبول أو الرفض.</p>
                            <p>- ابدأ بكتابة النص في الوسط.</p>
                            <p>- استخدم «فحص سريع» للحصول على التحقق والجودة والجاهزية بضغطة واحدة.</p>
                            <p>- لا تعتمد النشر قبل زوال الموانع.</p>
                        </div>
                    </>
                ) : (
                    <>
                        <h2 className="text-lg font-semibold text-white">{action ? ACTION_HELP[action].title : 'شرح الزر'}</h2>
                        <p className="text-sm text-gray-300">{action ? ACTION_HELP[action].description : 'شرح غير متاح.'}</p>
                    </>
                )}

                <div className="flex items-center gap-2 justify-end">
                    <button onClick={onClose} className="rounded-xl border border-white/20 px-4 py-2 text-sm text-gray-300">إغلاق</button>
                    <button onClick={onConfirm} className="rounded-xl bg-emerald-500/25 border border-emerald-400/40 px-4 py-2 text-sm text-emerald-100">{type === 'welcome' ? 'فهمت، ابدأ' : 'فهمت، نفّذ'}</button>
                </div>
            </div>
        </div>
    );
}

export default function WorkspaceDraftsPage() {
    return (
        <Suspense
            fallback={
                <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 text-center text-gray-300">
                    Loading...
                </div>
            }
        >
            <WorkspaceDraftsPageContent />
        </Suspense>
    );
}

