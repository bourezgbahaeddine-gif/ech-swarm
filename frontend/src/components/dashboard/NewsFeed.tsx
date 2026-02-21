'use client';

import Link from 'next/link';
import { type ArticleBrief } from '@/lib/api';
import { cn, formatRelativeTime, getStatusColor, getCategoryLabel, isFreshBreaking, truncate } from '@/lib/utils';
import { Zap, ExternalLink, Clock, Star } from 'lucide-react';

interface NewsFeedProps {
    articles: ArticleBrief[] | undefined;
    isLoading: boolean;
    title?: string;
}

function ArticleCard({ article }: { article: ArticleBrief }) {
    const displayTitle = article.title_ar || article.original_title;
    const freshBreaking = isFreshBreaking(article.is_breaking, article.crawled_at);

    return (
        <Link href={`/news/${article.id}`} className="block">
            <div
                className={cn(
                    'group relative rounded-xl p-4 transition-all duration-300',
                    'app-surface',
                    'border hover:shadow-md cursor-pointer',
                    freshBreaking
                        ? 'border-red-300 hover:border-red-400'
                        : 'border-[var(--border-primary)] hover:border-gray-300',
                )}
            >
                {freshBreaking && (
                    <div className="absolute -top-2 right-4 px-2.5 py-0.5 rounded-full bg-[var(--semantic-danger)] text-[10px] font-bold text-white flex items-center gap-1 shadow-sm breaking-pulse">
                        <Zap className="w-3 h-3" />
                        عاجل
                    </div>
                )}

                <div className="flex items-start gap-3">
                    <div className="flex flex-col items-center gap-1 pt-0.5">
                        <div
                            className={cn(
                                'w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold',
                                article.importance_score >= 8
                                    ? 'bg-red-50 text-red-600 border border-red-200'
                                    : article.importance_score >= 6
                                      ? 'bg-amber-50 text-amber-600 border border-amber-200'
                                      : article.importance_score >= 4
                                        ? 'bg-sky-50 text-sky-700 border border-sky-200'
                                        : 'bg-gray-100 text-gray-600 border border-gray-200',
                            )}
                        >
                            {article.importance_score}
                        </div>
                    </div>

                    <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-semibold leading-relaxed transition-colors line-clamp-2 text-[var(--text-primary)] group-hover:text-[var(--accent-blue)]" dir="rtl">
                            {displayTitle}
                        </h3>

                        {article.summary && (
                            <p className="mt-1.5 text-xs app-text-muted leading-relaxed line-clamp-2" dir="rtl">
                                {truncate(article.summary, 150)}
                            </p>
                        )}

                        <div className="flex flex-wrap items-center gap-2 mt-3">
                            <span className={cn('px-2 py-0.5 rounded-md text-[10px] font-medium border', getStatusColor(article.status))}>
                                {article.status}
                            </span>
                            <span className="text-[10px] app-text-muted">{getCategoryLabel(article.category)}</span>
                            {article.source_name && (
                                <span className="text-[10px] app-text-muted flex items-center gap-1">
                                    <ExternalLink className="w-3 h-3" />
                                    {article.source_name}
                                </span>
                            )}
                            <span className="text-[10px] app-text-muted flex items-center gap-1 mr-auto">
                                <Clock className="w-3 h-3" />
                                {formatRelativeTime(article.crawled_at)}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </Link>
    );
}

function ArticleSkeleton() {
    return (
        <div className="rounded-xl p-4 app-surface border animate-pulse">
            <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg app-surface-soft border" />
                <div className="flex-1 space-y-2">
                    <div className="h-4 w-3/4 app-surface-soft border rounded" />
                    <div className="h-3 w-full app-surface-soft border rounded" />
                    <div className="flex gap-2 mt-3">
                        <div className="h-5 w-16 app-surface-soft border rounded-md" />
                        <div className="h-5 w-20 app-surface-soft border rounded-md" />
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function NewsFeed({ articles, isLoading, title = 'آخر الأخبار' }: NewsFeedProps) {
    return (
        <div className="rounded-2xl app-surface border overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--border-primary)]">
                <h2 className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                    <Star className="w-4 h-4 text-[var(--semantic-warning)]" />
                    {title}
                </h2>
                {articles && (
                    <span className="text-[10px] app-text-muted px-2 py-0.5 rounded-full app-surface-soft border">{articles.length} خبر</span>
                )}
            </div>

            <div className="p-3 space-y-2 max-h-[600px] overflow-y-auto scrollbar-thin">
                {isLoading ? (
                    Array.from({ length: 5 }).map((_, i) => <ArticleSkeleton key={i} />)
                ) : articles && articles.length > 0 ? (
                    articles.map((article) => <ArticleCard key={article.id} article={article} />)
                ) : (
                    <div className="text-center py-12 app-text-muted">
                        <Zap className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        <p className="text-sm">لا توجد أخبار حالياً</p>
                    </div>
                )}
            </div>
        </div>
    );
}
