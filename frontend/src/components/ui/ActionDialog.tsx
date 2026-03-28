'use client';

import { useEffect, type ReactNode } from 'react';
import { AlertTriangle, X } from 'lucide-react';

import { cn } from '@/lib/utils';

type InputKind = 'text' | 'textarea' | 'number';

type ActionDialogProps = {
    open: boolean;
    title: string;
    description?: ReactNode;
    confirmLabel?: string;
    cancelLabel?: string;
    tone?: 'default' | 'danger' | 'warn';
    isSubmitting?: boolean;
    confirmDisabled?: boolean;
    onClose: () => void;
    onConfirm: () => void;
    inputKind?: InputKind;
    inputLabel?: string;
    inputPlaceholder?: string;
    inputValue?: string;
    onInputChange?: (value: string) => void;
};

const toneClasses: Record<NonNullable<ActionDialogProps['tone']>, string> = {
    default: 'border-cyan-500/30 bg-cyan-500/15 text-cyan-100',
    danger: 'border-red-500/30 bg-red-500/15 text-red-100',
    warn: 'border-amber-500/30 bg-amber-500/15 text-amber-100',
};

export function ActionDialog({
    open,
    title,
    description,
    confirmLabel = 'تأكيد',
    cancelLabel = 'إلغاء',
    tone = 'default',
    isSubmitting = false,
    confirmDisabled = false,
    onClose,
    onConfirm,
    inputKind,
    inputLabel,
    inputPlaceholder,
    inputValue = '',
    onInputChange,
}: ActionDialogProps) {
    useEffect(() => {
        if (!open) return undefined;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                onClose();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [open, onClose]);

    if (!open) return null;

    const renderInput = () => {
        if (!inputKind || !onInputChange) return null;

        if (inputKind === 'textarea') {
            return (
                <textarea
                    value={inputValue}
                    onChange={(event) => onInputChange(event.target.value)}
                    placeholder={inputPlaceholder}
                    className="min-h-[120px] w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white placeholder:text-slate-500"
                />
            );
        }

        return (
            <input
                type={inputKind}
                value={inputValue}
                onChange={(event) => onInputChange(event.target.value)}
                placeholder={inputPlaceholder}
                className="w-full rounded-xl border border-white/10 bg-slate-950/70 px-3 py-2 text-sm text-white placeholder:text-slate-500"
            />
        );
    };

    return (
        <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/75 p-4" dir="rtl">
            <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#0f172a] shadow-2xl">
                <div className="flex items-start justify-between gap-3 border-b border-white/10 px-5 py-4">
                    <div>
                        <div className={cn('inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px]', toneClasses[tone])}>
                            <AlertTriangle className="h-3.5 w-3.5" />
                            تأكيد إجراء
                        </div>
                        <h3 className="mt-2 text-lg font-semibold text-white">{title}</h3>
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-xl border border-white/10 bg-white/5 p-2 text-slate-300 transition hover:text-white"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                <div className="space-y-4 px-5 py-4">
                    {description ? <div className="text-sm leading-7 text-slate-200">{description}</div> : null}
                    {inputKind && onInputChange ? (
                        <label className="block space-y-2">
                            {inputLabel ? <span className="text-xs text-slate-300">{inputLabel}</span> : null}
                            {renderInput()}
                        </label>
                    ) : null}
                </div>

                <div className="flex items-center justify-end gap-2 border-t border-white/10 px-5 py-4">
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200"
                    >
                        {cancelLabel}
                    </button>
                    <button
                        type="button"
                        onClick={onConfirm}
                        disabled={isSubmitting || confirmDisabled}
                        className={cn(
                            'rounded-xl border px-4 py-2 text-sm transition',
                            toneClasses[tone],
                            (isSubmitting || confirmDisabled) && 'cursor-not-allowed opacity-60',
                        )}
                    >
                        {isSubmitting ? 'جاري التنفيذ...' : confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
