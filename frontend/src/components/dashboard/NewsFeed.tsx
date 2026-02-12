'use client';

import { type ArticleBrief } from '@/lib/api';
import { cn, formatRelativeTime, getStatusColor, getUrgencyColor, getCategoryLabel, truncate } from '@/lib/utils';
import { Zap, ExternalLink, Clock, Star } from 'lucide-react';

interface NewsFeedProps {
    articles: ArticleBrief[] | undefined;
    isLoading: boolean;
    title?: string;
}

function ArticleCard({ article }: { article: ArticleBrief }) {
    const displayTitle = article.title_ar || article.original_title;

    return (
        <div className={cn(
            'group relative rounded-xl p-4 transition-all duration-300',
            'bg-gradient-to-br from-gray-800/40 to-gray-900/60',
            'border hover:shadow-lg cursor-pointer',
            article.is_breaking
                ? 'border-red-500/30 hover:border-red-500/60 hover:shadow-red-500/10'
                : 'border-white/5 hover:border-emerald-500/20 hover:shadow-emerald-500/5',
        )}>
            {/* Breaking badge */}
            {article.is_breaking && (
                <div className="absolute -top-2 right-4 px-2.5 py-0.5 rounded-full bg-red-500 text-[10px] font-bold text-white flex items-center gap-1 shadow-lg shadow-red-500/30 animate-pulse">
                    <Zap className="w-3 h-3" />
                    عاجل
                </div>
            )}

            <div className="flex items-start gap-3">
                {/* Importance indicator */}
                <div className="flex flex-col items-center gap-1 pt-0.5">
                    <div className={cn(
                        'w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold',
                        article.importance_score >= 8 ? 'bg-red-500/20 text-red-400' :
                            article.importance_score >= 6 ? 'bg-amber-500/20 text-amber-400' :
                                article.importance_score >= 4 ? 'bg-blue-500/20 text-blue-400' :
                                    'bg-gray-500/20 text-gray-400',
                    )}>
                        {article.importance_score}
                    </div>
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-white leading-relaxed group-hover:text-emerald-300 transition-colors line-clamp-2" dir="rtl">
                        {displayTitle}
                    </h3>

                    {article.summary && (
                        <p className="mt-1.5 text-xs text-gray-400 leading-relaxed line-clamp-2" dir="rtl">
                            {truncate(article.summary, 150)}
                        </p>
                    )}

                    {/* Meta row */}
                    <div className="flex flex-wrap items-center gap-2 mt-3">
                        <span className={cn('px-2 py-0.5 rounded-md text-[10px] font-medium border', getStatusColor(article.status))}>
                            {article.status}
                        </span>
                        <span className="text-[10px] text-gray-500">
                            {getCategoryLabel(article.category)}
                        </span>
                        {article.source_name && (
                            <span className="text-[10px] text-gray-600 flex items-center gap-1">
                                <ExternalLink className="w-3 h-3" />
                                {article.source_name}
                            </span>
                        )}
                        <span className="text-[10px] text-gray-600 flex items-center gap-1 mr-auto">
                            <Clock className="w-3 h-3" />
                            {formatRelativeTime(article.crawled_at)}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    );
}

function ArticleSkeleton() {
    return (
        <div className="rounded-xl p-4 bg-gray-800/30 border border-white/5 animate-pulse">
            <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-lg bg-gray-700" />
                <div className="flex-1 space-y-2">
                    <div className="h-4 w-3/4 bg-gray-700 rounded" />
                    <div className="h-3 w-full bg-gray-700/50 rounded" />
                    <div className="flex gap-2 mt-3">
                        <div className="h-5 w-16 bg-gray-700 rounded-md" />
                        <div className="h-5 w-20 bg-gray-700/50 rounded-md" />
                    </div>
                </div>
            </div>
        </div>
    );
}

export default function NewsFeed({ articles, isLoading, title = 'آخر الأخبار' }: NewsFeedProps) {
    return (
        <div className="rounded-2xl bg-gray-800/20 border border-white/5 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Star className="w-4 h-4 text-amber-400" />
                    {title}
                </h2>
                {articles && (
                    <span className="text-[10px] text-gray-500 px-2 py-0.5 rounded-full bg-white/5">
                        {articles.length} خبر
                    </span>
                )}
            </div>

            <div className="p-3 space-y-2 max-h-[600px] overflow-y-auto scrollbar-thin">
                {isLoading ? (
                    Array.from({ length: 5 }).map((_, i) => <ArticleSkeleton key={i} />)
                ) : articles && articles.length > 0 ? (
                    articles.map((article) => (
                        <ArticleCard key={article.id} article={article} />
                    ))
                ) : (
                    <div className="text-center py-12 text-gray-500">
                        <Zap className="w-8 h-8 mx-auto mb-2 opacity-30" />
                        <p className="text-sm">لا توجد أخبار حالياً</p>
                    </div>
                )}
            </div>
        </div>
    );
}
