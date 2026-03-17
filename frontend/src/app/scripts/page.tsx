'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, CheckCircle2, Clapperboard, Eye, RefreshCw, Video } from 'lucide-react';

import { scriptsApi, type ScriptProjectRecord } from '@/lib/api';
import { cn, formatRelativeTime } from '@/lib/utils';

type ScriptTypeFilter = 'all' | 'story_script' | 'video_script' | 'bulletin_daily' | 'bulletin_weekly';
type ScriptStatusFilter = 'all' | 'new' | 'generating' | 'failed' | 'ready_for_review' | 'approved' | 'rejected' | 'archived';

const TYPE_LABELS: Record<string, string> = {
  story_script: 'سكريبت قصة',
  video_script: 'سكريبت فيديو',
  bulletin_daily: 'نشرة يومية',
  bulletin_weekly: 'نشرة أسبوعية',
};

const STATUS_LABELS: Record<string, string> = {
  new: 'جديد',
  generating: 'قيد التوليد',
  failed: 'فشل',
  ready_for_review: 'بانتظار المراجعة',
  approved: 'معتمد',
  rejected: 'مرفوض',
  archived: 'مؤرشف',
};

export default function ScriptsPage() {
  const [typeFilter, setTypeFilter] = useState<ScriptTypeFilter>('all');
  const [statusFilter, setStatusFilter] = useState<ScriptStatusFilter>('all');

  const listQuery = useQuery({
    queryKey: ['scripts-list', typeFilter, statusFilter],
    queryFn: () =>
      scriptsApi.list({
        limit: 120,
        type: typeFilter === 'all' ? undefined : typeFilter,
        status: statusFilter === 'all' ? undefined : statusFilter,
      }),
    refetchInterval: 20_000,
  });

  const projects = useMemo(() => listQuery.data?.data || [], [listQuery.data?.data]);
  const videoProjects = useMemo(() => projects.filter((item) => item.type === 'video_script'), [projects]);
  const reviewCount = projects.filter((item) => item.status === 'ready_for_review').length;
  const failedCount = projects.filter((item) => item.status === 'failed').length;
  const approvedCount = projects.filter((item) => item.status === 'approved').length;

  return (
    <div className="space-y-5" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="inline-flex items-center gap-2 text-2xl font-bold text-white">
            <Clapperboard className="h-6 w-6 text-cyan-300" />
            Video Script Studio
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            مساحة إعداد ومراجعة وتسليم حزمة فيديو تحريرية، وليست مجرد مولد سكربت مع قائمة مراجعة.
          </p>
        </div>
        <button
          type="button"
          onClick={() => listQuery.refetch()}
          className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-slate-200"
        >
          <RefreshCw className={cn('h-4 w-4', listQuery.isFetching && 'animate-spin')} />
          تحديث
        </button>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <SummaryCard title="مشاريع الفيديو" value={videoProjects.length} hint="كل مشاريع الفيديو في الاستوديو" tone="cyan" />
        <SummaryCard title="بانتظار المراجعة" value={reviewCount} hint="تحتاج قرارًا أو مراجعة تحريرية" tone="amber" />
        <SummaryCard title="فشل" value={failedCount} hint="تحتاج إعادة توليد أو إصلاحًا سريعًا" tone="red" />
        <SummaryCard title="معتمد" value={approvedCount} hint="جاهز لحزمة التسليم أو التنفيذ" tone="emerald" />
      </div>

      <div className="grid gap-3 lg:grid-cols-[280px,1fr]">
        <aside className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4">
          <div>
            <h2 className="text-sm font-semibold text-white">فلاتر الاستوديو</h2>
            <p className="mt-1 text-xs text-slate-400">
              رتّب قائمة المشاريع حسب النوع أو الحالة للوصول السريع إلى ما يحتاجك الآن.
            </p>
          </div>
          <div className="space-y-2">
            <label className="text-xs text-slate-400">النوع</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as ScriptTypeFilter)}
              className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
            >
              <option value="all">كل الأنواع</option>
              <option value="video_script">سكريبت فيديو</option>
              <option value="story_script">سكريبت قصة</option>
              <option value="bulletin_daily">نشرة يومية</option>
              <option value="bulletin_weekly">نشرة أسبوعية</option>
            </select>
          </div>
          <div className="space-y-2">
            <label className="text-xs text-slate-400">الحالة</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as ScriptStatusFilter)}
              className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
            >
              <option value="all">كل الحالات</option>
              <option value="new">جديد</option>
              <option value="generating">قيد التوليد</option>
              <option value="failed">فشل</option>
              <option value="ready_for_review">بانتظار المراجعة</option>
              <option value="approved">معتمد</option>
              <option value="rejected">مرفوض</option>
              <option value="archived">مؤرشف</option>
            </select>
          </div>
          <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-3 text-xs text-cyan-100">
            كل مشروع فيديو يحتوي الآن على مساحة عمل خاصة بالمشاهد والتسليم، لذلك ابدأ من المشروع الذي يحتاجك أكثر الآن.
          </div>
        </aside>

        <section className="space-y-3">
          {listQuery.isLoading ? (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-slate-400">جارٍ تحميل مشاريع السكريبت...</div>
          ) : projects.length === 0 ? (
            <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-slate-400">لا توجد مشاريع تطابق الفلاتر الحالية.</div>
          ) : (
            <div className="grid gap-3 xl:grid-cols-2">
              {projects.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function SummaryCard({
  title,
  value,
  hint,
  tone,
}: {
  title: string;
  value: number;
  hint: string;
  tone: 'cyan' | 'amber' | 'red' | 'emerald';
}) {
  const toneClass =
    tone === 'red'
      ? 'border-red-500/30 bg-red-500/10'
      : tone === 'amber'
        ? 'border-amber-500/30 bg-amber-500/10'
        : tone === 'emerald'
          ? 'border-emerald-500/30 bg-emerald-500/10'
          : 'border-cyan-500/30 bg-cyan-500/10';

  return (
    <div className={cn('rounded-2xl border p-4', toneClass)}>
      <p className="text-xs text-slate-300">{title}</p>
      <p className="mt-2 text-3xl font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs text-slate-400">{hint}</p>
    </div>
  );
}

function ProjectCard({ project }: { project: ScriptProjectRecord }) {
  const summary = project.video_workspace;
  const blockers = summary?.blockers?.length ?? project.latest_quality_blockers ?? 0;
  const warnings = summary?.warnings?.length ?? project.latest_quality_warnings ?? 0;

  return (
    <Link
      href={`/scripts/${project.id}`}
      className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 transition hover:border-cyan-400/40 hover:bg-slate-900/80"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-cyan-300">{TYPE_LABELS[project.type] || project.type}</p>
          <h3 className="mt-1 text-lg font-semibold leading-7 text-white">{project.title}</h3>
        </div>
        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-200">
          {STATUS_LABELS[project.status] || project.status}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-300">
        <InfoChip icon={<Video className="h-3.5 w-3.5" />} label={`آخر نسخة: v${project.latest_version ?? '-'}`} />
        <InfoChip icon={<AlertTriangle className="h-3.5 w-3.5" />} label={`عوائق: ${blockers}`} />
        <InfoChip icon={<CheckCircle2 className="h-3.5 w-3.5" />} label={`تنبيهات: ${warnings}`} />
      </div>

      {summary ? (
        <div className="mt-4 rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-3 text-sm text-slate-100">
          <p className="font-medium text-white">أفضل إجراء الآن</p>
          <p className="mt-1">{summary.next_action || 'راجع المشاهد وحدد ما الذي يحتاج تعديلًا أولًا.'}</p>
          <p className="mt-2 text-xs text-slate-300">
            {summary.video_profile || 'news_package'} · {summary.target_platform || 'youtube'} · {summary.total_duration_s || 0} ثانية
          </p>
        </div>
      ) : null}

      <div className="mt-4 flex items-center justify-between text-xs text-slate-400">
        <span>آخر تحديث: {project.updated_at ? formatRelativeTime(project.updated_at) : '-'}</span>
        <span className="inline-flex items-center gap-1 text-cyan-300">
          <Eye className="h-3.5 w-3.5" />
          افتح مساحة العمل
        </span>
      </div>
    </Link>
  );
}

function InfoChip({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-white/5 px-2.5 py-1">
      {icon}
      {label}
    </span>
  );
}
