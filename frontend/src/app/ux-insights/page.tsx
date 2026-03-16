'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity, BarChart3, MousePointerClick, RefreshCw, Route, TrendingDown, Users } from 'lucide-react';

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

type FunnelStep = {
    step: string;
    label: string;
    users: number;
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

function percent(value: number, total: number): string {
    if (!total) return '0%';
    return `${Math.round((value / total) * 100)}%`;
}

function conversionRate(surfaceViews: number, nextActionClicks: number): number {
    if (!surfaceViews) return 0;
    return Math.round((nextActionClicks / surfaceViews) * 100);
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

    const weakSurfaces = useMemo(
        () =>
            surfaceRows
                .filter((item) => item.surface_views > 0)
                .map((item) => ({
                    ...item,
                    conversion: conversionRate(item.surface_views, item.next_action_clicks),
                }))
                .sort((a, b) => a.conversion - b.conversion)
                .slice(0, 4),
        [surfaceRows],
    );

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
                        قراءة مبسطة لكيفية استخدام الصفحات الجديدة: من أين يبدأ المستخدم، وأين يتقدم، وأين يتوقف قبل تنفيذ الإجراء التالي.
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
                        description: 'نقيس أي الصفحات أصبحت نقطة البداية الفعلية مثل اليوم أو الأخبار أو الاعتماد.',
                    },
                    {
                        title: 'الإجراء التالي',
                        description: 'أهم مؤشر هنا هو هل يضغط المستخدم الزر المقترح أم يكتفي بالمشاهدة فقط.',
                    },
                    {
                        title: 'التسرب',
                        description: 'إذا كانت الصفحة تُزار كثيرًا لكن التحويل فيها ضعيف، فهذا يعني أن التبسيط لم يصل بعد إلى الخطوة العملية الواضحة.',
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
                    لا توجد بيانات استخدام بعد. افتح الصفحات من المتصفح وسجّل دخولك واضغط بعض أزرار <span className="font-semibold">الإجراء التالي</span> ثم أعد التحديث هنا.
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
                        <FunnelCard
                            title="مسار الصحفي والمستخدم التنفيذي"
                            hint="هل يصل المستخدم من اليوم إلى الأخبار ثم إلى المسودات ثم يتخذ إجراءً فعليًا؟"
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
                            <div className="flex items-center gap-2 text-sm font-semibold text-white">
                                <TrendingDown className="h-4 w-4 text-amber-300" />
                                أين يحدث التسرب أكثر؟
                            </div>
                            <div className="mt-4 space-y-3">
                                {weakSurfaces.map((item) => (
                                    <div key={item.surface} className="rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="flex items-center justify-between gap-3">
                                            <div>
                                                <div className="text-sm font-medium text-white">{labelSurface(item.surface)}</div>
                                                <div className="mt-1 text-[11px] text-slate-400">
                                                    زيارات: {item.surface_views} • الإجراء التالي: {item.next_action_clicks} • التحويل: {item.conversion}%
                                                </div>
                                            </div>
                                            <div
                                                className={cn(
                                                    'rounded-full px-2 py-1 text-[11px] font-medium',
                                                    item.conversion >= 40
                                                        ? 'bg-emerald-500/15 text-emerald-200'
                                                        : item.conversion >= 20
                                                            ? 'bg-amber-500/15 text-amber-200'
                                                            : 'bg-rose-500/15 text-rose-200',
                                                )}
                                            >
                                                {item.conversion >= 40 ? 'جيد' : item.conversion >= 20 ? 'متوسط' : 'ضعيف'}
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </section>

                        <section className="space-y-6">
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
                        </section>
                    </div>

                    <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                        <h2 className="text-sm font-semibold text-white">السطوح الأكثر استخدامًا</h2>
                        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                            {surfaceRows.map((item) => {
                                const rate = conversionRate(item.surface_views, item.next_action_clicks);
                                return (
                                    <div key={item.surface} className="rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="flex items-center justify-between gap-3">
                                            <div className="text-sm font-medium text-white">{labelSurface(item.surface)}</div>
                                            <div className="text-xs text-cyan-200">{percent(item.next_action_clicks, item.surface_views)}</div>
                                        </div>
                                        <div className="mt-2 text-[11px] text-slate-400">
                                            زيارات: {item.surface_views} • الإجراء التالي: {item.next_action_clicks} • تفاعلات أخرى: {item.ui_actions}
                                        </div>
                                        <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/5">
                                            <div
                                                className={cn(
                                                    'h-full rounded-full',
                                                    rate >= 40 ? 'bg-emerald-400' : rate >= 20 ? 'bg-amber-400' : 'bg-rose-400',
                                                )}
                                                style={{ width: `${Math.max(rate, 6)}%` }}
                                            />
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </section>
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
                            {recent.map((item) => (
                                <RecentRow key={item.id} item={item} />
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </div>
    );
}

function MetricCard({ title, value, hint, icon }: { title: string; value: number; hint: string; icon: ReactNode }) {
    return (
        <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <div className="text-sm font-semibold text-white">{title}</div>
                    <div className="mt-1 text-[11px] text-slate-400">{hint}</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-white/5 p-2">{icon}</div>
            </div>
            <div className="mt-4 text-3xl font-bold text-white">{value}</div>
        </div>
    );
}

function FunnelCard({ title, hint, steps }: { title: string; hint: string; steps: FunnelStep[] }) {
    const maxUsers = Math.max(...steps.map((step) => step.users), 1);
    return (
        <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-white">
                <Route className="h-4 w-4 text-cyan-300" />
                {title}
            </div>
            <p className="mt-1 text-[11px] text-slate-400">{hint}</p>
            <div className="mt-4 space-y-3">
                {steps.map((step, index) => {
                    const previous = index === 0 ? step.users : steps[index - 1]?.users || 0;
                    const drop = index === 0 ? null : Math.max(previous - step.users, 0);
                    const width = Math.max(Math.round((step.users / maxUsers) * 100), 8);
                    return (
                        <div key={step.step} className="rounded-xl border border-white/10 bg-black/20 p-3">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <div className="text-sm font-medium text-white">{step.label}</div>
                                    <div className="mt-1 text-[11px] text-slate-400">
                                        {index === 0 ? 'نقطة الدخول' : `الاحتفاظ من الخطوة السابقة: ${percent(step.users, previous || 1)}`}
                                    </div>
                                </div>
                                <div className="text-lg font-semibold text-cyan-200">{step.users}</div>
                            </div>
                            <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/5">
                                <div className="h-full rounded-full bg-cyan-400" style={{ width: `${width}%` }} />
                            </div>
                            {drop !== null && (
                                <div className="mt-2 text-[11px] text-amber-200">
                                    التسرب من الخطوة السابقة: {drop}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </section>
    );
}

function RecentRow({ item }: { item: UxTelemetryRecentItem }) {
    return (
        <tr className="border-b border-white/5 text-slate-200">
            <td className="py-3 pr-2">{formatRelativeTime(item.created_at)}</td>
            <td className="py-3">{item.actor_username || '—'}</td>
            <td className="py-3">{labelRole(item.actor_role)}</td>
            <td className="py-3">{labelSurface(item.surface)}</td>
            <td className="py-3">
                <span className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-[11px] text-cyan-200">
                    {labelEvent(item.event_name)}
                </span>
            </td>
            <td className="py-3">{item.action_label || '—'}</td>
        </tr>
    );
}
