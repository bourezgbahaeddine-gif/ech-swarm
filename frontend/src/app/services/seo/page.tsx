'use client';

import Link from 'next/link';
import { TrendingUp, ArrowLeft } from 'lucide-react';

export default function SeoServicesPage() {
    return (
        <div className="max-w-3xl mx-auto space-y-6" dir="rtl">
            <div className="rounded-2xl border border-white/10 bg-gray-900/50 p-6 space-y-4">
                <div className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-emerald-400" />
                    <h1 className="text-xl font-semibold text-white">خدمات SEO أصبحت داخل المحرر الذكي</h1>
                </div>
                <p className="text-sm text-gray-300">
                    لم تعد صفحة SEO مستقلة. جميع أدوات SEO تعمل الآن من داخل المحرر الذكي:
                    عنوان SEO، الوصف التعريفي، الوسوم، الكلمات المفتاحية، وتقييم الجاهزية.
                </p>
                <Link
                    href="/workspace-drafts"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30"
                >
                    <ArrowLeft className="w-4 h-4" />
                    فتح المحرر الذكي
                </Link>
            </div>
        </div>
    );
}
