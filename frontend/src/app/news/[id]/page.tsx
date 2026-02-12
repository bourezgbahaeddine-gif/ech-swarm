"use client";

import { useMemo } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, ExternalLink, Clock, Tag, ShieldCheck } from "lucide-react";
import { newsApi } from "@/lib/api";
import { formatDate, formatRelativeTime, getCategoryLabel, getStatusColor, cn } from "@/lib/utils";

export default function NewsDetailsPage() {
    const params = useParams<{ id: string }>();
    const id = useMemo(() => Number(params?.id || 0), [params?.id]);

    const { data, isLoading, isError } = useQuery({
        queryKey: ["news-details", id],
        queryFn: () => newsApi.get(id),
        enabled: Number.isFinite(id) && id > 0,
    });

    const article = data?.data;

    if (isLoading) {
        return (
            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-6 animate-pulse h-72" />
        );
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
        <div className="space-y-5">
            <div className="flex items-center justify-between gap-3">
                <Link
                    href="/news"
                    className="inline-flex items-center gap-2 text-sm text-emerald-300 hover:text-emerald-200"
                >
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

            <article className="rounded-2xl border border-white/5 bg-gray-900/40 p-6 space-y-5">
                <header className="space-y-3">
                    <h1 className="text-2xl font-bold text-white leading-relaxed" dir="rtl">
                        {article.title_ar || article.original_title}
                    </h1>
                    <div className="flex flex-wrap items-center gap-2 text-xs text-gray-400">
                        <span className={cn("px-2 py-1 rounded-md border", getStatusColor(article.status))}>
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
                            {article.source_name || "غير معروف"}
                        </span>
                        {typeof article.truth_score === "number" && (
                            <span className="px-2 py-1 rounded-md border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 inline-flex items-center gap-1">
                                <ShieldCheck className="w-3 h-3" />
                                وثوقية: {article.truth_score.toFixed(2)}
                            </span>
                        )}
                    </div>
                </header>

                {article.summary && (
                    <section className="rounded-xl border border-white/5 bg-white/[0.02] p-4" dir="rtl">
                        <h2 className="text-sm text-gray-300 mb-2">الملخص</h2>
                        <p className="text-sm text-gray-200 leading-7">{article.summary}</p>
                    </section>
                )}

                <section className="space-y-3" dir="rtl">
                    <h2 className="text-sm text-gray-300">المحتوى</h2>
                    {article.body_html ? (
                        <div
                            className="prose prose-invert max-w-none prose-p:leading-8 prose-p:text-gray-200"
                            dangerouslySetInnerHTML={{ __html: article.body_html }}
                        />
                    ) : (
                        <p className="text-sm text-gray-400 leading-7 whitespace-pre-wrap">
                            {article.original_content || "لا يوجد محتوى متاح لهذا الخبر."}
                        </p>
                    )}
                </section>

                <footer className="text-xs text-gray-500 border-t border-white/5 pt-4 space-y-1">
                    <div>نشر في المصدر: {article.published_at ? formatDate(article.published_at) : "غير متاح"}</div>
                    <div>تمت إضافته: {formatDate(article.created_at)}</div>
                    <div>آخر تحديث: {formatDate(article.updated_at)}</div>
                </footer>
            </article>
        </div>
    );
}
