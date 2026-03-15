from django.core.management.base import BaseCommand
from django.utils import timezone
from users.models import User
from communities.models import Community, Membership, CommunityArticle
from articles.models import Article

class Command(BaseCommand):
    help = 'Seeds PoC data for the AI Reviewer Recommendation system'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting PoC data seed...")

        # 1. Create a Community
        community, _ = Community.objects.get_or_create(
            name="Cognitive Neuroscience Society",
            defaults={"description": "Community dedicated to neuroimaging and cognition research."}
        )

        # 2. Create Users (Reviewers with different semantic bios)
        users_data = [
            {
                "username": "dr_fmri_expert",
                "email": "fmri@example.com",
                "bio": "Neuroscientist specializing in functional magnetic resonance imaging (fMRI) to study attention, working memory, and prefrontal cortex function."
            },
            {
                "username": "eeg_researcher",
                "email": "eeg@example.com",
                "bio": "Cognitive psychology researcher focused on temporal dynamics of attention using electroencephalography (EEG) and event-related potentials."
            },
            {
                "username": "clinical_neurologist",
                "email": "clinical@example.com",
                "bio": "Physician treating patients with frontal lobe lesions, studying the behavioral impacts of disrupted attention networks."
            },
            {
                "username": "computational_modeler",
                "email": "comp@example.com",
                "bio": "Computer scientist building artificial neural networks inspired by human brain architecture to simulate cognitive processes."
            },
            {
                "username": "botanist_user",
                "email": "botany@example.com",
                "bio": "Plant biologist studying photosynthesis pathways, soil microbiomes, and environmental adaptations in tropical flora."
            }
        ]

        memberships_created = 0
        for data in users_data:
            user, created = User.objects.get_or_create(
                username=data["username"],
                defaults={"email": data["email"], "bio": data["bio"]}
            )
            # Add to community
            Membership.objects.get_or_create(
                user=user,
                community=community,
                defaults={"joined_at": timezone.now()}
            )
            if created:
                memberships_created += 1

        # 3. Create Submitting User
        submitter, _ = User.objects.get_or_create(
            username="author_jones",
            defaults={"email": "jones@test.com", "bio": "Postdoc studying human attention."}
        )

        # 4. Create the Article
        article, _ = Article.objects.get_or_create(
            title="Attention mechanisms in prefrontal cortex during working memory tasks",
            defaults={
                "abstract": "We utilized high-resolution fMRI to investigate the role of the dorsolateral prefrontal cortex in sustaining attention during a delayed-response task. Results suggest a dynamic network engagement...",
                "submitter": submitter,
                "submission_type": "Public"
            }
        )

        # 5. Add Article to Community
        CommunityArticle.objects.get_or_create(
            article=article,
            community=community,
            defaults={"status": "submitted"}
        )

        self.stdout.write(self.style.SUCCESS("Seed data created successfully"))
        self.stdout.write(f"Article ID: {article.id}")
        self.stdout.write(f"Community ID: {community.id}")
        self.stdout.write("Use these IDs in the editorial dashboard.")
