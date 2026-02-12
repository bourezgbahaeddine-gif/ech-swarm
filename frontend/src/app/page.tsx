'use client';

import { useQuery } from '@tanstack/react-query';
import { dashboardApi, newsApi } from '@/lib/api';
import StatsCards from '@/components/dashboard/StatsCards';
import NewsFeed from '@/components/dashboard/NewsFeed';
import PipelineMonitor from '@/components/dashboard/PipelineMonitor';
import AgentControl from '@/components/dashboard/AgentControl';

export default function DashboardPage() {
  const { data: statsData, isLoading: statsLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => dashboardApi.stats(),
  });

  const { data: breakingData, isLoading: breakingLoading } = useQuery({
    queryKey: ['breaking-news'],
    queryFn: () => newsApi.breaking(5),
  });

  const { data: pendingData, isLoading: pendingLoading } = useQuery({
    queryKey: ['pending-articles'],
    queryFn: () => newsApi.pending(10),
  });

  const { data: pipelineData, isLoading: pipelineLoading } = useQuery({
    queryKey: ['pipeline-runs'],
    queryFn: () => dashboardApi.pipelineRuns(10),
  });

  const { data: agentsData } = useQuery({
    queryKey: ['agents-status'],
    queryFn: () => dashboardApi.agentStatus(),
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="animate-fade-in-up">
        <h1 className="text-2xl font-bold text-white">لوحة القيادة</h1>
        <p className="text-sm text-gray-500 mt-1">مرحباً برئيس التحرير — إليك آخر المستجدات</p>
      </div>

      {/* Stats Grid */}
      <div className="animate-fade-in-up" style={{ animationDelay: '100ms' }}>
        <StatsCards stats={statsData?.data} isLoading={statsLoading} />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Breaking + Pending */}
        <div className="lg:col-span-2 space-y-6">
          <div className="animate-fade-in-up" style={{ animationDelay: '200ms' }}>
            <NewsFeed
              articles={breakingData?.data}
              isLoading={breakingLoading}
              title="🚨 أخبار عاجلة"
            />
          </div>

          <div className="animate-fade-in-up" style={{ animationDelay: '300ms' }}>
            <NewsFeed
              articles={pendingData?.data}
              isLoading={pendingLoading}
              title="📋 بانتظار المراجعة"
            />
          </div>
        </div>

        {/* Right: Controls + Pipeline */}
        <div className="space-y-6">
          <div className="animate-fade-in-up" style={{ animationDelay: '250ms' }}>
            <AgentControl agents={agentsData?.data} />
          </div>

          <div className="animate-fade-in-up" style={{ animationDelay: '350ms' }}>
            <PipelineMonitor runs={pipelineData?.data} isLoading={pipelineLoading} />
          </div>
        </div>
      </div>
    </div>
  );
}
