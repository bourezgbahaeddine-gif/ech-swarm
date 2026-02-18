'use client';

import { useMemo, useState } from 'react';
import {
    Film,
    Image as ImageIcon,
    Layers,
    Clipboard,
    Sparkles,
    Settings2,
    SlidersHorizontal,
} from 'lucide-react';
import { journalistServicesApi } from '@/lib/journalist-services-api';
import { useAuth } from '@/lib/auth';

const btnClass = 'px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 text-sm disabled:opacity-60';
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

function buildNanoBananaPrompt(basePrompt: string, ratio: string, goal: string, safety: string, camera: string, lighting: string): string {
    return [
        '[MODEL] NanoBanana 2',
        '[TASK] Generate a photorealistic newsroom-safe visual for an Arabic news article.',
        `[EDITORIAL_GOAL] ${goal}`,
        `[ASPECT_RATIO] ${ratio}`,
        `[CAMERA_PROFILE] ${camera}`,
        `[LIGHTING_PROFILE] ${lighting}`,
        `[SAFETY_LEVEL] ${safety}`,
        '[POSITIVE_PROMPT]',
        basePrompt,
        '[NEGATIVE_PROMPT]',
        'no text overlays, no watermark, no logo distortion, no deformed hands, no exaggerated violence, no fake political symbols, no fantasy style, no cartoon style, no gore',
        '[OUTPUT_RULES]',
        'single still image, editorial realism, natural skin tones, clean composition, keep safe text zone for headline',
    ].join('\n');
}

function buildNanoInfographicPrompt(basePrompt: string, ratio: string, safety: string): string {
    return [
        '[MODEL] NanoBanana 2',
        '[TASK] Build a clean Arabic infographic scene from structured newsroom data.',
        `[ASPECT_RATIO] ${ratio}`,
        `[SAFETY_LEVEL] ${safety}`,
        '[LAYOUT_RULES]',
        'clear hierarchy, readable Arabic labels, balanced spacing, strong contrast, newsroom style',
        '[BRAND_COLORS]',
        '#F37021 #0A0A0A #FFFFFF',
        '[POSITIVE_PROMPT]',
        basePrompt,
        '[NEGATIVE_PROMPT]',
        'no clutter, no tiny unreadable text, no random icons, no decorative noise, no satire style',
    ].join('\n');
}

export default function MultimediaServicesPage() {
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canUseMultimedia = ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'].includes(role);

    const [articleText, setArticleText] = useState('');
    const [style, setStyle] = useState('صحفي واقعي');
    const [goal, setGoal] = useState('خبر عاجل');
    const [ratio, setRatio] = useState('16:9');
    const [model, setModel] = useState('nanobanana2');
    const [camera, setCamera] = useState('35mm documentary');
    const [lighting, setLighting] = useState('natural newsroom light');
    const [safety, setSafety] = useState('strict-newsroom');
    const [result, setResult] = useState('');
    const [busyImage, setBusyImage] = useState(false);

    const [infText, setInfText] = useState('');
    const [infStatus, setInfStatus] = useState<'جاهز' | 'جارٍ التحليل' | 'جارٍ البناء' | 'مكتمل' | 'فشل'>('جاهز');
    const [infData, setInfData] = useState<unknown>(null);
    const [infPrompt, setInfPrompt] = useState('');

    const prompts = useMemo(() => splitPrompts(result), [result]);

    if (!canUseMultimedia) {
        return (
            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 space-y-3" dir="rtl">
                <h1 className="text-xl text-white font-semibold">الوسائط</h1>
                <p className="text-sm text-gray-300">
                    هذه الصفحة متاحة للصحفيين وفرق التحرير والسوشيال ميديا فقط.
                </p>
            </div>
        );
    }

    const generateImagePrompts = async () => {
        setBusyImage(true);
        try {
            const editorialBrief = [
                `الهدف التحريري: ${goal}`,
                `النمط البصري: ${style}`,
                `نسبة الأبعاد: ${ratio}`,
                `الكاميرا: ${camera}`,
                `الإضاءة: ${lighting}`,
                `السلامة: ${safety}`,
                'قيود إلزامية: صورة صحفية واقعية، بدون تضليل، بدون نص داخل الصورة، مساحة عنوان آمنة.',
                `سياق الخبر:\n${articleText}`,
            ].join('\n');

            const res = await journalistServicesApi.imagePrompt(
                editorialBrief,
                style,
                undefined,
                undefined,
                'ar',
                model,
            );

            const base = splitPrompts(String(res?.data?.result || ''));
            const packaged = (base.length ? base : ['']).map((p, i) => {
                const cleaned = p.replace(/^\d+[\).\-\s]*/, '').trim();
                const finalPrompt = buildNanoBananaPrompt(cleaned, ratio, goal, safety, camera, lighting);
                return `برومبت NanoBanana 2 #${i + 1}\n${finalPrompt}`;
            });

            setResult(packaged.join('\n\n--------------------------------\n\n'));
        } finally {
            setBusyImage(false);
        }
    };

    const generateInfographic = async () => {
        setInfStatus('جارٍ التحليل');
        try {
            const analyzeRes = await journalistServicesApi.infographicAnalyze(infText, undefined, undefined, 'ar');
            const data = analyzeRes?.data?.data || null;
            setInfData(data);

            setInfStatus('جارٍ البناء');
            const promptRes = await journalistServicesApi.infographicPrompt(data || {}, undefined, undefined, 'ar', model);
            const basePrompt = cleanResult(promptRes?.data?.result || '');
            setInfPrompt(buildNanoInfographicPrompt(basePrompt, ratio, safety));
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
                    مولد احترافي لبرومبتات NanoBanana 2
                </p>
                <p>
                    الصفحة تبني برومبتات جاهزة للإنتاج البصري الصحفي (صور + إنفوغرافيا) بصيغة واضحة ومباشرة لفريق التصميم.
                </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                <div className="flex items-center gap-2">
                    <Settings2 className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm text-gray-300">إعدادات النموذج والإخراج</h2>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-2">
                    <select className={selectClass} value={model} onChange={(e) => setModel(e.target.value)}>
                        <option value="nanobanana2">NanoBanana 2</option>
                    </select>
                    <select className={selectClass} value={camera} onChange={(e) => setCamera(e.target.value)}>
                        <option>35mm documentary</option>
                        <option>50mm editorial portrait</option>
                        <option>24mm wide field shot</option>
                        <option>70mm compressed scene</option>
                    </select>
                    <select className={selectClass} value={lighting} onChange={(e) => setLighting(e.target.value)}>
                        <option>natural newsroom light</option>
                        <option>golden-hour natural</option>
                        <option>soft overcast daylight</option>
                        <option>controlled studio neutral</option>
                    </select>
                    <select className={selectClass} value={safety} onChange={(e) => setSafety(e.target.value)}>
                        <option>strict-newsroom</option>
                        <option>balanced-editorial</option>
                        <option>high-contrast-safe</option>
                    </select>
                </div>
            </div>

            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-3">
                <div className="flex items-center gap-2">
                    <ImageIcon className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm text-gray-300">مولد برومبتات صورة المقال</h2>
                </div>

                <textarea
                    className="w-full min-h-[180px] p-4 rounded-2xl bg-white/5 border border-white/10 text-white text-sm"
                    placeholder="ألصق نص الخبر أو الملخص التحريري هنا..."
                    value={articleText}
                    onChange={(e) => setArticleText(e.target.value)}
                />

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                    <select className={selectClass} value={goal} onChange={(e) => setGoal(e.target.value)}>
                        <option>خبر عاجل</option>
                        <option>تقرير تحليلي</option>
                        <option>تغطية اقتصادية</option>
                        <option>ملف استقصائي</option>
                    </select>
                    <select className={selectClass} value={style} onChange={(e) => setStyle(e.target.value)}>
                        <option>صحفي واقعي</option>
                        <option>وثائقي</option>
                        <option>تحليلي نظيف</option>
                        <option>درامي مضبوط</option>
                    </select>
                    <select className={selectClass} value={ratio} onChange={(e) => setRatio(e.target.value)}>
                        <option value="16:9">16:9 (الموقع)</option>
                        <option value="4:5">4:5 (Facebook)</option>
                        <option value="1:1">1:1 (عام)</option>
                        <option value="9:16">9:16 (Story)</option>
                    </select>
                </div>

                <button className={btnClass} onClick={generateImagePrompts} disabled={busyImage || !articleText.trim()}>
                    {busyImage ? 'جارٍ التوليد...' : 'توليد برومبتات NanoBanana 2'}
                </button>

                {prompts.length > 0 && (
                    <div className="grid grid-cols-1 gap-3">
                        {prompts.map((p, i) => (
                            <div key={i} className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                                <div className="flex items-center justify-between mb-2">
                                    <span className="text-[11px] text-gray-400">مخرج #{i + 1}</span>
                                    <button
                                        className="text-[11px] text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1"
                                        onClick={() => navigator.clipboard.writeText(p)}
                                    >
                                        <Clipboard className="w-3 h-3" /> نسخ
                                    </button>
                                </div>
                                <pre className="whitespace-pre-wrap text-gray-100 text-xs leading-6">{p}</pre>
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
                    placeholder="ألصق الخبر أو البيانات لبناء إنفوغرافيا احترافية..."
                    value={infText}
                    onChange={(e) => setInfText(e.target.value)}
                />
                <button className={btnClass} onClick={generateInfographic} disabled={!infText.trim()}>
                    تحليل وبناء برومبت NanoBanana 2 للإنفوغرافيا
                </button>
                <p className="text-[11px] text-gray-500 inline-flex items-center gap-1">
                    <SlidersHorizontal className="w-3 h-3" /> الحالة: {infStatus}
                </p>

                <div className="grid grid-cols-1 xl:grid-cols-12 gap-3">
                    <div className="xl:col-span-5 rounded-xl border border-white/10 bg-white/[0.02] p-3">
                        <h3 className="text-xs text-gray-400 mb-2">البيانات المستخرجة</h3>
                        <pre className="whitespace-pre-wrap text-[11px] text-gray-200">{JSON.stringify(infData || {}, null, 2)}</pre>
                    </div>
                    <div className="xl:col-span-7 rounded-xl border border-white/10 bg-white/[0.02] p-3">
                        <div className="flex items-center justify-between mb-2">
                            <h3 className="text-xs text-gray-400">البرومبت النهائي (NanoBanana 2)</h3>
                            <button
                                className="text-[10px] text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1"
                                onClick={() => navigator.clipboard.writeText(infPrompt || '')}
                            >
                                <Clipboard className="w-3 h-3" /> نسخ
                            </button>
                        </div>
                        <pre className="whitespace-pre-wrap text-sm text-gray-200 leading-7">{infPrompt || 'لا يوجد برومبت بعد.'}</pre>
                    </div>
                </div>
            </div>
        </div>
    );
}
