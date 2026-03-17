'use client';

import { useMemo, useState } from 'react';
import { Database, Sparkles, X } from 'lucide-react';

import { cn } from '@/lib/utils';

export type MemorySubtype =
    | 'general'
    | 'style_rule'
    | 'editorial_decision'
    | 'fact_pattern'
    | 'coverage_lesson'
    | 'source_note'
    | 'story_context'
    | 'event_playbook'
    | 'incident_postmortem';

export type MemoryFreshness = 'stable' | 'review_soon' | 'expired';

type MemoryQuickCaptureModalProps = {
    open: boolean;
    onClose: () => void;
    onSubmit: (payload: {
        memory_type: 'operational' | 'knowledge' | 'session';
        memory_subtype: MemorySubtype;
        title: string;
        content: string;
        tags: string[];
        importance: number;
        freshness_status: MemoryFreshness;
        valid_until: string | null;
        note: string | null;
    }) => void;
    isSubmitting?: boolean;
    title?: string;
    articleTitle?: string | null;
    sourceLabel?: string | null;
    suggestedSubtype?: MemorySubtype;
};

const subtypeOptions: Array<{ value: MemorySubtype; label: string; helper: string }> = [
    { value: 'editorial_decision', label: 'قرار تحريري', helper: 'قرار أو توجيه يمكن الرجوع إليه لاحقًا.' },
    { value: 'style_rule', label: 'قاعدة أسلوب', helper: 'قاعدة كتابة أو صياغة يجب تكرارها.' },
    { value: 'fact_pattern', label: 'نمط تحقق', helper: 'ملحوظة أو نمط متكرر في التحقق من الادعاءات.' },
    { value: 'coverage_lesson', label: 'درس تغطية', helper: 'شيء تعلمناه من تغطية مشابهة.' },
    { value: 'source_note', label: 'ملاحظة مصدر', helper: 'تنبيه مرتبط بمصدر أو جهة أو رابط.' },
    { value: 'story_context', label: 'سياق قصة', helper: 'سياق يجب تذكره عند متابعة قصة متكررة.' },
    { value: 'event_playbook', label: 'Playbook حدث', helper: 'قاعدة أو Checklist متكررة لحدث مشابه.' },
    { value: 'incident_postmortem', label: 'ما بعد الحادثة', helper: 'درس من خلل أو مشكلة تشغيلية.' },
    { value: 'general', label: 'عام', helper: 'عنصر مرجعي عام.' },
];

const freshnessOptions: Array<{ value: MemoryFreshness; label: string; helper: string }> = [
    { value: 'stable', label: 'مستقرة', helper: 'صالحة للاستخدام المستمر.' },
    { value: 'review_soon', label: 'تراجع قريبًا', helper: 'ما تزال مفيدة لكن تحتاج مراجعة لاحقًا.' },
    { value: 'expired', label: 'منتهية', helper: 'تبقى للتاريخ فقط ولا توصى يوميًا.' },
];

export function MemoryQuickCaptureModal({
    open,
    onClose,
    onSubmit,
    isSubmitting = false,
    title = 'حفظ في الذاكرة التحريرية',
    articleTitle,
    sourceLabel,
    suggestedSubtype = 'editorial_decision',
}: MemoryQuickCaptureModalProps) {
    const [memoryType, setMemoryType] = useState<'operational' | 'knowledge' | 'session'>('knowledge');
    const [memorySubtype, setMemorySubtype] = useState<MemorySubtype>(suggestedSubtype);
    const [itemTitle, setItemTitle] = useState(articleTitle ? `ملاحظة: ${articleTitle}` : '');
    const [content, setContent] = useState('');
    const [tags, setTags] = useState('');
    const [importance, setImportance] = useState(3);
    const [freshnessStatus, setFreshnessStatus] = useState<MemoryFreshness>('stable');
    const [validUntil, setValidUntil] = useState('');
    const [note, setNote] = useState('تم التقاط هذه الملاحظة أثناء العمل اليومي');

    const selectedSubtype = useMemo(() => subtypeOptions.find((item) => item.value === memorySubtype), [memorySubtype]);
    const selectedFreshness = useMemo(() => freshnessOptions.find((item) => item.value === freshnessStatus), [freshnessStatus]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[120] flex items-center justify-center bg-black/70 p-4" dir="rtl">
            <div className="w-full max-w-2xl rounded-2xl border border-white/10 bg-[#0f172a] shadow-2xl">
                <div className="flex items-start justify-between gap-3 border-b border-white/10 px-5 py-4">
                    <div>
                        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-[11px] text-emerald-100">
                            <Database className="h-3.5 w-3.5" />
                            Quick Capture
                        </div>
                        <h3 className="mt-2 text-lg font-semibold text-white">{title}</h3>
                        <p className="mt-1 text-sm text-slate-300">احفظ قرارًا أو قاعدة أو درسًا بحيث يظهر لاحقًا في سياق العمل المناسب.</p>
                    </div>
                    <button onClick={onClose} className="rounded-xl border border-white/10 bg-white/5 p-2 text-slate-300 hover:text-white">
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <div className="space-y-4 px-5 py-4">
                    {(articleTitle || sourceLabel) && (
                        <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-3 text-xs text-cyan-100">
                            <p>السياق الحالي: {articleTitle || 'بدون عنوان'}</p>
                            {sourceLabel ? <p className="mt-1 text-cyan-200">المصدر: {sourceLabel}</p> : null}
                        </div>
                    )}

                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                        <label className="space-y-1">
                            <span className="text-xs text-slate-300">نوع الذاكرة</span>
                            <select value={memoryType} onChange={(e) => setMemoryType(e.target.value as 'operational' | 'knowledge' | 'session')} className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
                                <option value="knowledge">معرفية</option>
                                <option value="operational">تشغيلية</option>
                                <option value="session">جلسة</option>
                            </select>
                        </label>
                        <label className="space-y-1">
                            <span className="text-xs text-slate-300">الغرض العملي</span>
                            <select value={memorySubtype} onChange={(e) => setMemorySubtype(e.target.value as MemorySubtype)} className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
                                {subtypeOptions.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                            </select>
                            {selectedSubtype ? <p className="text-[11px] text-slate-400">{selectedSubtype.helper}</p> : null}
                        </label>
                    </div>

                    <label className="block space-y-1">
                        <span className="text-xs text-slate-300">عنوان قصير وواضح</span>
                        <input value={itemTitle} onChange={(e) => setItemTitle(e.target.value)} className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="مثال: لا نعتمد هذه الصياغة دون مصدر رسمي" />
                    </label>

                    <label className="block space-y-1">
                        <span className="text-xs text-slate-300">المحتوى العملي</span>
                        <textarea value={content} onChange={(e) => setContent(e.target.value)} className="min-h-[140px] w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="اكتب القرار أو الدرس أو القاعدة بشكل مباشر وقابل للاستخدام لاحقًا..." />
                    </label>

                    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                        <label className="space-y-1">
                            <span className="text-xs text-slate-300">الأهمية</span>
                            <select value={importance} onChange={(e) => setImportance(Number(e.target.value))} className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
                                <option value={1}>1 — منخفضة</option>
                                <option value={2}>2</option>
                                <option value={3}>3 — متوسطة</option>
                                <option value={4}>4</option>
                                <option value={5}>5 — عالية</option>
                            </select>
                        </label>
                        <label className="space-y-1">
                            <span className="text-xs text-slate-300">الصلاحية</span>
                            <select value={freshnessStatus} onChange={(e) => setFreshnessStatus(e.target.value as MemoryFreshness)} className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white">
                                {freshnessOptions.map((option) => (
                                    <option key={option.value} value={option.value}>{option.label}</option>
                                ))}
                            </select>
                            {selectedFreshness ? <p className="text-[11px] text-slate-400">{selectedFreshness.helper}</p> : null}
                        </label>
                        <label className="space-y-1">
                            <span className="text-xs text-slate-300">صالح حتى</span>
                            <input type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white" />
                        </label>
                    </div>

                    <label className="block space-y-1">
                        <span className="text-xs text-slate-300">الوسوم</span>
                        <input value={tags} onChange={(e) => setTags(e.target.value)} dir="ltr" className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="market, economy, source-note" />
                    </label>

                    <label className="block space-y-1">
                        <span className="text-xs text-slate-300">ملاحظة السجل</span>
                        <div className="relative">
                            <Sparkles className="pointer-events-none absolute right-3 top-3 h-4 w-4 text-slate-500" />
                            <input value={note} onChange={(e) => setNote(e.target.value)} className="w-full rounded-xl border border-white/10 bg-white/5 pr-10 px-3 py-2 text-sm text-white placeholder:text-slate-500" placeholder="كيف التقطنا هذا العنصر؟" />
                        </div>
                    </label>
                </div>

                <div className="flex items-center justify-end gap-2 border-t border-white/10 px-5 py-4">
                    <button onClick={onClose} className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200">إلغاء</button>
                    <button
                        disabled={isSubmitting || itemTitle.trim().length < 3 || content.trim().length < 10}
                        onClick={() =>
                            onSubmit({
                                memory_type: memoryType,
                                memory_subtype: memorySubtype,
                                title: itemTitle,
                                content,
                                tags: tags.split(',').map((tag) => tag.trim()).filter(Boolean),
                                importance,
                                freshness_status: freshnessStatus,
                                valid_until: validUntil ? `${validUntil}T00:00:00` : null,
                                note: note.trim() || null,
                            })
                        }
                        className={cn('rounded-xl border px-4 py-2 text-sm', isSubmitting ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-200/70' : 'border-emerald-500/30 bg-emerald-500/15 text-emerald-100')}
                    >
                        {isSubmitting ? 'جاري الحفظ...' : 'حفظ في الذاكرة'}
                    </button>
                </div>
            </div>
        </div>
    );
}
