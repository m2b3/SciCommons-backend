from django.test import TestCase
from ..models import *
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

class UserTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('user-list')  # Reverse the URL using the name 'user-list'
        user_creation_data = {
            "username": "testinguser",
            "first_name": "string",
            "last_name": "string",
            "email": "user@example.com",
            "password": "string"
        }
        response = self.client.post(self.url, user_creation_data, format='json')
        user = User.objects.filter(username="testinguser").first()
        user.email_verified = True
        user.save()

        user_creation_data2 = {
            "username": "testinguser2",
            "first_name": "string",
            "last_name": "string",
            "email": "user2@example.com",
            "password": "string"
        }
        user2 = self.client.post(self.url, user_creation_data2, format='json')
        response2 = self.client.post(self.url, user_creation_data2, format='json')
        user2 = User.objects.filter(username="testinguser2").first()
        user2.email_verified = True
        user2.save()
        

    def test_user_login(self):
        self.url = reverse('user-login')  # Reverse the URL using the name 'user-list'
        user_login_data = {
            "username" : "testinguser",
            "password" : "string"
        }
        response = self.client.post(self.url,user_login_data,format='json')

        response_data = response.json()
        self.assertEqual(response.status_code,status.HTTP_200_OK)
        self.assertIn("success",response_data)
        self.access = response_data["success"]["access"]

    def test_user_articles(self):
        self.url = reverse('article-list')
        response = self.client.get(self.url)

        self.assertIn("success",response.json())
        self.assertEqual(response.status_code,status.HTTP_200_OK)

    def test_user_followers(self):
        self.url = reverse('user-followers')
        response = self.client.get(self.url)

        self.assertIn("success",response.json())
        self.assertEqual(response.status_code,status.HTTP_200_OK)

    def test_user_follow(self):
        self.url = reverse('user-login')  # Reverse the URL using the name 'user-list'
        user_login_data = {
            "username" : "testinguser",
            "password" : "string"
        }
        response = self.client.post(self.url,user_login_data,format='json')
        self.access = response.json()["success"]["access"]

        self.url = reverse('user-follow')
        user = User.objects.filter(username="testinguser2").first()
        user_id = user.id
        follow_data = {"followed_user" : user_id}

        token_header = 'Bearer ' + self.access
        response = self.client.post(self.url,follow_data,format='json',HTTP_AUTHORIZATION=token_header)

        self.assertIn("success",response.json())
        self.assertEqual(response.status_code,status.HTTP_200_OK)



        