'use client';
/* eslint-disable @typescript-eslint/no-explicit-any, react-hooks/set-state-in-effect, react-hooks/exhaustive-deps */

import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { EditorContent, useEditor } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import Highlight from '@tiptap/extension-highlight';
import { AlertTriangle, CheckCircle2, Clock3, Loader2, Save, SearchCheck, Sparkles } from 'lucide-react';

import { editorialApi } from '@/lib/api';
import { cn, formatRelativeTime, truncate } from '@/lib/utils';

type SaveState = 'saved' | 'saving' | 'unsaved' | 'error';
type RightTab = 'evidence' | 'quality' | 'seo' | 'social' | 'context';

const TABS: Array<{ id: RightTab; label: string }> = [
    { id: 'evidence', label: 'Evidence / Fact-check' },
    { id: 'quality', label: 'Quality Score' },
    { id: 'seo', label: 'SEO Tools' },
    { id: 'social', label: 'Social Versions' },
    { id: 'context', label: 'Story Context' },
];

export default function WorkspaceDraftsPage() {
    const queryClient = useQueryClient();
    const search = useSearchParams();
    const articleId = search.get('article_id');
    const initialWork = search.get('work_id');

    const [workId, setWorkId] = useState<string | null>(initialWork || null);
    const [title, setTitle] = useState('');
    const [bodyHtml, setBodyHtml] = useState('');
    const [baseVersion, setBaseVersion] = useState(1);
    const [saveState, setSaveState] = useState<SaveState>('saved');
    const [activeTab, setActiveTab] = useState<RightTab>('evidence');
    const [err, setErr] = useState<string | null>(null);
    const [ok, setOk] = useState<string | null>(null);
    const [claims, setClaims] = useState<any[]>([]);
    const [quality, setQuality] = useState<any | null>(null);
    const [seoPack, setSeoPack] = useState<any | null>(null);
    const [social, setSocial] = useState<any | null>(null);
    const [readiness, setReadiness] = useState<any | null>(null);
    const [headlines, setHeadlines] = useState<any[]>([]);
    const [suggestion, setSuggestion] = useState<any | null>(null);
    const [diffView, setDiffView] = useState<string>('');
    const [cmpFrom, setCmpFrom] = useState<number | null>(null);
    const [cmpTo, setCmpTo] = useState<number | null>(null);

    const { data: listData, isLoading: listLoading } = useQuery({
        queryKey: ['smart-editor-list', articleId],
        queryFn: () => editorialApi.workspaceDrafts({ status: 'draft', limit: 200, article_id: articleId ? Number(articleId) : undefined }),
    });
    const drafts = listData?.data || [];

    useEffect(() => {
        if (workId || drafts.length === 0) return;
        setWorkId(initialWork || drafts[0].work_id);
    }, [workId, drafts, initialWork]);

    const { data: contextData, isLoading: contextLoading } = useQuery({
        queryKey: ['smart-editor-context', workId],
        queryFn: () => editorialApi.smartContext(workId!),
        enabled: !!workId,
    });
    const { data: versionsData } = useQuery({
        queryKey: ['smart-editor-versions', workId],
        queryFn: () => editorialApi.draftVersions(workId!),
        enabled: !!workId,
    });
    const context = contextData?.data;
    const versions = versionsData?.data || [];

    const editor = useEditor({
        extensions: [
            StarterKit,
            Highlight,
            Link.configure({ openOnClick: false }),
            Placeholder.configure({ placeholder: 'ابدأ صياغة الخبر...' }),
        ],
        content: '',
        immediatelyRender: false,
        editorProps: {
            attributes: {
                class: 'smart-editor-content min-h-[520px] p-6 text-[15px] leading-8 text-white focus:outline-none',
                dir: 'rtl',
            },
        },
        onUpdate({ editor: ed }) {
            setBodyHtml(ed.getHTML());
            setSaveState('unsaved');
        },
    });

    useEffect(() => {
        const draft = context?.draft;
        if (!draft || !editor) return;
        setTitle(draft.title || '');
        setBodyHtml(draft.body || '');
        editor.commands.setContent(draft.body || '<p></p>', { emitUpdate: false });
        setBaseVersion(draft.version || 1);
        setSaveState('saved');
        setSuggestion(null);
    }, [context?.draft?.id, editor]);

    useEffect(() => {
        if (!versions.length) return;
        if (!cmpTo) setCmpTo(versions[0].version);
        if (!cmpFrom && versions.length > 1) setCmpFrom(versions[1].version);
    }, [versions, cmpFrom, cmpTo]);

    const autosave = useMutation({
        mutationFn: () => editorialApi.autosaveWorkspaceDraft(workId!, { title, body: bodyHtml, based_on_version: baseVersion, note: 'autosave_smart_editor' }),
        onSuccess: (res) => {
            setSaveState('saved');
            setBaseVersion(res.data?.draft?.version || baseVersion);
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
        },
        onError: (e: any) => {
            setSaveState('error');
            setErr(e?.response?.data?.detail || 'Autosave failed');
        },
    });

    useEffect(() => {
        if (!workId || saveState !== 'unsaved') return;
        const t = window.setTimeout(() => {
            setSaveState('saving');
            autosave.mutate();
        }, 1200);
        return () => window.clearTimeout(t);
    }, [saveState, workId, title, bodyHtml]);

    const rewrite = useMutation({
        mutationFn: () => editorialApi.aiRewriteSuggestion(workId!, { mode: 'formal' }),
        onSuccess: (res) => {
            setSuggestion(res.data?.suggestion || null);
            setActiveTab('quality');
        },
    });
    const applySuggestion = useMutation({
        mutationFn: () => editorialApi.applyAiSuggestion(workId!, { title: suggestion?.title, body: suggestion?.body_html || '', based_on_version: baseVersion, suggestion_tool: 'rewrite' }),
        onSuccess: (res) => {
            const draft = res.data?.draft;
            if (draft && editor) {
                setTitle(draft.title || '');
                setBodyHtml(draft.body || '');
                editor.commands.setContent(draft.body || '<p></p>', { emitUpdate: false });
                setBaseVersion(draft.version);
            }
            setSuggestion(null);
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
        },
    });

    const runVerifier = useMutation({ mutationFn: () => editorialApi.verifyClaims(workId!, 0.7), onSuccess: (r) => { setClaims(r.data?.claims || []); setActiveTab('evidence'); } });
    const runQuality = useMutation({ mutationFn: () => editorialApi.qualityScore(workId!), onSuccess: (r) => { setQuality(r.data); setActiveTab('quality'); } });
    const runSeo = useMutation({ mutationFn: () => editorialApi.aiSeoSuggestion(workId!), onSuccess: (r) => { setSeoPack(r.data); setActiveTab('seo'); } });
    const runSocial = useMutation({ mutationFn: () => editorialApi.aiSocialVariants(workId!), onSuccess: (r) => { setSocial(r.data?.variants || null); setActiveTab('social'); } });
    const runHeadlines = useMutation({ mutationFn: () => editorialApi.aiHeadlineSuggestion(workId!, 5), onSuccess: (r) => { setHeadlines(r.data?.headlines || []); setActiveTab('seo'); } });
    const runReadiness = useMutation({ mutationFn: () => editorialApi.publishReadiness(workId!), onSuccess: (r) => setReadiness(r.data) });
    const runDiff = useMutation({ mutationFn: () => editorialApi.draftDiff(workId!, cmpFrom!, cmpTo!), onSuccess: (r) => setDiffView(r.data?.diff || '') });
    const restoreVersion = useMutation({
        mutationFn: (version: number) => editorialApi.restoreWorkspaceDraftVersion(workId!, version),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
        },
    });
    const applyToArticle = useMutation({
        mutationFn: () => editorialApi.applyWorkspaceDraft(workId!),
        onSuccess: () => setOk('Draft applied'),
        onError: (e: any) => setErr(e?.response?.data?.detail || 'Apply failed'),
    });

    const saveNode = useMemo(() => {
        if (saveState === 'saved') return <span className="text-emerald-300 flex items-center gap-1"><CheckCircle2 className="w-4 h-4" />Saved</span>;
        if (saveState === 'saving') return <span className="text-sky-300 flex items-center gap-1"><Loader2 className="w-4 h-4 animate-spin" />Saving...</span>;
        if (saveState === 'unsaved') return <span className="text-amber-300 flex items-center gap-1"><Clock3 className="w-4 h-4" />Unsaved</span>;
        return <span className="text-red-300 flex items-center gap-1"><AlertTriangle className="w-4 h-4" />Save error</span>;
    }, [saveState]);

    if (listLoading) return <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 text-center text-gray-300">Loading...</div>;
    if (!drafts.length) return <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 text-center text-gray-400">No drafts available.</div>;

    return (
        <div className="space-y-4">
            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                        <h1 className="text-xl font-semibold text-white">Echorouk Smart News Editor</h1>
                        <p className="text-xs text-gray-400">Replacement mode: rich editor + AI suggestions + evidence + publish gate</p>
                    </div>
                    <div className="text-xs">{saveNode}</div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => runVerifier.mutate()} className="px-3 py-2 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-200 text-xs flex items-center gap-2"><SearchCheck className="w-4 h-4" />Verify</button>
                    <button onClick={() => rewrite.mutate()} className="px-3 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-200 text-xs flex items-center gap-2"><Sparkles className="w-4 h-4" />Improve</button>
                    <button onClick={() => runHeadlines.mutate()} className="px-3 py-2 rounded-xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-200 text-xs">Headlines</button>
                    <button onClick={() => runSeo.mutate()} className="px-3 py-2 rounded-xl bg-fuchsia-500/20 border border-fuchsia-500/30 text-fuchsia-200 text-xs">SEO</button>
                    <button onClick={() => runSocial.mutate()} className="px-3 py-2 rounded-xl bg-sky-500/20 border border-sky-500/30 text-sky-200 text-xs">Social</button>
                    <button onClick={() => runQuality.mutate()} className="px-3 py-2 rounded-xl bg-violet-500/20 border border-violet-500/30 text-violet-200 text-xs">Quality</button>
                    <button onClick={() => runReadiness.mutate()} className="px-3 py-2 rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-200 text-xs">Publish gate</button>
                    <button onClick={() => applyToArticle.mutate()} className="px-3 py-2 rounded-xl bg-white/10 border border-white/15 text-gray-200 text-xs">Apply</button>
                    <button onClick={() => { setSaveState('saving'); autosave.mutate(); }} className="px-3 py-2 rounded-xl bg-white/10 border border-white/15 text-gray-200 text-xs flex items-center gap-2"><Save className="w-4 h-4" />Save</button>
                </div>
                {(err || ok) && <div className={cn('mt-3 rounded-xl px-3 py-2 text-xs', err ? 'bg-red-500/15 text-red-200 border border-red-500/30' : 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/30')}>{err || ok}</div>}
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
                <aside className="xl:col-span-3 space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                        <h2 className="text-sm text-white mb-2">Drafts</h2>
                        <div className="space-y-2 max-h-[260px] overflow-auto">
                            {drafts.map((d) => (
                                <button key={`${d.work_id}-${d.id}`} onClick={() => setWorkId(d.work_id)} className={cn('w-full text-right rounded-xl border p-2', workId === d.work_id ? 'border-emerald-400/40 bg-emerald-500/10' : 'border-white/10 bg-white/5')}>
                                    <div className="text-xs text-gray-200">{truncate(d.title || 'Untitled', 58)}</div>
                                    <div className="text-[10px] text-gray-500 mt-1">{formatRelativeTime(d.updated_at)}</div>
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                        <h2 className="text-sm text-white mb-2">Source / Metadata</h2>
                        {contextLoading ? <p className="text-xs text-gray-500">Loading...</p> : (
                            <div className="text-xs space-y-2">
                                <p className="text-gray-200" dir="rtl">{context?.article?.original_title || '—'}</p>
                                <p className="text-gray-400">{context?.article?.router_rationale || '—'}</p>
                                <div className="rounded-xl border border-white/10 bg-black/25 p-2 text-gray-300 max-h-56 overflow-auto" dir="rtl">
                                    {context?.article?.summary || context?.article?.original_content || 'No source text'}
                                </div>
                            </div>
                        )}
                    </div>
                </aside>

                <main className="xl:col-span-6 space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 overflow-hidden">
                        <div className="border-b border-white/10 p-4">
                            <input value={title} onChange={(e) => { setTitle(e.target.value); setSaveState('unsaved'); }} className="w-full rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white text-lg" dir="rtl" />
                            <p className="text-xs text-gray-500 mt-2">Work: {workId} · v{baseVersion}</p>
                        </div>
                        {editor && (
                            <BubbleMenu editor={editor}>
                                <div className="rounded-xl bg-gray-950/95 border border-white/20 p-1 flex gap-1 text-xs">
                                    <button onClick={() => editor.chain().focus().toggleBold().run()} className="px-2 py-1 rounded bg-white/10">B</button>
                                    <button onClick={() => editor.chain().focus().toggleItalic().run()} className="px-2 py-1 rounded bg-white/10">I</button>
                                    <button onClick={() => editor.chain().focus().toggleHighlight().run()} className="px-2 py-1 rounded bg-white/10">Mark</button>
                                </div>
                            </BubbleMenu>
                        )}
                        <EditorContent editor={editor} />
                    </div>

                    {suggestion && (
                        <div className="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4 space-y-2">
                            <h3 className="text-sm text-amber-200">AI suggestion (diff)</h3>
                            <pre className="max-h-56 overflow-auto text-xs text-amber-50 bg-black/25 rounded-xl p-2" dir="ltr">{suggestion.diff || ''}</pre>
                            <div className="flex gap-2">
                                <button onClick={() => applySuggestion.mutate()} className="px-3 py-2 rounded-xl bg-emerald-500/30 text-emerald-100 text-xs">Accept as new version</button>
                                <button onClick={() => setSuggestion(null)} className="px-3 py-2 rounded-xl bg-white/10 text-gray-300 text-xs">Reject</button>
                            </div>
                        </div>
                    )}
                </main>

                <aside className="xl:col-span-3 space-y-4">
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
                        <div className="flex flex-wrap gap-2">
                            {TABS.map((t) => (
                                <button key={t.id} onClick={() => setActiveTab(t.id)} className={cn('px-2 py-1 rounded-lg text-[11px]', activeTab === t.id ? 'bg-emerald-500/20 text-emerald-200' : 'bg-white/10 text-gray-300')}>{t.label}</button>
                            ))}
                        </div>
                    </div>

                    {activeTab === 'evidence' && <Panel title="Claims">{claims.length ? claims.map((c) => <Row key={c.id} text={`${Math.round(c.confidence * 100)}% · ${c.text}`} danger={c.blocking} />) : <Empty text="No claims yet" />}</Panel>}
                    {activeTab === 'quality' && <Panel title="Quality">{quality ? <pre className="text-xs whitespace-pre-wrap text-gray-200">{JSON.stringify(quality, null, 2)}</pre> : <Empty text="Run quality engine" />}{readiness && <pre className="text-xs whitespace-pre-wrap text-amber-100">{JSON.stringify(readiness, null, 2)}</pre>}</Panel>}
                    {activeTab === 'seo' && <Panel title="SEO">{seoPack ? <pre className="text-xs whitespace-pre-wrap text-gray-200">{JSON.stringify({ ...seoPack, headlines }, null, 2)}</pre> : <Empty text="Run SEO/headlines" />}</Panel>}
                    {activeTab === 'social' && <Panel title="Social">{social ? <pre className="text-xs whitespace-pre-wrap text-gray-200">{JSON.stringify(social, null, 2)}</pre> : <Empty text="Run social generator" />}</Panel>}
                    {activeTab === 'context' && (
                        <Panel title="Story + Versions">
                            <div className="space-y-1 max-h-32 overflow-auto">
                                {versions.map((v) => (
                                    <button key={v.id} onClick={() => restoreVersion.mutate(v.version)} className="w-full text-right rounded bg-white/5 px-2 py-1 text-xs text-gray-200">
                                        v{v.version} · {v.change_origin || 'manual'}
                                    </button>
                                ))}
                            </div>
                            <div className="flex gap-2 mt-2">
                                <select value={cmpFrom || ''} onChange={(e) => setCmpFrom(Number(e.target.value))} className="flex-1 bg-white/10 rounded px-2 py-1 text-xs">{versions.map((v) => <option key={`f-${v.id}`} value={v.version}>from v{v.version}</option>)}</select>
                                <select value={cmpTo || ''} onChange={(e) => setCmpTo(Number(e.target.value))} className="flex-1 bg-white/10 rounded px-2 py-1 text-xs">{versions.map((v) => <option key={`t-${v.id}`} value={v.version}>to v{v.version}</option>)}</select>
                                <button onClick={() => runDiff.mutate()} className="px-2 py-1 rounded bg-white/10 text-xs">Diff</button>
                            </div>
                            <pre className="max-h-36 overflow-auto text-[11px] text-gray-200 whitespace-pre-wrap mt-2" dir="ltr">{diffView}</pre>
                        </Panel>
                    )}
                </aside>
            </div>
        </div>
    );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
    return (
        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-2">
            <h3 className="text-sm text-white">{title}</h3>
            {children}
        </div>
    );
}

function Empty({ text }: { text: string }) {
    return <p className="text-xs text-gray-500">{text}</p>;
}

function Row({ text, danger }: { text: string; danger?: boolean }) {
    return <div className={cn('rounded-xl border p-2 text-xs', danger ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100')} dir="rtl">{text}</div>;
}
