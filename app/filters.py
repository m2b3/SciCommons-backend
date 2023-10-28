import django_filters
from app.models import *
from django.db.models import Count, Q, Subquery, Sum, OuterRef, Avg, Value
import django_filters 
from django.db.models import F
from django.db.models.functions import Coalesce

# The ArticleFilter class is a Django filter that allows users to sort articles based on various
# criteria such as views, rating, and publication date.
class ArticleFilter(django_filters.FilterSet):
    order = django_filters.MultipleChoiceFilter(
        choices=[
            ('most_viewed', 'Most Viewed'),
            ('least_viewed', 'Least Viewed'),
            ('most_recent', 'Most Recent'),
            ('least_recent', 'Least Recent'),
            ('most_favourite', 'Most Favourite'),
            ('least_favourite', 'Least Favourite'),
            ('most_rated','Most Rated'),
            ('least_rated','Least Rated'),

        ],
        method='filter_by_ordering'
    )

    class Meta:
        model = Article
        fields = []

    def filter_by_ordering(self, queryset, name, value):

        if 'most_rated' in value:
            queryset = (queryset.annotate(avg_rating=Coalesce(Avg('commentbase__rating', filter=Q(commentbase__Type='review')), Value(0.0))).order_by('-avg_rating'))
        if 'least_rated' in value:
            queryset = (queryset.annotate(avg_rating=Coalesce(Avg('commentbase__rating', filter=Q(commentbase__Type='review')), Value(0.0))).order_by('avg_rating'))
        if 'most_viewed' in value:
            queryset = queryset.order_by('-views')
        if 'least_viewed' in value:
            queryset = queryset.order_by('views')
        if 'most_recent' in value:
            queryset = queryset.order_by('-Public_date')
        if 'least_recent' in value:
            queryset = queryset.order_by('Public_date')
        if 'most_favourite' in value:
            queryset = queryset.order_by('favourite')
        if 'least_favourite' in value:
            queryset = queryset.order_by('-favourite')
    
        return queryset
    
# The CommentFilter class is a Django filter class that allows filtering and ordering of CommentBase
# objects based on various criteria such as order, type, comment type, tag, article, parent comment,
# and version.
class CommentFilter(django_filters.FilterSet):
    order = django_filters.MultipleChoiceFilter(
        choices=[
            ('most_recent', 'Most Recent'),
            ('least_recent', 'Least Recent'),
            ('most_rated','Most Rated'),
            ('least_rated','Least Rated'),
            ('most_reputed', "Most Reputed"),
            ('least_reputed', "Least Reputed")
        ],
        method='filter_by_ordering'
    )
    Type=django_filters.CharFilter(field_name='Type')
    comment_type=django_filters.CharFilter(field_name='comment_type')
    tag=django_filters.CharFilter(field_name='tag')
    article=django_filters.CharFilter(field_name='article')
    parent_comment=django_filters.CharFilter(field_name='parent_comment')
    version=django_filters.CharFilter(field_name='version')
    
    class Meta:
        model = CommentBase
        fields = []

    def filter_by_ordering(self, queryset, name, value):
        if 'most_recent' in value:
            queryset = queryset.order_by('-Comment_date')
        if 'least_recent' in value:
            queryset = queryset.order_by('Comment_date')
        if 'most_rated' in value:
            query = Q(Type='review') | Q(Type='decision')
            queryset = CommentBase.objects.filter(query).annotate(likes_count=Count('posts__value', filter=Q(posts__value__isnull=False)))
            queryset = queryset.order_by('-likes_count')

        if 'least_rated' in value:
            query = Q(Type='review') | Q(Type='decision')
            queryset = CommentBase.objects.filter(query).annotate(likes_count=Count('posts__value', filter=Q(posts__value__isnull=False)))
            queryset = queryset.order_by('likes_count')

        if 'least_reputed' in value:
            queryset = queryset.order_by("user_rank")
        if 'most_reputed' in value:
            queryset = queryset.order_by("-user_rank")

        
        return queryset
    
# The `PostFilters` class is a Django filter class that allows filtering of `SocialPost` objects based
# on different ordering options such as most recent, most commented, most liked, and most bookmarked.
class PostFilters(django_filters.FilterSet):

    order = django_filters.MultipleChoiceFilter(
        choices=[
            ('most_recent', 'Most Recent'),
            ('most_commented','Most Commented'),
            ('most_liked','Most Liked'),
            ('most_bookmarked','Most Bookmarked'),
        ],
        method='filter_by_ordering'
    )

    class Meta:
        model = SocialPost
        fields = []

    def filter_by_ordering(self, queryset, name, value):
        if 'most_recent' in value:
            if self.request.user.is_authenticated:
                queryset = queryset.order_by('-created_at').exclude(user=self.request.user)
            else:
                queryset = queryset.order_by('-created_at')
        if 'most_commented' in value:
            if self.request.user.is_authenticated:
                queryset = queryset.annotate(comment_count=Count('comments')).order_by('-comment_count').exclude(user=self.request.user)
            else:
                queryset = queryset.annotate(comment_count=Count('comments')).order_by('-comment_count')
        if 'most_liked' in value:
            if self.request.user.is_authenticated:
                queryset = queryset.annotate(like_count=Count('likes')).order_by('-like_count').exclude(user=self.request.user)
            else:
                queryset = queryset.annotate(like_count=Count('likes')).order_by('-like_count')
        if 'most_bookmarked' in value:
            if self.request.user.is_authenticated:
                queryset = queryset.annotate(bookmark_count=Count('bookmark')).order_by('-bookmark_count').exclude(user=self.request.user)
            else:
                queryset = queryset.annotate(bookmark_count=Count('bookmark')).order_by('-bookmark_count')
        return queryset