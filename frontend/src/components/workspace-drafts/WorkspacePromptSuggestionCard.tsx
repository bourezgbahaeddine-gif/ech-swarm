'use client';

import NextLink from 'next/link';
import { Sparkles } from 'lucide-react';

import type { WorkspacePromptSuggestion } from '@/lib/api';

type WorkspacePromptSuggestionCardProps = {
    suggestion: WorkspacePromptSuggestion;
    isPending?: boolean;
    onRun: () => void;
};

export function WorkspacePromptSuggestionCard({
    suggestion,
    isPending = false,
    onRun,
}: WorkspacePromptSuggestionCardProps) {
    return (
        <div className="mt-3 rounded-2xl border border-fuchsia-500/20 bg-fuchsia-500/10 p-3 text-right">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                    <div className="inline-flex items-center gap-2 rounded-full border border-fuchsia-500/25 bg-fuchsia-500/10 px-2.5 py-1 text-[10px] text-fuchsia-100">
                        <Sparkles className="h-3.5 w-3.5" />
                        القالب الذكي المقترح الآن
                    </div>
                    <div className="text-sm font-semibold text-white">{suggestion.task_label}</div>
                    <p className="max-w-3xl text-[11px] leading-6 text-fuchsia-50/90">{suggestion.reason}</p>
                    <div className="flex flex-wrap gap-2 text-[10px] text-slate-300">
                        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                            {suggestion.template_title}
                        </span>
                        <span className="rounded-full border border-white/10 bg-white/5 px-2 py-1">
                            {suggestion.word_count} كلمة تقريبًا
                        </span>
                        {suggestion.auto_apply_default ? (
                            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 text-emerald-200">
                                سيُطبَّق تلقائيًا عند نجاح التوليد
                            </span>
                        ) : null}
                    </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <button
                        type="button"
                        disabled={isPending}
                        onClick={onRun}
                        className="min-h-10 rounded-xl border border-fuchsia-400/30 bg-fuchsia-500/15 px-4 py-2 text-xs font-medium text-fuchsia-50 disabled:opacity-60"
                    >
                        {isPending ? 'جاري التوليد...' : 'شغّل التوليد الذكي'}
                    </button>
                    <NextLink
                        href={suggestion.playbook_href}
                        className="min-h-10 rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-xs text-slate-200"
                    >
                        راجع القالب
                    </NextLink>
                </div>
            </div>
            <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
                {suggestion.auto_filled_fields.slice(0, 4).map((field) => (
                    <div key={`${field.label}-${field.value}`} className="rounded-xl border border-white/10 bg-black/20 px-3 py-2">
                        <div className="text-[10px] text-slate-400">{field.label}</div>
                        <div className="mt-1 line-clamp-2 text-[11px] text-white">{field.value}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}
