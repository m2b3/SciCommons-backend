from django.db import models


class FeedPreference(models.Model):
    """
    Stores one row of feed preferences per user.

    Added by Claude on 2026-08-10
    What: Per-user feed preference row (topics / authors / keywords / similar-to).
    Why: The feed needs user-supplied criteria to build a personalised front page.
    How: A single row per user, each criterion kept as a JSON list of strings.

    Note: `user_id` is a plain integer instead of a ForeignKey to users.User on
    purpose. It keeps this table free of cross-table dependencies so it can be
    moved to its own database later without a schema change.
    """

    user_id = models.PositiveIntegerField(unique=True, db_index=True)
    username = models.CharField(max_length=150, db_index=True)

    # e.g. ["auditory neuroscience", "transformers"]
    topics = models.JSONField(default=list, blank=True)
    # e.g. ["Jennifer Doudna", "David Chalmers"]
    authors = models.JSONField(default=list, blank=True)
    # e.g. ["C. Elegans OR Caenorhabditis Elegans", "JEPA"]
    keywords = models.JSONField(default=list, blank=True)
    # e.g. ["pubmed:22878719"]
    similar_to = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "feed_preference"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.username} - feed preferences"
