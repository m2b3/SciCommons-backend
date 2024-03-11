from app.models import *
from django.db.models import Count
import django_filters


# The `PostFilters` class is a Django filter class that allows filtering of `SocialPost` objects based
# on different ordering options such as most recent, most commented, most liked, and most bookmarked.
class PostFilters(django_filters.FilterSet):
    order = django_filters.MultipleChoiceFilter(
        choices=[
            ('most_recent', 'Most Recent'),
            ('most_commented', 'Most Commented'),
            ('most_liked', 'Most Liked'),
            ('most_bookmarked', 'Most Bookmarked'),
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
                queryset = queryset.annotate(comment_count=Count('comments')).order_by('-comment_count').exclude(
                    user=self.request.user)
            else:
                queryset = queryset.annotate(comment_count=Count('comments')).order_by('-comment_count')
        if 'most_liked' in value:
            if self.request.user.is_authenticated:
                queryset = queryset.annotate(like_count=Count('likes')).order_by('-like_count').exclude(
                    user=self.request.user)
            else:
                queryset = queryset.annotate(like_count=Count('likes')).order_by('-like_count')
        if 'most_bookmarked' in value:
            if self.request.user.is_authenticated:
                queryset = queryset.annotate(bookmark_count=Count('bookmark')).order_by('-bookmark_count').exclude(
                    user=self.request.user)
            else:
                queryset = queryset.annotate(bookmark_count=Count('bookmark')).order_by('-bookmark_count')
        return queryset
