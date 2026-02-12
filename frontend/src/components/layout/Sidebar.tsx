'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
    LayoutDashboard,
    Newspaper,
    Rss,
    UserCheck,
    Bot,
    TrendingUp,
    Activity,
    ChevronLeft,
    ChevronRight,
    Users,
    KeyRound,
    FileText,
    Sparkles,
    ShieldCheck,
    TrendingUp as SeoIcon,
    Film,
} from 'lucide-react';
import { useState } from 'react';

const navItems = [
    { href: '/', label: 'لوحة القيادة', labelEn: 'Dashboard', icon: LayoutDashboard },
    { href: '/news', label: 'الأخبار', labelEn: 'News', icon: Newspaper },
    { href: '/editorial', label: 'قسم التحرير', labelEn: 'Editorial', icon: UserCheck },
    { href: '/sources', label: 'المصادر', labelEn: 'Sources', icon: Rss },
    { href: '/agents', label: 'الوكلاء', labelEn: 'Agents', icon: Bot },
    { href: '/trends', label: 'رادار التراند', labelEn: 'Trends', icon: TrendingUp },
    { href: '/team', label: 'فريق التحرير', labelEn: 'Team', icon: Users },
    { href: '/settings', label: 'إعدادات APIs', labelEn: 'API Settings', icon: KeyRound },
    { href: '/constitution', label: 'الدستور', labelEn: 'Constitution', icon: FileText },
    { href: '/services/editor', label: 'خدمات التحرير', labelEn: 'Editor Services', icon: Sparkles },
    { href: '/services/fact-check', label: 'التحقق والاستقصاء', labelEn: 'Fact-Check', icon: ShieldCheck },
    { href: '/services/seo', label: 'خدمات SEO', labelEn: 'SEO', icon: SeoIcon },
    { href: '/services/multimedia', label: 'الوسائط', labelEn: 'Multimedia', icon: Film },
];

export default function Sidebar() {
    const pathname = usePathname();
    const [collapsed, setCollapsed] = useState(false);

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
                        <p className="text-[10px] text-emerald-400/80 font-medium">AI SWARM v1.0</p>
                    </div>
                )}
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
                {navItems.map((item) => {
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
                                <div className="flex flex-col">
                                    <span className="text-sm font-medium">{item.label}</span>
                                    <span className="text-[10px] text-gray-500">{item.labelEn}</span>
                                </div>
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
