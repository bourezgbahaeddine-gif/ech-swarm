import { useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { journalistServicesApi } from '@/lib/journalist-services-api';

const btnClass = "px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 text-sm";

export default function SeoServicesPage() {
    const [text, setText] = useState('');
    const [archive, setArchive] = useState('');
    const [result, setResult] = useState('');

    const run = async (fn: () => Promise<any>) => {
        const res = await fn();
        setResult(res?.data?.result || '');
    };

    const archiveList = archive
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean);

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-emerald-400" />
                <h1 className="text-2xl font-bold text-white">خدمات SEO والانتشار الرقمي</h1>
            </div>

            <textarea
                className="w-full min-h-[180px] p-4 rounded-2xl bg-white/5 border border-white/10 text-white"
                placeholder="ألصق الخبر هنا..."
                value={text}
                onChange={(e) => setText(e.target.value)}
                dir="rtl"
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                    <h2 className="text-sm text-gray-300">كلمات مفتاحية طويلة</h2>
                    <button className={btnClass} onClick={() => run(() => journalistServicesApi.keywords(text))}>توليد كلمات</button>
                </div>

                <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                    <h2 className="text-sm text-gray-300">روابط داخلية ذكية</h2>
                    <textarea
                        className="w-full min-h-[100px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                        placeholder="ألصق عناوين الأرشيف (سطر لكل عنوان)"
                        value={archive}
                        onChange={(e) => setArchive(e.target.value)}
                        dir="rtl"
                    />
                    <button className={btnClass} onClick={() => run(() => journalistServicesApi.internalLinks(text, archiveList))}>اقتراح روابط</button>
                </div>

                <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                    <h2 className="text-sm text-gray-300">Metadata</h2>
                    <button className={btnClass} onClick={() => run(() => journalistServicesApi.metadata(text))}>توليد ميتاداتا</button>
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
