'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import {
    AlertTriangle,
    CalendarClock,
    CheckCircle2,
    Download,
    Eye,
    Link2,
    PlusCircle,
    Search,
    Sparkles,
    Trash2,
} from 'lucide-react';

import {
    authApi,
    eventsApi,
    type EventActionItem,
    type EventCoverageResponse,
    type EventMemoItem,
    type EventMemoReadiness,
    type EventMemoScope,
    type EventMemoStatus,
} from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';

const WRITE_ROLES = new Set(['director', 'editor_chief', 'journalist', 'social_media', 'print_editor']);
const MANAGE_ROLES = new Set(['director', 'editor_chief']);
type DeskTab = 'now' | 'next24' | 'planning';

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
        monitoring: 'قيد المتابعة',
        covered: 'مكتمل',
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

function readinessLabel(readiness: string): string {
    const labels: Record<string, string> = {
        idea: 'فكرة',
        assigned: 'مُسنَد',
        prepared: 'مُحضّر',
        ready: 'جاهز',
        covered: 'مكتمل',
    };
    return labels[readiness] || readiness;
}

function statusClass(status: string): string {
    if (status === 'planned') return 'border-blue-500/30 bg-blue-500/10 text-blue-200';
    if (status === 'monitoring') return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
    if (status === 'covered') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200';
    return 'border-gray-500/30 bg-gray-500/10 text-gray-300';
}

function severityClass(severity: string): string {
    if (severity === 'high') return 'border-red-500/30 bg-red-500/10 text-red-200';
    if (severity === 'medium') return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
    return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200';
}

function toDate(value: string): Date {
    return new Date(value);
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
    const [tab, setTab] = useState<DeskTab>('now');
    const [onlyActive, setOnlyActive] = useState(true);
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [message, setMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const [formTitle, setFormTitle] = useState('');
    const [formSummary, setFormSummary] = useState('');
    const [formPlan, setFormPlan] = useState('');
    const [formScope, setFormScope] = useState<EventMemoScope>('national');
    const [formStartsAt, setFormStartsAt] = useState('');
    const [formLeadHours, setFormLeadHours] = useState(24);
    const [formPriority, setFormPriority] = useState(3);
    const [formReadiness, setFormReadiness] = useState<EventMemoReadiness>('idea');
    const [formPlaybook, setFormPlaybook] = useState('general');
    const [formSourceUrl, setFormSourceUrl] = useState('');
    const [formOwnerUserId, setFormOwnerUserId] = useState('');

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
                per_page: 300,
            }),
        refetchInterval: 30000,
    });

    const remindersQuery = useQuery({
        queryKey: ['events-reminders'],
        queryFn: () => eventsApi.reminders({ limit: 40 }),
        refetchInterval: 30000,
    });

    const actionsQuery = useQuery({
        queryKey: ['events-action-items'],
        queryFn: () => eventsApi.actionItems({ limit: 20 }),
        refetchInterval: 30000,
    });

    const playbooksQuery = useQuery({
        queryKey: ['events-playbooks'],
        queryFn: () => eventsApi.playbooks(),
    });

    const usersQuery = useQuery({
        queryKey: ['auth-users-event-desk'],
        queryFn: () => authApi.users(),
        enabled: canWrite,
    });

    const coverageQuery = useQuery({
        queryKey: ['events-coverage', selectedId],
        queryFn: () => eventsApi.coverage(selectedId as number),
        enabled: Boolean(selectedId),
        refetchInterval: selectedId ? 30000 : false,
    });

    const items = useMemo(() => (listQuery.data?.data?.items || []) as EventMemoItem[], [listQuery.data?.data?.items]);
    const selected = useMemo(() => items.find((item) => item.id === selectedId) || null, [items, selectedId]);
    const actionItems = actionsQuery.data?.data?.items || [];
    const listError = listQuery.isError ? apiErrorMessage(listQuery.error, 'تعذر تحميل قائمة الأحداث.') : null;
    const coverage = (coverageQuery.data?.data || null) as EventCoverageResponse | null;
    const playbooks = playbooksQuery.data?.data || [];
    const users = usersQuery.data?.data || [];
    const defaultOwnerId = users.find((u) => WRITE_ROLES.has((u.role || '').toLowerCase()))?.id || null;

    const filteredByDesk = useMemo(() => {
        const now = new Date();
        const in24 = new Date(now.getTime() + 24 * 3600 * 1000);
        const in6 = new Date(now.getTime() + 6 * 3600 * 1000);
        return items.filter((item) => {
            const starts = toDate(item.starts_at);
            if (tab === 'now') return starts <= in6;
            if (tab === 'next24') return starts > in6 && starts <= in24;
            return starts > in24;
        });
    }, [items, tab]);

    const refreshBoard = async () => {
        await queryClient.invalidateQueries({ queryKey: ['events-list'] });
        await queryClient.invalidateQueries({ queryKey: ['events-overview'] });
        await queryClient.invalidateQueries({ queryKey: ['events-reminders'] });
        await queryClient.invalidateQueries({ queryKey: ['events-action-items'] });
        await queryClient.invalidateQueries({ queryKey: ['events-coverage'] });
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
                readiness_status: formReadiness,
                playbook_key: formPlaybook,
                owner_user_id: formOwnerUserId ? Number(formOwnerUserId) : null,
                timezone: 'Africa/Algiers',
            });
        },
        onSuccess: async (res) => {
            setSelectedId(res.data.id);
            setFormTitle('');
            setFormSummary('');
            setFormPlan('');
            setFormStartsAt('');
            setFormSourceUrl('');
            setFormOwnerUserId('');
            setError(null);
            setMessage('تمت إضافة الحدث إلى لوحة التشغيل.');
            await refreshBoard();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر حفظ الحدث.')),
    });

    const importMutation = useMutation({
        mutationFn: ({ overwrite }: { overwrite: boolean }) => eventsApi.importDb({ overwrite }),
        onSuccess: async (res) => {
            const d = res.data;
            setError(null);
            setMessage(`استيراد event_db: جديد ${d.created} | محدث ${d.updated} | متجاوز ${d.skipped} | أخطاء ${d.errors_count}`);
            await refreshBoard();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر استيراد ملف قاعدة الأحداث.')),
    });

    const statusMutation = useMutation({
        mutationFn: ({ id, status }: { id: number; status: EventMemoStatus }) => eventsApi.update(id, { status }),
        onSuccess: refreshBoard,
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تحديث حالة الحدث.')),
    });

    const readinessMutation = useMutation({
        mutationFn: ({ id, readiness_status }: { id: number; readiness_status: EventMemoReadiness }) =>
            eventsApi.update(id, { readiness_status }),
        onSuccess: refreshBoard,
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تحديث الجاهزية.')),
    });

    const ownerMutation = useMutation({
        mutationFn: ({ id, owner_user_id }: { id: number; owner_user_id: number }) => eventsApi.update(id, { owner_user_id }),
        onSuccess: refreshBoard,
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تعيين المسؤول.')),
    });

    const storyMutation = useMutation({
        mutationFn: ({ id, story_id, create_if_missing }: { id: number; story_id?: number | null; create_if_missing?: boolean }) =>
            eventsApi.linkStory(id, { story_id, create_if_missing }),
        onSuccess: refreshBoard,
        onError: (err) => setError(apiErrorMessage(err, 'تعذر ربط/إنشاء القصة.')),
    });

    const automationMutation = useMutation({
        mutationFn: (id: number) => eventsApi.runAutomation(id),
        onSuccess: async (res) => {
            const actions = res.data.actions || [];
            setMessage(actions.length > 0 ? `تم تنفيذ الأتمتة: ${actions.join(', ')}` : 'لا توجد إجراءات أتمتة مطلوبة الآن.');
            setError(null);
            await refreshBoard();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تنفيذ الأتمتة.')),
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

    const handleActionItem = async (item: EventActionItem) => {
        setSelectedId(item.event.id);
        if (item.action === 'create_story') {
            storyMutation.mutate({ id: item.event.id, create_if_missing: true });
            return;
        }
        if (item.action === 'assign_owner') {
            if (defaultOwnerId) ownerMutation.mutate({ id: item.event.id, owner_user_id: defaultOwnerId });
            else setError('لا يوجد صحفي متاح للتعيين تلقائياً.');
            return;
        }
        if (item.action === 'prepare_now') {
            readinessMutation.mutate({ id: item.event.id, readiness_status: 'prepared' });
            return;
        }
        if (item.action === 'publish_followup') {
            statusMutation.mutate({ id: item.event.id, status: 'monitoring' });
            return;
        }
        if (item.action === 'raise_readiness') {
            automationMutation.mutate(item.event.id);
            return;
        }
    };

    const overview = overviewQuery.data?.data;
    const reminders = remindersQuery.data?.data || { t24: [], t6: [] };
    const byScope = overview?.by_scope || {};
    const byStatus = overview?.by_status || {};
    const kpi = overview?.kpi || {};

    return (
        <div className="space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <CalendarClock className="w-6 h-6 text-cyan-300" />
                        Event Desk
                    </h1>
                    <p className="text-sm text-gray-400 mt-1">لوحة تشغيل الأحداث: Now / Next 24h / Planning.</p>
                </div>
                {canManage && (
                    <div className="flex gap-2">
                        <button onClick={() => importMutation.mutate({ overwrite: false })} disabled={importMutation.isPending} className="h-10 px-3 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-xs inline-flex items-center gap-1 disabled:opacity-60">
                            <Download className="w-4 h-4" />
                            استيراد event_db
                        </button>
                        <button onClick={() => importMutation.mutate({ overwrite: true })} disabled={importMutation.isPending} className="h-10 px-3 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs disabled:opacity-60">
                            استيراد مع تحديث
                        </button>
                    </div>
                )}
            </div>

            {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
            {message && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">{message}</div>}

            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-8 gap-2">
                <StatCard label="نشط" value={overview?.total || 0} />
                <StatCard label="خلال 24 ساعة" value={overview?.upcoming_24h || 0} />
                <StatCard label="خلال 7 أيام" value={overview?.upcoming_7d || 0} />
                <StatCard label="متأخر" value={overview?.overdue || 0} />
                <StatCard label="وطني" value={byScope.national || 0} />
                <StatCard label="دولي" value={byScope.international || 0} />
                <StatCard label="ديني" value={byScope.religious || 0} />
                <StatCard label="متابعة" value={byStatus.monitoring || 0} />
            </div>

            <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                        <AlertTriangle className="w-4 h-4 text-amber-300" />
                        Action Center
                    </h2>
                    <div className="text-xs text-gray-400">
                        عالي: {actionsQuery.data?.data?.high || 0} • متوسط: {actionsQuery.data?.data?.medium || 0} • منخفض: {actionsQuery.data?.data?.low || 0}
                    </div>
                </div>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
                    {actionItems.length === 0 ? (
                        <div className="text-sm text-gray-500 border border-white/10 rounded-xl px-3 py-3">لا توجد عناصر حرجة حالياً.</div>
                    ) : (
                        actionItems.slice(0, 6).map((item) => (
                            <div key={`${item.code}-${item.event.id}`} className={cn('rounded-xl border px-3 py-3', severityClass(item.severity))}>
                                <p className="text-sm font-semibold">{item.title}</p>
                                <p className="text-xs mt-1 opacity-90">{item.event.title}</p>
                                <p className="text-xs mt-1 opacity-80">{item.recommendation}</p>
                                <div className="mt-2 flex gap-2">
                                    <button onClick={() => handleActionItem(item)} className="text-[11px] px-2 py-1 rounded border border-white/20 bg-white/10 text-white">
                                        تنفيذ الآن
                                    </button>
                                    <button onClick={() => setSelectedId(item.event.id)} className="text-[11px] px-2 py-1 rounded border border-white/20 bg-white/5 text-gray-200">
                                        فتح الحدث
                                    </button>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </section>

            <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                <div className="flex flex-wrap gap-2 items-center justify-between">
                    <div className="flex flex-wrap gap-2">
                        <DeskTabButton active={tab === 'now'} onClick={() => setTab('now')} label="Now" />
                        <DeskTabButton active={tab === 'next24'} onClick={() => setTab('next24')} label="Next 24h" />
                        <DeskTabButton active={tab === 'planning'} onClick={() => setTab('planning')} label="Planning" />
                    </div>
                    <div className="text-xs text-gray-400">Coverage Rate: {Number(kpi.coverage_rate || 0).toFixed(1)}% • On-time Prep: {Number(kpi.on_time_preparation_rate || 0).toFixed(1)}%</div>
                </div>

                <div className="flex flex-wrap gap-2 items-center">
                    <div className="relative flex-1 min-w-[220px]">
                        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="بحث في العنوان أو الوصف..." className="w-full h-10 pr-10 pl-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500" />
                    </div>
                    <select value={scope} onChange={(e) => setScope(e.target.value as typeof scope)} className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200">
                        <option value="all">كل النطاقات</option>
                        <option value="national">وطني</option>
                        <option value="international">دولي</option>
                        <option value="religious">ديني</option>
                    </select>
                    <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)} className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200">
                        <option value="all">كل الحالات</option>
                        <option value="planned">مخطط</option>
                        <option value="monitoring">متابعة</option>
                        <option value="covered">مكتمل</option>
                        <option value="dismissed">مستبعد</option>
                    </select>
                    <label className="inline-flex items-center gap-2 text-xs text-gray-300 px-2">
                        <input type="checkbox" checked={onlyActive} onChange={(e) => setOnlyActive(e.target.checked)} className="rounded border-white/20 bg-white/5" />
                        النشط فقط
                    </label>
                </div>

                <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                    <section className="xl:col-span-2 space-y-2 max-h-[520px] overflow-auto pr-1">
                        {listQuery.isLoading ? (
                            <div className="text-sm text-gray-400 p-3">جارٍ تحميل الأحداث...</div>
                        ) : listError ? (
                            <div className="text-sm text-red-300 p-3">{listError}</div>
                        ) : filteredByDesk.length === 0 ? (
                            <div className="text-sm text-gray-500 p-3">لا توجد عناصر في هذا القسم.</div>
                        ) : (
                            filteredByDesk.map((item) => (
                                <button key={item.id} onClick={() => setSelectedId(item.id)} className={cn('w-full text-right rounded-xl border px-3 py-3 transition-colors', selectedId === item.id ? 'border-cyan-500/40 bg-cyan-500/10' : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.04]')}>
                                    <div className="flex items-start justify-between gap-2">
                                        <p className="text-sm text-white leading-relaxed">{item.title}</p>
                                        <span className={cn('text-[10px] px-2 py-0.5 rounded border', statusClass(item.status))}>{statusLabel(item.status)}</span>
                                    </div>
                                    <p className="text-xs text-gray-400 mt-1">{formatDate(item.starts_at)}</p>
                                    <div className="mt-2 flex flex-wrap gap-1">
                                        <span className="text-[10px] px-2 py-0.5 rounded border border-cyan-500/30 text-cyan-200 bg-cyan-500/10">{scopeLabel(item.scope)}</span>
                                        <span className="text-[10px] px-2 py-0.5 rounded border border-white/10 text-gray-200 bg-white/[0.04]">{readinessLabel(item.readiness_status)}</span>
                                        <span className="text-[10px] px-2 py-0.5 rounded border border-emerald-500/30 text-emerald-200 bg-emerald-500/10">جاهزية {item.readiness_score}%</span>
                                    </div>
                                </button>
                            ))
                        )}
                    </section>

                    <section className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-3">
                        {selected ? (
                            <>
                                <div className="flex items-start justify-between gap-2">
                                    <h3 className="text-white font-semibold leading-relaxed">{selected.title}</h3>
                                    <span className={cn('text-[10px] px-2 py-0.5 rounded border', statusClass(selected.status))}>{statusLabel(selected.status)}</span>
                                </div>
                                <p className="text-xs text-gray-300">التوقيت: {formatDate(selected.starts_at)}</p>
                                <p className="text-xs text-gray-300">المسؤول: {selected.owner_username || '-'}</p>
                                <p className="text-xs text-gray-300">الجاهزية: {selected.readiness_score}%</p>
                                <p className="text-xs text-gray-400">آخر تحديث: {formatRelativeTime(selected.updated_at)}</p>
                                {selected.story_title && <p className="text-xs text-purple-200">{selected.story_title}</p>}
                                <div className="flex flex-wrap gap-2">
                                    <SmallAction onClick={() => statusMutation.mutate({ id: selected.id, status: 'monitoring' })} label="متابعة" icon={Eye} />
                                    <SmallAction onClick={() => readinessMutation.mutate({ id: selected.id, readiness_status: 'ready' })} label="جاهز" icon={CheckCircle2} />
                                    <SmallAction onClick={() => statusMutation.mutate({ id: selected.id, status: 'covered' })} label="مكتمل" icon={CheckCircle2} />
                                    <SmallAction onClick={() => storyMutation.mutate({ id: selected.id, create_if_missing: true })} label="إنشاء قصة" icon={Link2} />
                                    <SmallAction onClick={() => automationMutation.mutate(selected.id)} label="أتمتة" icon={Sparkles} />
                                    {canManage && <SmallAction onClick={() => deleteMutation.mutate(selected.id)} label="حذف" icon={Trash2} />}
                                </div>
                            </>
                        ) : (
                            <div className="text-sm text-gray-400">اختر حدثاً لعرض التفاصيل.</div>
                        )}
                    </section>
                </div>
            </section>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                <section className="xl:col-span-2 rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                    <h3 className="text-sm font-semibold text-white">Coverage Panel</h3>
                    {!selected ? (
                        <p className="text-sm text-gray-500">اختر حدثاً من القائمة لعرض التغطية المرتبطة.</p>
                    ) : coverageQuery.isLoading ? (
                        <p className="text-sm text-gray-400">تحميل تفاصيل التغطية...</p>
                    ) : coverage ? (
                        <>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                <StatCard label="Coverage" value={coverage.coverage_score} />
                                <StatCard label="Readiness" value={coverage.readiness_score} />
                                <StatCard label="Articles" value={coverage.metrics.articles || 0} />
                                <StatCard label="Scripts" value={coverage.metrics.scripts || 0} />
                            </div>
                            <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                <p className="text-xs text-gray-400">Next Best Action</p>
                                <p className="text-sm text-cyan-200 mt-1">{coverage.next_action || 'open_event'}</p>
                            </div>
                            <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                <p className="text-xs text-gray-400 mb-2">Preparation Timeline</p>
                                <div className="space-y-2">
                                    {coverage.timeline.map((step) => (
                                        <div key={step.code} className="flex items-center justify-between text-xs border border-white/10 rounded-lg px-2 py-1">
                                            <span className={cn(step.done ? 'text-emerald-200' : step.is_due ? 'text-amber-200' : 'text-gray-300')}>{step.label} - {step.action}</span>
                                            <span className="text-gray-500">{step.due_at ? formatDate(step.due_at) : '-'}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    ) : (
                        <p className="text-sm text-gray-500">لا توجد بيانات تغطية حالياً.</p>
                    )}
                </section>

                <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                    <h3 className="text-sm font-semibold text-white inline-flex items-center gap-1">
                        <PlusCircle className="w-4 h-4 text-cyan-300" />
                        إضافة حدث
                    </h3>
                    <input value={formTitle} onChange={(e) => setFormTitle(e.target.value)} placeholder="عنوان الحدث" className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500" />
                    <textarea value={formSummary} onChange={(e) => setFormSummary(e.target.value)} placeholder="ملخص الحدث..." className="w-full min-h-[64px] px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500" />
                    <textarea value={formPlan} onChange={(e) => setFormPlan(e.target.value)} placeholder="خطة التغطية..." className="w-full min-h-[64px] px-3 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500" />
                    <input value={formSourceUrl} onChange={(e) => setFormSourceUrl(e.target.value)} placeholder="رابط مرجعي (اختياري)" className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500" />
                    <select value={formScope} onChange={(e) => setFormScope(e.target.value as EventMemoScope)} className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200">
                        <option value="national">وطني</option>
                        <option value="international">دولي</option>
                        <option value="religious">ديني</option>
                    </select>
                    <select value={formReadiness} onChange={(e) => setFormReadiness(e.target.value as EventMemoReadiness)} className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200">
                        <option value="idea">فكرة</option>
                        <option value="assigned">مُسنَد</option>
                        <option value="prepared">مُحضّر</option>
                        <option value="ready">جاهز</option>
                        <option value="covered">مكتمل</option>
                    </select>
                    <select value={formPlaybook} onChange={(e) => setFormPlaybook(e.target.value)} className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200">
                        {playbooks.map((playbook) => (
                            <option key={playbook.key} value={playbook.key}>
                                {playbook.label}
                            </option>
                        ))}
                    </select>
                    <input type="datetime-local" value={formStartsAt} onChange={(e) => setFormStartsAt(e.target.value)} className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200" />
                    <div className="grid grid-cols-2 gap-2">
                        <input type="number" min={1} max={336} value={formLeadHours} onChange={(e) => setFormLeadHours(Number(e.target.value || 24))} className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200" placeholder="Lead hours" />
                        <input type="number" min={1} max={5} value={formPriority} onChange={(e) => setFormPriority(Number(e.target.value || 3))} className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200" placeholder="Priority" />
                    </div>
                    <input value={formOwnerUserId} onChange={(e) => setFormOwnerUserId(e.target.value)} placeholder="Owner user id (اختياري)" className="w-full h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200" />
                    <button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !formTitle.trim() || !formStartsAt} className="w-full h-10 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-sm disabled:opacity-50">
                        {createMutation.isPending ? 'جارٍ الحفظ...' : 'حفظ الحدث'}
                    </button>
                </section>
            </div>

            <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                <h3 className="text-sm font-semibold text-white mb-2">Reminder Windows</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                    <ReminderList title="T-6" items={reminders.t6 || []} />
                    <ReminderList title="T-24" items={reminders.t24 || []} />
                </div>
            </section>
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

function DeskTabButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
    return (
        <button onClick={onClick} className={cn('h-8 px-3 rounded-lg border text-xs', active ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200' : 'border-white/10 bg-white/[0.03] text-gray-300')}>
            {label}
        </button>
    );
}

function SmallAction({
    onClick,
    label,
    icon: Icon,
}: {
    onClick: () => void;
    label: string;
    icon: any;
}) {
    return (
        <button onClick={onClick} className="px-2 py-1 rounded-lg border border-white/20 bg-white/[0.06] text-[11px] text-gray-200 inline-flex items-center gap-1">
            <Icon className="w-3 h-3" />
            {label}
        </button>
    );
}

function ReminderList({ title, items }: { title: string; items: EventMemoItem[] }) {
    return (
        <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <p className="text-gray-300 mb-2">{title}</p>
            {items.length === 0 ? (
                <p className="text-gray-500">لا يوجد</p>
            ) : (
                <ul className="space-y-1">
                    {items.slice(0, 6).map((item) => (
                        <li key={item.id} className="text-gray-300 truncate">
                            {formatDate(item.starts_at)} - {item.title}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
