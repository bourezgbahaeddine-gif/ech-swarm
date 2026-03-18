import Link from 'next/link';
import { BookOpen, CheckCircle2, FileText, SearchCheck, Sparkles } from 'lucide-react';

type PromptSection = {
  id: string;
  title: string;
  stage: string;
  whenToUse: string;
  whereToUse: string;
  prompt: string;
  tip: string;
};

const sections: PromptSection[] = [
  {
    id: 'scribe',
    title: 'مسودة أولى قابلة للتحرير',
    stage: 'Scribe',
    whenToUse: 'عند بدء المادة لأول مرة أو عندما نريد نقطة انطلاق سريعة من وقائع مؤكدة.',
    whereToUse: 'داخل Scribe ومرحلة الكتابة في Workspace Drafts.',
    prompt: `أنت مساعد تحريري داخل غرفة أخبار.\nأريد مسودة أولية قابلة للتحرير لمادة صحفية اعتمادًا على المعطيات التالية فقط.\n\nالموضوع:\n[اكتب الموضوع]\n\nالوقائع المؤكدة:\n- [حقيقة 1]\n- [حقيقة 2]\n- [حقيقة 3]\n\nزاوية التناول:\n[خبر عاجل / متابعة / تفسير / خلفية / تحديث]\n\nالجمهور المستهدف:\n[عام / رقمي / محلي / سياسي / اقتصادي]\n\nالأسلوب المطلوب:\n[واضح / مهني / مباشر / مختصر / رسمي]\n\nالطول المطلوب:\n[قصير 120-180 كلمة / متوسط 250-400 / طويل]\n\nقيود مهمة:\n- لا تضف أي معلومة غير موجودة في المعطيات\n- لا تخمّن\n- لا تستخدم لغة دعائية\n- إذا كانت هناك فجوة معلوماتية اتركها بصياغة آمنة\n- ابدأ بأقوى معلومة خبرية\n\nالمخرج المطلوب:\n- عنوان مقترح\n- مقدمة\n- متن منظم\n- خاتمة قصيرة أو سطر ختامي`,
    tip: 'اطلب من Scribe مسودة نظيفة قابلة للتحرير، لا نصًا نهائيًا جاهزًا للنشر.',
  },
  {
    id: 'smart-editor-headlines',
    title: 'اقتراح العناوين',
    stage: 'Smart Editor',
    whenToUse: 'بعد وجود مسودة أو ملخص واضح للمادة.',
    whereToUse: 'داخل Smart Editor وأدوات العناوين في Workspace Drafts.',
    prompt: `اقترح 10 عناوين لهذه المادة.\n\nملخص المادة:\n[ألصق الملخص أو المسودة]\n\nنوع العناوين المطلوبة:\n[إخباري مباشر / تحليلي / رقمي / هادئ / قوي]\n\nالقيود:\n- لا تبالغ\n- لا تستخدم عبارات مضللة\n- لا تغيّر الوقائع\n- اجعل العنوان واضحًا ومفهومًا من القراءة الأولى\n- قدّم 3 عناوين قصيرة\n- 3 متوسطة\n- 4 أقوى من ناحية الجذب دون فقدان المهنية`,
    tip: 'اطلب دائمًا تنويعًا في الأطوال والأنماط بدل عنوان واحد فقط.',
  },
  {
    id: 'smart-editor-improve',
    title: 'تحسين لغوي وأسلوبي',
    stage: 'Smart Editor',
    whenToUse: 'بعد اكتمال المسودة وقبل الفحص النهائي.',
    whereToUse: 'وضع حسّن أكثر داخل Workspace Drafts.',
    prompt: `حسّن النص التالي لغويًا وأسلوبيا دون تغيير أي حقيقة.\n\nالمطلوب:\n- تصحيح اللغة\n- تحسين السلاسة\n- إزالة التكرار\n- تقوية الترابط بين الجمل\n- الحفاظ على المعنى والوقائع كما هي\n- عدم إضافة معلومات جديدة\n- عدم حذف أي معلومة أساسية\n\nالنص:\n[ألصق النص]\n\nأعد الناتج في نسختين:\n1) نسخة محافظة جدًا\n2) نسخة أكثر مهنية وسلاسة`,
    tip: 'أوضح دائمًا أن المطلوب تحسين الصياغة لا إعادة كتابة الوقائع.',
  },
  {
    id: 'quality-gates',
    title: 'فحص الجاهزية قبل الاعتماد',
    stage: 'Quality Gates',
    whenToUse: 'بعد الانتهاء من الكتابة وقبل الإرسال للاعتماد التحريري.',
    whereToUse: 'مرحلة المراجعة في Workspace Drafts وقبل Chief Approval.',
    prompt: `قيّم هذه المادة قبل الإرسال للاعتماد التحريري.\n\nافحص فقط:\n- الاتساق\n- الوضوح\n- الادعاءات التي تحتاج تحققًا\n- الثغرات المعلوماتية\n- الجاهزية العامة للنشر\n\nالنص:\n[ألصق النص]\n\nأعطني النتيجة بهذا الشكل:\n1) نقاط القوة\n2) نقاط الضعف\n3) المخاطر التحريرية\n4) ما الذي يجب إصلاحه قبل الاعتماد\n5) حكم نهائي: جاهز / يحتاج مراجعة / يحتاج تحقق إضافي`,
    tip: 'في هذه المرحلة لا نطلب كتابة جديدة، بل كشف المخاطر وما يمنع الاعتماد.',
  },
  {
    id: 'digital-compose',
    title: 'Compose للديجيتال',
    stage: 'Digital Compose',
    whenToUse: 'بعد اكتمال المادة أو اعتمادها تحريريًا.',
    whereToUse: 'داخل Digital Desk وCompose للمحتوى الاجتماعي.',
    prompt: `حوّل هذه المادة إلى منشور رقمي مناسب لـ [فيسبوك / إكس / تيليغرام / إنستغرام].\n\nالمادة:\n[ألصق النص]\n\nالهدف:\n[إخبار / جذب نقرات / شرح / متابعة]\n\nالنبرة:\n[مهنية / سريعة / تفاعلية / هادئة]\n\nالقيود:\n- لا تغيّر الوقائع\n- لا تستخدم clickbait مضلل\n- اجعل الافتتاحية قوية\n- أضف CTA مناسبًا إن لزم\n- حافظ على أسلوب عربي طبيعي وواضح\n\nأعطني:\n- نسخة أساسية\n- نسخة أقصر\n- نسخة أقوى من ناحية الجذب`,
    tip: 'حدد المنصة والهدف والنبرة دائمًا؛ “اكتب بوستًا” وحدها صيغة ضعيفة.',
  },
  {
    id: 'archive-rag',
    title: 'الأرشيف وRAG للخلفية',
    stage: 'Archive + RAG',
    whenToUse: 'عندما نحتاج فقرة خلفية أو سياقًا تاريخيًا داعمًا للمادة الحالية.',
    whereToUse: 'داخل Archive / RAG وWorkspace Drafts عند بناء الخلفية.',
    prompt: `أنشئ مسودة أو فقرة سياقية اعتمادًا على:\n1) الوقائع الحالية\n2) السياق الأرشيفي فقط\n\nالوقائع الحالية:\n[ألصقها]\n\nالسياق الأرشيفي:\n[ألصقه]\n\nالقواعد:\n- ميّز بوضوح بين ما هو جديد وما هو سياق سابق\n- لا تخلط بين المؤكد الحالي والمعلومة التاريخية\n- لا تضف أي معلومة غير موجودة\n- إذا تعارض الحالي مع الأرشيف، قدّم الحالي واذكر أن الأرشيف يوفّر خلفية فقط\n\nالمخرج:\n- فقرة خبرية حالية\n- فقرة خلفية قصيرة`,
    tip: 'الأرشيف سياق، وليس مصدرًا لتأكيد الوقائع الحالية.',
  },
];

export default function PromptPlaybookPage() {
  return (
    <div className="space-y-8" dir="rtl">
      <section className="rounded-[32px] border border-white/10 bg-[radial-gradient(circle_at_top_right,rgba(6,182,212,0.18),transparent_35%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(15,23,42,0.72))] p-8">
        <div className="max-w-5xl space-y-4">
          <p className="text-sm font-medium text-cyan-300">Prompt Playbook</p>
          <h1 className="text-4xl font-bold tracking-tight text-white">دليل البرومبتات داخل سير العمل</h1>
          <p className="text-lg leading-9 text-slate-200">
            هذا الدليل يربط البرومبت بالمرحلة الصحيحة داخل Editorial OS: <span className="font-semibold text-white">Scribe</span> للمسودة الأولى،
            <span className="font-semibold text-white"> Smart Editor</span> للعناوين والتحسين، <span className="font-semibold text-white">Quality Gates</span> للفحص،
            و<span className="font-semibold text-white">Digital Compose</span> للمنشورات والحِزم، مع استخدام <span className="font-semibold text-white">Archive + RAG</span> كسياق لا كبديل عن الوقائع الحالية.
          </p>
          <div className="flex flex-wrap gap-3 text-sm">
            <Link href="/workspace-drafts" className="rounded-xl border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-cyan-100 hover:bg-cyan-500/20">
              افتح المحرر
            </Link>
            <Link href="/digital" className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-slate-100 hover:bg-white/10">
              افتح Digital Compose
            </Link>
            <Link href="/how-editorial-os-works" className="rounded-xl border border-white/10 bg-white/5 px-4 py-2 text-slate-100 hover:bg-white/10">
              راجع كيف تعمل المنصة
            </Link>
          </div>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <QuickRuleCard
          icon={<Sparkles className="h-5 w-5 text-cyan-200" />}
          title="المسودة أولًا"
          description="في البداية نطلب مسودة نظيفة قابلة للتحرير، لا نصًا نهائيًا كاملًا."
        />
        <QuickRuleCard
          icon={<SearchCheck className="h-5 w-5 text-emerald-200" />}
          title="المراجعة لاحقًا"
          description="بعد الكتابة ننتقل إلى برومبتات الفحص والتحسين، لا نخلط كل شيء دفعة واحدة."
        />
        <QuickRuleCard
          icon={<CheckCircle2 className="h-5 w-5 text-amber-200" />}
          title="القرار بشري"
          description="المنصة تساعد في التوليد والتحسين، لكنها لا تنشر تلقائيًا ولا تلغي الاعتماد البشري."
        />
      </section>

      <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
        <h2 className="text-2xl font-semibold text-white">كيف نضمن البرومبت في سير العمل؟</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-5 text-sm">
          <FlowStep title="1. Scribe" description="نبدأ بالمسودة الأولى من الوقائع المؤكدة فقط." />
          <FlowStep title="2. Smart Editor" description="نحسن النص ونقترح العناوين دون تغيير الحقائق." />
          <FlowStep title="3. Quality Gates" description="نفحص الجاهزية والادعاءات والثغرات قبل الاعتماد." />
          <FlowStep title="4. Digital Compose" description="نحوّل المادة إلى منشورات أو حزمة رقمية متعددة النسخ." />
          <FlowStep title="5. Archive + RAG" description="نضيف الخلفية والسياق دون خلطه بالوقائع الحالية." />
        </div>
      </section>

      <section className="space-y-4">
        {sections.map((section) => (
          <article
            key={section.id}
            id={section.id}
            className="rounded-3xl border border-white/10 bg-white/[0.03] p-6 scroll-mt-24"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">
                  <BookOpen className="h-3.5 w-3.5" />
                  {section.stage}
                </div>
                <h2 className="text-2xl font-semibold text-white">{section.title}</h2>
              </div>
            </div>

            <div className="mt-4 grid gap-4 lg:grid-cols-[0.38fr_0.62fr]">
              <div className="space-y-4">
                <InfoCard title="متى أستخدمه؟" description={section.whenToUse} />
                <InfoCard title="أين يستخدم داخل المنصة؟" description={section.whereToUse} />
                <InfoCard title="ملاحظة مهمة" description={section.tip} />
              </div>
              <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
                <div className="mb-3 flex items-center gap-2 text-white">
                  <FileText className="h-4 w-4 text-cyan-300" />
                  <h3 className="text-sm font-semibold">القالب المقترح</h3>
                </div>
                <pre className="overflow-x-auto whitespace-pre-wrap text-sm leading-8 text-slate-200">{section.prompt}</pre>
              </div>
            </div>
          </article>
        ))}
      </section>

      <section className="rounded-3xl border border-emerald-500/20 bg-emerald-500/10 p-6">
        <h2 className="text-xl font-semibold text-white">الصيغة الموحدة لأي برومبت</h2>
        <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-sm leading-8 text-slate-100">{`المهمة:
[اكتب المهمة بدقة]

السياق:
[خبر / مادة / منشور / حزمة / مراجعة]

المدخلات المؤكدة:
- ...
- ...
- ...

المخرجات المطلوبة:
- ...
- ...
- ...

الأسلوب:
[مهني / مباشر / رقمي / مختصر / تحليلي]

الطول:
[قصير / متوسط / طويل]

قيود إلزامية:
- لا تضف معلومات غير موجودة
- لا تغيّر الحقائق
- لا تستخدم لغة دعائية
- اذكر الفجوات إن وجدت
- حافظ على العربية السليمة

معيار النجاح:
[مثلا: مسودة واضحة قابلة للتحرير / 10 عناوين متنوعة / 5 نسخ سوشيال]`}</pre>
      </section>

      <section className="rounded-3xl border border-white/10 bg-white/[0.03] p-6">
        <h2 className="text-xl font-semibold text-white">ما الذي يجب تجنبه؟</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {[
            'اكتب أفضل مقال ممكن',
            'اجعل النص احترافيًا جدًا',
            'حسن النص',
            'اكتب بوستًا قويًا',
            'استخدم الأرشيف',
          ].map((item) => (
            <div key={item} className="rounded-2xl border border-white/10 bg-slate-950/60 p-4 text-sm text-slate-200">
              {item}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-3xl border border-cyan-500/20 bg-cyan-500/10 p-6">
        <h2 className="text-xl font-semibold text-white">الخلاصة</h2>
        <p className="mt-3 text-base leading-8 text-slate-100">
          أفضل استخدام للبرومبت داخل Editorial OS هو أن يصبح <span className="font-semibold text-white">جزءًا من سير العمل</span>:
          مسودة أولى في Scribe، تحسين وعناوين في Smart Editor، فحص قبل الاعتماد في Quality Gates، ثم تحويل منظم إلى Compose رقمي أو سياق أرشيفي عند الحاجة.
        </p>
      </section>
    </div>
  );
}

function QuickRuleCard({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
      <div className="flex items-center gap-2 text-white">
        {icon}
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      <p className="mt-3 text-sm leading-7 text-slate-300">{description}</p>
    </div>
  );
}

function FlowStep({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <p className="mt-2 text-xs leading-6 text-slate-300">{description}</p>
    </div>
  );
}

function InfoCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/60 p-4">
      <h3 className="text-sm font-semibold text-white">{title}</h3>
      <p className="mt-2 text-sm leading-7 text-slate-300">{description}</p>
    </div>
  );
}
