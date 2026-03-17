import {
    SharedFooterNote,
    StageCard,
    WorkflowRibbon,
    editorialStages,
} from '@/components/editorial-os/editorial-os-shared';

export default function NewsroomFlowPage() {
    return (
        <div className="space-y-8" dir="rtl">
            <section className="rounded-[32px] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(14,165,233,0.16),transparent_32%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(15,23,42,0.72))] p-8">
                <div className="max-w-4xl space-y-4">
                    <p className="text-sm font-medium text-cyan-300">Newsroom Flow</p>
                    <h1 className="text-4xl font-bold tracking-tight text-white">مسار العمل داخل غرفة الأخبار</h1>
                    <p className="text-lg leading-9 text-slate-200">
                        من لحظة ظهور الإشارة الأولى، إلى لحظة تسليم المادة جاهزة للنشر اليدوي.
                    </p>
                    <p className="text-base leading-8 text-slate-300">
                        هذا المسار يوضح كيف تتحرك المادة داخل المنصة: تدخل أولًا كإشارة أو خبر أولي، ثم تمر بمرحلة
                        تنقية وتصنيف، ثم تتحول إلى مسودة أولية، ثم تدخل إلى المحرر الذكي للمراجعة والتحسين والتحقق،
                        ثم تمر عبر بوابات الجودة، ثم تصل إلى رئيس التحرير لاعتمادها أو إعادتها للمراجعة.
                    </p>
                </div>
            </section>

            <WorkflowRibbon />

            <section className="rounded-3xl border border-cyan-500/20 bg-cyan-500/10 p-6">
                <p className="text-lg font-medium text-white">المنصة لا تختصر غرفة الأخبار، بل تنظّمها.</p>
                <p className="mt-3 text-base leading-8 text-slate-100">
                    هي تجعل الانتقال بين الالتقاط، الكتابة، التحقق، والاعتماد أوضح وأسرع وأكثر قابلية للتتبع.
                </p>
            </section>

            <section className="space-y-5">
                <div>
                    <h2 className="text-2xl font-semibold text-white">مراحل الدورة التحريرية</h2>
                    <p className="mt-3 max-w-4xl text-base leading-8 text-slate-300">
                        الهدف من هذا المسار هو أن يفهم كل مستخدم: أين وصلت المادة الآن؟ من المسؤول عنها؟ وما الخطوة
                        التالية؟
                    </p>
                </div>

                <div className="space-y-4">
                    {editorialStages.map((stage, index) => (
                        <div key={stage.key} className="grid grid-cols-[auto_1fr] gap-4">
                            <div className="flex flex-col items-center">
                                <div className="flex h-10 w-10 items-center justify-center rounded-full border border-cyan-500/30 bg-cyan-500/10 text-sm font-semibold text-cyan-100">
                                    {index + 1}
                                </div>
                                {index < editorialStages.length - 1 && <div className="mt-2 h-full w-px bg-white/10" />}
                            </div>
                            <StageCard stage={stage} compact />
                        </div>
                    ))}

                    <article className="rounded-3xl border border-emerald-500/25 bg-emerald-500/10 p-5">
                        <h3 className="text-lg font-semibold text-white">Ready for Manual Publish</h3>
                        <p className="mt-3 text-sm leading-7 text-slate-200">
                            بعد الاعتماد، تصبح المادة جاهزة للنشر اليدوي. المنصة لا تقوم بالنشر تلقائيًا؛ وظيفتها أن
                            تجهز المادة وفق عملية تحرير واضحة ومنضبطة.
                        </p>
                    </article>
                </div>
            </section>

            <SharedFooterNote />
        </div>
    );
}
