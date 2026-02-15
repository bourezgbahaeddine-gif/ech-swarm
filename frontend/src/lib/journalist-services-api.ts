import { api } from '@/lib/api';

export const journalistServicesApi = {
    tonality: (text: string, language = 'ar') => api.post('/services/editor/tonality', { text, language }),
    inverted: (text: string, language = 'ar') => api.post('/services/editor/inverted-pyramid', { text, language }),
    proofread: (text: string, language = 'ar') => api.post('/services/editor/proofread', { text, language }),
    social: (text: string, platform: string, language = 'ar') => api.post('/services/editor/social-summary', { text, platform, language }),

    vision: (image_url: string, question: string) => api.post('/services/factcheck/vision', { image_url, question }),
    consistency: (text: string, reference: string) => api.post('/services/factcheck/consistency', { text, reference }),
    extract: (text: string) => api.post('/services/factcheck/extract', { text }),

    keywords: (text: string, language = 'ar') => api.post('/services/seo/keywords', { text, language }),
    internalLinks: (text: string, archive_titles: string[], language = 'ar') => api.post('/services/seo/internal-links', { text, archive_titles, language }),
    metadata: (text: string, language = 'ar') => api.post('/services/seo/metadata', { text, language }),

    videoScript: (text: string) => api.post('/services/multimedia/video-script', { text }),
    sentiment: (text: string) => api.post('/services/multimedia/sentiment', { text }),
    translate: (text: string, source_lang: string) => api.post('/services/multimedia/translate', { text, source_lang }),
    imagePrompt: (text: string, style: string, article_id?: number, created_by?: string, language = 'ar') =>
        api.post('/services/multimedia/image-prompt', { text, style, article_id, created_by, language }),
    infographicAnalyze: (text: string, article_id?: number, created_by?: string, language = 'ar') =>
        api.post('/services/multimedia/infographic/analyze', { text, article_id, created_by, language }),
    infographicPrompt: (data: unknown, article_id?: number, created_by?: string, language = 'ar') =>
        api.post('/services/multimedia/infographic/prompt', { data, article_id, created_by, language }),
    infographicRender: (prompt: string) => api.post('/services/multimedia/infographic/render', { prompt }),
};
