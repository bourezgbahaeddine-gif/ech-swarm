'use client';

import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import { FileText, CheckCircle } from 'lucide-react';
import { constitutionApi } from '@/lib/constitution-api';
import { useAuth } from '@/lib/auth';

const PUBLIC_PATHS = ['/login'];

export default function AppShell({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const { user } = useAuth();
    const isPublic = PUBLIC_PATHS.includes(pathname);
    const [showConstitution, setShowConstitution] = useState(false);
    const [ack, setAck] = useState(false);

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
        onSuccess: () => setShowConstitution(false),
    });

    useEffect(() => {
        if (isPublic || !user) return;
        if (latest?.data && ackStatus?.data) {
            if (!ackStatus.data.acknowledged) {
                setShowConstitution(true);
            }
        }
    }, [isPublic, user, latest, ackStatus]);

    if (isPublic) {
        return <>{children}</>;
    }

    const confirm = () => {
        const version = latest?.data?.version;
        if (!version) return;
        ackMutation.mutate(version);
    };

    return (
        <div className="flex">
            <Sidebar />
            <main className="flex-1 mr-[260px] min-h-screen transition-all duration-300">
                <TopBar />
                <div className="p-6 mesh-gradient min-h-[calc(100vh-64px)]">
                    {children}
                </div>
            </main>

            {showConstitution && (
                <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-gray-900/90 p-6">
                        <div className="flex items-center gap-2 text-white mb-3">
                            <FileText className="w-5 h-5 text-emerald-400" />
                            <h2 className="text-lg font-semibold">تأكيد قراءة الدستور</h2>
                        </div>
                        <p className="text-sm text-gray-300 leading-relaxed">
                            الدستور التحريري هو المرجع الإلزامي لجميع المراحل. يرجى الاطلاع عليه قبل المتابعة.
                        </p>
                        <div className="mt-3">
                            <a
                                href="/constitution"
                                className="text-emerald-300 hover:text-emerald-200 underline text-sm"
                                target="_blank"
                                rel="noreferrer"
                            >
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
