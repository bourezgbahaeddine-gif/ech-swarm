'use client';

import type { CSSProperties } from 'react';
import { useEffect, useMemo, useState } from 'react';

export function TutorialOverlay({
    open,
    stepLabel,
    title,
    description,
    targetSelector,
    primaryLabel,
    onPrimary,
    onSkip,
}: {
    open: boolean;
    stepLabel: string;
    title: string;
    description: string;
    targetSelector?: string;
    primaryLabel: string;
    onPrimary: () => void;
    onSkip: () => void;
}) {
    const [rect, setRect] = useState<DOMRect | null>(null);

    useEffect(() => {
        if (!open) return;
        const el = targetSelector ? (document.querySelector(targetSelector) as HTMLElement | null) : null;
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            const nextRect = el.getBoundingClientRect();
            setRect(nextRect);
            const prevOutline = el.style.outline;
            const prevShadow = el.style.boxShadow;
            el.style.outline = '2px solid rgba(34,211,238,0.9)';
            el.style.boxShadow = '0 0 0 6px rgba(14,116,144,0.35)';
            return () => {
                el.style.outline = prevOutline;
                el.style.boxShadow = prevShadow;
            };
        }
        setRect(null);
        return undefined;
    }, [open, targetSelector]);

    const highlightStyle = useMemo(() => {
        if (!rect) return undefined;
        return {
            top: Math.max(0, rect.top - 8),
            left: Math.max(0, rect.left - 8),
            width: rect.width + 16,
            height: rect.height + 16,
        } as CSSProperties;
    }, [rect]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[80] pointer-events-none" dir="rtl">
            <div className="absolute inset-0 bg-black/35" />
            {rect && <div className="absolute rounded-2xl border-2 border-cyan-400/70 shadow-[0_0_0_6px_rgba(14,116,144,0.35)]" style={highlightStyle} />}
            <div className="absolute bottom-6 right-6 max-w-md rounded-2xl border border-white/15 bg-slate-950/95 p-4 text-sm text-white pointer-events-auto">
                <div className="text-[11px] text-cyan-200">{stepLabel}</div>
                <div className="mt-2 text-base font-semibold">{title}</div>
                <div className="mt-2 text-xs text-slate-300 leading-6">{description}</div>
                <div className="mt-3 flex items-center gap-2">
                    <button
                        onClick={onPrimary}
                        className="rounded-xl border border-cyan-500/40 bg-cyan-500/15 px-3 py-2 text-xs text-cyan-100"
                    >
                        {primaryLabel}
                    </button>
                    <button
                        onClick={onSkip}
                        className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300"
                    >
                        تخطي
                    </button>
                </div>
            </div>
        </div>
    );
}
