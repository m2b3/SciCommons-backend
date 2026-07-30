from django.test import SimpleTestCase, override_settings

from myapp.upload_api import extract_image_object_keys


@override_settings(
    AWS_S3_CUSTOM_DOMAIN=(
        "object-arbutus.alliancecan.ca/"
        "56ef6dfb16b64243bb362f8bb7a23da2:cdn.scicommons.org"
    )
)
class ExtractImageObjectKeysTests(SimpleTestCase):
    object_key = (
        "user-attachments/prod/"
        "7_user_55b31315_1768284442.jpg"
    )

    def test_extracts_project_qualified_object_url(self):
        content = (
            "![image](https://object-arbutus.alliancecan.ca/"
            "56ef6dfb16b64243bb362f8bb7a23da2:cdn.scicommons.org/"
            f"{self.object_key}?download=1#preview)"
        )

        self.assertEqual(extract_image_object_keys(content), {self.object_key})

    def test_extracts_legacy_cdn_url(self):
        content = f"https://cdn.scicommons.org/{self.object_key}"

        self.assertEqual(extract_image_object_keys(content), {self.object_key})

    def test_ignores_lookalike_domain(self):
        content = f"https://cdn.scicommons.org.example.com/{self.object_key}"

        self.assertEqual(extract_image_object_keys(content), set())
