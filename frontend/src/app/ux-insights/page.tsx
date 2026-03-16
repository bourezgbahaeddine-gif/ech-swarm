'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, BarChart3, MousePointerClick, RefreshCw, Route, Users } from 'lucide-react';

import { telemetryApi, type UxTelemetryRecentItem } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatRelativeTime } from '@/lib/utils';
import { WorkflowHelpPanel } from '@/components/workflow/WorkflowHelpPanel';

const SURFACE_LABELS: Record<string, string> = {
    today: 'اليوم',
    news: 'الأخبار',
    editorial: 'الاعتماد',
    stories: 'القصص',
    workspace_drafts: 'المسودات',
    digital: 'التغطية الرقمية',
};

const EVENT_LABELS: Record<string, string> = {
    surface_view: 'زيارة صفحة',
    next_action_click: 'ضغط الإجراء التالي',
    ui_action: 'إجراء داخل الصفحة',
};

const ROLE_LABELS: Record<string, string> = {
    director: 'المدير',
    editor_chief: 'رئيس التحرير',
    journalist: 'الصحفي',
    social_media: 'السوشيال',
    print_editor: 'النسخة الورقية',
    fact_checker: 'التحقق',
};

function labelSurface(value: string | null | undefined): string {
    if (!value) return '—';
    return SURFACE_LABELS[value] || value;
}

function labelEvent(value: string | null | undefined): string {
    if (!value) return '—';
    return EVENT_LABELS[value] || value;
}

function labelRole(value: string | null | undefined): string {
    if (!value) return '—';
    return ROLE_LABELS[value] || value;
}

export default function UxInsightsPage() {
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canView = role === 'director' || role === 'editor_chief';
    const [days, setDays] = useState(7);

    const summaryQuery = useQuery({
        queryKey: ['ux-telemetry-summary', days],
        queryFn: async () => (await telemetryApi.summary(days)).data,
        enabled: canView,
        refetchInterval: 60_000,
    });

    const recentQuery = useQuery({
        queryKey: ['ux-telemetry-recent'],
        queryFn: async () => (await telemetryApi.recent(30)).data,
        enabled: canView,
        refetchInterval: 60_000,
    });

    const summary = summaryQuery.data;
    const recent = recentQuery.data || [];
    const isLoading = summaryQuery.isLoading || recentQuery.isLoading;
    const hasData = (summary?.total_events || 0) > 0;

    const surfaceRows = useMemo(() => summary?.by_surface || [], [summary?.by_surface]);
    const roleRows = useMemo(() => summary?.by_role || [], [summary?.by_role]);
    const topActions = useMemo(() => summary?.top_actions || [], [summary?.top_actions]);
    const authorFunnel = useMemo(() => summary?.funnels?.author || [], [summary?.funnels?.author]);
    const chiefFunnel = useMemo(() => summary?.funnels?.chief || [], [summary?.funnels?.chief]);

    if (!canView) {
        return (
            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 text-center text-gray-300">
                هذه الصفحة متاحة للمدير ورئيس التحرير فقط.
            </div>
        );
    }

    return (
        <div className="space-y-6" dir="rtl">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <h1 className="inline-flex items-center gap-2 text-2xl font-bold text-white">
                        <BarChart3 className="h-6 w-6 text-cyan-300" />
                        سلوك الاستخدام
                    </h1>
                    <p className="mt-2 text-sm text-slate-400">
                        قراءة مبسطة لكيفية استخدام الصفحات الجديدة: من أين يبدأ المستخدم، وهل يضغط الإجراء التالي فعلًا.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <select
                        value={days}
                        onChange={(e) => setDays(Number(e.target.value))}
                        className="h-10 rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-white focus:outline-none"
                    >
                        <option value={1}>آخر 24 ساعة</option>
                        <option value={7}>آخر 7 أيام</option>
                        <option value={14}>آخر 14 يومًا</option>
                    </select>
                    <button
                        onClick={() => {
                            void summaryQuery.refetch();
                            void recentQuery.refetch();
                        }}
                        className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-200 hover:text-white"
                    >
                        <RefreshCw className="h-4 w-4" />
                        تحديث
                    </button>
                </div>
            </div>

            <WorkflowHelpPanel
                title="كيف نقرأ هذه الصفحة؟"
                items={[
                    {
                        title: 'الدخول',
                        description: 'نقيس أي الصفحات أصبحت نقطة البداية الفعلية، مثل اليوم أو الأخبار أو الاعتماد.',
                    },
                    {
                        title: 'الإجراء التالي',
                        description: 'نقيس هل المستخدم يضغط الزر المقترح داخل الطوابير، لأن هذا أهم مؤشر على نجاح التبسيط.',
                    },
                    {
                        title: 'المسار',
                        description: 'الفَنَل أدناه يوضح هل المستخدم ينتقل من اليوم إلى الأخبار أو الاعتماد ثم يصل إلى المسودات ويتخذ إجراءً فعليًا.',
                    },
                ]}
            />

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                    title="إجمالي الأحداث"
                    value={summary?.total_events || 0}
                    hint="كل زيارات الصفحات والنقرات المسجلة."
                    icon={<Activity className="h-4 w-4 text-cyan-300" />}
                />
                <MetricCard
                    title="زيارات الصفحات"
                    value={summary?.surface_views || 0}
                    hint="عدد مرات دخول المستخدمين إلى الصفحات المقاسة."
                    icon={<Users className="h-4 w-4 text-emerald-300" />}
                />
                <MetricCard
                    title="نقرات الإجراء التالي"
                    value={summary?.next_action_clicks || 0}
                    hint="هل التبسيط يدفع فعلًا إلى الإجراء المقترح؟"
                    icon={<MousePointerClick className="h-4 w-4 text-amber-300" />}
                />
                <MetricCard
                    title="مستخدمون نشطون"
                    value={summary?.unique_users || 0}
                    hint="عدد المستخدمين الذين ظهر لهم استخدام فعلي خلال الفترة."
                    icon={<Users className="h-4 w-4 text-violet-300" />}
                />
            </div>

            {isLoading ? (
                <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 text-center text-slate-400">
                    جاري تحميل قراءة الاستخدام...
                </div>
            ) : !hasData ? (
                <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-6 text-sm text-amber-100">
                    لا توجد بيانات استخدام بعد. افتح الصفحات من المتصفح وسجّل دخولك واضغط بعض أزرار
                    {' '}
                    <span className="font-semibold">الإجراء التالي</span>
                    {' '}
                    ثم أعد التحديث هنا.
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                        <FunnelCard
                            title="مسار الصحفي والمستخدم التنفيذي"
                            hint="هل يصل المستخدم من اليوم إلى الأخبار ثم إلى المسودات ثم يضغط الإجراء التالي؟"
                            steps={authorFunnel}
                        />
                        <FunnelCard
                            title="مسار رئيس التحرير"
                            hint="هل ينتقل رئيس التحرير من اليوم إلى الاعتماد ثم إلى المسودات ثم يحسم الإجراء التالي؟"
                            steps={chiefFunnel}
                        />
                    </div>

                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.2fr_0.8fr]">
                        <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                            <h2 className="text-sm font-semibold text-white">السطوح الأكثر استخدامًا</h2>
                            <div className="mt-4 space-y-3">
                                {surfaceRows.map((item) => (
                                    <div key={item.surface} className="rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="flex items-center justify-between gap-3">
                                            <div>
                                                <div className="text-sm font-medium text-white">{labelSurface(item.surface)}</div>
                                                <div className="mt-1 text-[11px] text-slate-400">
                                                    زيارات: {item.surface_views} • الإجراء التالي: {item.next_action_clicks} • تفاعلات أخرى: {item.ui_actions}
                                                </div>
                                            </div>
                                            <div className="text-lg font-semibold text-cyan-200">{item.total_events}</div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>

                        <section className="space-y-6">
                            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                                <h2 className="text-sm font-semibold text-white">الاستخدام حسب الدور</h2>
                                <div className="mt-4 space-y-3">
                                    {roleRows.map((item) => (
                                        <div key={item.role} className="rounded-xl border border-white/10 bg-black/20 p-3">
                                            <div className="text-sm font-medium text-white">{labelRole(item.role)}</div>
                                            <div className="mt-1 text-[11px] text-slate-400">
                                                إجمالي: {item.total_events} • زيارات: {item.surface_views} • الإجراء التالي: {item.next_action_clicks}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                                <h2 className="text-sm font-semibold text-white">أكثر الإجراءات استخدامًا</h2>
                                <div className="mt-4 space-y-2">
                                    {topActions.slice(0, 8).map((item) => (
                                        <div key={item.action_label} className="flex items-center justify-between rounded-xl border border-white/10 bg-black/20 px-3 py-2">
                                            <span className="text-sm text-slate-200">{item.action_label}</span>
                                            <span className="text-xs text-cyan-200">{item.total}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </section>
                    </div>
                </>
            )}

            <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                <h2 className="text-sm font-semibold text-white">آخر الأحداث المسجلة</h2>
                <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b border-white/10 text-slate-400">
                                <th className="py-2 text-right">الوقت</th>
                                <th className="py-2 text-right">المستخدم</th>
                                <th className="py-2 text-right">الدور</th>
                                <th className="py-2 text-right">السطح</th>
                                <th className="py-2 text-right">الحدث</th>
                                <th className="py-2 text-right">الإجراء</th>
                            </tr>
                        </thead>
                        <tbody>
                            {recent.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="py-6 text-center text-slate-500">
                                        لا توجد أحداث مسجلة بعد.
                                    </td>
                                </tr>
                            ) : (
                                recent.map((item) => <RecentRow key={item.id} item={item} />)
                            )}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}

function MetricCard({
    title,
    value,
    hint,
    icon,
}: {
    title: string;
    value: number;
    hint: string;
    icon: ReactNode;
}) {
    return (
        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
            <div className="flex items-center gap-2 text-white">
                {icon}
                <span className="text-sm font-medium">{title}</span>
            </div>
            <div className="mt-3 text-2xl font-bold text-white">{value}</div>
            <div className="mt-2 text-xs leading-6 text-slate-400">{hint}</div>
        </div>
    );
}

function FunnelCard({
    title,
    hint,
    steps,
}: {
    title: string;
    hint: string;
    steps: Array<{ step: string; label: string; users: number }>;
}) {
    const peak = Math.max(...steps.map((step) => step.users), 1);

    return (
        <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
            <div className="flex items-center gap-2 text-white">
                <Route className="h-4 w-4 text-cyan-300" />
                <h2 className="text-sm font-semibold">{title}</h2>
            </div>
            <p className="mt-2 text-xs leading-6 text-slate-400">{hint}</p>
            <div className="mt-4 space-y-3">
                {steps.map((step, index) => (
                    <div key={step.step} className="rounded-xl border border-white/10 bg-black/20 p-3">
                        <div className="flex items-center justify-between gap-3">
                            <div>
                                <div className="text-sm font-medium text-white">
                                    {index + 1}. {step.label}
                                </div>
                                <div className="mt-1 text-[11px] text-slate-400">
                                    مستخدمون وصلوا إلى هذه المرحلة خلال الفترة المحددة
                                </div>
                            </div>
                            <div className="text-lg font-semibold text-cyan-200">{step.users}</div>
                        </div>
                        <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/5">
                            <div
                                className="h-full rounded-full bg-cyan-400/80 transition-all"
                                style={{ width: `${Math.max((step.users / peak) * 100, 6)}%` }}
                            />
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}

function RecentRow({ item }: { item: UxTelemetryRecentItem }) {
    return (
        <tr className="border-b border-white/5 text-slate-200">
            <td className="py-3">{item.created_at ? formatRelativeTime(item.created_at) : '—'}</td>
            <td className="py-3">{item.actor_username || '—'}</td>
            <td className="py-3 text-slate-400">{labelRole(item.actor_role)}</td>
            <td className="py-3">{labelSurface(item.surface)}</td>
            <td className="py-3">
                <span
                    className={cn(
                        'rounded-md border px-2 py-0.5 text-[11px]',
                        item.event_name === 'next_action_click'
                            ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                            : item.event_name === 'surface_view'
                              ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200'
                              : 'border-white/10 bg-white/5 text-slate-300',
                    )}
                >
                    {labelEvent(item.event_name)}
                </span>
            </td>
            <td className="py-3">{item.action_label || '—'}</td>
        </tr>
    );
}
