import django_filters
from django.db.models.functions import Coalesce
from django.db.models import Count, Q, Avg, Value

from article.models import CommentBase, Article


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
            ('most_rated', 'Most Rated'),
            ('least_rated', 'Least Rated'),

        ],
        method='filter_by_ordering'
    )

    class Meta:
        model = Article
        fields = []

    def filter_by_ordering(self, queryset, name, value):

        if 'most_rated' in value:
            queryset = (queryset.annotate(
                avg_rating=Coalesce(Avg('commentbase__rating', filter=Q(commentbase__Type='review')),
                                    Value(0.0))).order_by('-avg_rating'))
        if 'least_rated' in value:
            queryset = (queryset.annotate(
                avg_rating=Coalesce(Avg('commentbase__rating', filter=Q(commentbase__Type='review')),
                                    Value(0.0))).order_by('avg_rating'))
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
            ('most_rated', 'Most Rated'),
            ('least_rated', 'Least Rated'),
            ('most_reputed', "Most Reputed"),
            ('least_reputed', "Least Reputed")
        ],
        method='filter_by_ordering'
    )
    Type = django_filters.CharFilter(field_name='Type')
    comment_type = django_filters.CharFilter(field_name='comment_type')
    tag = django_filters.CharFilter(field_name='tag')
    article = django_filters.CharFilter(field_name='article')
    parent_comment = django_filters.CharFilter(field_name='parent_comment')
    version = django_filters.CharFilter(field_name='version')

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
            queryset = CommentBase.objects.filter(query).annotate(
                likes_count=Count('posts__value', filter=Q(posts__value__isnull=False)))
            queryset = queryset.order_by('-likes_count')

        if 'least_rated' in value:
            query = Q(Type='review') | Q(Type='decision')
            queryset = CommentBase.objects.filter(query).annotate(
                likes_count=Count('posts__value', filter=Q(posts__value__isnull=False)))
            queryset = queryset.order_by('likes_count')

        if 'least_reputed' in value:
            queryset = queryset.order_by("user_rank")
        if 'most_reputed' in value:
            queryset = queryset.order_by("-user_rank")

        return queryset
