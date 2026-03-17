'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { useRouter } from 'next/navigation';
import {
    AlertTriangle,
    CheckCircle2,
    FileSearch,
    FileUp,
    LibraryBig,
    Loader2,
    Newspaper,
    ScanSearch,
    Sparkles,
} from 'lucide-react';

import {
    documentIntelApi,
    editorialApi,
    type DocumentIntelClaim,
    type DocumentIntelEntity,
    type DocumentIntelExtractJobStatus,
    type DocumentIntelExtractResult,
    type DocumentIntelNewsItem,
    type DocumentIntelStoryAngle,
} from '@/lib/api';
import { useAuth } from '@/lib/auth';

const RUN_ROLES = new Set(['director', 'editor_chief', 'journalist', 'social_media', 'print_editor']);
const CREATE_DRAFT_ROLES = new Set(['director', 'editor_chief', 'journalist', 'print_editor']);

function apiError(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) return detail;
    }
    return fallback;
}

function documentTypeLabel(value?: string): string {
    switch ((value || '').toLowerCase()) {
        case 'official_gazette':
            return '????? ????? / ????? ?????';
        case 'statement':
            return '???? ?? ?????';
        case 'scanned_document':
            return '????? ?????? ??????';
        case 'report':
        default:
            return '????? ?? ????? ???????';
    }
}

function claimTypeLabel(value?: string): string {
    switch ((value || '').toLowerCase()) {
        case 'legal':
            return '????? ??????';
        case 'statistical':
            return '????? ????';
        case 'attribution':
            return '???? / ?????';
        case 'factual':
        default:
            return '????? ??????';
    }
}

function entityTypeLabel(value?: string): string {
    switch ((value || '').toLowerCase()) {
        case 'location':
            return '????';
        case 'person':
            return '???';
        case 'organization':
        default:
            return '??? / ?????';
    }
}

function nextActionText(result: DocumentIntelExtractResult | null): string {
    if (!result) return '???? ???? ????? ????? ??? ????? ??????? ?????.';
    if (result.news_candidates.length > 0) return '???? ?????? ???? ??? ???? ??? ????? ???? ??????.';
    if (result.claims.length > 0) return '???? ????????? ????????? ???? ?? ????? ?????? ??? ???????.';
    if (result.data_points.length > 0) return '????? ?? ?????? ??????? ????? ????? ??????? ?? ???? ????.';
    return '???? ??????? ????? ?? ???? ?? ??????? ?????? ??????? ??????.';
}

function riskBadgeClass(value?: string): string {
    switch ((value || '').toLowerCase()) {
        case 'high':
            return 'border-red-500/30 bg-red-500/15 text-red-200';
        case 'medium':
            return 'border-amber-500/30 bg-amber-500/15 text-amber-200';
        default:
            return 'border-emerald-500/30 bg-emerald-500/15 text-emerald-200';
    }
}

export default function DocumentIntelPage() {
    const router = useRouter();
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canRun = RUN_ROLES.has(role);
    const canCreateDraft = CREATE_DRAFT_ROLES.has(role);

    const [file, setFile] = useState<File | null>(null);
    const [languageHint, setLanguageHint] = useState<'ar' | 'fr' | 'en' | 'auto'>('ar');
    const [maxNewsItems, setMaxNewsItems] = useState(8);
    const [maxDataPoints, setMaxDataPoints] = useState(30);
    const [error, setError] = useState<string | null>(null);
    const [createdWorkId, setCreatedWorkId] = useState<string | null>(null);
    const [jobId, setJobId] = useState<string | null>(null);
    const [showTechDetails, setShowTechDetails] = useState(false);

    const runExtract = useMutation({
        mutationFn: () =>
            documentIntelApi.submitExtractJob({
                file: file as File,
                language_hint: languageHint,
                max_news_items: maxNewsItems,
                max_data_points: maxDataPoints,
            }),
        onSuccess: (res) => {
            setJobId(res.data.job_id);
            setError(null);
            setCreatedWorkId(null);
        },
        onError: (err) => setError(apiError(err, '???? ????? ??????? ??? ???????.')),
    });

    const extractStatusQuery = useQuery({
        queryKey: ['document-intel-job', jobId],
        queryFn: () => documentIntelApi.getExtractJobStatus(jobId as string),
        enabled: !!jobId,
        refetchInterval: (q) => {
            const status = (q.state.data?.data as DocumentIntelExtractJobStatus | undefined)?.status;
            if (!status || status === 'completed' || status === 'failed' || status === 'dead_lettered') return false;
            return 1500;
        },
    });

    const createDraftFromCandidate = useMutation({
        mutationFn: (candidate: DocumentIntelNewsItem) =>
            editorialApi.createManualWorkspaceDraft({
                title: candidate.headline,
                summary: candidate.summary,
                body: `${candidate.summary}

${candidate.evidence}`,
                category: 'international',
                urgency: 'normal',
                source_action: 'document_intel_pdf',
            }),
        onSuccess: (res) => {
            const workId = (res.data as { work_id?: string })?.work_id;
            if (!workId) {
                setError('?? ????? ??????? ??? ?? ??? ????? ???? ?????.');
                return;
            }
            setCreatedWorkId(workId);
            setError(null);
            router.push(`/workspace-drafts?work_id=${encodeURIComponent(workId)}`);
        },
        onError: (err) => setError(apiError(err, '???? ????? ????? ?? ????? ??????.')),
    });

    const statusPayload = extractStatusQuery.data?.data;
    const result: DocumentIntelExtractResult | null =
        statusPayload?.status === 'completed' && statusPayload.result ? statusPayload.result : null;
    const derivedError =
        statusPayload?.status === 'failed' || statusPayload?.status === 'dead_lettered'
            ? statusPayload.error || '??? ????? ???????.'
            : null;
    const effectiveError = error || derivedError;
    const extractStatus = statusPayload?.status ?? null;
    const isProcessing = runExtract.isPending || extractStatus === 'queued' || extractStatus === 'running';
    const extractStatusText =
        extractStatus === 'queued'
            ? '??????? ?? ???????'
            : extractStatus === 'running'
              ? '???? ????? ???????'
              : extractStatus === 'completed'
                ? '????? ???????'
                : extractStatus === 'failed' || extractStatus === 'dead_lettered'
                  ? '??? ???????'
                  : null;

    const overviewClaims = useMemo(() => (result?.claims || []).slice(0, 5), [result]);
    const overviewEntities = useMemo(() => (result?.entities || []).slice(0, 8), [result]);
    const overviewAngles = useMemo(() => (result?.story_angles || []).slice(0, 4), [result]);

    return (
        <div className="space-y-5 app-theme-shell" dir="rtl">
            <div className="space-y-2">
                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                    <FileSearch className="w-6 h-6 text-cyan-400" />
                    ????? ???????
                </h1>
                <p className="text-sm text-gray-400">
                    ???? ????? PDF ??????? ???? ????? ???????? ??????? ?????? ???????? ??????? ?????? ????? ??????? ??? ??? ????.
                </p>
            </div>

            {effectiveError && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{effectiveError}</div>}

            <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-4">
                <div className="grid grid-cols-1 lg:grid-cols-[1.6fr_1fr] gap-4">
                    <label className="h-12 px-3 rounded-xl border border-white/10 bg-white/5 text-sm text-gray-200 flex items-center gap-2 cursor-pointer">
                        <FileUp className="w-4 h-4 text-cyan-300" />
                        <span className="line-clamp-1">{file ? file.name : '???? ??? PDF ???????'}</span>
                        <input type="file" accept=".pdf,application/pdf" className="hidden" onChange={(e) => setFile(e.target.files?.[0] || null)} />
                    </label>

                    <button onClick={() => runExtract.mutate()} disabled={!canRun || !file || isProcessing} className="h-12 rounded-xl border border-emerald-500/30 bg-emerald-500/20 text-emerald-200 text-sm disabled:opacity-50 flex items-center justify-center gap-2">
                        {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                        ????? ???????
                    </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <label className="space-y-1">
                        <span className="text-xs text-gray-400">??? ???????</span>
                        <select value={languageHint} onChange={(e) => setLanguageHint(e.target.value as 'ar' | 'fr' | 'en' | 'auto')} className="w-full h-10 px-3 rounded-lg border border-white/10 bg-white/5 text-sm text-gray-200">
                            <option value="ar">???????</option>
                            <option value="fr">????????</option>
                            <option value="en">??????????</option>
                            <option value="auto">??? ??????</option>
                        </select>
                    </label>
                    <label className="space-y-1">
                        <span className="text-xs text-gray-400">??? ??????? ???????</span>
                        <input type="number" min={1} max={20} value={maxNewsItems} onChange={(e) => setMaxNewsItems(Math.max(1, Math.min(20, Number(e.target.value) || 1)))} className="w-full h-10 px-3 rounded-lg border border-white/10 bg-white/5 text-sm text-gray-200" />
                    </label>
                    <label className="space-y-1">
                        <span className="text-xs text-gray-400">??? ?????? ???????</span>
                        <input type="number" min={5} max={120} value={maxDataPoints} onChange={(e) => setMaxDataPoints(Math.max(5, Math.min(120, Number(e.target.value) || 5)))} className="w-full h-10 px-3 rounded-lg border border-white/10 bg-white/5 text-sm text-gray-200" />
                    </label>
                </div>

                {jobId && <div className="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-2 text-xs text-cyan-200">{extractStatusText ? `${extractStatusText} - ` : ''}???? ??????: {jobId}</div>}
            </section>

            {result && (
                <>
                    <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-cyan-950/40 via-slate-950/40 to-slate-900/50 p-5 space-y-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="space-y-2">
                                <p className="text-xs text-cyan-300">Overview</p>
                                <h2 className="text-xl font-bold text-white">{documentTypeLabel(result.document_type)}</h2>
                                <p className="text-sm text-gray-300 leading-7 max-w-4xl">{result.document_summary || '?? ????? ????? ????? ??????? ???.'}</p>
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 min-w-[260px] space-y-2">
                                <div className="text-xs text-gray-400">?? ??????? ???????</div>
                                <div className="text-sm text-white leading-6">{nextActionText(result)}</div>
                                <div className="flex flex-wrap gap-2 pt-1">
                                    {canCreateDraft && result.news_candidates[0] ? (
                                        <button onClick={() => createDraftFromCandidate.mutate(result.news_candidates[0])} disabled={createDraftFromCandidate.isPending} className="h-9 px-3 rounded-lg border border-emerald-500/30 bg-emerald-500/20 text-emerald-200 text-xs disabled:opacity-50">
                                            {createDraftFromCandidate.isPending ? '???? ????? ???????...' : '???? ?????'}
                                        </button>
                                    ) : null}
                                    <button onClick={() => router.push('/services/fact-check')} className="h-9 px-3 rounded-lg border border-amber-500/30 bg-amber-500/15 text-amber-200 text-xs">???? ??????</button>
                                    <button onClick={() => router.push('/memory')} className="h-9 px-3 rounded-lg border border-white/10 bg-white/5 text-gray-200 text-xs">???? ?? ???????</button>
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 text-xs">
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">??????? ???????</div><div className="text-white text-xl font-semibold mt-1">{result.news_candidates.length}</div></div>
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">?????????</div><div className="text-white text-xl font-semibold mt-1">{result.claims.length}</div></div>
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">????????</div><div className="text-white text-xl font-semibold mt-1">{result.entities.length}</div></div>
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">?????? ???????</div><div className="text-white text-xl font-semibold mt-1">{result.data_points.length}</div></div>
                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-gray-400">????? ????????</div><div className="text-white text-xl font-semibold mt-1">{result.detected_language}</div></div>
                        </div>
                    </section>

                    <section className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-4">
                        <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-4">
                            <div className="flex items-center gap-2 text-white font-semibold"><Newspaper className="w-4 h-4 text-cyan-300" />News & Angles</div>

                            {result.news_candidates.length === 0 ? (
                                <p className="text-sm text-gray-500">?? ??? ??????? ????? ????? ????? ?? ???????.</p>
                            ) : (
                                <div className="space-y-3">
                                    {result.news_candidates.map((item) => (
                                        <article key={item.rank} className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
                                            <div className="flex items-center justify-between gap-3">
                                                <p className="text-xs text-cyan-300">??? ???? #{item.rank}</p>
                                                <span className="text-xs text-gray-400">??? {Math.round(item.confidence * 100)}%</span>
                                            </div>
                                            <h3 className="text-base text-white font-semibold leading-7">{item.headline}</h3>
                                            <p className="text-sm text-gray-300 leading-7">{item.summary}</p>
                                            {item.entities.length > 0 ? <div className="flex flex-wrap gap-2">{item.entities.map((entity) => <span key={`${item.rank}-${entity}`} className="px-2 py-1 rounded-full border border-white/10 bg-white/5 text-[11px] text-gray-300">{entity}</span>)}</div> : null}
                                            <div className="flex flex-wrap gap-2">
                                                {canCreateDraft ? <button onClick={() => createDraftFromCandidate.mutate(item)} disabled={createDraftFromCandidate.isPending} className="h-9 px-3 rounded-lg border border-emerald-500/30 bg-emerald-500/20 text-emerald-200 text-xs disabled:opacity-50">????? ???</button> : null}
                                                <button onClick={() => router.push('/stories')} className="h-9 px-3 rounded-lg border border-white/10 bg-white/5 text-gray-200 text-xs">???? ???</button>
                                            </div>
                                        </article>
                                    ))}
                                </div>
                            )}

                            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 space-y-3">
                                <div className="text-sm font-semibold text-white">????? ??????? ??????</div>
                                {overviewAngles.length === 0 ? (
                                    <p className="text-sm text-gray-500">?? ???? ????? ????? ???? ??? ???? ?????? ??? ??????? ??????? ??????????.</p>
                                ) : (
                                    <div className="space-y-3">{overviewAngles.map((angle: DocumentIntelStoryAngle, idx) => <div key={`${angle.title}-${idx}`} className="rounded-lg border border-white/10 bg-black/20 p-3"><div className="text-sm text-white font-medium leading-6">{angle.title}</div><div className="text-xs text-gray-400 leading-6 mt-1">{angle.why_it_matters}</div></div>)}</div>
                                )}
                            </div>
                        </div>

                        <div className="space-y-4">
                            <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                                <div className="flex items-center gap-2 text-white font-semibold"><AlertTriangle className="w-4 h-4 text-amber-300" />Evidence & Data</div>

                                <div className="space-y-2">
                                    <div className="text-xs text-gray-400">????????? ?????????</div>
                                    {overviewClaims.length === 0 ? (
                                        <p className="text-sm text-gray-500">?? ??????? ??????? ????? ???.</p>
                                    ) : (
                                        overviewClaims.map((claim: DocumentIntelClaim, idx) => (
                                            <div key={`${claim.text}-${idx}`} className="rounded-xl border border-white/10 bg-white/[0.03] p-3 space-y-2">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <span className="px-2 py-1 rounded-full border border-cyan-500/20 bg-cyan-500/10 text-[11px] text-cyan-200">{claimTypeLabel(claim.type)}</span>
                                                    <span className={`px-2 py-1 rounded-full border text-[11px] ${riskBadgeClass(claim.risk_level)}`}>{claim.risk_level === 'high' ? '????? ?????' : claim.risk_level === 'medium' ? '????? ??????' : '????? ??????'}</span>
                                                    <span className="text-[11px] text-gray-400">??? {Math.round(claim.confidence * 100)}%</span>
                                                </div>
                                                <p className="text-sm text-gray-200 leading-6">{claim.text}</p>
                                            </div>
                                        ))
                                    )}
                                </div>

                                <div className="space-y-2">
                                    <div className="text-xs text-gray-400">???????? ???????</div>
                                    {overviewEntities.length === 0 ? (
                                        <p className="text-sm text-gray-500">?? ???? ?????? ????? ???.</p>
                                    ) : (
                                        <div className="flex flex-wrap gap-2">{overviewEntities.map((entity: DocumentIntelEntity) => <div key={`${entity.name}-${entity.type}`} className="px-3 py-2 rounded-xl border border-white/10 bg-white/[0.03] text-xs text-gray-200"><span className="font-medium text-white">{entity.name}</span><span className="text-gray-400"> - {entityTypeLabel(entity.type)}</span></div>)}</div>
                                    )}
                                </div>

                                <div className="space-y-2">
                                    <div className="text-xs text-gray-400">?????? ???????</div>
                                    {result.data_points.length === 0 ? (
                                        <p className="text-sm text-gray-500">?? ???? ???? ????? ?????.</p>
                                    ) : (
                                        <div className="space-y-2 max-h-[260px] overflow-auto">{result.data_points.slice(0, 8).map((item) => <div key={item.rank} className="rounded-xl border border-white/10 bg-white/[0.03] p-3"><div className="text-xs text-cyan-300 mb-1">#{item.rank} - {item.category}</div><div className="text-xs text-gray-100">{item.value_tokens.join(' | ')}</div><div className="text-xs text-gray-400 mt-1 leading-5">{item.context}</div></div>)}</div>
                                    )}
                                </div>
                            </section>
                        </div>
                    </section>

                    <section className="grid grid-cols-1 xl:grid-cols-[1.35fr_0.65fr] gap-4">
                        <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                            <div className="flex items-center gap-2 text-white font-semibold"><ScanSearch className="w-4 h-4 text-cyan-300" />Document View</div>
                            <pre className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-xs text-gray-300 leading-7 max-h-[520px] overflow-auto whitespace-pre-wrap">{result.preview_text || '?? ???? ?????? ????.'}</pre>
                        </section>

                        <section className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                            <div className="flex items-center justify-between gap-3">
                                <div className="flex items-center gap-2 text-white font-semibold"><LibraryBig className="w-4 h-4 text-cyan-300" />???????? ???????</div>
                                <button onClick={() => setShowTechDetails((prev) => !prev)} className="h-8 px-3 rounded-lg border border-white/10 bg-white/5 text-gray-200 text-xs">{showTechDetails ? '?????' : '?????'}</button>
                            </div>

                            {showTechDetails ? (
                                <div className="space-y-3">
                                    <div className="grid grid-cols-2 gap-2 text-xs">
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">???????: <span className="text-white">{result.parser_used}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">?????: <span className="text-white">{result.detected_language}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">???????: <span className="text-white">{result.stats.pages ?? '--'}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">???????: <span className="text-white">{result.stats.characters}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">???????: <span className="text-white">{result.stats.paragraphs}</span></div>
                                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-gray-300">????????: <span className="text-white">{result.stats.headings}</span></div>
                                    </div>
                                    {result.headings.length > 0 ? <div className="space-y-2"><div className="text-xs text-gray-400">???????? ?????????</div><div className="space-y-2">{result.headings.slice(0, 10).map((heading, idx) => <div key={`${heading}-${idx}`} className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-xs text-gray-300">{heading}</div>)}</div></div> : null}
                                    {result.warnings.length > 0 ? <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">{result.warnings.join(' | ')}</div> : <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200"><CheckCircle2 className="w-4 h-4" />?? ???? ??????? ????? ?????.</div>}
                                </div>
                            ) : (
                                <p className="text-sm text-gray-500">???????? ??????? ????? ??? ?????? ??? ??? ???? ??????? ??????? ??????.</p>
                            )}
                        </section>
                    </section>

                    {createdWorkId && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-200">?? ????? ????? ????? ?????: {createdWorkId}</div>}
                </>
            )}
        </div>
    );
}
