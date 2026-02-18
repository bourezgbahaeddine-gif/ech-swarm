'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BookOpenCheck, CheckCircle2, Download, ShieldCheck, AlertTriangle, CircleHelp } from 'lucide-react';
import { constitutionApi } from '@/lib/constitution-api';
import { useAuth } from '@/lib/auth';

const workflowChecklist = [
    'تأكد أن الفقرة الأولى تجيب: ماذا حدث؟ أين؟ متى؟ من؟',
    'أي رقم أو اسم أو تصريح يجب أن يكون له مصدر واضح.',
    'شغّل التحقق + الجودة + SEO قبل إرسال النسخة للاعتماد.',
    'أي معلومة غير مؤكدة يجب وسمها [VERIFY] أو حذفها.',
    'لا يوجد نشر تلقائي: فقط جاهز للنشر اليدوي بعد الاعتماد.',
];

export default function ConstitutionPage() {
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const [checked, setChecked] = useState(false);

    const { data: latestData, isLoading: latestLoading } = useQuery({
        queryKey: ['constitution-latest-page'],
        queryFn: () => constitutionApi.latest(),
    });
    const { data: ackData, isLoading: ackLoading } = useQuery({
        queryKey: ['constitution-ack-page'],
        queryFn: () => constitutionApi.ackStatus(),
    });
    const { data: tipsData } = useQuery({
        queryKey: ['constitution-tips'],
        queryFn: () => constitutionApi.tips(),
    });

    const latest = latestData?.data;
    const ack = ackData?.data;
    const tips = (tipsData?.data?.tips || []) as string[];
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
                'تشغيل التحقق والجودة وSEO من داخل المحرر.',
                'إرسال النسخة إلى رئيس التحرير بعد مرور وكيل السياسة.',
            ];
        }
        if (role === 'editor_chief' || role === 'director') {
            return [
                'استلام طابور الاعتماد مع تقرير وكيل السياسة التحريرية.',
                'القرار النهائي: اعتماد أو إعادة للمراجعة مع ملاحظات.',
                'عند الاعتماد تصبح النسخة جاهزة للنشر اليدوي.',
            ];
        }
        if (role === 'social_media') {
            return [
                'عرض الأخبار المعتمدة فقط.',
                'نسخ نسخ Facebook / X / Push / Breaking الجاهزة.',
                'عدم تعديل النص التحريري الأصلي.',
            ];
        }
        return ['الالتزام بالدستور التحريري أثناء كل خطوة في غرفة الأخبار.'];
    }, [user?.role]);

    return (
        <div className="space-y-6" dir="rtl">
            <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-gray-900/70 to-gray-950/80 p-6">
                <div className="flex items-center gap-3">
                    <BookOpenCheck className="w-6 h-6 text-emerald-400" />
                    <div>
                        <h1 className="text-2xl font-bold text-white">الدستور التحريري التفاعلي</h1>
                        <p className="text-sm text-gray-400 mt-1">مرجع عملي يومي للصحفي، ويعمل كحارس قبل الاعتماد النهائي.</p>
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
                        {workflowChecklist.map((item, idx) => (
                            <div key={item} className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-gray-200">
                                {idx + 1}. {item}
                            </div>
                        ))}
                    </div>

                    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-sm text-cyan-100">
                        <p className="font-semibold mb-2 flex items-center gap-2">
                            <CircleHelp className="w-4 h-4" />
                            ما الذي يراه دورك الآن؟
                        </p>
                        <div className="space-y-1">
                            {roleWorkflow.map((step, idx) => (
                                <p key={step}>{idx + 1}. {step}</p>
                            ))}
                        </div>
                    </div>

                    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                        <p className="font-semibold mb-1 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4" />
                            قاعدة إلزامية قبل الاعتماد النهائي
                        </p>
                        <p>لا يمكن اعتماد النسخة النهائية بدون الإقرار بالدستور ونجاح بوابات التحقق والجودة.</p>
                    </div>
                </div>

                <div className="xl:col-span-4 rounded-2xl border border-white/10 bg-gray-900/50 p-5 space-y-4">
                    <h2 className="text-white font-semibold">إقرار الدستور</h2>
                    <a
                        href={latest?.file_url || '/Constitution.docx'}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition-colors"
                        target="_blank"
                        rel="noreferrer"
                    >
                        <Download className="w-4 h-4" />
                        فتح/تحميل نسخة الدستور
                    </a>

                    <label className="flex items-start gap-2 text-sm text-gray-300">
                        <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => setChecked(e.target.checked)}
                            className="mt-1 accent-emerald-500"
                        />
                        أقر أنني قرأت الدستور وسألتزم به أثناء العمل التحريري.
                    </label>

                    <button
                        onClick={() => ackMutation.mutate()}
                        disabled={!checked || ackMutation.isPending || !latest?.version || loading}
                        className="w-full h-11 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        <CheckCircle2 className="w-4 h-4" />
                        {ackMutation.isPending ? 'جاري الحفظ...' : 'تأكيد الإقرار'}
                    </button>

                    <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-gray-300 space-y-1">
                        <p className="text-gray-400">تلميحات سريعة:</p>
                        {(tips.length ? tips : ['لا توجد نصائح إضافية حالياً.']).map((tip, idx) => (
                            <p key={`${tip}-${idx}`}>- {tip}</p>
                        ))}
                    </div>
                </div>
            </section>
        </div>
    );
}
