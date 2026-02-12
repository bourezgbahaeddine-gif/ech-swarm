'use client';

import { Bell, Search, LogOut, User, Shield, FileText } from 'lucide-react';
import { useState } from 'react';
import { useAuth } from '@/lib/auth';

const roleLabels: Record<string, string> = {
    director: 'المدير العام',
    editor_chief: 'رئيس التحرير',
    journalist: 'صحفي',
    social_media: 'سوشيال ميديا',
    print_editor: 'محرر الجريدة',
};

export default function TopBar() {
    const { user, logout } = useAuth();
    const [searchQuery, setSearchQuery] = useState('');
    const [showMenu, setShowMenu] = useState(false);

    return (
        <header className="sticky top-0 z-30 bg-gray-900/80 backdrop-blur-xl border-b border-white/5">
            <div className="h-16">
                <div className="flex items-center justify-between h-full px-6">
                    {/* Search */}
                    <div className="relative w-full max-w-md">
                        <Search className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="ابحث عن خبر، مصدر، أو كلمة مفتاحية..."
                            className="w-full h-10 pr-10 pl-4 rounded-xl bg-white/5 border border-white/5 text-sm text-white 
                       placeholder:text-gray-500 focus:outline-none focus:border-emerald-500/40 focus:ring-1 focus:ring-emerald-500/20
                       transition-all duration-200"
                            dir="rtl"
                        />
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 mr-4">
                        {/* Notifications */}
                        <button className="relative w-10 h-10 rounded-xl bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors group">
                            <Bell className="w-4 h-4 text-gray-400 group-hover:text-white transition-colors" />
                            <span className="absolute -top-1 -left-1 w-5 h-5 rounded-full bg-red-500 text-[10px] text-white font-bold flex items-center justify-center shadow-lg shadow-red-500/30 animate-bounce">
                                3
                            </span>
                        </button>

                        {/* User Menu */}
                        <div className="relative">
                            <button
                                onClick={() => setShowMenu(!showMenu)}
                                className="flex items-center gap-3 px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 transition-colors"
                            >
                                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center">
                                    {user?.role === 'director' ? (
                                        <Shield className="w-4 h-4 text-white" />
                                    ) : (
                                        <User className="w-4 h-4 text-white" />
                                    )}
                                </div>
                                <div className="hidden md:block text-right">
                                    <p className="text-xs font-medium text-white">{user?.full_name_ar || 'مستخدم'}</p>
                                    <p className="text-[10px] text-gray-500">
                                        {roleLabels[user?.role || ''] || user?.role}
                                    </p>
                                </div>
                            </button>

                            {/* Dropdown */}
                            {showMenu && (
                                <div className="absolute left-0 top-full mt-2 w-56 rounded-xl bg-gray-800 border border-white/10 shadow-xl overflow-hidden animate-fade-in-up z-50">
                                    <div className="px-4 py-3 border-b border-white/5">
                                        <p className="text-sm font-medium text-white">{user?.full_name_ar}</p>
                                        <p className="text-[10px] text-gray-500 mt-0.5">@{user?.username}</p>
                                        <p className="text-[10px] text-emerald-400 mt-1">{user?.specialization}</p>
                                    </div>

                                    <div className="px-2 py-1.5">
                                        {user?.departments && user.departments.length > 0 && (
                                            <div className="px-2 py-2">
                                                <p className="text-[9px] text-gray-500 uppercase mb-1.5">الأقسام</p>
                                                <div className="flex flex-wrap gap-1">
                                                    {user.departments.map((dept) => (
                                                        <span key={dept} className="px-2 py-0.5 rounded bg-white/5 text-[10px] text-gray-400">
                                                            {dept}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>

                                    <div className="border-t border-white/5">
                                        <button
                                            onClick={() => { setShowMenu(false); logout(); }}
                                            className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-red-400 hover:bg-red-500/10 transition-colors"
                                        >
                                            <LogOut className="w-4 h-4" />
                                            تسجيل الخروج
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {/* Constitution Banner */}
            <div className="px-6 py-2 border-t border-white/5 bg-white/[0.02]">
                <div className="flex items-center gap-2 text-xs text-gray-300">
                    <FileText className="w-3.5 h-3.5 text-emerald-400" />
                    <span>الدستور التحريري هو المرجع الإلزامي في جميع المراحل.</span>
                    <a
                        href="/Constitution.docx"
                        className="text-emerald-300 hover:text-emerald-200 underline"
                        target="_blank"
                        rel="noreferrer"
                    >
                        فتح الدستور
                    </a>
                </div>
            </div>
        </header>
    );
}
