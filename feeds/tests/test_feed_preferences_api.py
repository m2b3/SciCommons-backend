from django.test import TestCase
from ninja.testing import TestClient
from rest_framework_simplejwt.tokens import RefreshToken

from feeds.api import router
from feeds.models import FeedPreference
from users.models import User


class FeedPreferencesAPITestCase(TestCase):
    def setUp(self):
        self.client = TestClient(router)
        self.user = User.objects.create_user(
            username="feeduser",
            email="feeduser@example.com",
            password="password123",
        )
        access_token = RefreshToken.for_user(self.user).access_token
        self.headers = {"Authorization": f"Bearer {access_token}"}

    def test_get_returns_empty_preferences_when_nothing_saved(self):
        response = self.client.get("/preferences", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["has_saved_preferences"])
        self.assertEqual(data["topics"], [])
        self.assertEqual(data["similar_to"], [])

    def test_put_creates_a_single_row_for_the_user(self):
        payload = {
            "topics": ["auditory neuroscience", "transformers"],
            "authors": ["Jennifer Doudna"],
            "keywords": ["C. Elegans OR Caenorhabditis Elegans"],
            "similar_to": ["pubmed:22878719"],
        }

        response = self.client.put("/preferences", json=payload, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["has_saved_preferences"])

        self.assertEqual(FeedPreference.objects.count(), 1)
        preference = FeedPreference.objects.get(user_id=self.user.id)
        self.assertEqual(preference.username, "feeduser")
        self.assertEqual(preference.topics, ["auditory neuroscience", "transformers"])
        self.assertEqual(preference.authors, ["Jennifer Doudna"])
        self.assertEqual(preference.similar_to, ["pubmed:22878719"])

    def test_put_updates_the_existing_row_instead_of_adding_one(self):
        self.client.put("/preferences", json={"topics": ["transformers"]}, headers=self.headers)
        self.client.put("/preferences", json={"topics": ["JEPA"], "authors": ["David Chalmers"]}, headers=self.headers)

        self.assertEqual(FeedPreference.objects.count(), 1)
        preference = FeedPreference.objects.get(user_id=self.user.id)
        self.assertEqual(preference.topics, ["JEPA"])
        self.assertEqual(preference.authors, ["David Chalmers"])

    def test_put_clears_a_field_when_the_user_removes_every_entry(self):
        self.client.put("/preferences", json={"topics": ["transformers"]}, headers=self.headers)
        self.client.put("/preferences", json={"topics": []}, headers=self.headers)

        preference = FeedPreference.objects.get(user_id=self.user.id)
        self.assertEqual(preference.topics, [])

    def test_put_trims_blanks_and_case_insensitive_duplicates(self):
        payload = {"authors": ["  Jennifer Doudna  ", "jennifer doudna", "", "   ", "David Chalmers"]}

        response = self.client.put("/preferences", json=payload, headers=self.headers)

        self.assertEqual(response.json()["authors"], ["Jennifer Doudna", "David Chalmers"])

    def test_preferences_are_scoped_to_the_logged_in_user(self):
        other_user = User.objects.create_user(
            username="otheruser",
            email="otheruser@example.com",
            password="password123",
        )
        other_headers = {"Authorization": f"Bearer {RefreshToken.for_user(other_user).access_token}"}

        self.client.put("/preferences", json={"topics": ["transformers"]}, headers=self.headers)
        response = self.client.get("/preferences", headers=other_headers)

        self.assertFalse(response.json()["has_saved_preferences"])
        self.assertEqual(FeedPreference.objects.count(), 1)

    def test_requires_authentication(self):
        response = self.client.get("/preferences")

        self.assertEqual(response.status_code, 401)
