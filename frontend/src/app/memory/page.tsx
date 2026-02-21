'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { Database, PlusCircle, Search, Clock3, Archive, CheckCircle2 } from 'lucide-react';

import { memoryApi, type ProjectMemoryItem } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatRelativeTime } from '@/lib/utils';

function apiErrorMessage(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) return detail;
    }
    return fallback;
}

const WRITE_ROLES = new Set(['director', 'editor_chief', 'journalist', 'social_media', 'print_editor']);
const MANAGE_ROLES = new Set(['director', 'editor_chief']);

export default function MemoryPage() {
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canWrite = WRITE_ROLES.has(role);
    const canManage = MANAGE_ROLES.has(role);
    const queryClient = useQueryClient();

    const [q, setQ] = useState('');
    const [memoryType, setMemoryType] = useState<'all' | 'operational' | 'knowledge' | 'session'>('all');
    const [statusFilter, setStatusFilter] = useState<'active' | 'archived'>('active');
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [formType, setFormType] = useState<'operational' | 'knowledge' | 'session'>('operational');
    const [formTitle, setFormTitle] = useState('');
    const [formContent, setFormContent] = useState('');
    const [formTags, setFormTags] = useState('');
    const [message, setMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const { data: overviewData } = useQuery({
        queryKey: ['memory-overview'],
        queryFn: () => memoryApi.overview(),
        refetchInterval: 20000,
    });

    const { data: listData, isLoading } = useQuery({
        queryKey: ['memory-items', q, memoryType, statusFilter],
        queryFn: () =>
            memoryApi.list({
                q: q || undefined,
                memory_type: memoryType === 'all' ? undefined : memoryType,
                status: statusFilter,
                per_page: 50,
                page: 1,
            }),
    });

    const items = useMemo(() => (listData?.data?.items || []) as ProjectMemoryItem[], [listData?.data?.items]);
    const selectedItem = useMemo(() => items.find((i) => i.id === selectedId) || null, [items, selectedId]);

    const { data: eventsData } = useQuery({
        queryKey: ['memory-events', selectedId],
        queryFn: () => memoryApi.events(selectedId as number, 20),
        enabled: !!selectedId,
    });

    const createMutation = useMutation({
        mutationFn: () =>
            memoryApi.create({
                memory_type: formType,
                title: formTitle,
                content: formContent,
                tags: formTags
                    .split(',')
                    .map((v) => v.trim())
                    .filter(Boolean),
            }),
        onSuccess: async (res) => {
            setSelectedId(res.data.id);
            setFormTitle('');
            setFormContent('');
            setFormTags('');
            setError(null);
            setMessage('تمت إضافة عنصر جديد إلى ذاكرة المشروع.');
            await queryClient.invalidateQueries({ queryKey: ['memory-items'] });
            await queryClient.invalidateQueries({ queryKey: ['memory-overview'] });
        },
        onError: (err) => setError(apiErrorMessage(err, 'فشل إضافة عنصر الذاكرة.')),
    });

    const markUsedMutation = useMutation({
        mutationFn: (itemId: number) => memoryApi.markUsed(itemId, 'تم استخدام العنصر أثناء العمل التحريري'),
        onSuccess: async () => {
            setError(null);
            setMessage('تم تسجيل استخدام عنصر الذاكرة.');
            await queryClient.invalidateQueries({ queryKey: ['memory-events', selectedId] });
            await queryClient.invalidateQueries({ queryKey: ['memory-items'] });
            await queryClient.invalidateQueries({ queryKey: ['memory-overview'] });
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تسجيل الاستخدام.')),
    });

    const archiveMutation = useMutation({
        mutationFn: (item: ProjectMemoryItem) =>
            memoryApi.update(item.id, { status: item.status === 'active' ? 'archived' : 'active' }),
        onSuccess: async () => {
            setError(null);
            setMessage('تم تحديث حالة عنصر الذاكرة.');
            await queryClient.invalidateQueries({ queryKey: ['memory-items'] });
            await queryClient.invalidateQueries({ queryKey: ['memory-overview'] });
            await queryClient.invalidateQueries({ queryKey: ['memory-events', selectedId] });
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تحديث الحالة.')),
    });

    return (
        <div className="space-y-5">
            <div>
                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                    <Database className="w-6 h-6 text-emerald-400" />
                    ذاكرة المشروع
                </h1>
                <p className="text-sm text-gray-400 mt-1">مرجع موحّد للقرارات، الأعطال، الدروس، وإرشادات التشغيل.</p>
            </div>

            {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
            {message && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{message}</div>}

            <div className="grid grid-cols-1 md:grid-cols-6 gap-2">
                <StatCard label="نشط" value={overviewData?.data?.total_active || 0} />
                <StatCard label="تشغيلي" value={overviewData?.data?.operational_count || 0} />
                <StatCard label="معرفي" value={overviewData?.data?.knowledge_count || 0} />
                <StatCard label="جلسات" value={overviewData?.data?.session_count || 0} />
                <StatCard label="مؤرشف" value={overviewData?.data?.archived_count || 0} />
                <StatCard label="آخر 24 ساعة" value={overviewData?.data?.recent_updates || 0} />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                <section className="xl:col-span-2 rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                    <div className="flex flex-wrap gap-2 items-center">
                        <div className="relative flex-1 min-w-[220px]">
                            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                            <input
                                value={q}
                                onChange={(e) => setQ(e.target.value)}
                                placeholder="ابحث في العنوان أو المحتوى..."
                                className="w-full h-10 pr-10 pl-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="rtl"
                            />
                        </div>
                        <select
                            value={memoryType}
                            onChange={(e) => setMemoryType(e.target.value as typeof memoryType)}
                            className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                        >
                            <option value="all">كل الأنواع</option>
                            <option value="operational">تشغيلي</option>
                            <option value="knowledge">معرفي</option>
                            <option value="session">جلسة</option>
                        </select>
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
                            className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                        >
                            <option value="active">نشط</option>
                            <option value="archived">مؤرشف</option>
                        </select>
                    </div>

                    <div className="space-y-2 max-h-[520px] overflow-auto pr-1">
                        {isLoading ? (
                            <div className="text-sm text-gray-400 p-3">جاري تحميل عناصر الذاكرة...</div>
                        ) : items.length === 0 ? (
                            <div className="text-sm text-gray-500 p-3">لا توجد عناصر مطابقة.</div>
                        ) : (
                            items.map((item) => (
                                <button
                                    key={item.id}
                                    onClick={() => setSelectedId(item.id)}
                                    className={cn(
                                        'w-full text-right rounded-xl border px-3 py-3 transition-colors',
                                        selectedId === item.id
                                            ? 'border-emerald-500/40 bg-emerald-500/10'
                                            : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.04]'
                                    )}
                                >
                                    <div className="flex items-start justify-between gap-2">
                                        <p className="text-sm text-white leading-relaxed">{item.title}</p>
                                        <span className="text-[11px] text-gray-400 whitespace-nowrap">
                                            {formatRelativeTime(item.updated_at)}
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-400 mt-1 line-clamp-2">{item.content}</p>
                                    <div className="mt-2 flex flex-wrap gap-1">
                                        <span className="text-[10px] px-2 py-0.5 rounded border border-cyan-500/30 text-cyan-200 bg-cyan-500/10">{item.memory_type}</span>
                                        {item.tags.slice(0, 3).map((tag) => (
                                            <span key={tag} className="text-[10px] px-2 py-0.5 rounded border border-white/10 text-gray-300 bg-white/[0.04]">
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                </button>
                            ))
                        )}
                    </div>
                </section>

                <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                    {selectedItem ? (
                        <>
                            <div className="flex items-start justify-between gap-2">
                                <h2 className="text-white font-semibold leading-relaxed">{selectedItem.title}</h2>
                                <span className="text-[11px] text-gray-400">{selectedItem.status}</span>
                            </div>
                            <p className="text-sm text-gray-200 whitespace-pre-wrap">{selectedItem.content}</p>
                            <div className="flex flex-wrap gap-1">
                                {selectedItem.tags.map((tag) => (
                                    <span key={tag} className="text-[10px] px-2 py-0.5 rounded border border-white/10 text-gray-300 bg-white/[0.04]">
                                        {tag}
                                    </span>
                                ))}
                            </div>
                            <div className="flex flex-wrap gap-2">
                                <button
                                    onClick={() => markUsedMutation.mutate(selectedItem.id)}
                                    disabled={markUsedMutation.isPending}
                                    className="px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-xs"
                                >
                                    <span className="inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> تم الاستخدام</span>
                                </button>
                                {canManage && (
                                    <button
                                        onClick={() => archiveMutation.mutate(selectedItem)}
                                        disabled={archiveMutation.isPending}
                                        className="px-3 py-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs"
                                    >
                                        <span className="inline-flex items-center gap-1"><Archive className="w-3.5 h-3.5" /> {selectedItem.status === 'active' ? 'أرشفة' : 'إعادة تفعيل'}</span>
                                    </button>
                                )}
                            </div>
                            <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                <p className="text-xs text-gray-400 mb-2 inline-flex items-center gap-1"><Clock3 className="w-3.5 h-3.5" /> سجل الاستخدام</p>
                                <div className="space-y-1 max-h-44 overflow-auto">
                                    {(eventsData?.data || []).length === 0 ? (
                                        <p className="text-xs text-gray-500">لا توجد أحداث بعد.</p>
                                    ) : (
                                        (eventsData?.data || []).map((ev) => (
                                            <p key={ev.id} className="text-xs text-gray-300">
                                                {ev.event_type} — {ev.actor_username || 'system'} — {formatRelativeTime(ev.created_at)}
                                            </p>
                                        ))
                                    )}
                                </div>
                            </div>
                        </>
                    ) : (
                        <div className="text-sm text-gray-400">اختر عنصرًا من القائمة لعرض التفاصيل.</div>
                    )}

                    {canWrite && (
                        <div className="pt-2 border-t border-white/10 space-y-2">
                            <h3 className="text-sm font-semibold text-white inline-flex items-center gap-1">
                                <PlusCircle className="w-4 h-4 text-emerald-400" />
                                إضافة عنصر جديد
                            </h3>
                            <select
                                value={formType}
                                onChange={(e) => setFormType(e.target.value as typeof formType)}
                                className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                            >
                                <option value="operational">تشغيلي</option>
                                <option value="knowledge">معرفي</option>
                                <option value="session">جلسة</option>
                            </select>
                            <input
                                value={formTitle}
                                onChange={(e) => setFormTitle(e.target.value)}
                                placeholder="عنوان مختصر وواضح"
                                className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="rtl"
                            />
                            <textarea
                                value={formContent}
                                onChange={(e) => setFormContent(e.target.value)}
                                placeholder="وصف المشكلة/القرار/الحل بشكل عملي..."
                                className="w-full min-h-[110px] px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="rtl"
                            />
                            <input
                                value={formTags}
                                onChange={(e) => setFormTags(e.target.value)}
                                placeholder="وسوم مفصولة بفاصلة: auth,telegram,migration"
                                className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="ltr"
                            />
                            <button
                                onClick={() => createMutation.mutate()}
                                disabled={createMutation.isPending || !formTitle.trim() || !formContent.trim()}
                                className="w-full h-10 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-sm disabled:opacity-50"
                            >
                                {createMutation.isPending ? 'جاري الحفظ...' : 'حفظ في الذاكرة'}
                            </button>
                        </div>
                    )}
                </section>
            </div>
        </div>
    );
}

function StatCard({ label, value }: { label: string; value: number }) {
    return (
        <div className="rounded-xl border border-white/10 bg-gray-900/35 px-3 py-2">
            <p className="text-[11px] text-gray-400">{label}</p>
            <p className="text-lg font-semibold text-white mt-1">{value}</p>
        </div>
    );
}
