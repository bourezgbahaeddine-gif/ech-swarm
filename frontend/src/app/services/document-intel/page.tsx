'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { useRouter, useSearchParams } from 'next/navigation';
import {
    AlertTriangle,
    CheckCircle2,
    FileSearch,
    FileUp,
    LibraryBig,
    Loader2,
    Newspaper,
    ScanSearch,
    Sparkles,
} from 'lucide-react';

import {
    documentIntelApi,
    type DocumentIntelActionLogItem,
    type DocumentIntelActionResult,
    type DocumentIntelClaim,
    type DocumentIntelEntity,
    type DocumentIntelExtractJobStatus,
    type DocumentIntelExtractResult,
    type DocumentIntelNewsItem,
    type DocumentIntelStoryAngle,
} from '@/lib/api';
import { useAuth } from '@/lib/auth';

const RUN_ROLES = new Set(['director', 'editor_chief', 'journalist', 'social_media', 'print_editor']);
const CREATE_DRAFT_ROLES = new Set(['director', 'editor_chief', 'journalist', 'print_editor']);

function apiError(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) return detail;
    }
    return fallback;
}

function documentTypeLabel(value?: string): string {
    switch ((value || '').toLowerCase()) {
        case 'official_gazette':
            return 'وثيقة رسمية / جريدة رسمية';
        case 'statement':
            return 'بيان أو تصريح';
        case 'scanned_document':
            return 'وثيقة ممسوحة ضوئيًا';
        case 'report':
        default:
            return 'تقرير أو وثيقة تحليلية';
    }
}

function claimTypeLabel(value?: string): string {
    switch ((value || '').toLowerCase()) {
        case 'legal':
            return 'ادعاء قانوني';
        case 'statistical':
            return 'ادعاء رقمي';
        case 'attribution':
            return 'نسبة / تصريح';
        case 'factual':
        default:
            return 'ادعاء وقائعي';
    }
}

function entityTypeLabel(value?: string): string {
    switch ((value || '').toLowerCase()) {
        case 'location':
            return 'مكان';
        case 'person':
            return 'شخص';
        case 'organization':
        default:
            return 'جهة / مؤسسة';
    }
}

function nextActionText(result: DocumentIntelExtractResult | null): string {
    if (!result) return 'ابدأ برفع وثيقة للحصول على خلاصة تحريرية أولية وإجراءات مقترحة.';
    if (result.news_candidates.length > 0) return 'افتح الوثيقة داخل المحرر الذكي لبدء صياغة الخبر مع أهم الأدلة والادعاءات.';
    if (result.claims.length > 0) return 'راجع الادعاءات المستخرجة وحدد ما يحتاج تحققًا قبل تحويله إلى خبر أو قصة.';
    if (result.story_angles.length > 0) return 'اختر الزاوية الأقرب لاهتمام غرفة الأخبار ثم حوّلها إلى قصة أو افتحها في المحرر.';
    if (result.data_points.length > 0) return 'استفد من النقاط الرقمية لبناء زاوية تفسيرية أو موجز سريع من الوثيقة.';
    return 'اقرأ الخلاصة أولًا ثم راجع نص الوثيقة لتحديد الزاوية الأنسب.';
}

function riskBadgeClass(value?: string): string {
    switch ((value || '').toLowerCase()) {
        case 'high':
            return 'border-red-500/30 bg-red-500/15 text-red-200';
        case 'medium':
            return 'border-amber-500/30 bg-amber-500/15 text-amber-200';
        default:
            return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-200';
    }
}

function actionLabel(action: string): string {
    switch (action) {
        case 'document_saved':
            return 'تم حفظ الوثيقة';
        case 'draft_created':
            return 'تم فتحها في المحرر';
        case 'story_created':
            return 'تم إنشاء قصة';
        case 'memory_saved':
            return 'تم الحفظ في الذاكرة';
        case 'factcheck_sent':
            return 'تم تجهيز التحقق';
        default:
            return action;
    }
}

function DocumentIntelPageContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canRun = RUN_ROLES.has(role);
    const canCreateDraft = CREATE_DRAFT_ROLES.has(role);

    const [file, setFile] = useState<File | null>(null);
    const [languageHint, setLanguageHint] = useState<'ar' | 'fr' | 'en' | 'auto'>('ar');
    const [maxNewsItems, setMaxNewsItems] = useState(8);
    const [maxDataPoints, setMaxDataPoints] = useState(30);
    const [error, setError] = useState<string | null>(null);
    const [actionNotice, setActionNotice] = useState<string | null>(null);
    const [createdWorkId, setCreatedWorkId] = useState<string | null>(null);
    const [jobId, setJobId] = useState<string | null>(null);
    const [showTechDetails, setShowTechDetails] = useState(false);

    const selectedDocumentId = useMemo(() => {
        const raw = searchParams.get('document_id');
        const parsed = raw ? Number(raw) : NaN;
        return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
    }, [searchParams]);

    const runExtract = useMutation({
        mutationFn: () =>
            documentIntelApi.submitExtractJob({
                file: file as File,
                language_hint: languageHint,
                max_news_items: maxNewsItems,
                max_data_points: maxDataPoints,
            }),
        onSuccess: (res) => {
            setJobId(res.data.job_id);
            setError(null);
            setActionNotice(null);
            setCreatedWorkId(null);
        },
        onError: (err) => setError(apiError(err, 'تعذر إرسال الوثيقة إلى التحليل.')),
    });

    const extractStatusQuery = useQuery({
        queryKey: ['document-intel-job', jobId],
        queryFn: () => documentIntelApi.getExtractJobStatus(jobId as string),
        enabled: !!jobId,
        refetchInterval: (q) => {
            const status = (q.state.data?.data as DocumentIntelExtractJobStatus | undefined)?.status;
            if (!status || status === 'completed' || status === 'failed' || status === 'dead_lettered') return false;
            return 1500;
        },
    });

    const storedDocumentQuery = useQuery({
        queryKey: ['document-intel-document', selectedDocumentId],
        queryFn: () => documentIntelApi.getDocument(selectedDocumentId as number),
        enabled: !!selectedDocumentId,
    });

    const statusPayload = extractStatusQuery.data?.data;
    const extractedResult: DocumentIntelExtractResult | null =
        statusPayload?.status === 'completed' && statusPayload.result ? statusPayload.result : null;
    const result: DocumentIntelExtractResult | null =
        (storedDocumentQuery.data?.data as DocumentIntelExtractResult | undefined) || extractedResult;
    const documentId = result?.document_id ?? null;

    const actionsQuery = useQuery({
        queryKey: ['document-intel-actions', documentId],
        queryFn: () => documentIntelApi.listActions(documentId as number),
        enabled: !!documentId,
    });

    useEffect(() => {
        if (!extractedResult?.document_id) return;
        const next = new URLSearchParams(searchParams.toString());
        next.set('document_id', String(extractedResult.document_id));
        router.replace(`/services/document-intel?${next.toString()}`);
    }, [extractedResult?.document_id, router, searchParams]);

    const overviewClaims = useMemo(() => (result?.claims || []).slice(0, 5), [result]);
    const overviewEntities = useMemo(() => (result?.entities || []).slice(0, 8), [result]);
    const overviewAngles = useMemo(() => (result?.story_angles || []).slice(0, 4), [result]);

    const refreshActionLog = () => {
        if (documentId) queryClient.invalidateQueries({ queryKey: ['document-intel-actions', documentId] });
    };

    const createDocumentDraftMutation = useMutation({
        mutationFn: (payload?: { angle_title?: string; claim_indexes?: number[] }) =>
            documentIntelApi.createDraft(documentId as number, {
                angle_title: payload?.angle_title,
                claim_indexes: payload?.claim_indexes,
                category: 'international',
                urgency: 'normal',
            }),
        onSuccess: (res) => {
            const payload = (res.data as DocumentIntelActionResult).payload || {};
            const workId = typeof payload.work_id === 'string' ? payload.work_id : null;
            setError(null);
            setActionNotice((res.data as DocumentIntelActionResult).message || 'تم فتح الوثيقة داخل المحرر الذكي.');
            refreshActionLog();
            if (workId) {
                setCreatedWorkId(workId);
                router.push(`/workspace-drafts?work_id=${encodeURIComponent(workId)}`);
            }
        },
        onError: (err) => setError(apiError(err, 'تعذر فتح الوثيقة داخل المحرر الذكي.')),
    });

    const createDraftFromCandidate = useMutation({
        mutationFn: (candidate: DocumentIntelNewsItem) =>
            documentIntelApi.createDraft(documentId as number, {
                angle_title: candidate.headline,
                claim_indexes: [],
                category: 'international',
                urgency: 'normal',
            }),
        onSuccess: (res) => {
            const payload = (res.data as DocumentIntelActionResult).payload || {};
            const workId = typeof payload.work_id === 'string' ? payload.work_id : null;
            if (!workId) {
                setError('تم إنشاء المسودة لكن لم يتم إرجاع معرف العمل.');
                return;
            }
            setCreatedWorkId(workId);
            setError(null);
            setActionNotice((res.data as DocumentIntelActionResult).message || 'تم فتح الوثيقة داخل المحرر الذكي.');
            refreshActionLog();
            router.push(`/workspace-drafts?work_id=${encodeURIComponent(workId)}`);
        },
        onError: (err) => setError(apiError(err, 'تعذر إنشاء مسودة من الخبر المرشح.')),
    });

    const createStoryMutation = useMutation({
        mutationFn: (payload?: { angle_title?: string; angle_why_it_matters?: string }) =>
            documentIntelApi.createStory(documentId as number, payload || {}),
        onSuccess: (res) => {
            setError(null);
            setActionNotice((res.data as DocumentIntelActionResult).message || 'تم إنشاء قصة من الوثيقة.');
            refreshActionLog();
            router.push('/stories');
        },
        onError: (err) => setError(apiError(err, 'تعذر إنشاء قصة من الوثيقة.')),
    });

    const saveToMemoryMutation = useMutation({
        mutationFn: () => documentIntelApi.saveToMemory(documentId as number),
        onSuccess: (res) => {
            setError(null);
            setActionNotice((res.data as DocumentIntelActionResult).message || 'تم حفظ الوثيقة في الذاكرة التحريرية.');
            refreshActionLog();
        },
        onError: (err) => setError(apiError(err, 'تعذر حفظ الوثيقة في الذاكرة التحريرية.')),
    });

    const sendToFactcheckMutation = useMutation({
        mutationFn: () => documentIntelApi.sendToFactcheck(documentId as number),
        onSuccess: (res) => {
            const payload = (res.data as DocumentIntelActionResult).payload || {};
            const textSeed = typeof payload.text_seed === 'string' ? payload.text_seed : '';
            const reference = typeof payload.reference === 'string' ? payload.reference : '';
            const next = new URLSearchParams();
            if (textSeed) next.set('text', textSeed);
            if (reference) next.set('reference', reference);
            setError(null);
            setActionNotice((res.data as DocumentIntelActionResult).message || 'تم تجهيز الوثيقة للتحقق.');
            refreshActionLog();
            router.push(`/services/fact-check${next.toString() ? `?${next.toString()}` : ''}`);
        },
        onError: (err) => setError(apiError(err, 'تعذر تجهيز الوثيقة للتحقق.')),
    });

    const derivedError =
        statusPayload?.status === 'failed' || statusPayload?.status === 'dead_lettered'
            ? statusPayload.error || 'فشل تحليل الوثيقة.'
            : null;
    const effectiveError = error || derivedError;
    const extractStatus = statusPayload?.status ?? null;
    const isProcessing = runExtract.isPending || extractStatus === 'queued' || extractStatus === 'running';
    const extractStatusText =
        extractStatus === 'queued'
            ? 'الوثيقة في الطابور'
            : extractStatus === 'running'
              ? 'جارٍ تحليل الوثيقة'
              : extractStatus === 'completed'
                ? 'اكتمل التحليل'
                : extractStatus === 'failed' || extractStatus === 'dead_lettered'
                  ? 'فشل التحليل'
                  : null;

    return (
        <div className="space-y-5 app-theme-shell" dir="rtl">
            <div className="space-y-2">
                <h1 className="flex items-center gap-2 text-2xl font-bold text-white">
                    <FileSearch className="h-6 w-6 text-cyan-400" />
                    تحليل الوثائق
                </h1>
                <p className="text-sm text-gray-400">
                    ارفع وثيقة PDF لنستخرج منها خلاصة تحريرية، أخبارًا مرشحة، ادعاءات، كيانات، وزوايا قابلة للتحويل إلى خبر أو قصة.
                </p>
            </div>

            {effectiveError && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{effectiveError}</div>}
            {actionNotice && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{actionNotice}</div>}

            <section className="space-y-4 rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.6fr_1fr]">
                    <label className="flex h-12 cursor-pointer items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-gray-200">
                        <FileUp className="h-4 w-4 text-cyan-300" />
                        <span className="line-clamp-1">{file ? file.name : 'اختر ملف PDF للتحليل'}</span>
                        <input type="file" accept=".pdf,application/pdf" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                    </label>

                    <button onClick={() => runExtract.mutate()} disabled={!canRun || !file || isProcessing} className="flex h-12 items-center justify-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/20 text-sm text-emerald-200 disabled:opacity-50">
                        {isProcessing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                        تحليل الوثيقة
                    </button>
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <label className="space-y-1">
                        <span className="text-xs text-gray-400">لغة التلميح</span>
                        <select value={languageHint} onChange={(e) => setLanguageHint(e.target.value as 'ar' | 'fr' | 'en' | 'auto')} className="h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-gray-200">
                            <option value="ar">العربية</option>
                            <option value="fr">الفرنسية</option>
                            <option value="en">الإنجليزية</option>
                            <option value="auto">كشف تلقائي</option>
                        </select>
                    </label>
                    <label className="space-y-1">
                        <span className="text-xs text-gray-400">عدد الأخبار المرشحة</span>
                        <input type="number" min={1} max={20} value={maxNewsItems} onChange={(e) => setMaxNewsItems(Math.max(1, Math.min(20, Number(e.target.value) || 1)))} className="h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-gray-200" />
                    </label>
                    <label className="space-y-1">
                        <span className="text-xs text-gray-400">عدد النقاط الرقمية</span>
                        <input type="number" min={5} max={120} value={maxDataPoints} onChange={(e) => setMaxDataPoints(Math.max(5, Math.min(120, Number(e.target.value) || 5)))} className="h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-gray-200" />
                    </label>
                </div>

                {jobId && <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200">{extractStatusText ? `${extractStatusText} - ` : ''}معرف المهمة: {jobId}</div>}
            </section>

            {result && (
                <>
                    <section className="space-y-4 rounded-2xl border border-white/10 bg-gradient-to-br from-cyan-950/40 via-slate-950/40 to-slate-900/50 p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="space-y-2">
                                <p className="text-xs text-cyan-300">نظرة عامة</p>
                                <h2 className="text-xl font-bold text-white">{documentTypeLabel(result.document_type)}</h2>
                                <p className="max-w-4xl text-sm leading-7 text-gray-300">{result.document_summary || 'لم تتوفر خلاصة كافية للوثيقة بعد.'}</p>
                            </div>
                            <div className="min-w-[280px] space-y-2 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3">
                                <div className="text-xs text-gray-400">ما الإجراء التالي؟</div>
                                <div className="text-sm leading-6 text-white">{nextActionText(result)}</div>
                                <div className="flex flex-wrap gap-2 pt-1">
                                    {canCreateDraft ? <button onClick={() => createDocumentDraftMutation.mutate({ angle_title: result.news_candidates[0]?.headline, claim_indexes: overviewClaims.slice(0, 3).map((_, index) => index + 1) })} disabled={!documentId || createDocumentDraftMutation.isPending} className="h-9 rounded-lg border border-emerald-500/30 bg-emerald-500/20 px-3 text-xs text-emerald-200 disabled:opacity-50">{createDocumentDraftMutation.isPending ? 'جارٍ فتح المحرر...' : 'افتح في المحرر'}</button> : null}
                                    <button onClick={() => createStoryMutation.mutate(overviewAngles[0] ? { angle_title: overviewAngles[0].title, angle_why_it_matters: overviewAngles[0].why_it_matters } : undefined)} disabled={!documentId || createStoryMutation.isPending} className="h-9 rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/15 px-3 text-xs text-fuchsia-200 disabled:opacity-50">{createStoryMutation.isPending ? 'جارٍ إنشاء القصة...' : 'أنشئ قصة'}</button>
                                    <button onClick={() => sendToFactcheckMutation.mutate()} disabled={!documentId || sendToFactcheckMutation.isPending} className="h-9 rounded-lg border border-amber-500/30 bg-amber-500/15 px-3 text-xs text-amber-200 disabled:opacity-50">{sendToFactcheckMutation.isPending ? 'جارٍ تجهيز التحقق...' : 'أرسل للتحقق'}</button>
                                    <button onClick={() => saveToMemoryMutation.mutate()} disabled={!documentId || saveToMemoryMutation.isPending} className="h-9 rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-gray-200 disabled:opacity-50">{saveToMemoryMutation.isPending ? 'جارٍ الحفظ...' : 'احفظ في الذاكرة'}</button>
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3 text-xs lg:grid-cols-5">
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">الأخبار المرشحة</div><div className="mt-1 text-xl font-semibold text-white">{result.news_candidates.length}</div></div>
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">الادعاءات</div><div className="mt-1 text-xl font-semibold text-white">{result.claims.length}</div></div>
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">الكيانات</div><div className="mt-1 text-xl font-semibold text-white">{result.entities.length}</div></div>
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">النقاط الرقمية</div><div className="mt-1 text-xl font-semibold text-white">{result.data_points.length}</div></div>
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">اللغة المكتشفة</div><div className="mt-1 text-xl font-semibold text-white">{result.detected_language}</div></div>
                        </div>
                    </section>

                    <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.2fr_0.8fr]">
                        <div className="space-y-4 rounded-2xl border border-white/10 bg-black/20 p-4">
                            <div className="flex items-center gap-2 font-semibold text-white"><Newspaper className="h-4 w-4 text-cyan-300" />الأخبار والزوايا</div>

                            {result.news_candidates.length === 0 ? (
                                <p className="text-sm text-gray-500">لم يتم استخراج أخبار مرشحة واضحة من الوثيقة.</p>
                            ) : (
                                <div className="space-y-3">
                                    {result.news_candidates.map((item) => (
                                        <article key={item.rank} className="space-y-3 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                                            <div className="flex items-center justify-between gap-3">
                                                <p className="text-xs text-cyan-300">خبر مرشح #{item.rank}</p>
                                                <span className="text-xs text-gray-400">ثقة {Math.round(item.confidence * 100)}%</span>
                                            </div>
                                            <h3 className="text-base font-semibold leading-7 text-white">{item.headline}</h3>
                                            <p className="text-sm leading-7 text-gray-300">{item.summary}</p>
                                            {item.entities.length > 0 ? <div className="flex flex-wrap gap-2">{item.entities.map((entity) => <span key={`${item.rank}-${entity}`} className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[11px] text-gray-300">{entity}</span>)}</div> : null}
                                            <div className="flex flex-wrap gap-2">
                                                {canCreateDraft ? <button onClick={() => createDraftFromCandidate.mutate(item)} disabled={!documentId || createDraftFromCandidate.isPending} className="h-9 rounded-lg border border-emerald-500/30 bg-emerald-500/20 px-3 text-xs text-emerald-200 disabled:opacity-50">{createDraftFromCandidate.isPending ? 'جارٍ فتح المحرر...' : 'إنشاء خبر'}</button> : null}
                                                <button onClick={() => createStoryMutation.mutate({ angle_title: item.headline, angle_why_it_matters: item.summary })} disabled={!documentId || createStoryMutation.isPending} className="h-9 rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-gray-200 disabled:opacity-50">{createStoryMutation.isPending ? 'جارٍ إنشاء القصة...' : 'أنشئ قصة'}</button>
                                            </div>
                                        </article>
                                    ))}
                                </div>
                            )}

                            <div className="space-y-3 rounded-xl border border-white/10 bg-white/[0.03] p-4">
                                <div className="text-sm font-semibold text-white">زوايا تحريرية مقترحة</div>
                                {overviewAngles.length === 0 ? (
                                    <p className="text-sm text-gray-500">لا توجد زوايا واضحة بعد، لكن يمكن البناء على الأخبار المرشحة والادعاءات.</p>
                                ) : (
                                    <div className="space-y-3">
                                        {overviewAngles.map((angle: DocumentIntelStoryAngle, idx) => (
                                            <div key={`${angle.title}-${idx}`} className="rounded-lg border border-white/10 bg-black/20 p-3">
                                                <div className="text-sm font-medium leading-6 text-white">{angle.title}</div>
                                                <div className="mt-1 text-xs leading-6 text-gray-400">{angle.why_it_matters}</div>
                                                <div className="mt-3 flex flex-wrap gap-2">
                                                    <button onClick={() => createStoryMutation.mutate({ angle_title: angle.title, angle_why_it_matters: angle.why_it_matters })} disabled={!documentId || createStoryMutation.isPending} className="h-9 rounded-lg border border-fuchsia-500/30 bg-fuchsia-500/15 px-3 text-xs text-fuchsia-200 disabled:opacity-50">{createStoryMutation.isPending ? 'جارٍ إنشاء القصة...' : 'حوّلها إلى قصة'}</button>
                                                    {canCreateDraft ? <button onClick={() => createDocumentDraftMutation.mutate({ angle_title: angle.title, claim_indexes: overviewClaims.slice(0, 3).map((_, index) => index + 1) })} disabled={!documentId || createDocumentDraftMutation.isPending} className="h-9 rounded-lg border border-cyan-500/30 bg-cyan-500/15 px-3 text-xs text-cyan-200 disabled:opacity-50">{createDocumentDraftMutation.isPending ? 'جارٍ فتح المحرر...' : 'افتحها في المحرر'}</button> : null}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>

                        <div className="space-y-4">
                            <section className="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                                <div className="flex items-center gap-2 font-semibold text-white"><AlertTriangle className="h-4 w-4 text-amber-300" />الأدلة والبيانات</div>

                                <div className="space-y-2">
                                    <div className="text-xs text-gray-400">الادعاءات المستخرجة</div>
                                    {overviewClaims.length === 0 ? (
                                        <p className="text-sm text-gray-500">لم تُستخرج ادعاءات واضحة بعد.</p>
                                    ) : (
                                        overviewClaims.map((claim: DocumentIntelClaim, idx) => (
                                            <div key={`${claim.text}-${idx}`} className="space-y-2 rounded-xl border border-white/10 bg-white/[0.03] p-3">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-[11px] text-cyan-200">{claimTypeLabel(claim.type)}</span>
                                                    <span className={`rounded-full border px-2 py-1 text-[11px] ${riskBadgeClass(claim.risk_level)}`}>{claim.risk_level === 'high' ? 'مخاطر عالية' : claim.risk_level === 'medium' ? 'مخاطر متوسطة' : 'مخاطر منخفضة'}</span>
                                                    <span className="text-[11px] text-gray-400">ثقة {Math.round(claim.confidence * 100)}%</span>
                                                </div>
                                                <p className="text-sm leading-6 text-gray-200">{claim.text}</p>
                                            </div>
                                        ))
                                    )}
                                </div>

                                <div className="space-y-2">
                                    <div className="text-xs text-gray-400">الكيانات الظاهرة</div>
                                    {overviewEntities.length === 0 ? (
                                        <p className="text-sm text-gray-500">لا توجد كيانات واضحة بعد.</p>
                                    ) : (
                                        <div className="flex flex-wrap gap-2">{overviewEntities.map((entity: DocumentIntelEntity) => <div key={`${entity.name}-${entity.type}`} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-gray-200"><span className="font-medium text-white">{entity.name}</span><span className="text-gray-400"> - {entityTypeLabel(entity.type)}</span></div>)}</div>
                                    )}
                                </div>

                                <div className="space-y-2">
                                    <div className="text-xs text-gray-400">النقاط الرقمية</div>
                                    {result.data_points.length === 0 ? (
                                        <p className="text-sm text-gray-500">لا توجد نقاط رقمية واضحة.</p>
                                    ) : (
                                        <div className="max-h-[260px] space-y-2 overflow-auto">{result.data_points.slice(0, 8).map((item) => <div key={item.rank} className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="mb-1 text-xs text-cyan-300">#{item.rank} - {item.category}</div><div className="text-xs text-gray-100">{item.value_tokens.join(' | ')}</div><div className="mt-1 text-xs leading-5 text-gray-400">{item.context}</div></div>)}</div>
                                    )}
                                </div>
                            </section>
                        </div>
                    </section>

                    <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1.35fr_0.65fr]">
                        <section className="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                            <div className="flex items-center gap-2 font-semibold text-white"><ScanSearch className="h-4 w-4 text-cyan-300" />عرض الوثيقة</div>
                            <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-xl border border-white/10 bg-white/[0.03] p-4 text-xs leading-7 text-gray-300">{result.preview_text || 'لا توجد معاينة نصية.'}</pre>
                        </section>

                        <section className="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                            <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-2 font-semibold text-white"><LibraryBig className="h-4 w-4 text-cyan-300" />التفاصيل التقنية</div>
                                <button onClick={() => setShowTechDetails((prev) => !prev)} className="h-8 rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-gray-200">{showTechDetails ? 'إخفاء' : 'إظهار'}</button>
                            </div>

                            {showTechDetails ? (
                                <div className="space-y-3">
                                    <div className="grid grid-cols-2 gap-2 text-xs">
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">المعالج: <span className="text-white">{result.parser_used}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">اللغة: <span className="text-white">{result.detected_language}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">الصفحات: <span className="text-white">{result.stats.pages ?? '--'}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">المحارف: <span className="text-white">{result.stats.characters}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">الفقرات: <span className="text-white">{result.stats.paragraphs}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">العناوين: <span className="text-white">{result.stats.headings}</span></div>
                                    </div>
                                    {result.headings.length > 0 ? <div className="space-y-2"><div className="text-xs text-gray-400">العناوين المستخرجة</div><div className="space-y-2">{result.headings.slice(0, 10).map((heading, idx) => <div key={`${heading}-${idx}`} className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-xs text-gray-300">{heading}</div>)}</div></div> : null}
                                    {result.warnings.length > 0 ? <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">{result.warnings.join(' | ')}</div> : <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200"><CheckCircle2 className="h-4 w-4" />لا توجد تحذيرات تقنية بارزة.</div>}
                                </div>
                            ) : (
                                <p className="text-sm text-gray-500">التفاصيل التقنية متاحة عند الحاجة فقط حتى تبقى القراءة تحريرية وواضحة.</p>
                            )}
                        </section>
                    </section>

                    <section className="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4">
                        <div className="flex items-center justify-between gap-3">
                            <div className="font-semibold text-white">سجل استخدام الوثيقة</div>
                            <div className="text-xs text-gray-500">يسجل ما الذي فعلناه بهذه الوثيقة داخل غرفة الأخبار.</div>
                        </div>
                        {actionsQuery.isLoading ? (
                            <div className="text-sm text-gray-500">جارٍ تحميل السجل...</div>
                        ) : (actionsQuery.data?.data || []).length === 0 ? (
                            <div className="text-sm text-gray-500">لا توجد إجراءات مسجلة بعد لهذه الوثيقة.</div>
                        ) : (
                            <div className="space-y-2">
                                {(actionsQuery.data?.data || []).slice(0, 8).map((action: DocumentIntelActionLogItem) => (
                                    <div key={action.id} className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3 text-sm">
                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                            <div className="text-white">{actionLabel(action.action_type)}</div>
                                            <div className="text-xs text-gray-500">{new Date(action.created_at).toLocaleString('ar-DZ')}</div>
                                        </div>
                                        <div className="mt-1 text-xs text-gray-400">{action.actor_username ? `بواسطة ${action.actor_username}` : 'إجراء نظام'}{action.target_type ? ` - النوع: ${action.target_type}` : ''}{action.target_id ? ` - المعرف: ${action.target_id}` : ''}</div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </section>

                    {createdWorkId && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">تم إنشاء مسودة جديدة بنجاح: {createdWorkId}</div>}
                </>
            )}
        </div>
    );
}

export default function DocumentIntelPage() {
    return (
        <Suspense fallback={<div className="space-y-5 app-theme-shell" dir="rtl"><div className="rounded-2xl border border-white/10 bg-black/20 p-6 text-sm text-gray-300">جارٍ تحميل مساحة تحليل الوثائق...</div></div>}>
            <DocumentIntelPageContent />
        </Suspense>
    );
}
