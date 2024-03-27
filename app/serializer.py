import datetime
import random
import uuid
from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import IntegrityError, transaction
from faker import Faker
from django.core.mail import send_mail
from django.db.models import Avg, Sum, Q
from django.conf import settings

import json

fake = Faker()

from app.models import *














