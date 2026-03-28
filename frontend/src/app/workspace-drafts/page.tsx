'use client';
/* eslint-disable @typescript-eslint/no-explicit-any, react-hooks/exhaustive-deps, react-hooks/refs */

import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import NextLink from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'next/navigation';
import { EditorContent, useEditor } from '@tiptap/react';
import { BubbleMenu } from '@tiptap/react/menus';
import StarterKit from '@tiptap/starter-kit';
import { Extension } from '@tiptap/core';
import Link from '@tiptap/extension-link';
import Placeholder from '@tiptap/extension-placeholder';
import Highlight from '@tiptap/extension-highlight';
import { Plugin } from 'prosemirror-state';
import { Decoration, DecorationSet } from 'prosemirror-view';
import {
    AlertTriangle,
    CheckCircle2,
    Clock3,
    Loader2,
    Save,
    SearchCheck,
    ShieldCheck,
    Sparkles,
} from 'lucide-react';

import {
    archiveApi,
    competitorXrayApi,
    editorialApi,
    jobsApi,
    memoryApi,
    msiApi,
    simApi,
    storiesApi,
    sourcesApi,
    type ClaimOverrideInput,
    type ArchiveSearchItem,
    type FactCheckClaim,
    type Source,
    type StoryControlCenterResponse,
    type StorySuggestion,
    type WorkspaceOrchestratorTaskKey,
    type WorkspacePromptSuggestion,
    type WorkspacePublishReadiness,
} from '@/lib/api';
import { constitutionApi } from '@/lib/constitution-api';
import { useAuth } from '@/lib/auth';
import { cn, formatRelativeTime, truncate } from '@/lib/utils';
import { MemoryQuickCaptureModal } from '@/components/memory/MemoryQuickCaptureModal';
import { WorkspaceEmpty as Empty, WorkspaceInfoBlock as InfoBlock, WorkspacePanel as Panel } from '@/components/workspace-drafts/WorkspacePrimitives';
import { trackNextAction, trackUiAction, useTrackSurfaceView } from '@/lib/ux-telemetry';
import { TutorialOverlay } from '@/components/onboarding/TutorialOverlay';
import { useTutorialState } from '@/lib/tutorial';

type SaveState = 'saved' | 'saving' | 'unsaved' | 'error';
type RightTab = 'evidence' | 'proofread' | 'quality' | 'seo' | 'social' | 'context' | 'msi' | 'simulator' | 'xray';
type ActionId = 'quick_check' | 'verify' | 'proofread' | 'improve' | 'headlines' | 'seo' | 'links' | 'social' | 'quality' | 'publish_gate' | 'apply' | 'save' | 'manual_draft' | 'audience_test';
type ViewMode = 'write';
type EditorStage = 'writing' | 'review';
type LeftTab = 'drafts' | 'source' | 'archive';
type ClaimOverrideDraft = {
    evidenceLinksRaw: string;
    unverifiable: boolean;
    unverifiableReason: string;
};
type DecisionSeverity = 'critical' | 'high' | 'medium' | 'low';
type DecisionActionId = 'verify' | 'quality' | 'proofread' | 'seo' | 'headlines' | 'links' | 'social' | 'publish_gate' | 'quick_check';
type DecisionItem = {
    id: string;
    title: string;
    reason: string;
    impact: string;
    rule: string;
    severity: DecisionSeverity;
    confidence?: number;
    action?: DecisionActionId;
};
type ReviewCard = {
    id: string;
    title: string;
    value: string;
    hint: string;
    severity: DecisionSeverity;
    action?: DecisionActionId;
};
type BlockerExplanation = {
    title: string;
    detail: string;
    action?: DecisionActionId;
    stage?: string;
    raw?: string;
};
type StoryGap = {
    id: string;
    title: string;
    hint: string;
    severity: DecisionSeverity;
    action?: DecisionActionId;
};
type StoryCenterTimelineItem = StoryControlCenterResponse['timeline'][number];
type StoryContextItem = {
    id?: number;
    title?: string;
    summary?: string | null;
    url?: string | null;
    source_name?: string | null;
    created_at?: string | null;
    published_at?: string | null;
    category?: string | null;
    status?: string | null;
};
type StoryDraftMode = 'followup' | 'analysis' | 'background';

const TABS: Array<{ id: RightTab; label: string }> = [
    { id: 'evidence', label: 'التحقق والأدلة' },
    { id: 'proofread', label: 'تدقيق لغوي' },
    { id: 'quality', label: 'تقييم الجودة' },
    { id: 'seo', label: 'أدوات SEO' },
    { id: 'social', label: 'نسخ السوشيال' },
    { id: 'context', label: 'السياق والنسخ' },
    { id: 'msi', label: 'MSI السياقي' },
    { id: 'simulator', label: 'محاكي الجمهور' },
    { id: 'xray', label: 'زوايا المنافسين' },
];


const ACTION_SOURCE_LABELS: Record<DecisionActionId, string> = {
    verify: 'تحقق الادعاءات',
    quality: 'تقييم الجودة',
    proofread: 'تدقيق لغوي',
    seo: 'SEO',
    headlines: 'عناوين',
    links: 'روابط',
    social: 'سوشيال',
    publish_gate: 'بوابة النشر',
    quick_check: 'فحص سريع',
};

const STAGE_LABELS: Record<string, string> = {
    FACT_CHECK: 'التحقق من الادعاءات',
    SEO_TECH: 'التدقيق التقني',
    READABILITY: 'قابلية القراءة',
    QUALITY_SCORE: 'جودة التحرير',
};

const STAGE_ACTIONS: Record<string, DecisionActionId | null> = {
    FACT_CHECK: 'verify',
    SEO_TECH: 'seo',
    READABILITY: 'quality',
    QUALITY_SCORE: 'quality',
};

const STORY_TEMPLATE_SECTIONS = [
    { title: 'المقدمة', hint: 'ملخص سريع يجيب عن ماذا/من/أين/متى.' },
    { title: 'الخلفية', hint: 'سياق مختصر يشرح لماذا يهم الخبر.' },
    { title: 'التفاصيل', hint: 'أبرز الوقائع والأرقام والتصريحات.' },
    { title: 'ردود الفعل', hint: 'مواقف الجهات المعنية أو الجمهور.' },
    { title: 'ما التالي؟', hint: 'الخطوات القادمة أو التطورات المنتظرة.' },
];

function explainBlockerReason(reason: string): BlockerExplanation {
    const msg = cleanText(reason || '');
    if (!msg) {
        return {
            title: 'مانع نشر غير محدد',
            detail: 'لا يوجد وصف واضح للمانع. شغّل بوابة النشر لإعادة التحقق.',
            action: 'publish_gate',
            raw: reason,
        };
    }

    const stageMatch = msg.match(/(?:تقرير مفقود:|stage|مرحلة)\s*([A-Z_]+)/i);
    const stage = stageMatch?.[1]?.toUpperCase();
    if (stage && STAGE_LABELS[stage]) {
        return {
            title: `تقرير مفقود: ${STAGE_LABELS[stage]}`,
            detail: `شغّل ${STAGE_LABELS[stage]} لإزالة هذا المانع.`,
            action: STAGE_ACTIONS[stage] || 'publish_gate',
            stage,
            raw: msg,
        };
    }

    if (/claim|ادعاء|ادعاءات|مصدر|إسناد/i.test(msg)) {
        return {
            title: 'ادعاءات بلا مصادر كافية',
            detail: msg,
            action: 'verify',
            raw: msg,
        };
    }
    if (/seo/i.test(msg)) {
        return {
            title: 'مانع SEO',
            detail: msg,
            action: 'seo',
            raw: msg,
        };
    }
    if (/readability|قابلية|قراءة/i.test(msg)) {
        return {
            title: 'مانع قابلية القراءة',
            detail: msg,
            action: 'quality',
            raw: msg,
        };
    }
    if (/quality|جودة/i.test(msg)) {
        return {
            title: 'مانع جودة التحرير',
            detail: msg,
            action: 'quality',
            raw: msg,
        };
    }
    if (/policy|دستور|سياسة/i.test(msg)) {
        return {
            title: 'مانع سياسة تحريرية',
            detail: msg,
            action: 'publish_gate',
            raw: msg,
        };
    }

    return {
        title: 'ملاحظة جودة',
        detail: msg,
        action: 'publish_gate',
        raw: msg,
    };
}

function buildBlockerExplanations(params: {
    readiness?: any;
    quality?: any;
    proofread?: any;
    claims?: any[];
    seoPack?: any;
}): BlockerExplanation[] {
    const { readiness, quality, proofread, claims, seoPack } = params;
    const blockingClaims = (claims || []).filter((claim: any) => claim?.blocking);

    if (readiness?.ready_for_publish && blockingClaims.length === 0) {
        return [];
    }

    if (!readiness) {
        return [{
            title: 'بوابة النشر غير مشغّلة',
            detail: 'شغّل بوابة النشر لإظهار الموانع الفعلية.',
            action: 'publish_gate',
            raw: 'readiness_missing',
        }];
    }

    const list: BlockerExplanation[] = [];
    const pushUnique = (item: BlockerExplanation | null | undefined) => {
        if (!item) return;
        const key = `${item.title}|${item.detail}`;
        if (list.some((x) => `${x.title}|${x.detail}` === key)) return;
        list.push(item);
    };

    const reasons: string[] = [];
    (readiness.blocking_reasons || []).forEach((reason: string) => {
        if (reason) reasons.push(String(reason));
    });
    const gateItems = (readiness.gates?.items || []).filter((item: any) => item?.severity === 'blocker');
    gateItems.forEach((item: any) => {
        if (item?.message) reasons.push(String(item.message));
        else if (item?.rule) reasons.push(String(item.rule));
    });

    const cleaned = reasons.map((r) => cleanText(r)).filter(Boolean);
    const genericPattern = /(غير جاهز|غير جاهزة|مانع نشر|blocked|not ready)/i;
    const specific = cleaned.filter((r) => !genericPattern.test(r));

    if (specific.length) {
        specific.forEach((reason) => pushUnique(explainBlockerReason(reason)));
    }

    if (blockingClaims.length) {
        pushUnique({
            title: `ادعاءات تحتاج إسناداً (${blockingClaims.length})`,
            detail: cleanText(blockingClaims[0]?.text || 'يوجد ادعاءات دون مصادر كافية.'),
            action: 'verify',
            raw: 'claims_blocking',
        });
    }

    if (!specific.length) {
        if (!quality) {
            pushUnique({
                title: 'تقرير الجودة غير متاح',
                detail: 'شغّل تقييم الجودة لاستكمال جاهزية النشر.',
                action: 'quality',
                raw: 'quality_missing',
            });
        }
        if (!proofread) {
            pushUnique({
                title: 'تدقيق لغوي غير منفّذ',
                detail: 'شغّل التدقيق اللغوي لاكتشاف الأخطاء قبل الاعتماد.',
                action: 'proofread',
                raw: 'proofread_missing',
            });
        }
        if (!claims || claims.length === 0) {
            pushUnique({
                title: 'التحقق من الادعاءات غير منفّذ',
                detail: 'شغّل التحقق قبل إرسال الخبر للاعتماد.',
                action: 'verify',
                raw: 'verify_missing',
            });
        }
        if (!seoPack) {
            pushUnique({
                title: 'تقرير SEO غير متاح',
                detail: 'شغّل أدوات SEO لضبط العنوان والوصف والكلمات المفتاحية.',
                action: 'seo',
                raw: 'seo_missing',
            });
        }
    }

    if (list.length === 0) {
        if (cleaned.length) {
            pushUnique(explainBlockerReason(cleaned[0]));
        } else {
            pushUnique({
                title: 'موانع غير موصوفة',
                detail: 'أعد تشغيل بوابة النشر لتوليد سبب واضح.',
                action: 'publish_gate',
                raw: 'unknown',
            });
        }
    }

    return list;
}

const METRIC_LABELS: Record<string, string> = {
    clarity: 'الوضوح',
    structure: 'البنية',
    inverted_pyramid: 'الهرم المقلوب',
    redundancy: 'عدم التكرار',
    length_suitability: 'ملاءمة الطول',
    tone_neutrality: 'الحياد',
    sources_attribution: 'الإسناد للمصادر',
    word_count: 'عدد الكلمات',
};

function parseEvidenceLinks(raw: string): string[] {
    const unique = new Set<string>();
    for (const chunk of (raw || '').split(/\r?\n|,/)) {
        const value = (chunk || '').trim();
        if (!value) continue;
        if (!/^https?:\/\//i.test(value) && !/^(docintel:|document-intel:|doc:|di:\/\/)/i.test(value)) continue;
        unique.add(value);
    }
    return Array.from(unique).slice(0, 12);
}

function claimDraftFromClaim(claim: FactCheckClaim): ClaimOverrideDraft {
    return {
        evidenceLinksRaw: (claim?.evidence_links || []).join('\n'),
        unverifiable: Boolean(claim?.unverifiable),
        unverifiableReason: String(claim?.unverifiable_reason || ''),
    };
}

function mergeClaimOverrideDrafts(
    claims: FactCheckClaim[],
    previous: Record<string, ClaimOverrideDraft>,
): Record<string, ClaimOverrideDraft> {
    const next: Record<string, ClaimOverrideDraft> = {};
    for (const claim of claims || []) {
        const claimId = String(claim?.id || '').trim();
        if (!claimId) continue;
        next[claimId] = previous[claimId] || claimDraftFromClaim(claim);
    }
    return next;
}

function cleanText(value: string): string {
    if (!value) return '';
    return value
        .replace(/```[\s\S]*?```/g, '')
        .replace(/^\s*(حسنًا|حسنا|ملاحظات|ملاحظة|يمكنني|آمل|إذا كان لديك)\b.*$/gim, '')
        .replace(/^\s*(note|notes|explanation|comment)\s*:\s*.*$/gim, '')
        .replace(/\[[^\]\n]{2,120}\]/g, '')
        .replace(/\?{3,}/g, '')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
}

function safeInlineText(value: string): string {
    return cleanText(value || '')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function htmlToReadableText(value: string): string {
    if (!value) return '';
    if (typeof window !== 'undefined') {
        const parsed = new window.DOMParser().parseFromString(value, 'text/html');
        return cleanText(parsed.body.textContent || '');
    }
    return cleanText(value.replace(/<[^>]+>/g, ' '));
}

function normalizeDiffOutput(value: string): string {
    if (!value) return '';
    const hasHtml = /<[^>]+>/.test(value);
    return hasHtml ? htmlToReadableText(value) : cleanText(value);
}

function normalizeForMatch(value: string): string {
    return cleanText(value || '')
        .replace(/[^\u0600-\u06FFa-zA-Z0-9\s]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .toLowerCase();
}

function storyItemTimestamp(item: StoryContextItem): number {
    const value = item?.published_at || item?.created_at;
    if (!value) return 0;
    const parsed = new Date(value);
    const ts = parsed.getTime();
    return Number.isNaN(ts) ? 0 : ts;
}

function storyItemDateLabel(item: StoryContextItem): string {
    const value = item?.published_at || item?.created_at;
    if (!value) return '';
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return '';
    return parsed.toLocaleDateString('ar-DZ');
}

function entityMatchesContext(entity: string, contextText: string): boolean {
    const entityNorm = normalizeForMatch(entity);
    const contextNorm = normalizeForMatch(contextText);
    if (!entityNorm || !contextNorm) return false;
    const tokens = entityNorm.split(' ').filter((t) => t.length >= 3);
    if (!tokens.length) return false;
    return tokens.every((t) => contextNorm.includes(t));
}

function severityRank(sev: DecisionSeverity): number {
    return { critical: 4, high: 3, medium: 2, low: 1 }[sev] || 0;
}

function severityStyles(sev: DecisionSeverity): { badge: string; border: string } {
    switch (sev) {
        case 'critical':
            return { badge: 'bg-rose-500/20 text-rose-100', border: 'border-rose-500/30 bg-rose-500/10' };
        case 'high':
            return { badge: 'bg-amber-500/20 text-amber-100', border: 'border-amber-500/30 bg-amber-500/10' };
        case 'medium':
            return { badge: 'bg-cyan-500/20 text-cyan-100', border: 'border-cyan-500/30 bg-cyan-500/10' };
        default:
            return { badge: 'bg-white/10 text-gray-200', border: 'border-white/10 bg-white/5' };
    }
}

function severityLabel(sev: DecisionSeverity): string {
    return sev === 'critical' ? 'حرج' : sev === 'high' ? 'عاجل' : sev === 'medium' ? 'متوسط' : 'خفيف';
}

function externalVerdictLabel(value?: string): string {
    const verdict = String(value || '').toLowerCase();
    if (verdict === 'true') return 'صحيح';
    if (verdict === 'false') return 'غير صحيح';
    if (verdict === 'mixed') return 'مختلط';
    return 'غير واضح';
}

function mapStoryGapSeverity(severity?: string | null): DecisionSeverity {
    const value = String(severity || '').toLowerCase();
    if (value === 'high' || value === 'critical') return 'high';
    if (value === 'medium' || value === 'warn') return 'medium';
    return 'low';
}

function mapGapToStoryTask(title: string, hint: string, id?: string): StoryDraftMode | 'source' {
    const text = `${id || ''} ${title || ''} ${hint || ''}`.toLowerCase();
    if (/source|مصدر|إسناد|quote|تصريح/.test(text)) return 'source';
    if (/analysis|تحليل/.test(text)) return 'analysis';
    if (/background|خلفي|timeline|سياق/.test(text)) return 'background';
    return 'followup';
}

function storyTaskLabel(task: StoryDraftMode | 'source'): string {
    if (task === 'source') return 'فتح المصدر';
    if (task === 'analysis') return 'إنشاء تحليل';
    if (task === 'background') return 'إنشاء خلفية';
    return 'إنشاء متابعة';
}

function impactBySeverity(sev: DecisionSeverity): string {
    switch (sev) {
        case 'critical':
            return 'قد يمنع النشر أو يسبب ضرراً تحريرياً مباشراً.';
        case 'high':
            return 'يؤثر على المصداقية أو وضوح الخبر بشكل ملحوظ.';
        case 'medium':
            return 'يحسن الجودة ويقلل الالتباس دون تغيير المعنى.';
        default:
            return 'تحسين إضافي يمكن تأجيله.';
    }
}

function createSmartHighlightExtension(isEnabled: () => boolean) {
    return Extension.create({
        name: 'smartHighlight',
        addProseMirrorPlugins() {
            const numberRegex = /(?:\d+[.,]?\d*|[٠-٩]+(?:[٫٬.]\d+)?)/g;
            const quoteRegex = /“[^”]{3,}”|\"[^\"]{3,}\"|«[^»]{3,}»/g;
            const claimVerbRegex = /(قال|أعلن|أكد|صرّح|صرح|أوضح|ذكر|أفاد|كشف|بيّن|أضاف|أردف)/g;

            return [
                new Plugin({
                    props: {
                        decorations(state) {
                            if (!isEnabled()) return DecorationSet.empty;
                            const decorations: Decoration[] = [];
                            state.doc.descendants((node, pos) => {
                                if (!node.isText) return;
                                const text = node.text || '';
                                if (!text.trim()) return;

                                let match: RegExpExecArray | null;
                                numberRegex.lastIndex = 0;
                                while ((match = numberRegex.exec(text))) {
                                    const from = pos + match.index;
                                    const to = from + match[0].length;
                                    decorations.push(
                                        Decoration.inline(from, to, {
                                            style: 'background-color: rgba(56, 189, 248, 0.18); border-radius: 4px; padding: 0 2px;',
                                        }),
                                    );
                                }

                                quoteRegex.lastIndex = 0;
                                while ((match = quoteRegex.exec(text))) {
                                    const from = pos + match.index;
                                    const to = from + match[0].length;
                                    decorations.push(
                                        Decoration.inline(from, to, {
                                            style: 'background-color: rgba(167, 139, 250, 0.18); border-radius: 4px; padding: 0 2px;',
                                        }),
                                    );
                                }

                                claimVerbRegex.lastIndex = 0;
                                while ((match = claimVerbRegex.exec(text))) {
                                    const from = pos + match.index;
                                    const to = from + match[0].length;
                                    decorations.push(
                                        Decoration.inline(from, to, {
                                            style: 'background-color: rgba(251, 191, 36, 0.2); border-radius: 4px; padding: 0 2px;',
                                        }),
                                    );
                                }
                            });
                            return DecorationSet.create(state.doc, decorations);
                        },
                    },
                }),
            ];
        },
    });
}

function evaluateHeadline(headline: string, isBreaking: boolean): { score: number; risks: string[]; reasons: string[] } {
    const cleaned = cleanText(headline);
    const words = cleaned.split(/\s+/).filter(Boolean);
    let score = 60;
    const risks: string[] = [];
    const reasons: string[] = [];

    if (words.length >= 8 && words.length <= 14) {
        score += 15;
        reasons.push('طول مناسب لعنوان خبري واضح.');
    } else {
        score -= 10;
        risks.push('طول غير مناسب (قصير جداً أو طويل جداً).');
    }

    if (/(هذا|هذه|هؤلاء|ذلك|تلك)/.test(cleaned)) {
        score -= 15;
        risks.push('عنوان مبهم يعتمد على ضمير إشارة.');
    }

    if (/عاجل/.test(cleaned) && !isBreaking) {
        score -= 15;
        risks.push('ذكر “عاجل” دون سياق عاجل واضح.');
    }

    if (/[0-9]/.test(cleaned)) {
        score += 5;
        reasons.push('وجود رقم أو تاريخ يزيد الإفصاح.');
    }

    const verbHit = /(أعلن|أكد|قرر|دعا|كشف|نفى|أوضح|قال|صرّح|افتتح|أطلق)/.test(cleaned);
    if (verbHit) {
        score += 8;
        reasons.push('صيغة فعل واضحة تدل على الحدث.');
    } else {
        risks.push('قد يفتقد إلى فعل خبري واضح.');
    }

    score = Math.max(0, Math.min(100, score));
    return { score, risks, reasons };
}

function classifyClaimSource(text: string): { label: string; reason: string; severity: DecisionSeverity } {
    const clean = cleanText(text || '');
    const hasNumber = /\d/.test(clean);
    const hasDate = /\b(20\d{2}|19\d{2})\b/.test(clean);
    const hasQuote = /["«»]/.test(clean);
    const hasAttribution = /(بحسب|وفق|أفاد|أعلن|صرّح|أكد|ذكر)/.test(clean);

    if (hasNumber || hasDate || hasQuote) {
        return {
            label: 'يحتاج مصدراً أولياً',
            reason: 'يتضمن رقماً/تاريخاً/اقتباساً يستلزم مصدرًا مباشرًا.',
            severity: 'high',
        };
    }
    if (hasAttribution) {
        return {
            label: 'مصدر مذكور',
            reason: 'يوجد إسناد داخل الجملة لكن يلزم التحقق منه.',
            severity: 'medium',
        };
    }
    return {
        label: 'مصدر ثانوي مقبول',
        reason: 'ادعاء وصفي بدون أرقام مباشرة.',
        severity: 'low',
    };
}

function appendEvidenceLink(existing: string, nextValue: string): string {
    const cleaned = cleanText(nextValue || '').trim();
    if (!cleaned) return existing;
    const base = (existing || '').trim();
    if (!base) return cleaned;
    return `${base}\n${cleaned}`;
}

function WorkspaceDraftsPageContent() {
    const queryClient = useQueryClient();
    const { user } = useAuth();
    const { state: tutorialState, update: updateTutorial, complete: completeTutorial, active: tutorialActive } = useTutorialState();
    const userRole = (user?.role || '').toLowerCase();
    const isDirector = userRole === 'director';
    const isJournalist = userRole === 'journalist';
    const isWriterRole = ['journalist', 'social_media', 'print_editor', 'fact_checker'].includes(userRole);
    const search = useSearchParams();
    const articleId = search.get('article_id');
    const initialWork = search.get('work_id');
    const articleNumericId = useMemo(() => {
        if (!articleId) return null;
        const parsed = Number(articleId);
        return Number.isFinite(parsed) ? parsed : null;
    }, [articleId]);
    const autoCreateAttemptRef = useRef(false);

    const [workId, setWorkId] = useState<string | null>(initialWork || null);
    const [title, setTitle] = useState('');
    const [bodyHtml, setBodyHtml] = useState('');
    const [baseVersion, setBaseVersion] = useState(1);
    const [saveState, setSaveState] = useState<SaveState>('saved');
    const [activeTab, setActiveTab] = useState<RightTab>('evidence');
    const viewMode: ViewMode = 'write';
    const [err, setErr] = useState<string | null>(null);
    const [ok, setOk] = useState<string | null>(null);
    const [claims, setClaims] = useState<FactCheckClaim[]>([]);
    const [claimOverrideDrafts, setClaimOverrideDrafts] = useState<Record<string, ClaimOverrideDraft>>({});
    const [proofread, setProofread] = useState<any | null>(null);
    const [quality, setQuality] = useState<any | null>(null);
    const [seoPack, setSeoPack] = useState<any | null>(null);
    const [linkMode, setLinkMode] = useState<'internal' | 'external' | 'mixed'>('mixed');
    const [linkRunId, setLinkRunId] = useState<string | null>(null);
    const [linkSuggestions, setLinkSuggestions] = useState<Array<any>>([]);
    const [social, setSocial] = useState<any | null>(null);
    const [simResult, setSimResult] = useState<any | null>(null);
    const [readiness, setReadiness] = useState<WorkspacePublishReadiness | null>(null);
    const [headlines, setHeadlines] = useState<any[]>([]);
    const [suggestion, setSuggestion] = useState<any | null>(null);
    const [showTechnicalDiff, setShowTechnicalDiff] = useState(false);
    const [diffView, setDiffView] = useState('');
    const [cmpFrom, setCmpFrom] = useState<number | null>(null);
    const [cmpTo, setCmpTo] = useState<number | null>(null);
    const [newDraftOpen, setNewDraftOpen] = useState(false);
    const [manualTitle, setManualTitle] = useState('');
    const [manualBody, setManualBody] = useState('');
    const [manualSummary, setManualSummary] = useState('');
    const [manualCategory, setManualCategory] = useState('local_algeria');
    const [manualUrgency, setManualUrgency] = useState('medium');
    const [leftTab, setLeftTab] = useState<LeftTab>('drafts');
    const surfaceDetails = useMemo(
        () => ({
            role: user?.role || 'guest',
            view_mode: viewMode,
            article_id: articleNumericId,
            work_id: workId,
        }),
        [articleNumericId, user?.role, viewMode, workId],
    );

    useTrackSurfaceView('workspace_drafts', surfaceDetails);
    const [archiveQuery, setArchiveQuery] = useState('');
    const [archiveItems, setArchiveItems] = useState<ArchiveSearchItem[]>([]);
    const [archiveError, setArchiveError] = useState<string | null>(null);

    const [toolsExpanded, setToolsExpanded] = useState(true);
    const [blockersOpen, setBlockersOpen] = useState(false);
    const [decisionDetailOpen, setDecisionDetailOpen] = useState(false);
    const [copilotExpanded, setCopilotExpanded] = useState(false);
    const [copilotOpen, setCopilotOpen] = useState(false);
    const [focusMode, setFocusMode] = useState(false);
    const [headerToolsOpen, setHeaderToolsOpen] = useState(false);
    const [editorStage, setEditorStage] = useState<EditorStage>(isWriterRole ? 'writing' : 'review');
    const [smartHighlightEnabled, setSmartHighlightEnabled] = useState(true);
    const [inlineAiOpen, setInlineAiOpen] = useState(false);
    const [inlineSourceOpen, setInlineSourceOpen] = useState(false);
    const [inlineAiError, setInlineAiError] = useState<string | null>(null);
    const [paletteOpen, setPaletteOpen] = useState(false);
    const [paletteQuery, setPaletteQuery] = useState('');
    const [paletteIndex, setPaletteIndex] = useState(0);
    const paletteInputRef = useRef<HTMLInputElement | null>(null);
    const reportPanelRef = useRef<HTMLDivElement | null>(null);
    const [diffOpen, setDiffOpen] = useState(false);
    const [storyOpen, setStoryOpen] = useState(false);
    const [storyAdvancedOpen, setStoryAdvancedOpen] = useState(false);
    const [selectedStoryId, setSelectedStoryId] = useState<number | null>(null);
    const [overrideOpen, setOverrideOpen] = useState(false);
    const [overrideNote, setOverrideNote] = useState('');
    const [memoryCaptureOpen, setMemoryCaptureOpen] = useState(false);
    const lastSimplifiedWorkRef = useRef<string | null>(null);
    const lastSavedRef = useRef<{ title: string; body: string }>({ title: '', body: '' });
    const isWriteMode = true;
    const isImproveMode = false;
    const isAdvancedMode = false;
    const allowedTabs = useMemo(() => TABS.filter((tab) => (tab.id === 'msi' ? isDirector : true)), [isDirector]);
    const visibleTabs = useMemo(() => {
        const writeIds = new Set<RightTab>(['evidence', 'proofread', 'quality']);
        const improveIds = new Set<RightTab>(['evidence', 'proofread', 'quality', 'seo', 'social', 'context']);
        if (isAdvancedMode) return allowedTabs;
        if (isImproveMode) return allowedTabs.filter((tab) => improveIds.has(tab.id));
        if (isWriteMode && toolsExpanded) return allowedTabs.filter((tab) => improveIds.has(tab.id));
        return allowedTabs.filter((tab) => writeIds.has(tab.id));
    }, [allowedTabs, isAdvancedMode, isImproveMode, isWriteMode, toolsExpanded]);

    const setClaimOverrideDraftField = (claimId: string, patch: Partial<ClaimOverrideDraft>) => {
        setClaimOverrideDrafts((prev) => {
            const current = prev[claimId] || { evidenceLinksRaw: '', unverifiable: false, unverifiableReason: '' };
            return {
                ...prev,
                [claimId]: { ...current, ...patch },
            };
        });
    };

    const buildClaimOverridesPayload = (): ClaimOverrideInput[] => {
        const payload: ClaimOverrideInput[] = [];
        for (const claim of claims) {
            const claimId = String(claim?.id || '').trim();
            if (!claimId) continue;
            const draft = claimOverrideDrafts[claimId] || claimDraftFromClaim(claim);
            const evidenceLinks = parseEvidenceLinks(draft.evidenceLinksRaw || '');
            const unverifiableReason = (draft.unverifiableReason || '').trim();
            const hasOverride = evidenceLinks.length > 0 || draft.unverifiable || Boolean(unverifiableReason);
            if (!hasOverride) continue;
            payload.push({
                claim_id: claimId,
                evidence_links: evidenceLinks,
                unverifiable: Boolean(draft.unverifiable),
                unverifiable_reason: draft.unverifiable ? unverifiableReason : '',
            });
        }
        return payload;
    };

    const { data: listData, isLoading: listLoading } = useQuery({
        queryKey: ['smart-editor-list', articleId],
        queryFn: () => editorialApi.workspaceDrafts({ status: 'draft', limit: 200, article_id: articleNumericId || undefined }),
    });
    const drafts = listData?.data || [];

    const { data: sourcesData } = useQuery({
        queryKey: ['smart-editor-sources'],
        queryFn: () => sourcesApi.list({ enabled: true }),
        staleTime: 1000 * 60 * 10,
    });
    const sources = (sourcesData?.data || []) as Source[];

    useEffect(() => {
        if (!isDirector && activeTab === 'msi') setActiveTab('evidence');
    }, [isDirector, activeTab]);
    useEffect(() => {
        const allowed = new Set(visibleTabs.map((tab) => tab.id));
        if (!allowed.has(activeTab)) setActiveTab(visibleTabs[0]?.id || 'evidence');
    }, [activeTab, visibleTabs]);

    useEffect(() => {
        autoCreateAttemptRef.current = false;
    }, [articleNumericId]);

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
    const { data: constitutionTipsData } = useQuery({
        queryKey: ['smart-editor-constitution-tips'],
        queryFn: () => constitutionApi.tips(),
    });
    const { data: linkHistoryData } = useQuery({
        queryKey: ['smart-editor-links-history', workId],
        queryFn: () => editorialApi.linkSuggestionsHistory(workId!, 8),
        enabled: !!workId,
    });
    const { data: orchestratorData } = useQuery({
        queryKey: ['workspace-prompt-orchestrator', workId],
        queryFn: () => editorialApi.workspacePromptSuggestion(workId!),
        enabled: !!workId,
        staleTime: 1000 * 20,
    });

    const context = contextData?.data;
    const versions = versionsData?.data || [];
    const constitutionTips = constitutionTipsData?.data?.tips || [];
    const articleContextId = context?.article?.id || null;
    const promptSuggestion = (orchestratorData?.data || null) as WorkspacePromptSuggestion | null;
    const invalidatePromptSuggestion = () => {
        queryClient.invalidateQueries({ queryKey: ['workspace-prompt-orchestrator', workId] });
    };
    const { data: storySuggestionsData, isLoading: storySuggestionsLoading } = useQuery({
        queryKey: ['smart-editor-story-suggest', articleContextId],
        queryFn: () => storiesApi.suggest(articleContextId!, { limit: 8 }),
        enabled: Boolean(articleContextId),
        staleTime: 1000 * 60 * 2,
    });
    const storySuggestions = (storySuggestionsData?.data || []) as StorySuggestion[];
    useEffect(() => {
        if (!storySuggestions.length) {
            setSelectedStoryId(null);
            return;
        }
        if (!selectedStoryId || !storySuggestions.some((item) => item.story_id === selectedStoryId)) {
            setSelectedStoryId(storySuggestions[0].story_id);
        }
    }, [storySuggestions, selectedStoryId]);
    const quickCaptureMutation = useMutation({
        mutationFn: (payload: {
            memory_type: 'operational' | 'knowledge' | 'session';
            memory_subtype: string;
            title: string;
            content: string;
            tags: string[];
            importance: number;
            freshness_status: 'stable' | 'review_soon' | 'expired';
            valid_until: string | null;
            note: string | null;
        }) =>
            memoryApi.quickCapture({
                ...payload,
                article_id: articleContextId || articleNumericId || null,
                source_type: 'workspace_draft',
                source_ref: workId ? `workspace:${workId}` : articleContextId ? `article:${articleContextId}` : 'workspace',
            }),
        onSuccess: async () => {
            setOk('تم حفظ الملاحظة في الذاكرة التحريرية.');
            setMemoryCaptureOpen(false);
            await queryClient.invalidateQueries({ queryKey: ['workspace-memory-recommendations'] });
            await queryClient.invalidateQueries({ queryKey: ['memory-items'] });
            await queryClient.invalidateQueries({ queryKey: ['memory-overview'] });
        },
        onError: () => setErr('تعذر حفظ الملاحظة في الذاكرة التحريرية.'),
    });

    const { data: storyCenterData, isLoading: storyCenterLoading } = useQuery({
        queryKey: ['smart-editor-story-center', selectedStoryId],
        queryFn: () => storiesApi.controlCenter(selectedStoryId!, { timeline_limit: 40 }),
        enabled: Boolean(selectedStoryId),
    });
    const storyCenter = storyCenterData?.data as StoryControlCenterResponse | undefined;

    const { data: msiTopDailyData } = useQuery({
        queryKey: ['smart-editor-msi-top-daily'],
        queryFn: () => msiApi.top({ mode: 'daily', limit: 10 }),
        enabled: isDirector,
    });
    const { data: msiTopWeeklyData } = useQuery({
        queryKey: ['smart-editor-msi-top-weekly'],
        queryFn: () => msiApi.top({ mode: 'weekly', limit: 10 }),
        enabled: isDirector,
    });
    const msiTopDaily = msiTopDailyData?.data?.items || [];
    const msiTopWeekly = msiTopWeeklyData?.data?.items || [];
    const linkHistory = linkHistoryData?.data?.items || [];
    const msiContextText = useMemo(
        () =>
            `${context?.draft?.title || ''} ${context?.article?.title_ar || ''} ${context?.article?.original_title || ''}`,
        [context?.draft?.title, context?.article?.title_ar, context?.article?.original_title]
    );
    const msiContextHit = useMemo(() => {
        const all = [...msiTopDaily, ...msiTopWeekly];
        return all.find((item: any) => entityMatchesContext(item?.entity || '', msiContextText)) || null;
    }, [msiTopDaily, msiTopWeekly, msiContextText]);
    const xrayQueryText = useMemo(() => cleanText(context?.draft?.title || context?.article?.title_ar || context?.article?.original_title || ''), [context?.draft?.title, context?.article?.title_ar, context?.article?.original_title]);
    const { data: xrayItemsData } = useQuery({
        queryKey: ['smart-editor-xray-latest', xrayQueryText],
        queryFn: () => competitorXrayApi.latest({ limit: 8, q: xrayQueryText || undefined, status_filter: 'new' }),
        enabled: !!xrayQueryText,
    });
    const xrayItems = xrayItemsData?.data || [];
    const [xrayBrief, setXrayBrief] = useState<any | null>(null);
    const xrayBriefMutation = useMutation({
        mutationFn: (itemId: number) => competitorXrayApi.brief({ item_id: itemId, tone: 'newsroom' }),
        onSuccess: (r) => setXrayBrief(r.data),
    });
    const xrayMarkUsed = useMutation({
        mutationFn: (itemId: number) => competitorXrayApi.markUsed(itemId, 'used'),
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ['smart-editor-xray-latest'] }),
    });

    const smartHighlightExtension = useMemo(() => createSmartHighlightExtension(() => smartHighlightEnabled), [smartHighlightEnabled]);

    const editor = useEditor({
        extensions: [
            StarterKit.configure({ link: false }),
            Highlight,
            Link.configure({ openOnClick: false }),
            Placeholder.configure({ placeholder: 'ابدأ كتابة الخبر هنا...' }),
            smartHighlightExtension,
        ],
        content: '',
        immediatelyRender: false,
        editorProps: {
            attributes: { class: 'smart-editor-content min-h-[300px] md:min-h-[460px] p-4 md:p-6 text-[14px] md:text-[15px] leading-7 md:leading-8 text-white focus:outline-none', dir: 'rtl' },
        },
        onUpdate({ editor: ed }) {
            setBodyHtml(ed.getHTML());
            setSaveState('unsaved');
        },
    });

    useEffect(() => {
        if (editor) editor.view.dispatch(editor.state.tr);
    }, [smartHighlightEnabled, editor]);

    useEffect(() => {
        const draft = context?.draft;
        if (!draft || !editor) return;
        setTitle(cleanText(draft.title || ''));
        setBodyHtml(draft.body || '');
        editor.commands.setContent(draft.body || '<p></p>', { emitUpdate: false });
        setBaseVersion(draft.version || 1);
        setSaveState('saved');
        lastSavedRef.current = { title: cleanText(draft.title || ''), body: draft.body || '' };
        setSuggestion(null);
        setProofread(null);
        setSimResult(null);
        setClaims([]);
        setClaimOverrideDrafts({});
        setReadiness(null);
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
            lastSavedRef.current = { title: cleanText(title || ''), body: bodyHtml || '' };
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
            invalidatePromptSuggestion();
        },
        onError: (e: any) => { setSaveState('error'); setErr(e?.response?.data?.detail || 'تعذر الحفظ التلقائي'); },
    });

    useEffect(() => {
        if (!workId || saveState !== 'unsaved') return;
        if (autosave.isPending) return;
        const currentTitle = cleanText(title || '');
        const currentBody = bodyHtml || '';
        if (lastSavedRef.current.title === currentTitle && lastSavedRef.current.body === currentBody) {
            setSaveState('saved');
            return;
        }
        const t = window.setTimeout(() => { setSaveState('saving'); autosave.mutate(); }, 1200);
        return () => window.clearTimeout(t);
    }, [saveState, workId, title, bodyHtml, autosave.isPending]);

    async function runEditorialActionWithPolling<T = any>(
        action: () => Promise<any>,
        label: string,
        timeoutMs = 90_000,
        pollMs = 750,
    ): Promise<T> {
        const initial = await action();
        const payload = initial?.data;
        if (!payload || payload.status !== 'queued' || !payload.job_id) {
            return payload as T;
        }

        setOk(`${label}: جاري التنفيذ...`);
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
            const statusRes = await jobsApi.getJob(payload.job_id);
            const status = statusRes?.data?.status;
            if (status === 'completed') {
                return (statusRes?.data?.result || {}) as T;
            }
            if (status === 'failed' || status === 'dead_lettered') {
                throw new Error(statusRes?.data?.error || `فشلت العملية (${status}).`);
            }
            await new Promise((resolve) => setTimeout(resolve, pollMs));
        }
        throw new Error(`انتهت مهلة انتظار ${label}.`);
    }

    const rewrite = useMutation({
        mutationFn: () => runEditorialActionWithPolling(() => editorialApi.aiRewriteSuggestion(workId!, { mode: 'formal' }), 'تحسين النص'),
        onSuccess: (data) => {
            setSuggestion(data?.suggestion || null);
            setActiveTab('quality');
            invalidatePromptSuggestion();
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تشغيل تحسين النص'),
    });
    const runProofread = useMutation({
        mutationFn: () => runEditorialActionWithPolling(() => editorialApi.aiProofreadSuggestion(workId!), 'التدقيق اللغوي'),
        onSuccess: (data) => {
            setProofread(data?.suggestion || null);
            setActiveTab('proofread');
            invalidatePromptSuggestion();
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تشغيل التدقيق اللغوي'),
    });
    const applySuggestion = useMutation({
        mutationFn: () => runEditorialActionWithPolling(() => editorialApi.applyAiSuggestion(workId!, {
            title: suggestion?.title,
            body: suggestion?.body_html || '',
            based_on_version: baseVersion,
            suggestion_tool: 'rewrite',
        }), 'تطبيق الاقتراح'),
        onSuccess: (data) => {
            const d = data?.draft;
            if (d && editor) {
                setTitle(cleanText(d.title || ''));
                setBodyHtml(d.body || '');
                editor.commands.setContent(d.body || '<p></p>', { emitUpdate: false });
                setBaseVersion(d.version);
            }
            setSuggestion(null);
            setShowTechnicalDiff(false);
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
            invalidatePromptSuggestion();
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تطبيق الاقتراح'),
    });
    const applyProofread = useMutation({
        mutationFn: () => runEditorialActionWithPolling(() => editorialApi.applyAiSuggestion(workId!, {
            title: proofread?.title || title,
            body: proofread?.body_html || '',
            based_on_version: baseVersion,
            suggestion_tool: 'proofread',
        }), 'تطبيق التدقيق اللغوي'),
        onSuccess: (data) => {
            const d = data?.draft;
            if (d && editor) {
                setTitle(cleanText(d.title || ''));
                setBodyHtml(d.body || '');
                editor.commands.setContent(d.body || '<p></p>', { emitUpdate: false });
                setBaseVersion(d.version);
            }
            setProofread(null);
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
            invalidatePromptSuggestion();
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تطبيق نتيجة التدقيق اللغوي'),
    });

    const runVerifier = useMutation({
        mutationFn: () =>
            runEditorialActionWithPolling(
                () => editorialApi.verifyClaims(workId!, 0.7, buildClaimOverridesPayload()),
                'التحقق من الادعاءات',
            ),
        onSuccess: (data) => {
            const nextClaims = data?.claims || [];
            setClaims(nextClaims);
            setClaimOverrideDrafts((prev) => mergeClaimOverrideDrafts(nextClaims, prev));
            setActiveTab('evidence');
            invalidatePromptSuggestion();
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تنفيذ التحقق'),
    });
    const runQuality = useMutation({
        mutationFn: () => runEditorialActionWithPolling(() => editorialApi.qualityScore(workId!), 'تقييم الجودة'),
        onSuccess: (data) => { setQuality(data); setActiveTab('quality'); invalidatePromptSuggestion(); },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تنفيذ تقييم الجودة'),
    });
    const runSeo = useMutation({
        mutationFn: () => runEditorialActionWithPolling(() => editorialApi.aiSeoSuggestion(workId!), 'تحسين SEO'),
        onSuccess: (data) => {
            setSeoPack(data);
            openReportTab('quality');
            if (!runReadiness.isPending) {
                runReadiness.mutate();
            }
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تشغيل اقتراحات SEO'),
    });
    const runLinks = useMutation({
        mutationFn: () => runEditorialActionWithPolling(
            () => editorialApi.aiLinkSuggestions(workId!, { mode: linkMode, target_count: 6 }),
            'اقتراح الروابط',
        ),
        onSuccess: (data) => {
            setLinkRunId(data?.run_id || null);
            setLinkSuggestions((data?.items || []).map((x: any) => ({ ...x, selected: true })));
            openReportTab('quality');
            if (!runReadiness.isPending) {
                runReadiness.mutate();
            }
            queryClient.invalidateQueries({ queryKey: ['smart-editor-links-history', workId] });
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || 'تعذر توليد اقتراحات الروابط'),
    });
    const validateLinks = useMutation({
        mutationFn: () => {
            if (!linkRunId) throw new Error('شغّل اقتراح الروابط أولاً');
            return editorialApi.validateLinkSuggestions(workId!, linkRunId);
        },
        onSuccess: (r) => {
            const data = r.data || {};
            setOk(`فحص الروابط: ${data.alive || 0} صالح، ${data.dead || 0} غير صالح.`);
            queryClient.invalidateQueries({ queryKey: ['smart-editor-links-history', workId] });
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || e?.message || 'تعذر فحص الروابط'),
    });
    const applyLinks = useMutation({
        mutationFn: () => {
            if (!linkRunId) throw new Error('شغّل اقتراح الروابط أولاً');
            const selectedIds = (linkSuggestions || []).filter((x: any) => x.selected !== false).map((x: any) => Number(x.id));
            return editorialApi.applyLinkSuggestions(workId!, { run_id: linkRunId, based_on_version: baseVersion, item_ids: selectedIds });
        },
        onSuccess: (r) => {
            const d = r.data?.draft;
            if (d && editor) {
                setTitle(cleanText(d.title || ''));
                setBodyHtml(d.body || '');
                editor.commands.setContent(d.body || '<p></p>', { emitUpdate: false });
                setBaseVersion(d.version);
                setSaveState('saved');
            }
            setOk(`تم إدراج ${r.data?.applied_links || 0} رابط في المسودة.`);
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-links-history', workId] });
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || e?.message || 'تعذر تطبيق الروابط'),
    });
    const runSocial = useMutation({
        mutationFn: () => runEditorialActionWithPolling(() => editorialApi.aiSocialVariants(workId!), 'نسخ السوشيال'),
        onSuccess: (data) => {
            setSocial(data?.variants || null);
            openReportTab('quality');
            if (!runReadiness.isPending) {
                runReadiness.mutate();
            }
            invalidatePromptSuggestion();
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر توليد نسخ السوشيال'),
    });
    const runHeadlines = useMutation({
        mutationFn: () => runEditorialActionWithPolling(() => editorialApi.aiHeadlineSuggestion(workId!, 5), 'اقتراح العناوين'),
        onSuccess: (data) => {
            setHeadlines(data?.headlines || []);
            openReportTab('quality');
            if (!runReadiness.isPending) {
                runReadiness.mutate();
            }
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر توليد العناوين'),
    });
    const runArchiveSearch = useMutation({
        mutationFn: (query: string) => archiveApi.search({ q: query, limit: 8, sort: 'recent' }),
        onSuccess: (res) => {
            const items = res?.data?.items || [];
            const sorted = [...items].sort((a, b) => {
                const da = a.published_at ? new Date(a.published_at).getTime() : 0;
                const db = b.published_at ? new Date(b.published_at).getTime() : 0;
                return db - da;
            });
            setArchiveItems(sorted);
            setArchiveError(null);
        },
        onError: () => setArchiveError('تعذر البحث في الأرشيف الآن.'),
    });
    const runReadiness = useMutation({ mutationFn: () => editorialApi.publishReadiness(workId!), onSuccess: (r) => { setReadiness(r.data); setActiveTab('quality'); invalidatePromptSuggestion(); } });
    const runQuickCheck = useMutation({
        mutationFn: async () => {
            const [verifyData, qualityData, readinessRes] = await Promise.all([
                runEditorialActionWithPolling(
                    () => editorialApi.verifyClaims(workId!, 0.7, buildClaimOverridesPayload()),
                    'التحقق من الادعاءات',
                ),
                runEditorialActionWithPolling(() => editorialApi.qualityScore(workId!), 'تقييم الجودة'),
                editorialApi.publishReadiness(workId!),
            ]);
            return { verifyData, qualityData, readinessRes };
        },
        onSuccess: ({ verifyData, qualityData, readinessRes }) => {
            const nextClaims = verifyData?.claims || [];
            setClaims(nextClaims);
            setClaimOverrideDrafts((prev) => mergeClaimOverrideDrafts(nextClaims, prev));
            setQuality(qualityData);
            setReadiness(readinessRes.data);
            setActiveTab('quality');
            setErr(null);
            setOk('اكتمل الفحص السريع: تم تحديث التحقق والجودة وحالة الجاهزية.');
            invalidatePromptSuggestion();
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || 'تعذر تنفيذ الفحص السريع'),
    });
    const runPromptOrchestrator = useMutation({
        mutationFn: (payload?: { task_key?: WorkspaceOrchestratorTaskKey; auto_apply?: boolean }) =>
            editorialApi.runWorkspacePromptTask(workId!, payload || {
                task_key: promptSuggestion?.task_key,
                auto_apply: promptSuggestion?.auto_apply_default,
            }),
        onSuccess: (response) => {
            const data = response?.data;
            if (!data) return;
            const taskKey = data.task?.task_key;
            if (data.error) {
                setErr(data.error);
                return;
            }

            if (data.result_type === 'suggestion' && data.suggestion) {
                if (taskKey === 'proofread') {
                    setProofread(data.suggestion);
                    setActiveTab('proofread');
                } else {
                    setSuggestion(data.suggestion);
                    setActiveTab('quality');
                }
            }
            if (data.result_type === 'claims' && data.report) {
                const nextClaims = ((data.report as any)?.claims || []) as FactCheckClaim[];
                setClaims(nextClaims);
                setClaimOverrideDrafts((prev) => mergeClaimOverrideDrafts(nextClaims, prev));
                setActiveTab('evidence');
            }
            if (data.result_type === 'quality' && data.report) {
                setQuality(data.report);
                setActiveTab('quality');
            }
            if (data.result_type === 'headlines') {
                setHeadlines(data.headlines || []);
                setActiveTab('seo');
            }
            if (data.result_type === 'social') {
                setSocial(data.variants || null);
                setActiveTab('social');
            }
            if (data.result_type === 'readiness' && data.readiness) {
                setReadiness(data.readiness);
                setActiveTab('quality');
            }
            if (data.applied && data.draft && editor) {
                setTitle(cleanText(data.draft.title || ''));
                setBodyHtml(data.draft.body || '');
                editor.commands.setContent(data.draft.body || '<p></p>', { emitUpdate: false });
                setBaseVersion(data.draft.version);
                setSaveState('saved');
                queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
                queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] });
            }
            invalidatePromptSuggestion();
            setErr(null);
            setOk(data.applied
                ? `اكتمل ${data.task?.task_label || 'التوليد الذكي'} وتم تحديث المسودة تلقائيًا.`
                : `اكتمل ${data.task?.task_label || 'التوليد الذكي'} وجاهز الآن للمراجعة.`);
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تشغيل التوليد الذكي'),
    });

    const runInlineAi = useMutation({
        mutationFn: (payload: { action: 'rewrite' | 'shorten' | 'expand' | 'clarify'; text: string; from: number; to: number }) =>
            editorialApi.aiInlineSuggestion(workId!, { action: payload.action, text: payload.text }),
        onSuccess: (res, payload) => {
            const nextText = cleanText(res?.data?.text || '');
            if (editor && nextText) {
                editor.chain().focus().insertContentAt({ from: payload.from, to: payload.to }, nextText).run();
                setSaveState('unsaved');
            }
            setInlineAiOpen(false);
            setInlineAiError(null);
        },
        onError: () => setInlineAiError('تعذر تنفيذ الإجراء على المقطع المحدد.'),
    });

    const readinessBlockers = useMemo(() => buildBlockerExplanations({
        readiness,
        quality,
        proofread,
        claims,
        seoPack,
    }), [readiness, quality, proofread, claims, seoPack]);

    const decisionModel = useMemo(() => {
        const urgent: DecisionItem[] = [];
        const improve: DecisionItem[] = [];
        const extra: DecisionItem[] = [];

        const isBreaking = String(context?.article?.urgency || '').toLowerCase() === 'breaking';

        const pushUnique = (list: DecisionItem[], item: DecisionItem) => {
            if (list.some((x) => x.id === item.id)) return;
            list.push(item);
        };

        if (readinessBlockers.length) {
            readinessBlockers.forEach((explained, idx) => {
                pushUnique(urgent, {
                    id: `readiness-block-${idx}`,
                    title: explained.title,
                    reason: explained.detail,
                    impact: impactBySeverity('critical'),
                    rule: 'بوابة النشر: معالجة الموانع قبل الإرسال.',
                    severity: 'critical',
                    confidence: 0.82,
                    action: explained.action || 'publish_gate',
                });
            });
        }

        (claims || []).forEach((claim: any, idx: number) => {
            if (!claim?.blocking) return;
            const text = cleanText(claim?.text || '');
            pushUnique(urgent, {
                id: `claim-${claim?.id || idx}`,
                title: 'ادعاء يحتاج إسناداً',
                reason: text || 'ادعاء دون إسناد كافٍ.',
                impact: impactBySeverity('high'),
                rule: 'لا ادعاء دون مصدر واضح.',
                severity: 'high',
                confidence: Number(claim?.confidence || 0),
                action: 'verify',
            });
        });

        const proofIssues = (proofread?.issues || []) as Array<any>;
        proofIssues.forEach((issue, idx) => {
            const sev = (issue?.severity as DecisionSeverity) || (issue?.kind === 'headline' ? 'medium' : 'low');
            const target = sev === 'critical' || sev === 'high' ? urgent : improve;
            pushUnique(target, {
                id: `proof-${issue?.kind || idx}-${idx}`,
                title: issue?.kind === 'headline' ? 'عنوان يحتاج ضبطاً' : 'ملاحظة أسلوبية',
                reason: cleanText(issue?.message || '') || 'ملاحظة تحريرية/لغوية.',
                impact: issue?.impact ? cleanText(issue?.impact) : impactBySeverity(sev),
                rule: cleanText(issue?.rule || 'قواعد التحرير اللغوي والأسلوبي.'),
                severity: sev,
                confidence: Number(issue?.confidence || 0.6),
                action: 'proofread',
            });
        });

        (quality?.actionable_fixes || []).forEach((fix: string, idx: number) => {
            const cleanFix = cleanText(fix || '');
            if (!cleanFix) return;
            pushUnique(improve, {
                id: `quality-fix-${idx}`,
                title: 'تحسين جودة التحرير',
                reason: cleanFix,
                impact: impactBySeverity('medium'),
                rule: 'رفع وضوح وبنية الخبر.',
                severity: 'medium',
                confidence: 0.7,
                action: 'quality',
            });
        });

        if (!quality) {
            pushUnique(improve, {
                id: 'quality-missing',
                title: 'لم يتم تشغيل تقييم الجودة',
                reason: 'لا توجد درجة جودة حالياً.',
                impact: 'قد تمرّ مشكلات وضوح أو بنية دون تنبيه.',
                rule: 'شغّل تقييم الجودة قبل الاعتماد.',
                severity: 'medium',
                confidence: 0.6,
                action: 'quality',
            });
        }

        if (!seoPack) {
            pushUnique(extra, {
                id: 'seo-missing',
                title: 'SEO غير مُفعل',
                reason: 'لم يتم توليد عنوان ووصف وكلمات مفتاحية.',
                impact: 'تحسين إضافي لنتائج البحث.',
                rule: 'تهيئة SEO قبل النشر النهائي.',
                severity: 'low',
                confidence: 0.55,
                action: 'seo',
            });
        }
        if (!headlines.length) {
            pushUnique(extra, {
                id: 'headlines-missing',
                title: 'اقتراح العناوين غير مشغّل',
                reason: 'لا توجد بدائل تحريرية للعنوان.',
                impact: 'تحسين إضافي يمكن أن يرفع وضوح الخبر.',
                rule: 'توليد عناوين متعددة للمقارنة.',
                severity: 'low',
                confidence: 0.55,
                action: 'headlines',
            });
        }
        if (!social) {
            pushUnique(extra, {
                id: 'social-missing',
                title: 'نسخ السوشيال غير مولدة',
                reason: 'لا توجد نسخ للنشر الاجتماعي.',
                impact: 'تحسين إضافي لفريق الديجيتال.',
                rule: 'توليد نسخ السوشيال قبل الجدولة.',
                severity: 'low',
                confidence: 0.5,
                action: 'social',
            });
        }
        if (!linkSuggestions.length) {
            pushUnique(extra, {
                id: 'links-missing',
                title: 'روابط مقترحة غير متاحة',
                reason: 'لم يتم توليد روابط داخلية/خارجية بعد.',
                impact: 'تحسين إضافي للسياق والSEO.',
                rule: 'توليد روابط سياقية عند الحاجة.',
                severity: 'low',
                confidence: 0.5,
                action: 'links',
            });
        }

        const headlineCandidates = headlines.length
            ? headlines.map((h: any) => String(h?.headline || '')).filter(Boolean)
            : [title || context?.article?.title_ar || context?.article?.original_title || ''];
        const scored = headlineCandidates.map((h) => ({ headline: h, ...evaluateHeadline(h, isBreaking) }));
        scored.sort((a, b) => b.score - a.score);
        const bestHeadline = scored[0] || { headline: '', score: 0, risks: [], reasons: [] };

        urgent.sort((a, b) => severityRank(b.severity) - severityRank(a.severity));
        improve.sort((a, b) => severityRank(b.severity) - severityRank(a.severity));
        extra.sort((a, b) => severityRank(b.severity) - severityRank(a.severity));

        return { urgent, improve, extra, bestHeadline };
    }, [readinessBlockers, claims, proofread, quality, seoPack, headlines, social, linkSuggestions, context?.article?.urgency, context?.article?.title_ar, context?.article?.original_title, title]);

    const headlineInsights = useMemo(() => {
        const isBreaking = String(context?.article?.urgency || '').toLowerCase() === 'breaking';
        const candidates = (headlines.length
            ? headlines.map((h: any) => String(h?.headline || '')).filter(Boolean)
            : [title || context?.article?.title_ar || context?.article?.original_title || ''].filter(Boolean));
        const scored = candidates.map((headline) => ({ headline, ...evaluateHeadline(headline, isBreaking) }));
        scored.sort((a, b) => b.score - a.score);
        return scored;
    }, [headlines, title, context?.article?.title_ar, context?.article?.original_title, context?.article?.urgency]);

    const professionalReview = useMemo(() => {
        const proofIssues = (proofread?.issues || []) as Array<any>;
        const proofHigh = proofIssues.filter((issue) => ['critical', 'high'].includes(String(issue?.severity))).length;
        const proofTotal = proofIssues.length;
        const claimTotal = claims.length;
        const claimBlocking = claims.filter((claim: any) => claim?.blocking).length;
        const claimHighRisk = claims.filter((claim: any) => String(claim?.risk_level || '').toLowerCase() === 'high').length;
        const qualityScore = typeof quality?.score === 'number' ? Number(quality.score) : null;
        const readinessReady = Boolean(readiness?.ready_for_publish);

        const cards: ReviewCard[] = [
            {
                id: 'readiness',
                title: 'بوابة النشر',
                value: readiness ? (readinessReady ? 'جاهز للنشر' : 'غير جاهز') : 'غير مفعلة',
                hint: readiness ? (readinessReady ? 'لا توجد ملاحظات حرجة حالياً.' : 'راجع ملاحظات الجودة قبل الإرسال.') : 'شغّل بوابة النشر للتحقق من الجاهزية.',
                severity: readiness ? (readinessReady ? 'low' : 'high') : 'medium',
                action: 'publish_gate',
            },
            {
                id: 'claims',
                title: 'الادعاءات',
                value: claimTotal ? `${claimBlocking} حرجة من ${claimTotal}` : 'لا ادعاءات بعد',
                hint: claimBlocking ? 'ادعاءات بحاجة مصادر مباشرة.' : claimHighRisk ? 'يوجد ادعاءات عالية المخاطر.' : 'لا توجد ادعاءات حرجة.',
                severity: claimBlocking ? 'high' : claimTotal ? 'medium' : 'low',
                action: 'verify',
            },
            {
                id: 'proofread',
                title: 'التدقيق والأسلوب',
                value: proofTotal ? `${proofTotal} ملاحظة` : 'نظيف',
                hint: proofHigh ? `${proofHigh} ملاحظة عالية الأثر.` : proofTotal ? 'تحتاج تحسينات لغوية/أسلوبية.' : 'لا توجد ملاحظات كبيرة.',
                severity: proofHigh ? 'high' : proofTotal ? 'medium' : 'low',
                action: 'proofread',
            },
            {
                id: 'quality',
                title: 'جودة التحرير',
                value: qualityScore !== null ? `${qualityScore}/100` : 'غير متاح',
                hint: qualityScore !== null ? 'راجع مؤشرات البنية والوضوح.' : 'شغّل تقييم الجودة للحصول على الدرجة.',
                severity: qualityScore !== null ? (qualityScore < 70 ? 'high' : qualityScore < 85 ? 'medium' : 'low') : 'medium',
                action: 'quality',
            },
            {
                id: 'headlines',
                title: 'العناوين',
                value: headlines.length ? `${headlines.length} عنوان` : 'غير مولدة',
                hint: headlines.length ? 'قارن مع أفضل عنوان مقترح.' : 'ولّد بدائل للعنوان قبل الاعتماد.',
                severity: headlines.length ? 'low' : 'medium',
                action: 'headlines',
            },
            {
                id: 'seo',
                title: 'SEO + روابط',
                value: seoPack ? 'جاهز' : 'غير مشغّل',
                hint: linkSuggestions.length ? `روابط مقترحة: ${linkSuggestions.length}` : 'لم يتم توليد روابط بعد.',
                severity: seoPack ? 'low' : 'medium',
                action: 'seo',
            },
            {
                id: 'social',
                title: 'السوشيال',
                value: social ? 'جاهز' : 'غير مشغّل',
                hint: social ? 'نسخ جاهزة للنشر الرقمي.' : 'ولّد النسخ الاجتماعية قبل الجدولة.',
                severity: social ? 'low' : 'low',
                action: 'social',
            },
        ];

        if (simResult) {
            cards.push({
                id: 'audience',
                title: 'محاكي الجمهور',
                value: `مخاطر ${Number(simResult?.risk_score || 0).toFixed(1)}/10`,
                hint: `ثقة ${Number(simResult?.confidence_score || 0).toFixed(1)}% • انتشار ${Number(simResult?.virality_score || 0).toFixed(1)}/10`,
                severity: Number(simResult?.risk_score || 0) >= 7 ? 'high' : Number(simResult?.risk_score || 0) >= 4 ? 'medium' : 'low',
            });
        } else {
            cards.push({
                id: 'audience',
                title: 'محاكي الجمهور',
                value: 'غير مشغّل',
                hint: 'شغّل المحاكي لمعرفة المخاطر قبل الاعتماد.',
                severity: 'low',
            });
        }

        if (xrayItems.length) {
            cards.push({
                id: 'xray',
                title: 'زوايا المنافسين',
                value: `${xrayItems.length} زاوية متاحة`,
                hint: 'استفد من Brief المقترح لإبراز قيمة الخبر.',
                severity: 'low',
            });
        }

        return cards;
    }, [claims, headlines, linkSuggestions.length, proofread, quality, readiness, seoPack, simResult, social, xrayItems.length]);

    const decisionActionHandlers: Record<DecisionActionId, () => void> = {
        verify: () => runVerifier.mutate(),
        quality: () => runQuality.mutate(),
        proofread: () => runProofread.mutate(),
        seo: () => runSeo.mutate(),
        headlines: () => runHeadlines.mutate(),
        links: () => runLinks.mutate(),
        social: () => runSocial.mutate(),
        publish_gate: () => runReadiness.mutate(),
        quick_check: () => runQuickCheck.mutate(),
    };

    const nextAction = useMemo(() => {
        const primary = decisionModel.urgent[0] || decisionModel.improve[0] || null;
        if (primary && primary.action) {
            return {
                label: `التالي: ${primary.title}`,
                description: primary.reason,
                actionId: primary.action as ActionId,
                severity: primary.severity,
                handler: decisionActionHandlers[primary.action],
            };
        }
        return {
            label: 'تشغيل فحص سريع',
            description: 'لا توجد ملاحظات ظاهرة الآن. شغّل الفحص للتأكيد.',
            actionId: 'quick_check' as ActionId,
            severity: 'low' as DecisionSeverity,
            handler: decisionActionHandlers.quick_check,
        };
    }, [decisionModel, decisionActionHandlers]);

    const blockerSummary = useMemo(() => {
        const blockers = decisionModel.urgent.filter((item) => item.severity === 'critical' || item.severity === 'high');
        return {
            items: blockers,
            count: blockers.length,
            top: blockers[0] || null,
        };
    }, [decisionModel]);

    const explainedBlockers = useMemo(() => readinessBlockers, [readinessBlockers]);

    const blockerActionHandler = blockerSummary.top?.action
        ? decisionActionHandlers[blockerSummary.top.action]
        : null;

    const compactStatus = useMemo(() => {
        const readinessLabel = readiness
            ? (readiness.ready_for_publish ? 'جاهز للنشر' : 'غير جاهز')
            : 'لم يتم الفحص';
        const blockingClaims = claims.filter((claim: any) => claim?.blocking).length;
        const qualityScore = typeof quality?.score === 'number' ? `${quality.score}/100` : 'غير متاح';
        return { readinessLabel, blockingClaims, qualityScore };
    }, [readiness, claims, quality]);

    const bodyText = useMemo(() => htmlToReadableText(bodyHtml || ''), [bodyHtml]);
    const hasSubmissionBody = bodyText.trim().length >= 120;

    const storyTimelineFromContext = useMemo(
        () => (context?.story_context?.timeline || []) as StoryContextItem[],
        [context?.story_context?.timeline]
    );
    const storyTimelineFromCenter = useMemo(() => {
        const centerTimeline = (storyCenter?.timeline || []) as StoryCenterTimelineItem[];
        return centerTimeline.map((item) => ({
            id: item.id,
            title: item.title,
            summary: null,
            url: item.url || null,
            source_name: item.source_name || null,
            created_at: item.created_at || null,
            published_at: item.created_at || null,
            category: null,
            status: item.status || null,
        })) as StoryContextItem[];
    }, [storyCenter?.timeline]);
    const storyTimeline = useMemo(
        () => (storyTimelineFromCenter.length ? storyTimelineFromCenter : storyTimelineFromContext),
        [storyTimelineFromCenter, storyTimelineFromContext]
    );
    const storyRelations = useMemo(() => (context?.story_context?.relations || []) as StoryContextItem[], [context?.story_context?.relations]);
    const storyItems = useMemo(() => [...storyTimeline, ...storyRelations], [storyTimeline, storyRelations]);
    const storyTimelineSorted = useMemo(() => {
        const list = [...storyTimeline];
        list.sort((a, b) => storyItemTimestamp(b) - storyItemTimestamp(a));
        return list;
    }, [storyTimeline]);
    const storyTimelineChrono = useMemo(() => {
        const list = [...storyTimeline].filter((item) => storyItemTimestamp(item) > 0);
        list.sort((a, b) => storyItemTimestamp(a) - storyItemTimestamp(b));
        return list;
    }, [storyTimeline]);
    const storyHub = useMemo(() => {
        const sources = new Set<string>();
        const categories = new Set<string>();
        let latest = 0;
        for (const item of storyItems) {
            const source = cleanText(item?.source_name || '');
            const category = cleanText(item?.category || '');
            if (source) sources.add(source);
            if (category) categories.add(category);
            latest = Math.max(latest, storyItemTimestamp(item));
        }
        const latestLabel = latest ? new Date(latest).toLocaleString('ar-DZ') : '—';
        return {
            total: storyItems.length,
            timelineCount: storyTimeline.length,
            relationsCount: storyRelations.length,
            sourcesCount: sources.size,
            categories: Array.from(categories).slice(0, 4),
            latestLabel,
            coverageScore: storyCenter?.overview?.coverage_score ?? null,
            gapsCount: storyCenter?.overview?.gaps_count ?? null,
        };
    }, [storyItems, storyTimeline.length, storyRelations.length, storyCenter?.overview?.coverage_score, storyCenter?.overview?.gaps_count]);
    const localStoryGaps = useMemo<StoryGap[]>(() => {
        const gaps: StoryGap[] = [];
        const text = `${bodyText} ${cleanText(context?.article?.summary || '')} ${cleanText(context?.article?.original_content || '')}`.trim();
        const hasNumbers = /\d/.test(text);
        const hasQuote = /(قال|أفاد|أعلن|صرّح|صرح|أكد|حسب|وفق)/.test(text);
        const hasReaction = /(رد|تعليق|انتقاد|ترحيب|أكدت المعارضة|رفض|طالبت)/.test(text);
        const sourcesSet = new Set(storyItems.map((item) => cleanText(item?.source_name || '')).filter(Boolean));
        const hasBlockingClaims = claims.some((claim: any) => claim?.blocking);
        if (hasBlockingClaims) {
            gaps.push({
                id: 'claims',
                title: 'ادعاءات بحاجة إلى توثيق',
                hint: 'يوجد ادعاءات حرجة بدون مصادر كافية. شغّل التحقق لإضافة الأدلة.',
                severity: 'high',
                action: 'verify',
            });
        }
        if (sourcesSet.size < 2) {
            gaps.push({
                id: 'sources',
                title: 'تنويع المصادر',
                hint: 'أضف مصدراً ثانياً مستقلاً لتقوية المصداقية.',
                severity: 'medium',
            });
        }
        if (!hasNumbers) {
            gaps.push({
                id: 'numbers',
                title: 'لا توجد بيانات رقمية',
                hint: 'أضف أرقاماً أو إحصاءات موثقة لتدعيم الخبر.',
                severity: 'medium',
            });
        }
        if (!hasQuote) {
            gaps.push({
                id: 'quote',
                title: 'لا يوجد تصريح مباشر',
                hint: 'أدرج تصريحاً أو بياناً رسمياً إن توفر.',
                severity: 'low',
            });
        }
        if (!hasReaction) {
            gaps.push({
                id: 'reaction',
                title: 'لا توجد ردود فعل',
                hint: 'حاول إضافة رأي طرف آخر أو رد فعل مختصر.',
                severity: 'low',
            });
        }
        if (storyTimeline.length < 3) {
            gaps.push({
                id: 'timeline',
                title: 'السياق الزمني محدود',
                hint: 'أضف مواد سابقة لشرح الخلفية والتطورات.',
                severity: 'low',
            });
        }
        return gaps.slice(0, 5);
    }, [bodyText, context?.article?.summary, context?.article?.original_content, storyItems, storyTimeline.length, claims]);
    const storyGaps = useMemo<StoryGap[]>(() => {
        const centerGaps = storyCenter?.gaps || [];
        if (centerGaps.length > 0) {
            return centerGaps.slice(0, 6).map((gap, idx) => ({
                id: `${gap.code || 'story_gap'}_${idx}`,
                title: cleanText(gap.title || 'فجوة تغطية'),
                hint: cleanText(gap.recommendation || 'أضف مادة تغطي هذه الفجوة.'),
                severity: mapStoryGapSeverity(gap.severity),
            }));
        }
        return localStoryGaps;
    }, [storyCenter?.gaps, localStoryGaps]);
    const storyTopSources = useMemo(() => storyTimelineSorted.slice(0, 5), [storyTimelineSorted]);

    const [storyLastSeenAt, setStoryLastSeenAt] = useState<string | null>(null);
    useEffect(() => {
        if (!storyOpen || !selectedStoryId || typeof window === 'undefined') return;
        const key = `story_last_seen_${selectedStoryId}`;
        setStoryLastSeenAt(window.localStorage.getItem(key));
    }, [storyOpen, selectedStoryId]);

    const storyLastSeenMs = useMemo(() => {
        if (!storyLastSeenAt) return 0;
        const ts = new Date(storyLastSeenAt).getTime();
        return Number.isNaN(ts) ? 0 : ts;
    }, [storyLastSeenAt]);

    const storyUpdatesSinceLastSeen = useMemo(() => {
        if (!storyLastSeenMs) return [];
        return storyTimelineSorted.filter((item) => storyItemTimestamp(item) > storyLastSeenMs);
    }, [storyTimelineSorted, storyLastSeenMs]);

    const storyWhatChanged = useMemo(() => {
        if (!storyLastSeenMs) return 'هذه أول مرة تفتح هذه القصة.';
        if (storyUpdatesSinceLastSeen.length === 0) return 'لا جديد منذ آخر زيارة.';
        return `تمت إضافة ${storyUpdatesSinceLastSeen.length} مادة منذ آخر زيارة.`;
    }, [storyLastSeenMs, storyUpdatesSinceLastSeen.length]);

    const storyWhyNow = useMemo(() => {
        if (storyUpdatesSinceLastSeen.length >= 2) return 'القصة نشطة الآن بسبب تحديثات متتالية خلال فترة قصيرة.';
        if (storyGaps.some((gap) => gap.severity === 'high')) return 'القصة تحتاج تدخلًا تحريريًا لأن فيها فجوة حرجة.';
        if ((storyHub.coverageScore ?? 0) < 60) return 'التغطية ما زالت ناقصة وتحتاج استكمالًا قبل الإغلاق.';
        return 'القصة مستقرة ويمكن تعزيزها بمتابعة قصيرة.';
    }, [storyUpdatesSinceLastSeen.length, storyGaps, storyHub.coverageScore]);

    const storyUsage = useMemo(() => {
        const contextText = normalizeForMatch(bodyText);
        const used: StoryContextItem[] = [];
        const unused: StoryContextItem[] = [];
        storyTopSources.forEach((item) => {
            const title = cleanText(item.title || '');
            const isUsed = title ? entityMatchesContext(title, contextText) : false;
            if (isUsed) used.push(item);
            else unused.push(item);
        });
        return { used, unused };
    }, [bodyText, storyTopSources]);

    function closeStoryMode() {
        if (selectedStoryId && typeof window !== 'undefined') {
            const key = `story_last_seen_${selectedStoryId}`;
            window.localStorage.setItem(key, new Date().toISOString());
        }
        setStoryAdvancedOpen(false);
        setStoryOpen(false);
    }
    const autoTimelineLines = useMemo(() => {
        const lines = storyTimelineChrono.slice(-8).map((item) => {
            const dateLabel = storyItemDateLabel(item);
            const titleLine = cleanText(item?.title || 'خبر مرتبط');
            return dateLabel ? `${dateLabel} — ${titleLine}` : titleLine;
        });
        return lines.filter(Boolean);
    }, [storyTimelineChrono]);
    const runAudienceSimulation = useMutation({
        mutationFn: async () => {
            const headline = cleanText(title || context?.article?.title_ar || context?.article?.original_title || '');
            const excerpt = htmlToReadableText(bodyHtml || context?.draft?.body || '').slice(0, 1800);
            if (!headline || headline.length < 6) {
                throw new Error('العنوان غير كافٍ لتشغيل محاكي الجمهور.');
            }
            const runRes = await simApi.run({
                headline,
                excerpt,
                platform: 'facebook',
                mode: 'fast',
                article_id: context?.article?.id,
                draft_id: context?.draft?.id,
            });
            const runId = runRes.data.run_id;
            for (let i = 0; i < 30; i += 1) {
                const statusRes = await simApi.runStatus(runId);
                const status = statusRes.data?.status;
                if (status === 'completed') {
                    const resultRes = await simApi.result(runId);
                    return { runId, result: resultRes.data };
                }
                if (status === 'failed') {
                    throw new Error(statusRes.data?.error || 'فشل تشغيل محاكي الجمهور.');
                }
                await new Promise((resolve) => setTimeout(resolve, 1500));
            }
            throw new Error('انتهت مهلة انتظار نتيجة محاكي الجمهور.');
        },
        onSuccess: ({ runId, result }) => {
            setSimResult({ ...result, run_id: runId });
            setActiveTab('simulator');
            setErr(null);
            setOk('تم تحديث نتائج محاكي الجمهور بنجاح.');
        },
        onError: (e: any) => setErr(e?.message || e?.response?.data?.detail || 'تعذر تشغيل محاكي الجمهور'),
    });
    const runDiff = useMutation({ mutationFn: () => editorialApi.draftDiff(workId!, cmpFrom!, cmpTo!), onSuccess: (r) => setDiffView(r.data?.diff || '') });
    const restoreVersion = useMutation({ mutationFn: (v: number) => editorialApi.restoreWorkspaceDraftVersion(workId!, v), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] }); queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', workId] }); } });
    const handleSubmissionSuccess = (data: any, fallbackMessage: string) => {
        setOk(data?.status_message ? `تم الإرسال: ${data.status_message}` : fallbackMessage);
        setErr(null);
        queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
    };
    const applyToArticle = useMutation({
        mutationFn: () => editorialApi.submitWorkspaceDraftForChief(workId!),
        onSuccess: (res) => {
            handleSubmissionSuccess(res.data || {}, 'تم إرسال النسخة إلى رئيس التحرير.');
            if (tutorialActive && tutorialState.role === 'journalist' && tutorialState.step === 'editor_submit') {
                completeTutorial();
            }
        },
        onError: (e: any) => {
            const detail = e?.response?.data?.detail;
            if (detail?.blocking_reasons) {
                setErr('ظهرت ملاحظات جودة. يمكنك المتابعة بالاعتماد المباشر أو الإرسال بتحفّظ.');
                setOverrideOpen(true);
                return;
            }
            setErr(detail || e?.message || 'تعذر إرسال النسخة.');
        },
    });
    const selfApproveDraft = useMutation({
        mutationFn: () => editorialApi.selfApproveWorkspaceDraft(workId!),
        onSuccess: (res) => {
            handleSubmissionSuccess(res.data || {}, 'تم اعتماد الموضوع مباشرة من الصحفي.');
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || e?.message || 'تعذر الاعتماد المباشر.'),
    });
    const submitWithReservations = useMutation({
        mutationFn: () => editorialApi.submitWorkspaceDraftWithReservations(workId!, { notes: overrideNote.trim() }),
        onSuccess: (res) => {
            const data = res.data || {};
            setOk(data?.message || 'تم إرسال طلب اعتماد بتحفظات.');
            setErr(null);
            setOverrideOpen(false);
            setOverrideNote('');
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', workId] });
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || e?.message || 'تعذر إرسال الطلب بتحفظات'),
    });
    const handleTutorialEditNext = () => {
        updateTutorial({ step: 'editor_submit' });
    };
    const handleTutorialSubmit = () => {
        if (applyToArticle.isPending) return;
        if (!hasSubmissionBody) {
            completeTutorial();
            return;
        }
        applyToArticle.mutate();
    };
    const createManualDraft = useMutation({
        mutationFn: () =>
            editorialApi.createManualWorkspaceDraft({
                title: manualTitle,
                body: manualBody,
                summary: manualSummary || undefined,
                category: manualCategory,
                urgency: manualUrgency,
                source_action: 'manual_topic',
            }),
        onSuccess: (res) => {
            const nextWorkId = res.data?.work_id;
            if (!nextWorkId) return;
            setWorkId(nextWorkId);
            setOk('تم إنشاء مسودة جديدة وفتحها في المحرر.');
            setErr(null);
            setNewDraftOpen(false);
            setManualTitle('');
            setManualBody('');
            setManualSummary('');
            queryClient.invalidateQueries({ queryKey: ['smart-editor-list'] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', nextWorkId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', nextWorkId] });
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || 'تعذر إنشاء المسودة الجديدة'),
    });
    const createStoryDraft = useMutation({
        mutationFn: async (mode: StoryDraftMode) => {
            const storyTitle = cleanText(storyCenter?.story?.title || context?.article?.title_ar || context?.article?.original_title || title || 'قصة');
            const topItems = storyTopSources.slice(0, 4);
            const topLines = topItems
                .map((item, idx) => {
                    const source = cleanText(item.source_name || '');
                    const date = storyItemDateLabel(item);
                    const meta = [source, date].filter(Boolean).join(' • ');
                    return `${idx + 1}. ${cleanText(item.title || 'عنصر مرتبط')}${meta ? ` (${meta})` : ''}`;
                })
                .join('\n');
            const gapsLines = storyGaps.slice(0, 3).map((gap) => `- ${gap.title}`).join('\n');
            const header = mode === 'analysis' ? 'تحليل' : mode === 'background' ? 'خلفية' : 'متابعة';
            const body = mode === 'analysis'
                ? `مقدمة تحليلية:\n\nخلاصة المستجد:\n${cleanText(context?.article?.summary || '') || '—'}\n\nالمعطيات:\n${topLines || '- لا توجد مواد كافية بعد'}\n\nما الذي يحتاج تدقيقاً:\n${gapsLines || '- لا توجد فجوات حرجة'}\n\nالاستنتاج:\n`
                : mode === 'background'
                  ? `خلفية القصة:\n\nالمحطات الرئيسية:\n${topLines || '- لا توجد مواد كافية بعد'}\n\nالسياق الأوسع:\n\nنقاط تحتاج استكمال:\n${gapsLines || '- لا توجد فجوات حرجة'}\n`
                  : `تحديث جديد على القصة:\n\nأبرز ما استجد:\n${topLines || '- لا توجد مواد كافية بعد'}\n\nما الذي تغيّر الآن:\n\nالمتابعة القادمة:\n`;
            return editorialApi.createManualWorkspaceDraft({
                title: `${storyTitle} — ${header}`,
                body,
                summary: cleanText(context?.article?.summary || '') || undefined,
                category: storyCenter?.story?.category || context?.article?.category || undefined,
                urgency: context?.article?.urgency || 'medium',
                source_action: `story_${mode}`,
            });
        },
        onSuccess: (res, mode) => {
            const nextWorkId = res.data?.work_id;
            if (!nextWorkId) {
                setErr('تم إنشاء المسودة لكن بدون Work ID.');
                return;
            }
            setWorkId(nextWorkId);
            setStoryOpen(false);
            setOk(mode === 'analysis' ? 'تم إنشاء مسودة تحليل وفتحها.' : mode === 'background' ? 'تم إنشاء مسودة خلفية وفتحها.' : 'تم إنشاء مسودة متابعة وفتحها.');
            setErr(null);
            queryClient.invalidateQueries({ queryKey: ['smart-editor-list'] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', nextWorkId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', nextWorkId] });
        },
        onError: (e: any) => setErr(e?.response?.data?.detail || 'تعذر إنشاء مسودة من القصة'),
    });
    const createDraftFromArticle = useMutation({
        mutationFn: () => editorialApi.handoff(articleNumericId!),
        onSuccess: (res) => {
            const nextWorkId = res.data?.work_id;
            if (!nextWorkId) {
                setErr('تم ترشيح الخبر ولكن لم يتم إنشاء Work ID. أعد المحاولة.');
                return;
            }
            setWorkId(nextWorkId);
            setErr(null);
            setOk('تم إنشاء المسودة من الخبر وفتحها في المحرر.');
            queryClient.invalidateQueries({ queryKey: ['smart-editor-list', articleId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-context', nextWorkId] });
            queryClient.invalidateQueries({ queryKey: ['smart-editor-versions', nextWorkId] });
        },
        onError: (e: any) => {
            setErr(e?.response?.data?.detail || 'تعذر إنشاء مسودة الخبر. حاول مرة أخرى.');
        },
    });

    useEffect(() => {
        if (!articleNumericId || listLoading || workId || drafts.length > 0) return;
        if (autoCreateAttemptRef.current) return;
        autoCreateAttemptRef.current = true;
        createDraftFromArticle.mutate();
    }, [articleNumericId, listLoading, workId, drafts.length, createDraftFromArticle]);

    useEffect(() => {
        if (tutorialActive && tutorialState.role === 'journalist' && tutorialState.step === 'news_open' && workId) {
            updateTutorial({ step: 'editor_edit' });
        }
    }, [tutorialActive, tutorialState.role, tutorialState.step, updateTutorial, workId]);

    useEffect(() => {
        if (!isWriterRole) return;
        const marker = workId || articleId || 'initial';
        if (lastSimplifiedWorkRef.current === marker) return;
        lastSimplifiedWorkRef.current = marker;
        setEditorStage('writing');
        setToolsExpanded(true);
        setHeaderToolsOpen(false);
        setCopilotOpen(false);
        setFocusMode(false);
    }, [articleId, isWriterRole, workId]);

    const showSidePanels = !focusMode;
    const mainSpanClass = showSidePanels ? 'xl:col-span-7' : 'xl:col-span-12';
    const isWritingStage = isWriterRole && editorStage === 'writing';
    const showTechnicalDiagnostics = !isWriterRole || decisionDetailOpen;
    const showInlineResults = toolsExpanded;
    const tutorialStep = tutorialState.step;
    const showEditorEditOverlay = tutorialActive && tutorialState.role === 'journalist' && tutorialStep === 'editor_edit';
    const showEditorSubmitOverlay = tutorialActive && tutorialState.role === 'journalist' && tutorialStep === 'editor_submit';
    const openReportTab = (tab: RightTab) => {
        setToolsExpanded(true);
        setActiveTab(tab);
        setDecisionDetailOpen(true);
        setTimeout(() => {
            reportPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 0);
    };

    const reportPanels = (
        <div ref={reportPanelRef} className="space-y-3">
        {showInlineResults && (
        <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4">
            <div className="flex gap-2 overflow-x-auto pb-1 xl:flex-wrap xl:overflow-visible">
                {visibleTabs.map((t) => (
                    <button key={t.id} onClick={() => setActiveTab(t.id)} className={cn('shrink-0 min-h-9 px-2 py-1 rounded-lg text-[11px]', activeTab === t.id ? 'bg-emerald-500/20 text-emerald-200' : 'bg-white/10 text-gray-300')}>{t.label}</button>
                ))}
            </div>
        </div>
        )}

        {showInlineResults && activeTab === 'evidence' && (
            <Panel title="نتائج التحقق">
                {claims.length ? (
                    <div className="space-y-2">
                        {claims.map((claim) => {
                            const claimId = String(claim?.id || '');
                            const draft = claimOverrideDrafts[claimId] || claimDraftFromClaim(claim);
                            const sourceInfo = classifyClaimSource(claim?.text || '');
                            const sourceStyles = severityStyles(sourceInfo.severity);
                            return (
                                <div
                                    key={claimId}
                                    className={cn(
                                        'rounded-xl border p-2 text-xs space-y-2',
                                        claim?.blocking ? 'border-red-500/30 bg-red-500/10' : 'border-emerald-500/30 bg-emerald-500/10',
                                    )}
                                >
                                    <div className="flex items-start justify-between gap-2">
                                        <p className="text-gray-100 flex-1">{cleanText(claim?.text || '')}</p>
                                        <div className="shrink-0 flex flex-col items-end gap-1">
                                            <span className={cn('rounded px-2 py-0.5 text-[10px]', claim?.blocking ? 'bg-red-500/20 text-red-100' : 'bg-emerald-500/20 text-emerald-100')}>
                                                {Math.round(Number(claim?.confidence || 0) * 100)}% ثقة
                                            </span>
                                            <span className={cn(
                                                'rounded px-2 py-0.5 text-[10px] uppercase',
                                                claim?.risk_level === 'high'
                                                    ? 'bg-red-500/20 text-red-100'
                                                    : claim?.risk_level === 'medium'
                                                        ? 'bg-amber-500/20 text-amber-100'
                                                        : 'bg-cyan-500/20 text-cyan-100',
                                            )}>
                                                {String(claim?.risk_level || 'low')}
                                            </span>
                                        </div>
                                    </div>
                                    <div className={cn('rounded-lg border px-2 py-1 text-[10px]', sourceStyles.border)}>
                                        <div className="flex items-center justify-between gap-2">
                                            <span className={cn('px-2 py-0.5 rounded text-[10px]', sourceStyles.badge)}>
                                                {sourceInfo.label}
                                            </span>
                                            <span className="text-gray-400">تصنيف المصدر</span>
                                        </div>
                                        <p className="text-gray-200 mt-1">{sourceInfo.reason}</p>
                                    </div>
                                    {Array.isArray(claim?.external_matches) && claim.external_matches.length > 0 && (
                                        <div className="rounded-lg border border-cyan-500/20 bg-cyan-500/5 px-2 py-1 text-[10px] space-y-1">
                                            <div className="flex items-center justify-between gap-2">
                                                <span className="text-cyan-200">نتائج Google Fact Check</span>
                                                {claim?.external_verdict && (
                                                    <span className="text-cyan-100">الخلاصة: {externalVerdictLabel(claim.external_verdict)}</span>
                                                )}
                                            </div>
                                            {claim.external_matches.slice(0, 3).map((match, idx) => (
                                                <div key={`match-${claimId}-${idx}`} className="rounded border border-white/10 bg-black/20 px-2 py-1">
                                                    <a
                                                        href={match.url || '#'}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        className="text-cyan-200 underline decoration-dotted"
                                                    >
                                                        {cleanText(match.title || match.claim || 'تدقيق خارجي')}
                                                    </a>
                                                    <p className="text-gray-400 mt-0.5">
                                                        {cleanText(match.publisher || '')}
                                                        {match.rating ? ` • ${cleanText(match.rating)}` : ''}
                                                    </p>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                    <textarea
                                        value={draft.evidenceLinksRaw}
                                        onChange={(e) => setClaimOverrideDraftField(claimId, { evidenceLinksRaw: e.target.value })}
                                        placeholder="روابط الأدلة أو مراجع DocIntel (سطر لكل مرجع أو مفصولة بفاصلة)"
                                        className="w-full min-h-14 rounded-lg bg-black/20 border border-white/15 px-2 py-1 text-[11px] text-gray-100 placeholder:text-gray-500"
                                    />
                                    {sources.length > 0 && (
                                        <div className="flex flex-wrap gap-1">
                                            {sources.slice(0, 6).map((source) => (
                                                <button
                                                    key={`claim-source-${claimId}-${source.id}`}
                                                    onClick={() =>
                                                        setClaimOverrideDraftField(claimId, {
                                                            evidenceLinksRaw: appendEvidenceLink(
                                                                draft.evidenceLinksRaw,
                                                                source.url || source.name,
                                                            ),
                                                        })
                                                    }
                                                    className="px-2 py-0.5 rounded bg-white/10 text-[10px] text-gray-200"
                                                >
                                                    {cleanText(source.name || source.url)}
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                    <label className="flex items-center gap-2 text-[11px] text-gray-200">
                                        <input
                                            type="checkbox"
                                            checked={Boolean(draft.unverifiable)}
                                            onChange={(e) => setClaimOverrideDraftField(claimId, { unverifiable: e.target.checked })}
                                        />
                                        تعليم الادعاء كغير قابل للتحقق مع سبب
                                    </label>
                                    {draft.unverifiable && (
                                        <input
                                            value={draft.unverifiableReason}
                                            onChange={(e) => setClaimOverrideDraftField(claimId, { unverifiableReason: e.target.value })}
                                            placeholder="سبب عدم إمكانية التحقق"
                                            className="w-full rounded-lg bg-black/20 border border-white/15 px-2 py-1 text-[11px] text-gray-100 placeholder:text-gray-500"
                                        />
                                    )}
                                </div>
                            );
                        })}
                        <p className="text-[11px] text-gray-400">
                            عند الضغط على «تحقق»، يتم إرسال روابط الأدلة/حالات عدم التحقق الحالية لبوابة الجودة.
                        </p>
                    </div>
                ) : <Empty text="اضغط زر «تحقق» لعرض الادعاءات." />}
            </Panel>
        )}

        {showInlineResults && activeTab === 'proofread' && (
            <Panel title="نتائج التدقيق اللغوي">
                {proofread ? (
                    <div className="space-y-2 text-xs text-gray-200">
                        <div className="rounded-xl border border-lime-500/30 bg-lime-500/10 p-2 text-lime-100">
                            <p>العنوان المقترح: {cleanText(proofread?.title || title || 'بدون عنوان')}</p>
                            <p>التعديل: +{proofread?.diff_stats?.added || 0} / -{proofread?.diff_stats?.removed || 0}</p>
                        </div>
                        <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                            <p className="text-gray-400 mb-1">قبل التدقيق</p>
                            <p className="text-gray-200 whitespace-pre-wrap max-h-40 overflow-auto">
                                {cleanText(proofread?.preview?.before_text || htmlToReadableText(bodyHtml))}
                            </p>
                        </div>
                        <div className="rounded-xl border border-lime-500/30 bg-lime-500/10 p-2">
                            <p className="text-lime-100 mb-1">بعد التدقيق</p>
                            <p className="text-lime-50 whitespace-pre-wrap max-h-40 overflow-auto">
                                {cleanText(proofread?.preview?.after_text || proofread?.body_text || htmlToReadableText(proofread?.body_html || ''))}
                            </p>
                        </div>
                        <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-gray-300">
                            <p className="text-gray-400 mb-1">ملاحظات التدقيق</p>
                            {(proofread?.issues || []).length ? (
                                (proofread.issues || []).slice(0, 12).map((issue: any, idx: number) => (
                                    <p key={`${issue?.kind || 'issue'}-${idx}`}>
                                        - [{cleanText(issue?.kind || 'language')}] {cleanText(issue?.message || '')}
                                    </p>
                                ))
                            ) : (
                                <p>لا توجد ملاحظات إضافية.</p>
                            )}
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <button
                                onClick={() => applyProofread.mutate()}
                                disabled={applyProofread.isPending}
                                className="px-3 py-2 rounded-xl bg-emerald-500/30 text-emerald-100 text-xs disabled:opacity-60"
                            >
                                {applyProofread.isPending ? 'جاري التطبيق...' : 'تطبيق كنسخة جديدة'}
                            </button>
                            <button
                                onClick={() => setProofread(null)}
                                className="px-3 py-2 rounded-xl bg-white/10 text-gray-300 text-xs"
                            >
                                تجاهل
                            </button>
                        </div>
                    </div>
                ) : <Empty text="اضغط زر «تدقيق لغوي» لعرض التصحيحات." />}
            </Panel>
        )}

        {showInlineResults && activeTab === 'quality' && (
            <Panel title="تقييم الجودة">
                {quality ? (
                    <div className="space-y-2 text-xs text-gray-200">
                        <div className="rounded-xl border border-white/10 bg-white/5 p-2">الدرجة الكلية: <span className="font-semibold">{quality.score ?? '-'}/100</span></div>
                        {Object.entries(quality.metrics || {}).map(([k, v]) => (
                            <div key={k} className="flex items-center justify-between rounded-lg bg-black/20 px-2 py-1 text-gray-300"><span>{METRIC_LABELS[k] || k}</span><span>{String(v)}</span></div>
                        ))}
                        {!!quality.actionable_fixes?.length && <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 p-2 text-amber-100">{quality.actionable_fixes.map((f: string, i: number) => <p key={`${f}-${i}`}>- {cleanText(f)}</p>)}</div>}
                    </div>
                ) : <Empty text="اضغط زر «جودة» للحصول على التقرير." />}
                {readiness && (
                    <div className="mt-2 space-y-2 text-xs">
                        <div className={cn('rounded-xl border p-2', readiness.ready_for_publish ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100' : 'border-amber-500/30 bg-amber-500/10 text-amber-100')}>
                            {readiness.ready_for_publish ? 'جاهزية ممتازة للنشر بعد المراجعة البشرية.' : 'التقييمات تحتاج تحسين، لكنها لا توقف كتابة الصحفي.'}
                        </div>
                        {!readiness.ready_for_publish && (
                            <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-2 text-amber-100 space-y-1">
                                {explainedBlockers.length === 0
                                    ? <p className="text-[11px]">لا توجد تفاصيل إضافية بعد.</p>
                                    : explainedBlockers.map((item, i) => (
                                        <div key={`ready-${i}`} className="text-[11px]">
                                            <span className="font-semibold">{item.title}</span>
                                            <span className="text-amber-100/80"> — {item.detail}</span>
                                        </div>
                                    ))}
                            </div>
                        )}
                        {showTechnicalDiagnostics ? (
                            <>
                                <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-gray-300 space-y-1">
                                    {Object.entries(readiness.reports || {}).map(([stage, report]) => (
                                        <div key={stage} className="flex items-center justify-between gap-2">
                                            <span>{STAGE_LABELS[stage] || stage}</span>
                                            <div className="flex items-center gap-2">
                                                <span className={report?.passed ? 'text-emerald-300' : 'text-red-300'}>{report?.passed ? 'ناجح' : 'فشل'}</span>
                                                {!report?.passed && STAGE_ACTIONS[stage] && (
                                                    <button
                                                        onClick={() => decisionActionHandlers[STAGE_ACTIONS[stage] as DecisionActionId]()}
                                                        className="px-2 py-0.5 rounded bg-white/10 text-[10px] text-gray-200"
                                                    >
                                                        فتح
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                                {!!readiness.gates && (
                                    <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-gray-200 space-y-2">
                                        <p className="text-[11px] text-gray-400">
                                            Gate Severities: blocker={readiness.gates.counts?.blocker || 0} · warn={readiness.gates.counts?.warn || 0} · info={readiness.gates.counts?.info || 0}
                                        </p>
                                        {([
                                            { key: 'blocker', label: 'Blockers', style: 'border-red-500/30 bg-red-500/10 text-red-100' },
                                            { key: 'warn', label: 'Warnings', style: 'border-amber-500/30 bg-amber-500/10 text-amber-100' },
                                            { key: 'info', label: 'Info', style: 'border-cyan-500/30 bg-cyan-500/10 text-cyan-100' },
                                        ] as const).map((group) => {
                                            const groupItems = (readiness.gates.items || []).filter((item) => item.severity === group.key);
                                            if (groupItems.length === 0) return null;
                                            return (
                                                <div key={group.key} className="space-y-1">
                                                    <p className="text-[11px] uppercase tracking-wide text-gray-400">{group.label}</p>
                                                    {groupItems.map((item, idx) => (
                                                        <div
                                                            key={`${group.key}-${item.code}-${idx}`}
                                                            className={cn('rounded-lg border px-2 py-1', group.style)}
                                                        >
                                                            <p>{cleanText(item.message || '')}</p>
                                                        </div>
                                                    ))}
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-[11px] text-slate-300">
                                تفاصيل التقرير التقني مخفية لتقليل التشويش. يمكنك إظهارها من زر «عرض التفاصيل».
                            </div>
                        )}
                    </div>
                )}
            </Panel>
        )}

        {showInlineResults && activeTab === 'seo' && (
            <Panel title="نتائج SEO">
                {seoPack ? (
                    <div className="space-y-2 text-xs text-gray-200">
                        <InfoBlock label="عنوان SEO" value={seoPack.seo_title} />
                        <InfoBlock label="الوصف التعريفي" value={seoPack.meta_description} />
                        <InfoBlock label="العبارة المفتاحية الرئيسية" value={seoPack.focus_keyphrase} />
                        <InfoBlock label="عبارات مفتاحية ثانوية" value={(seoPack.secondary_keyphrases || []).join('، ')} />
                        <InfoBlock label="الكلمات المفتاحية" value={(seoPack.keywords || []).join('، ')} />
                        <InfoBlock label="الوسوم" value={(seoPack.tags || []).join('، ')} />
                        <InfoBlock label="Slug" value={seoPack.slug} />
                        <InfoBlock label="OG Title" value={seoPack.og_title} />
                        <InfoBlock label="OG Description" value={seoPack.og_description} />
                        <InfoBlock label="Twitter Title" value={seoPack.twitter_title} />
                        <InfoBlock label="Twitter Description" value={seoPack.twitter_description} />
                        <div className={cn(
                            'rounded-lg border p-2 text-[11px]',
                            seoPack?.yoast?.meta_ok && seoPack?.yoast?.title_ok
                                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-100'
                                : 'border-amber-500/30 bg-amber-500/10 text-amber-100'
                        )}>
                            <p>جاهزية Yoast:</p>
                            <p>- طول Meta: {seoPack?.yoast?.meta_length ?? 0} (المطلوب 140-155)</p>
                            <p>- طول SEO Title: {seoPack?.yoast?.title_length ?? 0} (الموصى به 40-60)</p>
                        </div>
                    </div>
                ) : <Empty text="اضغط زر «SEO» لاستخراج المقترحات." />}
                <div className="mt-3 rounded-xl border border-teal-500/30 bg-teal-500/10 p-2 space-y-2 text-xs text-teal-100">
                    <p className="font-semibold">Link Intelligence (داخلي + خارجي)</p>
                    <div className="flex flex-wrap items-center gap-2">
                        <select
                            value={linkMode}
                            onChange={(e) => setLinkMode(e.target.value as 'internal' | 'external' | 'mixed')}
                            className="rounded-lg bg-black/30 border border-white/20 px-2 py-1 text-xs text-white"
                        >
                            <option value="mixed">مختلط</option>
                            <option value="internal">داخلي فقط</option>
                            <option value="external">خارجي فقط</option>
                        </select>
                        <button
                            onClick={() => runLinks.mutate()}
                            disabled={runLinks.isPending}
                            className="px-2 py-1 rounded-lg bg-teal-500/30 border border-teal-400/40 text-teal-50 disabled:opacity-50"
                        >
                            {runLinks.isPending ? 'جاري التوليد...' : 'توليد روابط'}
                        </button>
                        <button
                            onClick={() => validateLinks.mutate()}
                            disabled={!linkRunId || validateLinks.isPending}
                            className="px-2 py-1 rounded-lg bg-white/10 border border-white/20 text-gray-200 disabled:opacity-50"
                        >
                            فحص الروابط
                        </button>
                        <button
                            onClick={() => applyLinks.mutate()}
                            disabled={!linkRunId || applyLinks.isPending || !linkSuggestions.length}
                            className="px-2 py-1 rounded-lg bg-emerald-500/30 border border-emerald-400/40 text-emerald-50 disabled:opacity-50"
                        >
                            تطبيق المحدد
                        </button>
                    </div>
                    {linkRunId ? <p className="text-[11px] text-teal-50/80">Run ID: {linkRunId}</p> : null}

                    {!!linkSuggestions.length && (
                        <div className="space-y-1 max-h-64 overflow-auto">
                            {linkSuggestions.map((item: any) => (
                                <label key={`lnk-${item.id}`} className="block rounded-lg border border-white/15 bg-black/20 p-2 cursor-pointer">
                                    <div className="flex items-start gap-2">
                                        <input
                                            type="checkbox"
                                            checked={item.selected !== false}
                                            onChange={(e) =>
                                                setLinkSuggestions((prev) =>
                                                    prev.map((x: any) =>
                                                        x.id === item.id ? { ...x, selected: e.target.checked } : x
                                                    )
                                                )
                                            }
                                        />
                                        <div className="min-w-0 flex-1">
                                            <p className="text-teal-100 line-clamp-1">{cleanText(item.title || '')}</p>
                                            <p className="text-gray-300 line-clamp-1">{cleanText(item.anchor_text || '')}</p>
                                            <p className="text-[11px] text-gray-400 line-clamp-1">{item.url}</p>
                                            <p className="text-[11px] text-gray-400">
                                                {item.link_type === 'external' ? 'خارجي' : 'داخلي'} •
                                                Score {Number(item.score || 0).toFixed(2)} •
                                                ثقة {Math.round(Number(item.confidence || 0) * 100)}%
                                            </p>
                                        </div>
                                    </div>
                                </label>
                            ))}
                        </div>
                    )}

                    {!!linkHistory.length && (
                        <div className="rounded-lg border border-white/10 bg-black/20 p-2">
                            <p className="text-gray-300 mb-1">آخر تشغيلات الروابط</p>
                            {(linkHistory || []).slice(0, 3).map((run: any) => (
                                <p key={`hist-${run.run_id}`} className="text-[11px] text-gray-400">
                                    {run.mode} • {run.status} • {run.run_id}
                                </p>
                            ))}
                        </div>
                    )}
                </div>
                {!!headlineInsights.length && (
                    <div className="mt-2 rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-200 space-y-2">
                        <p className="text-gray-400 mb-1">تحليل العناوين (وضوح + SEO)</p>
                        {headlineInsights.map((item, idx) => (
                            <div key={`headline-${idx}-${item.headline}`} className="rounded-lg border border-white/10 bg-black/20 p-2 space-y-1">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-gray-200 line-clamp-2">{cleanText(item.headline || '')}</p>
                                    <span className={cn('px-2 py-0.5 rounded text-[10px]', item.score >= 80 ? 'bg-emerald-500/20 text-emerald-100' : item.score >= 65 ? 'bg-amber-500/20 text-amber-100' : 'bg-rose-500/20 text-rose-100')}>
                                        {item.score}/100
                                    </span>
                                </div>
                                {!!item.reasons?.length && <p className="text-[10px] text-emerald-200">أسباب القوة: {item.reasons.slice(0, 2).join(' • ')}</p>}
                                {!!item.risks?.length && <p className="text-[10px] text-amber-200">مخاطر: {item.risks.slice(0, 2).join(' • ')}</p>}
                            </div>
                        ))}
                    </div>
                )}
            </Panel>
        )}

        {showInlineResults && activeTab === 'social' && (
            <Panel title="نسخ السوشيال">
                {social ? (
                    <div className="space-y-2 text-xs text-gray-200">
                        <InfoBlock label="فيسبوك" value={social.facebook} />
                        <InfoBlock label="X" value={social.x} />
                        <InfoBlock label="Push" value={social.push} />
                        <InfoBlock label="ملخص 120 كلمة" value={social.summary_120} />
                        <InfoBlock label="تنبيه عاجل" value={social.breaking_alert} />
                    </div>
                ) : <Empty text="اضغط زر «سوشيال» لإنشاء النسخ." />}
            </Panel>
        )}

        {showInlineResults && activeTab === 'msi' && (
            <Panel title="MSI السياقي">
                {msiContextHit ? (
                    <div className={cn('rounded-xl border p-2 text-xs', Number(msiContextHit.msi || 100) < 60 ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-amber-500/30 bg-amber-500/10 text-amber-100')}>
                        <p className="font-semibold mb-1">تنبيه سياقي مرتبط بالكيان: {cleanText(msiContextHit.entity || '')}</p>
                        <p>المؤشر الحالي: {Number(msiContextHit.msi || 0).toFixed(1)} / 100</p>
                        <p>التصنيف: {cleanText(msiContextHit.level || '-')}</p>
                        <p className="mt-1 text-[11px] opacity-90">عند انخفاض المؤشر، شدّد على التحقق من الادعاءات والمصادر قبل الإرسال النهائي.</p>
                    </div>
                ) : (
                    <Empty text="لا يوجد تطابق MSI مباشر مع موضوع المسودة الحالية." />
                )}
                <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-300 mt-2 space-y-1">
                    <p className="text-gray-400 mb-1">الأكثر اضطراباً اليوم</p>
                    {(msiTopDaily || []).slice(0, 5).map((item: any) => (
                        <div key={`msi-d-${item.profile_id}-${item.entity}-${item.period_end}`} className="flex items-center justify-between">
                            <span className="line-clamp-1">{cleanText(item.entity || '-')}</span>
                            <span className="text-red-300">{Number(item.msi || 0).toFixed(1)}</span>
                        </div>
                    ))}
                </div>
                <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-300 space-y-1">
                    <p className="text-gray-400 mb-1">الأكثر اضطراباً أسبوعياً</p>
                    {(msiTopWeekly || []).slice(0, 5).map((item: any) => (
                        <div key={`msi-w-${item.profile_id}-${item.entity}-${item.period_end}`} className="flex items-center justify-between">
                            <span className="line-clamp-1">{cleanText(item.entity || '-')}</span>
                            <span className="text-orange-300">{Number(item.msi || 0).toFixed(1)}</span>
                        </div>
                    ))}
                </div>
            </Panel>
        )}

        {showInlineResults && activeTab === 'simulator' && (
            <Panel title="محاكي الجمهور">
                {simResult ? (
                    <div className="space-y-2 text-xs text-gray-200">
                        <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                            <p>مخاطر المحتوى: <span className="font-semibold text-red-200">{Number(simResult.risk_score || 0).toFixed(1)}/10</span></p>
                            <p>قابلية الانتشار: <span className="font-semibold text-cyan-200">{Number(simResult.virality_score || 0).toFixed(1)}/10</span></p>
                            <p>تصنيف الحوكمة: <span className="font-semibold text-amber-200">{cleanText(simResult.policy_level || '-')}</span></p>
                            <p>موثوقية القياس: <span className="font-semibold text-gray-100">{Number(simResult.confidence_score || 0).toFixed(1)}%</span></p>
                        </div>
                        <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                            <p className="text-gray-400 mb-1">ردود الشخصيات</p>
                            {(simResult.reactions || []).map((rx: any, idx: number) => (
                                <p key={`${rx.persona_id || 'persona'}-${idx}`}>
                                    - {cleanText(rx.persona_label || rx.persona_id || 'شخصية')}: {cleanText(rx.comment || '')}
                                </p>
                            ))}
                        </div>
                        <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                            <p className="text-gray-400 mb-1">نصائح التحرير</p>
                            <p>{cleanText(simResult?.advice?.summary || '') || '—'}</p>
                            {(simResult?.advice?.improvements || []).map((fix: string, idx: number) => (
                                <p key={`${fix}-${idx}`}>- {cleanText(fix)}</p>
                            ))}
                        </div>
                    </div>
                ) : (
                    <Empty text="اضغط زر «محاكي الجمهور» لتقييم العنوان قبل الاعتماد." />
                )}
            </Panel>
        )}

        {showInlineResults && activeTab === 'xray' && (
            <Panel title="زوايا المنافسين">
                {xrayItems.length ? (
                    <div className="space-y-2 text-xs text-gray-200">
                        {xrayItems.slice(0, 6).map((item: any) => (
                            <div key={`xray-${item.id}`} className="rounded-xl border border-white/10 bg-black/20 p-2">
                                <a href={item.competitor_url} target="_blank" rel="noreferrer" className="text-cyan-300 hover:underline line-clamp-1">
                                    {cleanText(item.competitor_title || '')}
                                </a>
                                <p className="text-[11px] text-amber-200 mt-1">أولوية {Number(item.priority_score || 0).toFixed(1)}</p>
                                {item.angle_title ? <p className="text-emerald-200 mt-1">{cleanText(item.angle_title)}</p> : null}
                                {item.angle_rationale ? <p className="text-gray-300 mt-1 line-clamp-3">{cleanText(item.angle_rationale)}</p> : null}
                                {(item.angle_questions_json || []).slice(0, 3).map((qText: string, idx: number) => (
                                    <p key={`${item.id}-q-${idx}`} className="text-gray-200">- {cleanText(qText)}</p>
                                ))}
                                <div className="flex flex-wrap gap-2 mt-2">
                                    <button
                                        onClick={() => xrayBriefMutation.mutate(item.id)}
                                        className="px-2 py-1 rounded bg-cyan-500/20 border border-cyan-500/30 text-cyan-200"
                                    >
                                        توليد Brief
                                    </button>
                                    <button
                                        onClick={() => xrayMarkUsed.mutate(item.id)}
                                        className="px-2 py-1 rounded bg-emerald-500/20 border border-emerald-500/30 text-emerald-200"
                                    >
                                        تم الاستخدام
                                    </button>
                                </div>
                            </div>
                        ))}
                        {xrayBrief ? (
                            <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-2 text-cyan-100 space-y-1">
                                <p className="font-semibold">{cleanText(xrayBrief.title || 'Brief')}</p>
                                <p>{cleanText(xrayBrief.counter_angle || '')}</p>
                                <p className="text-cyan-200">{cleanText(xrayBrief.why_it_wins || '')}</p>
                                {(xrayBrief.newsroom_plan || []).slice(0, 4).map((step: string, idx: number) => (
                                    <p key={`${step}-${idx}`}>- {cleanText(step)}</p>
                                ))}
                            </div>
                        ) : null}
                    </div>
                ) : (
                    <Empty text="لا توجد فجوات منافسين مرتبطة مباشرة بموضوع المسودة الحالية." />
                )}
            </Panel>
        )}

        {showInlineResults && activeTab === 'context' && (
            <Panel title="السياق والنسخ">
                <div className="space-y-1 max-h-32 overflow-auto">
                    {versions.map((v) => <button key={v.id} onClick={() => restoreVersion.mutate(v.version)} className="w-full text-right rounded bg-white/5 px-2 py-1 text-xs text-gray-200">الإصدار v{v.version} • {v.change_origin || 'يدوي'}</button>)}
                </div>
                <div className="flex gap-2 mt-2">
                    <select value={cmpFrom || ''} onChange={(e) => setCmpFrom(Number(e.target.value))} className="flex-1 bg-white/10 rounded px-2 py-1 text-xs">{versions.map((v) => <option key={`f-${v.id}`} value={v.version}>من v{v.version}</option>)}</select>
                    <select value={cmpTo || ''} onChange={(e) => setCmpTo(Number(e.target.value))} className="flex-1 bg-white/10 rounded px-2 py-1 text-xs">{versions.map((v) => <option key={`t-${v.id}`} value={v.version}>إلى v{v.version}</option>)}</select>
                    <button onClick={() => runDiff.mutate()} className="px-2 py-1 rounded bg-white/10 text-xs">فرق</button>
                </div>
                <pre className="max-h-36 overflow-auto text-[11px] text-gray-200 whitespace-pre-wrap mt-2" dir="ltr">{diffView || 'لا يوجد فرق معروض بعد.'}</pre>
                <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-300">
                    <p className="text-gray-400 mb-1">الخط الزمني المرتبط</p>
                    {storyTimelineSorted.slice(0, 5).map((item: any) => (
                        <p key={item.id}>- {cleanText(item.title || 'بدون عنوان')}</p>
                    ))}
                </div>
                <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-2 text-xs text-cyan-100 space-y-1">
                    <p className="text-cyan-200">تلميحات الدستور أثناء التحرير</p>
                    {(constitutionTips || []).slice(0, 4).map((tip: string, idx: number) => (
                        <p key={`${tip}-${idx}`}>- {cleanText(tip)}</p>
                    ))}
                </div>
            </Panel>
        )}
        </div>
    );

    useEffect(() => {
        if (leftTab !== 'archive') return;
        if (archiveQuery.trim().length > 1) return;
        const seed = cleanText(title || context?.article?.original_title || '');
        if (seed.length > 2) setArchiveQuery(seed.slice(0, 80));
    }, [leftTab, archiveQuery, title, context?.article?.original_title]);

    useEffect(() => {
        if (archiveQuery.trim().length >= 2) return;
        if (archiveItems.length) setArchiveItems([]);
    }, [archiveQuery, archiveItems.length]);

    const paletteItems = useMemo(() => {
        const items = [
            {
                id: 'quick_check',
                label: 'فحص سريع',
                keywords: ['check', 'speed'],
                run: () => runWithGuide('quick_check', () => runQuickCheck.mutate()),
            },
            {
                id: 'verify',
                label: 'تحقق الادعاءات',
                keywords: ['claims', 'verify'],
                run: () => runWithGuide('verify', () => runVerifier.mutate()),
            },
            {
                id: 'quality',
                label: 'تقييم الجودة',
                keywords: ['quality', 'score'],
                run: () => runWithGuide('quality', () => runQuality.mutate()),
            },
            {
                id: 'proofread',
                label: 'تدقيق لغوي',
                keywords: ['language', 'proofread'],
                run: () => runWithGuide('proofread', () => runProofread.mutate()),
            },
            {
                id: 'headlines',
                label: 'اقتراح عناوين',
                keywords: ['headline'],
                run: () => runWithGuide('headlines', () => runHeadlines.mutate()),
            },
            {
                id: 'seo',
                label: 'تحليل SEO',
                keywords: ['seo'],
                run: () => runWithGuide('seo', () => runSeo.mutate()),
            },
            {
                id: 'links',
                label: 'اقتراح روابط',
                keywords: ['links'],
                run: () => runWithGuide('links', () => runLinks.mutate()),
            },
            {
                id: 'social',
                label: 'نسخ السوشيال',
                keywords: ['social'],
                run: () => runWithGuide('social', () => runSocial.mutate()),
            },
            {
                id: 'toggle_focus',
                label: focusMode ? 'إلغاء وضع التركيز' : 'وضع التركيز',
                keywords: ['focus'],
                run: () => setFocusMode((prev) => !prev),
            },
            {
                id: 'toggle_highlight',
                label: smartHighlightEnabled ? 'إيقاف التظليل الذكي' : 'تشغيل التظليل الذكي',
                keywords: ['highlight'],
                run: () => setSmartHighlightEnabled((prev) => !prev),
            },
            {
                id: 'open_archive',
                label: 'فتح الأرشيف',
                keywords: ['archive'],
                run: () => { setLeftTab('archive'); },
            },
            {
                id: 'open_drafts',
                label: 'عرض المسودات',
                keywords: ['drafts'],
                run: () => { setLeftTab('drafts'); },
            },
            {
                id: 'compare_versions',
                label: 'مقارنة النسخ',
                keywords: ['diff', 'versions'],
                run: () => setDiffOpen(true),
            },
            {
                id: 'submit_with_reservations',
                label: 'إرسال بتحفّظ',
                keywords: ['override', 'reservations'],
                run: () => setOverrideOpen(true),
            },
            {
                id: 'new_draft',
                label: 'مسودة جديدة',
                keywords: ['new'],
                run: () => setNewDraftOpen(true),
            },
        ];
        return items;
    }, [
        focusMode,
        smartHighlightEnabled,
        runQuickCheck,
        runVerifier,
        runQuality,
        runProofread,
        runHeadlines,
        runSeo,
        runLinks,
        runSocial,
        runAudienceSimulation,
    ]);

    const filteredPaletteItems = useMemo(() => {
        const q = cleanText(paletteQuery || '').toLowerCase();
        if (!q) return paletteItems;
        return paletteItems.filter((item) => {
            if (item.label.toLowerCase().includes(q)) return true;
            return (item.keywords || []).some((k) => k.toLowerCase().includes(q));
        });
    }, [paletteItems, paletteQuery]);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                setPaletteOpen(true);
                setPaletteQuery('');
                setPaletteIndex(0);
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, []);

    useEffect(() => {
        if (paletteIndex >= filteredPaletteItems.length) setPaletteIndex(0);
    }, [filteredPaletteItems.length, paletteIndex]);

    useEffect(() => {
        if (!paletteOpen) return;
        paletteInputRef.current?.focus();
        const handler = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                setPaletteOpen(false);
                return;
            }
            if (!filteredPaletteItems.length) return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setPaletteIndex((prev) => Math.min(prev + 1, filteredPaletteItems.length - 1));
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                setPaletteIndex((prev) => Math.max(prev - 1, 0));
                return;
            }
            if (e.key === 'Enter') {
                e.preventDefault();
                const item = filteredPaletteItems[paletteIndex];
                if (item) {
                    item.run();
                    setPaletteOpen(false);
                }
            }
        };
        window.addEventListener('keydown', handler);
        return () => window.removeEventListener('keydown', handler);
    }, [paletteOpen, filteredPaletteItems, paletteIndex]);

    const saveNode = useMemo(() => {
        if (saveState === 'saved') return <span className="text-emerald-300 flex items-center gap-1"><CheckCircle2 className="w-4 h-4" />محفوظ</span>;
        if (saveState === 'saving') return <span className="text-sky-300 flex items-center gap-1"><Loader2 className="w-4 h-4 animate-spin" />جاري الحفظ...</span>;
        if (saveState === 'unsaved') return <span className="text-amber-300 flex items-center gap-1"><Clock3 className="w-4 h-4" />غير محفوظ</span>;
        return <span className="text-red-300 flex items-center gap-1"><AlertTriangle className="w-4 h-4" />خطأ في الحفظ</span>;
    }, [saveState]);

    function insertArchiveItem(item: ArchiveSearchItem) {
        if (!editor) return;
        const dateLabel = item.published_at ? new Date(item.published_at).toLocaleDateString('ar-DZ') : '';
        const titleLine = cleanText(item.title || 'بدون عنوان');
        const urlLine = cleanText(item.url || '');
        const label = dateLabel ? `${titleLine} (${dateLabel})` : titleLine;
        const html = `<p>مصدر من الأرشيف: ${label}</p>${urlLine ? `<p>${urlLine}</p>` : ''}`;
        editor.chain().focus().insertContent(html).run();
        setSaveState('unsaved');
    }

    function insertStorySummary(item: StoryContextItem) {
        if (!editor) return;
        const titleLine = cleanText(item.title || 'عنصر مرتبط');
        const summaryLine = cleanText(item.summary || '');
        const sourceLine = cleanText(item.source_name || '');
        const dateValue = item.published_at || item.created_at || '';
        const dateLabel = dateValue ? new Date(dateValue).toLocaleDateString('ar-DZ') : '';
        const meta = [sourceLine, dateLabel].filter(Boolean).join(' • ');
        const html = `<p><strong>${titleLine}</strong></p>${summaryLine ? `<p>${summaryLine}</p>` : ''}${meta ? `<p>${meta}</p>` : ''}`;
        editor.chain().focus().insertContent(html).run();
        setSaveState('unsaved');
    }

    function insertStoryTemplate() {
        if (!editor) return;
        const html = STORY_TEMPLATE_SECTIONS
            .map((section) => `<h2>${section.title}</h2><p>${section.hint}</p>`)
            .join('');
        editor.chain().focus().insertContent(html).run();
        setSaveState('unsaved');
    }

    function insertStoryStarterPack() {
        if (!editor) return;
        insertStoryTemplate();
        storyTopSources.slice(0, 2).forEach((item) => insertStorySummary(item));
        if (autoTimelineLines.length > 0) {
            insertAutoTimeline();
        }
        setOk('تم إدراج باقة القصة (قالب + أهم المصادر + تسلسل زمني).');
    }

    function insertAutoTimeline() {
        if (!editor) return;
        if (autoTimelineLines.length === 0) {
            setErr('لا يوجد خط زمني كافٍ للإدراج.');
            return;
        }
        const html = `<h2>التسلسل الزمني</h2><ul>${autoTimelineLines
            .map((line) => `<li>${safeInlineText(line)}</li>`)
            .join('')}</ul>`;
        editor.chain().focus().insertContent(html).run();
        setSaveState('unsaved');
        setOk('تم إدراج التسلسل الزمني في المسودة.');
    }

    async function openStoryInEditor(item: StoryContextItem) {
        if (!item?.id) return;
        try {
            const res = await editorialApi.handoff(item.id);
            const workId = res?.data?.work_id;
            const target = workId
                ? `/workspace-drafts?article_id=${item.id}&work_id=${workId}`
                : `/workspace-drafts?article_id=${item.id}`;
            if (typeof window !== 'undefined') {
                window.open(target, '_blank');
            }
            setOk('تم فتح خبر القصة في تبويب جديد.');
            setErr(null);
        } catch {
            setErr('تعذر فتح خبر القصة في المحرر.');
        }
    }

    const storyQuickActions = useMemo(() => {
        return storyGaps.slice(0, 3).map((gap) => {
            let actionLabel = 'معالجة';
            let handler: () => void = () => setStoryOpen(false);
            if (gap.action && decisionActionHandlers[gap.action]) {
                const runner = decisionActionHandlers[gap.action];
                actionLabel = ACTION_SOURCE_LABELS[gap.action] || 'تشغيل';
                handler = () => {
                    runner();
                    setStoryOpen(false);
                };
            } else {
                const task = mapGapToStoryTask(gap.title, gap.hint, gap.id);
                actionLabel = storyTaskLabel(task);
                if (task === 'source') {
                    handler = () => {
                        setLeftTab('archive');
                        setStoryOpen(false);
                    };
                } else if (task === 'background') {
                    handler = () => {
                        insertAutoTimeline();
                        setStoryOpen(false);
                    };
                } else {
                    handler = () => {
                        createStoryDraft.mutate(task);
                    };
                }
            }
            return { ...gap, actionLabel, handler };
        });
    }, [storyGaps, decisionActionHandlers, createStoryDraft, setStoryOpen, setLeftTab, insertAutoTimeline]);

    const nextBestAction = useMemo(() => {
        if (storyQuickActions.length > 0) return storyQuickActions[0];
        return {
            id: 'story_pack',
            title: 'ابدأ من باقة القصة',
            hint: 'أدرج القالب والخلفية والتسلسل الزمني مباشرة في المسودة.',
            severity: 'low' as DecisionSeverity,
            actionLabel: 'إدراج الباقة',
            handler: () => {
                insertStoryStarterPack();
                setStoryOpen(false);
            },
        };
    }, [storyQuickActions, insertStoryStarterPack, setStoryOpen]);

    function handleInlineAiAction(action: 'rewrite' | 'shorten' | 'expand' | 'clarify') {
        setInlineAiError(null);
        if (!editor || !workId) {
            setInlineAiError('المحرر غير جاهز الآن.');
            return;
        }
        const { from, to } = editor.state.selection;
        if (from === to) {
            setInlineAiError('حدد جزءاً من النص أولاً.');
            return;
        }
        const selectedText = editor.state.doc.textBetween(from, to, ' ');
        if (!selectedText.trim()) {
            setInlineAiError('لا يوجد نص واضح داخل التحديد.');
            return;
        }
        runInlineAi.mutate({ action, text: selectedText, from, to });
    }

    function insertSourceInline(source: Source) {
        if (!editor) return;
        const label = cleanText(source.name || source.url || 'مصدر');
        const html = source.url
            ? ` <a href="${source.url}" target="_blank" rel="noreferrer">المصدر: ${label}</a>`
            : ` (المصدر: ${label})`;
        const { to } = editor.state.selection;
        editor.chain().focus().insertContentAt(to, html).run();
        setInlineSourceOpen(false);
        setSaveState('unsaved');
    }

    function enterReviewStage() {
        setEditorStage('review');
        setToolsExpanded(true);
        setHeaderToolsOpen(false);
        setCopilotOpen(false);
        setFocusMode(false);
    }

    function returnToWritingStage() {
        setEditorStage('writing');
        setToolsExpanded(true);
        setHeaderToolsOpen(false);
        setCopilotOpen(false);
        setFocusMode(false);
    }

    function runWithGuide(_action: ActionId, callback: () => void) {
        setErr(null);
        setOk(null);
        callback();
    }

    if (listLoading) return <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 text-center text-gray-300">جاري تحميل المسودات...</div>;
    if (!drafts.length) {
        return (
            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 space-y-4" dir="rtl">
                <h2 className="text-lg text-white font-semibold">لا توجد مسودة جاهزة الآن</h2>
                <p className="text-sm text-gray-300">
                    {articleNumericId
                        ? 'هذا الخبر لا يملك مسودة بعد. يمكنك إنشاء مسودة فورية من الخبر الحالي.'
                        : 'ابدأ بإنشاء مسودة جديدة لموضوعك أو افتح خبرًا من صفحة الأخبار.'}
                </p>
                <div className="flex flex-wrap gap-2">
                    {articleNumericId && (
                        <button
                            onClick={() => createDraftFromArticle.mutate()}
                            disabled={createDraftFromArticle.isPending}
                            className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-200 disabled:opacity-60"
                        >
                            {createDraftFromArticle.isPending ? 'جاري إنشاء المسودة...' : 'إنشاء مسودة من الخبر'}
                        </button>
                    )}
                    <button
                        onClick={() => setNewDraftOpen(true)}
                        className="rounded-xl border border-cyan-400/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-200"
                    >
                        إنشاء مسودة موضوع خاص
                    </button>
                    <NextLink
                        href="/news"
                        className="rounded-xl border border-white/20 bg-white/5 px-4 py-2 text-sm text-gray-200 hover:text-white"
                    >
                        العودة إلى الأخبار
                    </NextLink>
                </div>
                {err && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{err}</div>}
                {newDraftOpen && (
                    <div className="rounded-2xl border border-white/10 bg-black/20 p-4 space-y-3">
                        <input
                            value={manualTitle}
                            onChange={(e) => setManualTitle(cleanText(e.target.value))}
                            className="w-full rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="عنوان الموضوع"
                        />
                        <textarea
                            value={manualBody}
                            onChange={(e) => setManualBody(e.target.value)}
                            className="w-full min-h-[160px] rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="متن المسودة الأولي"
                        />
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <select value={manualCategory} onChange={(e) => setManualCategory(e.target.value)} className="rounded-xl bg-white/10 px-3 py-2 text-sm text-gray-100">
                                <option value="local_algeria">محلي الجزائر</option>
                                <option value="politics">سياسة</option>
                                <option value="economy">اقتصاد</option>
                                <option value="society">مجتمع</option>
                                <option value="technology">تكنولوجيا</option>
                                <option value="international">دولي</option>
                                <option value="sports">رياضة</option>
                            </select>
                            <select value={manualUrgency} onChange={(e) => setManualUrgency(e.target.value)} className="rounded-xl bg-white/10 px-3 py-2 text-sm text-gray-100">
                                <option value="low">منخفض</option>
                                <option value="medium">متوسط</option>
                                <option value="high">عالٍ</option>
                                <option value="breaking">عاجل</option>
                            </select>
                        </div>
                        <div className="flex items-center justify-end gap-2">
                            <button
                                onClick={() => setNewDraftOpen(false)}
                                className="rounded-xl border border-white/20 px-4 py-2 text-sm text-gray-300"
                            >
                                إلغاء
                            </button>
                            <button
                                onClick={() => createManualDraft.mutate()}
                                disabled={createManualDraft.isPending || manualTitle.trim().length < 5 || manualBody.trim().length < 30}
                                className="rounded-xl bg-emerald-500/25 border border-emerald-400/40 px-4 py-2 text-sm text-emerald-100 disabled:opacity-50"
                            >
                                {createManualDraft.isPending ? 'جاري الإنشاء...' : 'إنشاء المسودة'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        );
    }

    return (
        <div className="space-y-4">
            <TutorialOverlay
                open={showEditorEditOverlay}
                stepLabel="الخطوة 3 / 4"
                title="هذا هو مكان العمل الأساسي"
                description="قم بتعديل العنوان أو أضف جملة بسيطة لتبدأ."
                targetSelector="[data-tutorial=\"editor-title\"]"
                primaryLabel="تم التعديل"
                onPrimary={handleTutorialEditNext}
                onSkip={completeTutorial}
            />
            <TutorialOverlay
                open={showEditorSubmitOverlay}
                stepLabel="الخطوة 4 / 4"
                title="أرسل المادة للاعتماد"
                description="عندما تنتهي من التعديل، أرسل المادة مباشرة للاعتماد."
                targetSelector="[data-tutorial=\"editor-submit\"]"
                primaryLabel="إرسال للاعتماد"
                onPrimary={handleTutorialSubmit}
                onSkip={completeTutorial}
            />
            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-3" dir="rtl">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-100">
                                مساحة كتابة هادئة
                            </span>
                            <span className="text-[11px] text-gray-400">{saveNode}</span>
                        </div>
                        <p className="text-[12px] text-slate-300">اكتب فقط. بعد أن تنتهي اضغط «أنهيت الكتابة» لنفتح المراجعة والأدوات.</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            disabled={autosave.isPending}
                            onClick={() => {
                                trackUiAction('workspace_drafts', 'حفظ', surfaceDetails);
                                runWithGuide('save', () => {
                                    setSaveState('saving');
                                    autosave.mutate();
                                });
                            }}
                            className="min-h-10 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs text-slate-200 disabled:opacity-60"
                        >
                            حفظ
                        </button>
                        <button
                            type="button"
                            onClick={enterReviewStage}
                            className="min-h-10 rounded-xl border border-cyan-500/30 bg-cyan-500/15 px-4 py-2 text-xs font-medium text-cyan-100"
                        >
                            أنهيت الكتابة
                        </button>
                        <button
                            type="button"
                            onClick={() => setHeaderToolsOpen((prev) => !prev)}
                            className="inline-flex min-h-10 items-center gap-1 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs text-slate-200"
                        >
                            {headerToolsOpen ? 'إغلاق' : 'المزيد'}
                        </button>
                    </div>
                </div>

                {headerToolsOpen && (
                    <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
                        <button
                            onClick={() => setMemoryCaptureOpen(true)}
                            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200"
                        >
                            حفظ في الذاكرة
                        </button>
                        <button
                            onClick={() => runWithGuide('manual_draft', () => setNewDraftOpen(true))}
                            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200"
                        >
                            مسودة جديدة
                        </button>
                        <NextLink
                            href="/services/multimedia"
                            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-violet-400/30 bg-violet-500/10 px-3 py-2 text-xs text-violet-200"
                        >
                            أدوات الوسائط
                        </NextLink>
                    </div>
                )}

                {(err || ok) && <div className={cn('mt-3 rounded-xl px-3 py-2 text-xs', err ? 'bg-red-500/15 text-red-200 border border-red-500/30' : 'bg-emerald-500/15 text-emerald-200 border border-emerald-500/30')}>{err || ok}</div>}
            </div>

            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-4" dir="rtl">
                {blockerSummary.count > 0 ? (
                    <div className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-100">
                        <div className="space-y-0.5">
                            <p className="font-semibold">ملاحظات جودة عالية ({blockerSummary.count})</p>
                            <p className="text-[10px] text-amber-200 line-clamp-1">
                                {explainedBlockers[0]?.title || blockerSummary.top?.title || 'يمكنك معالجتها الآن أو المتابعة ثم الرجوع لها.'}
                            </p>
                        </div>
                    </div>
                ) : (
                    <div className="mt-2 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-[10px] text-emerald-200">
                        لا توجد ملاحظات جودة عالية حالياً.
                    </div>
                )}

                <div className="mt-3 space-y-3">
                    <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                            <button
                                onClick={() => {
                                    trackNextAction('workspace_drafts', nextAction.label, surfaceDetails);
                                    nextAction.handler();
                                }}
                                className={cn('min-h-10 px-4 py-2 rounded-xl border text-xs flex items-center gap-2 font-medium', severityStyles(nextAction.severity).badge, 'border-white/15')}
                            >
                                {nextAction.label}
                            </button>
                            <button
                                disabled={autosave.isPending}
                                onClick={() => {
                                trackUiAction('workspace_drafts', 'حفظ', surfaceDetails);
                                    runWithGuide('save', () => { setSaveState('saving'); autosave.mutate(); });
                                }}
                                className="min-h-10 px-3 py-2 rounded-xl bg-white/10 border border-white/15 text-slate-200 text-xs flex items-center gap-2 disabled:opacity-60"
                            >
                                <Save className="w-4 h-4" />حفظ
                            </button>
                            {readiness?.ready_for_publish && workId && (
                                <NextLink
                                    href={`/ready-publish/${workId}`}
                                    className="min-h-10 px-3 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-100 text-xs flex items-center gap-2"
                                >
                                    صفحة الجاهز للنشر
                                </NextLink>
                            )}
                            <button
                                disabled={applyToArticle.isPending || !hasSubmissionBody}
                                onClick={() => {
                                    trackNextAction('workspace_drafts', 'إرسال لاعتماد رئيس التحرير', surfaceDetails);
                                    runWithGuide('apply', () => applyToArticle.mutate());
                                }}
                                data-tutorial={showEditorSubmitOverlay ? 'editor-submit' : undefined}
                                className="min-h-10 px-3 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-100 text-xs disabled:opacity-60"
                            >
                                {applyToArticle.isPending ? 'جاري الإرسال...' : 'إرسال لاعتماد رئيس التحرير'}
                            </button>
                            {isJournalist && (
                                <button
                                    disabled={selfApproveDraft.isPending || !hasSubmissionBody}
                                    onClick={() => {
                                        trackNextAction('workspace_drafts', 'اعتماد مباشر', surfaceDetails);
                                        runWithGuide('apply', () => selfApproveDraft.mutate());
                                    }}
                                    className="min-h-10 px-3 py-2 rounded-xl bg-cyan-500/15 border border-cyan-500/30 text-cyan-100 text-xs disabled:opacity-60"
                                >
                                    {selfApproveDraft.isPending ? 'جاري الاعتماد...' : 'اعتماد مباشر'}
                                </button>
                            )}
                        </div>
                        <div className="mt-2 text-[10px] text-slate-400">
                            إرسال للاعتماد = إنهاء المسودة وإرسالها إلى رئيس التحرير. اعتماد مباشر = إنهاء سريع مع تسجيل القرار.
                        </div>
                    </div>
                    <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="text-xs text-slate-300">أدوات التحرير السريعة داخل الصفحة</div>
                            <div className="flex flex-wrap items-center gap-2">
                                <button
                                    onClick={() => {
                                        trackUiAction('workspace_drafts', 'فحص سريع', surfaceDetails);
                                        runWithGuide('quick_check', () => runQuickCheck.mutate());
                                    }}
                                    disabled={runQuickCheck.isPending}
                                    className="min-h-8 px-3 py-2 rounded-lg bg-indigo-500/20 border border-indigo-500/30 text-indigo-100 text-[11px] flex items-center gap-2 disabled:opacity-60"
                                >
                                    <ShieldCheck className="w-4 h-4" />
                                    {runQuickCheck.isPending ? 'جاري الفحص...' : 'فحص سريع'}
                                </button>
                                <button
                                    onClick={() => setToolsExpanded((prev) => !prev)}
                                    className="min-h-8 px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-slate-200 text-[11px]"
                                >
                                    {toolsExpanded ? 'إخفاء أدوات التحسين' : 'إظهار أدوات التحسين'}
                                </button>
                                <button
                                    onClick={() => setSmartHighlightEnabled((prev) => !prev)}
                                    className="min-h-8 px-3 py-2 rounded-lg bg-white/5 border border-white/15 text-slate-200 text-[11px]"
                                >
                                    {smartHighlightEnabled ? 'إيقاف التظليل' : 'تفعيل التظليل'}
                                </button>
                            </div>
                        </div>
                        {toolsExpanded && (
                            <div className="flex flex-wrap gap-2">
                                <button disabled={runVerifier.isPending} onClick={() => runWithGuide('verify', () => runVerifier.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-cyan-500/20 border border-cyan-500/30 text-cyan-200 text-xs flex items-center gap-2 disabled:opacity-60"><SearchCheck className="w-4 h-4" />{runVerifier.isPending ? 'جاري التحقق...' : 'تحقق'}</button>
                                <button disabled={runProofread.isPending} onClick={() => runWithGuide('proofread', () => runProofread.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-lime-500/20 border border-lime-500/30 text-lime-200 text-xs disabled:opacity-60">{runProofread.isPending ? 'جاري التدقيق...' : 'تدقيق لغوي'}</button>
                                <button disabled={runQuality.isPending} onClick={() => runWithGuide('quality', () => runQuality.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-violet-500/20 border border-violet-500/30 text-violet-200 text-xs disabled:opacity-60">{runQuality.isPending ? 'جاري التقييم...' : 'جودة'}</button>
                                <button disabled={runReadiness.isPending} onClick={() => runWithGuide('publish_gate', () => runReadiness.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-amber-500/20 border border-amber-500/30 text-amber-200 text-xs disabled:opacity-60">{runReadiness.isPending ? 'جاري الفحص...' : 'بوابة النشر'}</button>
                                <button disabled={rewrite.isPending} onClick={() => runWithGuide('improve', () => rewrite.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-200 text-xs flex items-center gap-2 disabled:opacity-60"><Sparkles className="w-4 h-4" />{rewrite.isPending ? 'جاري التحسين...' : 'تحسين'}</button>
                                <button disabled={runHeadlines.isPending} onClick={() => runWithGuide('headlines', () => runHeadlines.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-indigo-500/20 border border-indigo-500/30 text-indigo-200 text-xs disabled:opacity-60">{runHeadlines.isPending ? 'جاري التوليد...' : 'عناوين'}</button>
                                <button disabled={runSeo.isPending} onClick={() => runWithGuide('seo', () => runSeo.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-fuchsia-500/20 border border-fuchsia-500/30 text-fuchsia-200 text-xs disabled:opacity-60">{runSeo.isPending ? 'جاري التحليل...' : 'SEO'}</button>
                                <button disabled={runLinks.isPending} onClick={() => runWithGuide('links', () => runLinks.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-teal-500/20 border border-teal-500/30 text-teal-200 text-xs disabled:opacity-60">{runLinks.isPending ? 'جاري جلب الروابط...' : 'روابط'}</button>
                                <button disabled={runSocial.isPending} onClick={() => runWithGuide('social', () => runSocial.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-sky-500/20 border border-sky-500/30 text-sky-200 text-xs disabled:opacity-60">{runSocial.isPending ? 'جاري التوليد...' : 'سوشيال'}</button>
                                {isAdvancedMode && (
                                    <button disabled={runAudienceSimulation.isPending} onClick={() => runWithGuide('audience_test', () => runAudienceSimulation.mutate())} className="min-h-9 px-3 py-2 rounded-xl bg-rose-500/20 border border-rose-500/30 text-rose-100 text-xs disabled:opacity-60">محاكي الجمهور</button>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            </div>
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
                <div className={cn('order-1 xl:order-2 space-y-4', mainSpanClass)}>
                    <div className="rounded-2xl border border-white/10 bg-gray-900/50 overflow-hidden">
                        <div className="border-b border-white/10 p-4">
                            <input
                                data-tutorial={showEditorEditOverlay ? 'editor-title' : undefined}
                                value={title}
                                onChange={(e) => { setTitle(cleanText(e.target.value)); setSaveState('unsaved'); }}
                                className="w-full rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white text-lg"
                                dir="rtl"
                            />
                            {isWritingStage ? (
                                <p className="mt-2 text-[11px] text-gray-500">ابدأ بالعنوان ثم اكتب المتن مباشرة. ستظهر أدوات المراجعة بعد الانتقال إلى المرحلة التالية.</p>
                            ) : (
                                <p className="text-xs text-gray-500 mt-2">معرف العمل: {workId} • الإصدار v{baseVersion}</p>
                            )}
                        </div>
                        {editor && (
                            <BubbleMenu editor={editor}>
                                <div className="relative rounded-xl bg-gray-950/95 border border-white/20 p-1 flex gap-1 text-xs">
                                    <button onClick={() => editor.chain().focus().toggleBold().run()} className="px-2 py-1 rounded bg-white/10">عريض</button>
                                    {!isWritingStage && (
                                        <>
                                            <button onClick={() => editor.chain().focus().toggleItalic().run()} className="px-2 py-1 rounded bg-white/10">مائل</button>
                                            <button onClick={() => editor.chain().focus().toggleHighlight().run()} className="px-2 py-1 rounded bg-white/10">تمييز</button>
                                            <span className="w-px bg-white/10 mx-1" />
                                        </>
                                    )}
                                    <button onClick={() => { setInlineAiOpen((v) => !v); setInlineSourceOpen(false); }} className="px-2 py-1 rounded bg-emerald-500/20 text-emerald-100">AI</button>

                                    {inlineAiOpen && (
                                        <div className="absolute right-0 top-full mt-2 w-44 rounded-xl border border-white/20 bg-gray-950/95 p-2 space-y-1 text-[11px] text-gray-200 z-20">
                                            <button onClick={() => handleInlineAiAction('rewrite')} className="w-full text-right px-2 py-1 rounded bg-white/10">إعادة صياغة</button>
                                            <button onClick={() => handleInlineAiAction('shorten')} className="w-full text-right px-2 py-1 rounded bg-white/10">اختصار</button>
                                            <button onClick={() => handleInlineAiAction('expand')} className="w-full text-right px-2 py-1 rounded bg-white/10">توسيع</button>
                                            <button onClick={() => handleInlineAiAction('clarify')} className="w-full text-right px-2 py-1 rounded bg-white/10">توضيح</button>
                                            {!isWritingStage && (
                                                <>
                                                    <button onClick={() => setInlineSourceOpen((v) => !v)} className="w-full text-right px-2 py-1 rounded bg-white/10">إضافة مصدر</button>
                                                    {inlineSourceOpen && (
                                                        <div className="mt-1 max-h-40 overflow-auto rounded-lg border border-white/10 bg-black/30 p-1 space-y-1">
                                                            {(sources || []).slice(0, 10).map((source) => (
                                                                <button
                                                                    key={`source-inline-${source.id}`}
                                                                    onClick={() => insertSourceInline(source)}
                                                                    className="w-full text-right px-2 py-1 rounded bg-white/10 text-[10px]"
                                                                >
                                                                    {cleanText(source.name || source.url)}
                                                                </button>
                                                            ))}
                                                        </div>
                                                    )}
                                                </>
                                            )}
                                            {inlineAiError && <p className="text-[10px] text-red-300">{inlineAiError}</p>}
                                        </div>
                                    )}
                                </div>
                            </BubbleMenu>
                        )}
                        <EditorContent editor={editor} />
                    </div>

                    {suggestion && (
                        <div className="rounded-2xl border border-amber-400/30 bg-amber-500/10 p-4 space-y-2">
                            <h3 className="text-sm text-amber-200">اقتراح التحسين بصيغة واضحة</h3>
                            <div className="rounded-xl border border-amber-300/30 bg-black/25 p-3 text-xs text-amber-100 space-y-1" dir="rtl">
                                <p>العنوان المقترح: {cleanText(suggestion.title || title || 'بدون عنوان')}</p>
                                <p>التعديل: +{suggestion?.diff_stats?.added || 0} / -{suggestion?.diff_stats?.removed || 0}</p>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                <div className="rounded-xl border border-white/10 bg-black/20 p-2">
                                    <p className="text-[11px] text-gray-400 mb-1">قبل التحسين</p>
                                    <p className="text-sm leading-8 text-gray-100 whitespace-pre-wrap max-h-96 overflow-auto">
                                        {cleanText(suggestion?.preview?.before_text || htmlToReadableText(bodyHtml))}
                                    </p>
                                </div>
                                <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-2">
                                    <p className="text-[11px] text-emerald-200 mb-1">بعد التحسين</p>
                                    <p className="text-sm leading-8 text-emerald-50 whitespace-pre-wrap max-h-96 overflow-auto">
                                        {cleanText(suggestion?.preview?.after_text || suggestion?.body_text || htmlToReadableText(suggestion?.body_html || ''))}
                                    </p>
                                </div>
                            </div>
                            <button
                                onClick={() => setShowTechnicalDiff((v) => !v)}
                                className="px-2 py-1 rounded-lg bg-white/10 text-gray-200 text-[11px]"
                            >
                                {showTechnicalDiff ? 'إخفاء الفرق التقني' : 'عرض الفرق التقني'}
                            </button>
                            {showTechnicalDiff && (
                                <pre className="max-h-56 overflow-auto text-xs text-amber-50 bg-black/25 rounded-xl p-2" dir="ltr">
                                    {normalizeDiffOutput(suggestion.diff || suggestion.diff_html || '') || 'لا يوجد فرق تقني'}
                                </pre>
                            )}
                            <div className="flex gap-2">
                                <button onClick={() => applySuggestion.mutate()} className="px-3 py-2 rounded-xl bg-emerald-500/30 text-emerald-100 text-xs">قبول كنسخة جديدة</button>
                                <button onClick={() => { setSuggestion(null); setShowTechnicalDiff(false); }} className="px-3 py-2 rounded-xl bg-white/10 text-gray-300 text-xs">رفض</button>
                            </div>
                        </div>
                    )}

                    <div className="xl:hidden">
                        {reportPanels}
                    </div>
                </div>

                {showSidePanels && (
                <aside className="order-2 xl:order-1 xl:col-span-2 space-y-4 xl:sticky xl:top-24 self-start max-h-[calc(100vh-140px)] overflow-auto pr-1">
                    <div className="rounded-xl border border-white/10 bg-gray-950/50 p-3 space-y-3">
                        <div className="flex flex-wrap items-center gap-2">
                            <button
                                onClick={() => setLeftTab('drafts')}
                                className={cn('px-3 py-1 rounded-lg text-[11px] border', leftTab === 'drafts' ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-100' : 'bg-white/5 border-white/10 text-gray-300')}
                            >
                                المسودات
                            </button>
                            <button
                                onClick={() => setLeftTab('source')}
                                className={cn('px-3 py-1 rounded-lg text-[11px] border', leftTab === 'source' ? 'bg-cyan-500/20 border-cyan-500/40 text-cyan-100' : 'bg-white/5 border-white/10 text-gray-300')}
                            >
                                المصدر
                            </button>
                            <button
                                onClick={() => setLeftTab('archive')}
                                className={cn('px-3 py-1 rounded-lg text-[11px] border', leftTab === 'archive' ? 'bg-amber-500/20 border-amber-500/40 text-amber-100' : 'bg-white/5 border-white/10 text-gray-300')}
                            >
                                الأرشيف
                            </button>
                        </div>

                        {leftTab === 'drafts' && (
                            <div>
                                <h2 className="text-sm text-white mb-2">المسودات</h2>
                                <div className="space-y-2 max-h-[260px] overflow-auto">
                                    {drafts.map((d) => (
                                        <button key={`${d.work_id}-${d.id}`} onClick={() => setWorkId(d.work_id)} className={cn('w-full text-right rounded-lg border p-2', workId === d.work_id ? 'border-emerald-400/40 bg-emerald-500/10' : 'border-white/10 bg-white/5')}>
                                            <div className="text-xs text-gray-200">{truncate(cleanText(d.title || 'بدون عنوان'), 58)}</div>
                                            <div className="text-[10px] text-gray-500 mt-1">{formatRelativeTime(d.updated_at)}</div>
                                        </button>
                                    ))}
                                </div>
                                <div className="mt-2 flex flex-wrap gap-2">
                                    <button
                                        onClick={() => setDiffOpen(true)}
                                        className="px-2 py-1 rounded-lg bg-white/10 text-[10px] text-gray-200 border border-white/10"
                                    >
                                        مقارنة النسخ
                                    </button>
                                </div>
                            </div>
                        )}

                        {leftTab === 'source' && (
                            <div>
                                <h2 className="text-sm text-white mb-2">المصدر والبيانات</h2>
                                {contextLoading ? <p className="text-xs text-gray-500">جاري التحميل...</p> : (
                                    <div className="text-xs space-y-2" dir="rtl">
                                        <p className="text-gray-200">{cleanText(context?.article?.original_title || 'لا يوجد عنوان مصدر')}</p>
                                        <p className="text-gray-400">{cleanText(context?.article?.router_rationale || 'لا يوجد تفسير توجيه')}</p>
                                        <div className="rounded-xl border border-white/10 bg-black/25 p-2 text-gray-300 max-h-56 overflow-auto">{cleanText(context?.article?.summary || context?.article?.original_content || 'لا يوجد نص مصدر متاح')}</div>
                                    </div>
                                )}
                            </div>
                        )}

                        {leftTab === 'archive' && (
                            <div className="space-y-2" dir="rtl">
                                <h2 className="text-sm text-white">الأرشيف</h2>
                                <div className="flex items-center gap-2">
                                    <input
                                        value={archiveQuery}
                                        onChange={(e) => setArchiveQuery(e.target.value)}
                                        placeholder="ابحث في أرشيف الشروق..."
                                        className="w-full rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-xs text-white"
                                    />
                                    <button
                                        disabled={runArchiveSearch.isPending || archiveQuery.trim().length < 2}
                                        onClick={() => {
                                            setArchiveError(null);
                                            runArchiveSearch.mutate(archiveQuery.trim());
                                        }}
                                        className="px-3 py-2 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-100 text-xs disabled:opacity-60"
                                    >
                                        {runArchiveSearch.isPending ? 'بحث...' : 'بحث'}
                                    </button>
                                </div>
                                {archiveError && <p className="text-[11px] text-red-300">{archiveError}</p>}
                                {archiveItems.length === 0 && !runArchiveSearch.isPending && (
                                    <p className="text-[11px] text-gray-500">اكتب كلمات مفتاحية ثم اضغط بحث.</p>
                                )}
                                <div className="space-y-2 max-h-[320px] overflow-auto">
                                    {archiveItems.map((item) => (
                                        <div key={`archive-${item.id}`} className="rounded-lg border border-white/10 bg-black/20 p-2">
                                            <p className="text-xs text-gray-200 line-clamp-2">{cleanText(item.title || 'بدون عنوان')}</p>
                                            <p className="text-[10px] text-gray-500 mt-1">
                                                {item.published_at ? new Date(item.published_at).toLocaleDateString('ar-DZ') : 'بدون تاريخ'}
                                            </p>
                                            {item.summary && <p className="text-[11px] text-gray-400 mt-1 line-clamp-2">{cleanText(item.summary)}</p>}
                                            <div className="mt-2 flex items-center gap-2">
                                                <button
                                                    onClick={() => insertArchiveItem(item)}
                                                    className="px-2 py-1 rounded-lg bg-white/10 text-[10px] text-gray-200"
                                                >
                                                    إدراج
                                                </button>
                                                {item.url && (
                                                    <a
                                                        href={item.url}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        className="text-[10px] text-cyan-300 underline decoration-dotted"
                                                    >
                                                        فتح المصدر
                                                    </a>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </aside>
                )}

                {showSidePanels && (
                <aside className="order-3 hidden xl:block xl:col-span-3 space-y-3 xl:sticky xl:top-24 self-start max-h-[calc(100vh-140px)] overflow-auto pr-1">
                    {reportPanels}
                </aside>
                )}
            </div>

            {paletteOpen && (
                <div className="fixed inset-0 z-[90] bg-black/60 backdrop-blur-sm flex items-start justify-center p-4">
                    <div className="w-full max-w-xl rounded-2xl border border-white/10 bg-gray-950 p-4 space-y-3" dir="rtl">
                        <input
                            ref={paletteInputRef}
                            value={paletteQuery}
                            onChange={(e) => { setPaletteQuery(e.target.value); setPaletteIndex(0); }}
                            placeholder="ابحث عن أمر... (Ctrl/Cmd + K)"
                            className="w-full rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-sm text-white"
                        />
                        <div className="max-h-64 overflow-auto space-y-1">
                            {filteredPaletteItems.length === 0 && (
                                <p className="text-xs text-gray-500">لا توجد أوامر مطابقة.</p>
                            )}
                            {filteredPaletteItems.map((item, idx) => (
                                <button
                                    key={item.id}
                                    onClick={() => { item.run(); setPaletteOpen(false); }}
                                    className={cn(
                                        'w-full text-right rounded-lg px-3 py-2 text-xs border',
                                        idx === paletteIndex ? 'bg-white/10 border-white/20 text-white' : 'bg-black/20 border-white/10 text-gray-200',
                                    )}
                                >
                                    {item.label}
                                </button>
                            ))}
                        </div>
                        <div className="flex justify-end">
                            <button onClick={() => setPaletteOpen(false)} className="rounded-lg border border-white/15 bg-white/10 px-3 py-1 text-[11px] text-gray-200">
                                إغلاق
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {diffOpen && (
                <div className="fixed inset-0 z-[88] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-gray-950 p-5 space-y-4" dir="rtl">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-lg text-white font-semibold">مقارنة النسخ</h2>
                                <p className="text-[11px] text-gray-400">اختر نسختين لعرض الفروقات.</p>
                            </div>
                            <button onClick={() => setDiffOpen(false)} className="rounded-lg border border-white/15 bg-white/10 px-3 py-1 text-[11px] text-gray-200">
                                إغلاق
                            </button>
                        </div>
                        {versions.length === 0 ? (
                            <p className="text-xs text-gray-400">لا توجد نسخ محفوظة بعد.</p>
                        ) : (
                            <>
                                <div className="flex flex-wrap gap-2">
                                    <select value={cmpFrom || ''} onChange={(e) => setCmpFrom(Number(e.target.value))} className="flex-1 bg-white/10 rounded px-2 py-1 text-xs">
                                        {versions.map((v) => <option key={`f-${v.id}`} value={v.version}>من v{v.version}</option>)}
                                    </select>
                                    <select value={cmpTo || ''} onChange={(e) => setCmpTo(Number(e.target.value))} className="flex-1 bg-white/10 rounded px-2 py-1 text-xs">
                                        {versions.map((v) => <option key={`t-${v.id}`} value={v.version}>إلى v{v.version}</option>)}
                                    </select>
                                    <button onClick={() => runDiff.mutate()} className="px-3 py-1 rounded bg-white/10 text-xs text-gray-200">
                                        {runDiff.isPending ? 'جاري...' : 'قارن'}
                                    </button>
                                    {cmpTo && (
                                        <button onClick={() => restoreVersion.mutate(cmpTo)} className="px-3 py-1 rounded bg-emerald-500/20 text-xs text-emerald-100">
                                            استرجاع v{cmpTo}
                                        </button>
                                    )}
                                </div>
                                <pre className="max-h-56 overflow-auto text-[11px] text-gray-200 whitespace-pre-wrap mt-2" dir="ltr">
                                    {diffView || 'لا يوجد فرق معروض بعد.'}
                                </pre>
                                <div className="rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-300">
                                    <p className="text-gray-400 mb-1">النسخ الأخيرة</p>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-40 overflow-auto">
                                        {versions.slice(0, 8).map((v) => (
                                            <button key={`ver-${v.id}`} onClick={() => restoreVersion.mutate(v.version)} className="w-full text-right rounded bg-white/5 px-2 py-1 text-xs text-gray-200">
                                                الإصدار v{v.version} • {v.change_origin || 'يدوي'}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>
                </div>
            )}

            {storyOpen && (
                <div className="fixed inset-0 z-[88] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-2xl max-h-[78vh] overflow-auto rounded-2xl border border-white/10 bg-gray-950 p-4 space-y-3" dir="rtl">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-lg text-white font-semibold">Story Mode</h2>
                                <p className="text-[11px] text-gray-400">أدوات عملية لبناء قصة صحفية بسرعة وبدون تعقيد.</p>
                            </div>
                            <button
                                onClick={closeStoryMode}
                                className="rounded-lg border border-white/15 bg-white/10 px-3 py-1 text-[11px] text-gray-200"
                            >
                                إغلاق
                            </button>
                        </div>

                        <div className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-gray-300">
                            <div className="flex flex-col md:flex-row md:items-center gap-2">
                                <label className="text-gray-400">القصة:</label>
                                <select
                                    value={selectedStoryId || ''}
                                    onChange={(e) => setSelectedStoryId(Number(e.target.value) || null)}
                                    className="flex-1 min-w-[220px] rounded-lg border border-white/15 bg-white/10 px-2 py-1 text-[11px] text-white"
                                    disabled={storySuggestionsLoading || storySuggestions.length === 0}
                                >
                                    {storySuggestions.length === 0 && <option value="">لا توجد قصة مقترحة</option>}
                                    {storySuggestions.map((item) => (
                                        <option key={`story-suggest-${item.story_id}`} value={item.story_id}>
                                            {item.story_key} — {cleanText(item.title)}
                                        </option>
                                    ))}
                                </select>
                                {storyCenterLoading && <span className="text-[11px] text-sky-300">تحميل...</span>}
                            </div>

                            <div className="grid grid-cols-3 gap-2 mt-2 text-[11px]">
                                <div className="rounded-lg border border-white/10 bg-white/5 px-2 py-1">
                                    <p className="text-gray-400">التغطية</p>
                                    <p className="text-white">{storyHub.coverageScore !== null ? `${storyHub.coverageScore}%` : '—'}</p>
                                </div>
                                <div className="rounded-lg border border-white/10 bg-white/5 px-2 py-1">
                                    <p className="text-gray-400">الفجوات</p>
                                    <p className="text-white">{storyHub.gapsCount !== null ? storyHub.gapsCount : storyGaps.length}</p>
                                </div>
                                <div className="rounded-lg border border-white/10 bg-white/5 px-2 py-1">
                                    <p className="text-gray-400">المواد</p>
                                    <p className="text-white">{storyHub.timelineCount}</p>
                                </div>
                            </div>

                            <div className="rounded-lg border border-cyan-500/25 bg-cyan-500/10 p-2 mt-2 space-y-1">
                                <p className="text-[11px] text-cyan-100 font-semibold">لوحة القرار الآن</p>
                                <p className="text-[10px] text-cyan-100/90">{storyWhatChanged}</p>
                                <p className="text-[10px] text-cyan-100/80">{storyWhyNow}</p>
                                <div className="flex flex-wrap items-center gap-2 pt-1">
                                    <button
                                        onClick={nextBestAction.handler}
                                        className="px-2 py-1 rounded bg-cyan-500/20 text-[10px] text-cyan-100"
                                    >
                                        {nextBestAction.actionLabel}
                                    </button>
                                    <span className="text-[10px] text-gray-300 line-clamp-1">{nextBestAction.title}</span>
                                </div>
                            </div>

                            <div className="flex flex-wrap gap-2 mt-2">
                                <button onClick={insertStoryStarterPack} className="px-2 py-1 rounded bg-emerald-500/20 text-[10px] text-emerald-100">
                                    إدراج باقة القصة
                                </button>
                                <button
                                    onClick={insertAutoTimeline}
                                    disabled={autoTimelineLines.length === 0}
                                    className="px-2 py-1 rounded bg-white/10 text-[10px] text-gray-200 disabled:opacity-40"
                                >
                                    إدراج التسلسل الزمني
                                </button>
                                <button
                                    onClick={() => {
                                        setLeftTab('archive');
                                        setStoryOpen(false);
                                    }}
                                    className="px-2 py-1 rounded bg-white/10 text-[10px] text-gray-200"
                                >
                                    فتح الأرشيف
                                </button>
                                <button
                                    onClick={() => createStoryDraft.mutate('followup')}
                                    disabled={createStoryDraft.isPending}
                                    className="px-2 py-1 rounded bg-white/10 text-[10px] text-gray-200 disabled:opacity-50"
                                >
                                    إنشاء متابعة
                                </button>
                                <button
                                    onClick={() => createStoryDraft.mutate('analysis')}
                                    disabled={createStoryDraft.isPending}
                                    className="px-2 py-1 rounded bg-white/10 text-[10px] text-gray-200 disabled:opacity-50"
                                >
                                    إنشاء تحليل
                                </button>
                                <button
                                    onClick={() => createStoryDraft.mutate('background')}
                                    disabled={createStoryDraft.isPending}
                                    className="px-2 py-1 rounded bg-white/10 text-[10px] text-gray-200 disabled:opacity-50"
                                >
                                    إنشاء خلفية
                                </button>
                            </div>
                        </div>

                        <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
                            <p className="text-xs text-gray-400">ماذا ينقص القصة الآن؟</p>
                            {storyQuickActions.length === 0 ? (
                                <p className="text-[11px] text-emerald-200">لا توجد فجوات حرجة. القصة متوازنة.</p>
                            ) : (
                                storyQuickActions.map((gap) => (
                                    <div key={gap.id} className={cn('rounded-lg border p-2 text-[11px] space-y-1', severityStyles(gap.severity).border)}>
                                        <div className="flex items-center justify-between gap-2">
                                            <p className="text-gray-100">{gap.title}</p>
                                            <button
                                                onClick={gap.handler}
                                                className="px-2 py-1 rounded bg-white/10 text-[10px] text-gray-200"
                                            >
                                                {gap.actionLabel}
                                            </button>
                                        </div>
                                        <p className="text-[10px] text-gray-400">{gap.hint}</p>
                                    </div>
                                ))
                            )}
                        </div>

                        <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
                            <p className="text-xs text-gray-400">مواد جاهزة للإدراج</p>
                            {storyTopSources.length === 0 && <p className="text-xs text-gray-500">لا توجد مواد مرتبطة كافية بعد.</p>}
                            {storyTopSources.map((item: any) => (
                                <div key={`timeline-${item.id}`} className="rounded-lg border border-white/10 bg-white/5 p-2">
                                    <p className="text-xs text-gray-200 line-clamp-2">{cleanText(item.title || 'بدون عنوان')}</p>
                                    <p className="text-[10px] text-gray-500 mt-1">
                                        {storyItemDateLabel(item)}
                                        {item.source_name ? ` • ${cleanText(item.source_name)}` : ''}
                                    </p>
                                    <div className="mt-2 flex flex-wrap items-center gap-2">
                                        <button onClick={() => insertStorySummary(item)} className="px-2 py-1 rounded bg-white/10 text-[10px] text-gray-200">إدراج</button>
                                        <button onClick={() => openStoryInEditor(item)} className="px-2 py-1 rounded bg-emerald-500/15 text-[10px] text-emerald-100">فتح كخبر متابعة</button>
                                        {item.url && <a href={item.url} target="_blank" rel="noreferrer" className="text-[10px] text-cyan-300 underline decoration-dotted">المصدر</a>}
                                    </div>
                                </div>
                            ))}
                            {createStoryDraft.isPending && (
                                <p className="text-[10px] text-cyan-200">جاري تجهيز المسودة من القصة...</p>
                            )}
                        </div>

                        <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
                            <p className="text-xs text-gray-400">استخدام القصة داخل هذه المسودة</p>
                            <div className="grid grid-cols-2 gap-2 text-[10px]">
                                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-2">
                                    <p className="text-emerald-100">تم استخدامه</p>
                                    <p className="text-white mt-1">{storyUsage.used.length}</p>
                                </div>
                                <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-2">
                                    <p className="text-amber-100">غير مستخدم بعد</p>
                                    <p className="text-white mt-1">{storyUsage.unused.length}</p>
                                </div>
                            </div>
                            {storyUsage.unused.slice(0, 2).map((item, idx) => (
                                <div key={`story-unused-${idx}`} className="rounded border border-white/10 bg-white/5 p-2 text-[10px] text-gray-300">
                                    <p className="line-clamp-1">{cleanText(item.title || 'عنصر غير مستخدم')}</p>
                                </div>
                            ))}
                        </div>

                        <div className="pt-1">
                            <button
                                onClick={() => setStoryAdvancedOpen((v) => !v)}
                                className="w-full rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-[11px] text-gray-300"
                            >
                                {storyAdvancedOpen ? 'إخفاء التفاصيل المتقدمة' : 'عرض التفاصيل المتقدمة'}
                            </button>
                        </div>

                        {storyAdvancedOpen && (
                            <div className="rounded-xl border border-white/10 bg-black/20 p-3 space-y-2">
                                <p className="text-xs text-gray-400">تفاصيل متقدمة</p>
                                <p className="text-[11px] text-gray-300">العلاقات: {storyHub.relationsCount} • مصادر متنوعة: {storyHub.sourcesCount} • آخر تحديث: {storyHub.latestLabel}</p>
                                <div className="max-h-44 overflow-auto space-y-1">
                                    {(context?.story_context?.relations || []).slice(0, 6).map((item: any, idx: number) => (
                                        <div key={`relation-${idx}`} className="rounded border border-white/10 bg-white/5 px-2 py-1 text-[10px] text-gray-300">
                                            {cleanText(item.title || 'بدون عنوان')}
                                        </div>
                                    ))}
                                    {(context?.story_context?.relations || []).length === 0 && (
                                        <p className="text-[10px] text-gray-500">لا توجد علاقات معرفة بعد.</p>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {overrideOpen && (
                <div className="fixed inset-0 z-[88] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-2xl rounded-2xl border border-white/10 bg-gray-950 p-5 space-y-4" dir="rtl">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-lg text-white font-semibold">إرسال بتحفّظ (تجاوز الملاحظات)</h2>
                                <p className="text-[11px] text-gray-400">سيتم إرسال الخبر لرئيس التحرير مع توثيق سبب التجاوز.</p>
                            </div>
                            <button onClick={() => setOverrideOpen(false)} className="rounded-lg border border-white/15 bg-white/10 px-3 py-1 text-[11px] text-gray-200">
                                إغلاق
                            </button>
                        </div>
                        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-[11px] text-red-100 space-y-2">
                            <p className="font-semibold">الملاحظات الحالية (سبب + إجراء)</p>
                            {explainedBlockers.length === 0 ? (
                                <p className="text-[10px] text-red-200">لا توجد ملاحظات حرجة حالياً.</p>
                            ) : (
                                explainedBlockers.slice(0, 6).map((item, idx) => (
                                    <div key={`override-${idx}`} className="rounded-lg border border-white/10 bg-black/20 p-2">
                                        <p className="text-[10px] text-red-100">{item.title}</p>
                                        <p className="text-[10px] text-red-200/80 mt-1 line-clamp-2">{item.detail}</p>
                                        {item.action && ACTION_SOURCE_LABELS[item.action as DecisionActionId] && (
                                            <p className="text-[10px] text-amber-200/80 mt-1">الإجراء المقترح: {ACTION_SOURCE_LABELS[item.action as DecisionActionId]}</p>
                                        )}
                                        {item.action && (
                                            <button
                                                onClick={() => decisionActionHandlers[item.action as DecisionActionId]()}
                                                className="mt-2 px-2 py-0.5 rounded bg-white/10 text-[10px] text-gray-200"
                                            >
                                                فتح الأداة
                                            </button>
                                        )}
                                    </div>
                                ))
                            )}
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs text-gray-300">سبب التجاوز (إلزامي)</label>
                            <textarea
                                value={overrideNote}
                                onChange={(e) => setOverrideNote(e.target.value)}
                                className="w-full min-h-[90px] rounded-xl bg-black/30 border border-white/15 px-3 py-2 text-xs text-gray-100 placeholder:text-gray-500"
                                placeholder="اكتب سبب التجاوز بوضوح... (مثال: عاجل ويحتاج النشر مع متابعة لاحقة للتدقيق)"
                            />
                        </div>
                        <div className="flex items-center justify-end gap-2">
                            <button
                                onClick={() => setOverrideOpen(false)}
                                className="rounded-lg border border-white/15 bg-white/10 px-3 py-2 text-[11px] text-gray-200"
                            >
                                إلغاء
                            </button>
                            <button
                                disabled={submitWithReservations.isPending || overrideNote.trim().length < 5}
                                onClick={() => submitWithReservations.mutate()}
                                className="rounded-lg bg-amber-500/30 border border-amber-500/40 px-3 py-2 text-[11px] text-amber-100 disabled:opacity-60"
                            >
                                {submitWithReservations.isPending ? 'جاري الإرسال...' : 'إرسال بتحفّظ'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {newDraftOpen && (
                <div className="fixed inset-0 z-[82] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-gray-950 p-5 space-y-4" dir="rtl">
                        <h2 className="text-lg text-white font-semibold">إنشاء مسودة جديدة لموضوع خاص</h2>
                        <p className="text-xs text-gray-400">استخدم هذا النموذج عندما لا يكون الموضوع واردًا من مصادر النظام.</p>
                        <input
                            value={manualTitle}
                            onChange={(e) => setManualTitle(cleanText(e.target.value))}
                            className="w-full rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="عنوان الموضوع"
                        />
                        <textarea
                            value={manualSummary}
                            onChange={(e) => setManualSummary(cleanText(e.target.value))}
                            className="w-full min-h-[70px] rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="ملخص اختياري"
                        />
                        <textarea
                            value={manualBody}
                            onChange={(e) => setManualBody(e.target.value)}
                            className="w-full min-h-[220px] rounded-xl bg-white/5 border border-white/15 px-3 py-2 text-white"
                            placeholder="متن المسودة الأولي"
                        />
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            <select value={manualCategory} onChange={(e) => setManualCategory(e.target.value)} className="rounded-xl bg-white/10 px-3 py-2 text-sm text-gray-100">
                                <option value="local_algeria">محلي الجزائر</option>
                                <option value="politics">سياسة</option>
                                <option value="economy">اقتصاد</option>
                                <option value="society">مجتمع</option>
                                <option value="technology">تكنولوجيا</option>
                                <option value="international">دولي</option>
                                <option value="sports">رياضة</option>
                            </select>
                            <select value={manualUrgency} onChange={(e) => setManualUrgency(e.target.value)} className="rounded-xl bg-white/10 px-3 py-2 text-sm text-gray-100">
                                <option value="low">منخفض</option>
                                <option value="medium">متوسط</option>
                                <option value="high">عالٍ</option>
                                <option value="breaking">عاجل</option>
                            </select>
                        </div>
                        <div className="flex items-center justify-end gap-2">
                            <button
                                onClick={() => setNewDraftOpen(false)}
                                className="rounded-xl border border-white/20 px-4 py-2 text-sm text-gray-300"
                            >
                                إلغاء
                            </button>
                            <button
                                onClick={() => createManualDraft.mutate()}
                                disabled={createManualDraft.isPending || manualTitle.trim().length < 5 || manualBody.trim().length < 30}
                                className="rounded-xl bg-emerald-500/25 border border-emerald-400/40 px-4 py-2 text-sm text-emerald-100 disabled:opacity-50"
                            >
                                {createManualDraft.isPending ? 'جاري الإنشاء...' : 'إنشاء المسودة'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {memoryCaptureOpen && (
                <MemoryQuickCaptureModal
                    open={memoryCaptureOpen}
                    onClose={() => setMemoryCaptureOpen(false)}
                    onSubmit={(payload) => quickCaptureMutation.mutate(payload)}
                    isSubmitting={quickCaptureMutation.isPending}
                    articleTitle={title || context?.article?.title_ar || context?.article?.original_title || null}
                    sourceLabel={context?.article?.source_name || null}
                    suggestedSubtype="editorial_decision"
                />
            )}

        </div>
    );
}

export default function WorkspaceDraftsPage() {
    return (
        <Suspense
            fallback={
                <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 text-center text-gray-300">
                    Loading...
                </div>
            }
        >
            <WorkspaceDraftsPageContent />
        </Suspense>
    );
}
