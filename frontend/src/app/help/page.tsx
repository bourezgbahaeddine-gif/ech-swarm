export default function HelpCenterPage() {
    return (
        <div className="space-y-6" dir="rtl">
            <section className="rounded-[28px] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(34,211,238,0.12),transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(15,23,42,0.75))] p-6">
                <p className="text-xs text-cyan-200">مركز المساعدة</p>
                <h1 className="mt-2 text-2xl font-semibold text-white">دليل سريع لإنجاز أول مهمة</h1>
                <p className="mt-2 max-w-2xl text-sm text-slate-300 leading-7">
                    الهدف هنا ليس شرح كل المنصة، بل مساعدتك على إنجاز أول مهمة خلال 5–10 دقائق.
                    ابدأ من المسار الأبسط: افتح مادة، عدّلها، ثم أرسلها للاعتماد.
                </p>
            </section>

            <section className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <h2 className="text-sm font-semibold text-white">كيف أكتب خبرًا؟</h2>
                    <ol className="mt-3 space-y-2 text-xs text-slate-300 list-decimal pr-4">
                        <li>اذهب إلى صفحة Today واختر مادة مناسبة.</li>
                        <li>افتح "التحرير" للدخول إلى المحرر.</li>
                        <li>عدّل العنوان والافتتاحية لتصبح واضحة ومباشرة.</li>
                        <li>شغّل الأدوات السريعة (تدقيق/تحقق/SEO) عند الحاجة.</li>
                        <li>أرسل المادة لاعتماد رئيس التحرير.</li>
                    </ol>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <h2 className="text-sm font-semibold text-white">كيف أراجع مادة؟</h2>
                    <ol className="mt-3 space-y-2 text-xs text-slate-300 list-decimal pr-4">
                        <li>افتح صفحة الاعتماد لترى المواد التي تنتظر قرارك.</li>
                        <li>اقرأ الملخص والتقارير الجانبية بسرعة.</li>
                        <li>افتح المحرر إذا احتجت مراجعة تفصيلية.</li>
                        <li>اتخذ القرار: اعتماد / بتحفظات / إعادة للمراجعة.</li>
                        <li>اكتب سبب القرار عند الحاجة.</li>
                    </ol>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <h2 className="text-sm font-semibold text-white">كيف أتعامل مع عاجل؟</h2>
                    <ol className="mt-3 space-y-2 text-xs text-slate-300 list-decimal pr-4">
                        <li>اختر مادة موسومة "عاجل" من Today أو News.</li>
                        <li>ادخل المحرر واكتب مقدمة قصيرة بالمعلومة الأهم.</li>
                        <li>أضف سطر دعم واحد يوضح السياق.</li>
                        <li>شغّل فحصًا سريعًا فقط لتجنب التأخير.</li>
                        <li>أرسل للاعتماد مع ملاحظة "عاجل".</li>
                    </ol>
                </div>
                <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
                    <h2 className="text-sm font-semibold text-white">ماذا أفعل إذا رجعت المادة؟</h2>
                    <ol className="mt-3 space-y-2 text-xs text-slate-300 list-decimal pr-4">
                        <li>افتح المسودة التي عادت إليك من الاعتماد.</li>
                        <li>راجع سبب الإرجاع أو الملاحظات الظاهرة.</li>
                        <li>صحّح النص أو أضف المصادر المطلوبة.</li>
                        <li>أعد تشغيل الأدوات المطلوبة (تدقيق/تحقق/SEO).</li>
                        <li>أعد إرسال المادة للاعتماد.</li>
                    </ol>
                </div>
            </section>

            <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <h2 className="text-sm font-semibold text-white">مبادئ سريعة تختصر الوقت</h2>
                <ul className="mt-3 space-y-2 text-xs text-slate-300 list-disc pr-4">
                    <li>ابدأ دائمًا من Today إذا كنت صحفيًا.</li>
                    <li>افتح التحرير فقط عندما تكون لديك مادة واضحة للعمل.</li>
                    <li>شغّل الأدوات السريعة عند الحاجة فقط لتقليل التأخير.</li>
                    <li>الاعتماد النهائي لا ينشر تلقائيًا، بل يجهّز للنشر اليدوي.</li>
                </ul>
            </section>

            <section className="rounded-2xl border border-white/10 bg-white/5 p-4">
                <h2 className="text-sm font-semibold text-white">روابط سريعة</h2>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <a className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-slate-200" href="/today">Today</a>
                    <a className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-slate-200" href="/news">الأخبار</a>
                    <a className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-slate-200" href="/workspace-drafts">المسودات</a>
                    <a className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-slate-200" href="/editorial">الاعتماد</a>
                    <a className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-slate-200" href="/news?status=ready_for_manual_publish">جاهز للنشر</a>
                </div>
            </section>
        </div>
    );
}
