'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bell, Search, LogOut, User, Shield, FileText, Sparkles, Loader2, Clipboard, X } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { dashboardApi, type DashboardNotification } from '@/lib/api';
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

export default function TopBar() {
    const { user, logout } = useAuth();
    const [searchQuery, setSearchQuery] = useState('');
    const [showMenu, setShowMenu] = useState(false);
    const [showNotifications, setShowNotifications] = useState(false);
    const [showQuickTools, setShowQuickTools] = useState(false);
    const role = (user?.role || '').toLowerCase();
    const canUseQuickTasks = ['director', 'editor_chief', 'journalist', 'print_editor', 'fact_checker'].includes(role);

    const { data: notificationsData, isLoading: notificationsLoading } = useQuery({
        queryKey: ['dashboard-notifications'],
        queryFn: () => dashboardApi.notifications({ limit: 20 }),
        refetchInterval: 30000,
    });
    const notifications: DashboardNotification[] = notificationsData?.data?.items || [];

    return (
        <header className="sticky top-0 z-30 bg-gray-900/80 backdrop-blur-xl border-b border-white/5">
            <div className="h-16">
                <div className="flex items-center justify-between h-full px-6">
                    <div className="relative w-full max-w-md">
                        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="ابحث عن خبر أو كلمة مفتاحية..."
                            className="w-full h-10 pr-10 pl-4 rounded-xl bg-white/5 border border-white/5 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-emerald-500/40 focus:ring-1 focus:ring-emerald-500/20 transition-all duration-200"
                            dir="rtl"
                        />
                    </div>

                    <div className="flex items-center gap-2 mr-4">
                        {canUseQuickTasks && (
                            <button
                                onClick={() => setShowQuickTools(true)}
                                className="h-10 px-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/20 text-xs flex items-center gap-1.5"
                            >
                                <Sparkles className="w-4 h-4" />
                                مهام سريعة
                            </button>
                        )}

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
                                                    href={item.article_id ? `/news/${item.article_id}` : '/trends'}
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

            <div className="px-6 py-2 border-t border-white/5 bg-white/[0.02]">
                <div className="flex items-center gap-2 text-xs text-gray-300">
                    <FileText className="w-3.5 h-3.5 text-emerald-400" />
                    <span>الدستور التحريري يعمل كحارس قبل اعتماد النسخة النهائية.</span>
                    <a href="/constitution" className="text-emerald-300 hover:text-emerald-200 underline">
                        فتح الدستور
                    </a>
                </div>
            </div>

            {showQuickTools && <QuickTasksDrawer onClose={() => setShowQuickTools(false)} />}
        </header>
    );
}

function QuickTasksDrawer({ onClose }: { onClose: () => void }) {
    const [text, setText] = useState('');
    const [reference, setReference] = useState('');
    const [platform, setPlatform] = useState('facebook');
    const [result, setResult] = useState('');
    const [busy, setBusy] = useState(false);
    const [showHelp, setShowHelp] = useState(() => {
        if (typeof window === 'undefined') return false;
        return !window.localStorage.getItem(QUICK_HELP_KEY);
    });

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

    return (
        <div className="fixed inset-0 z-[70] bg-black/60 backdrop-blur-sm flex justify-end">
            <div className="w-full max-w-2xl h-full bg-gray-950 border-l border-white/10 p-4 space-y-3" dir="rtl">
                <div className="flex items-center justify-between">
                    <h2 className="text-white font-semibold">الخانة الجانبية للمهام السريعة</h2>
                    <button onClick={onClose} className="px-2 py-1 rounded bg-white/10 text-gray-300 text-xs">إغلاق</button>
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
                    className="w-full min-h-[180px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
                    placeholder="ألصق النص هنا..."
                />

                <textarea
                    value={reference}
                    onChange={(e) => setReference(e.target.value)}
                    className="w-full min-h-[90px] p-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm"
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
                        className="px-2 py-2 rounded-xl bg-white/5 border border-white/10 text-xs text-gray-200"
                    >
                        <option value="facebook">Facebook</option>
                        <option value="twitter">X</option>
                        <option value="telegram">Telegram</option>
                    </select>
                    <button onClick={() => run('social')} className="px-3 py-2 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-200 text-xs">نسخ سوشيال</button>
                </div>

                <div className="rounded-xl border border-white/10 bg-black/20 p-3 min-h-[220px]">
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
        </div>
    );
}
