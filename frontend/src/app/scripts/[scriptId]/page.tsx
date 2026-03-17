'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'next/navigation';
import { AlertTriangle, Download, RefreshCw } from 'lucide-react';

import {
  scriptsApi,
  type ScriptOutputRecord,
  type ScriptProjectRecord,
  type VideoCaptionLine,
  type VideoScriptScene,
} from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn, formatRelativeTime } from '@/lib/utils';

type TabKey = 'overview' | 'vo' | 'scenes' | 'assets' | 'captions' | 'versions' | 'delivery';

const TABS: TabKey[] = ['overview', 'vo', 'scenes', 'assets', 'captions', 'versions', 'delivery'];

const TAB_LABELS: Record<TabKey, string> = {
  overview: 'نظرة عامة',
  vo: 'النص الصوتي',
  scenes: 'المشاهد',
  assets: 'الأصول البصرية',
  captions: 'الكابشن',
  versions: 'النسخ',
  delivery: 'التسليم',
};

const VIDEO_PROFILE_OPTIONS = [
  'short_vertical',
  'news_package',
  'explainer',
  'breaking_clip',
  'voiceover_package',
  'document_explainer',
];

const PLATFORM_OPTIONS = ['instagram_reels', 'youtube', 'youtube_shorts', 'facebook', 'x'];

type VideoWorkspaceModel = ReturnType<typeof toVideoWorkspace>;

export default function ScriptWorkspacePage() {
  const params = useParams<{ scriptId: string }>();
  const scriptId = Number(params?.scriptId);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [tab, setTab] = useState<TabKey>('overview');
  const [message, setMessage] = useState<string | null>(null);
  const [fromVersion, setFromVersion] = useState<number | null>(null);
  const [toVersion, setToVersion] = useState<number | null>(null);

  const projectQuery = useQuery({
    queryKey: ['script-project', scriptId],
    queryFn: () => scriptsApi.get(scriptId),
    enabled: Number.isFinite(scriptId) && scriptId > 0,
    refetchInterval: 20_000,
  });

  const project = projectQuery.data?.data;
  const outputs = project?.outputs || [];
  const latestOutput = outputs[0];
  const video = useMemo(() => toVideoWorkspace(project, latestOutput), [project, latestOutput]);
  const canReview = user?.role === 'director' || user?.role === 'editor_chief';

  const effectiveToVersion = toVersion ?? outputs[0]?.version ?? null;
  const effectiveFromVersion = fromVersion ?? outputs[1]?.version ?? outputs[0]?.version ?? null;

  const diffQuery = useQuery({
    queryKey: ['script-diff', scriptId, effectiveFromVersion, effectiveToVersion],
    queryFn: () => scriptsApi.versionsDiff(scriptId, effectiveFromVersion as number, effectiveToVersion as number),
    enabled:
      Number.isFinite(scriptId) &&
      scriptId > 0 &&
      Boolean(effectiveFromVersion && effectiveToVersion && effectiveFromVersion !== effectiveToVersion),
  });

  const invalidate = async (nextMessage?: string) => {
    if (nextMessage) setMessage(nextMessage);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['script-project', scriptId] }),
      queryClient.invalidateQueries({ queryKey: ['scripts-list'] }),
    ]);
  };

  const updateWorkspace = useMutation({
    mutationFn: (payload: Parameters<typeof scriptsApi.updateVideoWorkspace>[1]) =>
      scriptsApi.updateVideoWorkspace(scriptId, payload),
    onSuccess: async () => invalidate('تم حفظ إعدادات المشروع بنجاح.'),
  });

  const updateScene = useMutation({
    mutationFn: ({ sceneIdx, payload }: { sceneIdx: number; payload: Parameters<typeof scriptsApi.updateScene>[2] }) =>
      scriptsApi.updateScene(scriptId, sceneIdx, payload),
    onSuccess: async () => invalidate('تم تحديث المشهد.'),
  });

  const runAction = async (runner: () => Promise<unknown>, successMessage: string) => {
    await runner();
    await invalidate(successMessage);
  };

  if (projectQuery.isLoading) {
    return (
      <div dir="rtl" className="rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-slate-400">
        جارٍ تحميل مشروع الفيديو...
      </div>
    );
  }

  if (!project) {
    return (
      <div dir="rtl" className="rounded-2xl border border-white/10 bg-white/5 p-6 text-sm text-slate-400">
        لم نتمكن من العثور على هذا المشروع.
      </div>
    );
  }

  if (project.type !== 'video_script') {
    return (
      <div dir="rtl" className="space-y-4">
        <Link href="/scripts" className="text-sm text-cyan-300">
          العودة إلى Script Studio
        </Link>
        <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-6 text-sm text-slate-300">
          صفحة المساحة التفصيلية متاحة الآن فقط لمشاريع الفيديو.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/scripts" className="text-sm text-cyan-300">
            العودة إلى Script Studio
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-white">{project.title}</h1>
          <p className="mt-1 text-sm text-slate-400">
            {labelForProfile(video.video_profile)} · {labelForPlatform(video.target_platform)} · آخر تحديث{' '}
            {project.updated_at ? formatRelativeTime(project.updated_at) : '-'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => projectQuery.refetch()}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 text-sm text-slate-200"
          >
            <RefreshCw className={cn('h-4 w-4', projectQuery.isFetching && 'animate-spin')} />
            تحديث
          </button>
          <button
            type="button"
            onClick={() => void runAction(() => scriptsApi.exportDelivery(scriptId), 'تم توليد حزمة التسليم.')}
            className="inline-flex h-10 items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 text-sm text-emerald-100"
          >
            <Download className="h-4 w-4" />
            صدّر الحزمة
          </button>
        </div>
      </div>

      {message ? (
        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 p-3 text-sm text-cyan-100">{message}</div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[260px,1fr,320px]">
        <aside className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4">
          <Panel title="ملخص المشروع">
            <Row label="الحالة" value={labelForStatus(project.status)} />
            <Row label="الملف" value={labelForProfile(video.video_profile)} />
            <Row label="المنصة" value={labelForPlatform(video.target_platform)} />
            <Row label="الهدف" value={labelForObjective(video.editorial_objective)} />
            <Row label="المدة" value={`${video.total_duration_s} ثانية`} />
            <Row label="التسليم" value={labelForDeliveryStatus(video.delivery.status || video.delivery_status || 'draft')} />
          </Panel>

          <Panel title="إجراءات سريعة">
            <div className="grid gap-2">
              <button
                type="button"
                onClick={() => setTab('scenes')}
                className="inline-flex h-10 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 text-sm text-cyan-100"
              >
                افتح Workspace المشاهد
              </button>
              <button
                type="button"
                onClick={() => void runAction(() => scriptsApi.regenerate(scriptId, {}), 'تم طلب إعادة توليد المشروع.')}
                className="inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-slate-100"
              >
                أعد توليد المشروع
              </button>
              {canReview ? (
                <button
                  type="button"
                  onClick={() => void runAction(() => scriptsApi.approve(scriptId, {}), 'تم اعتماد المشروع.')}
                  className="inline-flex h-10 items-center justify-center rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 text-sm text-emerald-100"
                >
                  اعتمد المشروع
                </button>
              ) : null}
              {canReview ? (
                <button
                  type="button"
                  onClick={() => {
                    const reason = window.prompt('اكتب سبب الرفض أو الإرجاع');
                    if (!reason) return;
                    void runAction(() => scriptsApi.reject(scriptId, { reason }), 'تم رفض المشروع.');
                  }}
                  className="inline-flex h-10 items-center justify-center rounded-xl border border-red-500/30 bg-red-500/10 px-4 text-sm text-red-100"
                >
                  ارفض المشروع
                </button>
              ) : null}
            </div>
          </Panel>

          <Panel title="النسخ المتاحة">
            <div className="space-y-2">
              {outputs.map((output) => (
                <div key={output.id} className="rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-300">
                  <div className="flex items-center justify-between">
                    <span>v{output.version}</span>
                    <span>{output.created_at ? formatRelativeTime(output.created_at) : '-'}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      void runAction(
                        () => scriptsApi.duplicateVersion(scriptId, { source_version: output.version }),
                        'تم إنشاء نسخة جديدة من هذا الإصدار.',
                      )
                    }
                    className="mt-2 inline-flex items-center gap-1 text-cyan-300"
                  >
                    انسخ هذه النسخة
                  </button>
                </div>
              ))}
            </div>
          </Panel>
        </aside>

        <main className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4">
          <div className="flex flex-wrap gap-2">
            {TABS.map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setTab(item)}
                className={cn(
                  'h-10 rounded-xl border px-4 text-sm',
                  tab === item ? 'border-cyan-400/50 bg-cyan-500/15 text-cyan-100' : 'border-white/10 bg-white/5 text-slate-300',
                )}
              >
                {TAB_LABELS[item]}
              </button>
            ))}
          </div>

          {tab === 'overview' ? (
            <OverviewPanel
              key={`overview-${video.video_profile}-${video.target_platform}-${video.editorial_objective}-${video.pace_notes}`}
              video={video}
              onSave={(payload) => updateWorkspace.mutate(payload)}
              saving={updateWorkspace.isPending}
            />
          ) : null}

          {tab === 'vo' ? (
            <VoPanel
              key={`vo-${video.hook}-${video.closing}-${video.vo_script.length}`}
              video={video}
              onSave={(payload) => updateWorkspace.mutate(payload)}
              saving={updateWorkspace.isPending}
            />
          ) : null}

          {tab === 'scenes' ? (
            <ScenesPanel
              video={video}
              pending={updateScene.isPending}
              onSave={(sceneIdx, payload) => updateScene.mutate({ sceneIdx, payload })}
              onMove={async (sceneIdx, direction) => {
                const scenes = [...video.scenes];
                const index = scenes.findIndex((item) => item.idx === sceneIdx);
                const target = direction === 'up' ? index - 1 : index + 1;
                if (index < 0 || target < 0 || target >= scenes.length) return;
                [scenes[index], scenes[target]] = [scenes[target], scenes[index]];
                await runAction(
                  () => scriptsApi.reorderScenes(scriptId, scenes.map((item) => item.idx)),
                  'تمت إعادة ترتيب المشاهد.',
                );
              }}
              onAdd={() =>
                void runAction(
                  () => scriptsApi.addScene(scriptId, { insert_after: video.scenes.length, duration_s: 5 }),
                  'تمت إضافة مشهد جديد.',
                )
              }
              onDelete={(sceneIdx) => void runAction(() => scriptsApi.deleteScene(scriptId, sceneIdx), 'تم حذف المشهد.')}
              onSplit={(sceneIdx, splitDuration) =>
                void runAction(() => scriptsApi.splitScene(scriptId, sceneIdx, splitDuration), 'تم تقسيم المشهد.')
              }
              onMerge={(sceneIdx) =>
                void runAction(() => scriptsApi.mergeScenes(scriptId, sceneIdx + 1, sceneIdx), 'تم دمج المشهدين.')
              }
              onToggleLock={(sceneIdx, locked) =>
                void runAction(
                  () => (locked ? scriptsApi.unlockScene(scriptId, sceneIdx) : scriptsApi.lockScene(scriptId, sceneIdx)),
                  locked ? 'تم فتح المشهد للتعديل.' : 'تم قفل المشهد.',
                )
              }
              onRegenerate={(sceneIdx) =>
                void runAction(() => scriptsApi.regenerateScene(scriptId, sceneIdx), 'تم طلب إعادة توليد المشهد.')
              }
            />
          ) : null}

          {tab === 'assets' ? (
            <AssetsPanel
              video={video}
              onChange={(sceneIdx, asset_status) => updateScene.mutate({ sceneIdx, payload: { asset_status } })}
            />
          ) : null}

          {tab === 'captions' ? (
            <CaptionsPanel
              key={`captions-${video.captions_lines.map((line) => `${line.idx}-${line.text}`).join('|')}`}
              lines={video.captions_lines}
              onSave={(lines) => void runAction(() => scriptsApi.updateCaptions(scriptId, lines), 'تم حفظ الكابشن.')}
            />
          ) : null}

          {tab === 'versions' ? (
            <VersionsPanel
              outputs={outputs}
              fromVersion={effectiveFromVersion}
              toVersion={effectiveToVersion}
              setFromVersion={setFromVersion}
              setToVersion={setToVersion}
              diffData={diffQuery.data?.data}
              loading={diffQuery.isFetching}
            />
          ) : null}

          {tab === 'delivery' ? (
            <DeliveryPanel
              key={`delivery-${video.delivery.title}-${video.delivery.status}-${video.thumbnail_ideas.join('|')}`}
              delivery={video.delivery}
              title={project.title}
              thumbnailIdeas={video.thumbnail_ideas}
              onSave={(payload) => void runAction(() => scriptsApi.updateDelivery(scriptId, payload), 'تم حفظ حزمة التسليم.')}
              onExport={() => void runAction(() => scriptsApi.exportDelivery(scriptId), 'تم تصدير الحزمة.')}
            />
          ) : null}
        </main>

        <aside className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4">
          <Panel title="لوحة الجودة والإجراء التالي">
            <div className="rounded-xl border border-cyan-500/20 bg-cyan-500/10 p-3 text-sm text-cyan-100">
              <p className="font-semibold text-white">أفضل إجراء الآن</p>
              <p className="mt-1">{project.video_workspace?.next_action || 'راجع المشاهد وحدد أول عنصر يحتاج تعديلًا.'}</p>
            </div>
            <Row label="قوة البداية" value={`${Math.round((video.hook_strength || 0) * 100)}%`} />
            <Row label="ملاحظات الإيقاع" value={video.pace_notes || 'لا توجد ملاحظات بعد'} />
            <Row label="عوائق" value={String(project.video_workspace?.blockers?.length || 0)} />
            <Row label="تنبيهات" value={String(project.video_workspace?.warnings?.length || 0)} />
          </Panel>

          <Panel title="العوائق">
            {(project.video_workspace?.blockers || []).length === 0 ? (
              <p className="text-sm text-slate-400">لا توجد عوائق تمنع التقدم الآن.</p>
            ) : (
              <div className="space-y-2">
                {(project.video_workspace?.blockers || []).map((issue) => (
                  <IssueCard key={issue.code} issue={issue} tone="red" />
                ))}
              </div>
            )}
          </Panel>

          <Panel title="التنبيهات">
            {(project.video_workspace?.warnings || []).length === 0 ? (
              <p className="text-sm text-slate-400">لا توجد تنبيهات حالية.</p>
            ) : (
              <div className="space-y-2">
                {(project.video_workspace?.warnings || []).map((issue) => (
                  <IssueCard key={issue.code} issue={issue} tone="amber" />
                ))}
              </div>
            )}
          </Panel>
        </aside>
      </div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-2xl border border-white/10 bg-slate-950/50 p-4">
      <h2 className="text-sm font-semibold text-white">{title}</h2>
      {children}
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 text-sm">
      <span className="text-slate-400">{label}</span>
      <span className="text-left text-slate-100">{value}</span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-2">
      <span className="text-xs text-slate-400">{label}</span>
      {children}
    </label>
  );
}

function OverviewPanel({
  video,
  onSave,
  saving,
}: {
  video: VideoWorkspaceModel;
  onSave: (payload: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const [profile, setProfile] = useState(video.video_profile);
  const [platform, setPlatform] = useState(video.target_platform);
  const [objective, setObjective] = useState(video.editorial_objective);
  const [paceNotes, setPaceNotes] = useState(video.pace_notes || '');

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="إعدادات المشروع">
        <div className="space-y-3">
          <Field label="Video profile">
            <select
              value={profile}
              onChange={(e) => setProfile(e.target.value)}
              className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
            >
              {VIDEO_PROFILE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {labelForProfile(option)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="المنصة المستهدفة">
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
            >
              {PLATFORM_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {labelForPlatform(option)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="الهدف التحريري">
            <input
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
            />
          </Field>
          <Field label="ملاحظات الإيقاع">
            <textarea
              value={paceNotes}
              onChange={(e) => setPaceNotes(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
              rows={4}
            />
          </Field>
          <button
            type="button"
            onClick={() =>
              onSave({
                video_profile: profile,
                target_platform: platform,
                editorial_objective: objective,
                pace_notes: paceNotes,
              })
            }
            className="inline-flex h-10 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 text-sm text-cyan-100"
            disabled={saving}
          >
            {saving ? 'جارٍ الحفظ...' : 'احفظ الإعدادات'}
          </button>
        </div>
      </Panel>

      <Panel title="ملخص سريع">
        <div className="space-y-3 text-sm text-slate-200">
          <Row label="المدة الإجمالية" value={`${video.total_duration_s} ثانية`} />
          <Row label="عدد المشاهد" value={String(video.scenes.length)} />
          <Row label="مشاهد بلا أصول" value={String(video.scenes.filter((scene) => scene.asset_status === 'missing').length)} />
          <Row label="حالة التسليم" value={labelForDeliveryStatus(video.delivery.status || 'draft')} />
        </div>
      </Panel>
    </div>
  );
}

function VoPanel({
  video,
  onSave,
  saving,
}: {
  video: VideoWorkspaceModel;
  onSave: (payload: Record<string, unknown>) => void;
  saving: boolean;
}) {
  const [hook, setHook] = useState(video.hook || '');
  const [voScript, setVoScript] = useState(video.vo_script || '');
  const [closing, setClosing] = useState(video.closing || '');

  return (
    <div className="space-y-4">
      <Field label="الافتتاحية Hook">
        <textarea
          value={hook}
          onChange={(e) => setHook(e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
          rows={3}
        />
      </Field>
      <Field label="النص الصوتي الكامل">
        <textarea
          value={voScript}
          onChange={(e) => setVoScript(e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
          rows={12}
        />
      </Field>
      <Field label="الخاتمة">
        <textarea
          value={closing}
          onChange={(e) => setClosing(e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
          rows={3}
        />
      </Field>
      <button
        type="button"
        onClick={() => onSave({ hook, vo_script: voScript, closing })}
        className="inline-flex h-10 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 text-sm text-cyan-100"
        disabled={saving}
      >
        {saving ? 'جارٍ الحفظ...' : 'احفظ النص الصوتي'}
      </button>
    </div>
  );
}

function ScenesPanel({
  video,
  pending,
  onSave,
  onMove,
  onAdd,
  onDelete,
  onSplit,
  onMerge,
  onToggleLock,
  onRegenerate,
}: {
  video: VideoWorkspaceModel;
  pending: boolean;
  onSave: (sceneIdx: number, payload: Record<string, unknown>) => void;
  onMove: (sceneIdx: number, direction: 'up' | 'down') => Promise<void>;
  onAdd: () => void;
  onDelete: (sceneIdx: number) => void;
  onSplit: (sceneIdx: number, splitDuration: number) => void;
  onMerge: (sceneIdx: number) => void;
  onToggleLock: (sceneIdx: number, locked: boolean) => void;
  onRegenerate: (sceneIdx: number) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between rounded-xl border border-white/10 bg-black/20 p-3">
        <div>
          <p className="text-sm font-semibold text-white">Scene Editor</p>
          <p className="text-xs text-slate-400">عدّل كل مشهد بشكل مستقل ثم احفظه، أو أعد ترتيبه قبل الاعتماد.</p>
        </div>
        <button
          type="button"
          onClick={onAdd}
          className="inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-slate-100"
        >
          أضف مشهدًا
        </button>
      </div>

      <div className="rounded-xl border border-white/10 bg-black/20 p-3">
        <div className="mb-2 flex items-center justify-between text-sm text-slate-300">
          <span>المدة الإجمالية</span>
          <span>{video.total_duration_s} ثانية</span>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-white/5">
          <div className="h-full rounded-full bg-cyan-400" style={{ width: `${Math.min(100, (video.total_duration_s / 180) * 100)}%` }} />
        </div>
      </div>

      <div className="space-y-3">
        {video.scenes.map((scene, index) => (
          <SceneCard
            key={`${scene.idx}-${scene.duration_s}-${scene.locked ? 'locked' : 'open'}-${scene.vo_line}`}
            scene={scene}
            canMoveUp={index > 0}
            canMoveDown={index < video.scenes.length - 1}
            pending={pending}
            onSave={onSave}
            onMove={onMove}
            onDelete={onDelete}
            onSplit={onSplit}
            onMerge={onMerge}
            onToggleLock={onToggleLock}
            onRegenerate={onRegenerate}
          />
        ))}
      </div>
    </div>
  );
}

function SceneCard({
  scene,
  canMoveUp,
  canMoveDown,
  pending,
  onSave,
  onMove,
  onDelete,
  onSplit,
  onMerge,
  onToggleLock,
  onRegenerate,
}: {
  scene: VideoScriptScene;
  canMoveUp: boolean;
  canMoveDown: boolean;
  pending: boolean;
  onSave: (sceneIdx: number, payload: Record<string, unknown>) => void;
  onMove: (sceneIdx: number, direction: 'up' | 'down') => Promise<void>;
  onDelete: (sceneIdx: number) => void;
  onSplit: (sceneIdx: number, splitDuration: number) => void;
  onMerge: (sceneIdx: number) => void;
  onToggleLock: (sceneIdx: number, locked: boolean) => void;
  onRegenerate: (sceneIdx: number) => void;
}) {
  const [duration, setDuration] = useState(scene.duration_s);
  const [visual, setVisual] = useState(scene.visual);
  const [onScreenText, setOnScreenText] = useState(scene.on_screen_text);
  const [voLine, setVoLine] = useState(scene.vo_line);
  const [assetStatus, setAssetStatus] = useState(scene.asset_status || 'missing');

  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-slate-950/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-white">المشهد {scene.idx}</p>
          <p className="text-xs text-slate-400">
            {labelForSceneType(scene.scene_type)} · {labelForPriority(scene.priority)} · {scene.locked ? 'مقفول' : 'قابل للتعديل'}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void onMove(scene.idx, 'up')}
            disabled={!canMoveUp || pending}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-slate-200"
          >
            ↑
          </button>
          <button
            type="button"
            onClick={() => void onMove(scene.idx, 'down')}
            disabled={!canMoveDown || pending}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-slate-200"
          >
            ↓
          </button>
          <button
            type="button"
            onClick={() => onToggleLock(scene.idx, !!scene.locked)}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 px-3 text-slate-200"
          >
            {scene.locked ? 'فتح' : 'قفل'}
          </button>
          <button
            type="button"
            onClick={() => onRegenerate(scene.idx)}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-white/10 bg-white/5 px-3 text-slate-200"
          >
            AI
          </button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Field label="المدة بالثواني">
          <input
            type="number"
            min={1}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
          />
        </Field>
        <Field label="حالة الأصل البصري">
          <select
            value={assetStatus}
            onChange={(e) => setAssetStatus(e.target.value)}
            className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
          >
            <option value="missing">ناقص</option>
            <option value="linked">مرتبط</option>
            <option value="optional">اختياري</option>
          </select>
        </Field>
      </div>

      <Field label="الوصف البصري">
        <textarea
          value={visual}
          onChange={(e) => setVisual(e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
          rows={2}
        />
      </Field>
      <Field label="النص الظاهر على الشاشة">
        <textarea
          value={onScreenText}
          onChange={(e) => setOnScreenText(e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
          rows={2}
        />
      </Field>
      <Field label="VO line">
        <textarea
          value={voLine}
          onChange={(e) => setVoLine(e.target.value)}
          className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
          rows={3}
        />
      </Field>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() =>
            onSave(scene.idx, {
              duration_s: duration,
              visual,
              on_screen_text: onScreenText,
              vo_line: voLine,
              asset_status: assetStatus,
            })
          }
          className="inline-flex h-10 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 text-sm text-cyan-100"
        >
          احفظ المشهد
        </button>
        <button
          type="button"
          onClick={() => {
            const value = window.prompt('أدخل مدة الجزء الأول بعد التقسيم', String(Math.max(1, Math.floor(duration / 2))));
            if (!value) return;
            const splitValue = Number(value);
            if (!Number.isFinite(splitValue)) return;
            onSplit(scene.idx, splitValue);
          }}
          className="inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-slate-100"
        >
          قسّم
        </button>
        <button
          type="button"
          onClick={() => onMerge(scene.idx)}
          className="inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-slate-100"
        >
          ادمج مع السابق
        </button>
        <button
          type="button"
          onClick={() => onDelete(scene.idx)}
          className="inline-flex h-10 items-center justify-center rounded-xl border border-red-500/30 bg-red-500/10 px-4 text-sm text-red-100"
        >
          احذف
        </button>
      </div>
    </div>
  );
}

function AssetsPanel({
  video,
  onChange,
}: {
  video: VideoWorkspaceModel;
  onChange: (sceneIdx: number, assetStatus: string) => void;
}) {
  return (
    <div className="space-y-3">
      {video.scenes.map((scene) => (
        <div key={scene.idx} className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">المشهد {scene.idx}</p>
              <p className="text-xs text-slate-400">{scene.visual || 'لا يوجد وصف بصري بعد'}</p>
            </div>
            <select
              value={scene.asset_status || 'missing'}
              onChange={(e) => onChange(scene.idx, e.target.value)}
              className="h-11 max-w-[180px] rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
            >
              <option value="missing">ناقص</option>
              <option value="linked">مرتبط</option>
              <option value="optional">اختياري</option>
            </select>
          </div>
        </div>
      ))}
    </div>
  );
}

function CaptionsPanel({ lines, onSave }: { lines: VideoCaptionLine[]; onSave: (lines: VideoCaptionLine[]) => void }) {
  const [items, setItems] = useState(lines);

  return (
    <div className="space-y-4">
      {items.map((line, index) => (
        <div key={`${line.idx}-${index}`} className="space-y-2 rounded-2xl border border-white/10 bg-slate-950/60 p-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>سطر {line.idx}</span>
            <span>
              {line.start_s}s → {line.end_s}s
            </span>
          </div>
          <textarea
            value={line.text}
            onChange={(e) => {
              const next = [...items];
              next[index] = { ...next[index], text: e.target.value };
              setItems(next);
            }}
            className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
            rows={2}
          />
        </div>
      ))}
      <button
        type="button"
        onClick={() => onSave(items)}
        className="inline-flex h-10 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 text-sm text-cyan-100"
      >
        احفظ الكابشن
      </button>
    </div>
  );
}

function VersionsPanel({
  outputs,
  fromVersion,
  toVersion,
  setFromVersion,
  setToVersion,
  diffData,
  loading,
}: {
  outputs: ScriptOutputRecord[];
  fromVersion: number | null;
  toVersion: number | null;
  setFromVersion: (value: number | null) => void;
  setToVersion: (value: number | null) => void;
  diffData: { diff_lines: string[]; added_lines: number; removed_lines: number } | undefined;
  loading: boolean;
}) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2">
        <select
          value={fromVersion ?? ''}
          onChange={(e) => setFromVersion(e.target.value ? Number(e.target.value) : null)}
          className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
        >
          {outputs.map((output) => (
            <option key={`from-${output.id}`} value={output.version}>
              من v{output.version}
            </option>
          ))}
        </select>
        <select
          value={toVersion ?? ''}
          onChange={(e) => setToVersion(e.target.value ? Number(e.target.value) : null)}
          className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
        >
          {outputs.map((output) => (
            <option key={`to-${output.id}`} value={output.version}>
              إلى v{output.version}
            </option>
          ))}
        </select>
      </div>

      <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
        <div className="flex items-center justify-between text-sm text-slate-300">
          <span>ملخص الفروقات</span>
          <span>{loading ? 'جارٍ المقارنة...' : `+${diffData?.added_lines || 0} / -${diffData?.removed_lines || 0}`}</span>
        </div>
        <pre className="mt-3 max-h-[420px] overflow-auto whitespace-pre-wrap text-xs text-slate-200">
          {diffData?.diff_lines?.join('\n') || 'اختر نسختين مختلفتين لعرض المقارنة.'}
        </pre>
      </div>
    </div>
  );
}

function DeliveryPanel({
  delivery,
  title,
  thumbnailIdeas,
  onSave,
  onExport,
}: {
  delivery: VideoWorkspaceModel['delivery'];
  title: string;
  thumbnailIdeas: string[];
  onSave: (payload: Record<string, unknown>) => void;
  onExport: () => void;
}) {
  const [form, setForm] = useState({
    title: delivery.title || title,
    thumbnail_line: delivery.thumbnail_line || thumbnailIdeas[0] || '',
    social_copy: delivery.social_copy || '',
    shot_list: (delivery.shot_list || []).join('\n'),
    source_references: (delivery.source_references || []).join('\n'),
    status: delivery.status || 'draft',
  });

  return (
    <div className="space-y-4">
      <Field label="عنوان الحزمة">
        <input
          value={form.title}
          onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
          className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
        />
      </Field>
      <Field label="جملة المصغرة Thumbnail line">
        <input
          value={form.thumbnail_line}
          onChange={(e) => setForm((prev) => ({ ...prev, thumbnail_line: e.target.value }))}
          className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
        />
      </Field>
      <Field label="Social copy">
        <textarea
          value={form.social_copy}
          onChange={(e) => setForm((prev) => ({ ...prev, social_copy: e.target.value }))}
          className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
          rows={4}
        />
      </Field>
      <div className="grid gap-4 md:grid-cols-2">
        <Field label="Shot list">
          <textarea
            value={form.shot_list}
            onChange={(e) => setForm((prev) => ({ ...prev, shot_list: e.target.value }))}
            className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
            rows={6}
          />
        </Field>
        <Field label="Source references">
          <textarea
            value={form.source_references}
            onChange={(e) => setForm((prev) => ({ ...prev, source_references: e.target.value }))}
            className="w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-slate-200"
            rows={6}
          />
        </Field>
      </div>
      <Field label="حالة التسليم">
        <select
          value={form.status}
          onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}
          className="h-11 w-full rounded-xl border border-white/10 bg-black/20 px-3 text-sm text-slate-200"
        >
          <option value="draft">مسودة</option>
          <option value="bundle_ready">الحزمة جاهزة</option>
          <option value="sent">تم الإرسال</option>
        </select>
      </Field>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() =>
            onSave({
              title: form.title,
              thumbnail_line: form.thumbnail_line,
              social_copy: form.social_copy,
              shot_list: splitLines(form.shot_list),
              source_references: splitLines(form.source_references),
              status: form.status,
            })
          }
          className="inline-flex h-10 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 text-sm text-cyan-100"
        >
          احفظ الحزمة
        </button>
        <button
          type="button"
          onClick={onExport}
          className="inline-flex h-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-slate-100"
        >
          صدّر الحزمة
        </button>
      </div>
    </div>
  );
}

function IssueCard({
  issue,
  tone,
}: {
  issue: { code: string; message: string; details?: Record<string, unknown> };
  tone: 'red' | 'amber';
}) {
  return (
    <div
      className={cn(
        'rounded-xl border p-3 text-sm',
        tone === 'red' ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-amber-500/30 bg-amber-500/10 text-amber-100',
      )}
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p>{issue.message}</p>
          {issue.details ? <p className="mt-1 text-xs text-slate-300">{JSON.stringify(issue.details)}</p> : null}
        </div>
      </div>
    </div>
  );
}

function toVideoWorkspace(project: ScriptProjectRecord | undefined, latestOutput: ScriptOutputRecord | undefined) {
  const content = (latestOutput?.content_json || {}) as Record<string, unknown>;
  const scenes = Array.isArray(content.scenes) ? (content.scenes as VideoScriptScene[]) : [];
  const captionsLines = Array.isArray(content.captions_lines) ? (content.captions_lines as VideoCaptionLine[]) : [];
  const delivery = typeof content.delivery === 'object' && content.delivery ? (content.delivery as Record<string, unknown>) : {};

  return {
    video_profile: String(content.video_profile || project?.params_json?.video_profile || project?.video_workspace?.video_profile || 'news_package'),
    target_platform: String(content.target_platform || project?.params_json?.target_platform || project?.video_workspace?.target_platform || 'youtube'),
    editorial_objective: String(
      content.editorial_objective || project?.params_json?.editorial_objective || project?.video_workspace?.editorial_objective || 'inform',
    ),
    total_duration_s: Number(
      content.total_duration_s ||
        project?.video_workspace?.total_duration_s ||
        scenes.reduce((sum, scene) => sum + Number(scene.duration_s || 0), 0),
    ),
    delivery_status: String(content.delivery_status || project?.video_workspace?.delivery_status || 'draft'),
    vo_script: String(content.vo_script || latestOutput?.content_text || ''),
    hook: String(content.hook || ''),
    closing: String(content.closing || ''),
    hook_strength: Number(content.hook_strength || 0),
    pace_notes: String(content.pace_notes || ''),
    scenes,
    captions_lines: captionsLines,
    captions_srt: String(content.captions_srt || ''),
    assets_list: Array.isArray(content.assets_list) ? content.assets_list : [],
    thumbnail_ideas: Array.isArray(content.thumbnail_ideas) ? (content.thumbnail_ideas as string[]) : [],
    delivery: {
      title: String(delivery.title || project?.title || ''),
      thumbnail_line: String(delivery.thumbnail_line || ''),
      social_copy: String(delivery.social_copy || ''),
      shot_list: Array.isArray(delivery.shot_list) ? (delivery.shot_list as string[]) : [],
      source_references: Array.isArray(delivery.source_references) ? (delivery.source_references as string[]) : [],
      status: String(delivery.status || content.delivery_status || 'draft'),
    },
  };
}

function labelForProfile(value: string) {
  return (
    {
      short_vertical: 'قصير عمودي',
      news_package: 'حزمة خبرية',
      explainer: 'فيديو تفسيري',
      breaking_clip: 'عاجل سريع',
      voiceover_package: 'حزمة تعليق صوتي',
      document_explainer: 'شرح وثيقة',
    }[value] || value
  );
}

function labelForPlatform(value: string) {
  return (
    {
      instagram_reels: 'Instagram Reels',
      youtube: 'YouTube',
      youtube_shorts: 'YouTube Shorts',
      facebook: 'Facebook',
      x: 'X',
    }[value] || value
  );
}

function labelForObjective(value: string) {
  return (
    {
      inform: 'إخباري',
      explain: 'تفسيري',
      recap: 'تلخيص',
      engage: 'جذب التفاعل',
      convert: 'دفع للمشاهدة',
    }[value] || value
  );
}

function labelForStatus(value: string) {
  return (
    {
      new: 'جديد',
      generating: 'قيد التوليد',
      failed: 'فشل',
      ready_for_review: 'بانتظار المراجعة',
      approved: 'معتمد',
      rejected: 'مرفوض',
      archived: 'مؤرشف',
    }[value] || value
  );
}

function labelForDeliveryStatus(value: string) {
  return (
    {
      draft: 'مسودة',
      bundle_ready: 'الحزمة جاهزة',
      sent: 'تم الإرسال',
    }[value] || value
  );
}

function labelForSceneType(value?: string | null) {
  return (
    {
      hook: 'افتتاحية',
      body: 'جسم',
      transition: 'انتقال',
      closing: 'خاتمة',
    }[value || 'body'] || value || 'body'
  );
}

function labelForPriority(value?: string | null) {
  return (
    {
      high: 'أولوية عالية',
      medium: 'أولوية متوسطة',
      low: 'أولوية منخفضة',
    }[value || 'medium'] || value || 'medium'
  );
}

function splitLines(value: string) {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}
