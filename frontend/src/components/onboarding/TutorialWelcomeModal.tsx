'use client';

export function TutorialWelcomeModal({
    open,
    onSelectRole,
    onSkip,
}: {
    open: boolean;
    onSelectRole: (role: 'journalist' | 'editor_chief') => void;
    onSkip: () => void;
}) {
    if (!open) return null;

    return (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/60 px-4" dir="rtl">
            <div className="w-full max-w-lg rounded-3xl border border-white/10 bg-slate-950/95 p-6 text-white">
                <div className="text-sm text-cyan-200">?????? ?? ?? ???? ???????</div>
                <h2 className="mt-2 text-2xl font-semibold">???? ??? ???? ???? ??????</h2>
                <p className="mt-3 text-sm text-slate-300 leading-7">
                    ??? ???? ???? ????? ???? ?? ???? ??? ???? ???? ????? ?? ??????? ??? ????????. ???? ???? ????? ??? ???? ????.
                </p>
                <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <button
                        onClick={() => onSelectRole('journalist')}
                        className="rounded-2xl border border-emerald-500/30 bg-emerald-500/15 px-4 py-3 text-sm text-emerald-100"
                    >
                        ??? ????
                    </button>
                    <button
                        onClick={() => onSelectRole('editor_chief')}
                        className="rounded-2xl border border-cyan-500/30 bg-cyan-500/15 px-4 py-3 text-sm text-cyan-100"
                    >
                        ??? ???? ?????
                    </button>
                </div>
                <button
                    onClick={onSkip}
                    className="mt-4 text-xs text-slate-400 underline"
                >
                    ???? ????
                </button>
            </div>
        </div>
    );
}
