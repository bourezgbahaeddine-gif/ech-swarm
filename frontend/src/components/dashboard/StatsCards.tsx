'use client';

import Link from 'next/link';
import { type DashboardStats } from '@/lib/api';
import { cn } from '@/lib/utils';
import {
    Newspaper,
    Clock,
    CheckCircle,
    XCircle,
    Send,
    Zap,
    Rss,
    Bot,
    Timer,
} from 'lucide-react';

interface StatsCardsProps {
    stats: DashboardStats | undefined;
    isLoading: boolean;
}

interface StatCardProps {
    label: string;
    value: number | string;
    icon: React.ElementType;
    color: string;
    glowColor: string;
    trend?: string;
    href?: string;
}

function StatCard({ label, value, icon: Icon, color, glowColor, trend, href }: StatCardProps) {
    const content = (
        <div
            className={cn(
                'relative overflow-hidden rounded-2xl p-5',
                'bg-gradient-to-br from-gray-800/50 to-gray-900/80',
                'border border-white/5 hover:border-white/10',
                'group transition-all duration-300 hover:scale-[1.02] hover:shadow-xl',
                href && 'cursor-pointer',
            )}
        >
            <div
                className={cn(
                    'absolute -top-12 -left-12 w-24 h-24 rounded-full blur-2xl opacity-20 group-hover:opacity-40 transition-opacity',
                    glowColor,
                )}
            />

            <div className="relative flex items-start justify-between">
                <div>
                    <p className="text-xs text-gray-500 mb-1">{label}</p>
                    <p className="text-2xl font-bold text-white tracking-tight">
                        {typeof value === 'number' ? value.toLocaleString('ar-DZ') : value}
                    </p>
                    {trend && <p className="text-[10px] text-emerald-400 mt-1">{trend}</p>}
                </div>
                <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center', color)}>
                    <Icon className="w-5 h-5 text-white" />
                </div>
            </div>
        </div>
    );

    if (!href) return content;
    return (
        <Link href={href} className="block">
            {content}
        </Link>
    );
}

function StatCardSkeleton() {
    return (
        <div className="rounded-2xl p-5 bg-gray-800/30 border border-white/5 animate-pulse">
            <div className="flex items-start justify-between">
                <div className="space-y-2">
                    <div className="h-3 w-16 bg-gray-700 rounded" />
                    <div className="h-7 w-12 bg-gray-700 rounded" />
                </div>
                <div className="w-10 h-10 rounded-xl bg-gray-700" />
            </div>
        </div>
    );
}

export default function StatsCards({ stats, isLoading }: StatsCardsProps) {
    if (isLoading) {
        return (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
                {Array.from({ length: 10 }).map((_, i) => (
                    <StatCardSkeleton key={i} />
                ))}
            </div>
        );
    }

    const cards: StatCardProps[] = [
        {
            label: 'إجمالي الأخبار',
            value: stats?.total_articles || 0,
            icon: Newspaper,
            color: 'bg-blue-500/20',
            glowColor: 'bg-blue-500',
            href: '/dashboard/metric/total-articles',
        },
        {
            label: 'أخبار اليوم',
            value: stats?.articles_today || 0,
            icon: Clock,
            color: 'bg-cyan-500/20',
            glowColor: 'bg-cyan-500',
            trend: 'محدثة مباشرة',
            href: '/dashboard/metric/today-articles',
        },
        {
            label: 'بانتظار المراجعة',
            value: stats?.pending_review || 0,
            icon: Clock,
            color: 'bg-amber-500/20',
            glowColor: 'bg-amber-500',
            href: '/dashboard/metric/pending-review',
        },
        {
            label: 'تمت الموافقة',
            value: stats?.approved || 0,
            icon: CheckCircle,
            color: 'bg-emerald-500/20',
            glowColor: 'bg-emerald-500',
            href: '/dashboard/metric/approved',
        },
        {
            label: 'تم الرفض',
            value: stats?.rejected || 0,
            icon: XCircle,
            color: 'bg-red-500/20',
            glowColor: 'bg-red-500',
            href: '/dashboard/metric/rejected',
        },
        {
            label: 'تم النشر',
            value: stats?.published || 0,
            icon: Send,
            color: 'bg-violet-500/20',
            glowColor: 'bg-violet-500',
            href: '/dashboard/metric/published',
        },
        {
            label: 'أخبار عاجلة',
            value: stats?.breaking_news || 0,
            icon: Zap,
            color: 'bg-rose-500/20',
            glowColor: 'bg-rose-500',
            href: '/dashboard/metric/breaking-news',
        },
        {
            label: 'المصادر النشطة',
            value: `${stats?.sources_active || 0}/${stats?.sources_total || 0}`,
            icon: Rss,
            color: 'bg-orange-500/20',
            glowColor: 'bg-orange-500',
            href: '/dashboard/metric/sources-active',
        },
        {
            label: 'استدعاءات AI اليوم',
            value: stats?.ai_calls_today || 0,
            icon: Bot,
            color: 'bg-indigo-500/20',
            glowColor: 'bg-indigo-500',
            href: '/dashboard/metric/ai-calls',
        },
        {
            label: 'متوسط المعالجة',
            value: stats?.avg_processing_ms ? `${Math.round(stats.avg_processing_ms)}ms` : '—',
            icon: Timer,
            color: 'bg-teal-500/20',
            glowColor: 'bg-teal-500',
            href: '/dashboard/metric/avg-processing',
        },
    ];

    return (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {cards.map((card) => (
                <StatCard key={card.label} {...card} />
            ))}
        </div>
    );
}
