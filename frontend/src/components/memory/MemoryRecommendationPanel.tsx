'use client';

import { BookOpen, Sparkles } from 'lucide-react';

import type { ProjectMemoryRecommendation } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';

const subtypeLabels: Record<string, string> = {
    general: 'عام',
    style_rule: 'قاعدة أسلوب',
    editorial_decision: 'قرار تحريري',
    fact_pattern: 'نمط تحقق',
    coverage_lesson: 'درس تغطية',
    source_note: 'ملاحظة مصدر',
    story_context: 'سياق قصة',
    event_playbook: 'Playbook حدث',
    incident_postmortem: 'ما بعد الحادثة',
};

const freshnessLabels: Record<string, string> = {
    stable: 'مستقرة',
    review_soon: 'تراجع قريبًا',
    expired: 'منتهية',
};

type MemoryRecommendationPanelProps = {
    items: ProjectMemoryRecommendation[];
    isLoading?: boolean;
    onMarkUsed?: (itemId: number) => void;
    onQuickCapture?: () => void;
    onOpenLibrary?: () => void;
};

export function MemoryRecommendationPanel({
    items,
    isLoading = false,
    onMarkUsed,
    onQuickCapture,
    onOpenLibrary,
}: MemoryRecommendationPanelProps) {
    return (
        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/[0.05] p-4" dir="rtl">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-[11px] text-emerald-100">
                        <BookOpen className="h-3.5 w-3.5" />
                        الذاكرة التحريرية في هذا السياق
                    </div>
                    <h3 className="mt-2 text-base font-semibold text-white">ما الذي يجب أن تتذكره في هذه المادة؟</h3>
                    <p className="mt-1 text-sm text-slate-300">نعرض فقط العناصر الأكثر صلة بما تعمل عليه الآن، مع سبب الظهور حتى لا تضيع بين العناصر العامة.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                    {onQuickCapture ? (
                        <button onClick={onQuickCapture} className="rounded-xl border border-cyan-500/30 bg-cyan-500/15 px-3 py-2 text-xs text-cyan-100">
                            التقط ملاحظة من العمل الحالي
                        </button>
                    ) : null}
                    {onOpenLibrary ? (
                        <button onClick={onOpenLibrary} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200">
                            افتح مكتبة الذاكرة
                        </button>
                    ) : null}
                </div>
            </div>

            <div className="mt-4 space-y-3">
                {isLoading ? (
                    <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-4 text-sm text-slate-400">جاري تحميل الذاكرة المرتبطة...</div>
                ) : items.length === 0 ? (
                    <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-4 text-sm text-slate-400">
                        لا توجد ذاكرة مرتبطة بهذه المادة بعد. إذا وجدت قرارًا أو درسًا مهمًا، التقطه الآن ليظهر لاحقًا في نفس السياق.
                    </div>
                ) : (
                    items.map((item) => (
                        <div key={item.id} className="rounded-xl border border-white/10 bg-black/20 p-3">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                                <div className="min-w-0 flex-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <h4 className="text-sm font-semibold text-white">{item.title}</h4>
                                        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] text-slate-300">
                                            {subtypeLabels[item.memory_subtype || 'general'] || item.memory_subtype || 'عام'}
                                        </span>
                                        <span className={cn('rounded-full border px-2 py-0.5 text-[10px]', item.freshness_status === 'stable' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : item.freshness_status === 'review_soon' ? 'border-amber-500/30 bg-amber-500/10 text-amber-200' : 'border-red-500/30 bg-red-500/10 text-red-200')}>
                                            {freshnessLabels[item.freshness_status] || item.freshness_status}
                                        </span>
                                    </div>
                                    <p className="mt-2 text-sm leading-7 text-slate-300">{item.content}</p>
                                    <div className="mt-3 rounded-xl border border-cyan-500/20 bg-cyan-500/10 px-3 py-2 text-[11px] text-cyan-100">
                                        <span className="font-medium">لماذا ظهر؟ </span>
                                        {item.recommendation_reason}
                                    </div>
                                </div>
                                <div className="min-w-[120px] text-left">
                                    <div className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">
                                        <Sparkles className="h-3 w-3" />
                                        score {item.recommendation_score}
                                    </div>
                                    <p className="mt-2 text-[11px] text-slate-500">آخر تحديث {formatRelativeTime(item.updated_at)}</p>
                                </div>
                            </div>

                            <div className="mt-3 flex flex-wrap items-center gap-2">
                                {(item.tags || []).slice(0, 4).map((tag) => (
                                    <span key={tag} className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-slate-300">
                                        {tag}
                                    </span>
                                ))}
                                {onMarkUsed ? (
                                    <button onClick={() => onMarkUsed(item.id)} className="mr-auto rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">
                                        استخدمتها الآن
                                    </button>
                                ) : null}
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
