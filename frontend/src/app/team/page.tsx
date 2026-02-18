'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { LucideIcon } from 'lucide-react';
import {
    Shield,
    UserCheck,
    Newspaper,
    MessageCircle,
    BookOpen,
    Users,
    PlusCircle,
    Clock4,
    Activity,
} from 'lucide-react';
import { authApi, type CreateUserPayload, type TeamMember, type UpdateUserPayload, type UserActivityLogItem } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatRelativeTime } from '@/lib/utils';

const ROLE_OPTIONS: Array<{ value: CreateUserPayload['role']; label: string }> = [
    { value: 'director', label: 'المدير العام' },
    { value: 'editor_chief', label: 'رئيس التحرير' },
    { value: 'journalist', label: 'صحفي' },
    { value: 'social_media', label: 'سوشيال ميديا' },
    { value: 'print_editor', label: 'مادة الجريدة' },
];

const ROLE_CONFIG: Record<string, { label: string; color: string; icon: LucideIcon }> = {
    director: { label: 'المدير العام', color: 'from-amber-500 to-orange-500', icon: Shield },
    editor_chief: { label: 'رئيس التحرير', color: 'from-purple-500 to-pink-500', icon: UserCheck },
    journalist: { label: 'صحفي', color: 'from-blue-500 to-cyan-500', icon: Newspaper },
    social_media: { label: 'سوشيال ميديا', color: 'from-pink-500 to-rose-500', icon: MessageCircle },
    print_editor: { label: 'مادة الجريدة', color: 'from-emerald-500 to-teal-500', icon: BookOpen },
};

const DEPARTMENT_OPTIONS = [
    { value: 'national', label: 'وطني' },
    { value: 'international', label: 'دولي' },
    { value: 'economy', label: 'اقتصاد' },
    { value: 'sports', label: 'رياضة' },
    { value: 'french', label: 'فرنسي' },
    { value: 'social_media', label: 'سوشيال' },
    { value: 'print', label: 'الجريدة' },
    { value: 'variety', label: 'منوعات' },
    { value: 'jewelry', label: 'جواهر' },
    { value: 'management', label: 'إدارة' },
];

type UserFormState = {
    full_name_ar: string;
    username: string;
    password: string;
    role: CreateUserPayload['role'];
    departments: string[];
    specialization: string;
    is_active: boolean;
};

function defaultCreateForm(): UserFormState {
    return {
        full_name_ar: '',
        username: '',
        password: '',
        role: 'journalist',
        departments: ['national'],
        specialization: '',
        is_active: true,
    };
}

function parseDetails(details: string | null): string {
    if (!details) return '—';
    try {
        const parsed = JSON.parse(details) as Record<string, unknown>;
        return Object.entries(parsed)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`)
            .join(' | ');
    } catch {
        return details;
    }
}

export default function TeamPage() {
    const { user: currentUser } = useAuth();
    const queryClient = useQueryClient();
    const isDirector = currentUser?.role === 'director';
    const canView = currentUser?.role === 'director' || currentUser?.role === 'editor_chief';

    const [createForm, setCreateForm] = useState<UserFormState>(defaultCreateForm());
    const [editTarget, setEditTarget] = useState<TeamMember | null>(null);
    const [editForm, setEditForm] = useState<UserFormState | null>(null);
    const [selectedLogUser, setSelectedLogUser] = useState<TeamMember | null>(null);
    const [msg, setMsg] = useState<string | null>(null);
    const [err, setErr] = useState<string | null>(null);

    const usersQuery = useQuery({
        queryKey: ['team-members'],
        queryFn: () => authApi.users(),
        enabled: canView,
    });
    const members = useMemo(
        () => (usersQuery.data?.data || []) as TeamMember[],
        [usersQuery.data?.data]
    );

    const activityQuery = useQuery({
        queryKey: ['team-member-activity', selectedLogUser?.id],
        queryFn: () => authApi.userActivity(selectedLogUser!.id, 120),
        enabled: !!selectedLogUser && canView,
    });
    const activityItems = (activityQuery.data?.data || []) as UserActivityLogItem[];

    const createMutation = useMutation({
        mutationFn: (payload: CreateUserPayload) => authApi.createUser(payload),
        onSuccess: async () => {
            setMsg('تمت إضافة العضو بنجاح');
            setErr(null);
            setCreateForm(defaultCreateForm());
            await queryClient.invalidateQueries({ queryKey: ['team-members'] });
        },
        onError: () => setErr('تعذر إضافة العضو'),
    });

    const updateMutation = useMutation({
        mutationFn: ({ userId, payload }: { userId: number; payload: UpdateUserPayload }) =>
            authApi.updateUser(userId, payload),
        onSuccess: async () => {
            setMsg('تم تحديث العضوية بنجاح');
            setErr(null);
            setEditTarget(null);
            setEditForm(null);
            await queryClient.invalidateQueries({ queryKey: ['team-members'] });
            if (selectedLogUser) {
                await queryClient.invalidateQueries({ queryKey: ['team-member-activity', selectedLogUser.id] });
            }
        },
        onError: () => setErr('تعذر تحديث العضوية'),
    });

    const grouped = useMemo(() => {
        const buckets: Record<string, TeamMember[]> = {};
        for (const member of members) {
            if (!buckets[member.role]) buckets[member.role] = [];
            buckets[member.role].push(member);
        }
        return buckets;
    }, [members]);

    if (!canView) {
        return (
            <div className="text-center py-20">
                <Shield className="w-16 h-16 text-gray-700 mx-auto mb-4" />
                <h2 className="text-lg font-semibold text-white">صلاحية محدودة</h2>
                <p className="text-sm text-gray-500 mt-1">هذه الصفحة متاحة للمدير ورئيس التحرير فقط</p>
            </div>
        );
    }

    const totalOnline = members.filter((m) => m.is_online).length;
    const roleOrder = ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'];

    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <Users className="w-7 h-7 text-violet-400" />
                        إدارة الفريق والعضوية
                    </h1>
                    <p className="text-sm text-gray-500 mt-1">
                        {members.length} عضو • {totalOnline} متصل الآن
                    </p>
                </div>
                <div className="px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm">
                    اتصال مباشر: {totalOnline}
                </div>
            </div>

            {msg && <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-200">{msg}</div>}
            {err && <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-200">{err}</div>}

            {isDirector && (
                <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                    <h2 className="text-white font-semibold flex items-center gap-2">
                        <PlusCircle className="w-4 h-4 text-emerald-300" />
                        إضافة عضو جديد
                    </h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <input
                            value={createForm.full_name_ar}
                            onChange={(e) => setCreateForm((prev) => ({ ...prev, full_name_ar: e.target.value }))}
                            className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                            placeholder="الاسم الكامل"
                        />
                        <input
                            value={createForm.username}
                            onChange={(e) => setCreateForm((prev) => ({ ...prev, username: e.target.value }))}
                            className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                            placeholder="اسم المستخدم"
                        />
                        <input
                            value={createForm.password}
                            onChange={(e) => setCreateForm((prev) => ({ ...prev, password: e.target.value }))}
                            className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                            placeholder="كلمة المرور المبدئية"
                            type="password"
                        />
                        <input
                            value={createForm.specialization}
                            onChange={(e) => setCreateForm((prev) => ({ ...prev, specialization: e.target.value }))}
                            className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                            placeholder="التخصص (اختياري)"
                        />
                        <select
                            value={createForm.role}
                            onChange={(e) => setCreateForm((prev) => ({ ...prev, role: e.target.value as CreateUserPayload['role'] }))}
                            className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                        >
                            {ROLE_OPTIONS.map((role) => (
                                <option key={role.value} value={role.value}>{role.label}</option>
                            ))}
                        </select>
                        <label className="flex items-center gap-2 text-sm text-gray-300">
                            <input
                                type="checkbox"
                                checked={createForm.is_active}
                                onChange={(e) => setCreateForm((prev) => ({ ...prev, is_active: e.target.checked }))}
                                className="accent-emerald-500"
                            />
                            الحساب نشط
                        </label>
                    </div>

                    <div className="flex flex-wrap gap-2">
                        {DEPARTMENT_OPTIONS.map((dept) => (
                            <button
                                key={dept.value}
                                type="button"
                                onClick={() =>
                                    setCreateForm((prev) => ({
                                        ...prev,
                                        departments: prev.departments.includes(dept.value)
                                            ? prev.departments.filter((d) => d !== dept.value)
                                            : [...prev.departments, dept.value],
                                    }))
                                }
                                className={cn(
                                    'px-3 py-1.5 rounded-lg text-xs border',
                                    createForm.departments.includes(dept.value)
                                        ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-200'
                                        : 'bg-white/5 border-white/10 text-gray-300'
                                )}
                            >
                                {dept.label}
                            </button>
                        ))}
                    </div>

                    <button
                        onClick={() =>
                            createMutation.mutate({
                                full_name_ar: createForm.full_name_ar.trim(),
                                username: createForm.username.trim(),
                                password: createForm.password,
                                role: createForm.role,
                                departments: createForm.departments,
                                specialization: createForm.specialization.trim() || null,
                                is_active: createForm.is_active,
                            })
                        }
                        disabled={createMutation.isPending || createForm.full_name_ar.trim().length < 2 || createForm.username.trim().length < 2 || createForm.password.length < 8}
                        className="h-10 px-4 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-200 text-sm disabled:opacity-40"
                    >
                        {createMutation.isPending ? 'جاري الإضافة...' : 'إضافة العضو'}
                    </button>
                </section>
            )}

            {usersQuery.isLoading ? (
                <div className="rounded-2xl border border-white/10 bg-gray-900/40 p-6 text-center text-gray-400">جاري تحميل الفريق...</div>
            ) : (
                roleOrder.map((roleKey) => {
                    const roleMembers = grouped[roleKey];
                    if (!roleMembers?.length) return null;
                    const config = ROLE_CONFIG[roleKey] || ROLE_CONFIG.journalist;
                    const Icon = config.icon;
                    return (
                        <section key={roleKey} className="space-y-3">
                            <div className="flex items-center gap-2">
                                <div className={cn('w-7 h-7 rounded-lg bg-gradient-to-br flex items-center justify-center', config.color)}>
                                    <Icon className="w-4 h-4 text-white" />
                                </div>
                                <h3 className="text-white text-sm font-semibold">{config.label}</h3>
                                <span className="text-xs text-gray-500">{roleMembers.length}</span>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                                {roleMembers.map((member) => (
                                    <article key={member.id} className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                                        <div className="flex items-center justify-between gap-2">
                                            <div>
                                                <h4 className="text-white text-sm font-semibold">{member.full_name_ar}</h4>
                                                <p className="text-xs text-gray-500">@{member.username}</p>
                                            </div>
                                            <span className={cn('px-2 py-0.5 rounded-full text-[10px] border', member.is_active ? 'border-emerald-500/40 text-emerald-300 bg-emerald-500/10' : 'border-red-500/40 text-red-300 bg-red-500/10')}>
                                                {member.is_active ? 'نشط' : 'معطّل'}
                                            </span>
                                        </div>

                                        <p className="text-xs text-gray-400">{member.specialization || '—'}</p>
                                        <div className="flex flex-wrap gap-1">
                                            {member.departments.map((dept) => (
                                                <span key={`${member.id}-${dept}`} className="px-2 py-0.5 rounded-md bg-white/5 text-[10px] text-gray-300">{dept}</span>
                                            ))}
                                        </div>

                                        <div className="text-[11px] text-gray-500 space-y-1">
                                            <div className="flex items-center gap-1">
                                                <Activity className="w-3 h-3" />
                                                {member.is_online ? 'متصل الآن' : 'غير متصل'}
                                            </div>
                                            <div className="flex items-center gap-1">
                                                <Clock4 className="w-3 h-3" />
                                                آخر دخول: {member.last_login_at ? formatRelativeTime(member.last_login_at) : '—'}
                                            </div>
                                        </div>

                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => setSelectedLogUser(member)}
                                                className="flex-1 h-9 rounded-xl bg-white/5 border border-white/10 text-xs text-gray-200"
                                            >
                                                سجل النشاط
                                            </button>
                                            {isDirector && (
                                                <button
                                                    onClick={() => {
                                                        setEditTarget(member);
                                                        setEditForm({
                                                            full_name_ar: member.full_name_ar,
                                                            username: member.username,
                                                            password: '',
                                                            role: (member.role as CreateUserPayload['role']) || 'journalist',
                                                            departments: [...member.departments],
                                                            specialization: member.specialization || '',
                                                            is_active: member.is_active,
                                                        });
                                                    }}
                                                    className="flex-1 h-9 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-xs text-emerald-200"
                                                >
                                                    إدارة العضوية
                                                </button>
                                            )}
                                        </div>
                                    </article>
                                ))}
                            </div>
                        </section>
                    );
                })
            )}

            {selectedLogUser && (
                <section className="rounded-2xl border border-white/10 bg-gray-900/40 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                        <h3 className="text-white font-semibold">سجل نشاط العضو: {selectedLogUser.full_name_ar}</h3>
                        <button onClick={() => setSelectedLogUser(null)} className="text-xs text-gray-400 hover:text-white">إغلاق</button>
                    </div>
                    {activityQuery.isLoading ? (
                        <p className="text-sm text-gray-400">جاري تحميل السجل...</p>
                    ) : !activityItems.length ? (
                        <p className="text-sm text-gray-500">لا يوجد نشاط مسجل بعد.</p>
                    ) : (
                        <div className="space-y-2 max-h-[320px] overflow-auto">
                            {activityItems.map((item) => (
                                <div key={item.id} className="rounded-xl border border-white/10 bg-black/20 p-2 text-xs text-gray-300">
                                    <div className="flex items-center justify-between">
                                        <span className="text-white">{item.action}</span>
                                        <span className="text-gray-500">{item.created_at ? formatRelativeTime(item.created_at) : '—'}</span>
                                    </div>
                                    <p className="text-gray-400 mt-1">من: {item.actor_username || 'system'}</p>
                                    <p className="text-gray-400 mt-1">تفاصيل: {parseDetails(item.details)}</p>
                                </div>
                            ))}
                        </div>
                    )}
                </section>
            )}

            {editTarget && editForm && (
                <div className="fixed inset-0 z-[80] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-gray-950 p-5 space-y-4" dir="rtl">
                        <h3 className="text-lg text-white font-semibold">تحديث العضوية: {editTarget.full_name_ar}</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                            <input
                                value={editForm.full_name_ar}
                                onChange={(e) => setEditForm((prev) => (prev ? { ...prev, full_name_ar: e.target.value } : prev))}
                                className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                                placeholder="الاسم"
                            />
                            <input
                                value={editForm.username}
                                onChange={(e) => setEditForm((prev) => (prev ? { ...prev, username: e.target.value } : prev))}
                                className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                                placeholder="اسم المستخدم"
                            />
                            <input
                                value={editForm.password}
                                onChange={(e) => setEditForm((prev) => (prev ? { ...prev, password: e.target.value } : prev))}
                                className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                                placeholder="كلمة مرور جديدة (اختياري)"
                                type="password"
                            />
                            <input
                                value={editForm.specialization}
                                onChange={(e) => setEditForm((prev) => (prev ? { ...prev, specialization: e.target.value } : prev))}
                                className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                                placeholder="التخصص"
                            />
                            <select
                                value={editForm.role}
                                onChange={(e) => setEditForm((prev) => (prev ? { ...prev, role: e.target.value as CreateUserPayload['role'] } : prev))}
                                className="h-10 rounded-xl bg-white/5 border border-white/10 px-3 text-sm text-white"
                            >
                                {ROLE_OPTIONS.map((role) => (
                                    <option key={role.value} value={role.value}>{role.label}</option>
                                ))}
                            </select>
                            <label className="flex items-center gap-2 text-sm text-gray-300">
                                <input
                                    type="checkbox"
                                    checked={editForm.is_active}
                                    onChange={(e) => setEditForm((prev) => (prev ? { ...prev, is_active: e.target.checked } : prev))}
                                    className="accent-emerald-500"
                                />
                                الحساب نشط
                            </label>
                        </div>

                        <div className="flex flex-wrap gap-2">
                            {DEPARTMENT_OPTIONS.map((dept) => (
                                <button
                                    key={dept.value}
                                    type="button"
                                    onClick={() =>
                                        setEditForm((prev) => {
                                            if (!prev) return prev;
                                            return {
                                                ...prev,
                                                departments: prev.departments.includes(dept.value)
                                                    ? prev.departments.filter((d) => d !== dept.value)
                                                    : [...prev.departments, dept.value],
                                            };
                                        })
                                    }
                                    className={cn(
                                        'px-3 py-1.5 rounded-lg text-xs border',
                                        editForm.departments.includes(dept.value)
                                            ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-200'
                                            : 'bg-white/5 border-white/10 text-gray-300'
                                    )}
                                >
                                    {dept.label}
                                </button>
                            ))}
                        </div>

                        <div className="flex items-center justify-end gap-2">
                            <button onClick={() => { setEditTarget(null); setEditForm(null); }} className="h-10 px-4 rounded-xl border border-white/20 text-sm text-gray-300">
                                إلغاء
                            </button>
                            <button
                                onClick={() => {
                                    const payload: UpdateUserPayload = {
                                        full_name_ar: editForm.full_name_ar.trim(),
                                        username: editForm.username.trim(),
                                        role: editForm.role,
                                        departments: editForm.departments,
                                        specialization: editForm.specialization.trim() || null,
                                        is_active: editForm.is_active,
                                    };
                                    if (editForm.password.trim().length >= 8) payload.password = editForm.password.trim();
                                    updateMutation.mutate({ userId: editTarget.id, payload });
                                }}
                                disabled={updateMutation.isPending}
                                className="h-10 px-4 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-sm text-emerald-200 disabled:opacity-50"
                            >
                                {updateMutation.isPending ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
