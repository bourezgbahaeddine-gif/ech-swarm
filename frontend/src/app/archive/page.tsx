'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Archive, Search, ExternalLink, Copy, CheckCircle2 } from 'lucide-react';

import { archiveApi, type ArchiveSearchItem } from '@/lib/api';
import { cn, formatDate, truncate } from '@/lib/utils';

function getApiErrorMessage(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) return detail;
        const message = error.response?.data?.error?.message;
        if (typeof message === 'string' && message.trim()) return message;
    }
    return fallback;
}

export default function ArchivePage() {
    const [query, setQuery] = useState('');
    const [debouncedQuery, setDebouncedQuery] = useState('');
    const [limit, setLimit] = useState(10);
    const [copiedId, setCopiedId] = useState<number | null>(null);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        const t = setTimeout(() => setDebouncedQuery(query.trim()), 350);
        return () => clearTimeout(t);
    }, [query]);

    const { data, isLoading, isFetching, error } = useQuery({
        queryKey: ['archive-search', debouncedQuery, limit],
        queryFn: () => archiveApi.search({ q: debouncedQuery, limit }),
        enabled: debouncedQuery.length >= 2,
    });

    useEffect(() => {
        if (!error) {
            setErrorMessage(null);
            return;
        }
        setErrorMessage(getApiErrorMessage(error, 'تعذر جلب نتائج الأرشيف.'));
    }, [error]);

    const items = useMemo(
        () => (data?.data?.items || []) as ArchiveSearchItem[],
        [data?.data?.items]
    );

    const handleCopy = async (item: ArchiveSearchItem) => {
        if (!item?.url) return;
        try {
            await navigator.clipboard.writeText(item.url);
            setCopiedId(item.id);
            window.setTimeout(() => setCopiedId(null), 1500);
        } catch {
            // ignore
        }
    };

    return (
        <div className="space-y-5">
            <div>
                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                    <Archive className="w-6 h-6 text-amber-400" />
                    أرشيف الشروق (RAG)
                </h1>
                <p className="text-sm text-gray-400 mt-1">
                    بحث دلالي داخل أرشيف الشروق. النتائج تستخدم كمرجع سياقي للكتابة عند تفعيل RAG.
                </p>
            </div>

            {errorMessage && (
                <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
                    {errorMessage}
                </div>
            )}

            <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                <div className="flex flex-wrap gap-2 items-center">
                    <div className="relative flex-1 min-w-[220px]">
                        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                        <input
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            placeholder="ابحث في أرشيف الشروق..."
                            className="w-full h-10 pr-10 pl-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                            dir="rtl"
                        />
                    </div>
                    <select
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                        className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                    >
                        {[5, 10, 15, 20].map((value) => (
                            <option key={value} value={value}>
                                {value} نتيجة
                            </option>
                        ))}
                    </select>
                    <div className="text-xs text-gray-500">
                        {debouncedQuery.length >= 2
                            ? isFetching
                                ? 'جارٍ البحث...'
                                : `نتائج: ${items.length}`
                            : 'اكتب كلمتين على الأقل'}
                    </div>
                </div>

                <div className="space-y-2">
                    {isLoading && debouncedQuery.length >= 2 ? (
                        <div className="text-sm text-gray-400 p-3">جارٍ جلب نتائج الأرشيف...</div>
                    ) : items.length === 0 && debouncedQuery.length >= 2 ? (
                        <div className="text-sm text-gray-500 p-3">لا توجد نتائج مطابقة.</div>
                    ) : (
                        items.map((item) => (
                            <article
                                key={item.id}
                                className="rounded-xl border border-white/10 bg-white/[0.02] px-4 py-3 space-y-2"
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <div className="space-y-1">
                                        <h3 className="text-white text-sm font-semibold leading-relaxed">
                                            {item.title || 'بدون عنوان'}
                                        </h3>
                                        <div className="flex flex-wrap gap-2 text-xs text-gray-400">
                                            <span>{item.source_name || 'الشروق أونلاين'}</span>
                                            <span>•</span>
                                            <span>{formatDate(item.published_at)}</span>
                                            <span>•</span>
                                            <span>درجة {(item.score * 100).toFixed(1)}%</span>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        {item.url && (
                                            <a
                                                href={item.url}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="text-xs px-2.5 py-1 rounded-lg border border-white/10 bg-white/5 text-gray-200 hover:text-white"
                                            >
                                                <span className="inline-flex items-center gap-1">
                                                    فتح
                                                    <ExternalLink className="w-3.5 h-3.5" />
                                                </span>
                                            </a>
                                        )}
                                        <button
                                            onClick={() => handleCopy(item)}
                                            className={cn(
                                                'text-xs px-2.5 py-1 rounded-lg border',
                                                copiedId === item.id
                                                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                                                    : 'border-white/10 bg-white/5 text-gray-300 hover:text-white'
                                            )}
                                        >
                                            <span className="inline-flex items-center gap-1">
                                                {copiedId === item.id ? (
                                                    <>
                                                        تم النسخ
                                                        <CheckCircle2 className="w-3.5 h-3.5" />
                                                    </>
                                                ) : (
                                                    <>
                                                        نسخ الرابط
                                                        <Copy className="w-3.5 h-3.5" />
                                                    </>
                                                )}
                                            </span>
                                        </button>
                                    </div>
                                </div>
                                <p className="text-sm text-gray-300 leading-relaxed">
                                    {truncate(item.summary || '', 260)}
                                </p>
                            </article>
                        ))
                    )}
                </div>
            </section>
        </div>
    );
}
