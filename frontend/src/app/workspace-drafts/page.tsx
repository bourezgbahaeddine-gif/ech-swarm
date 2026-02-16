'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { AlertTriangle, Bot, CheckCircle2, Copy, FileText, Filter, Loader2, PlayCircle, Search, Sparkles, Wand2 } from 'lucide-react';

import { editorialApi, newsApi, type WorkspaceDraft } from '@/lib/api';
import { journalistServicesApi } from '@/lib/journalist-services-api';
import { useAuth } from '@/lib/auth';
import { cn, formatRelativeTime, truncate } from '@/lib/utils';

type AIToolResult = {
    rewrite?: string;
    summary?: string;
    proofread?: string;
    keywords?: string;
    metadata?: string;
    imagePrompt?: string;
    infographicPrompt?: string;
};

type PipelineStepState = 'idle' | 'running' | 'done' | 'error';

export default function WorkspaceDraftsPage() {
    const queryClient = useQueryClient();
    const searchParams = useSearchParams();
    const { user } = useAuth();

    const [status, setStatus] = useState('draft');
    const [q, setQ] = useState('');
    const [articleIdFilter, setArticleIdFilter] = useState(searchParams.get('article_id') || '');
    const [selected, setSelected] = useState<WorkspaceDraft | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [ok, setOk] = useState<string | null>(null);

    const [workingTitle, setWorkingTitle] = useState('');
    const [workingBody, setWorkingBody] = useState('');
    const [seoTitle, setSeoTitle] = useState('');
    const [seoDescription, setSeoDescription] = useState('');
    const [seoKeywords, setSeoKeywords] = useState('');
    const [imageAlt, setImageAlt] = useState('');
    const [imagePrompt, setImagePrompt] = useState('');
    const [infographicPrompt, setInfographicPrompt] = useState('');
    const [selectedLanguage, setSelectedLanguage] = useState<'ar' | 'fr' | 'en'>('ar');
    const [aiResult, setAiResult] = useState<AIToolResult>({});

    const [busyAction, setBusyAction] = useState('');
    const [lastCopiedKey, setLastCopiedKey] = useState('');
    const [writerHeadlines, setWriterHeadlines] = useState<string[]>([]);
    const [writerLead, setWriterLead] = useState('');
    const [socialSnippets, setSocialSnippets] = useState<string[]>([]);
    const [pipelineSteps, setPipelineSteps] = useState<Record<string, PipelineStepState>>({
        regenerate: 'idle',
        proofread: 'idle',
        metadata: 'idle',
        keywords: 'idle',
        imagePrompt: 'idle',
        infographicPrompt: 'idle',
        social: 'idle',
    });

    const initialWorkId = searchParams.get('work_id') || '';

    const { data, isLoading } = useQuery({
        queryKey: ['workspace-drafts', status, articleIdFilter],
        queryFn: () =>
            editorialApi.workspaceDrafts({
                status,
                limit: 200,
                article_id: articleIdFilter ? Number(articleIdFilter) : undefined,
            }),
    });

    const { data: articleData } = useQuery({
        queryKey: ['workspace-article', selected?.article_id],
        queryFn: () => newsApi.get(selected!.article_id),
        enabled: !!selected?.article_id,
    });

    const applyMutation = useMutation({
        mutationFn: (workId: string) => editorialApi.applyWorkspaceDraft(workId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['workspace-drafts'] });
            queryClient.invalidateQueries({ queryKey: ['news'] });
            setSelected(null);
            setError(null);
            setOk('تم تطبيق المسودة على الخبر بنجاح');
        },
        onError: (err: any) => setError(err?.response?.data?.detail || 'تعذر تطبيق المسودة'),
    });

    const archiveMutation = useMutation({
        mutationFn: (workId: string) => editorialApi.archiveWorkspaceDraft(workId),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['workspace-drafts'] });
            setSelected(null);
            setError(null);
            setOk('تمت الأرشفة');
        },
        onError: (err: any) => setError(err?.response?.data?.detail || 'تعذر أرشفة المسودة'),
    });

    const saveMutation = useMutation({
        mutationFn: async () => {
            if (!selected) throw new Error('لا توجد مسودة محددة');
            return editorialApi.updateDraft(selected.article_id, selected.id, {
                title: workingTitle,
                body: workingBody,
                note: 'updated_in_workspace',
                version: selected.version,
            });
        },
        onSuccess: (res) => {
            queryClient.invalidateQueries({ queryKey: ['workspace-drafts'] });
            const updated = res.data;
            setSelected((prev) =>
                prev
                    ? {
                          ...prev,
                          title: updated?.title ?? prev.title,
                          body: updated?.body ?? prev.body,
                          version: updated?.version ?? prev.version,
                          updated_at: updated?.updated_at ?? prev.updated_at,
                      }
                    : prev,
            );
            setOk('تم حفظ التعديلات');
            setError(null);
        },
        onError: (err: any) => setError(err?.response?.data?.detail || 'تعذر حفظ المسودة'),
    });

    const createVersionMutation = useMutation({
        mutationFn: async () => {
            if (!selected) throw new Error('لا توجد مسودة محددة');
            return editorialApi.regenerateWorkspaceDraft(selected.work_id);
        },
        onSuccess: async (res) => {
            queryClient.invalidateQueries({ queryKey: ['workspace-drafts'] });
            const regeneratedWorkId = res.data?.work_id;
            if (regeneratedWorkId) {
                const latest = await editorialApi.workspaceDraft(regeneratedWorkId);
                if (latest?.data) {
                    setSelected(latest.data);
                }
            }
            setOk('تمت إعادة توليد المسودة بنفس Work ID مع إصدار جديد');
            setError(null);
            setStatus('draft');
        },
        onError: (err: any) => setError(err?.response?.data?.detail || 'تعذر إنشاء نسخة جديدة'),
    });

    const drafts = data?.data || [];

    const filtered = useMemo(() => {
        const needle = q.trim().toLowerCase();
        if (!needle) return drafts;
        return drafts.filter((d) =>
            d.work_id.toLowerCase().includes(needle) ||
            String(d.article_id).includes(needle) ||
            (d.title || '').toLowerCase().includes(needle) ||
            (d.source_action || '').toLowerCase().includes(needle),
        );
    }, [drafts, q]);

    const finalList = useMemo(() => {
        if (!initialWorkId) return filtered;
        return filtered.sort((a, b) => (a.work_id === initialWorkId ? -1 : b.work_id === initialWorkId ? 1 : 0));
    }, [filtered, initialWorkId]);

    useEffect(() => {
        if (selected || finalList.length === 0) return;
        if (initialWorkId) {
            const target = finalList.find((d) => d.work_id === initialWorkId);
            setSelected(target || finalList[0]);
            return;
        }
        setSelected(finalList[0]);
    }, [finalList, initialWorkId, selected]);

    useEffect(() => {
        if (!selected) return;
        setWorkingTitle(selected.title || '');
        setWorkingBody(selected.body || '');
        setSeoTitle('');
        setSeoDescription('');
        setSeoKeywords('');
        setImageAlt('');
        setImagePrompt('');
        setInfographicPrompt('');
        setAiResult({});
        setWriterHeadlines([]);
        setWriterLead('');
        setSocialSnippets([]);
        setPipelineSteps({
            regenerate: 'idle',
            proofread: 'idle',
            metadata: 'idle',
            keywords: 'idle',
            imagePrompt: 'idle',
            infographicPrompt: 'idle',
            social: 'idle',
        });
        const title = `${selected.title || ''} ${selected.body || ''}`;
        const hasArabic = /[\u0600-\u06FF]/.test(title);
        const hasFrench = /[éèêàùçôîïâ]/i.test(title);
        setSelectedLanguage(hasArabic ? 'ar' : hasFrench ? 'fr' : 'en');
    }, [selected?.id]);

    const cleanAiText = (raw: string) => {
        if (!raw) return '';
        let t = raw.trim();
        t = t.replace(/^```[\s\S]*?\n/, '').replace(/```$/, '').trim();
        t = t.replace(/^(here('?s| is)|note:|explanation:).*/gim, '').trim();
        t = t.replace(/\*\*/g, '').replace(/^[-*]\s+/gm, '');
        return t.trim();
    };

    const wpPackage = useMemo(() => {
        const title = (workingTitle || selected?.title || '').trim();
        const body = (workingBody || '').trim();
        const blocks = body
            .split(/\n{2,}/)
            .map((p) => p.trim())
            .filter(Boolean)
            .map((p) => `<p>${p}</p>`)
            .join('\n\n');

        return `<h1>${title}</h1>\n\n${blocks}\n\n<hr />\n<h3>بيانات SEO (إضافة يدوية)</h3>\n<p><strong>SEO Title:</strong> ${seoTitle || title}</p>\n<p><strong>Meta Description:</strong> ${seoDescription || '—'}</p>\n<p><strong>Focus Keywords:</strong> ${seoKeywords || '—'}</p>\n<p><strong>Image ALT:</strong> ${imageAlt || '—'}</p>`;
    }, [workingBody, workingTitle, selected?.title, seoTitle, seoDescription, seoKeywords, imageAlt]);

    const wpBodyOnlyPackage = useMemo(() => {
        const title = (workingTitle || selected?.title || '').trim();
        const body = (workingBody || '').trim();
        const blocks = body
            .split(/\n{2,}/)
            .map((p) => p.trim())
            .filter(Boolean)
            .map((p) => `<p>${p}</p>`)
            .join('\n\n');
        return `<h1>${title}</h1>\n\n${blocks}`;
    }, [workingBody, workingTitle, selected?.title]);

    const seoManualPackage = useMemo(() => {
        const title = (workingTitle || selected?.title || '').trim();
        return [
            `SEO Title: ${seoTitle || title}`,
            `Meta Description: ${seoDescription || '—'}`,
            `Focus Keywords: ${seoKeywords || '—'}`,
            `Image ALT: ${imageAlt || '—'}`,
            `Image Prompt: ${imagePrompt || '—'}`,
            `Infographic Prompt: ${infographicPrompt || '—'}`,
        ].join('\n');
    }, [workingTitle, selected?.title, seoTitle, seoDescription, seoKeywords, imageAlt, imagePrompt, infographicPrompt]);

    const qualityChecks = useMemo(() => {
        const body = (workingBody || '').trim();
        const title = (workingTitle || '').trim();
        const checks = [
            { id: 'title', label: 'عنوان تحريري موجود', pass: title.length >= 12 },
            { id: 'body', label: 'متن مناسب للنشر (>= 500 حرف)', pass: body.length >= 500 },
            { id: 'seo_title', label: 'SEO Title جاهز', pass: (seoTitle || title).trim().length >= 12 },
            { id: 'meta', label: 'Meta Description جاهز', pass: (seoDescription || '').trim().length >= 80 },
            { id: 'keywords', label: 'Focus Keywords جاهزة', pass: (seoKeywords || '').trim().length >= 10 },
            { id: 'alt', label: 'ALT للصورة جاهز', pass: (imageAlt || '').trim().length >= 8 },
        ];
        return checks;
    }, [workingBody, workingTitle, seoTitle, seoDescription, seoKeywords, imageAlt]);

    const canApplyDraft = useMemo(
        () => !!selected && selected.status === 'draft' && qualityChecks.every((c) => c.pass),
        [selected, qualityChecks],
    );

    const updatePipelineStep = (step: string, status: PipelineStepState) => {
        setPipelineSteps((prev) => ({ ...prev, [step]: status }));
    };

    const runAI = async (
        action: 'rewrite' | 'summary' | 'proofread' | 'keywords' | 'metadata' | 'imagePrompt' | 'infographicPrompt',
        opts?: { silent?: boolean; stepName?: string },
    ) => {
        const text = `${workingTitle}\n\n${workingBody}`.trim() || articleData?.data?.original_content || selected?.body || '';
        if (!text) {
            setError('لا يوجد نص لمعالجته');
            return;
        }

        const stepName = opts?.stepName || action;
        updatePipelineStep(stepName, 'running');
        setBusyAction(action);
        setError(null);

        try {
            if (action === 'rewrite') {
                const res = await journalistServicesApi.tonality(text, selectedLanguage);
                const result = cleanAiText(res?.data?.result || '');
                setAiResult((prev) => ({ ...prev, rewrite: result }));
                if (result) setWorkingBody(result);
                const lines = result.split('\n').map((l) => l.trim()).filter(Boolean);
                setWriterHeadlines(lines.slice(0, 3));
            }

            if (action === 'summary') {
                const res = await journalistServicesApi.social(text, 'general', selectedLanguage);
                const result = cleanAiText(res?.data?.result || '');
                setAiResult((prev) => ({ ...prev, summary: result }));
                const snippets = result.split('\n').map((l) => l.trim()).filter(Boolean);
                setSocialSnippets(snippets.slice(0, 4));
            }

            if (action === 'proofread') {
                const res = await journalistServicesApi.proofread(text, selectedLanguage);
                const result = cleanAiText(res?.data?.result || '');
                setAiResult((prev) => ({ ...prev, proofread: result }));
                if (result) setWorkingBody(result);
            }

            if (action === 'keywords') {
                const res = await journalistServicesApi.keywords(text, selectedLanguage);
                const result = cleanAiText(res?.data?.result || '');
                setAiResult((prev) => ({ ...prev, keywords: result }));
                setSeoKeywords(result);
            }

            if (action === 'metadata') {
                const res = await journalistServicesApi.metadata(text, selectedLanguage);
                const result = cleanAiText(res?.data?.result || '');
                setAiResult((prev) => ({ ...prev, metadata: result }));
                const titleMatch = result.match(/seo[_\s-]*title\s*[:：]\s*["']?(.+?)["']?(?:,|$)/i) || result.match(/SEO\s*Title\s*[:：]\s*(.+)/i);
                const descMatch = result.match(/meta[_\s-]*description\s*[:：]\s*["']?(.+?)["']?(?:,|$)/i) || result.match(/Meta\s*Description\s*[:：]\s*(.+)/i);
                if (titleMatch?.[1]) setSeoTitle(titleMatch[1].trim());
                if (descMatch?.[1]) setSeoDescription(descMatch[1].trim());
            }

            if (action === 'imagePrompt') {
                const res = await journalistServicesApi.imagePrompt(
                    text,
                    'documentary',
                    selected?.article_id,
                    user?.full_name_ar || 'editor',
                    selectedLanguage,
                );
                const result = cleanAiText(res?.data?.result || '');
                setAiResult((prev) => ({ ...prev, imagePrompt: result }));
                setImagePrompt(result.split(/\n{2,}/)[0] || result);
                setImageAlt(
                    `صورة توضيحية لموضوع: ${(workingTitle || selected?.title || articleData?.data?.title_ar || articleData?.data?.original_title || 'المقال').slice(0, 90)}`,
                );
            }

            if (action === 'infographicPrompt') {
                const analyzed = await journalistServicesApi.infographicAnalyze(
                    text,
                    selected?.article_id,
                    user?.full_name_ar || 'editor',
                    selectedLanguage,
                );
                const res = await journalistServicesApi.infographicPrompt(
                    analyzed?.data?.data || {},
                    selected?.article_id,
                    user?.full_name_ar || 'editor',
                    selectedLanguage,
                );
                const result = cleanAiText(res?.data?.result || '');
                setAiResult((prev) => ({ ...prev, infographicPrompt: result }));
                setInfographicPrompt(result);
            }

            updatePipelineStep(stepName, 'done');
            if (!opts?.silent) setOk('تم تنفيذ أداة الذكاء الاصطناعي بنجاح');
        } catch (err: any) {
            updatePipelineStep(stepName, 'error');
            setError(err?.response?.data?.detail || 'فشل تنفيذ أداة الذكاء الاصطناعي');
        } finally {
            setBusyAction('');
        }
    };

    const runWriterPack = async () => {
        if (!selected) return;
        setError(null);
        setOk(null);
        try {
            updatePipelineStep('regenerate', 'running');
            const regen = await editorialApi.regenerateWorkspaceDraft(selected.work_id);
            const latest = await editorialApi.workspaceDraft(regen.data?.work_id || selected.work_id);
            if (latest?.data) {
                setSelected(latest.data);
                setWorkingTitle(latest.data.title || '');
                setWorkingBody(latest.data.body || '');
            }
            updatePipelineStep('regenerate', 'done');

            const text = `${latest?.data?.title || workingTitle}\n\n${latest?.data?.body || workingBody}`.trim();
            const tonalityRes = await journalistServicesApi.tonality(text, selectedLanguage);
            const tonality = cleanAiText(tonalityRes?.data?.result || '');
            const headlines = tonality.split('\n').map((l) => l.trim()).filter(Boolean).slice(0, 3);
            setWriterHeadlines(headlines);

            const invertedRes = await journalistServicesApi.inverted(text, selectedLanguage);
            const inverted = cleanAiText(invertedRes?.data?.result || '');
            setWriterLead((inverted.split('\n').map((l) => l.trim()).find(Boolean) || '').trim());

            const socialRes = await journalistServicesApi.social(text, 'general', selectedLanguage);
            const social = cleanAiText(socialRes?.data?.result || '');
            const snippets = social.split('\n').map((l) => l.trim()).filter(Boolean).slice(0, 4);
            setSocialSnippets(snippets);
            setAiResult((prev) => ({ ...prev, summary: social, rewrite: tonality }));

            setOk('تم تشغيل حزمة الكاتب: نسخة محسنة + عناوين + ليد + صيغ سوشيال');
        } catch (err: any) {
            updatePipelineStep('regenerate', 'error');
            setError(err?.response?.data?.detail || 'فشل تشغيل حزمة الكاتب');
        }
    };

    const runPublishingWorkflow = async () => {
        await runAI('proofread', { silent: true, stepName: 'proofread' });
        await runAI('metadata', { silent: true, stepName: 'metadata' });
        await runAI('keywords', { silent: true, stepName: 'keywords' });
        await runAI('imagePrompt', { silent: true, stepName: 'imagePrompt' });
        await runAI('infographicPrompt', { silent: true, stepName: 'infographicPrompt' });
        await runAI('summary', { silent: true, stepName: 'social' });
        setOk('اكتملت حزمة النشر: تدقيق + SEO + وسائط + سوشيال');
    };

    const copyText = async (key: string, text: string, message: string) => {
        await navigator.clipboard.writeText(text || '');
        setLastCopiedKey(key);
        setTimeout(() => setLastCopiedKey(''), 1600);
        setOk(message);
    };

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white">Workspace Drafts</h1>
                    <p className="text-sm text-gray-400 mt-1">أداة تحرير متكاملة من المسودة إلى نسخة النشر</p>
                </div>
            </div>

            {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2 text-sm text-red-200">{error}</div>}
            {ok && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200">{ok}</div>}

            <div className="flex flex-wrap items-center gap-3 p-3 rounded-2xl border border-white/5 bg-gray-800/30">
                <div className="relative min-w-[260px] flex-1">
                    <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                    <input
                        value={q}
                        onChange={(e) => setQ(e.target.value)}
                        placeholder="بحث بـ work_id أو article_id أو العنوان..."
                        className="w-full h-10 pr-10 pl-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                    />
                </div>
                <input
                    value={articleIdFilter}
                    onChange={(e) => setArticleIdFilter(e.target.value.replace(/[^\d]/g, ''))}
                    placeholder="فلتر Article ID"
                    className="h-10 w-[170px] px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500"
                />
                <div className="flex items-center gap-2">
                    <Filter className="w-4 h-4 text-gray-500" />
                    <select
                        value={status}
                        onChange={(e) => setStatus(e.target.value)}
                        className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-gray-200"
                    >
                        <option value="draft">draft</option>
                        <option value="applied">applied</option>
                        <option value="archived">archived</option>
                    </select>
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                <div className="xl:col-span-1 space-y-3 max-h-[80vh] overflow-auto pr-1">
                    {isLoading ? (
                        Array.from({ length: 6 }).map((_, i) => (
                            <div key={i} className="h-40 rounded-2xl bg-gray-800/30 border border-white/5 animate-pulse" />
                        ))
                    ) : finalList.length > 0 ? (
                        finalList.map((d) => (
                            <button
                                key={d.id}
                                onClick={() => setSelected(d)}
                                className={cn(
                                    'w-full text-right rounded-2xl border p-4 bg-gradient-to-br from-gray-800/40 to-gray-900/70 transition-colors',
                                    selected?.id === d.id || d.work_id === initialWorkId ? 'border-emerald-500/40' : 'border-white/10 hover:border-white/20',
                                )}
                            >
                                <div className="flex items-center justify-between gap-2 mb-2">
                                    <span className="text-xs px-2 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300">{d.work_id}</span>
                                    <span className="text-xs text-gray-400">#{d.article_id}</span>
                                </div>
                                <h3 className="text-sm font-semibold text-white line-clamp-2" dir="rtl">{d.title || 'بدون عنوان'}</h3>
                                <p className="text-xs text-gray-400 mt-2 line-clamp-3" dir="rtl">{truncate(d.body || '', 160)}</p>
                                <div className="mt-3 flex items-center justify-between text-[11px] text-gray-500">
                                    <span>{d.source_action}</span>
                                    <span>{formatRelativeTime(d.updated_at)}</span>
                                </div>
                            </button>
                        ))
                    ) : (
                        <div className="rounded-2xl border border-white/5 bg-gray-800/20 p-8 text-center text-gray-400">لا توجد مسودات</div>
                    )}
                </div>

                <div className="xl:col-span-2 space-y-4">
                    {selected ? (
                        <>
                            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-3">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="flex items-center gap-2 text-white">
                                        <FileText className="w-4 h-4 text-emerald-300" />
                                        <span className="text-sm font-semibold">{selected.work_id}</span>
                                        <span className="text-xs text-gray-400">Article #{selected.article_id}</span>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            onClick={() => saveMutation.mutate()}
                                            disabled={saveMutation.isPending}
                                            className="px-3 py-2 rounded-xl text-xs border bg-violet-500/20 border-violet-500/30 text-violet-200"
                                        >
                                            حفظ
                                        </button>
                                        <button
                                            onClick={() => createVersionMutation.mutate()}
                                            disabled={createVersionMutation.isPending}
                                            className="px-3 py-2 rounded-xl text-xs border bg-sky-500/20 border-sky-500/30 text-sky-200"
                                        >
                                            إعادة توليد (v+1)
                                        </button>
                                        <button
                                            onClick={runWriterPack}
                                            disabled={busyAction !== ''}
                                            className="px-3 py-2 rounded-xl text-xs border bg-cyan-500/20 border-cyan-500/30 text-cyan-200 inline-flex items-center gap-2"
                                        >
                                            <Bot className="w-4 h-4" />
                                            حزمة الكاتب
                                        </button>
                                        <button
                                            onClick={runPublishingWorkflow}
                                            disabled={busyAction !== ''}
                                            className="px-3 py-2 rounded-xl text-xs border bg-emerald-500/20 border-emerald-500/30 text-emerald-100 inline-flex items-center gap-2"
                                        >
                                            <PlayCircle className="w-4 h-4" />
                                            حزمة النشر
                                        </button>
                                        <button
                                            onClick={() => applyMutation.mutate(selected.work_id)}
                                            disabled={applyMutation.isPending || !canApplyDraft}
                                            className={cn(
                                                'px-3 py-2 rounded-xl text-xs border flex items-center gap-2',
                                                canApplyDraft
                                                    ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-200'
                                                    : 'bg-white/5 border-white/10 text-gray-500 cursor-not-allowed',
                                            )}
                                        >
                                            <CheckCircle2 className="w-4 h-4" />
                                            تطبيق على الخبر
                                        </button>
                                        <button
                                            onClick={() => archiveMutation.mutate(selected.work_id)}
                                            disabled={archiveMutation.isPending || selected.status === 'archived'}
                                            className={cn(
                                                'px-3 py-2 rounded-xl text-xs border',
                                                selected.status !== 'archived'
                                                    ? 'bg-amber-500/20 border-amber-500/30 text-amber-200'
                                                    : 'bg-white/5 border-white/10 text-gray-500 cursor-not-allowed',
                                            )}
                                        >
                                            أرشفة
                                        </button>
                                    </div>
                                </div>

                                <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                    <div className="flex items-center justify-between mb-2">
                                        <h4 className="text-xs text-gray-300">بوابة الجودة قبل التطبيق</h4>
                                        {!canApplyDraft && (
                                            <span className="text-[11px] text-amber-300 inline-flex items-center gap-1">
                                                <AlertTriangle className="w-3 h-3" />
                                                أكمل المتطلبات أولاً
                                            </span>
                                        )}
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                        {qualityChecks.map((check) => (
                                            <div
                                                key={check.id}
                                                className={cn(
                                                    'px-2 py-1.5 rounded-lg text-xs border',
                                                    check.pass
                                                        ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-200'
                                                        : 'bg-amber-500/10 border-amber-500/30 text-amber-200',
                                                )}
                                            >
                                                {check.label}
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                    <h4 className="text-xs text-gray-300 mb-2">مراحل الكاتب</h4>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                                        {Object.entries(pipelineSteps).map(([step, state]) => (
                                            <div key={step} className="px-2 py-1.5 rounded-lg text-[11px] border border-white/10 bg-white/5 text-gray-200">
                                                <div className="font-medium">{step}</div>
                                                <div className={cn(
                                                    'mt-1',
                                                    state === 'done' && 'text-emerald-300',
                                                    state === 'running' && 'text-sky-300',
                                                    state === 'error' && 'text-red-300',
                                                    state === 'idle' && 'text-gray-500',
                                                )}>
                                                    {state}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <input
                                        value={workingTitle}
                                        onChange={(e) => setWorkingTitle(e.target.value)}
                                        className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white"
                                        placeholder="عنوان المقال"
                                        dir="rtl"
                                    />
                                    <input
                                        value={seoTitle}
                                        onChange={(e) => setSeoTitle(e.target.value)}
                                        className="h-10 px-3 rounded-xl bg-white/5 border border-white/10 text-sm text-white"
                                        placeholder="SEO Title"
                                        dir="rtl"
                                    />
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="text-xs text-gray-400">لغة التحرير:</span>
                                    <select
                                        value={selectedLanguage}
                                        onChange={(e) => setSelectedLanguage(e.target.value as 'ar' | 'fr' | 'en')}
                                        className="h-9 px-3 rounded-xl bg-white/5 border border-white/10 text-xs text-gray-200"
                                    >
                                        <option value="ar">العربية</option>
                                        <option value="fr">Français</option>
                                        <option value="en">English</option>
                                    </select>
                                </div>

                                <textarea
                                    value={workingBody}
                                    onChange={(e) => setWorkingBody(e.target.value)}
                                    className="w-full min-h-[260px] p-3 rounded-xl bg-black/30 border border-white/10 text-sm text-gray-100"
                                    dir="rtl"
                                />

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <textarea
                                        value={seoDescription}
                                        onChange={(e) => setSeoDescription(e.target.value)}
                                        className="min-h-[90px] p-3 rounded-xl bg-white/5 border border-white/10 text-xs text-white"
                                        placeholder="Meta Description"
                                        dir="rtl"
                                    />
                                    <textarea
                                        value={seoKeywords}
                                        onChange={(e) => setSeoKeywords(e.target.value)}
                                        className="min-h-[90px] p-3 rounded-xl bg-white/5 border border-white/10 text-xs text-white"
                                        placeholder="Focus Keywords (comma separated)"
                                        dir="rtl"
                                    />
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <button onClick={() => copyText('seo_title', seoTitle, 'تم نسخ SEO Title')} className="px-2 py-1 rounded-lg text-xs bg-white/10 text-gray-200">{lastCopiedKey === 'seo_title' ? 'تم النسخ' : 'نسخ SEO Title'}</button>
                                    <button onClick={() => copyText('seo_desc', seoDescription, 'تم نسخ Meta Description')} className="px-2 py-1 rounded-lg text-xs bg-white/10 text-gray-200">{lastCopiedKey === 'seo_desc' ? 'تم النسخ' : 'نسخ Meta'}</button>
                                    <button onClick={() => copyText('seo_kw', seoKeywords, 'تم نسخ الكلمات المفتاحية')} className="px-2 py-1 rounded-lg text-xs bg-white/10 text-gray-200">{lastCopiedKey === 'seo_kw' ? 'تم النسخ' : 'نسخ Keywords'}</button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <textarea
                                        value={imageAlt}
                                        onChange={(e) => setImageAlt(e.target.value)}
                                        className="min-h-[80px] p-3 rounded-xl bg-white/5 border border-white/10 text-xs text-white"
                                        placeholder="وصف الصورة / ALT text"
                                        dir="rtl"
                                    />
                                    <textarea
                                        value={imagePrompt}
                                        onChange={(e) => setImagePrompt(e.target.value)}
                                        className="min-h-[80px] p-3 rounded-xl bg-white/5 border border-white/10 text-xs text-white"
                                        placeholder="Prompt توليد صورة"
                                        dir="rtl"
                                    />
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <button onClick={() => copyText('image_alt', imageAlt, 'تم نسخ وصف الصورة')} className="px-2 py-1 rounded-lg text-xs bg-white/10 text-gray-200">{lastCopiedKey === 'image_alt' ? 'تم النسخ' : 'نسخ ALT'}</button>
                                    <button onClick={() => copyText('image_prompt', imagePrompt, 'تم نسخ برومبت الصورة')} className="px-2 py-1 rounded-lg text-xs bg-white/10 text-gray-200">{lastCopiedKey === 'image_prompt' ? 'تم النسخ' : 'نسخ Prompt صورة'}</button>
                                </div>

                                <textarea
                                    value={infographicPrompt}
                                    onChange={(e) => setInfographicPrompt(e.target.value)}
                                    className="w-full min-h-[90px] p-3 rounded-xl bg-white/5 border border-white/10 text-xs text-white"
                                    placeholder="Prompt إنفوغراف"
                                    dir="rtl"
                                />
                                <button onClick={() => copyText('infographic_prompt', infographicPrompt, 'تم نسخ برومبت الإنفوغراف')} className="px-2 py-1 rounded-lg text-xs bg-white/10 text-gray-200">{lastCopiedKey === 'infographic_prompt' ? 'تم النسخ' : 'نسخ Prompt إنفوغراف'}</button>
                            </div>

                            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4 space-y-3">
                                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                                    <Sparkles className="w-4 h-4 text-emerald-300" />
                                    أدوات الذكاء الاصطناعي للمحرر
                                </h3>
                                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 flex flex-wrap items-center justify-between gap-2">
                                    <div className="text-xs text-emerald-100">تشغيل الحزمة الذكية: تدقيق + SEO + كلمات مفتاحية + Prompt صورة</div>
                                    <button
                                        onClick={runPublishingWorkflow}
                                        disabled={busyAction !== ''}
                                        className="px-3 py-2 rounded-xl text-xs border bg-emerald-500/20 border-emerald-500/40 text-emerald-100 inline-flex items-center gap-2"
                                    >
                                        {busyAction ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                                        تجهيز نسخة للنشر
                                    </button>
                                </div>
                                <div className="flex flex-wrap gap-2">
                                    <button onClick={() => runAI('rewrite')} disabled={busyAction !== ''} className="px-3 py-2 rounded-xl text-xs bg-emerald-500/20 border border-emerald-500/30 text-emerald-200">إعادة صياغة صحفية</button>
                                    <button onClick={() => runAI('proofread')} disabled={busyAction !== ''} className="px-3 py-2 rounded-xl text-xs bg-sky-500/20 border border-sky-500/30 text-sky-200">تدقيق لغوي</button>
                                    <button onClick={() => runAI('summary')} disabled={busyAction !== ''} className="px-3 py-2 rounded-xl text-xs bg-violet-500/20 border border-violet-500/30 text-violet-200">ملخص شبكات</button>
                                    <button onClick={() => runAI('keywords')} disabled={busyAction !== ''} className="px-3 py-2 rounded-xl text-xs bg-amber-500/20 border border-amber-500/30 text-amber-200">كلمات SEO</button>
                                    <button onClick={() => runAI('metadata')} disabled={busyAction !== ''} className="px-3 py-2 rounded-xl text-xs bg-fuchsia-500/20 border border-fuchsia-500/30 text-fuchsia-200">Meta SEO</button>
                                    <button onClick={() => runAI('imagePrompt')} disabled={busyAction !== ''} className="px-3 py-2 rounded-xl text-xs bg-cyan-500/20 border border-cyan-500/30 text-cyan-200">اقتراح صورة</button>
                                    <button onClick={() => runAI('infographicPrompt')} disabled={busyAction !== ''} className="px-3 py-2 rounded-xl text-xs bg-rose-500/20 border border-rose-500/30 text-rose-200">اقتراح إنفوغراف</button>
                                </div>
                                {busyAction && <p className="text-xs text-gray-400">جاري التنفيذ: {busyAction}</p>}

                                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="text-xs text-gray-300">بدائل عنوان الكاتب</h4>
                                            <button
                                                onClick={() => copyText('writer_headlines', writerHeadlines.join('\n'), 'تم نسخ بدائل العنوان')}
                                                className="px-2 py-1 rounded-lg text-[10px] bg-white/10 text-gray-200"
                                            >
                                                {lastCopiedKey === 'writer_headlines' ? 'تم النسخ' : 'نسخ'}
                                            </button>
                                        </div>
                                        <ul className="text-xs text-gray-100 space-y-1" dir="rtl">
                                            {(writerHeadlines.length ? writerHeadlines : ['شغّل حزمة الكاتب لتوليد 3 بدائل']).map((h, idx) => (
                                                <li key={`${h}-${idx}`} className="rounded-lg bg-white/5 px-2 py-1">{h}</li>
                                            ))}
                                        </ul>
                                    </div>

                                    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="text-xs text-gray-300">Lead مقترح</h4>
                                            <button
                                                onClick={() => copyText('writer_lead', writerLead, 'تم نسخ الـ Lead')}
                                                className="px-2 py-1 rounded-lg text-[10px] bg-white/10 text-gray-200"
                                            >
                                                {lastCopiedKey === 'writer_lead' ? 'تم النسخ' : 'نسخ'}
                                            </button>
                                        </div>
                                        <p className="text-xs text-gray-100" dir="rtl">
                                            {writerLead || 'شغّل حزمة الكاتب لتوليد Lead افتتاحي.'}
                                        </p>
                                    </div>

                                    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="text-xs text-gray-300">ملخصات سوشيال</h4>
                                            <button
                                                onClick={() => copyText('writer_social', socialSnippets.join('\n'), 'تم نسخ صيغ السوشيال')}
                                                className="px-2 py-1 rounded-lg text-[10px] bg-white/10 text-gray-200"
                                            >
                                                {lastCopiedKey === 'writer_social' ? 'تم النسخ' : 'نسخ'}
                                            </button>
                                        </div>
                                        <ul className="text-xs text-gray-100 space-y-1" dir="rtl">
                                            {(socialSnippets.length ? socialSnippets : ['شغّل حزمة الكاتب لتوليد صيغ سوشيال.']).map((s, idx) => (
                                                <li key={`${s}-${idx}`} className="rounded-lg bg-white/5 px-2 py-1">{s}</li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                    <div className="rounded-xl border border-white/10 bg-black/20 p-3">
                                        <div className="flex items-center justify-between mb-2">
                                            <h4 className="text-xs text-gray-400">آخر مخرجات AI</h4>
                                            <button
                                                onClick={() => copyText('ai_result', JSON.stringify(aiResult, null, 2), 'تم نسخ مخرجات AI')}
                                                className="px-2 py-1 rounded-lg text-[10px] bg-white/10 text-gray-200"
                                            >
                                                {lastCopiedKey === 'ai_result' ? 'تم النسخ' : 'نسخ'}
                                            </button>
                                        </div>
                                        <pre className="whitespace-pre-wrap text-xs text-gray-200 max-h-56 overflow-auto" dir="rtl">
                                            {JSON.stringify(aiResult, null, 2)}
                                        </pre>
                                    </div>
                                    <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
                                        <h4 className="text-xs text-gray-400">نسخة WordPress جاهزة للنسخ (متوافقة مع Gutenberg)</h4>
                                        <div className="flex flex-wrap gap-2">
                                            <button
                                                onClick={() => copyText('wp_full', wpPackage, 'تم نسخ النسخة الكاملة للووردبريس')}
                                                className="px-3 py-2 rounded-xl text-xs bg-emerald-500/20 border border-emerald-500/30 text-emerald-200 inline-flex items-center gap-2"
                                            >
                                                <Copy className="w-4 h-4" />
                                                {lastCopiedKey === 'wp_full' ? 'تم النسخ' : 'نسخ النسخة الكاملة'}
                                            </button>
                                            <button
                                                onClick={() => copyText('wp_body', wpBodyOnlyPackage, 'تم نسخ متن المقال فقط')}
                                                className="px-3 py-2 rounded-xl text-xs bg-sky-500/20 border border-sky-500/30 text-sky-200"
                                            >
                                                {lastCopiedKey === 'wp_body' ? 'تم النسخ' : 'نسخ المقال فقط'}
                                            </button>
                                            <button
                                                onClick={() => copyText('wp_seo', seoManualPackage, 'تم نسخ باقة SEO والوسائط')}
                                                className="px-3 py-2 rounded-xl text-xs bg-amber-500/20 border border-amber-500/30 text-amber-200"
                                            >
                                                {lastCopiedKey === 'wp_seo' ? 'تم النسخ' : 'نسخ SEO + وسائط'}
                                            </button>
                                        </div>
                                        <pre className="whitespace-pre-wrap text-xs text-gray-200 max-h-56 overflow-auto" dir="rtl">{wpPackage}</pre>
                                    </div>
                                </div>
                            </div>

                            <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-4">
                                <h3 className="text-sm text-gray-200 mb-2 flex items-center gap-2">
                                    <Wand2 className="w-4 h-4 text-emerald-300" />
                                    مرجع الخبر الأصلي
                                </h3>
                                <p className="text-xs text-gray-400">المصدر: {articleData?.data?.source_name || '—'}</p>
                                <p className="text-xs text-gray-400">الرابط: {articleData?.data?.original_url || '—'}</p>
                                <p className="text-sm text-gray-200 mt-2" dir="rtl">{articleData?.data?.summary || articleData?.data?.original_title || '—'}</p>
                            </div>
                        </>
                    ) : (
                        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 text-center text-gray-400">اختر مسودة من القائمة</div>
                    )}
                </div>
            </div>
        </div>
    );
}
