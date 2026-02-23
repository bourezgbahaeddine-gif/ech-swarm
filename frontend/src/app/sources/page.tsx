'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    AlertTriangle,
    CheckCircle2,
    Clock,
    ExternalLink,
    Globe,
    Plus,
    RefreshCcw,
    Rss,
    Save,
    Shield,
    ToggleLeft,
    ToggleRight,
    Trash2,
    Wand2,
} from 'lucide-react';

import { sourcesApi, type Source, type SourceHealthApplyResponse } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';

export default function SourcesPage() {
    const queryClient = useQueryClient();
    const [showAdd, setShowAdd] = useState(false);
    const [hoursWindow, setHoursWindow] = useState(48);
    const [policyDomainsText, setPolicyDomainsText] = useState('');
    const [policyCap, setPolicyCap] = useState(12);
    const [policyDomainsTouched, setPolicyDomainsTouched] = useState(false);
    const [policyCapTouched, setPolicyCapTouched] = useState(false);
    const [lastApply, setLastApply] = useState<SourceHealthApplyResponse | null>(null);
    const [newSource, setNewSource] = useState({
        name: '',
        url: '',
        category: 'general',
        priority: 5,
    });

    const { data: sourcesData, isLoading } = useQuery({
        queryKey: ['sources'],
        queryFn: () => sourcesApi.list(),
    });

    const { data: statsData } = useQuery({
        queryKey: ['sources-stats'],
        queryFn: () => sourcesApi.stats(),
    });

    const { data: policyData } = useQuery({
        queryKey: ['sources-policy'],
        queryFn: () => sourcesApi.getPolicy(),
    });

    const { data: healthData, isFetching: healthLoading } = useQuery({
        queryKey: ['sources-health', hoursWindow],
        queryFn: () => sourcesApi.health({ hours: hoursWindow, include_disabled: true }),
    });

    const policyDomainsInitial = useMemo(
        () => (policyData?.data?.blocked_domains || []).join('\n'),
        [policyData?.data?.blocked_domains],
    );
    const policyCapInitial = policyData?.data?.freshrss_max_per_source_per_run || 12;
    const policyDomainsValue = policyDomainsTouched ? policyDomainsText : policyDomainsInitial;
    const policyCapValue = policyCapTouched ? policyCap : policyCapInitial;

    const createMutation = useMutation({
        mutationFn: (data: Partial<Source>) => sourcesApi.create(data),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['sources'] });
            setShowAdd(false);
            setNewSource({ name: '', url: '', category: 'general', priority: 5 });
        },
    });

    const toggleMutation = useMutation({
        mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
            sourcesApi.update(id, { enabled }),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
    });

    const deleteMutation = useMutation({
        mutationFn: (id: number) => sourcesApi.delete(id),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sources'] }),
    });

    const updatePolicyMutation = useMutation({
        mutationFn: () => {
            const domains = (policyDomainsTouched ? policyDomainsText : policyDomainsInitial)
                .split('\n')
                .map((x) => x.trim())
                .filter(Boolean);
            return sourcesApi.updatePolicy({
                blocked_domains: domains,
                freshrss_max_per_source_per_run: Number.isFinite(policyCapValue) ? policyCapValue : 12,
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['sources-policy'] });
            queryClient.invalidateQueries({ queryKey: ['sources-health'] });
            setPolicyDomainsTouched(false);
            setPolicyCapTouched(false);
        },
    });

    const applyHealthMutation = useMutation({
        mutationFn: (dryRun: boolean) =>
            sourcesApi.applyHealth({
                hours: hoursWindow,
                include_disabled: true,
                dry_run: dryRun,
                max_changes: 100,
            }),
        onSuccess: (response) => {
            setLastApply(response.data);
            queryClient.invalidateQueries({ queryKey: ['sources'] });
            queryClient.invalidateQueries({ queryKey: ['sources-health'] });
        },
    });

    const sources = sourcesData?.data || [];
    const sourcesStats = statsData?.data as { total?: number; active?: number } | undefined;
    const health = healthData?.data;

    const healthTopRisk = useMemo(() => {
        return (health?.items || []).slice(0, 8);
    }, [health?.items]);

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <Rss className="w-7 h-7 text-orange-400" />
                        إدارة المصادر
                    </h1>
                    <p className="text-sm text-gray-500 mt-1">
                        إجمالي {sourcesStats?.total ?? sources.length} مصدر — النشط {sourcesStats?.active ?? sources.filter((s) => s.enabled).length}
                    </p>
                </div>
                <button
                    onClick={() => setShowAdd(!showAdd)}
                    className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 transition-colors text-sm font-medium"
                >
                    <Plus className="w-4 h-4" />
                    إضافة مصدر
                </button>
            </div>

            <div className="rounded-2xl bg-gray-800/30 border border-cyan-500/20 p-5 space-y-4">
                <div className="flex items-center gap-2 text-white">
                    <Shield className="w-4 h-4 text-cyan-300" />
                    <h2 className="text-sm font-semibold">سياسة المصادر</h2>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div>
                        <label className="text-xs text-gray-400 block mb-2">
                            الدومينات المحظورة (سطر لكل دومين)
                        </label>
                        <textarea
                            value={policyDomainsValue}
                            onChange={(e) => {
                                setPolicyDomainsTouched(true);
                                setPolicyDomainsText(e.target.value);
                            }}
                            rows={6}
                            className="w-full rounded-xl bg-white/5 border border-white/10 text-sm text-white px-3 py-2 focus:outline-none focus:border-cyan-500/40"
                            dir="ltr"
                        />
                    </div>
                    <div className="space-y-3">
                        <div>
                            <label className="text-xs text-gray-400 block mb-2">
                                الحد الأقصى لكل مصدر FreshRSS في كل دورة
                            </label>
                            <input
                                type="number"
                                min={1}
                                max={100}
                                value={policyCapValue}
                                onChange={(e) => {
                                    setPolicyCapTouched(true);
                                    setPolicyCap(Number(e.target.value || 12));
                                }}
                                className="h-10 w-full rounded-xl bg-white/5 border border-white/10 text-sm text-white px-3 focus:outline-none focus:border-cyan-500/40"
                            />
                        </div>
                        <button
                            onClick={() => updatePolicyMutation.mutate()}
                            disabled={updatePolicyMutation.isPending}
                            className="h-10 px-4 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/30 text-sm flex items-center gap-2"
                        >
                            <Save className="w-4 h-4" />
                            حفظ السياسة
                        </button>
                    </div>
                </div>
            </div>

            <div className="rounded-2xl bg-gray-800/30 border border-amber-500/20 p-5 space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-white">
                        <AlertTriangle className="w-4 h-4 text-amber-300" />
                        <h2 className="text-sm font-semibold">مراقبة صحة المصادر</h2>
                    </div>
                    <div className="flex items-center gap-2">
                        <select
                            value={hoursWindow}
                            onChange={(e) => setHoursWindow(Number(e.target.value))}
                            className="h-9 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-300"
                        >
                            <option value={24}>آخر 24 ساعة</option>
                            <option value={48}>آخر 48 ساعة</option>
                            <option value={72}>آخر 72 ساعة</option>
                            <option value={168}>آخر 7 أيام</option>
                        </select>
                        <button
                            onClick={() => queryClient.invalidateQueries({ queryKey: ['sources-health'] })}
                            className="h-9 px-3 rounded-xl bg-white/5 border border-white/10 text-gray-300 hover:text-white flex items-center gap-2 text-sm"
                        >
                            <RefreshCcw className={cn('w-4 h-4', healthLoading && 'animate-spin')} />
                            تحديث
                        </button>
                    </div>
                </div>

                <div className="flex items-center gap-3 text-xs text-gray-400">
                    <span>إجمالي: {health?.total_sources ?? 0}</span>
                    <span>ضعيف/مراجعة: {health?.weak_sources ?? 0}</span>
                    <button
                        onClick={() => applyHealthMutation.mutate(true)}
                        disabled={applyHealthMutation.isPending}
                        className="h-8 px-3 rounded-lg bg-white/5 border border-white/10 hover:text-white"
                    >
                        <Wand2 className="w-3.5 h-3.5 inline ml-1" />
                        محاكاة تطبيق
                    </button>
                    <button
                        onClick={() => applyHealthMutation.mutate(false)}
                        disabled={applyHealthMutation.isPending}
                        className="h-8 px-3 rounded-lg bg-amber-500/20 border border-amber-500/30 text-amber-200"
                    >
                        تطبيق فعلي
                    </button>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                        <thead>
                            <tr className="text-gray-500 border-b border-white/10">
                                <th className="py-2 text-right">المصدر</th>
                                <th className="py-2 text-right">Score</th>
                                <th className="py-2 text-right">المرشحات</th>
                                <th className="py-2 text-right">آخر ظهور</th>
                                <th className="py-2 text-right">إجراءات</th>
                            </tr>
                        </thead>
                        <tbody>
                            {healthTopRisk.map((item) => (
                                <tr key={item.source_id} className="border-b border-white/5 text-gray-200">
                                    <td className="py-2">{item.name}</td>
                                    <td className="py-2">{item.health_score}</td>
                                    <td className="py-2">{Math.round(item.candidate_rate * 100)}%</td>
                                    <td className="py-2">{item.last_seen_at ? formatRelativeTime(item.last_seen_at) : '—'}</td>
                                    <td className="py-2 text-amber-300">{item.actions.join(', ') || '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {lastApply && (
                    <div className="text-xs text-gray-300 rounded-xl border border-white/10 bg-black/20 p-3">
                        <div>
                            dry_run: {String(lastApply.dry_run)} | candidate_changes: {lastApply.candidate_changes} | applied_changes: {lastApply.applied_changes}
                        </div>
                    </div>
                )}
            </div>

            {showAdd && (
                <div className="rounded-2xl bg-gray-800/30 border border-emerald-500/20 p-5">
                    <h3 className="text-sm font-semibold text-white mb-4">مصدر جديد</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                            placeholder="اسم المصدر"
                            value={newSource.name}
                            onChange={(e) => setNewSource((p) => ({ ...p, name: e.target.value }))}
                            className="h-10 px-4 rounded-xl bg-white/5 border border-white/5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-emerald-500/40"
                            dir="rtl"
                        />
                        <input
                            placeholder="رابط RSS"
                            value={newSource.url}
                            onChange={(e) => setNewSource((p) => ({ ...p, url: e.target.value }))}
                            className="h-10 px-4 rounded-xl bg-white/5 border border-white/5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-emerald-500/40"
                            dir="ltr"
                        />
                        <select
                            value={newSource.category}
                            onChange={(e) => setNewSource((p) => ({ ...p, category: e.target.value }))}
                            className="h-10 px-3 rounded-xl bg-white/5 border border-white/5 text-sm text-gray-300 focus:outline-none"
                        >
                            <option value="general">عام</option>
                            <option value="official">رسمي</option>
                            <option value="media_dz">إعلام جزائري</option>
                            <option value="international">دولي</option>
                            <option value="sports">رياضة</option>
                            <option value="economy">اقتصاد</option>
                            <option value="culture">ثقافة</option>
                        </select>
                        <div className="flex gap-2">
                            <button
                                onClick={() => createMutation.mutate(newSource)}
                                disabled={!newSource.name || !newSource.url || createMutation.isPending}
                                className="flex-1 h-10 rounded-xl bg-emerald-500 text-white text-sm font-medium hover:bg-emerald-600 disabled:opacity-30 transition-colors"
                            >
                                حفظ
                            </button>
                            <button
                                onClick={() => setShowAdd(false)}
                                className="h-10 px-4 rounded-xl bg-white/5 text-gray-400 text-sm hover:text-white transition-colors"
                            >
                                إلغاء
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {isLoading ? (
                    Array.from({ length: 9 }).map((_, i) => (
                        <div key={i} className="h-32 rounded-2xl bg-gray-800/30 border border-white/5 animate-pulse" />
                    ))
                ) : (
                    sources.map((source: Source) => (
                        <div
                            key={source.id}
                            className={cn(
                                'rounded-2xl p-4 border transition-all duration-200',
                                'bg-gradient-to-br from-gray-800/40 to-gray-900/60',
                                source.enabled ? 'border-white/5 hover:border-white/10' : 'border-white/[0.02] opacity-50',
                            )}
                        >
                            <div className="flex items-start justify-between mb-3">
                                <div className="flex items-center gap-2">
                                    <Globe className="w-4 h-4 text-gray-500" />
                                    <h3 className="text-sm font-semibold text-white">{source.name}</h3>
                                </div>
                                <button
                                    onClick={() => toggleMutation.mutate({ id: source.id, enabled: !source.enabled })}
                                    className="text-gray-400 hover:text-white transition-colors"
                                >
                                    {source.enabled ? (
                                        <ToggleRight className="w-5 h-5 text-emerald-400" />
                                    ) : (
                                        <ToggleLeft className="w-5 h-5" />
                                    )}
                                </button>
                            </div>

                            <div className="space-y-1.5 text-[11px]">
                                <div className="flex items-center gap-2 text-gray-500">
                                    <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-400">{source.category}</span>
                                    <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-400">{source.language}</span>
                                    <span className="px-1.5 py-0.5 rounded bg-white/5 text-gray-400">P{source.priority}</span>
                                </div>

                                <div className="flex items-center justify-between text-gray-500">
                                    <span className="flex items-center gap-1">
                                        <Clock className="w-3 h-3" />
                                        {source.last_fetched_at ? formatRelativeTime(source.last_fetched_at) : 'لم يجلب بعد'}
                                    </span>
                                    {source.error_count > 0 && (
                                        <span className="flex items-center gap-1 text-red-400">
                                            <AlertTriangle className="w-3 h-3" />
                                            {source.error_count} أخطاء
                                        </span>
                                    )}
                                </div>

                                <div className="flex items-center gap-2 mt-2">
                                    <div className="flex-1 h-1.5 rounded-full bg-gray-700 overflow-hidden">
                                        <div
                                            className="h-full rounded-full bg-emerald-400 transition-all"
                                            style={{ width: `${source.trust_score * 100}%` }}
                                        />
                                    </div>
                                    <span className="text-[10px] text-gray-500">{Math.round(source.trust_score * 100)}%</span>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/[0.03]">
                                <a
                                    href={source.url}
                                    target="_blank"
                                    rel="noopener"
                                    className="text-[10px] text-gray-500 hover:text-emerald-400 flex items-center gap-1 transition-colors"
                                >
                                    <ExternalLink className="w-3 h-3" /> RSS
                                </a>
                                <button
                                    onClick={() => deleteMutation.mutate(source.id)}
                                    className="text-gray-600 hover:text-red-400 transition-colors mr-auto"
                                >
                                    <Trash2 className="w-3.5 h-3.5" />
                                </button>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {updatePolicyMutation.isSuccess && (
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-2 text-xs text-emerald-200 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4" />
                    تم حفظ سياسة المصادر.
                </div>
            )}
        </div>
    );
}
