'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle, FileText } from 'lucide-react';
import { cn } from '@/lib/utils';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import { constitutionApi } from '@/lib/constitution-api';
import { useAuth } from '@/lib/auth';

const PUBLIC_PATHS = ['/login'];

export default function AppShell({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const isPublic = PUBLIC_PATHS.includes(pathname);
    const [ack, setAck] = useState(false);
    const [ackDismissed, setAckDismissed] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
    const [theme, setTheme] = useState<'light' | 'dark'>(() => {
        if (typeof window === 'undefined') return 'light';
        return localStorage.getItem('ech_theme') === 'dark' ? 'dark' : 'light';
    });

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        if (typeof window !== 'undefined') {
            localStorage.setItem('ech_theme', theme);
        }
    }, [theme]);

    const toggleTheme = () => {
        setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
    };

    const { data: latest } = useQuery({
        queryKey: ['constitution-latest'],
        queryFn: () => constitutionApi.latest(),
        enabled: !isPublic,
    });

    const { data: ackStatus } = useQuery({
        queryKey: ['constitution-ack'],
        queryFn: () => constitutionApi.ackStatus(),
        enabled: !isPublic && !!user,
    });

    const ackMutation = useMutation({
        mutationFn: (version: string) => constitutionApi.acknowledge(version),
        onSuccess: async () => {
            setAckDismissed(true);
            await queryClient.invalidateQueries({ queryKey: ['constitution-ack'] });
        },
    });

    if (isPublic) return <>{children}</>;

    const shouldShowConstitutionGate = Boolean(
        !ackDismissed &&
        user &&
        latest?.data &&
        ackStatus?.data &&
        !ackStatus.data.acknowledged
    );

    const confirm = () => {
        const version = latest?.data?.version;
        if (!version) return;
        ackMutation.mutate(version);
    };

    return (
        <div className="flex app-theme-shell">
            <Sidebar
                collapsed={sidebarCollapsed}
                onToggleCollapsed={() => setSidebarCollapsed((prev) => !prev)}
                mobileOpen={mobileSidebarOpen}
                onCloseMobile={() => setMobileSidebarOpen(false)}
            />
            <main
                className={cn(
                    'flex-1 min-h-screen transition-all duration-300',
                    sidebarCollapsed ? 'md:mr-[72px]' : 'md:mr-[260px]'
                )}
            >
                <TopBar theme={theme} onToggleTheme={toggleTheme} onOpenSidebar={() => setMobileSidebarOpen(true)} />
                <div className="p-3 md:p-6 mesh-gradient min-h-[calc(100vh-64px)]">{children}</div>
            </main>

            {shouldShowConstitutionGate && (
                <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-gray-900/90 p-6 app-surface">
                        <div className="flex items-center gap-2 text-white mb-3">
                            <FileText className="w-5 h-5 text-emerald-400" />
                            <h2 className="text-lg font-semibold">تأكيد قراءة الدستور</h2>
                        </div>
                        <p className="text-sm text-gray-300 leading-relaxed">
                            الدستور التحريري هو المرجع الإلزامي لجميع المراحل. يرجى الاطلاع عليه قبل المتابعة.
                        </p>
                        <div className="mt-3">
                            <a href="/constitution" className="text-emerald-300 hover:text-emerald-200 underline text-sm" target="_blank" rel="noreferrer">
                                فتح الدستور
                            </a>
                        </div>
                        <label className="mt-4 flex items-center gap-2 text-sm text-gray-300">
                            <input
                                type="checkbox"
                                checked={ack}
                                onChange={(e) => setAck(e.target.checked)}
                                className="accent-emerald-500"
                            />
                            أقر أنني قرأت الدستور وسألتزم به
                        </label>
                        <button
                            onClick={confirm}
                            disabled={!ack || ackMutation.isPending}
                            className="mt-4 w-full h-11 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            <CheckCircle className="w-4 h-4" />
                            متابعة
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
