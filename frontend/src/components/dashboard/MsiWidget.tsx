'use client';

import { useQuery } from '@tanstack/react-query';
import { Activity } from 'lucide-react';

import { msiApi } from '@/lib/api';

export default function MsiWidget() {
    const { data: dailyData } = useQuery({
        queryKey: ['msi-top-daily-widget'],
        queryFn: () => msiApi.top({ mode: 'daily', limit: 5 }),
        refetchInterval: 60000,
    });
    const { data: weeklyData } = useQuery({
        queryKey: ['msi-top-weekly-widget'],
        queryFn: () => msiApi.top({ mode: 'weekly', limit: 5 }),
        refetchInterval: 120000,
    });

    const dailyItems = dailyData?.data?.items || [];
    const weeklyItems = weeklyData?.data?.items || [];

    return (
        <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
            <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Activity className="w-4 h-4 text-cyan-300" />
                    MSI Monitor
                </h3>
                <a href="/msi" className="text-xs text-emerald-300 hover:text-emerald-200">فتح</a>
            </div>

            <div className="space-y-3">
                <div>
                    <p className="text-[11px] text-gray-400 mb-1">الأكثر اضطراباً اليوم</p>
                    <div className="space-y-1.5">
                        {dailyItems.slice(0, 5).map((item) => (
                            <div key={`d-${item.entity}-${item.period_end}`} className="flex items-center justify-between text-xs rounded-lg bg-white/5 border border-white/10 px-2 py-1.5">
                                <span className="text-gray-200 line-clamp-1">{item.entity}</span>
                                <span className="text-red-300 font-semibold">{item.msi.toFixed(1)}</span>
                            </div>
                        ))}
                        {dailyItems.length === 0 && <p className="text-xs text-gray-500">لا توجد بيانات بعد.</p>}
                    </div>
                </div>

                <div>
                    <p className="text-[11px] text-gray-400 mb-1">الأكثر اضطراباً أسبوعياً</p>
                    <div className="space-y-1.5">
                        {weeklyItems.slice(0, 5).map((item) => (
                            <div key={`w-${item.entity}-${item.period_end}`} className="flex items-center justify-between text-xs rounded-lg bg-white/5 border border-white/10 px-2 py-1.5">
                                <span className="text-gray-200 line-clamp-1">{item.entity}</span>
                                <span className="text-orange-300 font-semibold">{item.msi.toFixed(1)}</span>
                            </div>
                        ))}
                        {weeklyItems.length === 0 && <p className="text-xs text-gray-500">لا توجد بيانات بعد.</p>}
                    </div>
                </div>
            </div>
        </div>
    );
}
