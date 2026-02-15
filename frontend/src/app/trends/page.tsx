'use client';

import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { dashboardApi, type TrendAlert } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
    TrendingUp,
    Radar,
    Flame,
    Lightbulb,
    Search,
    Loader2,
    ArrowUpRight,
    Radio,
    Globe2,
    Tags,
} from 'lucide-react';

const GEO_OPTIONS = [
    { value: 'DZ', label: 'الجزائر' },
    { value: 'GLOBAL', label: 'دولي' },
    { value: 'FR', label: 'فرنسا' },
    { value: 'US', label: 'أمريكا' },
    { value: 'MA', label: 'المغرب' },
    { value: 'TN', label: 'تونس' },
    { value: 'EG', label: 'مصر' },
];

const CATEGORY_OPTIONS = [
    { value: 'all', label: 'كل التصنيفات' },
    { value: 'politics', label: 'سياسة' },
    { value: 'economy', label: 'اقتصاد' },
    { value: 'sports', label: 'رياضة' },
    { value: 'technology', label: 'تكنولوجيا' },
    { value: 'society', label: 'مجتمع' },
    { value: 'international', label: 'دولي' },
    { value: 'general', label: 'عام' },
];

const GEO_LABEL: Record<string, string> = {
    DZ: 'الجزائر',
    MA: 'المغرب',
    TN: 'تونس',
    EG: 'مصر',
    FR: 'فرنسا',
    US: 'أمريكا',
    GB: 'بريطانيا',
    GLOBAL: 'دولي',
};

const CATEGORY_LABEL: Record<string, string> = {
    politics: 'سياسة',
    economy: 'اقتصاد',
    sports: 'رياضة',
    technology: 'تكنولوجيا',
    society: 'مجتمع',
    international: 'دولي',
    general: 'عام',
};

export default function TrendsPage() {
    const [trends, setTrends] = useState<TrendAlert[]>([]);
    const [geo, setGeo] = useState('DZ');
    const [category, setCategory] = useState('all');
    const [limit, setLimit] = useState(12);

    const scanMutation = useMutation({
        mutationFn: () => dashboardApi.triggerTrends({ geo, category, limit, wait: true }),
        onSuccess: (response) => {
            const alerts = response.data?.alerts || [];
            setTrends(alerts);
        },
    });

    const groupedByCategory = useMemo(() => {
        const buckets = new Map<string, TrendAlert[]>();
        for (const item of trends) {
            const key = item.category || 'general';
            const prev = buckets.get(key) || [];
            prev.push(item);
            buckets.set(key, prev);
        }
        return Array.from(buckets.entries()).sort((a, b) => b[1].length - a[1].length);
    }, [trends]);

    const groupedByGeo = useMemo(() => {
        const buckets = new Map<string, number>();
        for (const item of trends) {
            const key = item.geography || 'GLOBAL';
            buckets.set(key, (buckets.get(key) || 0) + 1);
        }
        return Array.from(buckets.entries()).sort((a, b) => b[1] - a[1]);
    }, [trends]);

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <TrendingUp className="w-7 h-7 text-emerald-400" />
                        رادار التراند
                    </h1>
                    <p className="text-sm text-gray-400 mt-1">مسح ترندات فعّال مع تقسيم جغرافي وتصنيفي يخدم غرفة التحرير</p>
                </div>
                <button
                    onClick={() => scanMutation.mutate()}
                    disabled={scanMutation.isPending}
                    className={cn(
                        'flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium transition-all',
                        scanMutation.isPending
                            ? 'bg-amber-500/20 text-amber-300 cursor-wait'
                            : 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-white hover:shadow-lg hover:shadow-emerald-500/20',
                    )}
                >
                    {scanMutation.isPending ? (
                        <>
                            <Loader2 className="w-4 h-4 animate-spin" />
                            جاري المسح...
                        </>
                    ) : (
                        <>
                            <Radar className="w-4 h-4" />
                            مسح الآن
                        </>
                    )}
                </button>
            </div>

            <div className="rounded-2xl bg-gray-900/40 border border-white/10 p-4 grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                    <label className="text-xs text-gray-400 mb-1 block">الجغرافيا</label>
                    <select
                        value={geo}
                        onChange={(e) => setGeo(e.target.value)}
                        className="h-10 w-full px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white"
                    >
                        {GEO_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                                {opt.label}
                            </option>
                        ))}
                    </select>
                </div>
                <div>
                    <label className="text-xs text-gray-400 mb-1 block">التصنيف</label>
                    <select
                        value={category}
                        onChange={(e) => setCategory(e.target.value)}
                        className="h-10 w-full px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white"
                    >
                        {CATEGORY_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                                {opt.label}
                            </option>
                        ))}
                    </select>
                </div>
                <div>
                    <label className="text-xs text-gray-400 mb-1 block">عدد النتائج</label>
                    <select
                        value={limit}
                        onChange={(e) => setLimit(Number(e.target.value))}
                        className="h-10 w-full px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white"
                    >
                        {[8, 12, 16, 20, 24].map((n) => (
                            <option key={n} value={n}>
                                {n}
                            </option>
                        ))}
                    </select>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/20 p-3 flex items-center justify-between">
                    <span className="text-xs text-gray-400">آخر مسح</span>
                    <span className="text-sm text-emerald-300 font-semibold">{trends.length}</span>
                </div>
            </div>

            <div className="rounded-2xl bg-gradient-to-br from-gray-800/30 to-gray-900/40 border border-white/10 p-5">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                    <Radio className="w-4 h-4 text-cyan-400" />
                    كيف يعمل الرادار
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                        { step: '1', title: 'مسح المصادر', desc: 'Google Trends + RSS + منافسين', color: 'text-blue-400' },
                        { step: '2', title: 'تحقق تقاطعي', desc: 'يقبل فقط الترند المؤكد من مصدرين+', color: 'text-purple-400' },
                        { step: '3', title: 'تحليل تحريري', desc: 'زوايا نشر + سبب الصعود + أرشيف', color: 'text-emerald-400' },
                    ].map(({ step, title, desc, color }) => (
                        <div key={step} className="flex items-start gap-3">
                            <div className={cn('w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center text-sm font-bold flex-shrink-0', color)}>
                                {step}
                            </div>
                            <div>
                                <p className="text-sm font-medium text-white">{title}</p>
                                <p className="text-xs text-gray-400 mt-0.5">{desc}</p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {trends.length > 0 && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                            <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                                <Tags className="w-4 h-4 text-amber-300" />
                                التقسيم حسب التصنيف
                            </h4>
                            <div className="flex flex-wrap gap-2">
                                {groupedByCategory.map(([key, items]) => (
                                    <span key={key} className="px-3 py-1 rounded-full text-xs bg-white/5 border border-white/10 text-gray-200">
                                        {CATEGORY_LABEL[key] || key}: {items.length}
                                    </span>
                                ))}
                            </div>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                            <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
                                <Globe2 className="w-4 h-4 text-cyan-300" />
                                التقسيم الجغرافي
                            </h4>
                            <div className="flex flex-wrap gap-2">
                                {groupedByGeo.map(([key, count]) => (
                                    <span key={key} className="px-3 py-1 rounded-full text-xs bg-white/5 border border-white/10 text-gray-200">
                                        {GEO_LABEL[key] || key}: {count}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="space-y-3">
                        {trends.map((trend, index) => (
                            <div
                                key={`${trend.keyword}-${index}`}
                                className="rounded-2xl bg-gradient-to-br from-gray-800/40 to-gray-900/60 border border-white/10 hover:border-emerald-500/30 transition-all p-5"
                            >
                                <div className="flex items-start justify-between mb-3 gap-3">
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center shadow-lg">
                                            <Flame className="w-5 h-5 text-white" />
                                        </div>
                                        <div>
                                            <h3 className="text-base font-bold text-white">{trend.keyword}</h3>
                                            <div className="flex items-center gap-2 mt-1 flex-wrap">
                                                <span className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-[10px] text-emerald-300">
                                                    {CATEGORY_LABEL[trend.category] || trend.category}
                                                </span>
                                                <span className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30 text-[10px] text-cyan-300">
                                                    {GEO_LABEL[trend.geography] || trend.geography}
                                                </span>
                                                {trend.source_signals.map((signal, i) => (
                                                    <span key={i} className="px-1.5 py-0.5 rounded bg-white/5 text-[9px] text-gray-400">
                                                        {signal}
                                                    </span>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2">
                                        <div className="flex gap-0.5">
                                            {Array.from({ length: 10 }).map((_, i) => (
                                                <div
                                                    key={i}
                                                    className={cn(
                                                        'w-2 h-5 rounded-sm transition-all',
                                                        i < trend.strength
                                                            ? i < 4
                                                                ? 'bg-yellow-500'
                                                                : i < 7
                                                                  ? 'bg-orange-500'
                                                                  : 'bg-red-500'
                                                            : 'bg-gray-700',
                                                    )}
                                                />
                                            ))}
                                        </div>
                                        <span className="text-xs font-bold text-white">{trend.strength}/10</span>
                                    </div>
                                </div>

                                {trend.reason && (
                                    <p className="text-sm text-gray-300 mb-3 leading-relaxed" dir="rtl">
                                        {trend.reason}
                                    </p>
                                )}

                                {trend.suggested_angles.length > 0 && (
                                    <div className="mb-3">
                                        <h4 className="text-xs font-semibold text-amber-400 mb-2 flex items-center gap-1">
                                            <Lightbulb className="w-3.5 h-3.5" />
                                            زوايا تحريرية مقترحة
                                        </h4>
                                        <div className="space-y-1">
                                            {trend.suggested_angles.map((angle, i) => (
                                                <div key={i} className="flex items-center gap-2 text-sm text-gray-300">
                                                    <ArrowUpRight className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                                                    {angle}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {trend.archive_matches.length > 0 && (
                                    <div className="flex items-center gap-2 flex-wrap">
                                        <Search className="w-3.5 h-3.5 text-gray-500" />
                                        {trend.archive_matches.map((kw, i) => (
                                            <span key={i} className="px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 text-[10px]">
                                                {kw}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </>
            )}

            {!scanMutation.isPending && trends.length === 0 && (
                <div className="text-center py-20 rounded-2xl bg-gray-800/20 border border-white/10">
                    <Radar className="w-16 h-16 text-gray-700 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold text-white">اضغط "مسح الآن" لبدء الرادار</h3>
                    <p className="text-sm text-gray-500 mt-1">يمكنك تحديد الجغرافيا والتصنيف قبل المسح لنتائج أدق</p>
                </div>
            )}
        </div>
    );
}
