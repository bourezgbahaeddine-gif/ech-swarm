'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import {
    CalendarClock,
    PlusCircle,
    Search,
    CheckCircle2,
    Eye,
    Trash2,
    Download,
    Ban,
    RotateCcw,
    Link as LinkIcon,
} from 'lucide-react';

import {
    eventsApi,
    type EventMemoItem,
    type EventMemoScope,
    type EventMemoStatus,
} from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';

const WRITE_ROLES = new Set(['director', 'editor_chief', 'journalist', 'social_media', 'print_editor']);
const MANAGE_ROLES = new Set(['director', 'editor_chief']);

function apiErrorMessage(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) return detail;
    }
    if (error instanceof Error && error.message.trim()) return error.message;
    return fallback;
}

function statusLabel(status: string): string {
    const labels: Record<string, string> = {
        planned: 'مخطط',
        monitoring: 'تحت المراقبة',
        covered: 'تمت التغطية',
        dismissed: 'مستبعد',
    };
    return labels[status] || status;
}

function scopeLabel(scope: string): string {
    const labels: Record<string, string> = {
        national: 'وطني',
        international: 'دولي',
        religious: 'ديني',
    };
    return labels[scope] || scope;
}

function statusClass(status: string): string {
    if (status === 'planned') return 'border-blue-500/30 bg-blue-500/10 text-blue-200';
    if (status === 'monitoring') return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
    if (status === 'covered') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200';
    return 'border-gray-500/30 bg-gray-500/10 text-gray-300';
}

export default function EventsPage() {
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canWrite = WRITE_ROLES.has(role);
    const canManage = MANAGE_ROLES.has(role);
    const queryClient = useQueryClient();

    const [q, setQ] = useState('');
    const [scope, setScope] = useState<'all' | EventMemoScope>('all');
    const [statusFilter, setStatusFilter] = useState<'all' | EventMemoStatus>('all');
    const [onlyActive, setOnlyActive] = useState(true);
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [message, setMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const [formTitle, setFormTitle] = useState('');
    const [formSummary, setFormSummary] = useState('');
    const [formPlan, setFormPlan] = useState('');
    const [formSourceUrl, setFormSourceUrl] = useState('');
    const [formScope, setFormScope] = useState<EventMemoScope>('national');
    const [formStartsAt, setFormStartsAt] = useState('');
    const [formLeadHours, setFormLeadHours] = useState(24);
    const [formPriority, setFormPriority] = useState(3);
    const [formTags, setFormTags] = useState('');

    const overviewQuery = useQuery({
        queryKey: ['events-overview'],
        queryFn: () => eventsApi.overview({ window_days: 14 }),
        refetchInterval: 30000,
    });

    const listQuery = useQuery({
        queryKey: ['events-list', q, scope, statusFilter, onlyActive],
        queryFn: () =>
            eventsApi.list({
                q: q || undefined,
                scope: scope === 'all' ? undefined : scope,
                status: statusFilter === 'all' ? undefined : statusFilter,
                only_active: onlyActive,
                page: 1,
                per_page: 500,
            }),
    });

    const items = useMemo(() => (listQuery.data?.data?.items || []) as EventMemoItem[], [listQuery.data?.data?.items]);
    const selected = useMemo(() => items.find((item) => item.id === selectedId) || null, [items, selectedId]);

    const refreshBoard = async () => {
        await queryClient.invalidateQueries({ queryKey: ['events-list'] });
        await queryClient.invalidateQueries({ queryKey: ['events-overview'] });
    };

    const createMutation = useMutation({
        mutationFn: () => {
            const parsed = new Date(formStartsAt);
            if (!formStartsAt || Number.isNaN(parsed.getTime())) throw new Error('تاريخ البداية غير صالح.');
            return eventsApi.create({
                title: formTitle.trim(),
                summary: formSummary.trim() || null,
                coverage_plan: formPlan.trim() || null,
                source_url: formSourceUrl.trim() || null,
                scope: formScope,
                starts_at: parsed.toISOString(),
                lead_time_hours: formLeadHours,
                priority: formPriority,
                tags: formTags.split(',').map((v) => v.trim()).filter(Boolean),
                timezone: 'Africa/Algiers',
            });
        },
        onSuccess: async (res) => {
            setSelectedId(res.data.id);
            setFormTitle('');
            setFormSummary('');
            setFormPlan('');
            setFormSourceUrl('');
            setFormStartsAt('');
            setFormTags('');
            setError(null);
            setMessage('تمت إضافة الحدث إلى لوحة المتابعة.');
            await refreshBoard();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر حفظ الحدث.')),
    });

    const importMutation = useMutation({
        mutationFn: (overwrite = false) => eventsApi.importDb({ overwrite }),
        onSuccess: async (res) => {
            const d = res.data;
            setError(null);
            setMessage(
                `تم استيراد قاعدة الأحداث: جديد ${d.created} | محدث ${d.updated} | متجاوز ${d.skipped} | أخطاء ${d.errors_count}`
            );
            await refreshBoard();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر استيراد ملف قاعدة الأحداث.')),
    });

    const statusMutation = useMutation({
        mutationFn: ({ id, status }: { id: number; status: EventMemoStatus }) => eventsApi.update(id, { status }),
        onSuccess: async () => {
            setError(null);
            await refreshBoard();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تحديث حالة الحدث.')),
    });

    const deleteMutation = useMutation({
        mutationFn: (id: number) => eventsApi.remove(id),
        onSuccess: async () => {
            setSelectedId(null);
            setError(null);
            setMessage('تم حذف الحدث.');
            await refreshBoard();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر حذف الحدث.')),
    });

    const byScope = overviewQuery.data?.data?.by_scope || {};
    const byStatus = overviewQuery.data?.data?.by_status || {};

    return (
        <div className="space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <CalendarClock className="w-6 h-6 text-cyan-300" />
                        لوحة الأحداث
                    </h1>
                    <p className="text-sm text-gray-400 mt-1">
                        مذكرة استباقية للأحداث الوطنية والدولية والدينية التي تستحق التغطية.
                    </p>
                </div>
                {canManage && (
                    <div className="flex gap-2">
                        <button
                            onClick={() => importMutation.mutate(false)}
                            disabled={importMutation.isPending}
                            className="h-10 px-3 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-xs inline-flex items-center gap-1 disabled:opacity-60"
                        >
                            <Download className="w-4 h-4" />
                            استيراد event_db
                        </button>
                        <button
                            onClick={() => importMutation.mutate(true)}
                            disabled={importMutation.isPending}
                            className="h-10 px-3 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs disabled:opacity-60"
                        >
                            استيراد مع تحديث
                        </button>
                    </div>
                )}
            </div>

            {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
            {message && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{message}</div>}

            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-2">
                <StatCard label="نشط" value={overviewQuery.data?.data?.total || 0} />
                <StatCard label="خلال 24 ساعة" value={overviewQuery.data?.data?.upcoming_24h || 0} />
                <StatCard label="خلال 7 أيام" value={overviewQuery.data?.data?.upcoming_7d || 0} />
                <StatCard label="متأخر" value={overviewQuery.data?.data?.overdue || 0} />
                <StatCard label="وطني" value={byScope.national || 0} />
                <StatCard label="دولي" value={byScope.international || 0} />
                <StatCard label="ديني" value={byScope.religious || 0} />
                <StatCard label="مراقبة" value={byStatus.monitoring || 0} />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                <section className="xl:col-span-2 rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                    <div className="flex flex-wrap gap-2 items-center">
                        <div className="relative flex-1 min-w-[220px]">
                            <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                            <input
                                value={q}
                                onChange={(e) => setQ(e.target.value)}
                                placeholder="بحث في عنوان الحدث أو الوصف..."
                                className="w-full h-10 pr-10 pl-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="rtl"
                            />
                        </div>
                        <select
                            value={scope}
                            onChange={(e) => setScope(e.target.value as typeof scope)}
                            className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                        >
                            <option value="all">كل النطاقات</option>
                            <option value="national">وطني</option>
                            <option value="international">دولي</option>
                            <option value="religious">ديني</option>
                        </select>
                        <select
                            value={statusFilter}
                            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
                            className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                        >
                            <option value="all">كل الحالات</option>
                            <option value="planned">مخطط</option>
                            <option value="monitoring">تحت المراقبة</option>
                            <option value="covered">تمت التغطية</option>
                            <option value="dismissed">مستبعد</option>
                        </select>
                        <label className="inline-flex items-center gap-2 text-xs text-gray-300 px-2">
                            <input
                                type="checkbox"
                                checked={onlyActive}
                                onChange={(e) => setOnlyActive(e.target.checked)}
                                className="rounded border-white/20 bg-white/5"
                            />
                            النشط فقط
                        </label>
                    </div>

                    <div className="space-y-2 max-h-[560px] overflow-auto pr-1">
                        {listQuery.isLoading ? (
                            <div className="text-sm text-gray-400 p-3">جاري تحميل الأحداث...</div>
                        ) : items.length === 0 ? (
                            <div className="text-sm text-gray-500 p-3">لا توجد أحداث مطابقة.</div>
                        ) : (
                            items.map((item) => (
                                <button
                                    key={item.id}
                                    onClick={() => setSelectedId(item.id)}
                                    className={cn(
                                        'w-full text-right rounded-xl border px-3 py-3 transition-colors',
                                        selectedId === item.id
                                            ? 'border-cyan-500/40 bg-cyan-500/10'
                                            : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.04]',
                                        item.is_due_soon && 'border-amber-500/40'
                                    )}
                                >
                                    <div className="flex items-start justify-between gap-2">
                                        <p className="text-sm text-white leading-relaxed">{item.title}</p>
                                        <span className={cn('text-[10px] px-2 py-0.5 rounded border', statusClass(item.status))}>
                                            {statusLabel(item.status)}
                                        </span>
                                    </div>
                                    <p className="text-xs text-gray-400 mt-1">{formatDate(item.starts_at)}</p>
                                    <div className="mt-2 flex flex-wrap gap-1">
                                        <span className="text-[10px] px-2 py-0.5 rounded border border-cyan-500/30 text-cyan-200 bg-cyan-500/10">
                                            {scopeLabel(item.scope)}
                                        </span>
                                        {item.is_due_soon && (
                                            <span className="text-[10px] px-2 py-0.5 rounded border border-amber-500/30 text-amber-200 bg-amber-500/10">
                                                نافذة التحضير مفتوحة
                                            </span>
                                        )}
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
                    {selected ? (
                        <>
                            <div className="flex items-start justify-between gap-2">
                                <h2 className="text-white font-semibold leading-relaxed">{selected.title}</h2>
                                <span className={cn('text-[10px] px-2 py-0.5 rounded border', statusClass(selected.status))}>
                                    {statusLabel(selected.status)}
                                </span>
                            </div>
                            <p className="text-xs text-gray-300">النطاق: {scopeLabel(selected.scope)}</p>
                            <p className="text-xs text-gray-300">تاريخ الحدث: {formatDate(selected.starts_at)}</p>
                            <p className="text-xs text-gray-300">بدء التحضير: {formatDate(selected.prep_starts_at)}</p>
                            <p className="text-xs text-gray-400">آخر تحديث: {formatRelativeTime(selected.updated_at)}</p>
                            {selected.summary && <p className="text-sm text-gray-200 whitespace-pre-wrap">{selected.summary}</p>}
                            {selected.coverage_plan && (
                                <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                    <p className="text-xs text-gray-400 mb-1">خطة التغطية:</p>
                                    <p className="text-sm text-gray-200 whitespace-pre-wrap">{selected.coverage_plan}</p>
                                </div>
                            )}
                            {selected.source_url && (
                                <a
                                    href={selected.source_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1 text-xs text-cyan-300 hover:text-cyan-200"
                                >
                                    <LinkIcon className="w-3.5 h-3.5" />
                                    مصدر مرجعي
                                </a>
                            )}
                            {canWrite && (
                                <div className="flex flex-wrap gap-2">
                                    <button
                                        onClick={() => statusMutation.mutate({ id: selected.id, status: 'monitoring' })}
                                        disabled={statusMutation.isPending}
                                        className="px-3 py-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs inline-flex items-center gap-1"
                                    >
                                        <Eye className="w-3.5 h-3.5" />
                                        مراقبة
                                    </button>
                                    <button
                                        onClick={() => statusMutation.mutate({ id: selected.id, status: 'covered' })}
                                        disabled={statusMutation.isPending}
                                        className="px-3 py-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-xs inline-flex items-center gap-1"
                                    >
                                        <CheckCircle2 className="w-3.5 h-3.5" />
                                        تم التغطية
                                    </button>
                                    {canManage && (
                                        <>
                                            <button
                                                onClick={() => statusMutation.mutate({ id: selected.id, status: 'dismissed' })}
                                                disabled={statusMutation.isPending}
                                                className="px-3 py-2 rounded-lg border border-gray-500/30 bg-gray-500/10 text-gray-200 text-xs inline-flex items-center gap-1"
                                            >
                                                <Ban className="w-3.5 h-3.5" />
                                                استبعاد
                                            </button>
                                            <button
                                                onClick={() => statusMutation.mutate({ id: selected.id, status: 'planned' })}
                                                disabled={statusMutation.isPending}
                                                className="px-3 py-2 rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-200 text-xs inline-flex items-center gap-1"
                                            >
                                                <RotateCcw className="w-3.5 h-3.5" />
                                                إعادة للتخطيط
                                            </button>
                                            <button
                                                onClick={() => deleteMutation.mutate(selected.id)}
                                                disabled={deleteMutation.isPending}
                                                className="px-3 py-2 rounded-lg border border-red-500/30 bg-red-500/10 text-red-200 text-xs inline-flex items-center gap-1"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                                حذف
                                            </button>
                                        </>
                                    )}
                                </div>
                            )}
                        </>
                    ) : (
                        <div className="text-sm text-gray-400">اختر حدثًا من القائمة لعرض التفاصيل.</div>
                    )}

                    {canWrite && (
                        <div className="pt-2 border-t border-white/10 space-y-2">
                            <h3 className="text-sm font-semibold text-white inline-flex items-center gap-1">
                                <PlusCircle className="w-4 h-4 text-cyan-300" />
                                إضافة حدث
                            </h3>
                            <input
                                value={formTitle}
                                onChange={(e) => setFormTitle(e.target.value)}
                                placeholder="عنوان الحدث"
                                className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="rtl"
                            />
                            <textarea
                                value={formSummary}
                                onChange={(e) => setFormSummary(e.target.value)}
                                placeholder="ملخص الحدث..."
                                className="w-full min-h-[70px] px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="rtl"
                            />
                            <textarea
                                value={formPlan}
                                onChange={(e) => setFormPlan(e.target.value)}
                                placeholder="خطة التغطية المقترحة..."
                                className="w-full min-h-[70px] px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="rtl"
                            />
                            <input
                                value={formSourceUrl}
                                onChange={(e) => setFormSourceUrl(e.target.value)}
                                placeholder="رابط مرجعي (اختياري)"
                                className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="ltr"
                            />
                            <select
                                value={formScope}
                                onChange={(e) => setFormScope(e.target.value as EventMemoScope)}
                                className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                            >
                                <option value="national">وطني</option>
                                <option value="international">دولي</option>
                                <option value="religious">ديني</option>
                            </select>
                            <input
                                type="datetime-local"
                                value={formStartsAt}
                                onChange={(e) => setFormStartsAt(e.target.value)}
                                className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                            />
                            <div className="grid grid-cols-2 gap-2">
                                <input
                                    type="number"
                                    min={1}
                                    max={336}
                                    value={formLeadHours}
                                    onChange={(e) => setFormLeadHours(Number(e.target.value || 24))}
                                    className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                                    placeholder="ساعات التحضير"
                                />
                                <input
                                    type="number"
                                    min={1}
                                    max={5}
                                    value={formPriority}
                                    onChange={(e) => setFormPriority(Number(e.target.value || 3))}
                                    className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                                    placeholder="الأولوية"
                                />
                            </div>
                            <input
                                value={formTags}
                                onChange={(e) => setFormTags(e.target.value)}
                                placeholder="وسوم: election, summit, ramadan"
                                className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                                dir="ltr"
                            />
                            <button
                                onClick={() => createMutation.mutate()}
                                disabled={createMutation.isPending || !formTitle.trim() || !formStartsAt}
                                className="w-full h-10 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-sm disabled:opacity-50"
                            >
                                {createMutation.isPending ? 'جاري الحفظ...' : 'حفظ الحدث'}
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

