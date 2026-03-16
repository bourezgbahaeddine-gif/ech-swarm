export const workflowText = {
    reasonLabel: 'لماذا ظهر هنا؟',
    nextActionLabel: 'الإجراء التالي',
    blockersLabel: 'ما الذي يعيق التقدم؟',
    quickGuideTitle: 'دليل سريع',
} as const;

export function getWorkflowStatusLabel(status: string | null | undefined): string {
    const value = (status || '').toLowerCase();
    if (value === 'candidate') return 'مرشح جديد';
    if (value === 'classified') return 'مُصنَّف';
    if (value === 'draft_generated') return 'مسودة جاهزة للتحرير';
    if (value === 'ready_for_chief_approval') return 'بانتظار اعتماد رئيس التحرير';
    if (value === 'approval_request_with_reservations') return 'اعتماد بتحفظات';
    if (value === 'ready_for_manual_publish') return 'جاهز للنشر اليدوي';
    if (value === 'published') return 'منشور';
    if (value === 'rejected') return 'مرفوض';
    return status || 'غير محدد';
}
