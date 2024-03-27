import random

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from article.models import Article, Author
from article.serializer.article import AuthorSerializer, ArticleGetSerializer, ArticlelistSerializer
from chat.models import PersonalMessage
from chat.serializer import MessageListSerializer
from social.models import Follow
from social.serializer import SocialPostSerializer, FollowSerializer, FollowersSerializer, FollowingSerializer, \
    SocialPostListSerializer
from user.models import User, EmailVerify, ForgetPassword, UserActivity
from user.permissions import UserPermission
from rest_framework import parsers, viewsets, status

from user.serializer import UserSerializer, LoginSerializer, UserCreateSerializer, UserUpdateSerializer, \
    ForgotPasswordSerializer, ResetPasswordSerializer, UserActivitySerializer, VerifySerializer


class UserViewset(viewsets.ModelViewSet):
    # The above code is defining a Django view for handling user-related operations.
    queryset = User.objects.all()
    permission_classes = [UserPermission]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    http_method_names = ['get', 'post', 'put', 'delete']

    search_fields = ['username', 'email']
    action_serializers = {
        'login': LoginSerializer,
        'create': UserCreateSerializer,
        'list': UserSerializer,
        'update': UserUpdateSerializer,
        'forgot_password': ForgotPasswordSerializer,
        'reset_password': ResetPasswordSerializer,
        'get_current_user': UserSerializer,
        'getMyArticles': AuthorSerializer,
        'getMyArticle': AuthorSerializer,
        'getUserArticles': UserSerializer,
        'getposts': SocialPostSerializer,
        'follow': FollowSerializer,
        'unfollow': FollowSerializer,
        'followers': FollowersSerializer,
        'following': FollowingSerializer,
        'myactivity': UserActivitySerializer,
        'verifyrequest': ForgotPasswordSerializer,
        'verifyemail': VerifySerializer,
        'messages': MessageListSerializer,
        "getmyposts": SocialPostSerializer,
    }

    def get_serializer_class(self):
        return self.action_serializers.get(self.action, self.serializer_class)

    def get_authenticated_user(self):
        user = get_object_or_404(self.queryset, pk=self.request.user.pk)
        self.check_object_permissions(self.request, user)
        return user

    def list(self, request):

        response = super(UserViewset, self).list(request)

        return Response(data={"success": response.data})

    def retrieve(self, request, pk):

        response = super(UserViewset, self).retrieve(request, pk=pk)
        print(response.data)
        return Response(data={"success": response.data})

    def create(self, request):
        super(UserViewset, self).create(request)

        return Response(data={"success": "User successfully added"})

    def update(self, request, pk):

        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(data={"success": serializer.data})

    def destroy(self, request, pk):

        super(UserViewset, self).destroy(request, pk=pk)

        return Response(data={"success": "User successfully deleted"})

    @action(methods=['post'], detail=False, permission_classes=[permissions.AllowAny, ])
    def login(self, request, pk=None):
        """
        The above function is a login function that accepts a POST request, validates the data using a
        serializer, and returns a success response with the serialized data.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, query
        parameters, and the request body
        :param pk: The `pk` parameter is used to identify a specific object in the API. It stands for
        "primary key" and is typically used when performing CRUD operations (Create, Read, Update,
        Delete) on a specific object. In this case, since `detail=False`, the `pk` parameter is
        :return: The code is returning a Response object with the data {"success": serializer.data}.
        """
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            return Response(data={"success": serializer.data})

    @action(methods=['get'], detail=False, url_path="articles", permission_classes=[permissions.IsAuthenticated, ])
    def getMyArticles(self, request):
        """
        This function retrieves all articles written by the authenticated user.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the user making the request, the HTTP method used
        (GET, POST, etc.), and any data or parameters sent with the request. In this case, the `request`
        object is
        :return: The code is returning a response with a JSON object containing the serialized data of
        the articles that belong to the authenticated user. The serialized data is obtained using the
        ArticlelistSerializer class and is passed the articles queryset as well as the request context.
        The JSON object is wrapped in a "success" key.
        """
        authors = Author.objects.filter(User_id=request.user.id)
        articles = Article.objects.filter(author__in=authors)
        article_serializer = ArticlelistSerializer(articles, many=True, context={'request': request})

        return Response(data={"success": article_serializer.data})

    @action(methods=['get'], detail=False, url_path="articles/(?P<articleId>.+)",
            permission_classes=[permissions.IsAuthenticated, ])
    def getMyArticle(self, request, articleId):
        """
        This function retrieves a specific article belonging to the authenticated user.

        :param request: The `request` parameter is the HTTP request object that contains information
        about the current request, such as the user making the request, the request method (GET, POST,
        etc.), and any data or parameters included in the request
        :param articleId: The `articleId` parameter is a variable that represents the ID of the article
        that the user wants to retrieve. It is extracted from the URL path using regular expression
        matching
        :return: The response will contain a JSON object with the key "success" and the value will be
        the serialized data of the article(s) matching the given articleId.
        """
        from article.models import Author
        from article.models import Article

        authors = Author.objects.filter(User_id=request.user.id)
        articles = Article.objects.filter(author__in=authors, id=articleId)
        article_serializer = ArticleGetSerializer(articles, many=True, context={'request': request})

        return Response(data={"success": article_serializer.data})

    @action(methods=['get'], detail=False, url_path="(?P<username>.+)/posts", permission_classes=[UserPermission])
    def getposts(self, request, username):
        """
        This function retrieves all social posts for a given user.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (GET, POST, etc.), headers, query
        parameters, and the body of the request
        :param username: The `username` parameter is a string that represents the username of a user. It
        is used to filter the `User` objects and retrieve the user with the specified username
        :return: The code is returning a response with the serialized data of the social posts belonging
        to the user specified by the username parameter. The response data is a dictionary with a
        "success" key, and the value is the serialized data of the posts.
        """
        from social.models import SocialPost

        instance = User.objects.filter(username=username).first()
        queryset = SocialPost.objects.filter(user_id=instance.id)
        serializer = SocialPostListSerializer(data=queryset, many=True, context={'request': request})
        serializer.is_valid()
        posts = serializer.data
        return Response(data={"success": posts})

    @action(methods=['get'], detail=False, url_path="myposts", permission_classes=[UserPermission])
    def getmyposts(self, request):
        """
        This function retrieves all social posts created by a specific user and returns them in
        descending order of creation.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (GET, POST, etc.), headers, user
        authentication details, and query parameters
        :return: The code is returning a response with the data of the user's posts. The data being
        returned is a dictionary with a key "success" and the value being the serialized data of the
        user's posts.
        """
        from social.models import SocialPost

        instance = User.objects.filter(id=request.user).first()
        queryset = SocialPost.objects.filter(user_id=instance.id).order_by('-created_at')
        serializer = SocialPostListSerializer(data=queryset, many=True, context={'request': request})
        serializer.is_valid()
        posts = serializer.data
        return Response(data={"success": posts})

    @action(methods=['get'], detail=False, url_path="(?P<username>.+)/articles", permission_classes=[UserPermission])
    def getUserArticles(self, request, username):
        """
        This function retrieves all articles written by a specific user and returns them as a response.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (GET, POST, etc.), headers, query
        parameters, and the body of the request
        :param username: The `username` parameter is a string that represents the username of a user. It
        is used to filter the `User` objects based on the provided username
        :return: The response will contain a JSON object with a "success" key and the value will be a
        list of serialized article objects.
        """
        from article.models import Author

        user = User.objects.filter(username=username).first()
        queryset = Author.objects.filter(User_id=user.id)
        articles = Article.objects.filter(author__in=queryset)
        serializer = ArticlelistSerializer(articles, many=True, context={'request': request})
        articles = serializer.data
        return Response(data={"success": articles})

    @action(methods=['get'], detail=False, permission_classes=[permissions.IsAuthenticated, ])
    def get_current_user(self, request, pk=None):
        """
        get logged in user
        """
        serializer = self.get_serializer(self.get_authenticated_user())
        return Response(data={"success": serializer.data})

    @action(methods=['post'], url_path="verifyrequest", detail=False, permission_classes=[permissions.AllowAny, ])
    def verifyrequest(self, request):
        """
        The above function is a Django view that verifies a user's email address by sending an OTP
        (One-Time Password) to their email.

        :param request: The request object contains information about the HTTP request made to the API,
        such as the request method (POST in this case) and the data sent in the request body
        :return: The code is returning a response with a success message "code sent to your email" if
        the email verification request is successful.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        otp = random.randint(100000, 999999)
        user = User.objects.filter(email=serializer.data['email']).first()

        if user is None:
            return Response(data={"error": "Please Enter valid email address!!!"}, status=status.HTTP_400_BAD_REQUEST)

        if user.email_verified == True:
            return Response(data={"error": "Email already verified!!!"}, status=status.HTTP_400_BAD_REQUEST)

        verify = EmailVerify.objects.create(user=user, otp=otp)
        email_from = settings.EMAIL_HOST_USER
        email_subject = "Email Verification"
        email_body = "Your One Time Password is " + str(otp)
        send_mail(email_subject, email_body, email_from, [serializer.data['email']], fail_silently=False)
        return Response(data={"success": "code sent to your email"})

    @action(methods=['post'], url_path="verify_email", detail=False, permission_classes=[permissions.AllowAny, ])
    def verifyemail(self, request):
        """
        The above function verifies the email address of a user by checking the OTP (One-Time Password)
        provided and updates the user's email_verified field to True if the verification is successful.

        :param request: The request object contains information about the HTTP request made to the
        server, including the data sent in the request body
        :return: The code is returning a response in JSON format. If the user is not found or the OTP
        authentication fails, it returns an error message with a status code of 400 (Bad Request). If
        the email verification is successful, it returns a success message with a status code of 200.
        """
        otp = request.data.get('otp')
        email = request.data.get('email')
        user = User.objects.filter(email=email).first()
        if user is None:
            return Response(data={"error": "Please enter correct mail address"}, status=status.HTTP_400_BAD_REQUEST)
        res = EmailVerify.objects.filter(otp=otp, user=user).first()
        if res is None:
            res1 = EmailVerify.objects.filter(user=user).first()
            res1.delete()
            return Response(data={"error": "Otp authentication failed.Please generate new Otp!!!"},
                            status=status.HTTP_400_BAD_REQUEST)
        res.delete()
        user.email_verified = True
        user.save()
        return Response(data={"success": "Email Verified Successfully!!!"})

    @action(methods=['post'], url_path="forgot_password", detail=False, permission_classes=[permissions.AllowAny, ])
    def forgot_password(self, request):
        """
        The above function is a Django view that handles the forgot password functionality by generating
        a random OTP, saving it in the database, and sending it to the user's email address.

        :param request: The request object contains information about the HTTP request made to the API,
        such as the request method (POST in this case) and the data sent in the request body
        :return: The code is returning a response with a success message indicating that the OTP
        (One-Time Password) has been sent to the user's email address.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        otp = random.randint(100000, 999999)

        user = User.objects.filter(email=serializer.data['email']).first()
        if user is None:
            return Response(data={"error": "Please enter a valid email address"}, status=status.HTTP_400_BAD_REQUEST)

        if user.email_verified == False:
            return Response(data={"error": "Please verify your email address"}, status=status.HTTP_400_BAD_REQUEST)

        forget = ForgetPassword.objects.create(user=user, otp=otp)
        forget.save()

        email_from = settings.EMAIL_HOST_USER
        email_subject = "Reset Password"
        email_body = "You have forgot you account password. Your One Time Password is " + str(otp)
        send_mail(email_subject, email_body, email_from, [serializer.data['email']], fail_silently=False)
        return Response(data={"success": "code sent to your email"})

    @action(methods=['post'], url_path="reset_password", detail=False, permission_classes=[permissions.AllowAny, ])
    def reset_password(self, request):
        """
        The above function is a Django view that handles the password reset functionality by verifying the
        OTP and updating the user's password.

        :param request: The request object contains information about the HTTP request being made, such as
        the headers, body, and method
        :return: The code is returning a response object with the following data:
        """
        otp = request.data.get('otp')
        email = request.data.get('email')
        password = request.data.get('password')
        password2 = request.data.get('password2')
        user = User.objects.filter(email=email).first()
        if user is None:
            return Response(data={"error": "Please enter valid email address"}, status=status.HTTP_400_BAD_REQUEST)
        forget = ForgetPassword.objects.filter(otp=otp, user=user).first()
        if forget is None:
            return Response(data={"error": "Invalid One Time Password."}, status=status.HTTP_400_BAD_REQUEST)

        user = forget.user
        if password == password2:
            user.set_password(password)
            user.save()
            forget.delete()
            return Response(data={"success": "password reset successfully"})
        else:
            messages.error(request, 'Password not matching.')
            return Response(data={"error": "Password not matching"}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=['post'], url_path='follow', detail=False, permission_classes=[permissions.IsAuthenticated])
    def follow(self, request):
        """
        This function allows a user to follow another user by creating a new entry in the Follow model.

        :param request: The `request` parameter is an object that represents the HTTP request made by the
        client. It contains information such as the request method (e.g., GET, POST), headers, user
        authentication details, and the request data (e.g., form data, JSON payload). In this case, the `
        :return: The code is returning a Response object with either an error message or a success message.
        If the member is not None, indicating that the user is already following the specified user, it will
        return a Response object with an error message: {"error":"Already following!!!"}. Otherwise, it will
        create a new Follow object and return a Response object with a success message:
        {"success":"followed!!!"
        """
        instance = User.objects.filter(id=request.data["followed_user"]).first()
        member = Follow.objects.filter(followed_user=instance, user=request.user).first()
        if member is not None:
            return Response(data={"error": "Already following!!!"})
        Follow.objects.create(followed_user=instance, user=request.user)
        return Response(data={"success": "followed!!!"})

    @action(methods=['post'], url_path='unfollow', detail=False, permission_classes=[permissions.IsAuthenticated])
    def unfollow(self, request):
        """
        This function allows a user to unfollow another user.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, body,
        and user authentication details. In this case, it is used to retrieve the data sent in the
        request body,
        :return: The code is returning a response in JSON format. If the member exists and is
        successfully deleted, it will return a success message: {"success":"UnFollowed!!!"}. If the
        member does not exist, it will return an error message: {"error":"Did not Follow!!!"}.
        """
        instance = User.objects.filter(id=request.data["followed_user"]).first()
        member = Follow.objects.filter(followed_user=instance, user=request.user).first()
        if member is not None:
            member.delete()
            return Response(data={"success": "UnFollowed!!!"})
        else:
            return Response(data={"error": "Did not Follow!!!"})

    @action(methods=['get'], url_path='myactivity', detail=False, permission_classes=[permissions.IsAuthenticated])
    def myactivity(self, request):
        """
        The `myactivity` function retrieves the activities of the authenticated user and returns them as
        a serialized response.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (GET, POST, etc.), headers, query
        parameters, and the user making the request (if authenticated)
        :return: The response will contain a JSON object with a "success" key and the serialized data of
        the user's activities as the value.
        """
        activities = UserActivity.objects.filter(user_id=request.user)
        serializer = UserActivitySerializer(activities, many=True)
        return Response(data={"success": serializer.data})

    @action(methods=['get'], url_path="followers", detail=False, permission_classes=[UserPermission])
    def followers(self, request):
        """
        This function retrieves the followers of a user and returns a serialized response.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (GET, POST, etc.), headers, query
        parameters, and body
        :return: The code is returning a response with the serialized data of the followers of a user
        specified by the "username" query parameter. The response data is in the format of a dictionary
        with a key "success" and the value being the serialized data of the followers.
        """
        instance = User.objects.filter(username=request.query_params.get("username")).first()
        member = Follow.objects.filter(followed_user=instance)
        serializer = FollowersSerializer(member, many=True, context={'request': request})
        return Response(data={"success": serializer.data})

    @action(methods=['get'], url_path="following", detail=False, permission_classes=[UserPermission])
    def following(self, request):
        """
        The above function retrieves the list of users that a given user is following and returns it as
        a serialized response.

        :param request: The `request` parameter is the HTTP request object that contains information
        about the current request, such as the user making the request, the requested URL, and any query
        parameters or data sent with the request. It is passed to the view function or method as an
        argument
        :return: The code is returning a response with a JSON object containing the serialized data of
        the following members of a user. The JSON object has a "success" key with the value being the
        serialized data of the following members.
        """
        instance = User.objects.filter(username=request.query_params.get("username")).first()
        member = Follow.objects.filter(user=instance.id)
        serializer = FollowingSerializer(member, many=True, context={'request': request})
        return Response(data={"success": serializer.data})

    @action(methods=['get'], url_path="messages", detail=False, permission_classes=[UserPermission])
    def messages(self, request):
        """
        This function retrieves the most recent message and number of unread messages for each user that
        has messaged the current user, and orders it by the most recent message.

        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the user making the request, the HTTP method used
        (GET, POST, etc.), and any data or parameters sent with the request. In this case, it is used to
        identify the
        :return: The response will be a JSON object with a "success" key and the serialized data of the
        messages as its value.
        """
        # retrieve most recent message and number of unread messages of each user that has messaged the current user and order it by the most recent message
        messages = PersonalMessage.objects.filter(Q(sender=request.user) | Q(receiver=request.user)).distinct('sender',
                                                                                                              'receiver').order_by(
            'sender', 'receiver', '-created_at')
        serializer = MessageListSerializer(messages, many=True, context={'request': request})
        return Response(data={"success": serializer.data})
