'use client';

import { useState, useSyncExternalStore } from 'react';
import { Sparkles, X } from 'lucide-react';

type OnboardingStep = {
    title: string;
    description: string;
};

export function RoleOnboardingBanner({
    storageKey,
    title,
    description,
    steps,
}: {
    storageKey: string;
    title: string;
    description: string;
    steps: OnboardingStep[];
}) {
    const [dismissed, setDismissed] = useState(false);
    const seen = useSyncExternalStore(
        () => () => {},
        () => {
            if (typeof window === 'undefined') return true;
            return Boolean(window.localStorage.getItem(storageKey));
        },
        () => true,
    );
    const visible = !dismissed && !seen;

    const dismiss = () => {
        if (typeof window !== 'undefined') {
            window.localStorage.setItem(storageKey, '1');
        }
        setDismissed(true);
    };

    if (!visible) return null;

    return (
        <section className="rounded-3xl border border-cyan-500/20 bg-cyan-500/10 p-4">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <div className="flex items-center gap-2 text-white">
                        <Sparkles className="w-4 h-4 text-cyan-200" />
                        <h2 className="text-sm font-semibold">{title}</h2>
                    </div>
                    <p className="mt-2 text-sm text-cyan-50/90 leading-6">{description}</p>
                </div>
                <button
                    type="button"
                    onClick={dismiss}
                    className="inline-flex items-center justify-center rounded-lg border border-white/15 bg-white/5 p-2 text-cyan-100 hover:bg-white/10"
                    aria-label="إخفاء الدليل"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>

            <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-cyan-50/90">
                {steps.map((step) => (
                    <div key={step.title} className="rounded-2xl border border-white/10 bg-black/10 p-3">
                        <div className="font-semibold text-white mb-1">{step.title}</div>
                        <div>{step.description}</div>
                    </div>
                ))}
            </div>
        </section>
    );
}
