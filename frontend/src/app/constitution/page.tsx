import { FileText, Download } from 'lucide-react';

export default function ConstitutionPage() {
    return (
        <div className="max-w-3xl mx-auto space-y-6">
            <div className="flex items-center gap-3">
                <FileText className="w-6 h-6 text-emerald-400" />
                <h1 className="text-2xl font-bold text-white">الدستور التحريري</h1>
            </div>

            <div className="rounded-2xl border border-white/5 bg-gray-900/40 p-6 space-y-4">
                <p className="text-sm text-gray-300 leading-relaxed">
                    هذا الدستور هو المرجع الإلزامي لجميع مراحل العمل التحريري.
                    الرجاء الرجوع إليه قبل اتخاذ أي قرار تحريري أو نشر.
                </p>

                <a
                    href="/Constitution.docx"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/30 transition-colors"
                    target="_blank"
                    rel="noreferrer"
                >
                    <Download className="w-4 h-4" />
                    تحميل الدستور
                </a>
            </div>
        </div>
    );
}
