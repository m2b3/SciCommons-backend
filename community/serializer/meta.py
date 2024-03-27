from rest_framework import serializers

from community.models import CommunityMeta

'''
CommunityMeta serializers
'''


class CommunityMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityMeta
        fields = ['community', 'article', 'status']
        depth = 1


class CommunityMetaArticlesSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityMeta
        fields = ['article', 'status']
        depth = 1


class CommunityMetaApproveSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityMeta
        fields = ['community', 'status']
        depth = 1


__all__ = [
    "CommunityMetaSerializer",
    "CommunityMetaArticlesSerializer",
    "CommunityMetaApproveSerializer",
]
