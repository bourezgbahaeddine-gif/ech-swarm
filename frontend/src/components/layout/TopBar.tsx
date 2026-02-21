'use client';

import { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, Search, LogOut, User, Shield, FileText, Sparkles, Loader2, Clipboard, X, Radar, AlertTriangle, Moon, Sun } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { dashboardApi, type DashboardNotification, type PublishedMonitorReport } from '@/lib/api';
import { journalistServicesApi } from '@/lib/journalist-services-api';

const roleLabels: Record<string, string> = {
    director: 'المدير العام',
    editor_chief: 'رئيس التحرير',
    journalist: 'صحفي',
    social_media: 'السوشيال ميديا',
    print_editor: 'محرر النسخة المطبوعة',
    fact_checker: 'مدقق حقائق',
};

const QUICK_HELP_KEY = 'quick_tasks_help_seen_v2';

function cleanServiceOutput(value: string): string {
    return (value || '')
        .replace(/```[\s\S]*?```/g, '')
        .replace(/^\s*(note|notes|explanation|comment)\s*:.*$/gim, '')
        .replace(/^\s*(ملاحظة|شرح|تعليق)\s*:.*$/gim, '')
        .replace(/^\s*(حسنًا|حسنا|يمكنني|آمل).*$/gim, '')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

export default function TopBar({ theme, onToggleTheme }: { theme: 'light' | 'dark'; onToggleTheme: () => void }) {
    const { user, logout } = useAuth();
    const queryClient = useQueryClient();
    const [searchQuery, setSearchQuery] = useState('');
    const [showMenu, setShowMenu] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);
    const [showQuickTools, setShowQuickTools] = useState(false);
    const [showPublishedMonitor, setShowPublishedMonitor] = useState(false);
    const role = (user?.role || '').toLowerCase();
    const canUseQuickTasks = ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker'].includes(role);

    const { data: notificationsData, isLoading: notificationsLoading } = useQuery({
        queryKey: ['dashboard-notifications'],
        queryFn: () => dashboardApi.notifications({ limit: 20 }),
        refetchInterval: 30000,
    });
    const notifications: DashboardNotification[] = notificationsData?.data?.items || [];

    return (
        <header className={`sticky top-0 z-30 backdrop-blur-xl border-b ${theme === 'dark' ? 'bg-gray-900/80 border-white/5' : 'app-surface border-[var(--border-primary)]'}`}>
            <div className="h-16">
                <div className="flex items-center justify-between h-full px-6">
                    <div className="relative w-full max-w-md">
                        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="ابحث عن خبر أو كلمة مفتاحية..."
                            className={`w-full h-10 pr-10 pl-4 rounded-xl border text-sm focus:outline-none transition-all duration-200 ${
                                theme === 'dark'
                                    ? 'bg-white/5 border-white/5 text-white placeholder:text-gray-500 focus:border-emerald-500/40 focus:ring-1 focus:ring-emerald-500/20'
                                    : 'bg-white border-gray-300 text-[var(--text-primary)] placeholder:text-gray-400 focus:border-[var(--accent-blue)] focus:ring-1 focus:ring-blue-100'
                            }`}
                            dir="rtl"
                        />
                    </div>

                    <div className="flex items-center gap-2 mr-4">
                        <button
                            onClick={onToggleTheme}
                            className={`h-10 w-10 rounded-xl border flex items-center justify-center ${
                                theme === 'dark'
                                    ? 'bg-white/5 hover:bg-white/10 border-white/10 text-gray-300 hover:text-white'
                                    : 'bg-white hover:bg-gray-100 border-gray-300 text-gray-600 hover:text-gray-900'
                            }`}
                            title={theme === 'dark' ? 'تفعيل الوضع الفاتح' : 'تفعيل الوضع الداكن'}
                        >
                            {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                        </button>
                        {canUseQuickTasks && (
                            <button
                                onClick={() => setShowQuickTools(true)}
                                className={`h-10 px-3 rounded-xl border text-xs flex items-center gap-1.5 ${
                                    theme === 'dark'
                                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20'
                                        : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-100'
                                }`}
                            >
                                <Sparkles className="w-4 h-4" />
                                مهام سريعة
                            </button>
                        )}
                        <button
                            onClick={() => setShowPublishedMonitor(true)}
                            className={`h-10 px-3 rounded-xl border text-xs flex items-center gap-1.5 ${
                                theme === 'dark'
                                    ? 'bg-cyan-500/10 border-cyan-500/30 text-cyan-200 hover:bg-cyan-500/20'
                                    : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-100'
                            }`}
                        >
                            <Radar className="w-4 h-4" />
                            جودة المنشور
                        </button>

                        <div className="relative">
                            <button
                                onClick={() => setShowNotifications((s) => !s)}
                                className="relative w-10 h-10 rounded-xl bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors group"
                            >
                                <Bell className="w-4 h-4 text-gray-400 group-hover:text-white transition-colors" />
                                {notifications.length > 0 && (
                                    <span className="absolute -top-1 -left-1 min-w-5 h-5 px-1 rounded-full bg-red-500 text-[10px] text-white font-bold flex items-center justify-center shadow-lg shadow-red-500/30">
                                        {Math.min(notifications.length, 99)}
                                    </span>
                                )}
                            </button>
                            {showNotifications && (
                                <div className="absolute left-0 top-full mt-2 w-[360px] rounded-xl bg-gray-900 border border-white/10 shadow-xl overflow-hidden z-50">
                                    <div className="px-3 py-2 border-b border-white/10 text-sm text-white">التنبيهات</div>
                                    <div className="max-h-[360px] overflow-auto">
                                        {notificationsLoading ? (
                                            <div className="p-4 text-xs text-gray-400 flex items-center gap-2">
                                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                جاري تحميل التنبيهات...
                                            </div>
                                        ) : notifications.length === 0 ? (
                                            <div className="p-4 text-xs text-gray-500">لا توجد تنبيهات حالياً.</div>
                                        ) : (
                                            notifications.map((item) => (
                                                <a
                                                    key={item.id}
                                                    href={
                                                        item.article_id
                                                            ? `/news/${item.article_id}`
                                                            : item.type === 'published_quality'
                                                                ? '#'
                                                                : '/trends'
                                                    }
                                                    onClick={(e) => {
                                                        if (item.type === 'published_quality') {
                                                            e.preventDefault();
                                                            setShowNotifications(false);
                                                            setShowPublishedMonitor(true);
                                                        }
                                                    }}
                                                    className="block px-3 py-2 border-b border-white/5 hover:bg-white/5"
                                                >
                                                    <p className="text-xs text-white">{item.title}</p>
                                                    <p className="text-[11px] text-gray-400 mt-0.5">{item.message}</p>
                                                </a>
                                            ))
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        <div className="relative">
                            <button
                                onClick={() => setShowMenu(!showMenu)}
                                className="flex items-center gap-3 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                            >
                                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center">
                                    {user?.role === 'director' ? <Shield className="w-4 h-4 text-white" /> : <User className="w-4 h-4 text-white" />}
                                </div>
                                <div className="hidden md:block text-right">
                                    <p className="text-xs font-medium text-white">{user?.full_name_ar || 'مستخدم'}</p>
                                    <p className="text-[10px] text-gray-500">{roleLabels[user?.role || ''] || user?.role}</p>
                                </div>
                            </button>

                            {showMenu && (
                                <div className="absolute left-0 top-full mt-2 w-56 rounded-xl bg-gray-800 border border-white/10 shadow-xl overflow-hidden animate-fade-in-up z-50">
                                    <div className="px-4 py-3 border-b border-white/5">
                                        <p className="text-sm font-medium text-white">{user?.full_name_ar}</p>
                                        <p className="text-[10px] text-gray-500 mt-0.5">@{user?.username}</p>
                                        <p className="text-[10px] text-emerald-400 mt-1">{user?.specialization}</p>
                                    </div>
                                    <div className="border-t border-white/5">
                                        <button
                                            onClick={() => {
                                                setShowMenu(false);
                                                logout();
                                            }}
                                            className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                                        >
                                            <LogOut className="w-4 h-4" />
                                            تسجيل الخروج
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            <div className={`px-6 py-2 border-t ${theme === 'dark' ? 'border-white/5 bg-white/[0.02]' : 'border-[var(--border-primary)] bg-[var(--bg-tertiary)]'}`}>
                <div className={`flex items-center gap-2 text-xs ${theme === 'dark' ? 'text-gray-300' : 'text-[var(--text-primary)]'}`}>
                    <FileText className="w-3.5 h-3.5 text-emerald-400" />
                    <span>الدستور التحريري يعمل كحارس قبل اعتماد النسخة النهائية.</span>
                    <a href="/constitution" className="text-emerald-300 hover:text-emerald-200 underline">
                        فتح الدستور
                    </a>
                </div>
            </div>

            {showQuickTools && <QuickTasksDrawer theme={theme} onClose={() => setShowQuickTools(false)} />}
            {showPublishedMonitor && (
                <PublishedMonitorDrawer
                    theme={theme}
                    onClose={() => setShowPublishedMonitor(false)}
                    onRefresh={async () => {
                        await queryClient.invalidateQueries({ queryKey: ['published-monitor-latest'] });
                        await queryClient.invalidateQueries({ queryKey: ['dashboard-notifications'] });
                    }}
                />
            )}
        </header>
    );
}

function QuickTasksDrawer({ theme, onClose }: { theme: 'light' | 'dark'; onClose: () => void }) {
    const [text, setText] = useState('');
    const [reference, setReference] = useState('');
    const [platform, setPlatform] = useState('facebook');
    const [result, setResult] = useState('');
    const [busy, setBusy] = useState(false);
    const [mounted, setMounted] = useState(false);
    const [showHelp, setShowHelp] = useState(() => {
        if (typeof window === 'undefined') return false;
        return !window.localStorage.getItem(QUICK_HELP_KEY);
    });

    useEffect(() => {
        setMounted(true);
        return () => setMounted(false);
    }, []);

    const quickTips = useMemo(
        () => [
            'هذه الخانة للمهام السريعة خارج المحرر الذكي.',
            'استخدمها للتدقيق، التلخيص، والتحقق الأولي قبل فتح خبر كامل.',
            'كل نتيجة هنا مساعدة أولية ويجب مراجعتها بشرياً قبل الاعتماد.',
        ],
        [],
    );

    async function run(task: 'proofread' | 'inverted' | 'social' | 'metadata' | 'extract' | 'consistency') {
        setBusy(true);
        try {
            let raw = '';
            if (task === 'proofread') {
                const res = await journalistServicesApi.proofread(text, 'ar');
                raw = res?.data?.result || '';
            } else if (task === 'inverted') {
                const res = await journalistServicesApi.inverted(text, 'ar');
                raw = res?.data?.result || '';
            } else if (task === 'social') {
                const res = await journalistServicesApi.social(text, platform, 'ar');
                raw = res?.data?.result || '';
            } else if (task === 'metadata') {
                const res = await journalistServicesApi.metadata(text, 'ar');
                raw = res?.data?.result || '';
            } else if (task === 'consistency') {
                const res = await journalistServicesApi.consistency(text, reference);
                raw = res?.data?.result || '';
            } else {
                const res = await journalistServicesApi.extract(text);
                raw = res?.data?.result || '';
            }
            setResult(cleanServiceOutput(raw));
        } finally {
            setBusy(false);
        }
    }

    function closeHelp() {
        if (typeof window !== 'undefined') {
            window.localStorage.setItem(QUICK_HELP_KEY, '1');
        }
        setShowHelp(false);
    }

    if (!mounted) return null;

    return createPortal(
        <div className="fixed inset-0 z-[120] bg-black/70 flex justify-end">
            <div
                className={`w-full max-w-2xl h-full border-l shadow-2xl p-4 space-y-3 overflow-y-auto ${
                    theme === 'dark'
                        ? 'bg-[#0f172a] border-white/20 shadow-black/70'
                        : 'app-surface border-[var(--border-primary)] shadow-[rgba(15,23,42,0.18)]'
                }`}
                dir="rtl"
            >
                <div className="flex items-center justify-between">
                    <h2 className="text-white font-semibold">الخانة الجانبية للمهام السريعة</h2>
                    <button onClick={onClose} className="px-2 py-1 rounded bg-white/15 text-gray-100 text-xs border border-white/20 hover:bg-white/20">إغلاق</button>
                </div>

                {showHelp && (
                    <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-xs text-cyan-100 space-y-1 relative">
                        <button onClick={closeHelp} className="absolute left-2 top-2 text-cyan-200 hover:text-white">
                            <X className="w-3.5 h-3.5" />
                        </button>
                        {quickTips.map((tip) => (
                            <p key={tip}>- {tip}</p>
                        ))}
                    </div>
                )}

                <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    className="w-full min-h-[180px] p-3 rounded-xl bg-[#111827] border border-white/20 text-white text-sm placeholder:text-gray-400"
                    placeholder="ألصق النص هنا..."
                />

                <textarea
                    value={reference}
                    onChange={(e) => setReference(e.target.value)}
                    className="w-full min-h-[90px] p-3 rounded-xl bg-[#111827] border border-white/20 text-white text-sm placeholder:text-gray-400"
                    placeholder="مرجع التحقق (اختياري)"
                />

                <div className="flex flex-wrap gap-2">
                    <button onClick={() => run('proofread')} className="px-3 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-200 text-xs">تدقيق لغوي</button>
                    <button onClick={() => run('inverted')} className="px-3 py-2 rounded-xl bg-blue-500/20 border border-blue-500/30 text-blue-200 text-xs">هرم مقلوب</button>
                    <button onClick={() => run('extract')} className="px-3 py-2 rounded-xl bg-violet-500/20 border border-violet-500/30 text-violet-200 text-xs">استخراج نقاط</button>
                    <button onClick={() => run('consistency')} className="px-3 py-2 rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-200 text-xs">تحقق من الاتساق</button>
                    <button onClick={() => run('metadata')} className="px-3 py-2 rounded-xl bg-fuchsia-500/20 border border-fuchsia-500/30 text-fuchsia-200 text-xs">SEO سريع</button>
                    <select
                        value={platform}
                        onChange={(e) => setPlatform(e.target.value)}
                        className="px-2 py-2 rounded-xl bg-[#111827] border border-white/20 text-xs text-gray-100"
                    >
                        <option value="facebook">Facebook</option>
                        <option value="twitter">X</option>
                        <option value="telegram">Telegram</option>
                    </select>
                    <button onClick={() => run('social')} className="px-3 py-2 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-200 text-xs">نسخ سوشيال</button>
                </div>

                <div className="rounded-xl border border-white/20 bg-[#0b1324] p-3 min-h-[220px]">
                    <div className="flex items-center justify-between mb-1">
                        <p className="text-xs text-gray-400">النتيجة</p>
                        <button
                            onClick={() => navigator.clipboard.writeText(result || '')}
                            className="text-xs text-emerald-300 hover:text-emerald-200 inline-flex items-center gap-1"
                        >
                            <Clipboard className="w-3.5 h-3.5" />
                            نسخ
                        </button>
                    </div>
                    {busy ? (
                        <p className="text-xs text-gray-500">جاري التنفيذ...</p>
                    ) : (
                        <pre className="whitespace-pre-wrap text-sm text-gray-200">{result || 'لا توجد نتيجة بعد.'}</pre>
                    )}
                </div>
            </div>
        </div>,
        document.body
    );
}

function scoreColor(score: number): string {
    if (score >= 90) return 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10';
    if (score >= 75) return 'text-cyan-300 border-cyan-500/40 bg-cyan-500/10';
    if (score >= 60) return 'text-amber-300 border-amber-500/40 bg-amber-500/10';
    return 'text-red-300 border-red-500/40 bg-red-500/10';
}

function PublishedMonitorDrawer({
    theme,
    onClose,
    onRefresh,
}: {
    theme: 'light' | 'dark';
    onClose: () => void;
    onRefresh: () => Promise<void>;
}) {
    const { data, isLoading, refetch } = useQuery({
        queryKey: ['published-monitor-latest'],
        queryFn: () => dashboardApi.latestPublishedMonitor({ refresh_if_empty: true, limit: 12 }),
        refetchInterval: 900000,
    });

    const runNow = useMutation({
        mutationFn: () => dashboardApi.triggerPublishedMonitor({ wait: true, limit: 12 }),
        onSuccess: async (res) => {
            if (res.data?.report) {
                await onRefresh();
            } else {
                await refetch();
            }
        },
    });
    if (typeof document === 'undefined') return null;

    const report = data?.data as PublishedMonitorReport | undefined;
    const items = report?.items || [];

    return createPortal(
        <div className="fixed inset-0 z-[130] bg-black/70 flex justify-end">
            <div
                className={`w-full max-w-3xl h-full border-l shadow-2xl p-4 space-y-4 overflow-y-auto ${
                    theme === 'dark'
                        ? 'bg-[#0b1220] border-white/20 shadow-black/70'
                        : 'app-surface border-[var(--border-primary)] shadow-[rgba(15,23,42,0.18)]'
                }`}
                dir="rtl"
            >
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-white font-semibold">مراقبة جودة المحتوى المنشور</h2>
                        <p className="text-xs text-gray-400 mt-1">فحص دوري كل 15 دقيقة وفق الدستور التحريري</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => runNow.mutate()}
                            disabled={runNow.isPending}
                            className="px-3 py-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-xs hover:bg-cyan-500/20 disabled:opacity-50"
                        >
                            {runNow.isPending ? 'جاري الفحص...' : 'فحص الآن'}
                        </button>
                        <button onClick={onClose} className="px-2 py-1 rounded bg-white/15 text-gray-100 text-xs border border-white/20 hover:bg-white/20">إغلاق</button>
                    </div>
                </div>

                {isLoading ? (
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-gray-300">جاري تحميل تقرير المراقبة...</div>
                ) : !report ? (
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-gray-300">لا يوجد تقرير بعد.</div>
                ) : (
                    <>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                            <div className="rounded-xl border border-white/15 bg-white/[0.03] p-3">
                                <p className="text-[11px] text-gray-400">المعدل العام</p>
                                <p className="text-lg text-white font-semibold">{report.average_score}/100</p>
                            </div>
                            <div className="rounded-xl border border-white/15 bg-white/[0.03] p-3">
                                <p className="text-[11px] text-gray-400">عناصر مفحوصة</p>
                                <p className="text-lg text-white font-semibold">{report.total_items}</p>
                            </div>
                            <div className="rounded-xl border border-white/15 bg-white/[0.03] p-3">
                                <p className="text-[11px] text-gray-400">تحتاج مراجعة</p>
                                <p className="text-lg text-white font-semibold">{report.weak_items_count}</p>
                            </div>
                            <div className="rounded-xl border border-white/15 bg-white/[0.03] p-3">
                                <p className="text-[11px] text-gray-400">آخر تشغيل</p>
                                <p className="text-sm text-white font-semibold">{new Date(report.executed_at).toLocaleString('ar-DZ')}</p>
                            </div>
                        </div>

                        {report.weak_items_count > 0 && (
                            <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200 flex items-center gap-2">
                                <AlertTriangle className="w-4 h-4" />
                                تم رصد مشاكل جودة وتم إرسال تنبيه إلى تيليغرام.
                            </div>
                        )}

                        <div className="space-y-2">
                            {items.map((item, idx) => (
                                <div key={`${item.url}-${idx}`} className="rounded-xl border border-white/10 bg-[#0a1424] p-3 space-y-2">
                                    <div className="flex items-start justify-between gap-3">
                                        <a href={item.url} target="_blank" rel="noreferrer" className="text-sm text-white hover:text-cyan-200 leading-relaxed">
                                            {item.title || 'بدون عنوان'}
                                        </a>
                                        <span className={`text-xs px-2 py-1 rounded-lg border ${scoreColor(item.score)}`}>
                                            {item.score} - {item.grade}
                                        </span>
                                    </div>
                                    {item.issues.length > 0 ? (
                                        <ul className="text-xs text-amber-200 space-y-1">
                                            {item.issues.slice(0, 3).map((issue, issueIdx) => (
                                                <li key={issueIdx}>- {issue}</li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <p className="text-xs text-emerald-300">لا توجد مشاكل مرصودة.</p>
                                    )}
                                    {item.suggestions.length > 0 && (
                                        <p className="text-xs text-gray-300">اقتراح: {item.suggestions[0]}</p>
                                    )}
                                </div>
                            ))}
                        </div>
                    </>
                )}
            </div>
        </div>,
        document.body
    );
}
