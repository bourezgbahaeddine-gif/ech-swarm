'use client';

import { useMemo, useState } from 'react';
import { Film, Image as ImageIcon, Layers, Clipboard, Sparkles } from 'lucide-react';
import { journalistServicesApi } from '@/lib/journalist-services-api';

const btnClass = 'px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 text-sm';
const selectClass = 'h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-300';

function cleanResult(value: string): string {
    return (value || '')
        .replace(/```[\s\S]*?```/g, '')
        .replace(/^\s*(note|notes|explanation|comment)\s*:.*$/gim, '')
        .replace(/^\s*(ملاحظة|شرح|تعليق)\s*:.*$/gim, '')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

function splitPrompts(text: string): string[] {
    const cleaned = cleanResult(text);
    if (!cleaned) return [];
    const chunks = cleaned
        .split(/\n(?=(?:\d+[\).\-\s]|برومبت|Prompt))/i)
        .map((s) => s.trim())
        .filter(Boolean);
    return chunks.length > 1 ? chunks : [cleaned];
}

export default function MultimediaServicesPage() {
    const [articleText, setArticleText] = useState('');
    const [style, setStyle] = useState('صحفي واقعي');
    const [goal, setGoal] = useState('خبر عاجل');
    const [ratio, setRatio] = useState('16:9');
    const [result, setResult] = useState('');
    const [busyImage, setBusyImage] = useState(false);
    const [articleId, setArticleId] = useState('');
    const [createdBy, setCreatedBy] = useState('');

    const [infText, setInfText] = useState('');
    const [infStatus, setInfStatus] = useState<'جاهز' | 'جارٍ التحليل' | 'جارٍ البناء' | 'مكتمل' | 'فشل'>('جاهز');
    const [infData, setInfData] = useState<unknown>(null);
    const [infPrompt, setInfPrompt] = useState('');
    const [infArticleId, setInfArticleId] = useState('');
    const [infCreatedBy, setInfCreatedBy] = useState('');

    const prompts = useMemo(() => splitPrompts(result), [result]);

    const generateImagePrompts = async () => {
        setBusyImage(true);
        try {
            const editorialBrief = [
                `هدف الاستخدام: ${goal}`,
                `الأسلوب البصري: ${style}`,
                `نسبة الأبعاد: ${ratio}`,
                'اشتراطات: صورة صحفية مهنية، واقعية، بلا تضليل، مساحة عنوان آمنة.',
                `نص الخبر: ${articleText}`,
            ].join('\n');
            const res = await journalistServicesApi.imagePrompt(
                editorialBrief,
                style,
                articleId ? Number(articleId) : undefined,
                createdBy || undefined,
                'ar',
            );
            setResult(cleanResult(res?.data?.result || ''));
        } finally {
            setBusyImage(false);
        }
    };

    const generateInfographic = async () => {
        setInfStatus('جارٍ التحليل');
        try {
            const analyzeRes = await journalistServicesApi.infographicAnalyze(
                infText,
                infArticleId ? Number(infArticleId) : undefined,
                infCreatedBy || undefined,
                'ar',
            );
            const data = analyzeRes?.data?.data || null;
            setInfData(data);

            setInfStatus('جارٍ البناء');
            const promptRes = await journalistServicesApi.infographicPrompt(
                data || {},
                infArticleId ? Number(infArticleId) : undefined,
                infCreatedBy || undefined,
                'ar',
            );
            setInfPrompt(cleanResult(promptRes?.data?.result || ''));
            setInfStatus('مكتمل');
        } catch {
            setInfStatus('فشل');
        }
    };

    return (
        <div className="space-y-6" dir="rtl">
            <div className="flex items-center gap-2">
                <Film className="w-5 h-5 text-emerald-400" />
                <h1 className="text-2xl font-bold text-white">الوسائط</h1>
            </div>

            <div className="rounded-2xl border border-cyan-500/30 bg-cyan-500/10 p-4 text-sm text-cyan-100">
                <p className="font-semibold mb-2 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" />
                    دليل الاستخدام السريع
                </p>
                <p>1) ألصق نص الخبر. 2) اختر الهدف البصري والنمط. 3) ولّد برومبتات جاهزة للإنتاج. 4) راجع قبل النشر.</p>
            </div>

            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                <div className="flex items-center gap-2">
                    <ImageIcon className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm text-gray-300">مولد برومبتات صورة المقال</h2>
                </div>

                <textarea
                    className="w-full min-h-[180px] p-4 rounded-2xl bg-white/5 border border-white/10 text-white text-sm"
                    placeholder="ألصق الخبر أو الملخص التحريري هنا..."
                    value={articleText}
                    onChange={(e) => setArticleText(e.target.value)}
                />

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                    <select className={selectClass} value={goal} onChange={(e) => setGoal(e.target.value)}>
                        <option>خبر عاجل</option>
                        <option>تحليل</option>
                        <option>تقرير اقتصادي</option>
                        <option>ملف استقصائي</option>
                    </select>
                    <select className={selectClass} value={style} onChange={(e) => setStyle(e.target.value)}>
                        <option>صحفي واقعي</option>
                        <option>وثائقي</option>
                        <option>تحليلي نظيف</option>
                        <option>درامي مضبوط</option>
                    </select>
                    <select className={selectClass} value={ratio} onChange={(e) => setRatio(e.target.value)}>
                        <option value="16:9">16:9 (موقع)</option>
                        <option value="4:5">4:5 (فيسبوك)</option>
                        <option value="1:1">1:1 (عام)</option>
                        <option value="9:16">9:16 (ستوري)</option>
                    </select>
                </div>

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

                <button className={btnClass} onClick={generateImagePrompts} disabled={busyImage}>
                    {busyImage ? 'جارٍ التوليد...' : 'توليد برومبتات الصورة'}
                </button>

                {prompts.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {prompts.map((p, i) => (
                            <div key={i} className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-[10px] text-gray-500">برومبت #{i + 1}</span>
                                    <button
                                        className="text-[10px] text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1"
                                        onClick={() => navigator.clipboard.writeText(p)}
                                    >
                                        <Clipboard className="w-3 h-3" />
                                        نسخ
                                    </button>
                                </div>
                                <pre className="whitespace-pre-wrap text-gray-200 text-xs">{p}</pre>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm text-gray-300">مولد برومبت الإنفوغرافيا</h2>
                </div>

                <textarea
                    className="w-full min-h-[160px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                    placeholder="ألصق الخبر لبناء إنفوغرافيا احترافية..."
                    value={infText}
                    onChange={(e) => setInfText(e.target.value)}
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
                <button className={btnClass} onClick={generateInfographic}>تحليل وبناء برومبت الإنفوغرافيا</button>
                <p className="text-[11px] text-gray-500">الحالة: {infStatus}</p>

                <div className="grid grid-cols-1 xl:grid-cols-12 gap-3">
                    <div className="xl:col-span-5 rounded-xl border border-white/10 bg-white/[0.02] p-3">
                        <h3 className="text-xs text-gray-400 mb-2">البيانات المستخرجة</h3>
                        <pre className="whitespace-pre-wrap text-[11px] text-gray-200">{JSON.stringify(infData || {}, null, 2)}</pre>
                    </div>
                    <div className="xl:col-span-7 rounded-xl border border-white/10 bg-white/[0.02] p-3">
                        <div className="flex items-center justify-between mb-2">
                            <h3 className="text-xs text-gray-400">البرومبت النهائي</h3>
                            <button
                                className="text-[10px] text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1"
                                onClick={() => navigator.clipboard.writeText(infPrompt || '')}
                            >
                                <Clipboard className="w-3 h-3" />
                                نسخ
                            </button>
                        </div>
                        <pre className="whitespace-pre-wrap text-sm text-gray-200">{infPrompt || '—'}</pre>
                    </div>
                </div>
            </div>
        </div>
    );
}
