'use client';

import { useState } from 'react';

export function TutorialWelcomeModal({
    open,
    onSelectRole,
    onSkip,
}: {
    open: boolean;
    onSelectRole: (role: 'journalist' | 'editor_chief', pace: 'full' | 'quick') => void;
    onSkip: () => void;
}) {
    const [pace, setPace] = useState<'full' | 'quick'>('full');

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 px-4" dir="rtl">
            <div className="w-full max-w-lg rounded-3xl border border-white/10 bg-slate-950/95 p-6 text-white">
                <div className="text-sm text-cyan-200">مرحبًا بك في غرفة الأخبار</div>
                <h2 className="mt-2 text-2xl font-semibold">اختر الجولة الأنسب لك</h2>
                <p className="mt-3 text-sm text-slate-300 leading-7">
                    هدف الجولة هو إنجاز أول مهمة بسرعة: افتح مادة، عدّلها، ثم أرسلها للاعتماد.
                </p>

                <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 p-3">
                    <div className="text-xs text-slate-300 mb-2">مدة الجولة</div>
                    <div className="flex gap-2">
                        <button
                            onClick={() => setPace('full')}
                            className={`rounded-full px-3 py-1 text-xs border ${pace === 'full' ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-100' : 'border-white/10 bg-white/5 text-slate-300'}`}
                        >
                            دقيقتان (كاملة)
                        </button>
                        <button
                            onClick={() => setPace('quick')}
                            className={`rounded-full px-3 py-1 text-xs border ${pace === 'quick' ? 'border-cyan-400/40 bg-cyan-400/10 text-cyan-100' : 'border-white/10 bg-white/5 text-slate-300'}`}
                        >
                            60 ثانية (سريعة جدًا)
                        </button>
                    </div>
                </div>

                <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <button
                        onClick={() => onSelectRole('journalist', pace)}
                        className="rounded-2xl border border-emerald-500/30 bg-emerald-500/15 px-4 py-3 text-sm text-emerald-100"
                    >
                        أنا صحفي
                    </button>
                    <button
                        onClick={() => onSelectRole('editor_chief', pace)}
                        className="rounded-2xl border border-cyan-500/30 bg-cyan-500/15 px-4 py-3 text-sm text-cyan-100"
                    >
                        أنا رئيس تحرير
                    </button>
                </div>
                <button onClick={onSkip} className="mt-4 text-xs text-slate-400 underline">
                    تخطي الجولة
                </button>
            </div>
        </div>
    );
}
