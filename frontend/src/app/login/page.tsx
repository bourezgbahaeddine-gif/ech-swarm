'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { Loader2, Eye, EyeOff, AlertCircle, FileText } from 'lucide-react';

export default function LoginPage() {
    const { login } = useAuth();

    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);

        try {
            const response = await api.post('/auth/login', { username, password });
            const { access_token, user } = response.data;

            // Use auth context to login
            login(access_token, user);

        } catch (err: any) {
            const detail = err.response?.data?.detail || 'خطأ في الاتصال بالخادم';
            setError(detail);
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f] relative overflow-hidden" dir="rtl">
            {/* Background effects */}
            <div className="absolute inset-0">
                <div className="absolute top-1/4 right-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl" />
                <div className="absolute bottom-1/4 left-1/4 w-96 h-96 bg-cyan-500/8 rounded-full blur-3xl" />
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-violet-500/5 rounded-full blur-3xl" />
            </div>

            {/* Login Card */}
            <div className="relative w-full max-w-md mx-4">
                <div className="rounded-3xl bg-gradient-to-b from-gray-800/60 to-gray-900/80 backdrop-blur-xl border border-white/10 shadow-2xl p-8">
                    {/* Logo */}
                    <div className="text-center mb-6">
                        <div className="w-16 h-16 mx-auto rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center overflow-hidden mb-4">
                            <img src="/ech-logo.png" alt="Echorouk" className="w-10 h-10 object-contain" />
                        </div>
                        <h1 className="text-2xl font-bold text-white">غرفة الشروق الذكية</h1>
                        <p className="text-sm text-gray-400 mt-1">AI Swarm Newsroom</p>
                    </div>

                    {/* Constitution Notice */}
                    <div className="mb-6 px-4 py-2 rounded-xl bg-white/[0.03] border border-white/10 flex items-center gap-2">
                        <FileText className="w-4 h-4 text-emerald-400" />
                        <p className="text-xs text-gray-300">
                            الدستور التحريري مرجع إلزامي. <a className="underline text-emerald-300" href="/Constitution.docx" target="_blank" rel="noreferrer">فتح الدستور</a>
                        </p>
                    </div>

                    {/* Error Alert */}
                    {error && (
                        <div className="mb-6 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center gap-2 animate-fade-in-up">
                            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                            <p className="text-sm text-red-400">{error}</p>
                        </div>
                    )}

                    {/* Login Form */}
                    <form onSubmit={handleLogin} className="space-y-5">
                        <div>
                            <label className="block text-xs font-medium text-gray-400 mb-2">
                                اسم المستخدم
                            </label>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                placeholder="مثال: s.hawas"
                                required
                                autoComplete="username"
                                className="w-full h-12 px-4 rounded-xl bg-white/5 border border-white/10 text-white text-sm
                           placeholder:text-gray-600 focus:outline-none focus:border-emerald-500/50 focus:ring-2
                           focus:ring-emerald-500/20 transition-all duration-200"
                                dir="ltr"
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-medium text-gray-400 mb-2">
                                كلمة السر
                            </label>
                            <div className="relative">
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••••"
                                    required
                                    autoComplete="current-password"
                                    className="w-full h-12 px-4 pl-11 rounded-xl bg-white/5 border border-white/10 text-white text-sm
                             placeholder:text-gray-600 focus:outline-none focus:border-emerald-500/50 focus:ring-2
                             focus:ring-emerald-500/20 transition-all duration-200"
                                    dir="ltr"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white transition-colors"
                                >
                                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                </button>
                            </div>
                        </div>

                        <button
                            type="submit"
                            disabled={isLoading || !username || !password}
                            className="w-full h-12 rounded-xl bg-gradient-to-r from-emerald-500 to-cyan-500 text-white font-semibold text-sm
                         hover:shadow-lg hover:shadow-emerald-500/25 disabled:opacity-40 disabled:cursor-not-allowed
                         transition-all duration-200 flex items-center justify-center gap-2"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    جاري تسجيل الدخول...
                                </>
                            ) : (
                                'تسجيل الدخول'
                            )}
                        </button>
                    </form>

                    {/* Footer */}
                    <div className="mt-8 pt-6 border-t border-white/5 text-center">
                        <p className="text-[10px] text-gray-600">
                            نظام غرفة الشروق الذكية — الإصدار 1.0
                        </p>
                        <p className="text-[10px] text-gray-700 mt-1">
                            Echorouk AI Swarm © 2025
                        </p>
                    </div>
                </div>

                {/* Team list */}
                <div className="mt-6 rounded-2xl bg-gray-800/20 border border-white/5 p-4">
                    <p className="text-[10px] text-gray-500 text-center mb-3">فريق التحرير المتصل</p>
                    <div className="flex flex-wrap justify-center gap-2">
                        {['الوطني', 'الدولي', 'الاقتصاد', 'الرياضة', 'الفرنسي', 'السوشيال'].map((dept) => (
                            <span key={dept} className="px-2 py-1 rounded-lg bg-white/5 text-[10px] text-gray-400">
                                {dept}
                            </span>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
