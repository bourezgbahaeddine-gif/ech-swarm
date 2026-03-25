'use client';

import type { ReactNode } from 'react';

type PanelProps = {
    title: string;
    children: ReactNode;
};

type EmptyProps = {
    text: string;
};

type InfoBlockProps = {
    label: string;
    value?: string;
    formatValue?: (value?: string) => string;
};

export function WorkspacePanel({ title, children }: PanelProps) {
    return (
        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
            <h3 className="mb-3 text-sm font-semibold text-white">{title}</h3>
            {children}
        </div>
    );
}

export function WorkspaceEmpty({ text }: EmptyProps) {
    return <p className="text-xs text-gray-500">{text}</p>;
}

export function WorkspaceInfoBlock({ label, value, formatValue }: InfoBlockProps) {
    const resolved = formatValue ? formatValue(value) : value || '-';
    return (
        <div className="rounded-xl border border-white/10 bg-black/20 p-2">
            <p className="mb-1 text-xs text-gray-400">{label}</p>
            <p className="text-xs text-gray-200">{resolved}</p>
        </div>
    );
}
