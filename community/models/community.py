from django.db import models


# The Community class represents a community with various attributes such as title, subtitle,
# description, location, date, GitHub link, email, website, user, and members.
class Community(models.Model):
    title = models.CharField(max_length=300, unique=True, name='Community_name')
    subtitle = models.CharField(max_length=300, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=100, null=True, blank=True)
    date = models.DateField(auto_now_add=True, null=True)
    github = models.URLField(max_length=200, null=True, blank=True)
    email = models.EmailField(max_length=100, null=True, blank=True)
    website = models.CharField(max_length=300, null=True)
    user = models.OneToOneField('user.User', on_delete=models.CASCADE)
    members = models.ManyToManyField('user.User', through="CommunityMember", related_name='members')

    class Meta:
        db_table = 'community'

    def __str__(self):
        return self.Community_name


# The `CommunityMeta` class represents the metadata associated with an article in a community,
# including its status.
class CommunityMeta(models.Model):
    community = models.ForeignKey('community.Community', on_delete=models.CASCADE)
    article = models.ForeignKey('article.Article', on_delete=models.CASCADE, related_name="article_meta")
    ARTICLE_STATUS = {
        ('submitted', 'submitted'),
        ('in review', 'in review'),
        ('accepted', 'accepted'),
        ('published', 'published'),
        ('rejected by user', 'rejected by user'),
        ('rejected', 'rejected')
    }
    status = models.CharField(max_length=255, choices=ARTICLE_STATUS)

    class Meta:
        db_table = 'community_meta'
        unique_together = ["article", "community"]

    def __str__(self) -> str:
        return f"{self.community} - {self.article}"


# The `CommunityRequests` class represents a model for community requests, including information about
# the request, the user making the request, the community the request is for, and the status of the
# request.
class CommunityRequests(models.Model):
    about = models.CharField(max_length=5000, null=True)
    summary = models.CharField(max_length=5000, null=True)
    user = models.ForeignKey('user.User', related_name='requests', on_delete=models.CASCADE)
    community = models.ForeignKey('community.Community', related_name='requests', on_delete=models.CASCADE)
    REQUEST_STATUS = {
        ('pending', 'pending'),
        ('approved', 'approved'),
        ('rejected', 'rejected')
    }
    status = models.CharField(max_length=10, null=False, choices=REQUEST_STATUS)

    class Meta:
        db_table = 'community_request'

    def __str__(self):
        return f"{self.community.title}-{self.user.username}"


__all__ = [
    'Community',
    'CommunityMeta',
    'CommunityRequests',
]
