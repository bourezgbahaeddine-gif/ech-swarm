/**
 * Echorouk AI Swarm — Utility Functions
 */

import { clsx, type ClassValue } from 'clsx';

export function cn(...inputs: ClassValue[]) {
    return clsx(inputs);
}

export function formatDate(date: string | null): string {
    if (!date) return '—';
    try {
        return new Intl.DateTimeFormat('ar-DZ', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
        }).format(new Date(date));
    } catch {
        return date;
    }
}

export function formatRelativeTime(date: string | null): string {
    if (!date) return '—';
    const now = new Date();
    const then = new Date(date);
    const diff = now.getTime() - then.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'الآن';
    if (minutes < 60) return `منذ ${minutes} دقيقة`;
    if (hours < 24) return `منذ ${hours} ساعة`;
    if (days < 7) return `منذ ${days} يوم`;
    return formatDate(date);
}

export function truncate(str: string, length: number = 100): string {
    if (!str) return '';
    if (str.length <= length) return str;
    return str.slice(0, length) + '...';
}

export function isFreshBreaking(
    isBreaking: boolean,
    crawledAt: string | null | undefined,
    ttlMinutes: number = Number(process.env.NEXT_PUBLIC_BREAKING_TTL_MINUTES || 60),
): boolean {
    if (!isBreaking || !crawledAt) return false;
    const ts = new Date(crawledAt).getTime();
    if (Number.isNaN(ts)) return false;
    return Date.now() - ts <= ttlMinutes * 60 * 1000;
}

export function getStatusColor(status: string): string {
    const colors: Record<string, string> = {
        new: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
        cleaned: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
        classified: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
        candidate: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
        approved: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        rejected: 'bg-red-500/20 text-red-400 border-red-500/30',
        published: 'bg-green-500/20 text-green-400 border-green-500/30',
        archived: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    };
    return colors[status] || 'bg-gray-500/20 text-gray-400 border-gray-500/30';
}

export function getUrgencyColor(urgency: string | null): string {
    const colors: Record<string, string> = {
        breaking: 'text-red-400 animate-pulse',
        high: 'text-orange-400',
        medium: 'text-yellow-400',
        low: 'text-gray-400',
    };
    return colors[urgency || 'low'] || 'text-gray-400';
}

export function getCategoryLabel(category: string | null): string {
    const labels: Record<string, string> = {
        politics: '🏛️ سياسة',
        economy: '💹 اقتصاد',
        sports: '⚽ رياضة',
        technology: '💻 تكنولوجيا',
        local_algeria: '🇩🇿 محلي',
        international: '🌍 دولي',
        culture: '🎭 ثقافة',
        society: '👥 مجتمع',
        health: '🏥 صحة',
        environment: '🌿 بيئة',
    };
    return labels[category || ''] || '📰 عام';
}
