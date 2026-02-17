'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, CheckCircle2, Download, ShieldCheck, AlertTriangle } from 'lucide-react';
import { constitutionApi } from '@/lib/constitution-api';

export default function ConstitutionPage() {
    const queryClient = useQueryClient();
    const [checked, setChecked] = useState(false);

    const { data: latestData } = useQuery({
        queryKey: ['constitution-latest-page'],
        queryFn: () => constitutionApi.latest(),
    });
    const { data: ackData } = useQuery({
        queryKey: ['constitution-ack-page'],
        queryFn: () => constitutionApi.ackStatus(),
    });
    const { data: tipsData } = useQuery({
        queryKey: ['constitution-tips'],
        queryFn: () => constitutionApi.tips(),
    });

    const latest = latestData?.data;
    const ack = ackData?.data;
    const tips = tipsData?.data?.tips || [];

    const ackMutation = useMutation({
        mutationFn: () => constitutionApi.acknowledge(latest?.version),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['constitution-ack'] });
            queryClient.invalidateQueries({ queryKey: ['constitution-ack-page'] });
        },
    });

    return (
        <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-gradient-to-br from-gray-900/70 to-gray-950/80 p-6">
                <div className="flex items-center gap-3">
                    <FileText className="w-6 h-6 text-emerald-400" />
                    <div>
                        <h1 className="text-2xl font-bold text-white">الدستور التحريري التفاعلي</h1>
                        <p className="text-sm text-gray-400 mt-1">دليل عملي يرافق الصحفي أثناء الكتابة والمراجعة والاعتماد النهائي.</p>
                    </div>
                </div>
                <div className="mt-4 flex flex-wrap gap-3 text-xs">
                    <span className="px-3 py-1 rounded-full bg-white/10 text-gray-200">
                        النسخة الحالية: {latest?.version || 'غير متاحة'}
                    </span>
                    <span
                        className={`px-3 py-1 rounded-full ${
                            ack?.acknowledged
                                ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                                : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        }`}
                    >
                        {ack?.acknowledged ? 'تم الإقرار بهذه النسخة' : 'لم يتم الإقرار بعد'}
                    </span>
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
                <div className="xl:col-span-8 rounded-2xl border border-white/10 bg-gray-900/50 p-5 space-y-4">
                    <h2 className="text-white font-semibold flex items-center gap-2">
                        <ShieldCheck className="w-4 h-4 text-emerald-400" />
                        نصائح عملية أثناء العمل
                    </h2>
                    <div className="space-y-2">
                        {tips.length === 0 ? (
                            <p className="text-sm text-gray-500">لا توجد نصائح متاحة حالياً.</p>
                        ) : (
                            tips.map((tip: string, idx: number) => (
                                <div key={`${tip}-${idx}`} className="rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-gray-200">
                                    {idx + 1}. {tip}
                                </div>
                            ))
                        )}
                    </div>

                    <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-100">
                        <p className="font-semibold mb-1 flex items-center gap-2">
                            <AlertTriangle className="w-4 h-4" />
                            قاعدة إلزامية قبل الاعتماد النهائي
                        </p>
                        <p>لا يمكن اعتماد النسخة النهائية للمقال قبل الإقرار بالدستور ونجاح بوابة الجودة.</p>
                    </div>
                </div>

                <div className="xl:col-span-4 rounded-2xl border border-white/10 bg-gray-900/50 p-5 space-y-4">
                    <h2 className="text-white font-semibold">اعتماد الدستور</h2>
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
                        disabled={!checked || ackMutation.isPending || !latest?.version}
                        className="w-full h-11 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        <CheckCircle2 className="w-4 h-4" />
                        {ackMutation.isPending ? 'جاري الحفظ...' : 'تأكيد الإقرار'}
                    </button>
                </div>
            </div>
        </div>
    );
}
