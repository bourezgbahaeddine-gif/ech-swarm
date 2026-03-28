"use client";

import { useMemo } from 'react';
import { useParams } from 'next/navigation';
import NextLink from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, AlertTriangle, ArrowRight, Calendar, ExternalLink, FileText, Link2, Search, ShieldCheck } from 'lucide-react';
import { cn } from '@/lib/utils';
import { editorialApi, WorkspaceReadyPackage } from '@/lib/api';

const STAGE_LABELS: Record<string, string> = {
    FACT_CHECK: 'التحقق من الادعاءات',
    QUALITY_SCORE: 'تدقيق الجودة',
    READABILITY: 'قابلية القراءة',
    SEO_TECH: 'تدقيق SEO التقني',
    SEO_SUGGESTIONS: 'اقتراحات SEO',
    SOCIAL_VARIANTS: 'نسخ السوشيال',
    HEADLINE_PACK: 'حزمة العناوين',
};

const formatDate = (value?: string | null) => {
    if (!value) return 'غير متاح';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return new Intl.DateTimeFormat('ar-DZ', { dateStyle: 'medium', timeStyle: 'short' }).format(parsed);
};

const statusBadge = (passed?: boolean) =>
    passed
        ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100'
        : 'border-amber-500/40 bg-amber-500/10 text-amber-100';

export default function ReadyPublishPage() {
    const params = useParams();
    const workId = useMemo(() => {
        const raw = params?.workId;
        return Array.isArray(raw) ? raw[0] : raw;
    }, [params]);

    const readyQuery = useQuery({
        queryKey: ['ready-publish-package', workId],
        queryFn: async () => (await editorialApi.workspaceReadyPackage(String(workId))).data,
        enabled: Boolean(workId),
    });

    if (readyQuery.isLoading) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center text-sm text-slate-300" dir="rtl">
                جاري تجهيز صفحة الجاهزية...
            </div>
        );
    }

    if (!readyQuery.data) {
        return (
            <div className="flex min-h-[60vh] items-center justify-center text-sm text-slate-300" dir="rtl">
                لا توجد بيانات لهذه المادة بعد.
            </div>
        );
    }

    const data = readyQuery.data as WorkspaceReadyPackage;
    const readiness = data.readiness;
    const reports = data.reports || {};
    const articleTitle = data.draft?.title || data.article?.title || data.article?.original_title || 'عنوان غير متاح';
    const journalist = data.journalist?.name || data.journalist?.updated_by || data.journalist?.created_by || 'غير معروف';
    const sourceName = data.article?.source_name || 'مصدر غير معروف';
    const sourceUrl = data.article?.source_url || '';
    const articleDate = data.article?.published_at || data.article?.crawled_at || data.draft?.updated_at || data.article?.created_at || null;

    const factReport = reports.FACT_CHECK;
    const qualityReport = reports.QUALITY_SCORE;
    const readabilityReport = reports.READABILITY;
    const seoTechReport = reports.SEO_TECH;
    const seoSuggestionReport = reports.SEO_SUGGESTIONS;
    const socialReport = reports.SOCIAL_VARIANTS;
    const headlineReport = reports.HEADLINE_PACK;

    const factPayload = (factReport?.report || {}) as Record<string, any>;
    const claims = Array.isArray(factPayload.claims) ? factPayload.claims : [];

    const qualityPayload = (qualityReport?.report || {}) as Record<string, any>;
    const readabilityPayload = (readabilityReport?.report || {}) as Record<string, any>;
    const seoTechPayload = (seoTechReport?.report || {}) as Record<string, any>;
    const seoPayloadWrapper = (seoSuggestionReport?.report || {}) as Record<string, any>;
    const seoPayload = (seoPayloadWrapper.seo || seoPayloadWrapper) as Record<string, any>;
    const socialPayloadWrapper = (socialReport?.report || {}) as Record<string, any>;
    const socialVariants = (socialPayloadWrapper.variants || {}) as Record<string, any>;
    const headlinePayloadWrapper = (headlineReport?.report || {}) as Record<string, any>;
    const headlinesRaw = headlinePayloadWrapper.headlines || [];
    const headlines = Array.isArray(headlinesRaw)
        ? headlinesRaw.map((item: any) => (typeof item === 'string' ? item : String(item?.headline || item?.title || '')).trim()).filter(Boolean)
        : [];

    const latestLinksRun = (data.links_history || [])[0];

    return (
        <div className="space-y-6" dir="rtl">
            <section className="rounded-[28px] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(16,185,129,0.15),transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(15,23,42,0.75))] p-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                        <p className="text-xs text-emerald-200">جاهز للنشر</p>
                        <h1 className="mt-2 text-2xl font-semibold text-white">حزمة النشر اليدوي</h1>
                        <p className="mt-2 max-w-2xl text-sm text-slate-300">
                            كل المخرجات التحريرية مرتبطة بهذه المادة وجاهزة للتسليم والنشر اليدوي.
                        </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <span className={cn('inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs', readiness?.ready_for_publish ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100' : 'border-amber-500/40 bg-amber-500/10 text-amber-100')}>
                            {readiness?.ready_for_publish ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                            {readiness?.ready_for_publish ? 'جاهز للنشر' : 'غير مكتمل'}
                        </span>
                        <NextLink
                            href={`/workspace-drafts?work_id=${data.work_id}`}
                            className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white"
                        >
                            عودة إلى المحرر
                            <ArrowRight className="h-4 w-4" />
                        </NextLink>
                    </div>
                </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-[1.1fr_2fr]">
                <div className="space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                        <h2 className="text-sm font-semibold text-white">بيانات المادة</h2>
                        <div className="mt-3 space-y-2 text-xs text-slate-300">
                            <div className="flex items-center justify-between gap-2">
                                <span>الصحفي</span>
                                <span className="text-white">{journalist}</span>
                            </div>
                            <div className="flex items-center justify-between gap-2">
                                <span>التاريخ</span>
                                <span className="text-white">{formatDate(articleDate)}</span>
                            </div>
                            <div className="flex items-center justify-between gap-2">
                                <span>المصدر</span>
                                <span className="text-white">{sourceName}</span>
                            </div>
                            {sourceUrl && (
                                <a
                                    href={sourceUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-2 text-emerald-200"
                                >
                                    <ExternalLink className="h-4 w-4" />
                                    فتح المصدر
                                </a>
                            )}
                        </div>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                        <h2 className="text-sm font-semibold text-white">حالة الجاهزية</h2>
                        <div className="mt-3 space-y-2 text-xs text-slate-300">
                            <div className="flex items-center justify-between">
                                <span>الحالة</span>
                                <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', readiness?.ready_for_publish ? 'border-emerald-400/40 text-emerald-100' : 'border-amber-400/40 text-amber-100')}>
                                    {readiness?.ready_for_publish ? 'جاهز للنشر' : 'غير جاهز بعد'}
                                </span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span>عدد الموانع</span>
                                <span className="text-white">{readiness?.blocking_reasons?.length || 0}</span>
                            </div>
                            {readiness?.blocking_reasons?.length ? (
                                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2 text-[11px] text-amber-100">
                                    {readiness.blocking_reasons.slice(0, 5).map((reason, index) => (
                                        <div key={`${reason}-${index}`}>? {reason}</div>
                                    ))}
                                </div>
                            ) : (
                                <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-2 text-[11px] text-emerald-100">
                                    لا توجد موانع نشطة الآن.
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center gap-2 text-white">
                        <FileText className="h-5 w-5" />
                        <h2 className="text-lg font-semibold">نسخة المادة</h2>
                    </div>
                    <h3 className="mt-4 text-xl font-bold text-white">{articleTitle}</h3>
                    <div
                        className="prose prose-invert mt-4 max-w-none prose-p:leading-8 prose-p:text-slate-200"
                        dangerouslySetInnerHTML={{ __html: data.draft?.body || '' }}
                    />
                </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-white">
                            <ShieldCheck className="h-5 w-5" />
                            <h3 className="text-sm font-semibold">{STAGE_LABELS.FACT_CHECK}</h3>
                        </div>
                        <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', statusBadge(factReport?.passed))}>
                            {factReport ? (factReport.passed ? 'ناجح' : 'غير مكتمل') : 'غير متاح'}
                        </span>
                    </div>
                    <p className="mt-3 text-xs text-slate-300">عدد الادعاءات: {claims.length || 0}</p>
                    {claims.slice(0, 6).map((claim: any, idx: number) => (
                        <div key={`${claim?.id || idx}`} className="mt-2 rounded-lg border border-white/10 bg-white/5 p-2 text-[11px] text-slate-200">
                            <div className="flex items-center justify-between">
                                <span>{claim?.text}</span>
                                <span className="text-amber-200">{claim?.risk_level || 'غير معروف'}</span>
                            </div>
                        </div>
                    ))}
                    {!claims.length && <div className="mt-3 text-[11px] text-slate-400">لا توجد ادعاءات تحتاج تحققًا الآن.</div>}
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-white">
                            <CheckCircle2 className="h-5 w-5" />
                            <h3 className="text-sm font-semibold">{STAGE_LABELS.QUALITY_SCORE}</h3>
                        </div>
                        <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', statusBadge(qualityReport?.passed))}>
                            {qualityReport ? (qualityReport.passed ? 'ناجح' : 'غير مكتمل') : 'غير متاح'}
                        </span>
                    </div>
                    <p className="mt-3 text-xs text-slate-300">النتيجة: {qualityReport?.score ?? qualityPayload.score ?? '?'}</p>
                    {Array.isArray(qualityPayload?.actionable_fixes) && qualityPayload.actionable_fixes.length > 0 && (
                        <div className="mt-3 space-y-1 text-[11px] text-slate-200">
                            {qualityPayload.actionable_fixes.slice(0, 4).map((fix: string, idx: number) => (
                                <div key={`${fix}-${idx}`}>? {fix}</div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-white">
                            <FileText className="h-5 w-5" />
                            <h3 className="text-sm font-semibold">{STAGE_LABELS.READABILITY}</h3>
                        </div>
                        <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', statusBadge(readabilityReport?.passed))}>
                            {readabilityReport ? (readabilityReport.passed ? 'ناجح' : 'غير مكتمل') : 'غير متاح'}
                        </span>
                    </div>
                    <p className="mt-3 text-xs text-slate-300">النتيجة: {readabilityReport?.score ?? readabilityPayload.score ?? '?'}</p>
                    {Array.isArray(readabilityPayload?.actionable_fixes) && readabilityPayload.actionable_fixes.length > 0 && (
                        <div className="mt-3 space-y-1 text-[11px] text-slate-200">
                            {readabilityPayload.actionable_fixes.slice(0, 4).map((fix: string, idx: number) => (
                                <div key={`${fix}-${idx}`}>? {fix}</div>
                            ))}
                        </div>
                    )}
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-white">
                            <Calendar className="h-5 w-5" />
                            <h3 className="text-sm font-semibold">{STAGE_LABELS.SEO_TECH}</h3>
                        </div>
                        <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', statusBadge(seoTechReport?.passed))}>
                            {seoTechReport ? (seoTechReport.passed ? 'ناجح' : 'غير مكتمل') : 'غير متاح'}
                        </span>
                    </div>
                    <p className="mt-3 text-xs text-slate-300">النتيجة: {seoTechReport?.score ?? seoTechPayload.score ?? '?'}</p>
                    {Array.isArray(seoTechPayload?.actionable_fixes) && seoTechPayload.actionable_fixes.length > 0 && (
                        <div className="mt-3 space-y-1 text-[11px] text-slate-200">
                            {seoTechPayload.actionable_fixes.slice(0, 4).map((fix: string, idx: number) => (
                                <div key={`${fix}-${idx}`}>? {fix}</div>
                            ))}
                        </div>
                    )}
                </div>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-white">
                            <Search className="h-5 w-5" />
                            <h3 className="text-sm font-semibold">{STAGE_LABELS.SEO_SUGGESTIONS}</h3>
                        </div>
                        <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', statusBadge(seoSuggestionReport?.passed))}>
                            {seoSuggestionReport ? 'جاهز' : 'غير متاح'}
                        </span>
                    </div>
                    <div className="mt-3 space-y-2 text-xs text-slate-300">
                        <div>عنوان SEO: <span className="text-white">{seoPayload?.seo_title || '?'}</span></div>
                        <div>الوصف: <span className="text-white">{seoPayload?.meta_description || '?'}</span></div>
                        <div>الكلمة المفتاحية: <span className="text-white">{seoPayload?.focus_keyphrase || '?'}</span></div>
                    </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-white">
                            <CheckCircle2 className="h-5 w-5" />
                            <h3 className="text-sm font-semibold">{STAGE_LABELS.HEADLINE_PACK}</h3>
                        </div>
                        <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', statusBadge(headlineReport?.passed))}>
                            {headlineReport ? 'جاهز' : 'غير متاح'}
                        </span>
                    </div>
                    {headlines.length ? (
                        <div className="mt-3 space-y-2 text-[11px] text-slate-200">
                            {headlines.slice(0, 6).map((headline: string, idx: number) => (
                                <div key={`${headline}-${idx}`} className="rounded-lg border border-white/10 bg-white/5 px-2 py-1">{headline}</div>
                            ))}
                        </div>
                    ) : (
                        <p className="mt-3 text-xs text-slate-400">لا توجد عناوين مقترحة الآن.</p>
                    )}
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 text-white">
                            <FileText className="h-5 w-5" />
                            <h3 className="text-sm font-semibold">{STAGE_LABELS.SOCIAL_VARIANTS}</h3>
                        </div>
                        <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', statusBadge(socialReport?.passed))}>
                            {socialReport ? 'جاهز' : 'غير متاح'}
                        </span>
                    </div>
                    {Object.keys(socialVariants).length ? (
                        <div className="mt-3 space-y-2 text-[11px] text-slate-200">
                            {Object.entries(socialVariants).map(([key, value]) => (
                                <div key={key} className="rounded-lg border border-white/10 bg-white/5 p-2">
                                    <div className="text-[10px] text-emerald-200">{key}</div>
                                    <div>{String(value)}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="mt-3 text-xs text-slate-400">لا توجد نسخ اجتماعية جاهزة الآن.</p>
                    )}
                </div>

                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <div className="flex items-center gap-2 text-white">
                        <Link2 className="h-5 w-5" />
                        <h3 className="text-sm font-semibold">روابط مرجعية</h3>
                    </div>
                    {latestLinksRun ? (
                        <div className="mt-3 space-y-2 text-[11px] text-slate-200">
                            <div className="text-[10px] text-slate-400">آخر تحديث: {formatDate(latestLinksRun.created_at)}</div>
                            {latestLinksRun.items.slice(0, 6).map((item) => (
                                <div key={`${item.id}-${item.url}`} className="rounded-lg border border-white/10 bg-white/5 p-2">
                                    <div className="text-emerald-200">{item.title || item.url}</div>
                                    <div className="text-[10px] text-slate-400">{item.url}</div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="mt-3 text-xs text-slate-400">لا توجد روابط مرجعية الآن.</p>
                    )}
                </div>
            </section>
        </div>
    );
}
