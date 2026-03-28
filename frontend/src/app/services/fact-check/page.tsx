'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Clipboard, FileWarning, Image as ImageIcon, SearchCheck, ShieldCheck } from 'lucide-react';

import { journalistServicesApi } from '@/lib/journalist-services-api';

const btnClass =
    'px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 text-sm disabled:opacity-50';

function cleanResult(value: string): string {
    return (value || '')
        .replace(/```[\s\S]*?```/g, '')
        .replace(/^\s*(note|notes|explanation|comment)\s*:.*$/gim, '')
        .replace(/^\s*(ملاحظة|شرح|تعليق)\s*:.*$/gim, '')
        .replace(/^\s*(حسنًا|حسنا|يمكنني|آمل).*$/gim, '')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

function verdictLabel(value?: string): string {
    const verdict = String(value || '').toLowerCase();
    if (verdict === 'true') return 'صحيح';
    if (verdict === 'false') return 'غير صحيح';
    if (verdict === 'mixed') return 'مختلط';
    return 'غير واضح';
}

function FactCheckPageContent() {
    const searchParams = useSearchParams();
    const [imageUrl, setImageUrl] = useState('');
    const [question, setQuestion] = useState('تحقق من صحة الصورة وسياقها الزمني والمكاني');
    const [text, setText] = useState('');
    const [reference, setReference] = useState('');
    const [result, setResult] = useState('');
    const [busy, setBusy] = useState(false);
    const [googleQuery, setGoogleQuery] = useState('');
    const [googleMatches, setGoogleMatches] = useState<any[]>([]);
    const [googleSummary, setGoogleSummary] = useState<{ total?: number; verdicts?: Record<string, number>; primary_verdict?: string } | null>(null);
    const [googleBusy, setGoogleBusy] = useState(false);

    useEffect(() => {
        const nextText = searchParams.get('text');
        const nextReference = searchParams.get('reference');
        if (nextText) setText(nextText);
        if (nextReference) setReference(nextReference);
    }, [searchParams]);

    const checklist = useMemo(
        () => [
            'هل الادعاء منسوب إلى مصدر واضح؟',
            'هل الأرقام والتواريخ مدعومة بمرجع رسمي؟',
            'هل الخبر يتجنب الجزم من دون دليل؟',
            'هل تم وسم المعلومات غير المؤكدة بـ [VERIFY]؟',
        ],
        [],
    );

    const run = async (fn: () => Promise<{ data?: { result?: string } }>) => {
        setBusy(true);
        try {
            const res = await fn();
            setResult(cleanResult(res?.data?.result || ''));
        } finally {
            setBusy(false);
        }
    };

    const runGoogle = async () => {
        setGoogleBusy(true);
        try {
            const res = await journalistServicesApi.googleFactCheck(googleQuery);
            setGoogleMatches(Array.isArray(res?.data?.matches) ? res.data.matches : []);
            setGoogleSummary(res?.data?.summary || null);
        } finally {
            setGoogleBusy(false);
        }
    };

    return (
        <div className="space-y-6" dir="rtl">
            <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <h1 className="text-2xl font-bold text-white">التحقق والاستقصاء</h1>
            </div>

            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
                <p className="mb-2 flex items-center gap-2 font-semibold">
                    <FileWarning className="w-4 h-4" />
                    قائمة فحص سريعة قبل الاعتماد
                </p>
                <div className="space-y-1">
                    {checklist.map((item, idx) => (
                        <p key={item}>
                            {idx + 1}. {item}
                        </p>
                    ))}
                </div>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div className="space-y-3 rounded-2xl border border-white/5 bg-gray-900/40 p-4">
                    <h2 className="flex items-center gap-2 text-sm text-gray-300">
                        <SearchCheck className="h-4 w-4 text-emerald-400" />
                        تحقق نصي: اتساق وتعارضات
                    </h2>
                    <textarea
                        className="min-h-[140px] w-full rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white"
                        placeholder="ألصق النص المراد التحقق منه..."
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                    />
                    <textarea
                        className="min-h-[90px] w-full rounded-xl border border-white/10 bg-white/5 p-3 text-sm text-white"
                        placeholder="مرجع موثوق: رابط، بيان، أو أرشيف - اختياري"
                        value={reference}
                        onChange={(e) => setReference(e.target.value)}
                    />
                    <div className="flex flex-wrap gap-2">
                        <button className={btnClass} disabled={!text.trim() || busy} onClick={() => run(() => journalistServicesApi.consistency(text, reference))}>
                            كشف التناقضات
                        </button>
                        <button className={btnClass} disabled={!text.trim() || busy} onClick={() => run(() => journalistServicesApi.extract(text))}>
                            استخلاص النقاط
                        </button>
                    </div>
                </div>

                <div className="space-y-3 rounded-2xl border border-white/5 bg-gray-900/40 p-4">
                    <h2 className="flex items-center gap-2 text-sm text-gray-300">
                        <ImageIcon className="h-4 w-4 text-emerald-400" />
                        تحقق بصري للصور
                    </h2>
                    <input
                        className="h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white"
                        placeholder="رابط الصورة"
                        value={imageUrl}
                        onChange={(e) => setImageUrl(e.target.value)}
                    />
                    <input
                        className="h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white"
                        placeholder="سؤال التحقق"
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                    />
                    <button className={btnClass} disabled={!imageUrl.trim() || busy} onClick={() => run(() => journalistServicesApi.vision(imageUrl, question))}>
                        تشغيل التحقق البصري
                    </button>
                    <p className="text-[11px] text-gray-500">
                        مثال: هل الصورة قديمة؟ هل المكان مطابق للخبر؟ هل توجد مؤشرات تعديل أو تركيب؟
                    </p>
                </div>
            </div>

            <div className="space-y-3 rounded-2xl border border-white/5 bg-gray-900/40 p-4">
                <h2 className="flex items-center gap-2 text-sm text-gray-300">
                    <ShieldCheck className="h-4 w-4 text-emerald-400" />
                    نتائج Google Fact Check
                </h2>
                <input
                    className="h-10 w-full rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white"
                    placeholder="اكتب الادعاء أو الجملة المراد البحث عنها"
                    value={googleQuery}
                    onChange={(e) => setGoogleQuery(e.target.value)}
                />
                <div className="flex items-center gap-2">
                    <button className={btnClass} disabled={!googleQuery.trim() || googleBusy} onClick={runGoogle}>
                        {googleBusy ? 'جاري البحث...' : 'بحث خارجي'}
                    </button>
                    {googleSummary?.primary_verdict && (
                        <span className="text-xs text-emerald-200">الخلاصة: {verdictLabel(googleSummary.primary_verdict)}</span>
                    )}
                </div>
                {googleMatches.length === 0 ? (
                    <p className="text-xs text-gray-500">لا توجد نتائج بعد.</p>
                ) : (
                    <div className="space-y-2">
                        {googleMatches.slice(0, 6).map((match, idx) => (
                            <div key={`match-${idx}`} className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-gray-200">
                                <a href={match.url || '#'} target="_blank" rel="noreferrer" className="text-cyan-200 underline decoration-dotted">
                                    {match.title || match.claim || 'تدقيق خارجي'}
                                </a>
                                <p className="mt-1 text-[11px] text-gray-400">
                                    {match.publisher || 'بدون ناشر'}
                                    {match.rating ? ` • ${match.rating}` : ''}
                                </p>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4">
                <div className="mb-2 flex items-center justify-between">
                    <h2 className="text-sm text-gray-400">نتيجة التحقق</h2>
                    <button
                        onClick={() => navigator.clipboard.writeText(result || '')}
                        className="inline-flex items-center gap-1 text-xs text-emerald-300 hover:text-emerald-200"
                    >
                        <Clipboard className="h-3.5 w-3.5" />
                        نسخ
                    </button>
                </div>
                {busy ? (
                    <p className="text-sm text-gray-500">جارٍ التحليل...</p>
                ) : (
                    <pre className="whitespace-pre-wrap text-sm text-gray-200">{result || 'لا توجد نتيجة بعد.'}</pre>
                )}
            </div>
        </div>
    );
}

export default function FactCheckPage() {
    return (
        <Suspense fallback={<div className="space-y-6" dir="rtl"><div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 text-sm text-gray-300">جارٍ تحميل صفحة التحقق...</div></div>}>
            <FactCheckPageContent />
        </Suspense>
    );
}
