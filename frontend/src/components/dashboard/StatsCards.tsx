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
    trend?: string;
    href?: string;
}

function StatCard({ label, value, icon: Icon, color, trend, href }: StatCardProps) {
    const content = (
        <div
            className={cn(
                'rounded-2xl p-5 border app-surface',
                'group transition-all duration-200 hover:shadow-md',
                href && 'cursor-pointer',
            )}
        >
            <div className="relative flex items-start justify-between">
                <div>
                    <p className="text-xs app-text-muted mb-1">{label}</p>
                    <p className="text-2xl font-bold tracking-tight text-[var(--text-primary)]">
                        {typeof value === 'number' ? value.toLocaleString('ar-DZ') : value}
                    </p>
                    {trend && <p className="text-[10px] mt-1" style={{ color: 'var(--semantic-success)' }}>{trend}</p>}
                </div>
                <div className={cn('w-10 h-10 rounded-xl flex items-center justify-center border', color)}>
                    <Icon className="w-5 h-5" />
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
        <div className="rounded-2xl p-5 app-surface border animate-pulse">
            <div className="flex items-start justify-between">
                <div className="space-y-2">
                    <div className="h-3 w-16 rounded app-surface-soft border" />
                    <div className="h-7 w-12 rounded app-surface-soft border" />
                </div>
                <div className="w-10 h-10 rounded-xl app-surface-soft border" />
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
            color: 'text-[var(--semantic-info)] bg-[var(--semantic-info-bg)] border-sky-200/80',
            href: '/dashboard/metric/total-articles',
        },
        {
            label: 'أخبار اليوم',
            value: stats?.articles_today || 0,
            icon: Clock,
            color: 'text-[var(--accent-blue)] bg-blue-50 border-blue-200/80',
            trend: 'محدثة مباشرة',
            href: '/dashboard/metric/today-articles',
        },
        {
            label: 'بانتظار المراجعة',
            value: stats?.pending_review || 0,
            icon: Clock,
            color: 'text-[var(--semantic-warning)] bg-amber-50 border-amber-200/90',
            href: '/dashboard/metric/pending-review',
        },
        {
            label: 'تمت الموافقة',
            value: stats?.approved || 0,
            icon: CheckCircle,
            color: 'text-[var(--semantic-success)] bg-emerald-50 border-emerald-200/90',
            href: '/dashboard/metric/approved',
        },
        {
            label: 'تم الرفض',
            value: stats?.rejected || 0,
            icon: XCircle,
            color: 'text-[var(--semantic-danger)] bg-red-50 border-red-200/90',
            href: '/dashboard/metric/rejected',
        },
        {
            label: 'تم النشر',
            value: stats?.published || 0,
            icon: Send,
            color: 'text-[var(--accent-blue)] bg-blue-50 border-blue-200/90',
            href: '/dashboard/metric/published',
        },
        {
            label: 'أخبار عاجلة',
            value: stats?.breaking_news || 0,
            icon: Zap,
            color: 'text-[var(--semantic-danger)] bg-red-50 border-red-200/90',
            href: '/dashboard/metric/breaking-news',
        },
        {
            label: 'المصادر النشطة',
            value: `${stats?.sources_active || 0}/${stats?.sources_total || 0}`,
            icon: Rss,
            color: 'text-[var(--semantic-warning)] bg-amber-50 border-amber-200/90',
            href: '/dashboard/metric/sources-active',
        },
        {
            label: 'استدعاءات AI اليوم',
            value: stats?.ai_calls_today || 0,
            icon: Bot,
            color: 'text-[var(--accent-blue)] bg-blue-50 border-blue-200/90',
            href: '/dashboard/metric/ai-calls',
        },
        {
            label: 'متوسط المعالجة',
            value: stats?.avg_processing_ms ? `${Math.round(stats.avg_processing_ms)}ms` : '—',
            icon: Timer,
            color: 'text-[var(--semantic-info)] bg-[var(--semantic-info-bg)] border-sky-200/80',
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
