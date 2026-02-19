'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { dashboardApi, newsApi } from '@/lib/api';
import StatsCards from '@/components/dashboard/StatsCards';
import NewsFeed from '@/components/dashboard/NewsFeed';
import PipelineMonitor from '@/components/dashboard/PipelineMonitor';
import AgentControl from '@/components/dashboard/AgentControl';
import MsiWidget from '@/components/dashboard/MsiWidget';
import { useAuth } from '@/lib/auth';

export default function DashboardPage() {
  const router = useRouter();
  const { user } = useAuth();
  const role = (user?.role || '').toLowerCase();
  const isManagerView = role === 'director' || role === 'editor_chief';

  const { data: statsData, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => dashboardApi.stats(),
    refetchInterval: 20000,
    refetchOnWindowFocus: true,
    enabled: isManagerView,
  });

  const { data: breakingData, isLoading: breakingLoading } = useQuery({
    queryKey: ['breaking-news'],
    queryFn: () => newsApi.breaking(5),
    refetchInterval: 12000,
    refetchOnWindowFocus: true,
    enabled: isManagerView,
  });

  const { data: pendingData, isLoading: pendingLoading } = useQuery({
    queryKey: ['pending-articles'],
    queryFn: () => newsApi.pending(10),
    refetchInterval: 15000,
    refetchOnWindowFocus: true,
    enabled: isManagerView,
  });

  const { data: pipelineData, isLoading: pipelineLoading } = useQuery({
    queryKey: ['pipeline-runs'],
    queryFn: () => dashboardApi.pipelineRuns(10),
    refetchInterval: 15000,
    refetchOnWindowFocus: true,
    enabled: isManagerView,
  });

  const { data: agentsData } = useQuery({
    queryKey: ['agents-status'],
    queryFn: () => dashboardApi.agentStatus(),
    refetchInterval: 20000,
    refetchOnWindowFocus: true,
    enabled: isManagerView,
  });

  useEffect(() => {
    if (user && !isManagerView) {
      router.replace('/news');
    }
  }, [isManagerView, router, user]);

  if (user && !isManagerView) {
    return (
      <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-8 text-center text-gray-300">
        جاري تحويلك إلى واجهة الأخبار...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="animate-fade-in-up">
        <h1 className="text-2xl font-bold text-white">لوحة القيادة</h1>
        <p className="text-sm text-gray-500 mt-1">متابعة تشغيل المنصة لمدير التحرير</p>
      </div>

      <div className="animate-fade-in-up" style={{ animationDelay: '100ms' }}>
        <StatsCards stats={statsData?.data} isLoading={statsLoading} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="animate-fade-in-up" style={{ animationDelay: '200ms' }}>
            <NewsFeed articles={breakingData?.data} isLoading={breakingLoading} title="أخبار عاجلة" />
          </div>

          <div className="animate-fade-in-up" style={{ animationDelay: '300ms' }}>
            <NewsFeed articles={pendingData?.data} isLoading={pendingLoading} title="بانتظار المراجعة" />
          </div>
        </div>

        <div className="space-y-6">
          <div className="animate-fade-in-up" style={{ animationDelay: '250ms' }}>
            <AgentControl agents={agentsData?.data} />
          </div>

          <div className="animate-fade-in-up" style={{ animationDelay: '300ms' }}>
            <MsiWidget />
          </div>

          <div className="animate-fade-in-up" style={{ animationDelay: '380ms' }}>
            <PipelineMonitor runs={pipelineData?.data} isLoading={pipelineLoading} />
          </div>
        </div>
      </div>
    </div>
  );
}
