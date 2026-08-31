from django.test import SimpleTestCase, TestCase
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


class MainFeedItemsAPITestCase(SimpleTestCase):
    def setUp(self):
        self.client = TestClient(router)

    def test_returns_static_handoff_feed_shape(self):
        response = self.client.get("/main/items")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["feed"]["slug"], "u1-main")
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["generation"], 1)
        self.assertEqual(data["counts"]["pubmed"], 2)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["artifact_version"], "legacy")
        self.assertIsNotNone(data["completed_at"])
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["items"][0]["paper_key"], "pubmed:dev-002")

    def test_filters_items_by_source(self):
        pubmed_response = self.client.get("/main/items?source=pubmed")
        arxiv_response = self.client.get("/main/items?source=arxiv")

        self.assertEqual(pubmed_response.status_code, 200)
        self.assertEqual(pubmed_response.json()["total"], 2)
        self.assertEqual({item["source"] for item in pubmed_response.json()["items"]}, {"pubmed"})

        self.assertEqual(arxiv_response.status_code, 200)
        self.assertEqual(arxiv_response.json()["total"], 0)
        self.assertEqual(arxiv_response.json()["items"], [])

    def test_limits_items_and_returns_an_opaque_cursor(self):
        first_response = self.client.get("/main/items?source=pubmed&limit=1")

        self.assertEqual(first_response.status_code, 200)
        first_page = first_response.json()
        self.assertEqual(first_page["total"], 2)
        self.assertEqual(len(first_page["items"]), 1)
        self.assertTrue(first_page["has_more"])
        self.assertEqual(first_page["next_cursor"], "static:1")

        second_response = self.client.get(
            f"/main/items?source=pubmed&limit=1&cursor={first_page['next_cursor']}"
        )

        self.assertEqual(second_response.status_code, 200)
        second_page = second_response.json()
        self.assertEqual([item["paper_key"] for item in second_page["items"]], ["pubmed:dev-004"])
        self.assertFalse(second_page["has_more"])
        self.assertIsNone(second_page["next_cursor"])

    def test_rejects_invalid_cursor(self):
        response = self.client.get("/main/items?cursor=not-a-static-cursor")

        self.assertEqual(response.status_code, 400)
