'use client';

import { useMemo, useState } from 'react';
import { ShieldCheck, SearchCheck, FileWarning, Image as ImageIcon, Clipboard } from 'lucide-react';
import { journalistServicesApi } from '@/lib/journalist-services-api';

const btnClass = 'px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 text-sm';

function cleanResult(value: string): string {
    return (value || '')
        .replace(/```[\s\S]*?```/g, '')
        .replace(/^\s*(note|notes|explanation|comment)\s*:.*$/gim, '')
        .replace(/^\s*(ملاحظة|شرح|تعليق)\s*:.*$/gim, '')
        .replace(/^\s*(حسنًا|حسنا|يمكنني|آمل).*$/gim, '')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

export default function FactCheckPage() {
    const [imageUrl, setImageUrl] = useState('');
    const [question, setQuestion] = useState('تحقق من صحة الصورة وسياقها الزمني والمكاني');
    const [text, setText] = useState('');
    const [reference, setReference] = useState('');
    const [result, setResult] = useState('');
    const [busy, setBusy] = useState(false);

    const checklist = useMemo(
        () => [
            'هل الادعاء منسوب لمصدر واضح؟',
            'هل الرقم/التاريخ مطابق لمصدر رسمي أو وكالة موثوقة؟',
            'هل صياغة الخبر خالية من الجزم غير المؤكد؟',
            'هل توجد صيغة تحذير [VERIFY] عند نقص الدليل؟',
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

    return (
        <div className="space-y-6" dir="rtl">
            <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <h1 className="text-2xl font-bold text-white">التحقق والاستقصاء</h1>
            </div>

            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-100">
                <p className="font-semibold mb-2 flex items-center gap-2">
                    <FileWarning className="w-4 h-4" />
                    دليل عملي سريع قبل الاعتماد
                </p>
                <div className="space-y-1">
                    {checklist.map((item, idx) => (
                        <p key={item}>{idx + 1}. {item}</p>
                    ))}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                    <h2 className="text-sm text-gray-300 flex items-center gap-2">
                        <SearchCheck className="w-4 h-4 text-emerald-400" />
                        تحقق نصي (تعارضات + سياق)
                    </h2>
                    <textarea
                        className="w-full min-h-[140px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                        placeholder="ألصق النص المراد التحقق منه..."
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                    />
                    <textarea
                        className="w-full min-h-[90px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                        placeholder="مرجع موثوق (رابط/بيان/أرشيف) - اختياري"
                        value={reference}
                        onChange={(e) => setReference(e.target.value)}
                    />
                    <div className="flex flex-wrap gap-2">
                        <button className={btnClass} onClick={() => run(() => journalistServicesApi.consistency(text, reference))}>كشف التناقضات</button>
                        <button className={btnClass} onClick={() => run(() => journalistServicesApi.extract(text))}>استخلاص النقاط</button>
                    </div>
                </div>

                <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                    <h2 className="text-sm text-gray-300 flex items-center gap-2">
                        <ImageIcon className="w-4 h-4 text-emerald-400" />
                        تحقق بصري للصورة
                    </h2>
                    <input
                        className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                        placeholder="رابط الصورة"
                        value={imageUrl}
                        onChange={(e) => setImageUrl(e.target.value)}
                    />
                    <input
                        className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                        placeholder="سؤال التحقق"
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                    />
                    <button className={btnClass} onClick={() => run(() => journalistServicesApi.vision(imageUrl, question))}>تحقق بصري</button>
                    <p className="text-[11px] text-gray-500">
                        مثال سؤال: هل الصورة قديمة؟ هل المكان مطابق للخبر؟ هل توجد مؤشرات تعديل أو تركيب؟
                    </p>
                </div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4">
                <div className="flex items-center justify-between mb-2">
                    <h2 className="text-sm text-gray-400">نتيجة التحقق</h2>
                    <button
                        onClick={() => navigator.clipboard.writeText(result || '')}
                        className="inline-flex items-center gap-1 text-xs text-emerald-300 hover:text-emerald-200"
                    >
                        <Clipboard className="w-3.5 h-3.5" />
                        نسخ
                    </button>
                </div>
                {busy ? (
                    <p className="text-sm text-gray-500">جاري التحليل...</p>
                ) : (
                    <pre className="whitespace-pre-wrap text-gray-200 text-sm">{result || '—'}</pre>
                )}
            </div>
        </div>
    );
}
