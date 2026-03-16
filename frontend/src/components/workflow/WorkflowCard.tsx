'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { ArrowLeft, Clock3 } from 'lucide-react';

import { cn, formatRelativeTime, getStatusColor, truncate } from '@/lib/utils';
import { workflowText } from '@/lib/workflow-language';

export type WorkflowTone = 'default' | 'warn' | 'danger' | 'success';

export type WorkflowChip = {
    label: string;
    className?: string;
};

export function WorkflowCard({
    title,
    subtitle,
    statusLabel,
    statusClassName,
    chips = [],
    reason,
    nextActionLabel,
    timestamp,
    blockers = [],
    tone = 'default',
    compact = false,
    primaryAction,
    actions,
}: {
    title: string;
    subtitle?: string;
    statusLabel?: string;
    statusClassName?: string;
    chips?: WorkflowChip[];
    reason: string;
    nextActionLabel: string;
    timestamp?: string | null;
    blockers?: string[];
    tone?: WorkflowTone;
    compact?: boolean;
    primaryAction?: { label: string; href: string; onClick?: () => void };
    actions?: ReactNode;
}) {
    const toneClasses =
        tone === 'danger'
            ? 'border-rose-500/25 bg-rose-500/10'
            : tone === 'warn'
              ? 'border-amber-500/25 bg-amber-500/10'
              : tone === 'success'
                ? 'border-emerald-500/25 bg-emerald-500/10'
                : 'border-white/10 bg-white/5';

    return (
        <div className={cn('rounded-2xl border', compact ? 'px-3 py-3' : 'px-4 py-4', toneClasses)} dir="rtl">
            <div className={cn('flex items-start justify-between gap-4', compact && 'gap-3')}>
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <h3 className={cn('font-semibold text-white leading-6', compact ? 'text-base line-clamp-2' : 'text-sm')}>
                            {title}
                        </h3>
                        {statusLabel && (
                            <span className={cn('px-2 py-0.5 rounded-md text-[10px] font-medium border', statusClassName || getStatusColor((statusLabel || '').toLowerCase()))}>
                                {statusLabel}
                            </span>
                        )}
                        {chips.map((chip) => (
                            <span
                                key={`${title}-${chip.label}`}
                                className={cn(
                                    'rounded-md border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-300',
                                    chip.className,
                                )}
                            >
                                {chip.label}
                            </span>
                        ))}
                    </div>

                    {subtitle && <div className={cn('mt-1 text-slate-400', compact ? 'text-[11px]' : 'text-xs')}>{subtitle}</div>}

                    <div className={cn('text-slate-200 leading-6', compact ? 'mt-2 text-[12px] line-clamp-2' : 'mt-3 text-sm')}>
                        {truncate(reason, compact ? 120 : 190)}
                    </div>
                    <div className={cn('text-cyan-200', compact ? 'mt-1.5 text-[11px]' : 'mt-2 text-xs')}>
                        {workflowText.nextActionLabel}: <span className="font-semibold">{nextActionLabel}</span>
                    </div>

                    {blockers.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-1.5">
                            {blockers.slice(0, 2).map((blocker) => (
                                <span
                                    key={`${title}-${blocker}`}
                                    className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-100"
                                >
                                    عائق: {truncate(blocker, 80)}
                                </span>
                            ))}
                        </div>
                    )}
                </div>

                <div className={cn('flex shrink-0 flex-col items-end', compact ? 'gap-2' : 'gap-3')}>
                    {timestamp && (
                        <div className="inline-flex items-center gap-1 text-[11px] text-slate-400">
                            <Clock3 className="w-3.5 h-3.5" />
                            {formatRelativeTime(timestamp)}
                        </div>
                    )}
                    {primaryAction && (
                        <Link
                            href={primaryAction.href}
                            onClick={primaryAction.onClick}
                            className={cn(
                                'inline-flex items-center gap-2 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-xs text-cyan-100 hover:bg-cyan-500/20',
                                compact ? 'px-2.5 py-2' : 'px-3 py-2',
                            )}
                        >
                            <span>{primaryAction.label}</span>
                            <ArrowLeft className="w-3.5 h-3.5" />
                        </Link>
                    )}
                </div>
            </div>

            {actions && <div className={compact ? 'mt-3' : 'mt-4'}>{actions}</div>}
        </div>
    );
}

export function WorkflowSection({
    title,
    hint,
    count,
    icon,
    emptyLabel,
    children,
}: {
    title: string;
    hint: string;
    count?: number;
    icon?: ReactNode;
    emptyLabel?: string;
    children?: ReactNode;
}) {
    return (
        <section className="rounded-3xl border border-white/10 bg-[rgba(15,23,42,0.55)] p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                    <div className="flex items-center gap-2 text-white">
                        {icon}
                        <h2 className="text-lg font-semibold">{title}</h2>
                    </div>
                    <p className="mt-1 text-xs text-slate-400">{hint}</p>
                </div>
                {typeof count === 'number' && <div className="text-xs text-slate-500">{count} عنصر</div>}
            </div>

            {children || (
                <div className="rounded-2xl border border-dashed border-white/10 px-4 py-6 text-center text-sm text-slate-400">
                    {emptyLabel || 'لا توجد عناصر الآن.'}
                </div>
            )}
        </section>
    );
}
