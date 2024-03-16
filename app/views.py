import secrets
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework.decorators import action
from rest_framework import parsers, viewsets, permissions, status
from rest_framework.response import Response
from django.core.mail import send_mail
from django.contrib import messages
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from django.db.models import Q,Count,Subquery, OuterRef
from django.db.models.functions import Coalesce
from app.models import *
from app.serializer import *
from app.permissions import *
from app.filters import *
from rest_framework import filters
from django_filters import rest_framework as django_filters 

class UserViewset(viewsets.ModelViewSet):
    # The above code is defining a Django view for handling user-related operations.
    queryset = User.objects.all()
    permission_classes = [UserPermission]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    http_method_names = ['get','post','put','delete']

    search_fields = ['username', 'email']
    action_serializers = {
        'login':LoginSerializer,
        'create':UserCreateSerializer,
        'list': UserSerializer,
        'update':UserUpdateSerializer,
        'forgot_password':ForgotPasswordSerializer,
        'reset_password':ResetPasswordSerializer,
        'get_current_user':UserSerializer,
        'getMyArticles':AuthorSerializer,
        'getMyArticle':AuthorSerializer,
        'getUserArticles':UserSerializer,
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

        response = super(UserViewset, self).retrieve(request,pk=pk)
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

        return Response(data={"success":serializer.data})


    def destroy(self, request, pk ):

        super(UserViewset, self).destroy(request,pk=pk)

        return Response(data={"success": "User successfully deleted"})

    @action(methods=['post'], detail=False, permission_classes=[permissions.AllowAny,])
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
            return Response(data={"success":serializer.data})

    @action(methods=['get'], detail=False, url_path="articles", permission_classes=[permissions.IsAuthenticated,])
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
        article_serializer = ArticlelistSerializer(articles, many=True, context={'request':request})

        return Response(data={"success": article_serializer.data})
    
    @action(methods=['get'], detail=False, url_path="articles/(?P<articleId>.+)", permission_classes=[permissions.IsAuthenticated,])
    def getMyArticle(self, request,articleId):
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
        authors = Author.objects.filter(User_id=request.user.id)
        articles = Article.objects.filter(author__in=authors,id=articleId)
        article_serializer = ArticleGetSerializer(articles, many=True, context={'request':request})

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
        user = User.objects.filter(username=username).first()
        queryset = Author.objects.filter(User_id=user.id)
        articles = Article.objects.filter(author__in=queryset)
        serializer = ArticlelistSerializer(articles, many=True, context={'request':request})
        articles = serializer.data
        return Response(data={"success": articles})

    @action(methods=['get'], detail=False,permission_classes=[permissions.IsAuthenticated,])
    def get_current_user(self, request, pk=None):
        """
        get logged in user
        """
        serializer = self.get_serializer(self.get_authenticated_user())
        return Response(data={"success": serializer.data})

    @action(methods=['post'],url_path="verifyrequest", detail=False,permission_classes=[permissions.AllowAny,])
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
        otp = secrets.randbelow(999999 - 100000 + 1) + 100000
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
    
    @action(methods=['post'],url_path="verify_email",detail=False,permission_classes=[permissions.AllowAny,])
    def verifyemail(self,request):
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
        res = EmailVerify.objects.filter(otp=otp,user=user).first()
        if res is None:
            res1 = EmailVerify.objects.filter(user=user).first()
            res1.delete()
            return Response(data={"error": "Otp authentication failed.Please generate new Otp!!!"}, status=status.HTTP_400_BAD_REQUEST)
        res.delete()
        user.email_verified = True
        user.save()
        return Response(data={"success": "Email Verified Successfully!!!"})

    @action(methods=['post'],url_path="forgot_password", detail=False,permission_classes=[permissions.AllowAny,])
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
        
        otp = secrets.randbelow(999999 - 100000 + 1) + 100000

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

        
    @action(methods=['post'],url_path="reset_password", detail=False,permission_classes=[permissions.AllowAny,])
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
            return Response(data={"error":"Invalid One Time Password."}, status=status.HTTP_400_BAD_REQUEST)
                
        user = forget.user
        if password == password2:
            user.set_password(password)
            user.save()
            forget.delete()
            return Response(data={"success": "password reset successfully"})
        else:
            messages.error(request, 'Password not matching.')
            return Response(data={"error": "Password not matching"}, status=status.HTTP_400_BAD_REQUEST)
        
    @action(methods=['post'],url_path='follow', detail=False, permission_classes=[permissions.IsAuthenticated])
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
            return Response(data={"error":"Already following!!!"})
        Follow.objects.create(followed_user=instance, user=request.user)
        return Response(data={"success":"followed!!!"})

    @action(methods=['post'],url_path='unfollow', detail=False, permission_classes=[permissions.IsAuthenticated])
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
        member = Follow.objects.filter(followed_user=instance,user=request.user).first()
        if member is not None:
            member.delete()
            return Response(data={"success":"UnFollowed!!!"})
        else:
            return Response(data={"error":"Did not Follow!!!"})
    
    @action(methods=['get'],url_path='myactivity',detail=False,permission_classes=[permissions.IsAuthenticated])
    def myactivity(self,request):
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
        serializer = UserActivitySerializer(activities,many=True)
        return Response(data={"success":serializer.data})
        
    @action(methods=['get'],url_path="followers", detail=False,permission_classes=[UserPermission])
    def followers(self,request):
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
        serializer = FollowersSerializer(member,many=True,context={'request':request})
        return Response(data={"success": serializer.data})

    @action(methods=['get'],url_path="following", detail=False,permission_classes=[UserPermission])
    def following(self,request):
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
        serializer = FollowingSerializer(member,many=True,context={'request':request})
        return Response(data={"success": serializer.data})
    
    @action(methods=['get'],url_path="messages", detail=False,permission_classes=[UserPermission])
    def messages(self,request):
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
        messages = PersonalMessage.objects.filter(Q(sender=request.user) | Q(receiver=request.user)).distinct('sender','receiver').order_by('sender','receiver','-created_at')
        serializer = MessageListSerializer(messages,many=True,context={'request':request})
        return Response(data={"success": serializer.data})

class CommunityViewset(viewsets.ModelViewSet):
    # The above code is defining a view for a Django REST Framework API endpoint for the `Community`
    # model. It retrieves all instances of the `Community` model from the database using the
    # `Community.objects.all()` method and assigns it to the `queryset` variable. It also retrieves
    # all instances of the `CommunityMeta` model and assigns it to the `queryset2` variable, and
    # retrieves all instances of the `CommunityMember` model and assigns it to the `queryset3`
    # variable.
    queryset = Community.objects.all()
    queryset2 = CommunityMeta.objects.all()
    queryset3 = CommunityMember.objects.all()
    permission_classes = [CommunityPermission]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = CommunitySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    http_method_names = ['post', 'get', 'put', 'delete']
    lookup_field = "Community_name"

    search_fields = ['Community_name']
    
    # The above code defines a dictionary called `action_serializers` which maps different actions to
    # their respective serializers. Each key in the dictionary represents an action, such as "create",
    # "update", "promote_member", etc., and the corresponding value is the serializer class associated
    # with that action. These serializers are used to serialize and deserialize data when performing
    # different actions on a community object.
    action_serializers = {
        "create":CommunityCreateSerializer,
        "update":CommunityUpdateSerializer,
        "promote_member":PromoteSerializer,
        "addPublishedInfo":ArticlePostPublishSerializer,
        "getMembers":CommunityMemberSerializer,
        "getArticles": CommunityMetaArticlesSerializer,
        "list": CommunitylistSerializer,
        "retrieve": CommunityGetSerializer,
        "join_request":JoinRequestSerializer,
        "get_requests":CommunityRequestGetSerializer,
        "approve_request":ApproverequestSerializer,
        "subscribe": SubscribeSerializer,
        "unsubscribe": SubscribeSerializer,
        'mycommunity': CommunitySerializer,
    }
    
    def get_serializer_class(self):
        return self.action_serializers.get(self.action, self.serializer_class)
    
    def list(self, request):

        response = super(CommunityViewset, self).list(request)

        return Response(data={"success":response.data})
    
    def retrieve(self, request, Community_name):
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        response = super(CommunityViewset, self).retrieve(request,Community_name=Community_name)

        return Response(data={"success":response.data})

    def create(self, request):
        
        member = self.queryset.filter(user=request.user).first()
        if member is not None:
            return Response(data={"error": "You already created a community.You can't create another community!!!"}, status=status.HTTP_400_BAD_REQUEST)
        super(CommunityViewset, self).create(request)

        return Response(data={"success": "Community successfully added"})


    def update(self, request, Community_name):
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(data={"success": serializer.data})


    def destroy(self, request, Community_name ):
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        super(CommunityViewset, self).destroy(request,Community_name=Community_name)

        return Response(data={"success": "community successfully deleted"})

    @action(methods=['GET'], detail=False, url_path='(?P<Community_name>.+)/articles', permission_classes=[CommunityPermission])
    def getArticles(self, request, Community_name):
        """
        This function retrieves articles belonging to a specific community and returns them as a
        response.
        
        :param request: The request object represents the HTTP request made by the client. It contains
        information such as the request method (GET, POST, etc.), headers, and query parameters
        :param Community_name: The `Community_name` parameter is a string that represents the name of a
        community. It is used to filter the articles based on the community name
        :return: The response being returned is a JSON object with the key "success" and the value being
        the serialized data of the articles related to the specified community.
        """
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        response = self.queryset2.filter(community__Community_name=Community_name)
        serializer = CommunityMetaArticlesSerializer(data=response, many=True)
        serializer.is_valid()
        articles = serializer.data
        return Response(data={"success": articles})

    @action(methods=['get'], detail=False, url_path="mycommunity", permission_classes=[permissions.IsAuthenticated,])
    def getMyCommunity(self, request):
        """
        This function retrieves the community that the authenticated user is an admin of.
        
        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (GET, POST, etc.), headers, query
        parameters, and the user making the request. In this case, it is used to identify the user
        making the request
        :return: The code is returning a response with the data of the first community that the
        authenticated user is an admin of. The data is returned as a dictionary with a key "success" and
        the value being the community information.
        """
        member = CommunityMember.objects.filter(user=request.user,is_admin=True).first()
        instance = Community.objects.filter(id=member.community.id)
        serializer = CommunitySerializer(data=instance, many=True)
        serializer.is_valid()
        community = serializer.data
        return Response(data={"success": community[0]})
    
    @action(methods=['POST'], detail=False, url_path='(?P<Community_name>.+)/article/(?P<article_id>.+)/publish',permission_classes=[CommunityPermission])
    def addPublishedInfo(self, request, Community_name, article_id):
        """
        This function adds license, article file, DOI, and published date to a published article in a
        community.
        
        :param request: The request object contains information about the current HTTP request, such as
        the headers, body, and user authentication details
        :param Community_name: The Community_name parameter is a string that represents the name of a
        community. It is used to filter the articles based on the community they belong to
        :param article_id: The `article_id` parameter is the unique identifier of the article that you
        want to add published information to. It is used to retrieve the specific article from the
        database
        :return: The code is returning a response with data indicating whether the action was successful
        or not. If the condition `article.published != Community_name` is true, it will return a
        response with an error message. Otherwise, it will update the article object with the provided
        data and return a response with a success message.
        """
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        article = Article.objects.filter(id=article_id).first()
        if(article.published != Community_name):
            return Response(data={"error": "This action can't be performed"})
        else:
            data = request.data
            article.license = data["license"]
            article.published_article_file = data["published_article_file"]
            article.doi = data["doi"]
            article.published_date = datetime.datetime.now()
            article.save()
            return Response(data={"success": "You added the license,Article file to the published Article"})
    
    @action(methods=['GET'],detail=False,url_path='(?P<Community_name>.+)/members',permission_classes=[CommunityPermission])
    def getMembers(self, request, Community_name):
        """
        This function retrieves the members of a community and returns a response with the list of
        users.
        
        :param request: The request object contains information about the current HTTP request, such as
        the headers, method, and body
        :param Community_name: The `Community_name` parameter is a variable that captures the name of
        the community for which you want to retrieve the members. It is extracted from the URL path
        using regular expression matching
        :return: The response being returned is a JSON object with the key "success" and the value being
        the list of members in the specified community.
        """
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        response = self.queryset3.filter(community=obj)
        serializer = self.get_serializer(data=response, many=True)
        serializer.is_valid()
        users = serializer.data
        return Response(data={"success": users})
    
    @action(methods=['POST'],detail=False, url_path='(?P<Community_name>.+)/promote_member',permission_classes=[CommunityPermission]) 
    def promote_member(self, request, Community_name):
        """
        This function promotes a member of a community by updating their user_id in the serializer.
        
        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, query
        parameters, and request body
        :param Community_name: The `Community_name` parameter is a variable that captures the name of
        the community in the URL path. It is used to identify the specific community for which the
        member is being promoted
        :return: The code is returning a Response object with the data and status specified in the code.
        If the member is not found, it returns a Response with an error message and a status of 404 (Not
        Found). If the member is already an admin, it also returns a Response with an error message and
        a status of 404 (Not Found). If the request is successful, it saves the updated data
        """
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        member = User.objects.filter(username=request.data["username"]).first()
        if member is None:
            return Response(data={"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        admin = Community.objects.filter(user_id=member.id).first()
        if admin is not None:
            return Response(data={"error": "You cant perform this action"},status=status.HTTP_404_NOT_FOUND)
        request.data["user_id"] = member.id
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(data={"success": "member promoted successfully"})
    
    @action(methods=['DELETE'],detail=False, url_path='(?P<Community_name>.+)/remove_member/(?P<user_id>.+)',permission_classes=[CommunityPermission]) 
    def remove_member(self, request, Community_name, user_id):
        """
        This function removes a member from a community and sends them an email notification.
        
        :param request: The HTTP request object that contains information about the request made by the
        client
        :param Community_name: The name of the community from which the member will be removed
        :param user_id: The `user_id` parameter is the unique identifier of the user that you want to
        remove from the community
        :return: The code is returning a JSON response with the data "success": "member removed
        successfully" if the member is successfully removed from the community.
        """
        obj = self.get_object()
        self.check_object_permissions(request,obj)

        admin = Community.objects.filter(user_id=user_id).first()
        if admin is not None:
            return Response(data={"error": "You cant perform this action"},status=status.HTTP_404_NOT_FOUND)
        
        try:
            member = CommunityMember.objects.filter(community=obj, user_id=user_id).first()
            emails = []
            emails.append(member.user.email)
            if member is None:
                return Response(data={"error": "Not member of community"}, status=status.HTTP_404_NOT_FOUND)
            member.delete()
            send_mail(f'you are removed from {obj}',f'You have been removed from {obj}.Due to inappropriate behaviour', settings.EMAIL_HOST_USER , emails, fail_silently=False)

            
        except Exception as e:
            return Response(data={'error': 'unable to delete it.Please try again later!!!'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(data={"success": "member removed successfully"})
    
    
    @action(methods=['POST'],detail=False, url_path='(?P<Community_name>.+)/join_request',permission_classes=[CommunityPermission])
    def join_request(self, request, Community_name):
        """
        This function handles a POST request to join a community and saves the join request in the
        database.
        
        :param request: The `request` parameter is the HTTP request object that contains information
        about the request made by the client, such as the request method, headers, and body
        :param Community_name: The `Community_name` parameter is a named capture group in the URL
        pattern. It captures the name of the community that the user wants to send a join request to
        :return: The code is returning a response with a JSON object containing the data from the
        serializer, wrapped in a "success" key.
        """
        obj = self.get_object()
        data = request.data
        data["community"] = obj.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(data={"success":serializer.data})

    @action(methods=['GET'],detail=False, url_path='(?P<Community_name>.+)/get_requests',permission_classes=[CommunityPermission])
    def get_requests(self, request, Community_name):
        """
        This function retrieves all requests related to a specific community and returns them in a
        serialized format.
        
        :param request: The `request` parameter is the HTTP request object that contains information
        about the current request, such as the request method, headers, and query parameters. It is
        provided by the Django REST Framework
        :param Community_name: The `Community_name` parameter is a variable that captures the name of
        the community for which you want to retrieve requests. It is specified in the URL pattern as
        `(?P<Community_name>.+)`, which means that any string can be captured and assigned to the
        `Community_name` variable
        :return: The response being returned is a JSON object with the key "success" and the value being
        the serialized data of the CommunityRequests objects.
        """
        obj = self.get_object()
        requests = CommunityRequests.objects.filter(community=obj)
        serializer = self.get_serializer(requests, many=True)

        return Response(data={"success":serializer.data})

    @action(methods=['POST'],detail=False, url_path='(?P<Community_name>.+)/approve_request',permission_classes=[CommunityPermission])
    def approve_request(self, request, Community_name):
        """
        This function approves a join request for a community and adds the user to the community's
        members list.
        
        :param request: The `request` parameter is the HTTP request object that contains information
        about the request made by the client. It includes details such as the request method (e.g., GET,
        POST), headers, body, and user authentication
        :param Community_name: The `Community_name` parameter is a named capture group in the URL
        pattern. It captures the name of the community from the URL. For example, if the URL is
        `/communities/my-community/approve_request`, then `Community_name` will be set to
        `"my-community"`
        :return: The code is returning a Response object with the data {"success": serializer.data}.
        """
        obj = self.get_object()
        joinrequest = CommunityRequests.objects.get(community=obj)

        serializer = self.get_serializer(joinrequest, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        if serializer.data['status']=="approved":
            obj.members.add(serializer.data['user'])

        joinrequest.delete()

        return Response(data={"success":serializer.data})
    
    @action(methods=['post'], detail=False,url_path='(?P<Community_name>.+)/subscribe', permission_classes=[permissions.IsAuthenticated])
    def subscribe(self, request, Community_name):
        """
        This function allows a user to subscribe to a community if they are not already subscribed.
        
        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, user
        authentication details, and the request body
        :param Community_name: The Community_name parameter is a string that represents the name of the
        community that the user wants to subscribe to
        :return: The code is returning a response in JSON format. If the user is already subscribed to
        the community, it will return a response with an error message "Already Subscribed!!!". If the
        user is not already subscribed, it will create a new subscription and return a response with a
        success message "Subscribed!!!".
        """
        member = Subscribe.objects.filter(community__Community_name=Community_name, user=request.user).first()
        if member is not None:
            return Response(data={"error":"Already Subscribed!!!"})
        instance = Community.objects.filter(Community_name=Community_name).first()
        Subscribe.objects.create(community=instance, user=request.user)
        return Response(data={"success":"Subscribed!!!"})

    @action(methods=['post'], detail=False,url_path='(?P<Community_name>.+)/unsubscribe', permission_classes=[permissions.IsAuthenticated])
    def unsubscribe(self, request,Community_name):
        """
        This function allows a user to unsubscribe from a community by deleting their subscription
        entry.
        
        :param request: The request object contains information about the current HTTP request, such as
        the user making the request, the HTTP method used (e.g., GET, POST), and any data sent with the
        request
        :param Community_name: The Community_name parameter is a string that represents the name of the
        community that the user wants to unsubscribe from
        :return: The code is returning a response in JSON format. If the member is found and
        successfully deleted, it will return a success message: {"success":"Unsubscribed!!!"}. If the
        member is not found, it will return an error message: {"error":"Did not Subscribe!!!"}.
        """
        member = Subscribe.objects.filter(community__Community_name=Community_name,user=request.user).first()
        if member is not None:
            member.delete()
            return Response(data={"success":"Unsubscribed!!!"})
        else:
            return Response(data={"error":"Did not Subscribe!!!"})

    
class ArticleViewset(viewsets.ModelViewSet):
    # The above code is defining a Django view for handling CRUD operations on the Article model. It
    # specifies the queryset to retrieve all Article objects, sets the permission classes to
    # ArticlePermission, and defines the parser classes for handling JSON, multipart, and form data.
    # It also specifies the serializer class to use for serializing and deserializing Article objects,
    # and sets the filter backends to DjangoFilterBackend, SearchFilter, and OrderingFilter for
    # filtering, searching, and ordering the queryset. The filterset_class is set to ArticleFilter for
    # more advanced filtering options. The allowed HTTP methods are specified as post, get
    queryset = Article.objects.all()
    permission_classes = [ArticlePermission]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    serializer_class = ArticleSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter,filters.OrderingFilter]
    filterset_class = ArticleFilter
    http_method_names = ['post', 'get', 'put', 'delete']
    search_fields = ['article_name', 'keywords', 'authorstring']
    
    action_serializers = {
        "list": ArticlelistSerializer,
        "retrieve":ArticleGetSerializer,
        "create":ArticleCreateSerializer,
        "approve_article":ApproveSerializer,
        "approve_review":InReviewSerializer,
        "reject_article": RejectSerializer,
        "submit_article":SubmitArticleSerializer,
        "update": ArticleUpdateSerializer,
        "getIsapproved": CommunityMetaApproveSerializer,
        "getPublished": ArticlePublishSelectionSerializer,
        "status": StatusSerializer,
        "updateViews": ArticleViewsSerializer,
        "block_user": ArticleBlockUserSerializer,
        "favourite": FavouriteCreateSerializer,
        "unfavourite": FavouriteSerializer,
        "favourites": FavouriteSerializer

    }
    
    def get_serializer_class(self):
        return self.action_serializers.get(self.action, self.serializer_class)
    
    def get_queryset(self):
        queryset = self.queryset
        return queryset

    
    def list(self, request):
        response = super(ArticleViewset, self).list(request)

        return Response(data={"success":response.data})
    
    def retrieve(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        response = super(ArticleViewset, self).retrieve(request,pk=pk)

        return Response(data={"success":response.data})

    def create(self, request):
        name = request.data['article_name']
        name = name.replace(' ','_')
        article = self.queryset.filter(article_name=name).first()
        if article is not None:
            return Response(data={"error": "Article with same name already exists!!!"}, status=status.HTTP_400_BAD_REQUEST)
        response = super(ArticleViewset, self).create(request)
    
        return Response(data={"success": "Article successfully submitted"})


    def update(self, request, pk):
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        article = Article.objects.filter(id=pk).first()
        response = ArticleGetSerializer(article,context={'request': request})
        return Response(data={"success": "Article successfully updated", "data":response.data})

    def destroy(self, request, pk ):
        obj = self.get_object()
        self.check_object_permissions(request,obj)

        super(ArticleViewset, self).destroy(request,pk=pk)

        return Response(data={"success": "Article successfully deleted"})

    @action(methods=['get'], detail=False, url_path='(?P<pk>.+)/isapproved', permission_classes=[ArticlePermission])
    def getIsapproved(self, request, pk):
        """
        This function retrieves the status of an article in different communities with an accepted
        status.
        
        :param request: The request object contains information about the current HTTP request, such as
        the user making the request, the headers, and the request method
        :param pk: The `pk` parameter in the `getIsapproved` method represents the primary key of the
        article for which you want to retrieve the status in different communities with an accepted
        status
        :return: The response is a JSON object containing the success status and the communities where
        the article has been approved.
        """
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        response = CommunityMeta.objects.filter(article_id=pk)
        serializer = CommunityMetaApproveSerializer(data=response, many=True)
        serializer.is_valid()
        communities = serializer.data
        return Response(data={"success": communities})

    @action(methods=['post'],detail=False, url_path='(?P<pk>.+)/approve_for_review', permission_classes=[ArticlePermission])
    def approve_review(self, request, pk):
        """
        This function approves an article for the review process.
        
        :param request: The request object contains information about the HTTP request made to the API,
        such as the request method (POST in this case), headers, and body
        :param pk: The "pk" parameter in the URL pattern is used to capture the primary key of the
        article that needs to be approved for review. It is a placeholder that will be replaced with the
        actual primary key value when the URL is accessed
        :return: The code is returning a response with a success message indicating that the review
        process has started successfully.
        """
        member = Community.objects.filter(Community_name=request.data["community"]).first()
        request.data["community"] = member.id
        obj = self.get_object()
        serializer = self.get_serializer(obj,data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(data={"success":"review process started successfully"})
    
    @action(methods=['post'], detail=False, url_path='(?P<pk>.+)/publish', permission_classes=[ArticlePermission])
    def getPublished(self, request, pk):
        """
        This function selects a community for publication and updates the status of the article
        accordingly.
        
        :param request: The request object contains information about the current HTTP request, such as
        the headers, body, and user authentication details
        :param pk: The `pk` parameter is a placeholder for the primary key of the article. It is used to
        identify the specific article that is being published
        :return: The code is returning a response in the form of a JSON object. The specific content of
        the response depends on the conditions met in the code.
        """
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        data = request.data
        response = CommunityMeta.objects.filter(article_id=pk,community__Community_name=data["published"]).first()
        if response is None:
            return Response(data={"error": f'Article is not submitted to {data["published"]}'}) 
        if response.status == 'accepted':
            article = Article.objects.filter(id=pk).first() 
            article.published = data['published']
            article.save()
            response.status = data['status']
            response.save()
            return Response(data={"success": f"You have chosen {data['Community_name']} to publish your article"})
        else:
            return Response(data={"error": "Article is still not approved by community"})        

    @action(methods=['get'], detail=False, url_path='favourites', permission_classes=[ArticlePermission])
    def favourites(self, request):
        """
        The above function retrieves a list of articles that have been marked as favorites by the user
        and returns them in a serialized format.
        
        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the user making the request, the HTTP method used
        (GET, POST, etc.), and any data or parameters sent with the request
        :return: The code is returning a response with a JSON object containing the serialized data of
        the articles that are marked as favourites by the authenticated user. The serialized data
        includes the details of the articles such as title, content, author, etc.
        """
        favourites = Favourite.objects.filter(user=request.user).values_list('article', flat=True)
        posts = Article.objects.filter(id__in=favourites.all(),status="public")
        serializer = ArticlelistSerializer(posts, many=True, context={"request":request})
        return Response(data={"success":serializer.data})
        

    @action(methods=['post'],detail=False, url_path='(?P<pk>.+)/submit_article', permission_classes=[ArticlePermission])
    def submit_article(self, request, pk):
        """
        This function submits an article to different communities for reviewal process.
        
        :param request: The request object contains information about the current HTTP request, such as
        the request method, headers, and data
        :param pk: The `pk` parameter in the `submit_article` method represents the primary key of the
        object that the article is being submitted to. It is used to retrieve the object from the
        database and perform permission checks on it
        :return: The code is returning a response with a JSON object containing the key "success" and
        the value "Article submitted successfully for reviewal process!!!".
        """
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        data = request.data
        data['article_id']=pk
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(data={"success": "Article submited successfully for reviewal process!!!"})

    @action(methods=['put'], detail=False, url_path='(?P<pk>.+)/updateviews',permission_classes=[ArticlePermission])
    def updateViews(self, request, pk):
        """
        This function updates the number of views for an article.
        
        :param request: The `request` parameter is the HTTP request object that contains information
        about the current request, such as the headers, body, and user authentication details. It is
        passed to the view function or method when a request is made to the corresponding URL
        :param pk: The "pk" parameter in the above code refers to the primary key of the article object
        that needs to be updated. It is used to identify the specific article that needs to have its
        views incremented
        :return: The code is returning a response with a success message if the serializer is valid and
        the view count is successfully updated. If the serializer is not valid, it returns a response
        with the serializer errors and a status of HTTP 400 Bad Request.
        """
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = self.queryset.get(id=pk)
        serializer = ArticleViewsSerializer(response)
        article = serializer.data
        article['views'] += 1
        serializer = ArticleViewsSerializer(response, data=article)
        if serializer.is_valid():
            serializer.save() 
            return Response(data={"success": "Added a view to the article"})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        
    @action(methods=['post'],detail=False, url_path='(?P<pk>.+)/approve_article', permission_classes=[ArticlePermission])    
    def approve_article(self, request, pk):
        """
        This function is used by an admin to approve an article and select reviewers and moderators for
        a community.
        
        :param request: The request object contains information about the HTTP request made by the
        client, such as the headers, body, and method
        :param pk: The "pk" parameter is a regular expression pattern that matches any string of
        characters. It is used to capture the primary key (pk) of the article that needs to be approved
        :return: The response being returned is a JSON object with a "success" key and the value
        "article approved".
        """
        member = Community.objects.filter(Community_name=request.data["community"]).first()
        request.data["community"] = member.id
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        serializer = self.get_serializer(obj ,data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(data={"success":"article approved"})
    
    @action(methods=['post'], detail=False,url_path="favourite", permission_classes=[FavouritePermission])
    def favourite(self, request):
        """
        This function adds an article to a user's list of favorites if it is not already added.
        
        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, body,
        and user authentication details. In this code snippet, the `request` object is used to access
        the data sent
        :return: The code is returning a Response object with data indicating whether the favourite was
        successfully added or if it was already added to favourites. If the favourite was already added,
        the response will contain an error message. If the favourite was successfully added, the
        response will contain a success message.
        """
        post = Favourite.objects.filter(article_id=request.data["article"], user=request.user).first()
        if post is not None:
            return Response(data={"error":"Already added to Favourites!!!"})
        Favourite.objects.create(article_id=request.data["article"], user=request.user)
        return Response(data={"success":"Favourite added!!!"})

    @action(methods=['post'], detail=False,url_path="unfavourite", permission_classes=[FavouritePermission])
    def unfavourite(self, request):
        """
        The above function is a Django view that allows a user to unfavourite an article.
        
        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, body,
        and user authentication details. In this case, it is used to retrieve the data from the request
        body, specifically
        :return: The code is returning a Response object with either a success message ("Favourite
        Removed!!!") or an error message ("Favourite not found!!!").
        """
        member = Favourite.objects.filter(article_id=request.data["article"],user=request.user).first()
        if member is not None:
            member.delete()
            return Response(data={"success":"Favourite Removed!!!"})
        else:
            return Response(data={"error":"Favourite not found!!!"})
    
    @action(methods=['post'],detail=False, url_path='(?P<pk>.+)/reject_article', permission_classes=[ArticlePermission])    
    def reject_article(self, request, pk):
        """
        This function rejects an article by updating its status and returning a success message.
        
        :param request: The request object contains information about the HTTP request made by the
        client, such as the headers, body, and method
        :param pk: The `pk` parameter in the `reject_article` method represents the primary key of the
        article that is being rejected. It is used to identify the specific article that needs to be
        rejected
        :return: The response being returned is a JSON object with the key "success" and the value
        "article rejected".
        """
        member = Community.objects.filter(Community_name=request.data["community"]).first()
        request.data["community"] = member.id
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        serializer = self.get_serializer(obj ,data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(data={"success":"article rejected"})
    
    @action(methods=['post'],detail=False, url_path='(?P<pk>.+)/status', permission_classes=[ArticlePermission])
    def status(self, request, pk):
        """
        This function updates the status of an article based on the provided status value.
        
        :param request: The `request` parameter is an object that represents the HTTP request made by
        the client. It contains information such as the request method (e.g., GET, POST), headers, query
        parameters, and the request body
        :param pk: The "pk" parameter in the above code refers to the primary key of the article object.
        It is used to identify a specific article in the database
        :return: The code is returning a response object with the data and status code. If the "status"
        parameter is not provided in the request data, it will return a response with an error message
        and status code 400 (Bad Request). If the article with the given ID does not exist, it will
        return a response with an error message and status code 404 (Not Found). If the article status
        is
        """
        obj = self.get_object()
        self.check_object_permissions(request,obj)
        try:
            stat = request.data.get("status", None)
            if stat is None:
                return Response(data={"error":"status can't be None"}, status=status.HTTP_400_BAD_REQUEST)
                
            article = Article.objects.filter(id=pk).first()
            if article is None:
                return Response(data={"error":"article not exist"}, status=status.HTTP_404_NOT_FOUND)
            article.status = stat
            article.save()
            return Response(data={"success":f"article status changed to {stat}"})
        
        except Exception as e:
            return Response(data={"error":e}, status=status.HTTP_400_BAD_REQUEST)
    

      

