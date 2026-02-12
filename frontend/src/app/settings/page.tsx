'use client';

import { useMemo, useState, useEffect, type ReactNode } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '@/lib/settings-api';
import { cn, formatRelativeTime } from '@/lib/utils';
import { Save, KeyRound, Bell, Database, ShieldAlert, Wand2, PlugZap, History } from 'lucide-react';

type SettingRow = {
    key: string;
    label: string;
    description: string;
    is_secret: boolean;
    group: 'ai' | 'notifications' | 'storage' | 'system';
};

const SETTINGS: SettingRow[] = [
    { key: 'GEMINI_API_KEY', label: 'Gemini API Key', description: 'مفتاح Gemini', is_secret: true, group: 'ai' },
    { key: 'GEMINI_MODEL_FLASH', label: 'Gemini Flash Model', description: 'اسم نموذج Gemini Flash', is_secret: false, group: 'ai' },
    { key: 'GEMINI_MODEL_PRO', label: 'Gemini Pro Model', description: 'اسم نموذج Gemini Pro', is_secret: false, group: 'ai' },
    { key: 'GROQ_API_KEY', label: 'Groq API Key', description: 'مفتاح Groq', is_secret: true, group: 'ai' },

    { key: 'TELEGRAM_BOT_TOKEN', label: 'Telegram Bot Token', description: 'مفتاح بوت تيليجرام', is_secret: true, group: 'notifications' },
    { key: 'TELEGRAM_CHANNEL_EDITORS', label: 'Telegram Editors Channel', description: 'قناة المحررين', is_secret: false, group: 'notifications' },
    { key: 'TELEGRAM_CHANNEL_ALERTS', label: 'Telegram Alerts Channel', description: 'قناة التنبيهات', is_secret: false, group: 'notifications' },
    { key: 'SLACK_WEBHOOK_URL', label: 'Slack Webhook URL', description: 'رابط Slack', is_secret: true, group: 'notifications' },

    { key: 'MINIO_ENDPOINT', label: 'MinIO Endpoint', description: 'عنوان MinIO', is_secret: false, group: 'storage' },
    { key: 'MINIO_ACCESS_KEY', label: 'MinIO Access Key', description: 'مفتاح الوصول', is_secret: true, group: 'storage' },
    { key: 'MINIO_SECRET_KEY', label: 'MinIO Secret Key', description: 'المفتاح السري', is_secret: true, group: 'storage' },
    { key: 'MINIO_BUCKET', label: 'MinIO Bucket', description: 'اسم الحاوية', is_secret: false, group: 'storage' },
    { key: 'MINIO_USE_SSL', label: 'MinIO Use SSL', description: 'تفعيل SSL (true/false)', is_secret: false, group: 'storage' },
];

export default function SettingsPage() {
    const queryClient = useQueryClient();
    const [values, setValues] = useState<Record<string, string>>({});
    const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

    useEffect(() => {
        if (!toast) return;
        const timer = setTimeout(() => setToast(null), 3000);
        return () => clearTimeout(timer);
    }, [toast]);

    const { data } = useQuery({
        queryKey: ['settings'],
        queryFn: () => settingsApi.list(),
    });

    const { data: auditData } = useQuery({
        queryKey: ['settings-audit'],
        queryFn: () => settingsApi.audit(200),
    });

    const updateMutation = useMutation({
        mutationFn: (payload: { key: string; value: string; is_secret: boolean; description?: string }) =>
            settingsApi.upsert(payload.key, { value: payload.value, is_secret: payload.is_secret, description: payload.description }),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['settings'] });
            queryClient.invalidateQueries({ queryKey: ['settings-audit'] });
            setToast({ type: 'success', message: 'تم حفظ الإعداد' });
        },
        onError: () => setToast({ type: 'error', message: 'فشل الحفظ' }),
    });

    const importMutation = useMutation({
        mutationFn: () => settingsApi.importEnv(),
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['settings'] });
            queryClient.invalidateQueries({ queryKey: ['settings-audit'] });
            setToast({ type: 'success', message: 'تم استيراد الإعدادات بنجاح' });
        },
        onError: () => setToast({ type: 'error', message: 'فشل الاستيراد' }),
    });

    const testMutation = useMutation({
        mutationFn: (key: string) => settingsApi.test(key),
        onSuccess: (res, key) => {
            if (res?.data?.ok) {
                setToast({ type: 'success', message: `تم اختبار ${key}` });
            } else {
                const missing = res?.data?.missing ? ` (ناقص: ${res.data.missing})` : '';
                setToast({ type: 'error', message: `فشل اختبار ${key}${missing}` });
            }
        },
        onError: () => setToast({ type: 'error', message: 'فشل الاختبار' }),
    });

    const byKey = useMemo(() => {
        const map: Record<string, any> = {};
        (data?.data || []).forEach((s: any) => { map[s.key] = s; });
        return map;
    }, [data]);

    const renderGroup = (group: SettingRow['group'], title: string, icon: ReactNode) => (
        <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4 space-y-4">
            <div className="flex items-center gap-2 text-white">
                {icon}
                <h2 className="text-sm font-semibold">{title}</h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {SETTINGS.filter(s => s.group === group).map((s) => {
                    const current = byKey[s.key];
                    const displayValue = current?.value || (current?.has_value ? '••••••••' : '');
                    const val = values[s.key] ?? '';

                    return (
                        <div key={s.key} className="rounded-xl border border-white/5 bg-white/[0.02] p-3">
                            <div className="text-xs text-gray-400">{s.label}</div>
                            <div className="text-[10px] text-gray-500 mb-2">{s.description}</div>
                            <input
                                type={s.is_secret ? 'password' : 'text'}
                                value={val}
                                placeholder={displayValue || ''}
                                onChange={(e) => setValues(prev => ({ ...prev, [s.key]: e.target.value }))}
                                className="w-full h-9 px-3 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-emerald-500/40"
                            />
                            <div className="mt-2 grid grid-cols-2 gap-2">
                                <button
                                    onClick={() => updateMutation.mutate({ key: s.key, value: val, is_secret: s.is_secret, description: s.description })}
                                    disabled={updateMutation.isPending || val.length === 0}
                                    className={cn(
                                        'h-9 rounded-lg text-xs font-medium flex items-center justify-center gap-2 transition-colors',
                                        val.length === 0
                                            ? 'bg-white/5 text-gray-500 border border-white/10 cursor-not-allowed'
                                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30'
                                    )}
                                >
                                    <Save className="w-3.5 h-3.5" />
                                    حفظ
                                </button>
                                <button
                                    onClick={() => testMutation.mutate(s.key)}
                                    disabled={testMutation.isPending}
                                    className="h-9 rounded-lg text-xs font-medium flex items-center justify-center gap-2 bg-white/5 text-gray-300 border border-white/10 hover:text-white hover:border-white/20"
                                >
                                    <PlugZap className="w-3.5 h-3.5" />
                                    اختبار
                                </button>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );

    return (
        <div className="space-y-6">
            {toast && (
                <div
                    className={cn(
                        'px-4 py-3 rounded-xl text-sm border',
                        toast.type === 'success'
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                            : 'bg-red-500/10 border-red-500/30 text-red-300'
                    )}
                >
                    {toast.message}
                </div>
            )}

            <div className="flex items-center gap-3">
                <KeyRound className="w-6 h-6 text-emerald-400" />
                <h1 className="text-2xl font-bold text-white">إعدادات APIs</h1>
                <button
                    onClick={() => importMutation.mutate()}
                    className="ml-auto px-3 py-2 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-xs text-emerald-300 hover:bg-emerald-500/25 transition-colors flex items-center gap-2"
                >
                    <Wand2 className="w-4 h-4" />
                    استيراد من .env
                </button>
            </div>

            {renderGroup('ai', 'خدمات الذكاء الاصطناعي', <ShieldAlert className="w-4 h-4 text-emerald-400" />)}
            {renderGroup('notifications', 'التنبيهات', <Bell className="w-4 h-4 text-amber-400" />)}
            {renderGroup('storage', 'التخزين', <Database className="w-4 h-4 text-sky-400" />)}

            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-4">
                <div className="flex items-center gap-2 text-white mb-4">
                    <History className="w-4 h-4 text-emerald-400" />
                    <h2 className="text-sm font-semibold">سجل التغييرات</h2>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="text-xs text-gray-500 border-b border-white/5">
                                <th className="text-right py-2">المفتاح</th>
                                <th className="text-right py-2">الإجراء</th>
                                <th className="text-right py-2">القيمة السابقة</th>
                                <th className="text-right py-2">القيمة الجديدة</th>
                                <th className="text-right py-2">المنفذ</th>
                                <th className="text-right py-2">الوقت</th>
                            </tr>
                        </thead>
                        <tbody>
                            {(auditData?.data || []).map((row: any) => (
                                <tr key={row.id} className="border-b border-white/5 text-xs text-gray-300">
                                    <td className="py-2">{row.key}</td>
                                    <td className="py-2">{row.action}</td>
                                    <td className="py-2 text-gray-500">{row.old_value || '—'}</td>
                                    <td className="py-2">{row.new_value || '—'}</td>
                                    <td className="py-2 text-gray-400">{row.actor || '—'}</td>
                                    <td className="py-2 text-gray-500">{row.created_at ? formatRelativeTime(row.created_at) : '—'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
