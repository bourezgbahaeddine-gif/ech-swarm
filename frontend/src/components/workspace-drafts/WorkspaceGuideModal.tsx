'use client';

type WorkspaceGuideModalProps = {
    open: boolean;
    title: string;
    items?: Array<{ label: string; value: string; tone?: 'default' | 'warn' }>;
    introLines?: string[];
    confirmLabel: string;
    onClose: () => void;
    onConfirm: () => void;
};

export function WorkspaceGuideModal({
    open,
    title,
    items = [],
    introLines = [],
    confirmLabel,
    onClose,
    onConfirm,
}: WorkspaceGuideModalProps) {
    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
            <div className="w-full max-w-2xl space-y-4 rounded-2xl border border-white/10 bg-gray-950 p-5" dir="rtl">
                <h2 className="text-lg font-semibold text-white">{title}</h2>

                {introLines.length ? (
                    <div className="space-y-2 text-sm text-gray-300">
                        {introLines.map((line) => (
                            <p key={line}>{line}</p>
                        ))}
                    </div>
                ) : null}

                {items.length ? (
                    <div className="space-y-3 text-sm text-gray-300">
                        {items.map((item) => (
                            <div
                                key={`${item.label}-${item.value}`}
                                className={
                                    item.tone === 'warn'
                                        ? 'rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-amber-100'
                                        : 'rounded-xl border border-white/10 bg-black/20 p-3'
                                }
                            >
                                <p className="mb-1 text-xs text-gray-400">{item.label}</p>
                                <p>{item.value}</p>
                            </div>
                        ))}
                    </div>
                ) : null}

                <div className="flex items-center justify-end gap-2">
                    <button onClick={onClose} className="rounded-xl border border-white/20 px-4 py-2 text-sm text-gray-300">
                        إغلاق
                    </button>
                    <button
                        onClick={onConfirm}
                        className="rounded-xl border border-emerald-400/40 bg-emerald-500/25 px-4 py-2 text-sm text-emerald-100"
                    >
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
