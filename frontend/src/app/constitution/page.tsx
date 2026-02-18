'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    BookOpenCheck,
    CheckCircle2,
    ShieldCheck,
    AlertTriangle,
    CircleHelp,
    RotateCcw,
    Sparkles,
} from 'lucide-react';
import { constitutionApi } from '@/lib/constitution-api';
import { useAuth } from '@/lib/auth';

type ConstitutionGuide = {
    title: string;
    purpose: string;
    principles: string[];
    must_do: string[];
    must_not_do: string[];
    gate_before_final: string[];
    tips: string[];
};

export default function ConstitutionPage() {
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const [checked, setChecked] = useState(false);
    const [tipSeed, setTipSeed] = useState(0);

    const { data: latestData, isLoading: latestLoading } = useQuery({
        queryKey: ['constitution-latest-page'],
        queryFn: () => constitutionApi.latest(),
    });
    const { data: ackData, isLoading: ackLoading } = useQuery({
        queryKey: ['constitution-ack-page'],
        queryFn: () => constitutionApi.ackStatus(),
    });
    const { data: guideData } = useQuery({
        queryKey: ['constitution-guide'],
        queryFn: () => constitutionApi.guide(),
    });

    const latest = latestData?.data;
    const ack = ackData?.data;
    const guide = (guideData?.data || {}) as ConstitutionGuide;
    const tips = guide?.tips || [];
    const loading = latestLoading || ackLoading;

    const ackMutation = useMutation({
        mutationFn: () => constitutionApi.acknowledge(latest?.version),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['constitution-ack'] });
            queryClient.invalidateQueries({ queryKey: ['constitution-ack-page'] });
        },
    });

    const roleWorkflow = useMemo(() => {
        const role = (user?.role || '').toLowerCase();
        if (role === 'journalist' || role === 'print_editor') {
            return [
                'استلام الخبر → تحرير المسودة النهائية داخل المحرر الذكي.',
                'تشغيل التحقق والجودة وSEO قبل الإرسال.',
                'تمرير النسخة إلى رئيس التحرير بعد بوابة السياسة التحريرية.',
            ];
        }
        if (role === 'editor_chief' || role === 'director') {
            return [
                'استلام طلبات الاعتماد مع تقرير السياسة التحريرية.',
                'قرار نهائي: اعتماد أو إعادة للمراجعة مع ملاحظة واضحة.',
                'عند الاعتماد تصبح النسخة جاهزة للنشر اليدوي.',
            ];
        }
        if (role === 'social_media') {
            return [
                'عرض الأخبار المعتمدة فقط.',
                'نسخ مخرجات Facebook / X / Push / Breaking الجاهزة.',
                'بدون تعديل النص التحريري الأصلي.',
            ];
        }
        return ['الالتزام بالدستور التحريري أثناء كل خطوة في غرفة الأخبار.'];
    }, [user?.role]);

    const currentTip = tips.length ? tips[Math.abs(tipSeed) % tips.length] : 'لا توجد نصيحة إضافية حالياً.';

    return (
        <div className="space-y-6" dir="rtl">
            <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-gray-900/70 to-gray-950/80 p-6">
                <div className="flex items-center gap-3">
                    <BookOpenCheck className="w-6 h-6 text-emerald-400" />
                    <div>
                        <h1 className="text-2xl font-bold text-white">{guide.title || 'الدستور التحريري للشروق'}</h1>
                        <p className="text-sm text-gray-400 mt-1">{guide.purpose || 'مرجع تشغيلي دائم لحماية الجودة والثقة.'}</p>
                    </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-3 text-xs">
                    <span className="px-3 py-1 rounded-full bg-white/10 text-gray-200">
                        النسخة الحالية: {latest?.version || 'غير متاحة'}
                    </span>
                    <span
                        className={`px-3 py-1 rounded-full border ${
                            ack?.acknowledged
                                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        }`}
                    >
                        {ack?.acknowledged ? 'تم الإقرار بهذه النسخة' : 'لم يتم الإقرار بعد'}
                    </span>
                </div>
            </section>

            <section className="grid grid-cols-1 xl:grid-cols-12 gap-4">
                <div className="xl:col-span-8 rounded-2xl border border-white/10 bg-gray-900/50 p-5 space-y-4">
                    <h2 className="text-white font-semibold flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-emerald-400" />
                        نصائح عملية أثناء العمل
                    </h2>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {(guide.principles || []).map((item, idx) => (
                            <div key={`p-${idx}`} className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-gray-200">
                                {idx + 1}. {item}
                            </div>
                        ))}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">
                            <p className="font-semibold mb-2">ما يجب فعله</p>
                            <div className="space-y-1">
                                {(guide.must_do || []).map((item, idx) => (
                                    <p key={`do-${idx}`}>{idx + 1}. {item}</p>
                                ))}
                            </div>
                        </div>
                        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                            <p className="font-semibold mb-2">ممنوعات تحريرية</p>
                            <div className="space-y-1">
                                {(guide.must_not_do || []).map((item, idx) => (
                                    <p key={`no-${idx}`}>{idx + 1}. {item}</p>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-sm text-cyan-100">
                        <p className="font-semibold mb-2 flex items-center gap-2">
                            <CircleHelp className="w-4 h-4" />
                            دورك داخل الدورة التحريرية
                        </p>
                        <div className="space-y-1">
                            {roleWorkflow.map((step, idx) => (
                                <p key={step}>{idx + 1}. {step}</p>
                            ))}
                        </div>
                    </div>

                    <div className="rounded-xl border border-orange-500/30 bg-orange-500/10 p-3 text-sm text-orange-100">
                        <p className="font-semibold mb-2 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4" />
                            البوابات قبل الاعتماد النهائي
                        </p>
                        <div className="space-y-1">
                            {(guide.gate_before_final || []).map((item, idx) => (
                                <p key={`gate-${idx}`}>{idx + 1}. {item}</p>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="xl:col-span-4 rounded-2xl border border-white/10 bg-gray-900/50 p-5 space-y-4">
                    <h2 className="text-white font-semibold">إقرار الدستور</h2>

                    <label className="flex items-start gap-2 text-sm text-gray-300">
                        <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => setChecked(e.target.checked)}
                            className="mt-1 accent-emerald-500"
                        />
                        أقر أنني قرأت الدستور التحريري وسألتزم به أثناء العمل التحريري.
                    </label>

                    <button
                        onClick={() => ackMutation.mutate()}
                        disabled={!checked || ackMutation.isPending || !latest?.version || loading}
                        className="w-full h-11 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        <CheckCircle2 className="w-4 h-4" />
                        {ackMutation.isPending ? 'جاري الحفظ...' : 'تأكيد الإقرار'}
                    </button>

                    <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-3 text-sm text-indigo-100 space-y-2">
                        <p className="font-semibold flex items-center gap-2">
                            <Sparkles className="w-4 h-4" />
                            نصيحة من الدستور
                        </p>
                        <p>{currentTip}</p>
                        <button
                            type="button"
                            onClick={() => setTipSeed((s) => s + 1)}
                            className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg bg-white/10 border border-white/20 text-white hover:bg-white/20"
                        >
                            <RotateCcw className="w-3 h-3" /> نصيحة أخرى
                        </button>
                    </div>
                </div>
            </section>
        </div>
    );
}
