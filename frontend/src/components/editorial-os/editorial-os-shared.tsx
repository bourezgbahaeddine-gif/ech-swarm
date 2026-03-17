import Link from 'next/link';
import type { ComponentType } from 'react';
import {
    ArrowLeft,
    CheckCircle2,
    FileCheck2,
    FilePenLine,
    GitBranch,
    Radar,
    Route,
    ShieldCheck,
    Sparkles,
    UserCheck,
} from 'lucide-react';

import { cn } from '@/lib/utils';

export type EditorialStage = {
    key: string;
    title: string;
    description: string;
    shortLine: string;
    icon: ComponentType<{ className?: string }>;
    accent: string;
};

export const editorialStages: EditorialStage[] = [
    {
        key: 'scout',
        title: 'Scout — التقاط الإشارات وبداية الدورة التحريرية',
        description:
            'Scout هو نقطة الدخول الأولى في المنصة. يلتقط الأخبار والإشارات من المصادر، ثم ينظّفها ويزيل التكرار ويستبعد العناصر غير المناسبة قبل أن تدخل إلى المسار التحريري.',
        shortLine: 'يلتقط، ينظّف، ويزيل التكرار قبل أن تبدأ المعالجة التحريرية.',
        icon: Radar,
        accent: 'border-cyan-500/25 bg-cyan-500/10 text-cyan-100',
    },
    {
        key: 'router',
        title: 'Router — التصنيف والتوجيه وتحديد الأولوية',
        description:
            'بعد الالتقاط، يأتي دور Router في فهم طبيعة المادة: ما موضوعها؟ ما أولويتها؟ هل هي مرشحة للتحرير الآن؟ وإلى أي مسار أو دور يجب أن تذهب؟',
        shortLine: 'يصنّف، يوجّه، ويرتب الأولويات قبل بدء الكتابة.',
        icon: Route,
        accent: 'border-violet-500/25 bg-violet-500/10 text-violet-100',
    },
    {
        key: 'scribe',
        title: 'Scribe — توليد المسودة الأولى القابلة للتحرير',
        description:
            'Scribe يحول المادة المصنفة إلى مسودة أولية يمكن للصحفي البناء عليها. لا يقرر النشر، ولا يغني عن الصحفي، بل يسرّع نقطة البداية عبر تجهيز نص أولي مع دعم سياقي عند الحاجة.',
        shortLine: 'ينتج مسودة أولية تمهّد للتحرير المهني، لا للنشر المباشر.',
        icon: Sparkles,
        accent: 'border-emerald-500/25 bg-emerald-500/10 text-emerald-100',
    },
    {
        key: 'smart-editor',
        title: 'Smart Editor — مساحة التحرير الفعلية داخل المنصة',
        description:
            'هنا تتحول المسودة إلى مادة تحريرية جاهزة للمراجعة. يعمل الصحفي على النص، والتدقيق، والعناوين، والجودة، ضمن واجهة تركّز على القرار أولًا ثم التفاصيل.',
        shortLine: 'ليس مولّد نصوص، بل مساحة تحرير احترافية مدعومة بالذكاء والحوكمة.',
        icon: FilePenLine,
        accent: 'border-sky-500/25 bg-sky-500/10 text-sky-100',
    },
    {
        key: 'quality-gates',
        title: 'Quality Gates — بوابات الجودة والتحقق قبل الإرسال',
        description:
            'قبل أن تنتقل المادة إلى الاعتماد، تمر عبر فحوصات الجودة، والتحقق من الادعاءات، وقياس الجاهزية للنشر. هذه المرحلة تمنع انتقال مادة ناقصة أو ملتبسة إلى الاعتماد النهائي.',
        shortLine: 'الجودة هنا ليست تحسينًا تجميليًا، بل بوابة قرار قبل الاعتماد.',
        icon: ShieldCheck,
        accent: 'border-amber-500/25 bg-amber-500/10 text-amber-100',
    },
    {
        key: 'chief-approval',
        title: 'Chief Approval — القرار التحريري النهائي',
        description:
            'بعد اكتمال التحرير والتحقق، تصل المادة إلى رئيس التحرير كطلب اعتماد واضح: إما أن تُعتمد، أو تُعاد للمراجعة، أو تُرسل بتحفظات. القرار النهائي يبقى بيد الإنسان.',
        shortLine: 'المنصة تجهّز القرار، لكن الإنسان هو من يتخذه.',
        icon: UserCheck,
        accent: 'border-rose-500/25 bg-rose-500/10 text-rose-100',
    },
];

export const workflowSteps = [
    'Scout',
    'Router',
    'Scribe',
    'Smart Editor',
    'Quality Gates',
    'Chief Approval',
    'Ready for Manual Publish',
];

export function WorkflowRibbon() {
    return (
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4" dir="rtl">
            <div className="mb-2 text-xs text-slate-400">المسار الأساسي داخل المنصة</div>
            <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-white">
                {workflowSteps.map((step, index) => (
                    <div key={step} className="flex items-center gap-2">
                        <span className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2">{step}</span>
                        {index < workflowSteps.length - 1 && <GitBranch className="h-4 w-4 text-cyan-300" />}
                    </div>
                ))}
            </div>
        </div>
    );
}

export function StageCard({ stage, compact = false }: { stage: EditorialStage; compact?: boolean }) {
    const Icon = stage.icon;
    return (
        <article
            className={cn(
                'rounded-3xl border p-5',
                compact ? 'space-y-3' : 'space-y-4',
                stage.accent,
            )}
            dir="rtl"
        >
            <div className="flex items-start gap-3">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
                    <Icon className="h-5 w-5" />
                </div>
                <div className="space-y-2">
                    <h3 className={cn('font-semibold text-white', compact ? 'text-base' : 'text-lg')}>{stage.title}</h3>
                    <p className="text-sm leading-7 text-slate-200">{stage.description}</p>
                </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/15 px-4 py-3 text-sm text-slate-100">
                {stage.shortLine}
            </div>
        </article>
    );
}

export function SharedFooterNote() {
    return (
        <section className="rounded-3xl border border-cyan-500/20 bg-cyan-500/10 p-6" dir="rtl">
            <h2 className="text-xl font-semibold text-white">الخلاصة</h2>
            <p className="mt-3 text-base leading-8 text-slate-100">
                Editorial OS ليس أداة AI مستقلة، بل نظام عمل لغرفة الأخبار. هو يجمع بين الالتقاط، التصنيف،
                التوليد الأولي، التحرير، التحقق، الاعتماد، والجاهزية للنشر اليدوي داخل مسار واحد متكامل.
                لهذا السبب، حين تدخل المنصة، فأنت لا تدخل إلى “محرر نصوص ذكي”، بل إلى بنية تشغيل تحريرية كاملة
                تنظّم كيف تتحرك المادة، ومن يراجعها، ومتى تصبح جاهزة للنشر.
            </p>
        </section>
    );
}

export function RoleStartCta() {
    return (
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-2" dir="rtl">
            <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                <div className="flex items-center gap-2 text-white">
                    <CheckCircle2 className="h-5 w-5 text-emerald-300" />
                    <h3 className="text-lg font-semibold">إذا كنت صحفيًا</h3>
                </div>
                <p className="mt-3 text-sm leading-7 text-slate-300">
                    ابدأ من صفحة <span className="font-semibold text-white">Today</span> لمتابعة المواد التي تحتاج عملك الآن.
                </p>
                <Link
                    href="/today"
                    className="mt-4 inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-100 hover:bg-emerald-500/20"
                >
                    افتح Today
                    <ArrowLeft className="h-4 w-4" />
                </Link>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                <div className="flex items-center gap-2 text-white">
                    <FileCheck2 className="h-5 w-5 text-cyan-300" />
                    <h3 className="text-lg font-semibold">إذا كنت رئيس تحرير</h3>
                </div>
                <p className="mt-3 text-sm leading-7 text-slate-300">
                    ابدأ من صفحة <span className="font-semibold text-white">Approval Queue</span> لمراجعة المواد الجاهزة للاعتماد.
                </p>
                <Link
                    href="/editorial"
                    className="mt-4 inline-flex items-center gap-2 rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-100 hover:bg-cyan-500/20"
                >
                    افتح الاعتماد
                    <ArrowLeft className="h-4 w-4" />
                </Link>
            </div>
        </section>
    );
}
