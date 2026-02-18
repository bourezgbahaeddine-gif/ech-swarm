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
    { href: '/workspace-drafts', label: 'المحرر الذكي', icon: FolderGit2, roles: ['director', 'editor_chief', 'journalist', 'print_editor'] as Role[] },
    { href: '/trends', label: 'رادار التراند', icon: TrendingUp, roles: ['director', 'editor_chief', 'journalist', 'print_editor'] as Role[] },
    { href: '/constitution', label: 'الدستور', icon: FileText, roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker'] as Role[] },
    { href: '/services/multimedia', label: 'الوسائط', icon: Film, roles: ['director', 'social_media'] as Role[] },
    { href: '/team', label: 'فريق التحرير', icon: Users, roles: ['director', 'editor_chief'] as Role[] },
    { href: '/sources', label: 'المصادر', icon: Rss, roles: ['director'] as Role[] },
    { href: '/agents', label: 'مراقبة النظام', icon: Activity, roles: ['director'] as Role[] },
    { href: '/services/fact-check', label: 'التحقق والاستقصاء', icon: ShieldCheck, roles: ['director', 'editor_chief', 'journalist', 'fact_checker', 'print_editor'] as Role[] },
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
                'bg-gradient-to-b from-gray-900 via-gray-900 to-gray-950',
                'border-l border-white/5 flex flex-col',
                collapsed ? 'w-[72px]' : 'w-[260px]'
            )}
        >
            {/* Logo */}
            <div className="flex items-center gap-3 px-4 h-16 border-b border-white/5">
                <div className="w-9 h-9 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden">
                    <img src="/ech-logo.png" alt="Echorouk" className="w-7 h-7 object-contain" />
                </div>
                {!collapsed && (
                    <div className="overflow-hidden">
                        <h1 className="text-sm font-bold text-white truncate">غرفة الشروق</h1>
                        <p className="text-[10px] text-emerald-400/80 font-medium">النظام الذكي v1.0</p>
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
                                    ? 'bg-emerald-500/15 text-emerald-400 shadow-inner'
                                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                            )}
                        >
                            {isActive && (
                                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-emerald-400" />
                            )}
                            <item.icon className={cn('w-5 h-5 flex-shrink-0', isActive && 'drop-shadow-[0_0_6px_rgba(52,211,153,0.5)]')} />
                            {!collapsed && (
                                <span className="text-sm font-medium">{item.label}</span>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* System Status */}
            {!collapsed && (
                <div className="px-3 py-3 mx-2 mb-3 rounded-xl bg-white/[0.02] border border-white/5">
                    <div className="flex items-center gap-2">
                        <Activity className="w-4 h-4 text-emerald-400" />
                        <span className="text-xs text-gray-400">النظام يعمل</span>
                        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse mr-auto" />
                    </div>
                </div>
            )}

            {/* Collapse Toggle */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="flex items-center justify-center h-10 border-t border-white/5 text-gray-500 hover:text-white transition-colors"
            >
                {collapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </button>
        </aside>
    );
}
