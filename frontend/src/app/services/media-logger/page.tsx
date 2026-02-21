'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Copy, FileAudio2, HelpCircle, Link as LinkIcon, Loader2, Mic, PlayCircle, Quote } from 'lucide-react';

import {
    mediaLoggerApi,
    type MediaLoggerAskResponse,
    type MediaLoggerResult,
} from '@/lib/api';
import { useAuth } from '@/lib/auth';

const RUN_ROLES = new Set(['director', 'editor_chief', 'journalist', 'social_media', 'print_editor']);

function fmtTime(seconds: number): string {
    const total = Math.max(0, Math.floor(seconds || 0));
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

function apiError(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) return detail;
    }
    return fallback;
}

export default function MediaLoggerPage() {
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canRun = RUN_ROLES.has(role);
    const qc = useQueryClient();

    const [mode, setMode] = useState<'url' | 'upload'>('url');
    const [mediaUrl, setMediaUrl] = useState('');
    const [uploadFile, setUploadFile] = useState<File | null>(null);
    const [languageHint, setLanguageHint] = useState<'ar' | 'fr' | 'en' | 'auto'>('ar');
    const [runId, setRunId] = useState('');
    const [question, setQuestion] = useState('');
    const [answer, setAnswer] = useState<MediaLoggerAskResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    const runFromUrl = useMutation({
        mutationFn: () => mediaLoggerApi.runFromUrl({ media_url: mediaUrl.trim(), language_hint: languageHint }),
        onSuccess: (res) => {
            setRunId(res.data.run_id);
            setError(null);
            setAnswer(null);
            qc.invalidateQueries({ queryKey: ['media-logger-runs'] });
        },
        onError: (err) => setError(apiError(err, 'فشل تشغيل التفريغ من الرابط.')),
    });

    const runFromUpload = useMutation({
        mutationFn: () =>
            mediaLoggerApi.runFromUpload({
                file: uploadFile as File,
                language_hint: languageHint,
            }),
        onSuccess: (res) => {
            setRunId(res.data.run_id);
            setError(null);
            setAnswer(null);
            qc.invalidateQueries({ queryKey: ['media-logger-runs'] });
        },
        onError: (err) => setError(apiError(err, 'فشل تشغيل التفريغ من الملف.')),
    });

    const runStatusQuery = useQuery({
        queryKey: ['media-logger-status', runId],
        queryFn: () => mediaLoggerApi.runStatus(runId),
        enabled: !!runId,
        refetchInterval: (q) => {
            const status = q.state.data?.data?.status;
            if (!status || status === 'completed' || status === 'failed') return false;
            return 1800;
        },
    });
    const status = runStatusQuery.data?.data?.status;

    const resultQuery = useQuery({
        queryKey: ['media-logger-result', runId],
        queryFn: () => mediaLoggerApi.result(runId),
        enabled: !!runId && status === 'completed',
    });
    const result = resultQuery.data?.data as MediaLoggerResult | undefined;

    const recentRunsQuery = useQuery({
        queryKey: ['media-logger-runs'],
        queryFn: () => mediaLoggerApi.recentRuns({ limit: 10 }),
        refetchInterval: 20000,
    });
    const recentRuns = recentRunsQuery.data?.data?.items || [];

    const askMutation = useMutation({
        mutationFn: () => mediaLoggerApi.ask({ run_id: runId, question: question.trim() }),
        onSuccess: (res) => {
            setAnswer(res.data);
            setError(null);
        },
        onError: (err) => setError(apiError(err, 'تعذر استخراج الاقتباس المطلوب.')),
    });

    const busy = runFromUrl.isPending || runFromUpload.isPending;
    const canRunNow = canRun && ((mode === 'url' && mediaUrl.trim().length > 8) || (mode === 'upload' && !!uploadFile));

    const statusLabel = useMemo(() => {
        if (!status) return 'لم يبدأ';
        if (status === 'queued') return 'قيد الانتظار';
        if (status === 'running') return 'جاري التفريغ';
        if (status === 'completed') return 'مكتمل';
        if (status === 'failed') return 'فشل';
        return status;
    }, [status]);

    return (
        <div className="space-y-5 app-theme-shell" dir="rtl">
            <div>
                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                    <Mic className="w-6 h-6 text-cyan-400" />
                    مفرّغ الندوات ومقتنص الاقتباسات
                </h1>
                <p className="text-sm text-gray-400 mt-1">
                    ارفع ملفًا أو رابط بث YouTube/Facebook لاستخراج النص الكامل والاقتباسات الأساسية خلال دقائق.
                </p>
            </div>

            {error && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                    {error}
                </div>
            )}

            <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                <div className="flex flex-wrap gap-2">
                    <button
                        onClick={() => setMode('url')}
                        className={`px-3 py-2 rounded-lg text-sm border ${mode === 'url' ? 'border-cyan-500/40 bg-cyan-500/20 text-cyan-200' : 'border-white/10 bg-white/5 text-gray-300'}`}
                    >
                        رابط مباشر
                    </button>
                    <button
                        onClick={() => setMode('upload')}
                        className={`px-3 py-2 rounded-lg text-sm border ${mode === 'upload' ? 'border-cyan-500/40 bg-cyan-500/20 text-cyan-200' : 'border-white/10 bg-white/5 text-gray-300'}`}
                    >
                        رفع ملف صوت/فيديو
                    </button>
                    <select
                        value={languageHint}
                        onChange={(e) => setLanguageHint(e.target.value as 'ar' | 'fr' | 'en' | 'auto')}
                        className="mr-auto h-10 px-3 rounded-lg border border-white/10 bg-white/5 text-sm text-gray-200"
                    >
                        <option value="ar">العربية</option>
                        <option value="fr">الفرنسية</option>
                        <option value="en">الإنجليزية</option>
                        <option value="auto">كشف تلقائي</option>
                    </select>
                </div>

                {mode === 'url' ? (
                    <div className="space-y-2">
                        <div className="relative">
                            <LinkIcon className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                            <input
                                value={mediaUrl}
                                onChange={(e) => setMediaUrl(e.target.value)}
                                placeholder="ضع رابط YouTube أو Facebook Video"
                                className="w-full h-11 pr-10 pl-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-gray-500"
                                dir="ltr"
                            />
                        </div>
                    </div>
                ) : (
                    <div className="space-y-2">
                        <label className="h-11 px-3 rounded-xl border border-white/10 bg-white/5 text-sm text-gray-200 flex items-center gap-2 cursor-pointer">
                            <FileAudio2 className="w-4 h-4 text-cyan-300" />
                            <span className="line-clamp-1">{uploadFile ? uploadFile.name : 'اختر ملف MP3/MP4/MOV/WAV'}</span>
                            <input
                                type="file"
                                accept="audio/*,video/*"
                                className="hidden"
                                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                            />
                        </label>
                    </div>
                )}

                <button
                    onClick={() => (mode === 'url' ? runFromUrl.mutate() : runFromUpload.mutate())}
                    disabled={!canRunNow || busy}
                    className="w-full h-11 rounded-xl border border-emerald-500/30 bg-emerald-500/20 text-emerald-200 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                >
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
                    تشغيل المفرّغ
                </button>

                <div className="text-xs text-gray-400">
                    الحالة الحالية: <span className="text-gray-200">{statusLabel}</span>
                    {runId ? <span className="mr-2">run_id: {runId}</span> : null}
                </div>
            </section>

            <section className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                <div className="xl:col-span-2 rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                        <h2 className="text-sm text-white font-semibold">النص المفرّغ</h2>
                        {result?.transcript_text ? (
                            <button
                                onClick={() => navigator.clipboard.writeText(result.transcript_text)}
                                className="text-xs text-cyan-300 hover:text-cyan-200 inline-flex items-center gap-1"
                            >
                                <Copy className="w-3.5 h-3.5" /> نسخ
                            </button>
                        ) : null}
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 max-h-[360px] overflow-auto">
                        <pre className="whitespace-pre-wrap text-sm text-gray-100 leading-7">
                            {result?.transcript_text || 'لا يوجد تفريغ بعد.'}
                        </pre>
                    </div>
                    <p className="text-xs text-gray-500">
                        اللغة: {result?.transcript_language || '--'} • المدة: {result?.duration_seconds ? `${fmtTime(result.duration_seconds)}` : '--'} • المقاطع: {result?.segments_count ?? 0}
                    </p>
                </div>

                <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                    <h2 className="text-sm text-white font-semibold flex items-center gap-2">
                        <Quote className="w-4 h-4 text-cyan-300" />
                        أبرز الاقتباسات
                    </h2>
                    <div className="space-y-2 max-h-[420px] overflow-auto">
                        {(result?.highlights || []).length === 0 ? (
                            <p className="text-sm text-gray-500">لا توجد اقتباسات بعد.</p>
                        ) : (
                            result?.highlights.map((h) => (
                                <div key={`${h.rank}-${h.start_sec}`} className="rounded-xl border border-white/10 bg-white/[0.03] p-2">
                                    <p className="text-[11px] text-cyan-300 mb-1">
                                        #{h.rank} • {fmtTime(h.start_sec)} → {fmtTime(h.end_sec)}
                                    </p>
                                    <p className="text-sm text-gray-100 leading-6">{h.quote}</p>
                                    {h.reason ? <p className="text-[11px] text-gray-400 mt-1">{h.reason}</p> : null}
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </section>

            <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                <h2 className="text-sm text-white font-semibold flex items-center gap-2">
                    <HelpCircle className="w-4 h-4 text-cyan-300" />
                    سؤال مباشر داخل الندوة
                </h2>
                <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-2">
                    <input
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        placeholder='مثال: ماذا قال الوزير عن السكن في الدقيقة 40؟'
                        className="h-11 px-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder:text-gray-500"
                    />
                    <button
                        onClick={() => askMutation.mutate()}
                        disabled={!runId || !question.trim() || status !== 'completed' || askMutation.isPending}
                        className="h-11 px-4 rounded-xl border border-cyan-500/30 bg-cyan-500/20 text-cyan-200 text-sm disabled:opacity-50"
                    >
                        {askMutation.isPending ? 'جاري التحليل...' : 'استخراج الجواب'}
                    </button>
                </div>

                {answer ? (
                    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 space-y-2">
                        <p className="text-sm text-cyan-100">{answer.answer}</p>
                        <p className="text-sm text-white">«{answer.quote}»</p>
                        <p className="text-xs text-cyan-200">الطابع الزمني: {fmtTime(answer.start_sec)} → {fmtTime(answer.end_sec)} • ثقة {Math.round(answer.confidence * 100)}%</p>
                    </div>
                ) : null}
            </section>

            <section className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <h2 className="text-sm text-white font-semibold mb-3">آخر التشغيلات</h2>
                <div className="space-y-2">
                    {recentRuns.length === 0 ? (
                        <p className="text-sm text-gray-500">لا توجد تشغيلات بعد.</p>
                    ) : (
                        recentRuns.map((row) => (
                            <button
                                key={row.run_id}
                                onClick={() => setRunId(row.run_id)}
                                className="w-full text-right rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 hover:bg-white/[0.06]"
                            >
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-sm text-gray-100 line-clamp-1">{row.source_label || row.run_id}</p>
                                    <span className="text-xs text-cyan-300">{row.status}</span>
                                </div>
                                <p className="text-xs text-gray-500 mt-1">
                                    مقاطع: {row.segments_count || 0} • اقتباسات: {row.highlights_count || 0}
                                </p>
                            </button>
                        ))
                    )}
                </div>
            </section>
        </div>
    );
}
