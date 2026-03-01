'use client';

import { useMemo, useState } from 'react';
import { isAxiosError } from 'axios';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarDays, CheckCircle2, Copy, Megaphone, PlusCircle, RefreshCcw, Sparkles, UploadCloud } from 'lucide-react';

import {
    authApi,
    digitalApi,
    type DigitalChannel,
    type DigitalPost,
    type DigitalPostStatus,
    type DigitalTask,
    type DigitalTaskStatus,
    type TeamMember,
} from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatDate, formatRelativeTime } from '@/lib/utils';

const READ_ROLES = new Set(['director', 'editor_chief', 'social_media', 'journalist', 'print_editor']);
const WRITE_ROLES = new Set(['director', 'editor_chief', 'social_media']);
const MANAGE_ROLES = new Set(['director', 'editor_chief']);
const PLATFORM_OPTIONS = ['facebook', 'x', 'youtube', 'tiktok', 'instagram'];

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
    const [channel, setChannel] = useState<'all' | DigitalChannel>('all');
    const [status, setStatus] = useState<'all' | DigitalTaskStatus>('all');
    const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);

    const [taskTitle, setTaskTitle] = useState('');
    const [taskBrief, setTaskBrief] = useState('');
    const [taskChannel, setTaskChannel] = useState<DigitalChannel>('news');
    const [taskDueAt, setTaskDueAt] = useState('');

    const [postPlatform, setPostPlatform] = useState('facebook');
    const [postStatus, setPostStatus] = useState<DigitalPostStatus>('draft');
    const [postContent, setPostContent] = useState('');
    const [postHashtags, setPostHashtags] = useState('');
    const [postScheduledAt, setPostScheduledAt] = useState('');

    const [scopeUserId, setScopeUserId] = useState('');
    const [scopeNews, setScopeNews] = useState(true);
    const [scopeTv, setScopeTv] = useState(true);

    const [publishUrlDraft, setPublishUrlDraft] = useState<Record<number, string>>({});
    const [composerSlotId, setComposerSlotId] = useState('');
    const [composerDraft, setComposerDraft] = useState('');
    const [composerPlatforms, setComposerPlatforms] = useState<string[]>(['facebook']);
    const [composerTaskId, setComposerTaskId] = useState<number | null>(null);
    const [composerGenerated, setComposerGenerated] = useState<Record<string, { text: string; hashtags: string[] }>>({});

    const overviewQuery = useQuery({
        queryKey: ['digital-overview'],
        queryFn: () => digitalApi.overview(),
        enabled: canRead,
        refetchInterval: 30000,
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

    const usersQuery = useQuery({
        queryKey: ['digital-users'],
        queryFn: () => authApi.users(),
        enabled: canManage,
    });

    const tasks = useMemo(() => (tasksQuery.data?.data?.items || []) as DigitalTask[], [tasksQuery.data?.data?.items]);
    const selectedTask = useMemo(() => tasks.find((t) => t.id === selectedTaskId) || null, [tasks, selectedTaskId]);

    const postsQuery = useQuery({
        queryKey: ['digital-posts', selectedTaskId],
        queryFn: () => digitalApi.listTaskPosts(selectedTaskId as number),
        enabled: canRead && !!selectedTaskId,
    });
    const posts = useMemo(() => (postsQuery.data?.data?.items || []) as DigitalPost[], [postsQuery.data?.data?.items]);

    const socialUsers = useMemo(
        () =>
            ((usersQuery.data?.data || []) as TeamMember[])
                .filter((u) => (u.role || '').toLowerCase() === 'social_media')
                .sort((a, b) => (a.full_name_ar || a.username).localeCompare(b.full_name_ar || b.username)),
        [usersQuery.data?.data]
    );

    const refreshAll = async () => {
        await queryClient.invalidateQueries({ queryKey: ['digital-overview'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-tasks'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-slots'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-calendar'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-posts'] });
        await queryClient.invalidateQueries({ queryKey: ['digital-scopes'] });
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

    const createPostMutation = useMutation({
        mutationFn: () =>
            digitalApi.createTaskPost(selectedTaskId as number, {
                platform: postPlatform,
                content_text: postContent.trim(),
                hashtags: postHashtags.split(',').map((s) => s.trim()).filter(Boolean),
                status: postStatus,
                scheduled_at: postScheduledAt ? new Date(postScheduledAt).toISOString() : null,
            }),
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
            setError(null);
            setMessage(`تمت صياغة منشور تلقائي من مصدر: ${data.source?.title || 'المهمة'}`);
        },
        onError: (err) => setError(apiErrorMessage(err, 'تعذرت صياغة المنشور تلقائياً.')),
    });

    const generateFromProgramMutation = useMutation({
        mutationFn: async () => {
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
        },
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
                        لوحة فريق الديجيتال
                    </h1>
                    <p className="text-sm text-gray-400 mt-1">مهام النشر الاجتماعي لقناتي الشروق نيوز والشروق تي في.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                    <button onClick={() => refreshAll()} className="h-10 px-3 rounded-xl border border-slate-500/30 bg-slate-500/10 text-slate-200 text-xs inline-flex items-center gap-1"><RefreshCcw className="w-4 h-4" />تحديث</button>
                    {canWrite && <button onClick={() => generateMutation.mutate()} className="h-10 px-3 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-xs inline-flex items-center gap-1"><Sparkles className="w-4 h-4" />توليد المهام</button>}
                    {canManage && <button onClick={() => importSlotsMutation.mutate(false)} className="h-10 px-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-xs inline-flex items-center gap-1"><UploadCloud className="w-4 h-4" />استيراد الشبكة</button>}
                </div>
            </div>

            {message && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-emerald-200 text-sm">{message}</div>}
            {error && <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-rose-200 text-sm">{error}</div>}

            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
                <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3"><div className="text-xs text-gray-400">إجمالي المهام</div><div className="text-2xl font-bold text-white">{overviewQuery.data?.data?.total_tasks ?? 0}</div></div>
                <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-3"><div className="text-xs text-gray-400">متأخرة</div><div className="text-2xl font-bold text-white">{overviewQuery.data?.data?.overdue ?? 0}</div></div>
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3"><div className="text-xs text-gray-400">مستحقة اليوم</div><div className="text-2xl font-bold text-white">{overviewQuery.data?.data?.due_today ?? 0}</div></div>
                <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-3"><div className="text-xs text-gray-400">قيد التنفيذ</div><div className="text-2xl font-bold text-white">{overviewQuery.data?.data?.in_progress ?? 0}</div></div>
                <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3"><div className="text-xs text-gray-400">منجزة اليوم</div><div className="text-2xl font-bold text-white">{overviewQuery.data?.data?.done_today ?? 0}</div></div>
                <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-3"><div className="text-xs text-gray-400">منشور 24 ساعة</div><div className="text-2xl font-bold text-white">{overviewQuery.data?.data?.published_posts_24h ?? 0}</div></div>
                <div className="rounded-xl border border-indigo-500/20 bg-indigo-500/5 p-3"><div className="text-xs text-gray-400">مجدول 24 ساعة</div><div className="text-2xl font-bold text-white">{overviewQuery.data?.data?.scheduled_posts_next_24h ?? 0}</div></div>
                <div className="rounded-xl border border-slate-500/20 bg-slate-500/5 p-3"><div className="text-xs text-gray-400">الانضباط</div><div className="text-2xl font-bold text-white">{Number(overviewQuery.data?.data?.on_time_rate || 0).toFixed(1)}%</div></div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
                <section className="xl:col-span-2 rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                    <div className="flex flex-wrap gap-2 items-center">
                        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="بحث..." className="h-10 w-full md:w-72 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white" />
                        <select value={channel} onChange={(e) => setChannel(e.target.value as 'all' | DigitalChannel)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white"><option value="all">كل القنوات</option><option value="news">نيوز</option><option value="tv">TV</option></select>
                        <select value={status} onChange={(e) => setStatus(e.target.value as 'all' | DigitalTaskStatus)} className="h-10 rounded-xl border border-slate-700 bg-slate-900/60 px-3 text-sm text-white"><option value="all">كل الحالات</option><option value="todo">جديد</option><option value="in_progress">قيد التنفيذ</option><option value="review">مراجعة</option><option value="done">منجز</option><option value="cancelled">ملغي</option></select>
                    </div>
                    <div className="max-h-[520px] overflow-auto rounded-xl border border-slate-800">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-900/80 text-slate-300 sticky top-0"><tr><th className="text-right px-3 py-2">المهمة</th><th className="text-right px-3 py-2">القناة</th><th className="text-right px-3 py-2">الحالة</th><th className="text-right px-3 py-2">الاستحقاق</th><th className="text-right px-3 py-2">إجراءات</th></tr></thead>
                            <tbody>
                                {tasks.map((task) => (
                                    <tr key={task.id} className={cn('border-t border-slate-800 hover:bg-slate-900/50 cursor-pointer', selectedTaskId === task.id && 'bg-cyan-500/10')} onClick={() => setSelectedTaskId(task.id)}>
                                        <td className="px-3 py-2"><div className="text-white font-medium">{task.title}</div><div className="text-xs text-slate-500 mt-1">{task.brief || 'بدون وصف'}</div></td>
                                        <td className="px-3 py-2 text-slate-300">{channelLabel(task.channel)}</td>
                                        <td className="px-3 py-2"><span className={cn('inline-flex px-2 py-0.5 rounded-lg border text-xs', taskStatusClass(task.status))}>{taskStatusLabel(task.status)}</span></td>
                                        <td className="px-3 py-2 text-slate-300">{task.due_at ? <div><div>{formatDate(task.due_at)}</div><div className="text-xs text-slate-500">{formatRelativeTime(task.due_at)}</div></div> : '—'}</td>
                                        <td className="px-3 py-2">
                                            {canWrite && <div className="flex gap-1 flex-wrap">
                                                {task.status !== 'in_progress' && <button onClick={(e) => { e.stopPropagation(); updateTaskMutation.mutate({ taskId: task.id, nextStatus: 'in_progress' }); }} className="text-xs px-2 py-1 rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">بدء</button>}
                                                {task.status !== 'review' && task.status !== 'done' && <button onClick={(e) => { e.stopPropagation(); updateTaskMutation.mutate({ taskId: task.id, nextStatus: 'review' }); }} className="text-xs px-2 py-1 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-200">مراجعة</button>}
                                                {task.status !== 'done' && <button onClick={(e) => { e.stopPropagation(); updateTaskMutation.mutate({ taskId: task.id, nextStatus: 'done' }); }} className="text-xs px-2 py-1 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">إغلاق</button>}
                                            </div>}
                                        </td>
                                    </tr>
                                ))}
                                {!tasks.length && <tr><td colSpan={5} className="px-3 py-8 text-center text-slate-500">لا توجد مهام.</td></tr>}
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

            <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                <h2 className="text-sm font-semibold text-slate-200">مولّد منشورات البرامج/المسلسلات</h2>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
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
                        {Object.entries(composerGenerated).map(([platform, value]) => (
                            <div key={platform} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                    <div className="text-sm text-white font-medium">{platform}</div>
                                    <button
                                        onClick={() => copySimple(value.text)}
                                        className="h-8 px-2 rounded-lg border border-slate-600 bg-slate-800/60 text-slate-200 text-xs inline-flex items-center gap-1"
                                    >
                                        <Copy className="w-3 h-3" />
                                        نسخ
                                    </button>
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
                        ))}
                        <button
                            onClick={() => saveGeneratedPostsMutation.mutate()}
                            disabled={!canWrite || saveGeneratedPostsMutation.isPending}
                            className="h-10 w-full rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-sm disabled:opacity-50"
                        >
                            حفظ كل الصياغات
                        </button>
                    </div>
                )}
            </section>

            <section className="rounded-2xl border border-slate-700/70 bg-[#0b1323]/90 p-4 space-y-3">
                <h2 className="text-sm font-semibold text-slate-200">مواد السوشيال للمهمة المحددة</h2>
                {!selectedTask && <div className="text-sm text-slate-400">اختر مهمة من الجدول.</div>}
                {selectedTask && (
                    <div className="space-y-3">
                        <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 text-sm text-slate-200">{selectedTask.title}</div>
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
                        <textarea value={postContent} onChange={(e) => setPostContent(e.target.value)} rows={3} placeholder="نص المنشور" className="w-full rounded-xl border border-slate-700 bg-slate-900/60 px-3 py-2 text-sm text-white" />
                        <button onClick={() => createPostMutation.mutate()} disabled={!canWrite || !postContent.trim()} className="h-10 rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-200 text-sm disabled:opacity-50">حفظ المادة</button>
                        <div className="space-y-2">
                            {posts.map((post) => (
                                <div key={post.id} className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
                                    <div className="flex flex-wrap items-center justify-between gap-2"><div className="text-sm text-white">{post.platform}</div><span className={cn('inline-flex px-2 py-0.5 rounded-lg border text-xs', postStatusClass(post.status))}>{postStatusLabel(post.status)}</span></div>
                                    <p className="text-sm text-slate-200 mt-2 whitespace-pre-wrap">{post.content_text}</p>
                                    <div className="mt-2 flex flex-wrap gap-2">
                                        <input value={publishUrlDraft[post.id] || ''} onChange={(e) => setPublishUrlDraft((prev) => ({ ...prev, [post.id]: e.target.value }))} placeholder="رابط المنشور" className="h-9 min-w-[260px] flex-1 rounded-lg border border-slate-700 bg-slate-900/60 px-3 text-xs text-white" />
                                        {canWrite && post.status !== 'published' && <button onClick={() => publishPostMutation.mutate({ postId: post.id, publishedUrl: publishUrlDraft[post.id] })} className="h-9 px-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-200 text-xs inline-flex items-center gap-1"><CheckCircle2 className="w-3 h-3" />تم النشر</button>}
                                    </div>
                                </div>
                            ))}
                            {!posts.length && <div className="text-xs text-slate-500">لا توجد مواد بعد.</div>}
                        </div>
                    </div>
                )}
            </section>

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
        </div>
    );
}
