'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { useRouter } from 'next/navigation';
import { FileUp, FileText, Loader2, Newspaper, Sigma, Sparkles } from 'lucide-react';

import {
    documentIntelApi,
    editorialApi,
    type DocumentIntelExtractJobStatus,
    type DocumentIntelExtractResult,
    type DocumentIntelNewsItem,
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

export default function DocumentIntelPage() {
    const router = useRouter();
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canRun = RUN_ROLES.has(role);
    const canCreateDraft = CREATE_DRAFT_ROLES.has(role);

    const [file, setFile] = useState<File | null>(null);
    const [languageHint, setLanguageHint] = useState<'ar' | 'fr' | 'en' | 'auto'>('ar');
    const [maxNewsItems, setMaxNewsItems] = useState(8);
    const [maxDataPoints, setMaxDataPoints] = useState(30);
    const [error, setError] = useState<string | null>(null);
    const [createdWorkId, setCreatedWorkId] = useState<string | null>(null);
    const [jobId, setJobId] = useState<string | null>(null);

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
            setCreatedWorkId(null);
        },
        onError: (err) => setError(apiError(err, 'Failed to submit document extraction job.')),
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

    const createDraftFromCandidate = useMutation({
        mutationFn: (candidate: DocumentIntelNewsItem) =>
            editorialApi.createManualWorkspaceDraft({
                title: candidate.headline,
                summary: candidate.summary,
                body: `${candidate.summary}\n\n${candidate.evidence}`,
                category: 'international',
                urgency: 'normal',
                source_action: 'document_intel_pdf',
            }),
        onSuccess: (res) => {
            const workId = (res.data as { work_id?: string })?.work_id;
            if (!workId) {
                setError('تم إنشاء المسودة لكن لم يتم إرجاع Work ID.');
                return;
            }
            setCreatedWorkId(workId);
            setError(null);
            router.push(`/workspace-drafts?work_id=${encodeURIComponent(workId)}`);
        },
        onError: (err) => setError(apiError(err, 'تعذر إنشاء مسودة من الخبر المرشح.')),
    });

    const statusPayload = extractStatusQuery.data?.data;
    const result: DocumentIntelExtractResult | null =
        statusPayload?.status === 'completed' && statusPayload.result ? statusPayload.result : null;
    const derivedError =
        statusPayload?.status === 'failed' || statusPayload?.status === 'dead_lettered'
            ? statusPayload.error || 'Document extraction failed.'
            : null;
    const effectiveError = error || derivedError;
    const stats = result?.stats;
    const parserBadge = useMemo(() => {
        if (!result) return '--';
        if (result.parser_used === 'docling') return 'Docling';
        if (result.parser_used === 'pypdf') return 'pypdf (fallback)';
        return result.parser_used;
    }, [result]);
    const extractStatus = statusPayload?.status ?? null;
    const isProcessing = runExtract.isPending || extractStatus === 'queued' || extractStatus === 'running';
    const extractStatusText =
        extractStatus === 'queued'
            ? 'In queue'
            : extractStatus === 'running'
              ? 'Processing'
              : extractStatus === 'completed'
                ? 'Completed'
                : extractStatus === 'failed' || extractStatus === 'dead_lettered'
                  ? 'Failed'
                  : null;

    return (
        <div className="space-y-5 app-theme-shell" dir="rtl">
            <div>
                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                    <FileText className="w-6 h-6 text-cyan-400" />
                    محلل الوثائق الرسمية (PDF)
                </h1>
                <p className="text-sm text-gray-400 mt-1">
                    ارفع ملف PDF (تقارير، جريدة رسمية، بيانات) لاستخراج الأخبار المرشحة والنقاط الرقمية تلقائياً.
                </p>
            </div>

            {effectiveError && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                    {effectiveError}
                </div>
            )}

            <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                <label className="h-12 px-3 rounded-xl border border-white/10 bg-white/5 text-sm text-gray-200 flex items-center gap-2 cursor-pointer">
                    <FileUp className="w-4 h-4 text-cyan-300" />
                    <span className="line-clamp-1">{file ? file.name : 'اختر ملف PDF للتحليل'}</span>
                    <input
                        type="file"
                        accept=".pdf,application/pdf"
                        className="hidden"
                        onChange={(e) => setFile(e.target.files?.[0] || null)}
                    />
                </label>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <label className="space-y-1">
                        <span className="text-xs text-gray-400">لغة التلميح</span>
                        <select
                            value={languageHint}
                            onChange={(e) => setLanguageHint(e.target.value as 'ar' | 'fr' | 'en' | 'auto')}
                            className="w-full h-10 px-3 rounded-lg border border-white/10 bg-white/5 text-sm text-gray-200"
                        >
                            <option value="ar">العربية</option>
                            <option value="fr">الفرنسية</option>
                            <option value="en">الإنجليزية</option>
                            <option value="auto">كشف تلقائي</option>
                        </select>
                    </label>
                    <label className="space-y-1">
                        <span className="text-xs text-gray-400">عدد الأخبار المرشحة</span>
                        <input
                            type="number"
                            min={1}
                            max={20}
                            value={maxNewsItems}
                            onChange={(e) => setMaxNewsItems(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                            className="w-full h-10 px-3 rounded-lg border border-white/10 bg-white/5 text-sm text-gray-200"
                        />
                    </label>
                    <label className="space-y-1">
                        <span className="text-xs text-gray-400">عدد النقاط الرقمية</span>
                        <input
                            type="number"
                            min={5}
                            max={120}
                            value={maxDataPoints}
                            onChange={(e) => setMaxDataPoints(Math.max(5, Math.min(120, Number(e.target.value) || 5)))}
                            className="w-full h-10 px-3 rounded-lg border border-white/10 bg-white/5 text-sm text-gray-200"
                        />
                    </label>
                </div>

                <button
                    onClick={() => runExtract.mutate()}
                    disabled={!canRun || !file || isProcessing}
                    className="w-full h-11 rounded-xl border border-emerald-500/30 bg-emerald-500/20 text-emerald-200 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                    تحليل الوثيقة
                </button>
                {jobId && (
                    <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200">
                        {extractStatusText ? `${extractStatusText} - ` : ''}Job ID: {jobId}
                    </div>
                )}
            </section>

            {result && (
                <>
                    <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-2">
                        <h2 className="text-sm font-semibold text-white">ملخص التحليل</h2>
                        <div className="grid grid-cols-2 md:grid-cols-6 gap-2 text-xs">
                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">المعالج: <span className="text-white">{parserBadge}</span></div>
                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">اللغة: <span className="text-white">{result.detected_language}</span></div>
                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">صفحات: <span className="text-white">{stats?.pages ?? '--'}</span></div>
                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">محارف: <span className="text-white">{stats?.characters ?? 0}</span></div>
                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">فقرات: <span className="text-white">{stats?.paragraphs ?? 0}</span></div>
                            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">عناوين: <span className="text-white">{stats?.headings ?? 0}</span></div>
                        </div>
                        {(result.warnings || []).length > 0 && (
                            <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
                                {result.warnings.join(' | ')}
                            </div>
                        )}
                        {createdWorkId && (
                            <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                                تم إنشاء مسودة جديدة: {createdWorkId}
                            </div>
                        )}
                    </section>

                    <section className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                                <Newspaper className="w-4 h-4 text-cyan-300" />
                                الأخبار المرشحة ({result.news_candidates.length})
                            </h2>
                            <div className="space-y-2 max-h-[560px] overflow-auto">
                                {result.news_candidates.length === 0 ? (
                                    <p className="text-sm text-gray-500">لم يتم استخراج أخبار مرشحة من هذا الملف.</p>
                                ) : (
                                    result.news_candidates.map((item) => (
                                        <article key={item.rank} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                                            <p className="text-xs text-cyan-300 mb-1">#{item.rank} • ثقة {Math.round(item.confidence * 100)}%</p>
                                            <h3 className="text-sm text-white font-semibold leading-6">{item.headline}</h3>
                                            <p className="text-sm text-gray-300 leading-6 mt-1">{item.summary}</p>
                                            {item.entities.length > 0 && (
                                                <p className="text-xs text-gray-400 mt-2">كيانات: {item.entities.join('، ')}</p>
                                            )}
                                            {canCreateDraft && (
                                                <button
                                                    onClick={() => createDraftFromCandidate.mutate(item)}
                                                    disabled={createDraftFromCandidate.isPending}
                                                    className="mt-3 h-9 px-3 rounded-lg border border-emerald-500/30 bg-emerald-500/20 text-emerald-200 text-xs disabled:opacity-50"
                                                >
                                                    {createDraftFromCandidate.isPending ? 'جاري الإنشاء...' : 'إنشاء Draft في المحرر الذكي'}
                                                </button>
                                            )}
                                        </article>
                                    ))
                                )}
                            </div>
                        </div>

                        <div className="space-y-4">
                            <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                                <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                                    <Sigma className="w-4 h-4 text-cyan-300" />
                                    النقاط الرقمية ({result.data_points.length})
                                </h2>
                                <div className="space-y-2 max-h-[280px] overflow-auto">
                                    {result.data_points.length === 0 ? (
                                        <p className="text-sm text-gray-500">لا توجد نقاط رقمية واضحة.</p>
                                    ) : (
                                        result.data_points.map((item) => (
                                            <div key={item.rank} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                                                <p className="text-xs text-cyan-300 mb-1">#{item.rank} • {item.category}</p>
                                                <p className="text-xs text-gray-200">{item.value_tokens.join(' | ')}</p>
                                                <p className="text-xs text-gray-400 mt-1 leading-5">{item.context}</p>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </div>

                            <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                                <h2 className="text-sm font-semibold text-white">معاينة النص</h2>
                                <pre className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs text-gray-300 leading-6 max-h-[260px] overflow-auto whitespace-pre-wrap">
                                    {result.preview_text || 'لا توجد معاينة نصية.'}
                                </pre>
                            </div>
                        </div>
                    </section>
                </>
            )}
        </div>
    );
}
