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

export interface DashboardNotification {
    id: string;
    type: 'breaking' | 'candidate' | 'trend' | 'published_quality' | string;
    title: string;
    message: string;
    article_id?: number;
    created_at: string;
    severity: 'high' | 'medium' | 'low' | string;
}

export interface PublishedMonitorItem {
    title: string;
    url: string;
    published_at: string;
    score: number;
    grade: string;
    issues: string[];
    suggestions: string[];
    metrics: {
        title_length: number;
        word_count: number;
        clickbait_hits: number;
        spelling_hits: number;
        strong_keywords_hits: number;
    };
}

export interface PublishedMonitorReport {
    feed_url: string;
    executed_at: string;
    interval_minutes: number;
    total_items: number;
    average_score: number;
    weak_items_count: number;
    issues_count: number;
    status: 'ok' | 'alert' | 'empty' | string;
    items: PublishedMonitorItem[];
}

export interface WorkspaceDraft {
    id: number;
    article_id: number;
    work_id: string;
    source_action: string;
    parent_draft_id?: number | null;
    change_origin?: string;
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
    cluster_id?: number | null;
    relation_count: number;
}

export interface DraftVersionDiff {
    work_id: string;
    from_version: number;
    to_version: number;
    diff: string;
    stats: { added: number; removed: number };
}

export interface SmartEditorContext {
    work_id: string;
    draft: WorkspaceDraft;
    article: {
        id: number;
        title_ar: string | null;
        original_title: string;
        summary: string | null;
        original_url: string;
        original_content: string | null;
        category: string | null;
        urgency: string | null;
        importance_score: number;
        source_name: string | null;
        status: string;
        router_rationale: string;
    };
    story_context: {
        cluster: {
            cluster_id: number;
            cluster_key: string;
            label: string | null;
            category: string | null;
            geography: string | null;
        } | null;
        timeline: Array<{
            id: number;
            title: string;
            url: string | null;
            source_name: string | null;
            created_at: string;
        }>;
        relations: Array<{
            id: number;
            title: string;
            url: string | null;
            source_name: string | null;
            created_at: string;
            relation_type: string;
            score: number;
        }>;
    };
}

export type LinkSuggestionMode = 'internal' | 'external' | 'mixed';

export interface LinkSuggestionItem {
    id: number;
    link_type: 'internal' | 'external' | string;
    url: string;
    title: string;
    anchor_text: string;
    placement_hint: string | null;
    reason: string | null;
    score: number;
    confidence: number;
    rel_attrs: string | null;
    status: string;
    metadata: Record<string, unknown>;
}

export interface LinkSuggestionRun {
    run_id: string;
    mode: LinkSuggestionMode | string;
    work_id: string;
    source_counts: Record<string, unknown>;
    items: LinkSuggestionItem[];
}

export interface ChiefPendingItem {
    id: number;
    title_ar: string | null;
    original_title: string;
    summary: string | null;
    source_name: string | null;
    importance_score: number;
    is_breaking: boolean;
    category: string | null;
    status: string | null;
    updated_at: string;
    work_id: string | null;
    policy: {
        passed: boolean;
        score: number | null;
        decision: string | null;
        reasons: string[];
        required_fixes: string[];
        created_at: string | null;
    };
}

export interface SocialApprovedItem {
    article_id: number;
    title: string;
    status: string | null;
    source_name: string | null;
    updated_at: string;
    variants: {
        facebook?: string;
        x?: string;
        push?: string;
        summary_120?: string;
        breaking_alert?: string;
    };
}

export const newsApi = {
    list: (params?: {
        page?: number; per_page?: number;
        status?: string; category?: string;
        is_breaking?: boolean; search?: string;
        sort_by?: string;
        local_first?: boolean;
    }) => api.get<PaginatedResponse<ArticleBrief>>('/news/', { params }),

    get: (id: number) => api.get<Article>(`/news/${id}`),
    breaking: (limit?: number) => api.get<ArticleBrief[]>('/news/breaking/latest', { params: { limit } }),
    pending: (limit?: number) => api.get<ArticleBrief[]>('/news/candidates/pending', { params: { limit } }),
    insights: (articleIds: number[]) => {
        const params = new URLSearchParams();
        articleIds.forEach((id) => params.append('article_ids', String(id)));
        return api.get<ArticleInsight[]>(`/news/insights?${params.toString()}`);
    },
    semanticSearch: (params: {
        q: string;
        limit?: number;
        mode?: 'editorial' | 'semantic';
        include_aggregators?: boolean;
        strict_tokens?: boolean;
        status?: string;
    }) => api.get<ArticleBrief[]>('/news/search/semantic', { params }),
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
    createManualWorkspaceDraft: (data: {
        title: string;
        body: string;
        summary?: string;
        category?: string;
        urgency?: string;
        source_action?: string;
    }) => api.post('/editorial/workspace/manual-drafts', data),
    workspaceDraft: (workId: string) =>
        api.get<WorkspaceDraft>(`/editorial/workspace/drafts/${workId}`),
    applyWorkspaceDraft: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/apply`),
    submitWorkspaceDraftForChief: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/submit-for-chief-approval`),
    archiveWorkspaceDraft: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/archive`),
    regenerateWorkspaceDraft: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/regenerate`),
    smartContext: (workId: string) =>
        api.get<SmartEditorContext>(`/editorial/workspace/drafts/${workId}/context`),
    draftVersions: (workId: string) =>
        api.get<WorkspaceDraft[]>(`/editorial/workspace/drafts/${workId}/versions`),
    draftDiff: (workId: string, fromVersion: number, toVersion: number) =>
        api.get<DraftVersionDiff>(`/editorial/workspace/drafts/${workId}/diff`, {
            params: { from_version: fromVersion, to_version: toVersion },
        }),
    autosaveWorkspaceDraft: (workId: string, data: {
        title?: string | null;
        body: string;
        note?: string;
        based_on_version: number;
    }) => api.post(`/editorial/workspace/drafts/${workId}/autosave`, data),
    restoreWorkspaceDraftVersion: (workId: string, version: number) =>
        api.post(`/editorial/workspace/drafts/${workId}/restore/${version}`),
    aiRewriteSuggestion: (workId: string, data: { mode: 'formal' | 'breaking' | 'analysis' | 'simple'; instruction?: string }) =>
        api.post(`/editorial/workspace/drafts/${workId}/ai/rewrite`, data),
    aiHeadlineSuggestion: (workId: string, count = 5) =>
        api.post(`/editorial/workspace/drafts/${workId}/ai/headlines`, { count }),
    aiSeoSuggestion: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/ai/seo`),
    aiLinkSuggestions: (workId: string, data: { mode?: LinkSuggestionMode; target_count?: number }) =>
        api.post<LinkSuggestionRun>(`/editorial/workspace/drafts/${workId}/ai/links/suggest`, data),
    validateLinkSuggestions: (workId: string, runId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/ai/links/validate`, { run_id: runId }),
    applyLinkSuggestions: (workId: string, data: { run_id: string; based_on_version: number; item_ids?: number[] }) =>
        api.post(`/editorial/workspace/drafts/${workId}/ai/links/apply`, data),
    linkSuggestionsHistory: (workId: string, limit = 10) =>
        api.get<{ work_id: string; items: Array<{ run_id: string; mode: string; status: string; created_at: string; source_counts: Record<string, unknown>; items: LinkSuggestionItem[] }> }>(
            `/editorial/workspace/drafts/${workId}/ai/links/history`,
            { params: { limit } },
        ),
    aiSocialVariants: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/ai/social`),
    applyAiSuggestion: (workId: string, data: {
        title?: string | null;
        body: string;
        note?: string;
        based_on_version: number;
        suggestion_tool?: string;
    }) => api.post(`/editorial/workspace/drafts/${workId}/ai/apply`, data),
    verifyClaims: (workId: string, threshold = 0.7) =>
        api.post(`/editorial/workspace/drafts/${workId}/verify/claims`, { threshold }),
    qualityScore: (workId: string) =>
        api.post(`/editorial/workspace/drafts/${workId}/quality/score`),
    publishReadiness: (workId: string) =>
        api.get(`/editorial/workspace/drafts/${workId}/publish-readiness`),
    chiefPending: (limit = 100) =>
        api.get<ChiefPendingItem[]>(`/editorial/chief/pending`, { params: { limit } }),
    chiefFinalDecision: (articleId: number, data: { decision: 'approve' | 'return_for_revision'; notes?: string }) =>
        api.post(`/editorial/${articleId}/chief/final-decision`, data),
    socialApprovedFeed: (limit = 50) =>
        api.get<SocialApprovedItem[]>(`/editorial/social/approved-feed`, { params: { limit } }),
    socialVariantsForArticle: (articleId: number) =>
        api.get(`/editorial/${articleId}/social/variants`),
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
    triggerPublishedMonitor: (params?: { feed_url?: string; limit?: number; wait?: boolean }) =>
        api.post<{ message: string; report?: PublishedMonitorReport }>('/dashboard/agents/published-monitor/run', null, { params }),
    latestPublishedMonitor: (params?: { refresh_if_empty?: boolean; limit?: number }) =>
        api.get<PublishedMonitorReport>('/dashboard/agents/published-monitor/latest', { params }),
    notifications: (params?: { limit?: number }) =>
        api.get<{ items: DashboardNotification[]; total: number }>('/dashboard/notifications', { params }),
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
    created_at?: string;
    updated_at?: string;
}

export interface UserActivityLogItem {
    id: number;
    actor_user_id: number | null;
    actor_username: string | null;
    target_user_id: number | null;
    target_username: string | null;
    action: string;
    details: string | null;
    created_at: string | null;
}

export interface ProjectMemoryItem {
    id: number;
    memory_type: 'operational' | 'knowledge' | 'session' | string;
    title: string;
    content: string;
    tags: string[];
    source_type: string | null;
    source_ref: string | null;
    article_id: number | null;
    status: 'active' | 'archived' | string;
    importance: number;
    created_by_user_id: number | null;
    created_by_username: string | null;
    updated_by_user_id: number | null;
    updated_by_username: string | null;
    created_at: string;
    updated_at: string;
}

export interface ProjectMemoryEvent {
    id: number;
    memory_id: number;
    event_type: string;
    note: string | null;
    actor_user_id: number | null;
    actor_username: string | null;
    created_at: string;
}

export interface ProjectMemoryOverview {
    total_active: number;
    operational_count: number;
    knowledge_count: number;
    session_count: number;
    archived_count: number;
    recent_updates: number;
}

export interface ProjectMemoryListResponse {
    items: ProjectMemoryItem[];
    total: number;
    page: number;
    per_page: number;
    pages: number;
}

export interface MsiProfileInfo {
    id: string;
    display_name: string;
    description?: string | null;
}

export interface MsiRunResponse {
    run_id: string;
    status: string;
    profile_id: string;
    entity: string;
    mode: 'daily' | 'weekly' | string;
    start: string;
    end: string;
}

export interface MsiRunStatusResponse {
    run_id: string;
    status: string;
    error?: string | null;
    created_at: string;
    finished_at?: string | null;
}

export interface MsiReport {
    run_id: string;
    profile_id: string;
    entity: string;
    mode: string;
    period_start: string;
    period_end: string;
    msi: number;
    level: 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED' | string;
    drivers: Array<{ name: string; value: number }>;
    top_negative_items: Array<{ title: string; url: string; source?: string; tone?: number; intensity?: number; score?: number }>;
    topic_shift: { current: Record<string, number>; baseline: Record<string, number> };
    explanation: string;
    components: Record<string, number>;
    confidence?: { score: number; level: 'HIGH' | 'MEDIUM' | 'LOW' | string };
    data_quality?: { total_items: number; unique_sources: number; llm_failure_ratio: number };
}

export interface MsiTimeseriesPoint {
    ts: string;
    msi: number;
    level: string;
    components: Record<string, number>;
}

export interface MsiTimeseriesResponse {
    profile_id: string;
    entity: string;
    mode: string;
    points: MsiTimeseriesPoint[];
}

export interface MsiTopEntityItem {
    profile_id: string;
    entity: string;
    mode: string;
    msi: number;
    level: string;
    period_end: string;
}

export interface MsiWatchlistItem {
    id: number;
    profile_id: string;
    entity: string;
    enabled: boolean;
    run_daily: boolean;
    run_weekly: boolean;
    aliases: string[];
    created_by_username?: string | null;
    created_at: string;
    updated_at: string;
}

export interface SimRunResponse {
    run_id: string;
    status: string;
    platform: 'facebook' | 'x' | string;
    mode: 'fast' | 'deep' | string;
    headline: string;
}

export interface SimRunStatusResponse {
    run_id: string;
    status: string;
    error?: string | null;
    created_at: string;
    finished_at?: string | null;
}

export interface SimResult {
    run_id: string;
    status: string;
    headline: string;
    platform: string;
    mode: string;
    risk_score: number;
    virality_score: number;
    confidence_score: number;
    breakdown: {
        risk: Record<string, number>;
        virality: Record<string, number>;
    };
    reactions: Array<{
        persona_id: string;
        persona_label?: string;
        comment: string;
        sentiment: string;
        risk_signal: number;
        virality_signal: number;
    }>;
    advice: {
        summary?: string;
        improvements?: string[];
        alternative_headlines?: string[];
    };
    red_flags: Record<string, number>;
    policy_level: 'LOW_RISK' | 'REVIEW_RECOMMENDED' | 'HIGH_RISK' | string;
    created_at: string;
}

export interface SimHistoryItem {
    run_id: string;
    status: string;
    headline: string;
    platform: string;
    mode: string;
    created_at?: string | null;
    risk_score?: number | null;
    virality_score?: number | null;
    policy_level?: string | null;
}

export interface MediaLoggerRunResponse {
    run_id: string;
    status: string;
    source_type: 'url' | 'upload' | string;
    source_label?: string | null;
    language_hint: string;
    created_at: string;
}

export interface MediaLoggerRunStatusResponse {
    run_id: string;
    status: string;
    transcript_language?: string | null;
    segments_count: number;
    highlights_count: number;
    duration_seconds?: number | null;
    error?: string | null;
    created_at: string;
    finished_at?: string | null;
}

export interface MediaLoggerRecentRun {
    run_id: string;
    status: string;
    source_type: string;
    source_label?: string | null;
    language_hint: string;
    segments_count: number;
    highlights_count: number;
    created_at: string;
    finished_at?: string | null;
}

export interface MediaLoggerSegment {
    segment_index: number;
    start_sec: number;
    end_sec: number;
    text: string;
    confidence?: number | null;
    speaker?: string | null;
}

export interface MediaLoggerHighlight {
    rank: number;
    quote: string;
    reason?: string | null;
    start_sec: number;
    end_sec: number;
    confidence?: number | null;
}

export interface MediaLoggerResult {
    run_id: string;
    status: string;
    source_type: string;
    source_label?: string | null;
    language_hint: string;
    transcript_language?: string | null;
    transcript_text: string;
    duration_seconds?: number | null;
    segments_count: number;
    highlights_count: number;
    highlights: MediaLoggerHighlight[];
    segments: MediaLoggerSegment[];
    created_at: string;
    finished_at?: string | null;
}

export interface MediaLoggerAskResponse {
    run_id: string;
    answer: string;
    quote: string;
    start_sec: number;
    end_sec: number;
    confidence: number;
    context: MediaLoggerSegment[];
}

export interface CompetitorXraySource {
    id: number;
    name: string;
    feed_url: string;
    domain: string;
    language: string;
    weight: number;
    enabled: boolean;
    created_at: string;
    updated_at: string;
}

export interface CompetitorXrayRunResponse {
    run_id: string;
    status: string;
    created_at: string;
}

export interface CompetitorXrayRunStatus {
    run_id: string;
    status: string;
    total_scanned: number;
    total_gaps: number;
    created_at: string;
    finished_at?: string | null;
    error?: string | null;
}

export interface CompetitorXrayItem {
    id: number;
    run_id: string;
    source_id?: number | null;
    competitor_title: string;
    competitor_url: string;
    competitor_summary?: string | null;
    published_at?: string | null;
    priority_score: number;
    status: 'new' | 'used' | 'ignored' | string;
    angle_title?: string | null;
    angle_rationale?: string | null;
    angle_questions_json: string[];
    starter_sources_json: string[];
    matched_article_id?: number | null;
    created_at: string;
    updated_at: string;
}

export interface CompetitorXrayBrief {
    item_id: number;
    title: string;
    counter_angle: string;
    why_it_wins: string;
    newsroom_plan: string[];
    starter_sources: string[];
}

export interface CreateUserPayload {
    full_name_ar: string;
    username: string;
    password: string;
    role: 'director' | 'editor_chief' | 'journalist' | 'social_media' | 'print_editor';
    departments: string[];
    specialization?: string | null;
    is_active?: boolean;
}

export interface UpdateUserPayload {
    full_name_ar?: string;
    username?: string;
    password?: string;
    role?: 'director' | 'editor_chief' | 'journalist' | 'social_media' | 'print_editor';
    departments?: string[];
    specialization?: string | null;
    is_active?: boolean;
}

export const authApi = {
    login: (username: string, password: string) =>
        api.post<{ access_token: string; token_type: string; user: TeamMember }>('/auth/login', { username, password }),
    me: () => api.get<TeamMember>('/auth/me'),
    logout: () => api.post('/auth/logout'),
    users: () => api.get<TeamMember[]>('/auth/users'),
    createUser: (payload: CreateUserPayload) => api.post<TeamMember>('/auth/users', payload),
    updateUser: (userId: number, payload: UpdateUserPayload) => api.put<TeamMember>(`/auth/users/${userId}`, payload),
    userActivity: (userId: number, limit = 100) =>
        api.get<UserActivityLogItem[]>(`/auth/users/${userId}/activity`, { params: { limit } }),
};

export const memoryApi = {
    overview: () => api.get<ProjectMemoryOverview>('/memory/overview'),
    list: (params?: {
        q?: string;
        memory_type?: string;
        status?: string;
        tag?: string;
        page?: number;
        per_page?: number;
    }) => api.get<ProjectMemoryListResponse>('/memory/items', { params }),
    get: (itemId: number) => api.get<ProjectMemoryItem>(`/memory/items/${itemId}`),
    create: (payload: {
        memory_type: 'operational' | 'knowledge' | 'session';
        title: string;
        content: string;
        tags?: string[];
        source_type?: string | null;
        source_ref?: string | null;
        article_id?: number | null;
        importance?: number;
    }) => api.post<ProjectMemoryItem>('/memory/items', payload),
    update: (itemId: number, payload: Partial<{
        memory_type: 'operational' | 'knowledge' | 'session';
        title: string;
        content: string;
        tags: string[];
        source_type: string | null;
        source_ref: string | null;
        article_id: number | null;
        importance: number;
        status: 'active' | 'archived';
    }>) => api.patch<ProjectMemoryItem>(`/memory/items/${itemId}`, payload),
    markUsed: (itemId: number, note?: string) =>
        api.post<ProjectMemoryEvent>(`/memory/items/${itemId}/use`, { note }),
    events: (itemId: number, limit = 50) =>
        api.get<ProjectMemoryEvent[]>(`/memory/items/${itemId}/events`, { params: { limit } }),
};

export const msiApi = {
    profiles: () => api.get<MsiProfileInfo[]>('/msi/profiles'),
    run: (payload: {
        profile_id: string;
        entity: string;
        mode: 'daily' | 'weekly';
        start?: string;
        end?: string;
    }) => api.post<MsiRunResponse>('/msi/run', payload),
    runStatus: (runId: string) => api.get<MsiRunStatusResponse>(`/msi/runs/${runId}`),
    report: (runId: string) => api.get<MsiReport>('/msi/report', { params: { run_id: runId } }),
    timeseries: (params: { profile_id: string; entity: string; mode: 'daily' | 'weekly'; limit?: number }) =>
        api.get<MsiTimeseriesResponse>('/msi/timeseries', { params }),
    top: (params?: { mode?: 'daily' | 'weekly'; limit?: number }) =>
        api.get<{ mode: string; items: MsiTopEntityItem[] }>('/msi/top', { params }),
    watchlist: (enabled_only?: boolean) =>
        api.get<MsiWatchlistItem[]>('/msi/watchlist', { params: { enabled_only } }),
    addWatchlist: (payload: {
        profile_id: string;
        entity: string;
        aliases?: string[];
        run_daily?: boolean;
        run_weekly?: boolean;
        enabled?: boolean;
    }) => api.post<MsiWatchlistItem>('/msi/watchlist', payload),
    updateWatchlist: (itemId: number, payload: { run_daily?: boolean; run_weekly?: boolean; enabled?: boolean; aliases?: string[] }) =>
        api.patch<MsiWatchlistItem>(`/msi/watchlist/${itemId}`, payload),
    deleteWatchlist: (itemId: number) => api.delete(`/msi/watchlist/${itemId}`),
    seedWatchlist: () => api.post<{ created: number; updated: number; total_defaults: number }>('/msi/watchlist/seed'),
};

export const simApi = {
    run: (payload: {
        headline: string;
        excerpt?: string;
        platform?: 'facebook' | 'x';
        article_id?: number;
        draft_id?: number;
        mode?: 'fast' | 'deep';
        idempotency_key?: string;
    }) => api.post<SimRunResponse>('/sim/run', payload),
    runStatus: (runId: string) => api.get<SimRunStatusResponse>(`/sim/runs/${runId}`),
    result: (runId: string) => api.get<SimResult>('/sim/result', { params: { run_id: runId } }),
    history: (params?: { article_id?: number; draft_id?: number; limit?: number }) =>
        api.get<{ items: SimHistoryItem[]; total: number }>('/sim/history', { params }),
};

export const mediaLoggerApi = {
    runFromUrl: (payload: { media_url: string; language_hint?: 'ar' | 'fr' | 'en' | 'auto'; idempotency_key?: string }) =>
        api.post<MediaLoggerRunResponse>('/media-logger/run/url', payload),
    runFromUpload: (payload: { file: File; language_hint?: 'ar' | 'fr' | 'en' | 'auto'; idempotency_key?: string }) => {
        const form = new FormData();
        form.append('file', payload.file);
        form.append('language_hint', payload.language_hint || 'ar');
        if (payload.idempotency_key) form.append('idempotency_key', payload.idempotency_key);
        return api.post<MediaLoggerRunResponse>('/media-logger/run/upload', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout: 120000,
        });
    },
    runStatus: (runId: string) => api.get<MediaLoggerRunStatusResponse>(`/media-logger/runs/${runId}`),
    result: (runId: string) => api.get<MediaLoggerResult>('/media-logger/result', { params: { run_id: runId } }),
    ask: (payload: { run_id: string; question: string }) => api.post<MediaLoggerAskResponse>('/media-logger/ask', payload),
    recentRuns: (params?: { limit?: number; status_filter?: string }) =>
        api.get<{ items: MediaLoggerRecentRun[]; total: number }>('/media-logger/runs', { params }),
};

export const competitorXrayApi = {
    seedSources: () => api.post<{ created: number; updated: number; total_defaults: number }>('/competitor-xray/sources/seed'),
    sources: (enabled_only?: boolean) => api.get<CompetitorXraySource[]>('/competitor-xray/sources', { params: { enabled_only } }),
    createSource: (payload: { name: string; feed_url: string; domain: string; language?: string; weight?: number; enabled?: boolean }) =>
        api.post<CompetitorXraySource>('/competitor-xray/sources', payload),
    updateSource: (sourceId: number, payload: { name?: string; language?: string; weight?: number; enabled?: boolean }) =>
        api.patch<CompetitorXraySource>(`/competitor-xray/sources/${sourceId}`, payload),
    run: (payload?: { limit_per_source?: number; hours_window?: number; idempotency_key?: string }) =>
        api.post<CompetitorXrayRunResponse>('/competitor-xray/run', payload || {}),
    runStatus: (runId: string) => api.get<CompetitorXrayRunStatus>(`/competitor-xray/runs/${runId}`),
    latest: (params?: { limit?: number; status_filter?: string; q?: string }) =>
        api.get<CompetitorXrayItem[]>('/competitor-xray/items/latest', { params }),
    markUsed: (itemId: number, status_value: 'used' | 'ignored' | 'new' = 'used') =>
        api.post<{ id: number; status: string }>(`/competitor-xray/items/${itemId}/mark-used`, null, { params: { status_value } }),
    brief: (payload: { item_id: number; tone?: string }) =>
        api.post<CompetitorXrayBrief>('/competitor-xray/brief', payload),
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

