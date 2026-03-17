import {
    RoleStartCta,
    SharedFooterNote,
    StageCard,
    WorkflowRibbon,
    editorialStages,
} from '@/components/editorial-os/editorial-os-shared';

export default function HowEditorialOsWorksPage() {
    return (
        <div className="space-y-8" dir="rtl">
            <section className="rounded-[32px] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(6,182,212,0.18),transparent_35%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(15,23,42,0.72))] p-8">
                <div className="max-w-4xl space-y-4">
                    <p className="text-sm font-medium text-cyan-300">Editorial OS</p>
                    <h1 className="text-4xl font-bold tracking-tight text-white">كيف تعمل منصة Editorial OS؟</h1>
                    <p className="text-lg leading-9 text-slate-200">
                        منصة تشغيل تحريرية متكاملة تدير دورة الخبر من الالتقاط، إلى التصنيف، إلى كتابة المسودة،
                        إلى التحرير، إلى التحقق والجودة، ثم الاعتماد النهائي قبل الجاهزية للنشر اليدوي.
                    </p>
                    <p className="text-base leading-8 text-slate-300">
                        هي ليست مجرد أداة ذكاء اصطناعي، وليست CMS، ولا تنشر تلقائيًا؛ بل نظام عمل لغرفة الأخبار
                        يربط الإنسان والذكاء والحوكمة في مسار واحد واضح.
                    </p>
                </div>
            </section>

            <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
                <h2 className="text-2xl font-semibold text-white">كيف تعمل المنصة؟</h2>
                <p className="mt-4 text-base leading-8 text-slate-300">
                    في Echorouk Editorial OS، الذكاء الاصطناعي ليس بديلًا عن غرفة التحرير، بل جزءًا من سير عملها.
                    المنصة تبدأ من التقاط الإشارات والمصادر، ثم تنظّمها وتمنحها أولوية، ثم تولّد مسودة أولية، ثم
                    تضعها في مساحة تحرير احترافية مزودة بأدوات جودة وتحقق ومراجعة، قبل أن تصل إلى رئيس التحرير
                    لاتخاذ القرار النهائي.
                </p>
                <p className="mt-4 text-base leading-8 text-slate-300">
                    بمعنى آخر: هذه المنصة لا “تكتب لك مقالًا” فقط، بل تدير دورة المادة التحريرية كاملة مع تتبع،
                    وضبط حالات، وصلاحيات، ومراحل اعتماد واضحة.
                </p>
            </section>

            <WorkflowRibbon />

            <section className="grid grid-cols-1 gap-4 lg:grid-cols-3" dir="rtl">
                <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                    <h3 className="text-lg font-semibold text-white">هذه منصة تشغيل، لا مجرد مساعد كتابة</h3>
                    <p className="mt-3 text-sm leading-7 text-slate-300">
                        تدير الأخبار، الحالات، المسودات، الاعتماد، والمتابعة، وتجمع بين workflow واضح وأدوات ذكاء
                        مساندة.
                    </p>
                </div>
                <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                    <h3 className="text-lg font-semibold text-white">القرار النهائي تحريري بشري</h3>
                    <p className="mt-3 text-sm leading-7 text-slate-300">
                        المنصة تساعد، تقترح، تتحقق، وترفع الجاهزية، لكن الاعتماد النهائي والنشر يبقيان بيد الإنسان.
                    </p>
                </div>
                <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                    <h3 className="text-lg font-semibold text-white">كل مرحلة لها وظيفة واضحة</h3>
                    <p className="mt-3 text-sm leading-7 text-slate-300">
                        الالتقاط ليس هو التحرير، والتحرير ليس هو الاعتماد، والمتابعة بعد النشر ليست هي نفس مرحلة
                        الكتابة.
                    </p>
                </div>
            </section>

            <section className="space-y-4">
                <div>
                    <h2 className="text-2xl font-semibold text-white">لماذا ليست مجرد أداة AI؟</h2>
                    <p className="mt-3 max-w-4xl text-base leading-8 text-slate-300">
                        لأن المنصة لا تركز فقط على كتابة النص، بل على إدارة العمل التحريري بالكامل: التقاط الأخبار
                        والمصادر، تصنيف الأولويات، إنشاء مسودات أولية، تحرير النصوص، التحقق من الجودة، مراجعة رئيس
                        التحرير، وإدارة الحالات التحريرية.
                    </p>
                </div>
                <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                    {editorialStages.map((stage) => (
                        <StageCard key={stage.key} stage={stage} />
                    ))}
                </div>
            </section>

            <RoleStartCta />
            <SharedFooterNote />
        </div>
    );
}
