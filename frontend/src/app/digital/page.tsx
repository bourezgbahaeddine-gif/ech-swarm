'use client';

import Link from 'next/link';
import { startTransition, useEffect, useMemo, useState } from 'react';
import { isAxiosError } from 'axios';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowRightCircle, CalendarDays, CheckCircle2, Copy, Megaphone, PlusCircle, RefreshCcw, Sparkles, UploadCloud } from 'lucide-react';

import {
    authApi,
    digitalApi,
    type DigitalChannel,
    type DigitalPlaybookTemplate,
    type DigitalPost,
    type DigitalPostVersion,
    type DigitalPostStatus,
    type DigitalScopePerformanceItem,
    type DigitalTask,
    type DigitalTaskActionItem,
    type DigitalTaskStatus,
    type DigitalComposeResult,
    type TeamMember,
} from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';

const READ_ROLES = new Set(['director', 'editor_chief', 'social_media', 'journalist', 'print_editor']);
const WRITE_ROLES = new Set(['director', 'editor_chief', 'social_media']);
const MANAGE_ROLES = new Set(['director', 'editor_chief']);
const PLATFORM_OPTIONS = ['facebook', 'x', 'youtube', 'tiktok', 'instagram'];
const PLATFORM_CHAR_LIMITS: Record<string, number> = {
    x: 280,
    facebook: 5000,
    instagram: 2200,
    tiktok: 2200,
    youtube: 5000,
};
const TV_PLAYBOOK_KEYS = new Set([
    'pre_show_teaser',
    'live_now',
    'post_show_recap',
    'program_promo',
    'guest_quote',
    'clip_extract',
    'episode_highlights',
    'poster_teaser',
    'best_moment_repost',
]);
const COVERAGE_CHECK_LABELS: Record<string, string> = {
    missing_core: 'جملة الجوهر غير واضحة.',
    missing_source: 'المصدر غير ظاهر في الصياغات.',
    missing_time: 'الزمن أو السياق غير واضح.',
    headline_length: 'طول العنوان يحتاج ضبطًا.',
    summary_length: 'طول الملخص غير مناسب للجوال.',
    push_length: 'طول إشعار الدفع يحتاج ضبطًا.',
};

function normalizePlatform(platform: string): string {
    const key = (platform || '').trim().toLowerCase();
    if (key === 'twitter') return 'x';
    return key;
}

function postLengthState(platform: string, text: string): { count: number; limit: number; over: boolean } {
    const key = normalizePlatform(platform);
    const limit = PLATFORM_CHAR_LIMITS[key] || 5000;
    const count = (text || '').trim().length;
    return { count, limit, over: count > limit };
}

function composeCopyText(text: string, hashtags: string[] = []): string {
    const cleanText = (text || '').trim();
    const cleanTags = (hashtags || [])
        .map((tag) => String(tag || '').trim().replace(/^#/, ''))
        .filter(Boolean)
        .map((tag) => `#${tag}`);
    if (!cleanTags.length) return cleanText;
    return `${cleanText}\n\n${cleanTags.join(' ')}`.trim();
}

function platformComposeUrl(platform: string): string {
    const key = normalizePlatform(platform);
    if (key === 'x') return 'https://x.com/compose/post';
    if (key === 'facebook') return 'https://www.facebook.com/';
    if (key === 'instagram') return 'https://www.instagram.com/';
    if (key === 'tiktok') return 'https://www.tiktok.com/upload';
    if (key === 'youtube') return 'https://studio.youtube.com/';
    return 'https://www.facebook.com/';
}

function apiErrorMessage(error: unknown, fallback: string): string {
    if (isAxiosError(error)) {
        const detail = error.response?.data?.detail;
        if (typeof detail === 'string' && detail.trim()) return detail;
    }
    if (error instanceof Error && error.message.trim()) return error.message;
    return fallback;
}

function channelLabel(channel: string): string {
    if (channel === 'news') return 'الشروق نيوز';
    if (channel === 'tv') return 'الشروق تي في';
    return channel;
}

function resolveCoverageSource(task: DigitalTask | null, action: DigitalTaskActionItem | null): { type: string; id?: number } {
    if (action?.source_type) {
        return { type: action.source_type, id: undefined };
    }
    if (!task) return { type: 'manual', id: undefined };
    if (task.article_id) return { type: 'article', id: task.article_id };
    if (task.event_id) return { type: 'event', id: task.event_id };
    if (task.story_id) return { type: 'story', id: task.story_id };
    if (task.program_slot_id) return { type: 'program', id: task.program_slot_id };
    if (task.task_type === 'breaking') return { type: 'breaking', id: task.article_id || undefined };
    return { type: 'manual', id: undefined };
}

function resolveReadiness(task: DigitalTask | null, action: DigitalTaskActionItem | null): string {
    if (!task) return 'غير معروف';
    if (action?.risk_flags?.includes('بدون مسؤول') || !task.owner_user_id) return 'ناقص مسؤول';
    if (action?.risk_flags?.includes('يوجد منشور فاشل')) return 'بحاجة استرجاع';
    if (!task.title) return 'ناقص عنوان';
    return 'جاهز';
}

function buildCoverageMeta(task: DigitalTask | null, action: DigitalTaskActionItem | null): Array<{ label: string; value: string }> {
    if (!task) return [];
    const source = resolveCoverageSource(task, action);
    const readiness = resolveReadiness(task, action);
    const windowLabel = action?.trigger_window || (task.due_at ? formatRelativeTime(task.due_at) : '—');
    return [
        { label: 'المصدر', value: source.type },
        { label: 'معرف المصدر', value: source.id ? String(source.id) : '—' },
        { label: 'المسؤول', value: task.owner_username || 'غير محدد' },
        { label: 'الأولوية', value: String(task.priority || 3) },
        { label: 'الجاهزية', value: readiness },
        { label: 'النافذة', value: windowLabel },
        { label: 'الإجراء التالي', value: action?.next_best_action || '—' },
    ];
}

function taskStatusLabel(status: string): string {
    const labels: Record<string, string> = {
        todo: 'جديد',
        in_progress: 'قيد التنفيذ',
        review: 'للمراجعة',
        done: 'منجز',
        cancelled: 'ملغي',
    };
    return labels[status] || status;
}

function deskLabel(channel: string): string {
    if (channel === 'news') return 'News Desk';
    if (channel === 'tv') return 'TV/Program Desk';
    return 'Desk';
}

function postStatusLabel(status: string): string {
    const labels: Record<string, string> = {
        draft: 'مسودة',
        ready: 'جاهز',
        approved: 'معتمد',
        scheduled: 'مجدول',
        published: 'منشور',
        failed: 'فشل',
    };
    return labels[status] || status;
}

function taskStatusClass(status: string): string {
    if (status === 'done') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200';
    if (status === 'in_progress') return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200';
    if (status === 'review') return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
    if (status === 'cancelled') return 'border-rose-500/30 bg-rose-500/10 text-rose-200';
    return 'border-blue-500/30 bg-blue-500/10 text-blue-200';
}

function postStatusClass(status: string): string {
    if (status === 'published') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200';
    if (status === 'scheduled') return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200';
    if (status === 'failed') return 'border-rose-500/30 bg-rose-500/10 text-rose-200';
    if (status === 'approved') return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
    return 'border-blue-500/30 bg-blue-500/10 text-blue-200';
}

type DigitalComposeSuggestionKey = 'compose_post' | 'save_post' | 'generate_bundle' | 'regenerate_post' | 'run_next_action';

interface DigitalComposeSuggestion {
    taskKey: DigitalComposeSuggestionKey;
    taskLabel: string;
    templateTitle: string;
    playbookHref: string;
    reason: string;
    rationale: string[];
    autoFilledFields: Array<{ label: string; value: string }>;
    promptPreview: string;
    actionLabel: string;
    postId?: number;
}

function buildDigitalComposeSuggestion(args: {
    selectedTask: DigitalTask | null;
    selectedTaskAction: DigitalTaskActionItem | null;
    posts: DigitalPost[];
    postContent: string;
    postPlatform: string;
    bundlePlaybookKey: string;
    composerGenerated: Record<string, { text: string; hashtags: string[] }>;
}): DigitalComposeSuggestion | null {
    const { selectedTask, selectedTaskAction, posts, postContent, postPlatform, bundlePlaybookKey, composerGenerated } = args;
    if (!selectedTask) return null;

    const failedPost = posts.find((post) => post.status === 'failed');
    const generatedPlatforms = Object.keys(composerGenerated || {}).filter((platform) => composerGenerated[platform]?.text?.trim());
    const readyDraft = postContent.trim();
    const approvedPosts = posts.filter((post) => post.status === 'approved' || post.status === 'scheduled' || post.status === 'published');

    if (failedPost) {
        return {
            taskKey: 'regenerate_post',
            taskLabel: `استعد المنشور الفاشل لمنصة ${normalizePlatform(failedPost.platform)}`,
            templateTitle: 'Digital Compose — استرجاع نسخة منصة محددة',
            playbookHref: '/prompt-playbook',
            reason: 'لأن هناك منشورًا فشل سابقًا، وأسرع طريقة لإعادة الدفع هي إعادة توليده بدل البدء من الصفر.',
            rationale: [
                `المنصة المتأثرة: ${normalizePlatform(failedPost.platform)}`,
                `عدد المنشورات الفاشلة: ${posts.filter((post) => post.status === 'failed').length}`,
                selectedTaskAction?.why_now || 'المهمة ما زالت ضمن نافذة العمل الحالية.',
            ],
            autoFilledFields: [
                { label: 'المهمة', value: selectedTask.title },
                { label: 'المنصة', value: normalizePlatform(failedPost.platform) },
                { label: 'الهدف', value: taskObjectiveLabel(selectedTask.task_type) },
            ],
            promptPreview: [
                'المهمة: أعد توليد نسخة رقمية لمنصة واحدة بعد فشل سابق.',
                `العنوان: ${selectedTask.title}`,
                `المنصة: ${normalizePlatform(failedPost.platform)}`,
                `الهدف: ${taskObjectiveLabel(selectedTask.task_type)}`,
                `السبب: ${selectedTaskAction?.why_now || 'استعادة النسخة الفاشلة بأسرع وقت.'}`,
            ].join('\n'),
            actionLabel: 'أعد توليد المنشور',
            postId: failedPost.id,
        };
    }

    if (!posts.length && !readyDraft) {
        const shouldBundle = selectedTask.task_type !== 'manual' && selectedTaskAction?.next_best_action_code === 'generate_posts';
        return {
            taskKey: shouldBundle ? 'generate_bundle' : 'compose_post',
            taskLabel: shouldBundle ? 'أنشئ حزمة نشر أولية للمهمة' : `ولّد أول نسخة لمنصة ${normalizePlatform(postPlatform)}`,
            templateTitle: shouldBundle ? 'Digital Compose — حزمة نسخ متعددة' : 'Digital Compose — منشور أولي لمنصة واحدة',
            playbookHref: '/prompt-playbook',
            reason: shouldBundle
                ? 'لأن المهمة لا تملك منشورات بعد، والحزمة الرقمية ستنتج عدة نسخ قابلة للمراجعة بسرعة.'
                : 'لأن المهمة لا تملك بعد أي نسخة منشورة أو محفوظة، وأسرع خطوة الآن هي صياغة أول منشور.',
            rationale: [
                selectedTaskAction?.why_now || 'المهمة محددة الآن داخل Compose.',
                `المنصة الافتراضية: ${normalizePlatform(postPlatform)}`,
                `نوع المهمة: ${taskObjectiveLabel(selectedTask.task_type)}`,
            ],
            autoFilledFields: [
                { label: 'العنوان', value: selectedTask.title },
                { label: 'المنصة', value: shouldBundle ? `Bundle: ${bundlePlaybookKey}` : normalizePlatform(postPlatform) },
                { label: 'المرجع', value: selectedTaskAction?.source_ref || 'task' },
            ],
            promptPreview: [
                shouldBundle ? 'المهمة: أنشئ باقة رقمية متعددة النسخ لهذه المهمة.' : 'المهمة: صياغة أول منشور رقمي للمهمة الحالية.',
                `العنوان: ${selectedTask.title}`,
                selectedTask.brief ? `الـ brief: ${selectedTask.brief}` : null,
                `الهدف: ${taskObjectiveLabel(selectedTask.task_type)}`,
                shouldBundle ? `Playbook: ${bundlePlaybookKey}` : `المنصة: ${normalizePlatform(postPlatform)}`,
                'القيود: لا تغيّر الوقائع، واجعل النسخة قابلة للتحرير والحفظ فورًا.',
            ]
                .filter(Boolean)
                .join('\n'),
            actionLabel: shouldBundle ? 'ولّد الباقة' : 'صياغة تلقائية',
        };
    }

    if (readyDraft && !posts.length) {
        return {
            taskKey: 'save_post',
            taskLabel: 'احفظ النسخة التي ولّدناها الآن',
            templateTitle: 'Digital Compose — حفظ النسخة الجاهزة',
            playbookHref: '/prompt-playbook',
            reason: 'لأن النص الحالي جاهز تقريبًا، وأفضل خطوة الآن هي حفظه كمادة رقمية بدل فقدانه أو إعادة توليده.',
            rationale: [
                `طول النص الحالي: ${postLengthState(postPlatform, postContent).count} حرفًا`,
                `المنصة: ${normalizePlatform(postPlatform)}`,
                'بعد الحفظ ستدخل النسخة إلى مسار الجاهزية/الاعتماد.',
            ],
            autoFilledFields: [
                { label: 'المهمة', value: selectedTask.title },
                { label: 'المنصة', value: normalizePlatform(postPlatform) },
                { label: 'أول سطر', value: postContent.trim().slice(0, 90) },
            ],
            promptPreview: [
                'المهمة: ثبت النسخة الحالية كمسودة محفوظة داخل Digital Compose.',
                `المنصة: ${normalizePlatform(postPlatform)}`,
                `النص: ${postContent.trim().slice(0, 180)}`,
            ].join('\n'),
            actionLabel: 'احفظ المادة',
        };
    }

    if (generatedPlatforms.length > 0) {
        return {
            taskKey: 'save_post',
            taskLabel: 'احفظ كل النسخ المولدة عبر المنصات',
            templateTitle: 'Digital Compose — حفظ الحزمة المولدة',
            playbookHref: '/prompt-playbook',
            reason: 'لأن لدينا نسخًا مولدة جاهزة، والخطوة الصحيحة الآن هي تثبيتها داخل المهمة بدل إبقائها مؤقتة في واجهة Compose.',
            rationale: [
                `المنصات الجاهزة: ${generatedPlatforms.join('، ')}`,
                `عدد النسخ الجاهزة: ${generatedPlatforms.length}`,
                'بعد الحفظ يمكن مراجعتها أو اعتمادها أو جدولتها مباشرة.',
            ],
            autoFilledFields: [
                { label: 'المهمة', value: selectedTask.title },
                { label: 'المنصات', value: generatedPlatforms.join('، ') },
                { label: 'Playbook', value: bundlePlaybookKey },
            ],
            promptPreview: [
                'المهمة: احفظ الحزمة الرقمية المولدة داخل المهمة الحالية.',
                `المنصات: ${generatedPlatforms.join('، ')}`,
                `Playbook: ${bundlePlaybookKey}`,
            ].join('\n'),
            actionLabel: 'حفظ كل الصياغات',
        };
    }

    if (selectedTaskAction) {
        return {
            taskKey: 'run_next_action',
            taskLabel: selectedTaskAction.next_best_action,
            templateTitle: 'Digital Compose — الإجراء التالي حسب حالة المهمة',
            playbookHref: '/prompt-playbook',
            reason: selectedTaskAction.why_now,
            rationale: [
                `الكود التشغيلي: ${selectedTaskAction.next_best_action_code}`,
                `المصدر: ${selectedTaskAction.source_type}`,
                `الأعلام الحرجة: ${(selectedTaskAction.risk_flags || []).join('، ') || 'لا توجد'}`,
            ],
            autoFilledFields: [
                { label: 'المهمة', value: selectedTask.title },
                { label: 'الإجراء', value: selectedTaskAction.next_best_action },
                { label: 'النافذة', value: selectedTaskAction.trigger_window || '—' },
            ],
            promptPreview: [
                'المهمة: نفّذ الخطوة التالية الأنسب داخل سير عمل الديجيتال.',
                `العنوان: ${selectedTask.title}`,
                `الإجراء التالي: ${selectedTaskAction.next_best_action}`,
                `السبب: ${selectedTaskAction.why_now}`,
            ].join('\n'),
            actionLabel: selectedTaskAction.next_best_action,
        };
    }

    if (!approvedPosts.length && selectedTask.task_type !== 'manual') {
        return {
            taskKey: 'generate_bundle',
            taskLabel: 'وسّع المهمة إلى باقة نشر متعددة المنصات',
            templateTitle: 'Digital Compose — Bundle generation',
            playbookHref: '/prompt-playbook',
            reason: 'لأن لدينا نسخة أو أكثر، لكن لا توجد بعد حزمة مكتملة تغطي المنصات الأساسية لهذه المهمة.',
            rationale: [
                `عدد المواد الحالية: ${posts.length}`,
                `Playbook الحالي: ${bundlePlaybookKey}`,
                `نوع المهمة: ${taskObjectiveLabel(selectedTask.task_type)}`,
            ],
            autoFilledFields: [
                { label: 'المهمة', value: selectedTask.title },
                { label: 'المنصات الحالية', value: posts.map((post) => normalizePlatform(post.platform)).join('، ') || 'لا توجد' },
                { label: 'Playbook', value: bundlePlaybookKey },
            ],
            promptPreview: [
                'المهمة: أنشئ Bundle متعددة المنصات للمهمة الحالية.',
                `العنوان: ${selectedTask.title}`,
                selectedTask.brief ? `الـ brief: ${selectedTask.brief}` : null,
                `Playbook: ${bundlePlaybookKey}`,
            ]
                .filter(Boolean)
                .join('\n'),
            actionLabel: 'ولّد الباقة',
        };
    }

    return null;
}

function actionCodeLabel(code: string): string {
    const labels: Record<string, string> = {
        recover_failed: 'استرجاع الفشل',
        assign_owner: 'تعيين مالك',
        generate_posts: 'توليد منشورات',
        review_drafts: 'راجع المسودات',
        approve_posts: 'اعتماد',
        publish_or_schedule: 'نشر/جدولة',
        start_task: 'بدء التنفيذ',
        move_to_review: 'إرسال للمراجعة',
        monitor: 'متابعة',
    };
    return labels[code] || 'إجراء';
}

function actionCodeClass(code: string): string {
    if (code === 'recover_failed') return 'border-rose-500/30 bg-rose-500/10 text-rose-200';
    if (code === 'publish_or_schedule' || code === 'approve_posts') return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
    if (code === 'generate_posts') return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200';
    return 'border-slate-500/30 bg-slate-500/10 text-slate-200';
}

function taskObjectiveLabel(taskType: string): string {
    const key = (taskType || '').toLowerCase();
    if (key.includes('breaking')) return 'breaking';
    if (key.includes('pre')) return 'teaser';
    if (key.includes('live')) return 'live_update';
    if (key.includes('post')) return 'recap';
    if (key.includes('event')) return 'event_coverage';
    return 'general';
}

function coverageCheckLabel(code: string): string {
    return COVERAGE_CHECK_LABELS[code] || 'تنبيه جودة يحتاج مراجعة.';
}

function coverageCheckClass(level: string): string {
    if (level === 'warning') return 'border-rose-500/30 bg-rose-500/10 text-rose-200';
    return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
}

export default function DigitalPage() {
    const { user } = useAuth();
    const role = (user?.role || '').toLowerCase();
    const canRead = READ_ROLES.has(role);
    const canWrite = WRITE_ROLES.has(role);
    const canManage = MANAGE_ROLES.has(role);
    const queryClient = useQueryClient();

    const [message, setMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const [q, setQ] = useState('');
    const [desk, setDesk] = useState<'news' | 'tv'>('news');
    const [channel, setChannel] = useState<'all' | DigitalChannel>('news');
    const [status, setStatus] = useState<'all' | DigitalTaskStatus>('all');
    const [taskTypeFilter, setTaskTypeFilter] = useState<string>('all');
    const [onlyMine, setOnlyMine] = useState(false);
    const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
    const [selectedTaskIds, setSelectedTaskIds] = useState<number[]>([]);
    const [deskMode, setDeskMode] = useState<'execute' | 'compose' | 'planning'>('execute');
    const [changesSinceLast, setChangesSinceLast] = useState<{
        new_now: number;
        new_risk: number;
        moved_to_next: number;
    } | null>(null);

    const [taskTitle, setTaskTitle] = useState('');
    const [taskBrief, setTaskBrief] = useState('');
    const [taskChannel, setTaskChannel] = useState<DigitalChannel>('news');
    const [taskDueAt, setTaskDueAt] = useState('');

    const [postPlatform, setPostPlatform] = useState('facebook');
    const [postStatus, setPostStatus] = useState<DigitalPostStatus>('draft');
    const [postContent, setPostContent] = useState('');
    const [postHashtags, setPostHashtags] = useState('');
    const [postScheduledAt, setPostScheduledAt] = useState('');
    const [coveragePack, setCoveragePack] = useState<DigitalComposeResult['coverage_pack'] | null>(null);

    useEffect(() => {
        setChannel(desk);
        setTaskChannel(desk);
    }, [desk]);

    const [scopeUserId, setScopeUserId] = useState('');
    const [scopeNews, setScopeNews] = useState(true);
    const [scopeTv, setScopeTv] = useState(true);

    const [publishUrlDraft, setPublishUrlDraft] = useState<Record<number, string>>({});
    const [composerSlotId, setComposerSlotId] = useState('');
    const [composerDraft, setComposerDraft] = useState('');
    const [composerPlatforms, setComposerPlatforms] = useState<string[]>(['facebook']);
    const [composerTaskId, setComposerTaskId] = useState<number | null>(null);
    const [composerGenerated, setComposerGenerated] = useState<Record<string, { text: string; hashtags: string[] }>>({});
    const [bundlePlaybookKey, setBundlePlaybookKey] = useState('breaking_alert');
    const [openVersionsForPost, setOpenVersionsForPost] = useState<number | null>(null);
    const [compareBaseVersionNo, setCompareBaseVersionNo] = useState<number | null>(null);
    const [compareTargetVersionNo, setCompareTargetVersionNo] = useState<number | null>(null);
    const [engagementByPostId, setEngagementByPostId] = useState<Record<number, { score: number; rec: string[] }>>({});

    const overviewQuery = useQuery({
        queryKey: ['digital-overview'],
        queryFn: () => digitalApi.overview(),
        enabled: canRead,
        refetchInterval: 30000,
    });

    useEffect(() => {
        setCoveragePack(null);
    }, [selectedTaskId]);

    const actionDeskQuery = useQuery({
        queryKey: ['digital-action-desk', channel],
        queryFn: () => digitalApi.actionDesk({ channel, limit_each: 10 }),
        enabled: canRead,
        refetchInterval: 20000,
    });

    const tasksQuery = useQuery({
        queryKey: ['digital-tasks', q, channel, status],
        queryFn: () =>
            digitalApi.listTasks({
                q: q || undefined,
                channel: channel === 'all' ? undefined : channel,
                status: status === 'all' ? undefined : status,
                page: 1,
                per_page: 200,
            }),
        enabled: canRead,
        refetchInterval: 20000,
    });

    const slotsQuery = useQuery({
        queryKey: ['digital-slots'],
        queryFn: () => digitalApi.listProgramSlots({ channel: 'all', active_only: true, limit: 100 }),
        enabled: canRead,
    });

    const calendarQuery = useQuery({
        queryKey: ['digital-calendar', channel],
        queryFn: () => digitalApi.calendar({ channel, days: 7 }),
        enabled: canRead,
    });

    const scopesQuery = useQuery({
        queryKey: ['digital-scopes'],
        queryFn: () => digitalApi.scopes(),
        enabled: canManage,
    });

    const playbooksQuery = useQuery({
        queryKey: ['digital-playbooks'],
        queryFn: () => digitalApi.playbooks(),
        enabled: canRead,
    });

    const deskPlaybooks = useMemo(() => {
        const list = (playbooksQuery.data?.data || []) as DigitalPlaybookTemplate[];
        return list.filter((pb) => {
            if (pb.desk) return pb.desk === desk;
            return desk === 'tv' ? TV_PLAYBOOK_KEYS.has(pb.key) : !TV_PLAYBOOK_KEYS.has(pb.key);
        });
    }, [desk, playbooksQuery.data]);

    useEffect(() => {
        if (!deskPlaybooks.length) return;
        if (!deskPlaybooks.find((pb) => pb.key === bundlePlaybookKey)) {
            setBundlePlaybookKey(deskPlaybooks[0].key);
        }
    }, [deskPlaybooks, bundlePlaybookKey]);

    const scopePerformanceQuery = useQuery({
        queryKey: ['digital-scope-performance'],
        queryFn: () => digitalApi.scopePerformance(),
        enabled: canManage,
        refetchInterval: 60000,
    });

    const usersQuery = useQuery({
        queryKey: ['digital-users'],
        queryFn: () => authApi.users(),
        enabled: canManage,
    });

    const tasks = useMemo(() => (tasksQuery.data?.data?.items || []) as DigitalTask[], [tasksQuery.data?.data?.items]);
    const taskTypeOptions = useMemo(() => {
        const uniq = Array.from(new Set(tasks.map((t) => (t.task_type || '').trim()).filter(Boolean)));
        uniq.sort((a, b) => a.localeCompare(b));
        return uniq;
    }, [tasks]);
    const filteredTasks = useMemo(() => {
        return tasks.filter((task) => {
            if (taskTypeFilter !== 'all' && task.task_type !== taskTypeFilter) return false;
            if (onlyMine && (!user?.id || task.owner_user_id !== user.id)) return false;
            return true;
        });
    }, [onlyMine, taskTypeFilter, tasks, user]);
    const selectedTask = useMemo(() => filteredTasks.find((t) => t.id === selectedTaskId) || null, [filteredTasks, selectedTaskId]);
    const actionDesk = actionDeskQuery.data?.data;
    const actionDeskItems = useMemo(() => {
        const rows = [...(actionDesk?.now || []), ...(actionDesk?.next || []), ...(actionDesk?.at_risk || [])];
        const map = new Map<number, DigitalTaskActionItem>();
        rows.forEach((row) => map.set(row.task.id, row));
        return map;
    }, [actionDesk?.at_risk, actionDesk?.next, actionDesk?.now]);
    const failedRiskItems = useMemo(
        () => (actionDesk?.at_risk || []).filter((item) => (item.risk_flags || []).some((flag) => flag.includes('فاشل'))),
        [actionDesk?.at_risk]
    );
    const executeQueue = useMemo(() => {
        const seen = new Set<number>();
        const ordered = [...(actionDesk?.now || []), ...(actionDesk?.at_risk || []), ...(actionDesk?.next || [])];
        return ordered.filter((item) => {
            if (seen.has(item.task.id)) return false;
            seen.add(item.task.id);
            return true;
        });
    }, [actionDesk?.at_risk, actionDesk?.next, actionDesk?.now]);
    const selectedTaskAction = useMemo(
        () => (selectedTask ? actionDeskItems.get(selectedTask.id) || null : null),
        [actionDeskItems, selectedTask]
    );
    const operationalKpis = useMemo(
        () => [
            {
                label: 'يحتاج تنفيذ الآن',
                value: actionDesk?.now_count || 0,
                tone: 'border-cyan-500/20 bg-cyan-500/5',
            },
            {
                label: 'At Risk / Failed',
                value: actionDesk?.at_risk_count || 0,
                tone: 'border-rose-500/20 bg-rose-500/5',
            },
            {
                label: 'جاهز أو مجدول',
                value: overviewQuery.data?.data?.scheduled_posts_next_24h ?? 0,
                tone: 'border-emerald-500/20 bg-emerald-500/5',
            },
        ],
        [actionDesk?.at_risk_count, actionDesk?.now_count, overviewQuery.data?.data?.scheduled_posts_next_24h]
    );
    const planningKpis = useMemo(
        () => [
            { label: 'إجمالي المهام', value: overviewQuery.data?.data?.total_tasks ?? 0, tone: 'border-cyan-500/20 bg-cyan-500/5' },
            { label: 'متأخرة', value: overviewQuery.data?.data?.overdue ?? 0, tone: 'border-rose-500/20 bg-rose-500/5' },
            { label: 'مستحقة اليوم', value: overviewQuery.data?.data?.due_today ?? 0, tone: 'border-amber-500/20 bg-amber-500/5' },
            { label: 'قيد التنفيذ', value: overviewQuery.data?.data?.in_progress ?? 0, tone: 'border-blue-500/20 bg-blue-500/5' },
            { label: 'منجزة اليوم', value: overviewQuery.data?.data?.done_today ?? 0, tone: 'border-emerald-500/20 bg-emerald-500/5' },
            { label: 'منشور 24 ساعة', value: overviewQuery.data?.data?.published_posts_24h ?? 0, tone: 'border-violet-500/20 bg-violet-500/5' },
            { label: 'مجدول 24 ساعة', value: overviewQuery.data?.data?.scheduled_posts_next_24h ?? 0, tone: 'border-indigo-500/20 bg-indigo-500/5' },
            {
                label: 'الانضباط',
                value: `${Number(overviewQuery.data?.data?.on_time_rate || 0).toFixed(1)}%`,
                tone: 'border-slate-500/20 bg-slate-500/5',
            },
        ],
        [
            overviewQuery.data?.data?.done_today,
            overviewQuery.data?.data?.due_today,
            overviewQuery.data?.data?.in_progress,
            overviewQuery.data?.data?.on_time_rate,
            overviewQuery.data?.data?.overdue,
            overviewQuery.data?.data?.published_posts_24h,
            overviewQuery.data?.data?.scheduled_posts_next_24h,
            overviewQuery.data?.data?.total_tasks,
        ]
    );

    useEffect(() => {
        const nowItems = actionDesk?.now || [];
        const nextItems = actionDesk?.next || [];
        const riskItems = actionDesk?.at_risk || [];
        const prev = (window as typeof window & { __digitalDeskSnapshot?: { now: number[]; next: number[]; risk: number[] } }).__digitalDeskSnapshot;
        if (!prev) {
            (window as typeof window & { __digitalDeskSnapshot?: { now: number[]; next: number[]; risk: number[] } }).__digitalDeskSnapshot = {
                now: nowItems.map((x) => x.task.id),
                next: nextItems.map((x) => x.task.id),
                risk: riskItems.map((x) => x.task.id),
            };
            return;
        }
        const nowIds = new Set(nowItems.map((x) => x.task.id));
        const nextIds = new Set(nextItems.map((x) => x.task.id));
        const riskIds = new Set(riskItems.map((x) => x.task.id));
        const prevNow = new Set(prev.now);
        const prevRisk = new Set(prev.risk);
        const prevNext = new Set(prev.next);

        const newNow = [...nowIds].filter((id) => !prevNow.has(id)).length;
        const newRisk = [...riskIds].filter((id) => !prevRisk.has(id)).length;
        const movedToNext = [...nextIds].filter((id) => !prevNext.has(id)).length;

        if (newNow > 0 || newRisk > 0 || movedToNext > 0) {
            startTransition(() => {
                setChangesSinceLast({ new_now: newNow, new_risk: newRisk, moved_to_next: movedToNext });
            });
        }

        (window as typeof window & { __digitalDeskSnapshot?: { now: number[]; next: number[]; risk: number[] } }).__digitalDeskSnapshot = {
            now: [...nowIds],
            next: [...nextIds],
            risk: [...riskIds],
        };
    }, [actionDesk?.at_risk, actionDesk?.next, actionDesk?.now]);

    const postsQuery = useQuery({
        queryKey: ['digital-posts', selectedTaskId],
        queryFn: () => digitalApi.listTaskPosts(selectedTaskId as number),
        enabled: canRead && !!selectedTaskId,
    });
    const posts = useMemo(() => (postsQuery.data?.data?.items || []) as DigitalPost[], [postsQuery.data?.data?.items]);
    const versionsQuery = useQuery({
        queryKey: ['digital-post-versions', openVersionsForPost],
        queryFn: () => digitalApi.listPostVersions(openVersionsForPost as number),
        enabled: canRead && !!openVersionsForPost,
    });
    const versions = useMemo(() => (versionsQuery.data?.data?.items || []) as DigitalPostVersion[], [versionsQuery.data?.data?.items]);

    const versionCompareQuery = useQuery({
        queryKey: ['digital-post-compare', openVersionsForPost, compareBaseVersionNo, compareTargetVersionNo],
        queryFn: () =>
            digitalApi.comparePostVersions(openVersionsForPost as number, {
                base_version_no: compareBaseVersionNo as number,
                target_version_no: compareTargetVersionNo as number,
            }),
        enabled: canRead && !!openVersionsForPost && !!compareBaseVersionNo && !!compareTargetVersionNo,
    });

    const socialUsers = useMemo(
        () =>
            ((usersQuery.data?.data || []) as TeamMember[])
                .filter((u) => (u.role || '').toLowerCase() === 'social_media')
                .sort((a, b) => (a.full_name_ar || a.username).localeCompare(b.full_name_ar || b.username)),
        [usersQuery.data?.data]
    );
    const postDraftLength = useMemo(() => postLengthState(postPlatform, postContent), [postPlatform, postContent]);
    const composerHasOverLimit = useMemo(
        () =>
            Object.entries(composerGenerated || {}).some(([platform, value]) =>
                postLengthState(platform, value.text || '').over
            ),
        [composerGenerated]
    );
    const composeSuggestion = useMemo(
        () =>
            buildDigitalComposeSuggestion({
                selectedTask,
                selectedTaskAction,
                posts,
                postContent,
                postPlatform,
                bundlePlaybookKey,
                composerGenerated,
            }),
        [bundlePlaybookKey, composerGenerated, postContent, postPlatform, posts, selectedTask, selectedTaskAction]
    );

    const buildProgramDrafts = async (): Promise<{
        taskId: number;
        map: Record<string, { text: string; hashtags: string[] }>;
    }> => {
        const slotId = Number(composerSlotId);
        if (!slotId || Number.isNaN(slotId)) throw new Error('اختر برنامجاً أو مسلسلاً أولاً.');
        if (!composerPlatforms.length) throw new Error('اختر منصة واحدة على الأقل.');

        const slot = (slotsQuery.data?.data || []).find((s) => s.id === slotId);
        if (!slot) throw new Error('تعذر تحميل البرنامج المختار.');

        const taskRes = await digitalApi.createTask({
            channel: slot.channel,
            title: `منشور مقطع | ${slot.program_title}`,
            brief: composerDraft.trim() || slot.social_focus || slot.description || null,
            platform: 'all',
            priority: 3,
            program_slot_id: slot.id,
        });

        const taskId = taskRes.data.id;
        const composed = await Promise.all(
            composerPlatforms.map(async (platform) => {
                const res = await digitalApi.composeTask(taskId, { platform, max_hashtags: 6 });
                return [platform, { text: res.data.recommended_text, hashtags: res.data.hashtags || [] }] as const;
            })
        );
        return { taskId, map: Object.fromEntries(composed) as Record<string, { text: string; hashtags: string[] }> };
    };

    const refreshAll = async () => {
        await queryClient.invalidateQueries({ queryKey: ['digital-overview'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-action-desk'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-playbooks'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-scope-performance'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-tasks'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-slots'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-calendar'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-posts'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-post-versions'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-post-compare'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-scopes'] });
    };

    const toggleTaskSelection = (taskId: number, checked: boolean) => {
        setSelectedTaskIds((prev) => {
            if (checked) {
                if (prev.includes(taskId)) return prev;
                return [...prev, taskId];
            }
            return prev.filter((id) => id !== taskId);
        });
    };

    const toggleComposerPlatform = (platform: string) => {
        setComposerPlatforms((prev) => {
            if (prev.includes(platform)) return prev.filter((p) => p !== platform);
            return [...prev, platform];
        });
    };

    const copySimple = async (text: string) => {
        try {
            await navigator.clipboard.writeText(text || '');
            setError(null);
            setMessage('تم النسخ.');
        } catch {
            setError('تعذر النسخ التلقائي من المتصفح.');
        }
    };

    const openComposer = (platform: string) => {
        if (typeof window === 'undefined') return;
        const url = platformComposeUrl(platform);
        window.open(url, '_blank', 'noopener,noreferrer');
    };

    const copyAndOpenComposer = async (platform: string, text: string, hashtags?: string[]) => {
        await copySimple(composeCopyText(text, hashtags || []));
        openComposer(platform);
    };

    const generateMutation = useMutation({
        mutationFn: () => digitalApi.generate({ hours_ahead: 36, include_events: true, include_breaking: true }),
        onSuccess: async (res) => {
            const d = res.data;
            setError(null);
            setMessage(`تم توليد ${d.total_generated} مهمة (برامج ${d.generated_program_tasks} | أحداث ${d.generated_event_tasks} | عاجل ${d.generated_breaking_tasks})`);
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر توليد المهام تلقائياً.')),
    });

    const importSlotsMutation = useMutation({
        mutationFn: (overwrite: boolean) => digitalApi.importProgramSlots({ overwrite }),
        onSuccess: async (res) => {
            const d = res.data;
            setError(null);
            setMessage(`تم استيراد الشبكة: جديد ${d.created} | محدث ${d.updated} | متجاوز ${d.skipped} | أخطاء ${d.errors_count}`);
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر استيراد الشبكة البرامجية.')),
    });

    const createTaskMutation = useMutation({
        mutationFn: () =>
            digitalApi.createTask({
                channel: taskChannel,
                title: taskTitle.trim(),
                brief: taskBrief.trim() || null,
                due_at: taskDueAt ? new Date(taskDueAt).toISOString() : null,
            }),
        onSuccess: async (res) => {
            setSelectedTaskId(res.data.id);
            setTaskTitle('');
            setTaskBrief('');
            setTaskDueAt('');
            setError(null);
            setMessage('تم إنشاء المهمة.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر إنشاء المهمة.')),
    });

    const updateTaskMutation = useMutation({
        mutationFn: ({ taskId, nextStatus }: { taskId: number; nextStatus: DigitalTaskStatus }) =>
            digitalApi.updateTask(taskId, { status: nextStatus }),
        onSuccess: async () => {
            setError(null);
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تحديث حالة المهمة.')),
    });

    const claimTaskMutation = useMutation({
        mutationFn: (taskId: number) => {
            if (!user?.id) throw new Error('تعذر تحديد حسابك.');
            return digitalApi.updateTask(taskId, { owner_user_id: user.id });
        },
        onSuccess: async () => {
            setError(null);
            setMessage('تم استلام المهمة.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر استلام المهمة.')),
    });

    const createPostMutation = useMutation({
        mutationFn: () => {
            const draft = postContent.trim();
            const length = postLengthState(postPlatform, draft);
            if (length.over) {
                throw new Error(`تجاوزت الحد لمنصة ${normalizePlatform(postPlatform)}: ${length.count}/${length.limit}`);
            }
            return digitalApi.createTaskPost(selectedTaskId as number, {
                platform: postPlatform,
                content_text: draft,
                hashtags: postHashtags.split(',').map((s) => s.trim()).filter(Boolean),
                status: postStatus,
                scheduled_at: postScheduledAt ? new Date(postScheduledAt).toISOString() : null,
            });
        },
        onSuccess: async () => {
            setPostContent('');
            setPostHashtags('');
            setPostScheduledAt('');
            setPostStatus('draft');
            setError(null);
            setMessage('تم حفظ مادة السوشيال.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر حفظ المادة.')),
    });

    const composePostMutation = useMutation({
        mutationFn: () =>
            digitalApi.composeTask(selectedTaskId as number, {
                platform: postPlatform,
                max_hashtags: 6,
            }),
        onSuccess: (res) => {
            const data = res.data;
            setPostContent(data.recommended_text || '');
            setPostHashtags((data.hashtags || []).join(', '));
            setCoveragePack(data.coverage_pack || null);
            setError(null);
            setMessage(`تمت صياغة منشور تلقائي من مصدر: ${data.source?.title || 'المهمة'}`);
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذرت صياغة المنشور تلقائياً.')),
    });

    const generateFromProgramMutation = useMutation({
        mutationFn: buildProgramDrafts,
        onSuccess: async (res) => {
            setComposerTaskId(res.taskId);
            setSelectedTaskId(res.taskId);
            setComposerGenerated(res.map);
            setError(null);
            setMessage('تم توليد صياغات مخصصة حسب المنصات المختارة.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر توليد منشورات البرنامج.')),
    });

    const saveGeneratedPostsMutation = useMutation({
        mutationFn: async () => {
            if (!composerTaskId) throw new Error('لا توجد مهمة صياغة محفوظة بعد.');
            const entries = Object.entries(composerGenerated || {}).filter(([, value]) => value.text.trim());
            if (!entries.length) throw new Error('لا توجد صياغات جاهزة للحفظ.');
            const invalid = entries
                .map(([platform, value]) => ({
                    platform: normalizePlatform(platform),
                    state: postLengthState(platform, value.text || ''),
                }))
                .filter((item) => item.state.over);
            if (invalid.length) {
                const list = invalid.map((item) => `${item.platform} (${item.state.count}/${item.state.limit})`).join('، ');
                throw new Error(`يوجد تجاوز لطول النص في: ${list}`);
            }
            await Promise.all(
                entries.map(([platform, value]) =>
                    digitalApi.createTaskPost(composerTaskId, {
                        platform,
                        content_text: value.text,
                        hashtags: value.hashtags || [],
                        status: 'ready',
                    })
                )
            );
        },
        onSuccess: async () => {
            setError(null);
            setMessage('تم حفظ الصياغات في المهمة المختارة.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر حفظ الصياغات المولدة.')),
    });

    const generateAndSaveMutation = useMutation({
        mutationFn: async () => {
            const res = await buildProgramDrafts();
            const entries = Object.entries(res.map).filter(([, value]) => (value.text || '').trim());
            if (!entries.length) throw new Error('فشل التوليد: لا توجد صياغات صالحة للحفظ.');
            const invalid = entries
                .map(([platform, value]) => ({
                    platform: normalizePlatform(platform),
                    state: postLengthState(platform, value.text || ''),
                }))
                .filter((item) => item.state.over);
            if (invalid.length) {
                const list = invalid.map((item) => `${item.platform} (${item.state.count}/${item.state.limit})`).join('، ');
                throw new Error(`تم التوليد لكن يوجد تجاوز لطول النص في: ${list}`);
            }
            await Promise.all(
                entries.map(([platform, value]) =>
                    digitalApi.createTaskPost(res.taskId, {
                        platform,
                        content_text: value.text,
                        hashtags: value.hashtags || [],
                        status: 'ready',
                    })
                )
            );
            return { taskId: res.taskId, map: res.map, count: entries.length };
        },
        onSuccess: async (res) => {
            setComposerTaskId(res.taskId);
            setSelectedTaskId(res.taskId);
            setComposerGenerated(res.map);
            setError(null);
            setMessage(`تم توليد وحفظ ${res.count} منشور مباشرة.`);
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تنفيذ التوليد والحفظ المباشر.')),
    });

    const publishPostMutation = useMutation({
        mutationFn: ({ postId, publishedUrl }: { postId: number; publishedUrl?: string }) =>
            digitalApi.markPostPublished(postId, { published_url: publishedUrl || undefined }),
        onSuccess: async () => {
            setError(null);
            setMessage('تم تحديث المادة كمنشورة.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تحديث حالة المادة.')),
    });

    const generateBundleMutation = useMutation({
        mutationFn: () => {
            if (!selectedTaskId) throw new Error('اختر مهمة أولاً.');
            return digitalApi.generateBundle(selectedTaskId, {
                playbook_key: bundlePlaybookKey,
                save_as_posts: true,
            });
        },
        onSuccess: async (res) => {
            setError(null);
            setMessage(`تم توليد باقة رقمية: ${res.data.generated_count} منشور.`);
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر توليد الباقة الرقمية.')),
    });

    const regeneratePostMutation = useMutation({
        mutationFn: (postId: number) => digitalApi.regeneratePost(postId),
        onSuccess: async () => {
            setError(null);
            setMessage('تمت إعادة التوليد وحفظ نسخة جديدة.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذرت إعادة التوليد.')),
    });

    const duplicatePostVersionMutation = useMutation({
        mutationFn: ({ postId, sourceVersionNo }: { postId: number; sourceVersionNo?: number }) =>
            digitalApi.duplicatePostVersion(postId, {
                source_version_no: sourceVersionNo,
                version_type: 'duplicated',
            }),
        onSuccess: async () => {
            setError(null);
            setMessage('تم إنشاء نسخة جديدة من الإصدار المحدد.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تكرار النسخة.')),
    });

    const dispatchPostMutation = useMutation({
        mutationFn: ({ postId, action }: { postId: number; action: 'publish' | 'schedule' }) =>
            digitalApi.dispatchPost(postId, {
                adapter: 'manual',
                action,
                scheduled_at: action === 'schedule' ? new Date(Date.now() + 5 * 60 * 1000).toISOString() : null,
            }),
        onSuccess: async (res) => {
            setError(null);
            setMessage(res.data.message || 'تم تنفيذ التسليم.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تنفيذ التسليم.')),
    });

    const engagementMutation = useMutation({
        mutationFn: (postId: number) => digitalApi.postEngagementScore(postId),
        onSuccess: (res) => {
            setEngagementByPostId((prev) => ({
                ...prev,
                [res.data.post_id]: {
                    score: res.data.score,
                    rec: res.data.recommendations || [],
                },
            }));
            setError(null);
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر حساب مؤشر التفاعل.')),
    });

    const quickPostStatusMutation = useMutation({
        mutationFn: ({ postId, status }: { postId: number; status: DigitalPostStatus }) =>
            digitalApi.updatePost(postId, { status }),
        onSuccess: async () => {
            setError(null);
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تحديث حالة المنشور.')),
    });

    const bulkTaskStatusMutation = useMutation({
        mutationFn: async (nextStatus: DigitalTaskStatus) => {
            const ids = selectedTaskIds.slice();
            if (!ids.length) throw new Error('حدد مهمة واحدة على الأقل.');
            await Promise.all(ids.map((taskId) => digitalApi.updateTask(taskId, { status: nextStatus })));
            return ids.length;
        },
        onSuccess: async (count) => {
            setSelectedTaskIds([]);
            setError(null);
            setMessage(`تم تحديث ${count} مهمة.`);
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تنفيذ الإجراء الجماعي.')),
    });

    const runNextActionMutation = useMutation({
        mutationFn: async (item: DigitalTaskActionItem) => {
            const taskId = item.task.id;
            const code = item.next_best_action_code;
            if (code === 'assign_owner') {
                if (!user?.id) throw new Error('تعذر تحديد المستخدم الحالي.');
                await digitalApi.updateTask(taskId, { owner_user_id: user.id });
                return 'تم تعيينك مالكًا للمهمة.';
            }
            if (code === 'start_task') {
                await digitalApi.updateTask(taskId, { status: 'in_progress' });
                return 'تم بدء التنفيذ.';
            }
            if (code === 'move_to_review') {
                await digitalApi.updateTask(taskId, { status: 'review' });
                return 'تم نقل المهمة للمراجعة.';
            }
            if (code === 'generate_posts') {
                const composed = await digitalApi.composeTask(taskId, { platform: 'facebook', max_hashtags: 6 });
                setSelectedTaskId(taskId);
                setPostPlatform('facebook');
                setPostContent(composed.data.recommended_text || '');
                setPostHashtags((composed.data.hashtags || []).join(', '));
                return 'تم توليد مسودة منشور وفتحها للتحرير.';
            }
            if (code === 'approve_posts') {
                const postList = await digitalApi.listTaskPosts(taskId);
                const candidate = (postList.data.items || []).find((post) => post.status === 'ready' || post.status === 'draft');
                if (!candidate) return 'لا توجد مادة قابلة للاعتماد حالياً.';
                await digitalApi.updatePost(candidate.id, { status: 'approved' });
                return 'تم اعتماد أول مادة جاهزة.';
            }
            if (code === 'publish_or_schedule') {
                const postList = await digitalApi.listTaskPosts(taskId);
                const candidate = (postList.data.items || []).find((post) => post.status === 'approved');
                if (!candidate) return 'لا توجد مادة معتمدة للنشر.';
                await digitalApi.updatePost(candidate.id, { status: 'scheduled', scheduled_at: new Date().toISOString() });
                return 'تمت جدولة المادة المعتمدة.';
            }
            if (code === 'recover_failed') {
                const postList = await digitalApi.listTaskPosts(taskId);
                const failed = (postList.data.items || []).find((post) => post.status === 'failed');
                if (!failed) return 'لا يوجد منشور فاشل لهذا العنصر.';
                await digitalApi.updatePost(failed.id, { status: 'draft', error_message: null });
                return 'تم استرجاع المنشور الفاشل إلى مسودة.';
            }
            return 'لا يوجد إجراء آلي لهذه المهمة حالياً.';
        },
        onSuccess: async (msg) => {
            setError(null);
            setMessage(msg);
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تنفيذ الإجراء التالي.')),
    });

    const composeSuggestionPending =
        composePostMutation.isPending ||
        createPostMutation.isPending ||
        generateBundleMutation.isPending ||
        regeneratePostMutation.isPending ||
        runNextActionMutation.isPending ||
        saveGeneratedPostsMutation.isPending;

    const runComposeSuggestion = () => {
        if (!composeSuggestion) return;
        if (composeSuggestion.taskKey === 'compose_post') {
            composePostMutation.mutate();
            return;
        }
        if (composeSuggestion.taskKey === 'generate_bundle') {
            generateBundleMutation.mutate();
            return;
        }
        if (composeSuggestion.taskKey === 'regenerate_post' && composeSuggestion.postId) {
            regeneratePostMutation.mutate(composeSuggestion.postId);
            return;
        }
        if (composeSuggestion.taskKey === 'run_next_action' && selectedTaskAction) {
            runNextActionMutation.mutate(selectedTaskAction);
            return;
        }
        if (Object.keys(composerGenerated || {}).length) {
            saveGeneratedPostsMutation.mutate();
            return;
        }
        createPostMutation.mutate();
    };

    const saveScopeMutation = useMutation({
        mutationFn: () =>
            digitalApi.updateScope(Number(scopeUserId), {
                can_manage_news: scopeNews,
                can_manage_tv: scopeTv,
                platforms: ['facebook', 'x', 'youtube'],
            }),
        onSuccess: async () => {
            setError(null);
            setMessage('تم تحديث صلاحيات مسؤول الديجيتال.');
            await refreshAll();
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذر تحديث الصلاحيات.')),
    });

    if (!canRead) {
        return <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-rose-200">ليس لديك صلاحية لواجهة فريق الديجيتال.</div>;
    }

    return (
        <div className="space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                        <Megaphone className="w-6 h-6 text-cyan-300" />
                        Digital Coverage Desk
                    </h1>
                    <div className="mt-1 inline-flex items-center gap-2 text-xs text-slate-300">
                        <span className="rounded-full border border-slate-700 bg-slate-900/60 px-2 py-0.5">{deskLabel(channel)}</span>
                        <span>Queue • Workspace • Execute</span>
                    </div>
                    <p className="text-sm text-gray-400 mt-1">طبقة تشغيل رقمية تُحوّل الخبر أو الحدث إلى مهام متعددة القنوات قابلة للتخطيط والتركيب والتنفيذ والمتابعة.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <button onClick={() => refreshAll()} className="h-10 px-3 rounded-xl border border-slate-500/30 bg-slate-500/10 text-slate-200 text-xs inline-flex items-center gap-1"><RefreshCcw className="w-4 h-4" />تحديث</button>
                    {canWrite && <button onClick={() => generateMutation.mutate()} className="h-10 px-3 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-xs inline-flex items-center gap-1"><Sparkles className="w-4 h-4" />توليد المهام</button>}
                    {canManage && <button onClick={() => importSlotsMutation.mutate(false)} className="h-10 px-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-xs inline-flex items-center gap-1"><UploadCloud className="w-4 h-4" />استيراد الشبكة</button>}
                </div>
            </div>

            {message && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-emerald-200 text-sm">{message}</div>}
            {error && <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-rose-200 text-sm">{error}</div>}
            {changesSinceLast && (
                <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-cyan-100 text-sm flex flex-wrap gap-4">
                    <span>جديد منذ آخر زيارة: {changesSinceLast.new_now} في Now</span>
                    <span>{changesSinceLast.new_risk} في At Risk</span>
                    <span>{changesSinceLast.moved_to_next} انتقلت إلى Next</span>
                </div>
            )}

            {deskMode === 'planning' && (
                <>
                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
                        {planningKpis.map((kpi) => (
                            <div key={kpi.label} className={cn('rounded-xl border p-3', kpi.tone)}>
                                <div className="text-xs text-gray-400">{kpi.label}</div>
                                <div className="text-2xl font-bold text-white">{kpi.value}</div>
                            </div>
                        ))}
                    </div>
                    <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                        <section className="xl:col-span-2 rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                            <div className="flex flex-wrap gap-2 items-center">
                                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="بحث..." className="h-10 w-full md:w-72 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white" />
                                <div className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white flex items-center">
                                    {deskLabel(channel)}
                                    <span className="ml-2 text-[10px] text-slate-400">مثبت حسب Desk</span>
                                </div>
                                <select value={status} onChange={(e) => setStatus(e.target.value as 'all' | DigitalTaskStatus)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white"><option value="all">كل الحالات</option><option value="todo">جديد</option><option value="in_progress">قيد التنفيذ</option><option value="review">مراجعة</option><option value="done">منجز</option><option value="cancelled">ملغي</option></select>
                                <select value={taskTypeFilter} onChange={(e) => setTaskTypeFilter(e.target.value)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white">
                                    <option value="all">كل أنواع المهام</option>
                                    {taskTypeOptions.map((type) => (
                                        <option key={type} value={type}>{type}</option>
                                    ))}
                                </select>
                                <label className="inline-flex items-center gap-2 px-3 h-10 rounded-xl border border-slate-700 bg-slate-900/60 text-xs text-slate-300">
                                    <input type="checkbox" checked={onlyMine} onChange={(e) => setOnlyMine(e.target.checked)} />
                                    مهامي فقط
                                </label>
                            </div>
                            {canWrite && (
                                <div className="flex flex-wrap items-center gap-2">
                                    <button onClick={() => setSelectedTaskIds(filteredTasks.map((task) => task.id))} className="h-8 px-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-xs">تحديد الكل</button>
                                    <button onClick={() => setSelectedTaskIds([])} className="h-8 px-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-xs">إلغاء التحديد</button>
                                    <button onClick={() => bulkTaskStatusMutation.mutate('in_progress')} disabled={!selectedTaskIds.length || bulkTaskStatusMutation.isPending} className="h-8 px-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-xs disabled:opacity-50">بدء جماعي</button>
                                    <button onClick={() => bulkTaskStatusMutation.mutate('review')} disabled={!selectedTaskIds.length || bulkTaskStatusMutation.isPending} className="h-8 px-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs disabled:opacity-50">مراجعة جماعية</button>
                                    <button onClick={() => bulkTaskStatusMutation.mutate('done')} disabled={!selectedTaskIds.length || bulkTaskStatusMutation.isPending} className="h-8 px-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-xs disabled:opacity-50">إغلاق جماعي</button>
                                    <div className="text-xs text-slate-400">المحدد: {selectedTaskIds.length}</div>
                                </div>
                            )}
                            <div className="max-h-[520px] overflow-auto rounded-xl border border-slate-800">
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-900/80 text-slate-300 sticky top-0"><tr><th className="text-right px-3 py-2">تحديد</th><th className="text-right px-3 py-2">المهمة</th><th className="text-right px-3 py-2">القناة</th><th className="text-right px-3 py-2">الحالة</th><th className="text-right px-3 py-2">الاستحقاق</th><th className="text-right px-3 py-2">الإجراء التالي</th><th className="text-right px-3 py-2">إجراءات</th></tr></thead>
                                    <tbody>
                                        {filteredTasks.map((task) => (
                                            <tr key={task.id} className={cn('border-t border-slate-800 hover:bg-slate-900/50 cursor-pointer', selectedTaskId === task.id && 'bg-cyan-500/10')} onClick={() => setSelectedTaskId(task.id)}>
                                                <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                                                    <input type="checkbox" checked={selectedTaskIds.includes(task.id)} onChange={(e) => toggleTaskSelection(task.id, e.target.checked)} />
                                                </td>
                                                <td className="px-3 py-2">
                                                    <div className="text-white font-medium">{task.title}</div>
                                                    <div className="text-xs text-slate-500 mt-1">{task.brief || 'بدون وصف'}</div>
                                                    <div className="text-[11px] text-slate-500 mt-1">{task.task_type} {task.owner_username ? `• ${task.owner_username}` : ''}</div>
                                                    {actionDeskItems.get(task.id)?.why_now && <div className="text-[11px] text-cyan-300/80 mt-1">{actionDeskItems.get(task.id)?.why_now}</div>}
                                                </td>
                                                <td className="px-3 py-2 text-slate-300">{channelLabel(task.channel)}</td>
                                                <td className="px-3 py-2"><span className={cn('inline-flex px-2 py-0.5 rounded-lg border text-xs', taskStatusClass(task.status))}>{taskStatusLabel(task.status)}</span></td>
                                                <td className="px-3 py-2 text-slate-300">{task.due_at ? <div><div>{formatDate(task.due_at)}</div><div className="text-xs text-slate-500">{formatRelativeTime(task.due_at)}</div></div> : '—'}</td>
                                                <td className="px-3 py-2">
                                                    {actionDeskItems.get(task.id) ? (
                                                        <div className="space-y-1">
                                                            <span className={cn('inline-flex px-2 py-0.5 rounded-lg border text-xs', actionCodeClass(actionDeskItems.get(task.id)?.next_best_action_code || ''))}>{actionDeskItems.get(task.id)?.next_best_action || '—'}</span>
                                                            {!!actionDeskItems.get(task.id)?.risk_flags?.length && <div className="text-[11px] text-rose-300">{actionDeskItems.get(task.id)?.risk_flags.join('، ')}</div>}
                                                        </div>
                                                    ) : (
                                                        <span className="text-xs text-slate-500">—</span>
                                                    )}
                                                </td>
                                                <td className="px-3 py-2">
                                                    {canWrite && <div className="flex gap-1 flex-wrap">
                                                        {actionDeskItems.get(task.id) && <button onClick={(e) => { e.stopPropagation(); runNextActionMutation.mutate(actionDeskItems.get(task.id) as DigitalTaskActionItem); }} className="text-xs px-2 py-1 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">التالي</button>}
                                                        {user?.id && task.owner_user_id !== user.id && <button onClick={(e) => { e.stopPropagation(); claimTaskMutation.mutate(task.id); }} className="text-xs px-2 py-1 rounded-lg border border-slate-500/30 bg-slate-500/10 text-slate-200">استلام</button>}
                                                        {task.status !== 'in_progress' && <button onClick={(e) => { e.stopPropagation(); updateTaskMutation.mutate({ taskId: task.id, nextStatus: 'in_progress' }); }} className="text-xs px-2 py-1 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">بدء</button>}
                                                        {task.status !== 'review' && task.status !== 'done' && <button onClick={(e) => { e.stopPropagation(); updateTaskMutation.mutate({ taskId: task.id, nextStatus: 'review' }); }} className="text-xs px-2 py-1 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200">مراجعة</button>}
                                                        {task.status !== 'done' && <button onClick={(e) => { e.stopPropagation(); updateTaskMutation.mutate({ taskId: task.id, nextStatus: 'done' }); }} className="text-xs px-2 py-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">إغلاق</button>}
                                                    </div>}
                                                </td>
                                            </tr>
                                        ))}
                                        {!filteredTasks.length && <tr><td colSpan={7} className="px-3 py-8 text-center text-slate-500">لا توجد مهام مطابقة للفلاتر.</td></tr>}
                                    </tbody>
                                </table>
                            </div>
                        </section>
                        <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                            <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><PlusCircle className="w-4 h-4 text-cyan-300" />إضافة مهمة</h2>
                            <input value={taskTitle} onChange={(e) => setTaskTitle(e.target.value)} placeholder="عنوان المهمة" className="h-10 w-full rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white" />
                            <textarea value={taskBrief} onChange={(e) => setTaskBrief(e.target.value)} placeholder="وصف مختصر" rows={3} className="w-full rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm text-white" />
                            <div className="grid grid-cols-2 gap-2">
                                <select value={taskChannel} onChange={(e) => setTaskChannel(e.target.value as DigitalChannel)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white"><option value="news">الشروق نيوز</option><option value="tv">الشروق تي في</option></select>
                                <input type="datetime-local" value={taskDueAt} onChange={(e) => setTaskDueAt(e.target.value)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white" />
                            </div>
                            <button onClick={() => createTaskMutation.mutate()} disabled={!canWrite || !taskTitle.trim()} className="h-10 w-full rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-sm disabled:opacity-50">حفظ المهمة</button>
                            <div className="pt-3 border-t border-slate-800">
                                <h3 className="text-sm text-slate-200 mb-2 flex items-center gap-1"><CalendarDays className="w-4 h-4 text-indigo-300" />روزنامة 7 أيام</h3>
                                <div className="space-y-2 max-h-48 overflow-auto">
                                    {(calendarQuery.data?.data?.items || []).slice(0, 12).map((item, idx) => (
                                        <div key={`${item.item_type}-${item.reference_id}-${idx}`} className="rounded-lg border border-slate-800 bg-slate-900/50 p-2 text-xs text-slate-300">
                                            <div>{item.title}</div><div className="text-slate-500 mt-1">{formatDate(item.starts_at)} • {channelLabel(item.channel)}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </section>
                    </div>
                </>
            )}

            <div className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-2">
                <div className="flex flex-wrap gap-2 items-center">
                    <button
                        onClick={() => setDesk('news')}
                        className={cn(
                            'h-9 px-3 rounded-xl border text-xs',
                            desk === 'news'
                                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                                : 'border-slate-700 bg-slate-900/60 text-slate-300'
                        )}
                    >
                        News Desk
                    </button>
                    <button
                        onClick={() => setDesk('tv')}
                        className={cn(
                            'h-9 px-3 rounded-xl border text-xs',
                            desk === 'tv'
                                ? 'border-purple-500/30 bg-purple-500/10 text-purple-200'
                                : 'border-slate-700 bg-slate-900/60 text-slate-300'
                        )}
                    >
                        TV/Program Desk
                    </button>
                    <span className="text-[11px] text-slate-500">القناة الحالية: {channelLabel(channel)}</span>
                    <button
                        onClick={() => setDeskMode('execute')}
                        className={cn(
                            'h-9 px-3 rounded-xl border text-xs',
                            deskMode === 'execute'
                                ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200'
                                : 'border-slate-700 bg-slate-900/60 text-slate-300'
                        )}
                    >
                        Execute
                    </button>
                    <button
                        onClick={() => setDeskMode('compose')}
                        className={cn(
                            'h-9 px-3 rounded-xl border text-xs',
                            deskMode === 'compose'
                                ? 'border-indigo-500/30 bg-indigo-500/10 text-indigo-200'
                                : 'border-slate-700 bg-slate-900/60 text-slate-300'
                        )}
                    >
                        Compose
                    </button>
                    <button
                        onClick={() => setDeskMode('planning')}
                        className={cn(
                            'h-9 px-3 rounded-xl border text-xs',
                            deskMode === 'planning'
                                ? 'border-amber-500/30 bg-amber-500/10 text-amber-200'
                                : 'border-slate-700 bg-slate-900/60 text-slate-300'
                        )}
                    >Planning</button>
                </div>
            </div>

            {deskMode === 'execute' && (
            <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                    <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                        <ArrowRightCircle className="w-4 h-4 text-cyan-300" />
                        طابور التغطية الرقمية
                    </h2>
                    <div className="text-xs text-slate-400">Now / Next / At Risk</div>
                </div>
                <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
                    {[
                        {
                            key: 'now',
                            title: `Now (${actionDesk?.now_count || 0})`,
                            items: actionDesk?.now || [],
                            empty: 'لا توجد مهام حرجة الآن.',
                            tone: 'border-cyan-500/20 bg-cyan-500/5',
                        },
                        {
                            key: 'next',
                            title: `Next (${actionDesk?.next_count || 0})`,
                            items: actionDesk?.next || [],
                            empty: 'لا توجد مهام خلال الساعتين القادمتين.',
                            tone: 'border-indigo-500/20 bg-indigo-500/5',
                        },
                        {
                            key: 'risk',
                            title: `At Risk (${actionDesk?.at_risk_count || 0})`,
                            items: actionDesk?.at_risk || [],
                            empty: 'لا توجد مهام مهددة حالياً.',
                            tone: 'border-rose-500/20 bg-rose-500/5',
                        },
                    ].map((group) => (
                        <div key={group.key} className={cn('rounded-xl border p-3 space-y-2', group.tone)}>
                            <div className="text-sm font-medium text-white">{group.title}</div>
                            <div className="space-y-2 max-h-64 overflow-auto">
                                {group.items.map((item) => (
                                    <div key={`${group.key}-${item.task.id}`} className="rounded-lg border border-slate-800 bg-slate-900/60 p-2">
                                        <div className="flex items-center justify-between gap-2">
                                            <button
                                                onClick={() => setSelectedTaskId(item.task.id)}
                                                className="text-right text-xs text-cyan-200 hover:text-cyan-100"
                                            >
                                                {item.task.title}
                                            </button>
                                            <span className={cn('inline-flex px-2 py-0.5 rounded-lg border text-[10px]', actionCodeClass(item.next_best_action_code))}>
                                                {actionCodeLabel(item.next_best_action_code)}
                                            </span>
                                        </div>
                                        <div className="mt-1 flex flex-wrap gap-1 text-[10px] text-slate-300">
                                            <span className="rounded-md border border-slate-700 bg-slate-900/70 px-2 py-0.5">
                                                المصدر: {item.source_type || 'task'}
                                            </span>
                                            {item.source_ref && (
                                                <span className="rounded-md border border-slate-700 bg-slate-900/70 px-2 py-0.5">
                                                    المرجع: {item.source_ref}
                                                </span>
                                            )}
                                            {item.task.owner_username && (
                                                <span className="rounded-md border border-slate-700 bg-slate-900/70 px-2 py-0.5">
                                                    المسؤول: {item.task.owner_username}
                                                </span>
                                            )}
                                        </div>
                                        <div className="text-[11px] text-slate-400 mt-1">{item.why_now}</div>
                                        {!!item.risk_flags?.length && (
                                            <div className="mt-1 flex flex-wrap gap-1">
                                                {item.risk_flags.map((flag) => (
                                                    <span key={flag} className="inline-flex rounded-md border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] text-rose-200">
                                                        {flag}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                        {canWrite && (
                                            <button
                                                onClick={() => runNextActionMutation.mutate(item)}
                                                className="mt-2 h-7 px-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-[11px] disabled:opacity-50"
                                                disabled={runNextActionMutation.isPending}
                                            >
                                                تنفيذ: {item.next_best_action}
                                            </button>
                                        )}
                                    </div>
                                ))}
                                {!group.items.length && <div className="text-xs text-slate-500">{group.empty}</div>}
                            </div>
                        </div>
                    ))}
                </div>
                {!!failedRiskItems.length && (
                    <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3">
                        <div className="text-xs text-rose-200 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" />
                            Recovery Desk: توجد {failedRiskItems.length} مهمة بها منشورات فاشلة.
                        </div>
                    </div>
                )}
            </section>
            )}

            {deskMode === 'execute' && (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                        {operationalKpis.map((kpi) => (
                            <div key={kpi.label} className={cn('rounded-xl border p-3', kpi.tone)}>
                                <div className="text-xs text-gray-400">{kpi.label}</div>
                                <div className="text-2xl font-bold text-white">{kpi.value}</div>
                            </div>
                        ))}
                    </div>
                    <div className="grid grid-cols-1 xl:grid-cols-[1.15fr_0.85fr] gap-4">
                        <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                            <div className="flex items-center justify-between gap-2">
                                <div>
                                    <h2 className="text-sm font-semibold text-slate-200">Task Queue</h2>
                                    <p className="text-xs text-slate-400 mt-1">ترتيب ذكي حسب الاستعجال والمخاطر والنافذة الزمنية.</p>
                                </div>
                                <div className="text-xs text-slate-500">{executeQueue.length} مهام</div>
                            </div>
                            {canWrite && (
                                <div className="flex flex-wrap items-center gap-2">
                                    <button onClick={() => setSelectedTaskIds(executeQueue.map((item) => item.task.id))} className="h-8 px-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-xs">تحديد الكل</button>
                                    <button onClick={() => setSelectedTaskIds([])} className="h-8 px-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-xs">إلغاء التحديد</button>
                                    <button onClick={() => bulkTaskStatusMutation.mutate('review')} disabled={!selectedTaskIds.length || bulkTaskStatusMutation.isPending} className="h-8 px-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs disabled:opacity-50">Move to Review</button>
                                    <button onClick={() => bulkTaskStatusMutation.mutate('done')} disabled={!selectedTaskIds.length || bulkTaskStatusMutation.isPending} className="h-8 px-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-xs disabled:opacity-50">Close Selected</button>
                                    <div className="text-xs text-slate-400">المحدد: {selectedTaskIds.length}</div>
                                </div>
                            )}
                            <div className="space-y-3 max-h-[720px] overflow-auto pr-1">
                                {executeQueue.map((item) => {
                                    const task = item.task;
                                    return (
                                        <div key={task.id} className={cn('rounded-2xl border p-3 transition-colors', selectedTaskId === task.id ? 'border-cyan-500/30 bg-cyan-500/10' : 'border-slate-800 bg-slate-900/50')}>
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="space-y-2 flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <input type="checkbox" checked={selectedTaskIds.includes(task.id)} onChange={(e) => toggleTaskSelection(task.id, e.target.checked)} />
                                                        <button onClick={() => setSelectedTaskId(task.id)} className="text-right text-sm font-medium text-white hover:text-cyan-200">{task.title}</button>
                                                    </div>
                                                    <div className="text-xs text-cyan-200">{item.why_now}</div>
                                                    <div className="text-xs text-slate-400 line-clamp-2">{task.brief || 'بدون brief تحريري.'}</div>
                                                    <div className="flex flex-wrap gap-2 text-[11px]">
                                                        <span className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">{channelLabel(task.channel)}</span>
                                                        <span className={cn('rounded-lg border px-2 py-1', taskStatusClass(task.status))}>{taskStatusLabel(task.status)}</span>
                                                        <span className={cn('rounded-lg border px-2 py-1', actionCodeClass(item.next_best_action_code))}>{item.next_best_action}</span>
                                                        {task.owner_username && <span className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">{task.owner_username}</span>}
                                                        {task.due_at && <span className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">{formatRelativeTime(task.due_at)}</span>}
                                                    </div>
                                                    {!!item.risk_flags?.length && (
                                                        <div className="flex flex-wrap gap-1">
                                                            {item.risk_flags.map((flag) => (
                                                                <span key={flag} className="rounded-md border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] text-rose-200">{flag}</span>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="flex flex-col gap-2 shrink-0">
                                                    <button onClick={() => { setSelectedTaskId(task.id); setDeskMode('compose'); }} className="h-8 px-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-200 text-xs">Workspace</button>
                                                    {canWrite && <button onClick={() => runNextActionMutation.mutate(item)} disabled={runNextActionMutation.isPending} className="h-8 px-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-xs disabled:opacity-50">نفّذ الآن</button>}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                                {!executeQueue.length && <div className="text-sm text-slate-500">لا توجد مهام تشغيلية حالياً.</div>}
                            </div>
                        </section>
                        <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                            <div className="flex items-center justify-between gap-2">
                                <div>
                                    <h2 className="text-sm font-semibold text-slate-200">Coverage Workspace — Execute</h2>
                                    <p className="text-xs text-slate-400 mt-1">نافذة تنفيذ سريعة قبل الدخول إلى Workspace الكامل.</p>
                                </div>
                                {selectedTask && <button onClick={() => setDeskMode('compose')} className="h-8 px-2 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-200 text-xs">فتح Compose</button>}
                            </div>
                            {!selectedTask && <div className="text-sm text-slate-400">اختر مهمة من Task Queue لبدء التنفيذ السريع.</div>}
                            {selectedTask && (
                                <div className="space-y-3">
                                    <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
                                        <div className="text-sm text-white font-medium">{selectedTask.title}</div>
                                        <div className="text-xs text-slate-400 mt-1">{selectedTask.brief || 'بدون brief تحريري.'}</div>
                                    </div>
                                    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
                                        <div className="text-xs text-slate-300 mb-2">Coverage Object</div>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                                            {buildCoverageMeta(selectedTask, selectedTaskAction).map((item) => (
                                                <div key={item.label} className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">
                                                    {item.label}: {item.value}
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    {selectedTaskAction && (
                                        <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-3 space-y-2">
                                            <div className="text-xs text-slate-300">Trigger Layer</div>
                                            <div className="text-sm text-white">{selectedTaskAction.why_now}</div>
                                            <div className="grid grid-cols-2 gap-2 text-xs">
                                                <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">المصدر: {selectedTaskAction.source_type || 'task'}</div>
                                                <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">النافذة: {selectedTaskAction.trigger_window || '—'}</div>
                                            </div>
                                        </div>
                                    )}
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                        <select value={postPlatform} onChange={(e) => setPostPlatform(e.target.value)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white"><option value="facebook">facebook</option><option value="x">x</option><option value="youtube">youtube</option><option value="tiktok">tiktok</option><option value="instagram">instagram</option></select>
                                        <select value={postStatus} onChange={(e) => setPostStatus(e.target.value as DigitalPostStatus)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white"><option value="draft">مسودة</option><option value="ready">جاهز</option><option value="approved">معتمد</option><option value="scheduled">مجدول</option></select>
                                    </div>
                                    <input value={postHashtags} onChange={(e) => setPostHashtags(e.target.value)} placeholder="وسوم" className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white" />
                                    {canWrite && (
                                        <div className="flex gap-2">
                                            <button onClick={() => composePostMutation.mutate()} disabled={composePostMutation.isPending} className="h-10 flex-1 rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-indigo-200 text-sm disabled:opacity-50">صياغة سريعة</button>
                                            {selectedTaskAction && <button onClick={() => runNextActionMutation.mutate(selectedTaskAction)} disabled={runNextActionMutation.isPending} className="h-10 flex-1 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-sm disabled:opacity-50">{selectedTaskAction.next_best_action}</button>}
                                        </div>
                                    )}
                                    <textarea value={postContent} onChange={(e) => setPostContent(e.target.value)} rows={4} placeholder="نص المنشور" className="w-full rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm text-white" />
                                    <div className={cn('text-xs', postDraftLength.over ? 'text-rose-300' : 'text-slate-400')}>طول النص: {postDraftLength.count}/{postDraftLength.limit}</div>
                                    <button onClick={() => createPostMutation.mutate()} disabled={!canWrite || !postContent.trim() || postDraftLength.over} className="h-10 w-full rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-sm disabled:opacity-50">حفظ المادة</button>
                                    <div className="space-y-2">
                                        {posts.slice(0, 3).map((post) => (
                                            <div key={post.id} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
                                                <div className="flex items-center justify-between gap-2">
                                                    <div className="text-sm text-white">{post.platform}</div>
                                                    <span className={cn('inline-flex px-2 py-0.5 rounded-lg border text-xs', postStatusClass(post.status))}>{postStatusLabel(post.status)}</span>
                                                </div>
                                                <div className="text-xs text-slate-300 mt-2 line-clamp-3">{post.content_text}</div>
                                            </div>
                                        ))}
                                        {!posts.length && <div className="text-xs text-slate-500">لا توجد مواد بعد لهذه المهمة.</div>}
                                    </div>
                                </div>
                            )}
                        </section>
                    </div>
                </>
            )}

            {deskMode === 'planning' && (
            <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                <h2 className="text-sm font-semibold text-slate-200">مولّد منشورات البرامج/المسلسلات</h2>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                    <select
                        value={composerSlotId}
                        onChange={(e) => setComposerSlotId(e.target.value)}
                        className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white md:col-span-2"
                    >
                        <option value="">اختر البرنامج أو المسلسل</option>
                        {(slotsQuery.data?.data || []).map((slot) => (
                            <option key={slot.id} value={String(slot.id)}>
                                {slot.program_title} - {channelLabel(slot.channel)} - {slot.start_time}
                            </option>
                        ))}
                    </select>
                    <button
                        onClick={() => generateFromProgramMutation.mutate()}
                        disabled={!canWrite || generateFromProgramMutation.isPending}
                        className="h-10 rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-indigo-200 text-sm disabled:opacity-50"
                    >
                        توليد حسب المنصات
                    </button>
                    <button
                        onClick={() => generateAndSaveMutation.mutate()}
                        disabled={!canWrite || generateAndSaveMutation.isPending}
                        className="h-10 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-sm disabled:opacity-50"
                    >
                        توليد + حفظ مباشر
                    </button>
                </div>
                <textarea
                    value={composerDraft}
                    onChange={(e) => setComposerDraft(e.target.value)}
                    rows={3}
                    placeholder="المسودة التي تشرح المقطع..."
                    className="w-full rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm text-white"
                />
                <div className="flex flex-wrap gap-2">
                    {PLATFORM_OPTIONS.map((platform) => {
                        const active = composerPlatforms.includes(platform);
                        return (
                            <button
                                key={platform}
                                onClick={() => toggleComposerPlatform(platform)}
                                type="button"
                                className={cn(
                                    'px-3 h-9 rounded-xl border text-xs',
                                    active
                                        ? 'border-cyan-500/30 bg-cyan-500/10 text-cyan-200'
                                        : 'border-slate-700 bg-slate-900/60 text-slate-300'
                                )}
                            >
                                {platform}
                            </button>
                        );
                    })}
                </div>

                {!!Object.keys(composerGenerated || {}).length && (
                    <div className="space-y-2">
                        {Object.entries(composerGenerated).map(([platform, value]) => {
                            const length = postLengthState(platform, value.text || '');
                            return (
                            <div key={platform} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                    <div className="text-sm text-white font-medium">{platform}</div>
                                    <div className="flex items-center gap-2">
                                        <span className={cn('text-[11px]', length.over ? 'text-rose-300' : 'text-slate-400')}>
                                            {length.count}/{length.limit}
                                        </span>
                                        <button
                                            onClick={() => copySimple(value.text)}
                                            className="h-8 px-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-xs inline-flex items-center gap-1"
                                        >
                                            <Copy className="w-3 h-3" />
                                            نسخ
                                        </button>
                                        <button
                                            onClick={() => copySimple(composeCopyText(value.text, value.hashtags || []))}
                                            className="h-8 px-2 rounded-lg border border-cyan-600/40 bg-cyan-900/20 text-cyan-200 text-xs"
                                        >
                                            نسخ كامل
                                        </button>
                                    </div>
                                </div>
                                <textarea
                                    value={value.text}
                                    onChange={(e) =>
                                        setComposerGenerated((prev) => ({
                                            ...prev,
                                            [platform]: { ...prev[platform], text: e.target.value },
                                        }))
                                    }
                                    rows={3}
                                    className="w-full rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm text-white"
                                />
                                <input
                                    value={(value.hashtags || []).join(', ')}
                                    onChange={(e) =>
                                        setComposerGenerated((prev) => ({
                                            ...prev,
                                            [platform]: {
                                                ...prev[platform],
                                                hashtags: e.target.value
                                                    .split(',')
                                                    .map((s) => s.trim())
                                                    .filter(Boolean),
                                            },
                                        }))
                                    }
                                    placeholder="وسوم"
                                    className="h-9 w-full rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-xs text-white"
                                />
                            </div>
                        )})}
                        <button
                            onClick={() => saveGeneratedPostsMutation.mutate()}
                            disabled={!canWrite || saveGeneratedPostsMutation.isPending || composerHasOverLimit}
                            className="h-10 w-full rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-sm disabled:opacity-50"
                        >
                            حفظ كل الصياغات
                        </button>
                    </div>
                )}
            </section>
            )}

            {deskMode === 'compose' && (
            <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                <h2 className="text-sm font-semibold text-slate-200">Coverage Workspace — Compose</h2>
                {!selectedTask && <div className="text-sm text-slate-400">اختر مهمة من الجدول.</div>}
                {selectedTask && (
                    <div className="space-y-3">
                        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 text-sm text-slate-200">{selectedTask.title}</div>
                        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
                            <div className="text-xs text-slate-300 mb-2">Coverage Object</div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                                {buildCoverageMeta(selectedTask, actionDeskItems.get(selectedTask.id) || null).map((item) => (
                                    <div key={item.label} className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">
                                        {item.label}: {item.value}
                                    </div>
                                ))}
                            </div>
                        </div>
                        {composeSuggestion && (
                            <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-3 space-y-3">
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div className="space-y-1">
                                        <div className="text-xs text-cyan-300">القالب الذكي المقترح الآن</div>
                                        <div className="text-sm font-semibold text-white">{composeSuggestion.taskLabel}</div>
                                        <div className="text-sm leading-6 text-slate-200">{composeSuggestion.reason}</div>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        <button
                                            onClick={runComposeSuggestion}
                                            disabled={!canWrite || composeSuggestionPending}
                                            className="h-10 rounded-xl border border-cyan-500/30 bg-cyan-500/15 px-4 text-sm text-cyan-100 disabled:opacity-50"
                                        >
                                            {composeSuggestionPending ? 'جارٍ التنفيذ...' : composeSuggestion.actionLabel}
                                        </button>
                                        <Link href={composeSuggestion.playbookHref} className="inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-slate-200">
                                            افتح دليل البرومبت
                                        </Link>
                                    </div>
                                </div>
                                <div className="grid grid-cols-1 gap-2 md:grid-cols-3 text-xs">
                                    {composeSuggestion.autoFilledFields.map((field) => (
                                        <div key={field.label} className="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2">
                                            <div className="text-slate-400">{field.label}</div>
                                            <div className="mt-1 text-sm text-white">{field.value}</div>
                                        </div>
                                    ))}
                                </div>
                                <details className="rounded-lg border border-slate-700 bg-slate-950/50 p-3">
                                    <summary className="cursor-pointer text-xs text-cyan-200">كيف يملأ النظام هذا القالب تلقائيًا؟</summary>
                                    <pre className="mt-3 whitespace-pre-wrap text-xs leading-6 text-slate-300">{composeSuggestion.promptPreview}</pre>
                                </details>
                            </div>
                        )}
                        {actionDeskItems.get(selectedTask.id) && (
                            <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-3 space-y-2">
                                <div className="text-xs text-slate-300">Trigger Layer</div>
                                <div className="text-sm text-white">{actionDeskItems.get(selectedTask.id)?.why_now}</div>
                                <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs">
                                    <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">المصدر: {actionDeskItems.get(selectedTask.id)?.source_type || 'task'}</div>
                                    <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">النافذة: {actionDeskItems.get(selectedTask.id)?.trigger_window || '—'}</div>
                                    <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">إنشاء: {actionDeskItems.get(selectedTask.id)?.auto_generated ? 'آلي' : 'يدوي'}</div>
                                    <div className="rounded-lg border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">المرجع: {actionDeskItems.get(selectedTask.id)?.source_ref || '—'}</div>
                                </div>
                            </div>
                        )}
                        <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-3 space-y-2">
                            <div className="text-xs text-slate-300">Digital Pack Model</div>
                            <div className="flex flex-wrap gap-2 items-center">
                                <select
                                    value={bundlePlaybookKey}
                                    onChange={(e) => setBundlePlaybookKey(e.target.value)}
                                    className="h-9 min-w-[220px] rounded-lg border border-slate-700 bg-slate-900/60 px-3 text-xs text-white"
                                >
                                {(deskPlaybooks || []).map((pb) => (
                                    <option key={pb.key} value={pb.key}>{pb.label}</option>
                                ))}
                                {!deskPlaybooks.length && <option value="breaking_alert">Breaking Alert</option>}
                            </select>
                                <button
                                    onClick={() => generateBundleMutation.mutate()}
                                    disabled={!canWrite || generateBundleMutation.isPending}
                                    className="h-9 px-3 rounded-lg border border-indigo-500/30 bg-indigo-500/10 text-indigo-200 text-xs disabled:opacity-50"
                                >
                                    توليد باقة رقمية
                                </button>
                            </div>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                            <select value={postPlatform} onChange={(e) => setPostPlatform(e.target.value)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white"><option value="facebook">facebook</option><option value="x">x</option><option value="youtube">youtube</option><option value="tiktok">tiktok</option><option value="instagram">instagram</option></select>
                            <select value={postStatus} onChange={(e) => setPostStatus(e.target.value as DigitalPostStatus)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white"><option value="draft">مسودة</option><option value="ready">جاهز</option><option value="approved">معتمد</option><option value="scheduled">مجدول</option></select>
                            <input value={postHashtags} onChange={(e) => setPostHashtags(e.target.value)} placeholder="وسوم" className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white" />
                            <input type="datetime-local" value={postScheduledAt} onChange={(e) => setPostScheduledAt(e.target.value)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white" />
                        </div>
                        {canWrite && (
                            <button
                                onClick={() => composePostMutation.mutate()}
                                disabled={composePostMutation.isPending}
                                className="h-10 rounded-xl border border-indigo-500/30 bg-indigo-500/10 text-indigo-200 text-sm disabled:opacity-50"
                            >
                                صياغة تلقائية للمنشور
                            </button>
                        )}
                        {coveragePack && (
                            <div className="rounded-xl border border-slate-700 bg-slate-900/40 p-3 space-y-3">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div>
                                        <div className="text-xs text-cyan-300">Pack Variants</div>
                                        <div className="text-sm text-slate-200">نسخ متعددة جاهزة للتنفيذ والمراجعة</div>
                                    </div>
                                    <button
                                        onClick={() =>
                                            copySimple(
                                                [
                                                    coveragePack.core_statement,
                                                    coveragePack.headline_short,
                                                    coveragePack.summary_mobile,
                                                    coveragePack.push_text,
                                                    coveragePack.social_text,
                                                ]
                                                    .filter(Boolean)
                                                    .join('\n\n')
                                            )
                                        }
                                        className="h-8 px-3 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-xs"
                                    >
                                        نسخ الحزمة
                                    </button>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                                    {coveragePack.headline_short && (
                                        <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3 space-y-2">
                                            <div className="text-slate-400">عنوان رقمي قصير</div>
                                            <div className="text-sm text-white">{coveragePack.headline_short}</div>
                                            <button onClick={() => copySimple(coveragePack.headline_short || '')} className="h-7 px-2 rounded-md border border-slate-600 bg-slate-800/60 text-slate-200 text-[11px]">نسخ</button>
                                        </div>
                                    )}
                                    {coveragePack.core_statement && (
                                        <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3 space-y-2">
                                            <div className="text-slate-400">جملة الجوهر</div>
                                            <div className="text-sm text-white">{coveragePack.core_statement}</div>
                                            <button onClick={() => copySimple(coveragePack.core_statement || '')} className="h-7 px-2 rounded-md border border-slate-600 bg-slate-800/60 text-slate-200 text-[11px]">نسخ</button>
                                        </div>
                                    )}
                                    {coveragePack.summary_mobile && (
                                        <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3 space-y-2">
                                            <div className="text-slate-400">ملخص للجوال</div>
                                            <div className="text-sm text-white">{coveragePack.summary_mobile}</div>
                                            <button onClick={() => copySimple(coveragePack.summary_mobile || '')} className="h-7 px-2 rounded-md border border-slate-600 bg-slate-800/60 text-slate-200 text-[11px]">نسخ</button>
                                        </div>
                                    )}
                                    {coveragePack.push_text && (
                                        <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3 space-y-2">
                                            <div className="text-slate-400">إشعار دفع</div>
                                            <div className="text-sm text-white">{coveragePack.push_text}</div>
                                            <button onClick={() => copySimple(coveragePack.push_text || '')} className="h-7 px-2 rounded-md border border-slate-600 bg-slate-800/60 text-slate-200 text-[11px]">نسخ</button>
                                        </div>
                                    )}
                                    {coveragePack.social_text && (
                                        <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-3 space-y-2 md:col-span-2">
                                            <div className="text-slate-400">صيغة سوشيال</div>
                                            <div className="text-sm text-white whitespace-pre-wrap">{coveragePack.social_text}</div>
                                            <button onClick={() => copySimple(coveragePack.social_text || '')} className="h-7 px-2 rounded-md border border-slate-600 bg-slate-800/60 text-slate-200 text-[11px]">نسخ</button>
                                        </div>
                                    )}
                                    {coveragePack.breaking_alert && (
                                        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 space-y-2 md:col-span-2">
                                            <div className="text-rose-200">تنبيه عاجل</div>
                                            <div className="text-sm text-white whitespace-pre-wrap">{coveragePack.breaking_alert}</div>
                                            <button onClick={() => copySimple(coveragePack.breaking_alert || '')} className="h-7 px-2 rounded-md border border-rose-500/40 bg-rose-500/10 text-rose-200 text-[11px]">نسخ</button>
                                        </div>
                                    )}
                                </div>
                                {!!coveragePack.checks?.length && (
                                    <div className="space-y-2">
                                        <div className="text-xs text-slate-400">ملاحظات جودة سريعة</div>
                                        <div className="flex flex-wrap gap-2">
                                            {coveragePack.checks.map((check, idx) => (
                                                <span key={`${check.code}-${idx}`} className={cn('inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[11px]', coverageCheckClass(check.level))}>
                                                    <AlertTriangle className="w-3 h-3" />
                                                    {coverageCheckLabel(check.code)}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                        <textarea value={postContent} onChange={(e) => setPostContent(e.target.value)} rows={3} placeholder="نص المنشور" className="w-full rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm text-white" />
                        <div className={cn('text-xs', postDraftLength.over ? 'text-rose-300' : 'text-slate-400')}>
                            طول النص: {postDraftLength.count}/{postDraftLength.limit}
                        </div>
                        <button onClick={() => createPostMutation.mutate()} disabled={!canWrite || !postContent.trim() || postDraftLength.over} className="h-10 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-sm disabled:opacity-50">حفظ المادة</button>
                        <div className="space-y-2">
                            {posts.map((post) => (
                                <div key={post.id} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
                                    <div className="flex flex-wrap items-center justify-between gap-2"><div className="text-sm text-white">{post.platform}</div><span className={cn('inline-flex px-2 py-0.5 rounded-lg border text-xs', postStatusClass(post.status))}>{postStatusLabel(post.status)}</span></div>
                                    <p className="text-sm text-slate-200 mt-2 whitespace-pre-wrap">{post.content_text}</p>
                                    {!!(post.hashtags || []).length && (
                                        <div className="text-xs text-slate-400 mt-2">{(post.hashtags || []).map((tag) => `#${String(tag).replace(/^#/, '')}`).join(' ')}</div>
                                    )}
                                    <div className="mt-2 grid grid-cols-1 md:grid-cols-3 gap-2 text-[11px]">
                                        <div className="rounded-md border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">المنصة: {normalizePlatform(post.platform)}</div>
                                        <div className="rounded-md border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">الهدف: {taskObjectiveLabel(selectedTask.task_type)}</div>
                                        <div className="rounded-md border border-slate-700 bg-slate-900/60 px-2 py-1 text-slate-300">المنشأ: {post.created_by_username === 'system' ? 'AI/Auto' : 'Manual'}</div>
                                    </div>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                        <button onClick={() => copySimple(post.content_text)} className="h-8 px-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-xs inline-flex items-center gap-1"><Copy className="w-3 h-3" />نسخ النص</button>
                                        <button onClick={() => copySimple(composeCopyText(post.content_text, post.hashtags || []))} className="h-8 px-2 rounded-lg border border-cyan-600/40 bg-cyan-900/20 text-cyan-200 text-xs">نسخ كامل</button>
                                        <button onClick={() => openComposer(post.platform)} className="h-8 px-2 rounded-lg border border-indigo-600/40 bg-indigo-900/20 text-indigo-200 text-xs">فتح المنصة</button>
                                        <button onClick={() => copyAndOpenComposer(post.platform, post.content_text, post.hashtags || [])} className="h-8 px-2 rounded-lg border border-emerald-600/40 bg-emerald-900/20 text-emerald-200 text-xs">نسخ + فتح</button>
                                        <button onClick={() => engagementMutation.mutate(post.id)} className="h-8 px-2 rounded-lg border border-violet-600/40 bg-violet-900/20 text-violet-200 text-xs">Engagement</button>
                                        <button onClick={() => regeneratePostMutation.mutate(post.id)} className="h-8 px-2 rounded-lg border border-sky-600/40 bg-sky-900/20 text-sky-200 text-xs">Regenerate</button>
                                        <button onClick={() => duplicatePostVersionMutation.mutate({ postId: post.id })} className="h-8 px-2 rounded-lg border border-slate-500/40 bg-slate-900/30 text-slate-200 text-xs">Duplicate version</button>
                                        <button
                                            onClick={() => {
                                                setOpenVersionsForPost(post.id);
                                                setCompareBaseVersionNo(null);
                                                setCompareTargetVersionNo(null);
                                            }}
                                            className="h-8 px-2 rounded-lg border border-amber-600/40 bg-amber-900/20 text-amber-200 text-xs"
                                        >
                                            Versions ({post.versions_count || 0})
                                        </button>
                                        {canWrite && post.status === 'draft' && <button onClick={() => quickPostStatusMutation.mutate({ postId: post.id, status: 'ready' })} className="h-8 px-2 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs">جاهز</button>}
                                        {canWrite && (post.status === 'ready' || post.status === 'draft') && <button onClick={() => quickPostStatusMutation.mutate({ postId: post.id, status: 'approved' })} className="h-8 px-2 rounded-lg border border-blue-500/30 bg-blue-500/10 text-blue-200 text-xs">اعتماد</button>}
                                        {canWrite && post.status === 'failed' && <button onClick={() => quickPostStatusMutation.mutate({ postId: post.id, status: 'draft' })} className="h-8 px-2 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-200 text-xs">استرجاع</button>}
                                        {canWrite && post.status === 'approved' && <button onClick={() => dispatchPostMutation.mutate({ postId: post.id, action: 'publish' })} className="h-8 px-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-xs">Publish adapter</button>}
                                        {canWrite && post.status === 'approved' && <button onClick={() => dispatchPostMutation.mutate({ postId: post.id, action: 'schedule' })} className="h-8 px-2 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-xs">Schedule adapter</button>}
                                    </div>
                                    {engagementByPostId[post.id] && (
                                        <div className="mt-2 rounded-lg border border-violet-500/30 bg-violet-500/10 p-2 text-xs text-violet-200">
                                            Score: {engagementByPostId[post.id].score}/100
                                            {!!engagementByPostId[post.id].rec.length && (
                                                <div className="text-violet-100 mt-1">{engagementByPostId[post.id].rec[0]}</div>
                                            )}
                                        </div>
                                    )}
                                    <div className="mt-2 flex flex-wrap gap-2">
                                        <input value={publishUrlDraft[post.id] || ''} onChange={(e) => setPublishUrlDraft((prev) => ({ ...prev, [post.id]: e.target.value }))} placeholder="رابط المنشور" className="h-9 min-w-[260px] flex-1 rounded-lg border border-slate-700 bg-slate-900/60 px-3 text-xs text-white" />
                                        {canWrite && post.status !== 'published' && <button onClick={() => publishPostMutation.mutate({ postId: post.id, publishedUrl: publishUrlDraft[post.id] })} className="h-9 px-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-xs inline-flex items-center gap-1"><CheckCircle2 className="w-3 h-3" />تم النشر</button>}
                                    </div>
                                </div>
                            ))}
                            {openVersionsForPost && (
                                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 space-y-2">
                                    <div className="flex items-center justify-between gap-2">
                                        <div className="text-sm text-amber-100">Version History • Post #{openVersionsForPost}</div>
                                        <button
                                            onClick={() => setOpenVersionsForPost(null)}
                                            className="h-7 px-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-xs"
                                        >
                                            إغلاق
                                        </button>
                                    </div>
                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                                        <select
                                            value={compareBaseVersionNo || ''}
                                            onChange={(e) => setCompareBaseVersionNo(e.target.value ? Number(e.target.value) : null)}
                                            className="h-9 rounded-lg border border-slate-700 bg-slate-900/60 px-3 text-xs text-white"
                                        >
                                            <option value="">اختر النسخة الأساسية</option>
                                            {versions.map((v) => <option key={`base-${v.id}`} value={v.version_no}>v{v.version_no} - {v.version_type}</option>)}
                                        </select>
                                        <select
                                            value={compareTargetVersionNo || ''}
                                            onChange={(e) => setCompareTargetVersionNo(e.target.value ? Number(e.target.value) : null)}
                                            className="h-9 rounded-lg border border-slate-700 bg-slate-900/60 px-3 text-xs text-white"
                                        >
                                            <option value="">اختر نسخة المقارنة</option>
                                            {versions.map((v) => <option key={`target-${v.id}`} value={v.version_no}>v{v.version_no} - {v.version_type}</option>)}
                                        </select>
                                    </div>
                                    {versionCompareQuery.data?.data && (
                                        <div className="rounded-lg border border-slate-700 bg-slate-900/60 p-2 text-xs text-slate-200">
                                            Delta: {versionCompareQuery.data.data.length_delta} chars
                                            <div className="text-slate-400 mt-1">
                                                +Tags: {(versionCompareQuery.data.data.hashtags_added || []).join(', ') || '—'} | -Tags: {(versionCompareQuery.data.data.hashtags_removed || []).join(', ') || '—'}
                                            </div>
                                        </div>
                                    )}
                                    <div className="max-h-44 overflow-auto space-y-1">
                                        {versions.map((v) => (
                                            <div key={v.id} className="rounded-md border border-slate-700 bg-slate-900/60 p-2 text-xs text-slate-200">
                                                <div className="flex items-center justify-between gap-2">
                                                    <div>v{v.version_no} • {v.version_type}</div>
                                                    <button
                                                        onClick={() => duplicatePostVersionMutation.mutate({ postId: openVersionsForPost, sourceVersionNo: v.version_no })}
                                                        className="h-7 px-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-[11px]"
                                                    >
                                                        استعادة/تكرار
                                                    </button>
                                                </div>
                                                <div className="text-slate-400 mt-1">{formatDate(v.created_at)}</div>
                                                <div className="text-slate-300 mt-1 line-clamp-2">{v.content_text}</div>
                                            </div>
                                        ))}
                                        {!versions.length && <div className="text-xs text-slate-400">لا توجد نسخ بعد.</div>}
                                    </div>
                                </div>
                            )}
                            {!posts.length && <div className="text-xs text-slate-500">لا توجد مواد بعد.</div>}
                        </div>
                    </div>
                )}
            </section>
            )}

            {deskMode === 'planning' && (
                <>
            {canManage && (
                <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                    <h2 className="text-sm font-semibold text-slate-200">صلاحيات فريق الديجيتال</h2>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                        <select value={scopeUserId} onChange={(e) => setScopeUserId(e.target.value)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white md:col-span-2"><option value="">اختر صحفي السوشيال</option>{socialUsers.map((u) => <option key={u.id} value={String(u.id)}>{u.full_name_ar || u.username}</option>)}</select>
                        <label className="inline-flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={scopeNews} onChange={(e) => setScopeNews(e.target.checked)} /> نيوز</label>
                        <label className="inline-flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={scopeTv} onChange={(e) => setScopeTv(e.target.checked)} /> TV</label>
                    </div>
                    <button onClick={() => saveScopeMutation.mutate()} disabled={!scopeUserId} className="h-10 px-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-200 text-sm disabled:opacity-50">حفظ الصلاحية</button>
                    <div className="max-h-44 overflow-auto rounded-xl border border-slate-800">
                        <table className="w-full text-xs"><thead className="bg-slate-900/80 text-slate-300 sticky top-0"><tr><th className="text-right px-3 py-2">المستخدم</th><th className="text-right px-3 py-2">نيوز</th><th className="text-right px-3 py-2">TV</th><th className="text-right px-3 py-2">تحديث</th></tr></thead><tbody>{(scopesQuery.data?.data || []).map((scope) => <tr key={scope.id} className="border-t border-slate-800 text-slate-300"><td className="px-3 py-2">{scope.full_name_ar || scope.username || scope.user_id}</td><td className="px-3 py-2">{scope.can_manage_news ? '✓' : '—'}</td><td className="px-3 py-2">{scope.can_manage_tv ? '✓' : '—'}</td><td className="px-3 py-2">{formatRelativeTime(scope.updated_at)}</td></tr>)}</tbody></table>
                    </div>
                    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
                        <div className="text-xs text-slate-300 mb-2">Scope Performance</div>
                        <div className="max-h-44 overflow-auto">
                            <table className="w-full text-xs">
                                <thead className="bg-slate-900/80 text-slate-300 sticky top-0">
                                    <tr>
                                        <th className="text-right px-2 py-1">المستخدم</th>
                                        <th className="text-right px-2 py-1">المهام</th>
                                        <th className="text-right px-2 py-1">نشطة</th>
                                        <th className="text-right px-2 py-1">متأخرة</th>
                                        <th className="text-right px-2 py-1">فشل</th>
                                        <th className="text-right px-2 py-1">منشور</th>
                                        <th className="text-right px-2 py-1">On-time</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {((scopePerformanceQuery.data?.data?.items || []) as DigitalScopePerformanceItem[]).map((row) => (
                                        <tr key={`${row.user_id}-${row.username}`} className="border-t border-slate-800 text-slate-300">
                                            <td className="px-2 py-1">{row.username || row.user_id || '—'}</td>
                                            <td className="px-2 py-1">{row.total_tasks}</td>
                                            <td className="px-2 py-1">{row.active_tasks}</td>
                                            <td className="px-2 py-1 text-amber-200">{row.overdue_tasks}</td>
                                            <td className="px-2 py-1 text-rose-200">{row.failed_posts}</td>
                                            <td className="px-2 py-1 text-emerald-200">{row.published_posts}</td>
                                            <td className="px-2 py-1">{Number(row.on_time_rate || 0).toFixed(1)}%</td>
                                        </tr>
                                    ))}
                                    {!scopePerformanceQuery.data?.data?.items?.length && (
                                        <tr><td colSpan={7} className="px-2 py-3 text-center text-slate-500">لا توجد بيانات أداء بعد.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>
            )}

            <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4">
                <h2 className="text-sm font-semibold text-slate-200 mb-2">البرامج النشطة ({slotsQuery.data?.data?.length || 0})</h2>
                <div className="max-h-56 overflow-auto grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                    {(slotsQuery.data?.data || []).map((slot) => (
                        <div key={slot.id} className="rounded-lg border border-slate-800 bg-slate-900/50 p-2 text-xs text-slate-300">
                            <div className="font-medium text-white">{slot.program_title}</div>
                            <div className="text-slate-500 mt-1">{channelLabel(slot.channel)} • {slot.start_time} • {slot.duration_minutes}د</div>
                        </div>
                    ))}
                </div>
            </section>
                </>
            )}
        </div>
    );
}



