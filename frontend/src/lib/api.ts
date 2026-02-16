/**
 * Echorouk AI Swarm — API Client
 * Typed API service layer for backend communication
 */

import axios from 'axios';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '/api/v1';

export const api = axios.create({
    baseURL: API_BASE,
    timeout: 30000,
    headers: { 'Content-Type': 'application/json' },
});

// ── Types ──

export interface Source {
    id: number;
    name: string;
    url: string;
    category: string;
    language: string;
    trust_score: number;
    priority: number;
    enabled: boolean;
    fetch_interval_minutes: number;
    last_fetched_at: string | null;
    error_count: number;
    created_at: string;
}

export interface ArticleBrief {
    id: number;
    title_ar: string | null;
    original_title: string;
    original_url: string | null;
    source_name: string | null;
    category: string | null;
    importance_score: number;
    urgency: string | null;
    is_breaking: boolean;
    status: string;
    crawled_at: string;
    created_at: string;
    summary: string | null;
}

export interface Article extends ArticleBrief {
    unique_hash: string;
    original_url: string;
    original_content: string | null;
    body_html: string | null;
    sentiment: string | null;
    truth_score: number | null;
    entities: string[];
    keywords: string[];
    seo_title: string | null;
    seo_description: string | null;
    reviewed_by: string | null;
    reviewed_at: string | null;
    published_url: string | null;
    processing_time_ms: number | null;
    ai_model_used: string | null;
    trace_id: string | null;
    published_at: string | null;
    created_at: string;
    updated_at: string;
}

export interface DashboardStats {
    total_articles: number;
    articles_today: number;
    pending_review: number;
    approved: number;
    rejected: number;
    published: number;
    breaking_news: number;
    sources_active: number;
    sources_total: number;
    ai_calls_today: number;
    avg_processing_ms: number | null;
}

export interface PipelineRun {
    id: number;
    run_type: string;
    started_at: string;
    finished_at: string | null;
    total_items: number;
    new_items: number;
    duplicates: number;
    errors: number;
    ai_calls: number;
    status: string;
}

export interface TrendAlert {
    keyword: string;
    source_signals: string[];
    strength: number;
    category: string;
    geography: string;
    reason: string | null;
    suggested_angles: string[];
    archive_matches: string[];
    detected_at: string;
}

export interface PaginatedResponse<T> {
    items: T[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

export interface AgentStatus {
    status: string;
    description: string;
}

export interface WorkspaceDraft {
    id: number;
    article_id: number;
    work_id: string;
    source_action: string;
    title: string | null;
    body: string;
    note: string | null;
    status: string;
    version: number;
    created_by: string;
    updated_by: string | null;
    applied_by: string | null;
    applied_at: string | null;
    created_at: string;
    updated_at: string;
}

export interface ArticleInsight {
    article_id: number;
    cluster_size: number;
    relation_count: number;
}

export const newsApi = {
    list: (params?: {
        page?: number; per_page?: number;
        status?: string; category?: string;
        is_breaking?: boolean; search?: string;
        sort_by?: string;
    }) => api.get<PaginatedResponse<ArticleBrief>>('/news/', { params }),

    get: (id: number) => api.get<Article>(`/news/${id}`),
    breaking: (limit?: number) => api.get<ArticleBrief[]>('/news/breaking/latest', { params: { limit } }),
    pending: (limit?: number) => api.get<ArticleBrief[]>('/news/candidates/pending', { params: { limit } }),
    insights: (articleIds: number[]) =>
        api.get<ArticleInsight[]>('/news/insights', { params: { article_ids: articleIds } }),
};

export const sourcesApi = {
    list: (params?: { enabled?: boolean; category?: string }) =>
        api.get<Source[]>('/sources/', { params }),
    create: (data: Partial<Source>) => api.post<Source>('/sources/', data),
    update: (id: number, data: Partial<Source>) => api.put<Source>(`/sources/${id}`, data),
    delete: (id: number) => api.delete(`/sources/${id}`),
    stats: () => api.get('/sources/stats'),
};

export const editorialApi = {
    decide: (articleId: number, data: {
        editor_name: string; decision: string;
        reason?: string; edited_title?: string; edited_body?: string;
    }) => api.post(`/editorial/${articleId}/decide`, data),
    handoff: (articleId: number) => api.post(`/editorial/${articleId}/handoff`),
    process: (articleId: number, data: {
        action: string;
        value?: string;
    }) => api.post(`/editorial/${articleId}/process`, data),
    drafts: (articleId: number) => api.get<WorkspaceDraft[]>(`/editorial/${articleId}/drafts`),
    draft: (articleId: number, draftId: number) => api.get<WorkspaceDraft>(`/editorial/${articleId}/drafts/${draftId}`),
    createDraft: (articleId: number, data: {
        title?: string;
        body: string;
        note?: string;
        source_action?: string;
    }) => api.post(`/editorial/${articleId}/drafts`, data),
    updateDraft: (articleId: number, draftId: number, data: {
        title?: string;
        body: string;
        note?: string;
        version: number;
    }) => api.put(`/editorial/${articleId}/drafts/${draftId}`, data),
    applyDraft: (articleId: number, draftId: number) =>
        api.post(`/editorial/${articleId}/drafts/${draftId}/apply`),
    workspaceDrafts: (params?: { status?: string; limit?: number; article_id?: number; source_action?: string }) =>
        api.get<WorkspaceDraft[]>('/editorial/workspace/drafts', { params }),
    workspaceDraft: (workId: string) =>
        api.get<WorkspaceDraft>(`/editorial/workspace/drafts/${workId}`),
    applyWorkspaceDraft: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/apply`),
    archiveWorkspaceDraft: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/archive`),
    regenerateWorkspaceDraft: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/regenerate`),
    decisions: (articleId: number) => api.get(`/editorial/${articleId}/decisions`),
    generate: (articleId: number) => api.post(`/editorial/${articleId}/generate`),
};

export const dashboardApi = {
    stats: () => api.get<DashboardStats>('/dashboard/stats'),
    pipelineRuns: (limit?: number) =>
        api.get<PipelineRun[]>('/dashboard/pipeline-runs', { params: { limit } }),
    failedJobs: () => api.get('/dashboard/failed-jobs'),
    agentStatus: () => api.get<Record<string, AgentStatus>>('/dashboard/agents/status'),
    triggerScout: () => api.post('/dashboard/agents/scout/run'),
    triggerRouter: () => api.post('/dashboard/agents/router/run'),
    triggerScribe: () => api.post('/dashboard/agents/scribe/run'),
    triggerTrends: (params?: { geo?: string; category?: string; limit?: number; wait?: boolean }) =>
        api.post<{ message: string; alerts?: TrendAlert[] }>('/dashboard/agents/trends/scan', null, { params }),
    latestTrends: (params?: { geo?: string; category?: string }) =>
        api.get<{ alerts: TrendAlert[] }>('/dashboard/agents/trends/latest', { params }),
};

// ── Auth API ──

export interface TeamMember {
    id: number;
    full_name_ar: string;
    username: string;
    role: string;
    departments: string[];
    specialization: string | null;
    is_active: boolean;
    is_online: boolean;
    last_login_at: string | null;
}

export const authApi = {
    login: (username: string, password: string) =>
        api.post<{ access_token: string; token_type: string; user: TeamMember }>('/auth/login', { username, password }),
    me: () => api.get<TeamMember>('/auth/me'),
    logout: () => api.post('/auth/logout'),
    users: () => api.get<TeamMember[]>('/auth/users'),
};

// ── Axios Interceptor: auto-redirect on 401 ──

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401 && typeof window !== 'undefined') {
            localStorage.removeItem('echorouk_token');
            localStorage.removeItem('echorouk_user');
            window.location.href = '/login';
        }
        return Promise.reject(error);
    }
);

