import { useState } from 'react';
import { Film, Image, Layers } from 'lucide-react';
import { journalistServicesApi } from '@/lib/journalist-services-api';

const btnClass = "px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 text-sm";
const selectClass = "h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-300";

export default function MultimediaServicesPage() {
    const [text, setText] = useState('');
    const [sourceLang, setSourceLang] = useState('auto');
    const [style, setStyle] = useState('cinematic');
    const [result, setResult] = useState('');
    const [prompts, setPrompts] = useState<string[]>([]);
    const [articleId, setArticleId] = useState<string>('');
    const [createdBy, setCreatedBy] = useState<string>('');

    // Infographic states
    const [infText, setInfText] = useState('');
    const [infStatus, setInfStatus] = useState<'Idle' | 'Analyzing' | 'Generating' | 'Success' | 'Error'>('Idle');
    const [infData, setInfData] = useState<any>(null);
    const [refinedPrompt, setRefinedPrompt] = useState('');
    const [infArticleId, setInfArticleId] = useState<string>('');
    const [infCreatedBy, setInfCreatedBy] = useState<string>('');

    const run = async (fn: () => Promise<any>) => {
        const res = await fn();
        const r = res?.data?.result || '';
        setResult(r);
        if (r) {
            const list = r.split(/\n{2,}/).map((s: string) => s.trim()).filter(Boolean);
            setPrompts(list);
        }
    };

    const analyzeInfographic = async () => {
        setInfStatus('Analyzing');
        try {
            const res = await journalistServicesApi.infographicAnalyze(
                infText,
                infArticleId ? Number(infArticleId) : undefined,
                infCreatedBy || undefined
            );
            setInfData(res?.data?.data || null);
            setInfStatus('Generating');
            const promptRes = await journalistServicesApi.infographicPrompt(
                res?.data?.data || {},
                infArticleId ? Number(infArticleId) : undefined,
                infCreatedBy || undefined
            );
            setRefinedPrompt(promptRes?.data?.result || '');
            setInfStatus('Success');
        } catch {
            setInfStatus('Error');
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2">
                <Film className="w-5 h-5 text-emerald-400" />
                <h1 className="text-2xl font-bold text-white">خدمات الإبداع البصري والوسائط</h1>
            </div>

            <textarea
                className="w-full min-h-[180px] p-4 rounded-2xl bg-white/5 border border-white/10 text-white"
                placeholder="ألصق الخبر أو النص هنا..."
                value={text}
                onChange={(e) => setText(e.target.value)}
                dir="rtl"
            />

            <div className="flex flex-wrap gap-2">
                <button className={btnClass} onClick={() => run(() => journalistServicesApi.videoScript(text))}>سكريبت فيديو</button>
                <button className={btnClass} onClick={() => run(() => journalistServicesApi.sentiment(text))}>تحليل مشاعر</button>
                <div className="flex items-center gap-2">
                    <select className={selectClass} value={sourceLang} onChange={(e) => setSourceLang(e.target.value)}>
                        <option value="auto">Auto</option>
                        <option value="en">English</option>
                        <option value="fr">French</option>
                    </select>
                    <button className={btnClass} onClick={() => run(() => journalistServicesApi.translate(text, sourceLang))}>ترجمة</button>
                </div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                <div className="flex items-center gap-2">
                    <Image className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm text-gray-300">Nano-Hook: توليد برومبتات الصور</h2>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <select className={selectClass} value={style} onChange={(e) => setStyle(e.target.value)}>
                        <option value="cinematic">Cinematic</option>
                        <option value="documentary">Documentary</option>
                        <option value="realistic">Realistic</option>
                        <option value="dramatic">Dramatic</option>
                    </select>
                    <button className={btnClass} onClick={() => run(() => journalistServicesApi.imagePrompt(text, style, articleId ? Number(articleId) : undefined, createdBy || undefined))}>توليد برومبت</button>
                </div>
                <p className="text-[10px] text-gray-500">
                    يعتمد على الهوية البصرية للشروق مع 10 نقاط هندسة برومبت ثابتة.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <input
                        className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-300"
                        placeholder="معرّف الخبر (اختياري)"
                        value={articleId}
                        onChange={(e) => setArticleId(e.target.value)}
                    />
                    <input
                        className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-300"
                        placeholder="اسم المستخدم (اختياري)"
                        value={createdBy}
                        onChange={(e) => setCreatedBy(e.target.value)}
                    />
                </div>

                {prompts.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {prompts.map((p, i) => (
                            <div key={i} className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-[10px] text-gray-500">برومبت #{i + 1}</span>
                                    <button
                                        className="text-[10px] text-emerald-300 hover:text-emerald-200 underline"
                                        onClick={() => navigator.clipboard.writeText(p)}
                                    >
                                        نسخ
                                    </button>
                                </div>
                                <pre className="whitespace-pre-wrap text-gray-200 text-xs" dir="rtl">{p}</pre>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Infographic Builder */}
            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm text-gray-300">صانع الإنفوجرافيك الصحفي الذكي</h2>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-12 gap-3">
                    <div className="xl:col-span-8 space-y-2">
                        <textarea
                            className="w-full min-h-[160px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                            placeholder="ألصق الخبر لصناعة إنفوجرافيك..."
                            value={infText}
                            onChange={(e) => setInfText(e.target.value)}
                            dir="rtl"
                        />
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <input
                                className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-300"
                                placeholder="معرّف الخبر (اختياري)"
                                value={infArticleId}
                                onChange={(e) => setInfArticleId(e.target.value)}
                            />
                            <input
                                className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-300"
                                placeholder="اسم المستخدم (اختياري)"
                                value={infCreatedBy}
                                onChange={(e) => setInfCreatedBy(e.target.value)}
                            />
                        </div>
                        <button className={btnClass} onClick={analyzeInfographic}>تحليل وبناء البرومبت</button>
                        <div className="text-[10px] text-gray-500">الحالة: {infStatus}</div>
                    </div>
                    <div className="xl:col-span-4">
                        <div className="h-full rounded-xl border border-white/10 bg-white/[0.02] p-3">
                            <h3 className="text-xs text-gray-400 mb-2">المخرجات</h3>
                            <pre className="whitespace-pre-wrap text-[11px] text-gray-200" dir="rtl">{JSON.stringify(infData || {}, null, 2)}</pre>
                        </div>
                    </div>
                </div>

                <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                    <h3 className="text-xs text-gray-400 mb-2">البرومبت النهائي</h3>
                    <pre className="whitespace-pre-wrap text-sm text-gray-200" dir="rtl">{refinedPrompt || '—'}</pre>
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
