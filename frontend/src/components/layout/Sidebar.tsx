'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth';
import {
    LayoutDashboard,
    Newspaper,
    Rss,
    UserCheck,
    TrendingUp,
    Activity,
    ChevronLeft,
    ChevronRight,
    Users,
    KeyRound,
    FileText,
    ShieldCheck,
    Film,
    Mic2,
    FolderGit2,
    BookOpen,
    Gauge,
    MessagesSquare,
    Radar,
    FileSearch,
    Library,
    ScrollText,
    CalendarClock,
    Megaphone,
} from 'lucide-react';

type Role =
    | 'director'
    | 'editor_chief'
    | 'journalist'
    | 'social_media'
    | 'print_editor'
    | 'fact_checker'
    | 'observer';

type SidebarProps = {
    collapsed: boolean;
    onToggleCollapsed: () => void;
    mobileOpen: boolean;
    onCloseMobile: () => void;
};

function normalizeRole(role: string): Role | null {
    const value = (role || '').trim().toLowerCase();
    if (value === 'chief_editor' || value === 'editor_in_chief' || value === 'editor-chief') {
        return 'editor_chief';
    }
    const allowed: Role[] = [
        'director',
        'editor_chief',
        'journalist',
        'social_media',
        'print_editor',
        'fact_checker',
        'observer',
    ];
    return allowed.includes(value as Role) ? (value as Role) : null;
}

const navItems = [
    { href: '/', label: 'لوحة القيادة', icon: LayoutDashboard, roles: ['director', 'editor_chief'] as Role[] },
    { href: '/news', label: 'الأخبار', icon: Newspaper, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker'] as Role[] },
    { href: '/editorial', label: 'قسم التحرير', icon: UserCheck, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/workspace-drafts', label: 'المحرر الذكي', icon: FolderGit2, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/stories', label: 'القصص التحريرية', icon: Library, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/scripts', label: 'استوديو السكربت', icon: ScrollText, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/trends', label: 'رادار التراند', icon: TrendingUp, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/events', label: 'لوحة الأحداث', icon: CalendarClock, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/digital', label: 'فريق الديجيتال', icon: Megaphone, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/constitution', label: 'الدستور', icon: FileText, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker'] as Role[] },
    { href: '/msi', label: 'مؤشر MSI', icon: Gauge, roles: ['director'] as Role[] },
    { href: '/simulator', label: 'محاكي الجمهور', icon: MessagesSquare, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/competitor-xray', label: 'كشاف المنافسين', icon: Radar, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/memory', label: 'ذاكرة المشروع', icon: BookOpen, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/services/multimedia', label: 'الوسائط', icon: Film, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/services/media-logger', label: 'مفرّغ الندوات', icon: Mic2, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/services/document-intel', label: 'محلل الوثائق', icon: FileSearch, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/team', label: 'فريق التحرير', icon: Users, roles: ['director'] as Role[] },
    { href: '/sources', label: 'المصادر', icon: Rss, roles: ['director'] as Role[] },
    { href: '/agents', label: 'مراقبة النظام', icon: Activity, roles: ['director'] as Role[] },
    { href: '/services/fact-check', label: 'التحقق والاستقصاء', icon: ShieldCheck, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'fact_checker', 'print_editor'] as Role[] },
    { href: '/settings', label: 'إعدادات APIs', icon: KeyRound, roles: ['director'] as Role[] },
];

export default function Sidebar({
    collapsed,
    onToggleCollapsed,
    mobileOpen,
    onCloseMobile,
}: SidebarProps) {
    const pathname = usePathname();
    const { user } = useAuth();
    const role = normalizeRole(user?.role || '');
    const visibleNav = role ? navItems.filter((item) => item.roles.includes(role)) : [];

    return (
        <>
            <button
                type="button"
                aria-label="Close sidebar overlay"
                onClick={onCloseMobile}
                className={cn(
                    'fixed inset-0 z-40 bg-black/55 backdrop-blur-[1px] md:hidden transition-opacity',
                    mobileOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
                )}
            />
            <aside
                className={cn(
                    'fixed top-0 right-0 h-screen z-50 transition-all duration-300 ease-in-out',
                    'bg-[#0F172A] border-slate-800/70 border-l flex flex-col',
                    'w-[86vw] max-w-[280px] md:w-auto',
                    collapsed ? 'md:w-[72px]' : 'md:w-[260px]',
                    mobileOpen ? 'translate-x-0' : 'translate-x-full md:translate-x-0'
                )}
            >
                <div className="flex items-center gap-3 px-4 h-16 border-b border-white/10">
                    <div className="w-9 h-9 rounded-xl border flex items-center justify-center overflow-hidden bg-white/5 border-white/15">
                        <img src="/ech-logo.png" alt="Echorouk" className="w-7 h-7 object-contain" />
                    </div>
                    {!collapsed && (
                        <div className="overflow-hidden">
                            <h1 className="text-sm font-bold truncate text-[#F8FAFC]">غرفة الشروق</h1>
                            <p className="text-[10px] font-medium text-[#CBD5E1]">النظام الذكي v1.0</p>
                        </div>
                    )}
                </div>

                <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
                    {visibleNav.map((item) => {
                        const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
                        return (
                            <Link
                                key={item.href}
                                href={item.href}
                                onClick={onCloseMobile}
                                className={cn(
                                    'flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group relative',
                                    isActive
                                        ? 'bg-blue-500/20 text-[#F8FAFC] shadow-inner'
                                        : 'text-[#CBD5E1] hover:text-[#F8FAFC] hover:bg-white/8'
                                )}
                            >
                                {isActive && (
                                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-[#2563EB]" />
                                )}
                                <item.icon className={cn('w-5 h-5 flex-shrink-0', isActive && 'drop-shadow-[0_0_6px_rgba(37,99,235,0.5)]')} />
                                {!collapsed && <span className="text-sm font-medium">{item.label}</span>}
                            </Link>
                        );
                    })}
                </nav>

                {!collapsed && (
                    <div className="px-3 py-3 mx-2 mb-3 rounded-xl border bg-white/[0.03] border-white/10">
                        <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-[#2563EB]" />
                            <span className="text-xs text-[#CBD5E1]">النظام يعمل</span>
                            <span className="w-2 h-2 rounded-full animate-pulse mr-auto bg-[#2563EB]" />
                        </div>
                    </div>
                )}

                <button
                    onClick={onToggleCollapsed}
                    className="hidden md:flex items-center justify-center h-10 border-t transition-colors border-white/10 text-[#94A3B8] hover:text-[#F8FAFC]"
                >
                    {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                </button>
            </aside>
        </>
    );
}
