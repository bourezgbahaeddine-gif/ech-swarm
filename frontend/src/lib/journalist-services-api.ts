import { api } from '@/lib/api';

export const journalistServicesApi = {
    tonality: (text: string) => api.post('/services/editor/tonality', { text }),
    inverted: (text: string) => api.post('/services/editor/inverted-pyramid', { text }),
    proofread: (text: string) => api.post('/services/editor/proofread', { text }),
    social: (text: string, platform: string) => api.post('/services/editor/social-summary', { text, platform }),

    vision: (image_url: string, question: string) => api.post('/services/factcheck/vision', { image_url, question }),
    consistency: (text: string, reference: string) => api.post('/services/factcheck/consistency', { text, reference }),
    extract: (text: string) => api.post('/services/factcheck/extract', { text }),

    keywords: (text: string) => api.post('/services/seo/keywords', { text }),
    internalLinks: (text: string, archive_titles: string[]) => api.post('/services/seo/internal-links', { text, archive_titles }),
    metadata: (text: string) => api.post('/services/seo/metadata', { text }),

    videoScript: (text: string) => api.post('/services/multimedia/video-script', { text }),
    sentiment: (text: string) => api.post('/services/multimedia/sentiment', { text }),
    translate: (text: string, source_lang: string) => api.post('/services/multimedia/translate', { text, source_lang }),
    imagePrompt: (text: string, style: string, article_id?: number, created_by?: string) =>
        api.post('/services/multimedia/image-prompt', { text, style, article_id, created_by }),
    infographicAnalyze: (text: string, article_id?: number, created_by?: string) =>
        api.post('/services/multimedia/infographic/analyze', { text, article_id, created_by }),
    infographicPrompt: (data: any, article_id?: number, created_by?: string) =>
        api.post('/services/multimedia/infographic/prompt', { data, article_id, created_by }),
    infographicRender: (prompt: string) => api.post('/services/multimedia/infographic/render', { prompt }),
};
