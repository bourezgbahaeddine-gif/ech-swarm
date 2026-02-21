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
    FolderGit2,
    BookOpen,
    Gauge,
    MessagesSquare,
} from 'lucide-react';
import { useState } from 'react';

type Role =
    | 'director'
    | 'editor_chief'
    | 'journalist'
    | 'social_media'
    | 'print_editor'
    | 'fact_checker'
    | 'observer';

const navItems = [
    { href: '/', label: 'لوحة القيادة', icon: LayoutDashboard, roles: ['director', 'editor_chief'] as Role[] },
    { href: '/news', label: 'الأخبار', icon: Newspaper, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker'] as Role[] },
    { href: '/editorial', label: 'قسم التحرير', icon: UserCheck, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/workspace-drafts', label: 'المحرر الذكي', icon: FolderGit2, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/trends', label: 'رادار التراند', icon: TrendingUp, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/constitution', label: 'الدستور', icon: FileText, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker'] as Role[] },
    { href: '/msi', label: 'مؤشر MSI', icon: Gauge, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/simulator', label: 'محاكي الجمهور', icon: MessagesSquare, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/memory', label: 'ذاكرة المشروع', icon: BookOpen, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/services/multimedia', label: 'الوسائط', icon: Film, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'] as Role[] },
    { href: '/team', label: 'فريق التحرير', icon: Users, roles: ['director', 'editor_chief'] as Role[] },
    { href: '/sources', label: 'المصادر', icon: Rss, roles: ['director'] as Role[] },
    { href: '/agents', label: 'مراقبة النظام', icon: Activity, roles: ['director'] as Role[] },
    { href: '/services/fact-check', label: 'التحقق والاستقصاء', icon: ShieldCheck, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'fact_checker', 'print_editor'] as Role[] },
    { href: '/settings', label: 'إعدادات APIs', icon: KeyRound, roles: ['director'] as Role[] },
];

export default function Sidebar() {
    const pathname = usePathname();
    const { user } = useAuth();
    const [collapsed, setCollapsed] = useState(false);
    const role = ((user?.role || '') as Role);
    const visibleNav = navItems.filter((item) => item.roles.includes(role));

    return (
        <aside
            className={cn(
                'fixed top-0 right-0 h-screen z-40 transition-all duration-300 ease-in-out',
                'bg-[#0F172A] border-slate-800/70',
                'border-l flex flex-col',
                collapsed ? 'w-[72px]' : 'w-[260px]'
            )}
        >
            {/* Logo */}
            <div className="flex items-center gap-3 px-4 h-16 border-b border-white/10">
                <div className="w-9 h-9 rounded-xl border flex items-center justify-center overflow-hidden bg-white/5 border-white/15">
                    <img src="/ech-logo.png" alt="Echorouk" className="w-7 h-7 object-contain" />
                </div>
                {!collapsed && (
                    <div className="overflow-hidden">
                        <h1 className="text-sm font-bold truncate text-white">غرفة الشروق</h1>
                        <p className="text-[10px] font-medium text-slate-300">النظام الذكي v1.0</p>
                    </div>
                )}
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
                {visibleNav.map((item) => {
                    const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                'flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group relative',
                                isActive
                                    ? 'bg-blue-500/20 text-white shadow-inner'
                                    : 'text-slate-300 hover:text-white hover:bg-white/8'
                            )}
                        >
                            {isActive && (
                                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-[#2563EB]" />
                            )}
                            <item.icon className={cn('w-5 h-5 flex-shrink-0', isActive && 'drop-shadow-[0_0_6px_rgba(37,99,235,0.5)]')} />
                            {!collapsed && (
                                <span className="text-sm font-medium">{item.label}</span>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* System Status */}
            {!collapsed && (
                <div className="px-3 py-3 mx-2 mb-3 rounded-xl border bg-white/[0.03] border-white/10">
                    <div className="flex items-center gap-2">
                        <Activity className="w-4 h-4 text-[#2563EB]" />
                        <span className="text-xs text-slate-300">النظام يعمل</span>
                        <span className="w-2 h-2 rounded-full animate-pulse mr-auto bg-[#2563EB]" />
                    </div>
                </div>
            )}

            {/* Collapse Toggle */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="flex items-center justify-center h-10 border-t transition-colors border-white/10 text-slate-400 hover:text-white"
            >
                {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
        </aside>
    );
}
