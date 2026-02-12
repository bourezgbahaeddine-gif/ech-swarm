import { useState } from 'react';
import { ShieldCheck } from 'lucide-react';
import { journalistServicesApi } from '@/lib/journalist-services-api';

const btnClass = "px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 text-sm";

export default function FactCheckPage() {
    const [imageUrl, setImageUrl] = useState('');
    const [question, setQuestion] = useState('تحقق من صحة الصورة وسياقها');
    const [text, setText] = useState('');
    const [reference, setReference] = useState('');
    const [result, setResult] = useState('');

    const run = async (fn: () => Promise<any>) => {
        const res = await fn();
        setResult(res?.data?.result || '');
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-emerald-400" />
                <h1 className="text-2xl font-bold text-white">خدمات التحقق والاستقصاء</h1>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                    <h2 className="text-sm text-gray-300">تحقق بصري (Vision)</h2>
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
                </div>

                <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                    <h2 className="text-sm text-gray-300">كشف التناقضات التاريخية</h2>
                    <textarea
                        className="w-full min-h-[120px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                        placeholder="نص الخبر"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        dir="rtl"
                    />
                    <textarea
                        className="w-full min-h-[80px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                        placeholder="مرجع/أرشيف موثوق (اختياري)"
                        value={reference}
                        onChange={(e) => setReference(e.target.value)}
                        dir="rtl"
                    />
                    <button className={btnClass} onClick={() => run(() => journalistServicesApi.consistency(text, reference))}>كشف التناقضات</button>
                </div>

                <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                    <h2 className="text-sm text-gray-300">استخلاص من وثائق طويلة</h2>
                    <textarea
                        className="w-full min-h-[120px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                        placeholder="ألصق الوثيقة أو التقرير الطويل هنا"
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                        dir="rtl"
                    />
                    <button className={btnClass} onClick={() => run(() => journalistServicesApi.extract(text))}>استخلاص النقاط</button>
                </div>
            </div>

            <ResultBox result={result} />
        </div>
    );
}

function ResultBox({ result }: { result: string }) {
    return (
        <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4">
            <h2 className="text-sm text-gray-400 mb-2">النتيجة</h2>
            <pre className="whitespace-pre-wrap text-gray-200 text-sm" dir="rtl">{result || '—'}</pre>
        </div>
    );
}
