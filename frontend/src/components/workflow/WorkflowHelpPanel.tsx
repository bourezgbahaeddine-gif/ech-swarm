'use client';

import { Info } from 'lucide-react';

import { workflowText } from '@/lib/workflow-language';

export function WorkflowHelpPanel({
    title = workflowText.quickGuideTitle,
    items,
}: {
    title?: string;
    items: Array<{ title: string; description: string }>;
}) {
    return (
        <section className="rounded-3xl border border-white/10 bg-white/5 p-4">
            <div className="flex items-center gap-2 text-white mb-3">
                <Info className="w-4 h-4 text-cyan-300" />
                <h2 className="text-sm font-semibold">{title}</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-300">
                {items.map((item) => (
                    <div key={item.title} className="rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                        <div className="font-semibold text-white mb-1">{item.title}</div>
                        <div>{item.description}</div>
                    </div>
                ))}
            </div>
        </section>
    );
}
