import { useState } from 'react';
import { Sparkles } from 'lucide-react';
import { journalistServicesApi } from '@/lib/journalist-services-api';

const btnClass = "px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 text-sm";
const selectClass = "h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-300";

export default function EditorServicesPage() {
    const [input, setInput] = useState('');
    const [platform, setPlatform] = useState('twitter');
    const [result, setResult] = useState('');

    const run = async (fn: () => Promise<any>) => {
        const res = await fn();
        setResult(res?.data?.result || '');
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-emerald-400" />
                <h1 className="text-2xl font-bold text-white">خدمات التحرير والذكاء اللغوي</h1>
            </div>

            <textarea
                className="w-full min-h-[180px] p-4 rounded-2xl bg-white/5 border border-white/10 text-white"
                placeholder="ألصق النص هنا..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                dir="rtl"
            />

            <div className="flex flex-wrap gap-2">
                <button className={btnClass} onClick={() => run(() => journalistServicesApi.tonality(input))}>الرصانة اللغوية</button>
                <button className={btnClass} onClick={() => run(() => journalistServicesApi.inverted(input))}>الهرم المقلوب</button>
                <button className={btnClass} onClick={() => run(() => journalistServicesApi.proofread(input))}>تدقيق نحوي</button>
                <div className="flex items-center gap-2">
                    <select className={selectClass} value={platform} onChange={(e) => setPlatform(e.target.value)}>
                        <option value="twitter">Twitter</option>
                        <option value="facebook">Facebook</option>
                        <option value="instagram">Instagram</option>
                        <option value="general">General</option>
                    </select>
                    <button className={btnClass} onClick={() => run(() => journalistServicesApi.social(input, platform))}>ملخص سوشيال</button>
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
