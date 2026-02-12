'use client';

import { useQuery } from '@tanstack/react-query';
import { api, type AgentStatus } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/utils';
import {
    Users, Shield, UserCheck, Newspaper, Radio,
    PenTool, Globe, MessageCircle, BookOpen,
} from 'lucide-react';

interface TeamMember {
    id: number;
    full_name_ar: string;
    username: string;
    role: string;
    departments: string[];
    specialization: string | null;
    is_active: boolean;
    is_online: boolean;
    last_login_at: string | null;
}

const roleConfig: Record<string, { label: string; color: string; icon: any }> = {
    director: { label: 'المدير العام', color: 'from-amber-500 to-orange-500', icon: Shield },
    editor_chief: { label: 'رئيس التحرير', color: 'from-purple-500 to-pink-500', icon: UserCheck },
    journalist: { label: 'صحفي', color: 'from-blue-500 to-cyan-500', icon: Newspaper },
    social_media: { label: 'سوشيال ميديا', color: 'from-pink-500 to-rose-500', icon: MessageCircle },
    print_editor: { label: 'مادة الجريدة', color: 'from-emerald-500 to-teal-500', icon: BookOpen },
};

const deptLabels: Record<string, string> = {
    national: '🇩🇿 وطني',
    international: '🌍 دولي',
    economy: '💹 اقتصاد',
    sports: '⚽ رياضة',
    french: '🇫🇷 فرنسي',
    social_media: '📱 سوشيال',
    print: '📰 الجريدة',
    variety: '🎭 منوعات',
    jewelry: '💎 جواهر',
    management: '🏢 إدارة',
};

export default function TeamPage() {
    const { user: currentUser } = useAuth();

    const { data, isLoading } = useQuery({
        queryKey: ['team-members'],
        queryFn: () => api.get<TeamMember[]>('/auth/users'),
        enabled: currentUser?.role === 'director' || currentUser?.role === 'editor_chief',
    });

    const members = data?.data || [];

    // Group by role
    const grouped = members.reduce((acc, member) => {
        const role = member.role;
        if (!acc[role]) acc[role] = [];
        acc[role].push(member);
        return acc;
    }, {} as Record<string, TeamMember[]>);

    const roleOrder = ['director', 'editor_chief', 'journalist', 'social_media', 'print_editor'];

    if (currentUser?.role !== 'director' && currentUser?.role !== 'editor_chief') {
        return (
            <div className="text-center py-20">
                <Shield className="w-16 h-16 text-gray-700 mx-auto mb-4" />
                <h2 className="text-lg font-semibold text-white">صلاحية محدودة</h2>
                <p className="text-sm text-gray-500 mt-1">هذه الصفحة متاحة للمدير ورؤساء التحرير فقط</p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-white flex items-center gap-3">
                        <Users className="w-7 h-7 text-violet-400" />
                        فريق التحرير
                    </h1>
                    <p className="text-sm text-gray-500 mt-1">
                        {members.length} صحفي — {members.filter(m => m.is_online).length} متصل الآن
                    </p>
                </div>

                {/* Online counter */}
                <div className="flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span className="text-sm font-medium text-emerald-400">
                        {members.filter(m => m.is_online).length} متصل
                    </span>
                </div>
            </div>

            {/* Loading */}
            {isLoading && (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {Array.from({ length: 9 }).map((_, i) => (
                        <div key={i} className="h-40 rounded-2xl bg-gray-800/30 border border-white/5 animate-pulse" />
                    ))}
                </div>
            )}

            {/* Members by Role */}
            {roleOrder.map((role) => {
                const roleMembers = grouped[role];
                if (!roleMembers || roleMembers.length === 0) return null;
                const config = roleConfig[role] || { label: role, color: 'from-gray-500 to-gray-600', icon: Users };
                const RoleIcon = config.icon;

                return (
                    <div key={role}>
                        <div className="flex items-center gap-2 mb-3">
                            <div className={cn('w-7 h-7 rounded-lg bg-gradient-to-br flex items-center justify-center', config.color)}>
                                <RoleIcon className="w-4 h-4 text-white" />
                            </div>
                            <h2 className="text-sm font-semibold text-white">{config.label}</h2>
                            <span className="text-[10px] text-gray-500 px-2 py-0.5 rounded-full bg-white/5">
                                {roleMembers.length}
                            </span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {roleMembers.map((member) => (
                                <div
                                    key={member.id}
                                    className={cn(
                                        'rounded-2xl p-4 border transition-all duration-200',
                                        'bg-gradient-to-br from-gray-800/40 to-gray-900/60',
                                        member.is_active ? 'border-white/5 hover:border-white/10' : 'border-white/[0.02] opacity-50',
                                    )}
                                >
                                    <div className="flex items-center gap-3 mb-3">
                                        <div className={cn(
                                            'w-10 h-10 rounded-xl bg-gradient-to-br flex items-center justify-center relative',
                                            config.color,
                                        )}>
                                            <span className="text-white text-sm font-bold">
                                                {member.full_name_ar.charAt(0)}
                                            </span>
                                            {member.is_online && (
                                                <span className="absolute -bottom-0.5 -left-0.5 w-3 h-3 rounded-full bg-emerald-400 border-2 border-gray-900" />
                                            )}
                                        </div>
                                        <div>
                                            <h3 className="text-sm font-semibold text-white">{member.full_name_ar}</h3>
                                            <p className="text-[10px] text-gray-500">@{member.username}</p>
                                        </div>
                                    </div>

                                    {member.specialization && (
                                        <p className="text-xs text-gray-400 mb-2">{member.specialization}</p>
                                    )}

                                    <div className="flex flex-wrap gap-1">
                                        {member.departments.map((dept) => (
                                            <span key={dept} className="px-2 py-0.5 rounded-md bg-white/5 text-[10px] text-gray-400">
                                                {deptLabels[dept] || dept}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                );
            })}
        </div>
    );
}
