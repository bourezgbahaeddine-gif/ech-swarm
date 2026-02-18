'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
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
} from 'lucide-react';
import { constitutionApi } from '@/lib/constitution-api';
import { editorialApi, newsApi } from '@/lib/api';
import { formatDate, formatRelativeTime, getCategoryLabel, getStatusColor, cn } from '@/lib/utils';

function sanitizeToolText(text: string): string {
    return (text || '')
        .replace(/```[\s\S]*?```/g, '')
        .replace(/^\s*(note|notes|explanation|comment)\s*:.*$/gim, '')
        .replace(/^\s*(ملاحظة|شرح|تعليق)\s*:.*$/gim, '')
        .trim();
}

export default function NewsDetailsPage() {
    const params = useParams<{ id: string }>();
    const id = useMemo(() => Number(params?.id || 0), [params?.id]);

    const [actionMessage, setActionMessage] = useState<string>('');
    const [toolOutput, setToolOutput] = useState<string>('');
    const [toolLabel, setToolLabel] = useState<string>('');
    const [tipSeed, setTipSeed] = useState(0);

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

    const article = data?.data;
    const tips = (tipsData?.data?.tips || []) as string[];
    const currentTip = tips.length ? tips[Math.abs(tipSeed) % tips.length] : 'تحقق من الادعاءات قبل أي اعتماد نهائي.';

    if (isLoading) {
        return <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-6 animate-pulse h-72" />;
    }

    if (isError || !article) {
        return (
            <div className="space-y-4">
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
                                dangerouslySetInnerHTML={{ __html: article.body_html }}
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
                        <h3 className="text-sm font-semibold text-white inline-flex items-center gap-2">
                            <Wand2 className="w-4 h-4 text-emerald-400" />
                            أدوات التعامل مع الخبر
                        </h3>
                        <div className="grid grid-cols-1 gap-2">
                            <Link
                                href={`/workspace-drafts?article_id=${article.id}`}
                                className="h-10 rounded-xl border border-emerald-500/30 bg-emerald-500/15 text-sm text-emerald-200 flex items-center justify-center gap-2"
                            >
                                <FileCheck2 className="w-4 h-4" /> فتح في المحرر الذكي
                            </Link>
                            <button
                                onClick={() => handoffMutation.mutate()}
                                disabled={handoffMutation.isPending}
                                className="h-10 rounded-xl border border-cyan-500/30 bg-cyan-500/15 text-sm text-cyan-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                <Send className="w-4 h-4" />
                                {handoffMutation.isPending ? 'جاري الترشيح...' : 'ترشيح للتحرير'}
                            </button>
                            <button
                                onClick={() => toolMutation.mutate('summarize')}
                                disabled={toolMutation.isPending}
                                className="h-10 rounded-xl border border-violet-500/30 bg-violet-500/15 text-sm text-violet-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                <Sparkles className="w-4 h-4" /> تلخيص سريع
                            </button>
                            <button
                                onClick={() => toolMutation.mutate('fact_check')}
                                disabled={toolMutation.isPending}
                                className="h-10 rounded-xl border border-amber-500/30 bg-amber-500/15 text-sm text-amber-200 disabled:opacity-60 inline-flex items-center justify-center gap-2"
                            >
                                <ShieldCheck className="w-4 h-4" /> تحقق أولي
                            </button>
                            <button
                                onClick={() => toolMutation.mutate('translate')}
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
                                    onClick={() => navigator.clipboard.writeText(toolOutput)}
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
        </div>
    );
}
