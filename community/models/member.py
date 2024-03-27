from django.db import models


# The `CommunityMember` class represents a member of a community, with fields for the community they
# belong to, the user they are associated with, and their roles within the community.
class CommunityMember(models.Model):
    community = models.ForeignKey("community.Community", on_delete=models.CASCADE)
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)
    is_reviewer = models.BooleanField(default=False)
    is_moderator = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    class Meta:
        db_table = 'community_member'
        constraints = [
            models.UniqueConstraint(fields=['community', 'user'], name='unique_admin_per_community'),
            models.UniqueConstraint(fields=['user', 'is_admin'], condition=models.Q(is_admin=True),
                                    name='only_one_community_admin')
        ]

    def __str__(self) -> str:
        return f"{self.user} - {self.community}"


# The UnregisteredUser class represents a user who is not registered in the system and is associated
# with an article, with attributes for full name and email.
class UnregisteredUser(models.Model):
    article = models.ForeignKey("article.Article", on_delete=models.CASCADE)
    fullName = models.CharField(max_length=255, null=False)
    email = models.EmailField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = 'unregistered_user'


# The `OfficialReviewer` class represents an official reviewer in a community, with a user, official
# reviewer name, and community as its attributes.
class OfficialReviewer(models.Model):
    User = models.ForeignKey('user.User', on_delete=models.CASCADE)
    Official_Reviewer_name = models.CharField(max_length=100)
    community = models.ForeignKey('community.Community', on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'officialreviewer'
        unique_together = ['User', 'community']

    def __str__(self) -> str:
        return self.User.username


# The Moderator class represents a moderator in a community, with a foreign key to the Community and
# User models.
class Moderator(models.Model):
    community = models.ForeignKey('community.Community', on_delete=models.CASCADE)
    user = models.ForeignKey('user.User', on_delete=models.CASCADE)

    class Meta:
        db_table = 'moderator'
        unique_together = ["user", "community"]

    def __str__(self) -> str:
        return self.user.username


__all__ = [
    'CommunityMember',
    'UnregisteredUser',
    'OfficialReviewer',
    'Moderator',
]
