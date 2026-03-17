'use client';

import { useMemo, useState, type ComponentType } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth';
import {
    Activity,
    Archive,
    BookOpen,
    CalendarClock,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    FileSearch,
    FileText,
    Film,
    FolderGit2,
    Gauge,
    GitBranch,
    KeyRound,
    LayoutDashboard,
    Library,
    Megaphone,
    MessagesSquare,
    Mic2,
    MousePointerClick,
    Newspaper,
    Radar,
    Rss,
    ScrollText,
    ShieldCheck,
    TrendingUp,
    UserCheck,
    Users,
    Wrench,
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

type NavSection = 'primary' | 'knowledge' | 'tools' | 'ops';

type NavItem = {
    href: string;
    label: string;
    icon: ComponentType<{ className?: string }>;
    roles: Role[];
    section: NavSection;
    roleLabels?: Partial<Record<Role, string>>;
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

const navItems: NavItem[] = [
    {
        href: '/today',
        label: 'Ø§Ù„ÙŠÙˆÙ…',
        icon: LayoutDashboard,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker', 'observer'],
        section: 'primary',
    },
    {
        href: '/how-editorial-os-works',
        label: 'كيف تعمل المنصة؟',
        icon: BookOpen,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker', 'observer'],
        section: 'primary',
    },
    {
        href: '/newsroom-flow',
        label: 'مسار غرفة الأخبار',
        icon: GitBranch,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker', 'observer'],
        section: 'primary',
    },
    {
        href: '/',
        label: 'Ø§Ù„Ø£Ø¯Ø§Ø¡',
        icon: Gauge,
        roles: ['director'],
        section: 'primary',
    },
    {
        href: '/news',
        label: 'Ø§Ù„Ø£Ø®Ø¨Ø§Ø±',
        icon: Newspaper,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker'],
        section: 'primary',
    },
    {
        href: '/workspace-drafts',
        label: 'Ø§Ù„Ù…Ø³ÙˆØ¯Ø§Øª',
        icon: FolderGit2,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'primary',
    },
    {
        href: '/editorial',
        label: 'Ø§Ù„Ø§Ø¹ØªÙ…Ø§Ø¯',
        icon: UserCheck,
        roles: ['director', 'editor_chief', 'social_media'],
        section: 'primary',
        roleLabels: {
            social_media: 'Ù†Ø´Ø± ÙˆØ§Ø¹ØªÙ…Ø§Ø¯',
        },
    },
    {
        href: '/stories',
        label: 'Ø§Ù„Ù‚ØµØµ',
        icon: Library,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'primary',
    },
    {
        href: '/events',
        label: 'Ø§Ù„ØªØºØ·ÙŠØ§Øª',
        icon: CalendarClock,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'primary',
    },
    {
        href: '/archive',
        label: 'Ø§Ù„Ø£Ø±Ø´ÙŠÙ',
        icon: Archive,
        roles: ['editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker'],
        section: 'primary',
    },
    {
        href: '/',
        label: 'Ø§Ù„Ø£Ø¯Ø§Ø¡',
        icon: Gauge,
        roles: ['editor_chief'],
        section: 'ops',
    },
    {
        href: '/archive',
        label: 'Ø§Ù„Ø£Ø±Ø´ÙŠÙ',
        icon: Archive,
        roles: ['director'],
        section: 'knowledge',
    },
    {
        href: '/digital',
        label: 'Ø§Ù„ØªØºØ·ÙŠØ© Ø§Ù„Ø±Ù‚Ù…ÙŠØ©',
        icon: Megaphone,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'tools',
    },
    {
        href: '/constitution',
        label: 'Ø§Ù„Ø¯Ø³ØªÙˆØ± Ø§Ù„ØªØ­Ø±ÙŠØ±ÙŠ',
        icon: FileText,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor', 'fact_checker'],
        section: 'knowledge',
    },
    {
        href: '/memory',
        label: 'Ø§Ù„Ø°Ø§ÙƒØ±Ø© Ø§Ù„ØªØ­Ø±ÙŠØ±ÙŠØ©',
        icon: BookOpen,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'knowledge',
    },
    {
        href: '/services/document-intel',
        label: 'ØªØ­Ù„ÙŠÙ„ Ø§Ù„ÙˆØ«Ø§Ø¦Ù‚',
        icon: FileSearch,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'knowledge',
    },
    {
        href: '/services/media-logger',
        label: 'ØªÙØ±ÙŠØº Ø§Ù„ØªØ³Ø¬ÙŠÙ„Ø§Øª',
        icon: Mic2,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'knowledge',
    },
    {
        href: '/services/multimedia',
        label: 'Ø§Ù„ÙˆØ³Ø§Ø¦Ø·',
        icon: Film,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'tools',
    },
    {
        href: '/services/fact-check',
        label: 'Ø§Ù„ØªØ­Ù‚Ù‚ ÙˆØ§Ù„Ø§Ø³ØªÙ‚ØµØ§Ø¡',
        icon: ShieldCheck,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'fact_checker', 'print_editor'],
        section: 'tools',
    },
    {
        href: '/scripts',
        label: 'Ø§Ù„Ø³ÙƒØ±Ø¨Øª',
        icon: ScrollText,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'tools',
    },
    {
        href: '/trends',
        label: 'Ø§Ù„ØªØ±Ù†Ø¯Ø§Øª',
        icon: TrendingUp,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'tools',
    },
    {
        href: '/simulator',
        label: 'Ù…Ø­Ø§ÙƒØ§Ø© Ø§Ù„ØªÙØ§Ø¹Ù„',
        icon: MessagesSquare,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'tools',
    },
    {
        href: '/competitor-xray',
        label: 'Ø±ØµØ¯ Ø§Ù„Ù…Ù†Ø§ÙØ³ÙŠÙ†',
        icon: Radar,
        roles: ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'],
        section: 'tools',
    },
    {
        href: '/ux-insights',
        label: 'Ø³Ù„ÙˆÙƒ Ø§Ù„Ø§Ø³ØªØ®Ø¯Ø§Ù…',
        icon: MousePointerClick,
        roles: ['director', 'editor_chief'],
        section: 'ops',
    },
    {
        href: '/team',
        label: 'ÙØ±ÙŠÙ‚ Ø§Ù„ØªØ­Ø±ÙŠØ±',
        icon: Users,
        roles: ['director'],
        section: 'ops',
    },
    {
        href: '/sources',
        label: 'Ø§Ù„Ù…ØµØ§Ø¯Ø±',
        icon: Rss,
        roles: ['director'],
        section: 'ops',
    },
    {
        href: '/agents',
        label: 'Ù…Ø±Ø§Ù‚Ø¨Ø© Ø§Ù„Ù†Ø¸Ø§Ù…',
        icon: Activity,
        roles: ['director'],
        section: 'ops',
    },
    {
        href: '/settings',
        label: 'Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª APIs',
        icon: KeyRound,
        roles: ['director'],
        section: 'ops',
    },
];

const sectionLabels: Array<{ key: Exclude<NavSection, 'primary'>; label: string }> = [
    { key: 'knowledge', label: 'Ù…Ø¹Ø±ÙØ© Ù…Ø³Ø§Ù†Ø¯Ø©' },
    { key: 'tools', label: 'Ø£Ø¯ÙˆØ§Øª Ø¥Ø¶Ø§ÙÙŠØ©' },
    { key: 'ops', label: 'ØªØ´ØºÙŠÙ„ ÙˆØ¥Ø¯Ø§Ø±Ø©' },
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
    const [secondaryOpen, setSecondaryOpen] = useState(false);

    const visibleNav = useMemo(
        () => (role ? navItems.filter((item) => item.roles.includes(role)) : []),
        [role],
    );

    const primaryItems = visibleNav.filter((item) => item.section === 'primary');
    const secondarySections = sectionLabels
        .map((section) => ({
            ...section,
            items: visibleNav.filter((item) => item.section === section.key),
        }))
        .filter((section) => section.items.length > 0);

    const renderNavItem = (item: NavItem) => {
        const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
        const label = (role && item.roleLabels?.[role]) || item.label;

        return (
            <Link
                key={`${item.section}-${item.href}`}
                href={item.href}
                onClick={onCloseMobile}
                className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200 group relative',
                    isActive
                        ? 'bg-blue-500/20 text-[#F8FAFC] shadow-inner'
                        : 'text-[#CBD5E1] hover:text-[#F8FAFC] hover:bg-white/8',
                )}
            >
                {isActive && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-[#2563EB]" />
                )}
                <item.icon className={cn('w-5 h-5 flex-shrink-0', isActive && 'drop-shadow-[0_0_6px_rgba(37,99,235,0.5)]')} />
                {!collapsed && <span className="text-sm font-medium">{label}</span>}
            </Link>
        );
    };

    return (
        <>
            <button
                type="button"
                aria-label="Close sidebar overlay"
                onClick={onCloseMobile}
                className={cn(
                    'fixed inset-0 z-40 bg-black/55 backdrop-blur-[1px] md:hidden transition-opacity',
                    mobileOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none',
                )}
            />
            <aside
                className={cn(
                    'fixed top-0 right-0 h-screen z-50 transition-all duration-300 ease-in-out',
                    'bg-[#0F172A] border-slate-800/70 border-l flex flex-col',
                    'w-[86vw] max-w-[280px] md:w-auto',
                    collapsed ? 'md:w-[72px]' : 'md:w-[260px]',
                    mobileOpen ? 'translate-x-0' : 'translate-x-full md:translate-x-0',
                )}
            >
                <div className="flex items-center gap-3 px-4 h-16 border-b border-white/10">
                    <div className="w-9 h-9 rounded-xl border flex items-center justify-center overflow-hidden bg-white/5 border-white/15">
                        <Image src="/ech-logo.png" alt="Echorouk" width={28} height={28} className="w-7 h-7 object-contain" />
                    </div>
                    {!collapsed && (
                        <div className="overflow-hidden">
                            <h1 className="text-sm font-bold truncate text-[#F8FAFC]">ØºØ±ÙØ© Ø§Ù„Ø´Ø±ÙˆÙ‚</h1>
                            <p className="text-[10px] font-medium text-[#CBD5E1]">ØªØ¬Ø±Ø¨Ø© Ø¹Ù…Ù„ Ù…Ø¨Ø³Ø·Ø© Ø­Ø³Ø¨ Ø§Ù„Ø¯ÙˆØ±</p>
                        </div>
                    )}
                </div>

                <nav className="flex-1 py-4 px-2 overflow-y-auto">
                    <div className="space-y-1">
                        {primaryItems.map(renderNavItem)}
                    </div>

                    {secondarySections.length > 0 && (
                        <div className="mt-5 pt-4 border-t border-white/10">
                            {!collapsed && (
                                <button
                                    type="button"
                                    onClick={() => setSecondaryOpen((prev) => !prev)}
                                    className="w-full mb-2 px-3 py-2 rounded-xl border border-white/10 bg-white/5 text-[#CBD5E1] hover:text-white flex items-center justify-between text-xs"
                                >
                                    <span className="inline-flex items-center gap-2">
                                        <Wrench className="w-4 h-4" />
                                        Ø§Ù„Ù…Ø²ÙŠØ¯ Ù…Ù† Ø§Ù„Ø£Ø¯ÙˆØ§Øª
                                    </span>
                                    <ChevronDown className={cn('w-4 h-4 transition-transform', secondaryOpen && 'rotate-180')} />
                                </button>
                            )}

                            {(collapsed || secondaryOpen) && (
                                <div className="space-y-4">
                                    {secondarySections.map((section) => (
                                        <div key={section.key}>
                                            {!collapsed && (
                                                <div className="px-3 pb-1 text-[10px] uppercase tracking-[0.18em] text-[#64748B]">
                                                    {section.label}
                                                </div>
                                            )}
                                            <div className="space-y-1">
                                                {section.items.map(renderNavItem)}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </nav>

                {!collapsed && (
                    <div className="px-3 py-3 mx-2 mb-3 rounded-xl border bg-white/[0.03] border-white/10">
                        <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-[#2563EB]" />
                            <span className="text-xs text-[#CBD5E1]">Ø§Ù„Ù†Ø¸Ø§Ù… ÙŠØ¹Ù…Ù„</span>
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
