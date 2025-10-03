# Auto-Subscription System Implementation

## Overview
Automated discussion subscription system that automatically subscribes users to real-time notifications when:
1. **Articles are published** to private/hidden communities → Admins + submitter get subscribed
2. **Users become admins** → They get subscribed to all existing articles in the community

## Features
✅ **Automatic Django Signals** - No manual integration needed
✅ **Private/Hidden Communities Only** - Public articles excluded
✅ **Duplicate Prevention** - Won't create duplicate subscriptions  
✅ **Error Handling** - Comprehensive logging and error recovery
✅ **Management Command** - Backfill existing data
✅ **Real-time Integration** - Works with existing WebSocket system

## Files Created/Modified

### Core Implementation
- `articles/auto_subscription_integration.py` - Django signals implementation
- `articles/apps.py` - AppConfig to register signals
- `articles/models.py` - DiscussionSubscription model + helper methods
- `articles/schemas.py` - API schemas
- `articles/discussion_api.py` - REST API endpoints

### Management
- `articles/management/commands/backfill_auto_subscriptions.py` - Backfill command
- `myapp/settings.py` - Updated to use custom AppConfig

## How It Works

### 1. Automatic Triggers (Django Signals)

**Article Publication:**
```python
# When CommunityArticle.status changes to 'published' or 'accepted'
@receiver(post_save, sender=CommunityArticle)
def create_subscriptions_on_article_published(sender, instance, **kwargs):
    # Auto-subscribes community admins + article submitter
```

**Admin Promotion:**
```python  
# When users are added to community.admins
@receiver(m2m_changed, sender=Community.admins.through)
def create_subscriptions_on_admin_added(sender, instance, action, pk_set, **kwargs):
    # Auto-subscribes new admin to all community articles
```

### 2. Manual Subscription (API)

Users can also manually subscribe:
```http
POST /articles/discussions/subscribe/
{
  "community_article_id": 123,
  "community_id": 456
}
```

### 3. Real-time Notifications

All active subscribers receive real-time WebSocket notifications for:
- New discussions created
- New comments posted  
- Comment replies

## Usage

### Deploy the System
1. **Run Migration:**
   ```bash
   python manage.py makemigrations articles
   python manage.py migrate
   ```

2. **Signals are Active** - Auto-subscriptions will happen automatically from now on

### Backfill Existing Data
```bash
# Preview what would be created
python manage.py backfill_auto_subscriptions --dry-run

# Create subscriptions for all communities
python manage.py backfill_auto_subscriptions

# Process specific community only
python manage.py backfill_auto_subscriptions --community-id 123
```

### Monitor Logs
```bash
# Look for these log messages:
# Auto-subscriptions created for article 'Title' in community 'Name': 3 subscriptions
# Auto-subscriptions created for new admin 'username' in community 'Name': 5 subscriptions
```

## API Endpoints

### User Subscription Management
- `POST /discussions/subscribe/` - Manual subscription
- `DELETE /discussions/subscriptions/{id}/` - Unsubscribe
- `GET /discussions/my-subscriptions/` - Get user's subscriptions (grouped by community)
- `GET /discussions/subscription-status/` - Check subscription status

### Response Format
```json
{
  "communities": [
    {
      "community_id": 1,
      "community_name": "AI Research",
      "articles": [
        {
          "article_id": 123,
          "article_title": "Deep Learning Paper",
          "article_slug": "deep-learning-paper"
        }
      ]
    }
  ]
}
```

## Testing

### Test Auto-Subscription
1. **Create private community** with some admins
2. **Submit article** to community → Check admins + submitter are subscribed
3. **Promote user to admin** → Check they're subscribed to all articles
4. **Create discussion** → Check subscribers receive real-time notifications

### Test Manual Subscription  
1. **Join private community** as regular member
2. **Subscribe to article** via API
3. **Create discussion** → Check you receive real-time notifications
4. **Unsubscribe** → Check notifications stop

## Configuration

### Enable/Disable Features
Edit `articles/auto_subscription_integration.py`:

```python
# Enable subscriptions on article submission (instead of publication)
def create_subscriptions_on_article_submission(sender, instance, **kwargs):
    # Uncomment the code block in this function
```

### Logging Levels
- `INFO` - Successful subscription creation
- `DEBUG` - No subscriptions needed (already exist)
- `ERROR` - Failed subscription creation

## Troubleshooting

### Signals Not Working
- Check `myapp/settings.py` uses `articles.apps.ArticlesConfig`
- Restart Django server after changes

### No Subscriptions Created
- Ensure community type is 'private' or 'hidden' (not 'public')
- Check article status is 'published' or 'accepted'
- Verify users are community members

### Migration Issues
```bash
# If you get migration conflicts:
python manage.py makemigrations articles --empty
# Add manual migration operations if needed
```

## Architecture Notes

- **Signals run in same transaction** as the triggering operation
- **Error handling** prevents signals from breaking main operations  
- **Idempotent** - Safe to run multiple times
- **Scalable** - Uses efficient DB queries with select_related/prefetch_related
- **Real-time ready** - Integrates with existing WebSocket infrastructure
