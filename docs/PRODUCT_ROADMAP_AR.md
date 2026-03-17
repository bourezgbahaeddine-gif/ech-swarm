# خارطة التطوير الرسمية — Echorouk Editorial OS

آخر تحديث: 2026-03-17

## 1. الغرض من هذه الوثيقة

هذه الوثيقة هي خارطة التطوير الرسمية للخصائص القادمة في `Echorouk Editorial OS`.
وهي مبنية على:

- `docs/PLATFORM_MASTER_DETAILS_AR.md`
- `docs/PROJECT_PROFILE_AR.md`
- `docs/architecture.md`
- `docs/USER_GUIDE_AR.md`
- أعمال تبسيط UX الأخيرة في `Today`, `News`, `Workspace Drafts`, `Editorial`, `Stories`, و`Digital`

هدفها ليس فقط ترتيب قائمة مهام، بل تحديد:

- ما الذي سنطوره أولًا
- لماذا هذه الأولوية صحيحة
- ما التبعيات بين الوحدات
- ما معايير النجاح
- ما الذي يجب ألا نكسره أثناء التطوير

## 2. الحالة الحالية المختصرة

المنصة اليوم تملك أساسًا قويًا في 3 طبقات:

### 2.1 النواة التحريرية
- التقاط الأخبار
- التصنيف والتوجيه
- توليد المسودة الأولى
- التحرير داخل `Workspace Drafts`
- الاعتماد عبر `Editorial`
- الجاهزية للنشر اليدوي

### 2.2 الأسطح التشغيلية المبسطة
- `Today` كمنسق يومي حسب الدور
- `News` كقاعة أخبار ببطاقات أخف
- `Workspace Drafts` مقسم إلى كتابة ثم مراجعة
- `Editorial` كطوابير اعتماد واضحة
- `Stories` كطبقة متابعة تحريرية
- `Digital` كمنصة Execute / Compose / Planning

### 2.3 طبقات المساندة والقياس
- `Archive`
- `Memory`
- `UX Insights`
- Telemetry خفيفة لقياس surface usage وnext action adoption

المطلوب الآن ليس إضافة خصائص عشوائية، بل استكمال المنصة بوحدات أكثر نضجًا وانضباطًا على نفس الفلسفة.

## 3. المبدأ الحاكم للتطوير القادم

كل تطوير قادم يجب أن يحقق 5 شروط:

1. يدعم مسار المادة داخل الدورة التحريرية
2. يقلل الحمل المعرفي على المستخدم اليومي
3. يحافظ على الحوكمة والاعتماد البشري
4. يفضل `next action` على كثرة القرارات المتاحة
5. يظهر في السياق الصحيح، لا كصفحة مستقلة بلا حاجة

## 4. الأهداف الاستراتيجية للمرحلة القادمة

### الهدف 1: جعل المحرر هو أفضل مساحة عمل يومية للصحفي
بمعنى أن الصحفي يدخل، يكتب، يراجع، يرسل، دون أن يتوه في الأدوات.

### الهدف 2: جعل التغطيات والقصص أكثر التصاقًا بالعمل اليومي
بمعنى أن `Events` و`Stories` لا تكونان فقط مخازن بيانات، بل أدوات تنفيذ ومتابعة فعلية.

### الهدف 3: تحويل `Digital` إلى طبقة تنفيذ رقمية مرتبطة بالمادة والقصة والحدث
بمعنى أن الديجيتال يصبح امتدادًا لسير العمل التحريري، لا مسارًا منفصلًا.

### الهدف 4: استخدام telemetry لاتخاذ قرارات UX مبنية على الاستخدام الحقيقي
بمعنى أن التخفيف القادم لا يعتمد على الانطباع فقط، بل على سلوك المستخدم فعليًا.

## 5. أولويات الوحدات القادمة

الترتيب الموصى به لتطوير الوحدات القادمة هو:

1. `Smart Editor`
2. `Events`
3. `Stories`
4. `Digital`
5. `Archive + Memory + Knowledge surfaces`
6. `UX Insights / product telemetry expansion`

### لماذا هذا الترتيب؟

#### Smart Editor أولًا
لأنه أكثر سطح يومي حساس للصحفي، وأي تحسن فيه ينعكس مباشرة على جودة وسرعة العمل.

#### Events ثانيًا
لأن التغطيات هي الجسر بين التخطيط والتنفيذ، وتحسينها يربط غرفة الأخبار بالزمن الحقيقي.

#### Stories ثالثًا
لأنها طبقة المتابعة التي تمنع ضياع الزخم وتربط المواد المتفرقة داخل قصة واحدة.

#### Digital رابعًا
لأنها تعتمد عمليًا على نضج الخبر/القصة/الحدث، ومن الأفضل بناؤها فوق مسارات أوضح.

## 6. خريطة التطوير على مراحل

## المرحلة 0 — تثبيت الأساس

### الهدف
تثبيت ما تم تبسيطه ومنع التراجع في التجربة.

### النطاق
- مراجعة الترميز العربي عبر الأسطح الأساسية
- تثبيت لغة الحالات والأزرار المشتركة
- تثبيت الروابط الجديدة للوثائق التعريفية
- التأكد من أن `Today` هو نقطة الدخول الفعلية حسب الدور

### المخرجات
- zero mojibake in primary surfaces
- workflow language dictionary معتمد
- صفحات تعريفية مرتبطة بالـ sidebar
- baseline telemetry جاهز

### معايير القبول
- لا تظهر نصوص مكسورة في `Today`, `News`, `Workspace Drafts`, `Editorial`, `Stories`, `Sidebar`
- `surface_view` يعمل فعليًا في الصفحات الأساسية
- الصفحات التعريفية قابلة للوصول من القائمة

## المرحلة 1 — Smart Editor 2.0

### الهدف
تحويل المحرر إلى مساحة كتابة ومراجعة ممتازة للصحفي.

### المشاكل الحالية المستهدفة
- ما يزال هناك إدراك بأن المحرر “يعرض النظام” أكثر مما “يخدم الكتابة”
- المساعدة والخطوة التالية تحتاجان لتكونا أكثر دقة بحسب نوع المادة
- بعض الأدوات المتقدمة ما تزال قريبة جدًا من السطح الأول

### النطاق
#### 1. Writing-first surface
- جعل أول شاشة داخل المحرر هي النص نفسه
- تقليل أي حواجز بصرية فوق النص
- إبقاء شريط علوي صغير جدًا فقط

#### 2. Review stage as explicit second phase
- فحص سريع
- جودة
- تحقق
- readiness
- send for approval

#### 3. Context-aware guidance
- تغيير الدليل حسب نوع المادة:
  - عاجل
  - متابعة
  - تحليل
  - خبر قصير
- تغيير `next action` حسب:
  - الدور
  - حالة المادة
  - اكتمال النص

#### 4. Advanced tools as drawers/modals
- Story mode
- Compare versions
- Copilot
- deeper analysis

#### 5. Editorial readiness model inside editor
- ماذا ينقص المادة؟
- لماذا لا يمكن إرسالها بعد؟
- ما الذي يجب إصلاحه أولًا؟

### المخرجات
- Smart Editor UX spec
- focused writing shell
- stage-based review system
- contextual inline guidance
- advanced tool drawers

### مؤشرات النجاح
- انخفاض عدد النقرات قبل أول كتابة فعلية
- زيادة `next_action_click` داخل `workspace_drafts`
- انخفاض التخلي داخل المحرر
- ارتفاع نسبة الوصول إلى `ready_for_chief_approval`

## المرحلة 2 — Events Desk 2.0

### الهدف
تحويل `Events` من تقويم بيانات إلى مكتب تغطيات فعلي.

### المشاكل الحالية المستهدفة
- الأحداث قد تكون موجودة لكن ليس دائمًا واضحًا من المسؤول عنها وما الخطوة التالية
- الربط بين الحدث والتحضير والتحرير والديجيتال يحتاج تعميقًا

### النطاق
#### 1. Event action model
- assign owner
- open coverage
- create story
- generate digital bundle
- mark prep started

#### 2. Timeline-based readiness
- T-48
- T-24
- T-6
- T-1
- event
- T+1

#### 3. Coverage readiness linked to real execution
- source readiness
- ownership readiness
- planning readiness
- story linkage
- digital coverage linkage

#### 4. Event-to-news / event-to-story / event-to-digital linking
- ربط أوضح داخل الواجهة
- إبراز المواد المرتبطة بالحدث
- إظهار ما هو ناقص

### المخرجات
- Event Desk spec
- event action queue
- prep and coverage board
- deeper event linkage

### مؤشرات النجاح
- انخفاض نسبة الأحداث بلا owner
- انخفاض نسبة الأحداث بلا social coverage
- ارتفاع readiness score قبل وقت الحدث
- وضوح أكبر في action items

## المرحلة 3 — Stories 2.0

### الهدف
تحويل `Stories` إلى طبقة متابعة وتحويل تحريري قوية.

### المشاكل الحالية المستهدفة
- القصص ما تزال تحتاج وضوحًا أكبر في كيفية تحديثها وربطها بالمواد اليومية
- الحاجة إلى قواعد أوضح لتحديد فقدان الزخم أو الحاجة إلى زاوية جديدة

### النطاق
#### 1. Story lifecycle clarity
- active
- needs update
- lost momentum
- needs new angle

#### 2. Story pack / linked material surface
- news linked to story
- events linked to story
- digital tasks linked to story

#### 3. Follow-up recommendations
- ما الجديد منذ آخر تحديث؟
- هل فقدت القصة الزخم؟
- ما زاوية المتابعة المقترحة؟

#### 4. Story ownership and planning
- owner
- cadence
- expected follow-up windows

### المخرجات
- Story Desk spec
- story follow-up engine
- story-linked content panel
- angle suggestion model

### مؤشرات النجاح
- زيادة عدد القصص المحدثة بانتظام
- انخفاض القصص التي تفقد الزخم دون متابعة
- ارتفاع نسبة الأخبار المرتبطة بقصص واضحة

## المرحلة 4 — Digital Desk 3.0

### الهدف
تثبيت `Digital` كطبقة تنفيذية مرتبطة بالمادة والحدث والقصة.

### المشاكل الحالية المستهدفة
- رغم التقدم الكبير، ما تزال هناك فرصة لتعميق الربط مع القصص والأحداث
- يحتاج الفريق إلى explainability أقوى وdelivery أكثر نضجًا

### النطاق
#### 1. Story / event / article driven digital generation
- social task from event
- digital bundle from story
- teaser / recap / breaking / reminder based on context

#### 2. Delivery adapters maturity
- publish now
- schedule
- export bundle
- copy with audit

#### 3. Better recovery and operational resilience
- failed post recovery desk
- duplicate and retry
- publish manually
- mark handled

#### 4. Decision support before approval
- engagement pre-score
- timing fitness
- platform fit
- CTA and hook quality

#### 5. Role-specific digital views
- social operator
- editor chief
- director

### المخرجات
- Digital Product Spec
- delivery adapter plan
- recovery desk improvements
- role-based digital dashboards

### مؤشرات النجاح
- زيادة `approved -> published/scheduled` throughput
- انخفاض failed posts unresolved
- ارتفاع استخدام bundles بدل المنشورات المنفردة عند الحاجة

## المرحلة 5 — Knowledge Surfaces

### الهدف
إعادة تنظيم الأرشيف والذاكرة والأسطح المعرفية بحيث تكون أكثر إفادة داخل السياق التحريري.

### النطاق
- archive inline retrieval
- memory relevance improvements
- document intel within story/editor flows
- media logger within coverage and script contexts

### المخرجات
- Knowledge Surfaces spec
- contextual archive hooks
- memory relevance playbook

## المرحلة 6 — Product Telemetry & Optimization

### الهدف
الانتقال من “تبسيط حسب الانطباع” إلى “تبسيط حسب السلوك الفعلي”.

### النطاق
- telemetry funnel expansion
- drop-off analysis
- first-success tracking
- role-based usage analysis
- feature exposure vs. actual use

### المخرجات
- UX funnel dashboard
- abandonment hotspots report
- monthly UX review cadence

### مؤشرات النجاح
- ارتفاع نسبة بدء الجلسات من `Today`
- ارتفاع نسبة استخدام `next action`
- انخفاض استخدام الأسطح الثقيلة خارج السياق

## 7. خريطة التبعيات

## 7.1 Smart Editor قبل Stories وDigital
لأن المحرر هو المصدر الأساسي للمادة الجاهزة للمراجعة والديجيتال.

## 7.2 Events قبل Digital orchestration الكامل
لأن كثيرًا من مهام الديجيتال تعتمد على النوافذ الزمنية للأحداث.

## 7.3 Stories قبل deep story bundles
لأن الـ bundles الرقمية المرتبطة بالقصة تحتاج نموذج قصة أوضح.

## 7.4 Telemetry عبر كل المراحل
لأن كل مرحلة جديدة يجب أن تقاس لا أن تترك للانطباع.

## 8. خارطة Product Specs المقترحة

بعد هذه الوثيقة، الترتيب المقترح لكتابة وثائق `Product Spec` المستقلة هو:

1. `Smart Editor Product Spec`
2. `Events Product Spec`
3. `Stories Product Spec`
4. `Digital Product Spec`
5. `Knowledge Surfaces Product Spec`
6. `UX Telemetry Product Spec`

## 9. محتوى كل Product Spec لاحقًا

كل وثيقة `Product Spec` يجب أن تحتوي على:

- الغرض من الوحدة
- المستخدمون والأدوار
- المشاكل الحالية
- حالات الاستخدام الأساسية
- UX principles الخاصة بالوحدة
- data model / status model relevant
- API surfaces الحالية
- gaps الحالية
- roadmap داخل الوحدة
- acceptance criteria
- KPIs
- open questions

## 10. ما الذي يجب ألا نفعله أثناء التطوير؟

- لا نعيد تعقيد الواجهة اليومية من جديد
- لا نحول الأدوات المتقدمة إلى surface أولي لكل المستخدمين
- لا نكسر state transitions بلا مراجعة
- لا نضيف نشرًا تلقائيًا نهائيًا خارج الحوكمة
- لا نبني صفحات جديدة إذا كانت الخاصية يجب أن تكون drawer أو panel داخل صفحة قائمة
- لا نضيف نصوص عربية دون فحص ترميز واضح

## 11. معايير النجاح العامة للخارطة

### 11.1 على مستوى UX
- الزمن إلى أول إجراء ناجح
- عدد النقرات قبل إنجاز المهمة
- اعتماد المستخدمين على `Today`
- اعتماد المستخدمين على `Next Action`

### 11.2 على مستوى workflow
- الزمن من `candidate` إلى `draft_generated`
- الزمن من `draft_generated` إلى `ready_for_chief_approval`
- الزمن من الإرسال إلى قرار رئيس التحرير
- انخفاض العودة غير الضرورية للمراجعة

### 11.3 على مستوى adoption
- انخفاض طلبات “أين أذهب؟”
- ارتفاع استخدام المسارات المبسطة
- انخفاض استخدام الأدوات الثقيلة خارج السياق

## 12. التوصية التنفيذية النهائية

إذا أردنا تطوير باقي الخصائص بشكل منضبط، فهذه الوثيقة توصي بالتسلسل التالي:

### أولًا
`Smart Editor Product Spec`

### ثانيًا
`Events Product Spec`

### ثالثًا
`Stories Product Spec`

### رابعًا
`Digital Product Spec`

هذا الترتيب هو الأكثر واقعية لأنه يبدأ من السطح اليومي الأكثر حساسية، ثم يوسع العمل إلى التخطيط والمتابعة والتنفيذ الرقمي.

## 13. الخلاصة

المنصة اليوم تملك أساسًا قويًا.
المطلوب الآن ليس المزيد من “الخصائص المتفرقة”، بل تطوير منضبط يحترم المسار التحريري، ويحافظ على التبسيط، ويزيد الوضوح لكل دور.

هذه الخارطة تجعلنا نطوّر المنصة بوصفها `Operating System for Newsroom Work`, لا بوصفها مجموعة صفحات وأدوات منفصلة.
