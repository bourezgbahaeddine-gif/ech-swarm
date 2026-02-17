'use client';

import { Sparkles, ArrowLeft } from 'lucide-react';
import Link from 'next/link';

export default function EditorServicesPage() {
    return (
        <div className="max-w-3xl mx-auto space-y-6" dir="rtl">
            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 space-y-4">
                <div className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-emerald-400" />
                    <h1 className="text-xl font-semibold text-white">تم نقل خدمات التحرير إلى المهام السريعة</h1>
                </div>
                <p className="text-sm text-gray-300">
                    خدمات التحرير الجانبية أصبحت ضمن <span className="text-emerald-300">زر «مهام سريعة»</span> في الشريط العلوي
                    لتعمل مباشرة أثناء متابعة الأخبار خارج المحرر الذكي.
                </p>
                <Link
                    href="/news"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30"
                >
                    <ArrowLeft className="w-4 h-4" />
                    العودة إلى الأخبار
                </Link>
            </div>
        </div>
    );
}
