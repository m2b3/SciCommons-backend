import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, parsers, status, permissions
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response

from article.models import Article
from article.serializer.publish import ArticlePostPublishSerializer
from community.models import Community, CommunityMeta, CommunityMember, CommunityRequests
from community.permissions import CommunityPermission
from community.serializer.community import CommunitySerializer, CommunityCreateSerializer, CommunityListSerializer, \
    CommunityGetSerializer
from community.serializer.members import PromoteSerializer, CommunityMemberSerializer
from community.serializer.meta import CommunityMetaArticlesSerializer
from community.serializer.request import CommunityUpdateSerializer, JoinRequestSerializer, \
    CommunityRequestGetSerializer, ApproveRequestSerializer
from user.models import User, Subscribe
from user.serializer.subscription import SubscribeSerializer


# Create your views here.

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
        "create": CommunityCreateSerializer,
        "update": CommunityUpdateSerializer,
        "promote_member": PromoteSerializer,
        "addPublishedInfo": ArticlePostPublishSerializer,
        "getMembers": CommunityMemberSerializer,
        "getArticles": CommunityMetaArticlesSerializer,
        "list": CommunityListSerializer,
        "retrieve": CommunityGetSerializer,
        "join_request": JoinRequestSerializer,
        "get_requests": CommunityRequestGetSerializer,
        "approve_request": ApproveRequestSerializer,
        "subscribe": SubscribeSerializer,
        "unsubscribe": SubscribeSerializer,
        'mycommunity': CommunitySerializer,
    }

    def get_serializer_class(self):
        return self.action_serializers.get(self.action, self.serializer_class)

    def list(self, request):

        response = super(CommunityViewset, self).list(request)

        return Response(data={"success": response.data})

    def retrieve(self, request, Community_name):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        response = super(CommunityViewset, self).retrieve(request, Community_name=Community_name)

        return Response(data={"success": response.data})

    def create(self, request):

        member = self.queryset.filter(user=request.user).first()
        if member is not None:
            return Response(data={"error": "You already created a community.You can't create another community!!!"},
                            status=status.HTTP_400_BAD_REQUEST)
        super(CommunityViewset, self).create(request)

        return Response(data={"success": "Community successfully added"})

    def update(self, request, Community_name):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(data={"success": serializer.data})

    def destroy(self, request, Community_name):
        obj = self.get_object()
        self.check_object_permissions(request, obj)
        super(CommunityViewset, self).destroy(request, Community_name=Community_name)

        return Response(data={"success": "community successfully deleted"})

    @action(methods=['GET'], detail=False, url_path='(?P<Community_name>.+)/articles',
            permission_classes=[CommunityPermission])
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
        self.check_object_permissions(request, obj)
        response = self.queryset2.filter(community__Community_name=Community_name)
        serializer = CommunityMetaArticlesSerializer(data=response, many=True)
        serializer.is_valid()
        articles = serializer.data
        return Response(data={"success": articles})

    @action(methods=['get'], detail=False, url_path="mycommunity", permission_classes=[permissions.IsAuthenticated, ])
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
        member = CommunityMember.objects.filter(user=request.user, is_admin=True).first()
        instance = Community.objects.filter(id=member.community.id)
        serializer = CommunitySerializer(data=instance, many=True)
        serializer.is_valid()
        community = serializer.data
        return Response(data={"success": community[0]})

    @action(methods=['POST'], detail=False, url_path='(?P<Community_name>.+)/article/(?P<article_id>.+)/publish',
            permission_classes=[CommunityPermission])
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
        self.check_object_permissions(request, obj)
        article = Article.objects.filter(id=article_id).first()
        if (article.published != Community_name):
            return Response(data={"error": "This action can't be performed"})
        else:
            data = request.data
            article.license = data["license"]
            article.published_article_file = data["published_article_file"]
            article.doi = data["doi"]
            article.published_date = datetime.datetime.now()
            article.save()
            return Response(data={"success": "You added the license,Article file to the published Article"})

    @action(methods=['GET'], detail=False, url_path='(?P<Community_name>.+)/members',
            permission_classes=[CommunityPermission])
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
        self.check_object_permissions(request, obj)
        response = self.queryset3.filter(community=obj)
        serializer = self.get_serializer(data=response, many=True)
        serializer.is_valid()
        users = serializer.data
        return Response(data={"success": users})

    @action(methods=['POST'], detail=False, url_path='(?P<Community_name>.+)/promote_member',
            permission_classes=[CommunityPermission])
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
        self.check_object_permissions(request, obj)
        member = User.objects.filter(username=request.data["username"]).first()
        if member is None:
            return Response(data={"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        admin = Community.objects.filter(user_id=member.id).first()
        if admin is not None:
            return Response(data={"error": "You cant perform this action"}, status=status.HTTP_404_NOT_FOUND)
        request.data["user_id"] = member.id
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(data={"success": "member promoted successfully"})

    @action(methods=['DELETE'], detail=False, url_path='(?P<Community_name>.+)/remove_member/(?P<user_id>.+)',
            permission_classes=[CommunityPermission])
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
        self.check_object_permissions(request, obj)

        admin = Community.objects.filter(user_id=user_id).first()
        if admin is not None:
            return Response(data={"error": "You cant perform this action"}, status=status.HTTP_404_NOT_FOUND)

        try:
            member = CommunityMember.objects.filter(community=obj, user_id=user_id).first()
            emails = []
            emails.append(member.user.email)
            if member is None:
                return Response(data={"error": "Not member of community"}, status=status.HTTP_404_NOT_FOUND)
            member.delete()
            send_mail(f'you are removed from {obj}', f'You have been removed from {obj}.Due to inappropriate behaviour',
                      settings.EMAIL_HOST_USER, emails, fail_silently=False)


        except Exception as e:
            return Response(data={'error': 'unable to delete it.Please try again later!!!'},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response(data={"success": "member removed successfully"})

    @action(methods=['POST'], detail=False, url_path='(?P<Community_name>.+)/join_request',
            permission_classes=[CommunityPermission])
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

        return Response(data={"success": serializer.data})

    @action(methods=['GET'], detail=False, url_path='(?P<Community_name>.+)/get_requests',
            permission_classes=[CommunityPermission])
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

        return Response(data={"success": serializer.data})

    @action(methods=['POST'], detail=False, url_path='(?P<Community_name>.+)/approve_request',
            permission_classes=[CommunityPermission])
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

        if serializer.data['status'] == "approved":
            obj.members.add(serializer.data['user'])

        joinrequest.delete()

        return Response(data={"success": serializer.data})

    @action(methods=['post'], detail=False, url_path='(?P<Community_name>.+)/subscribe',
            permission_classes=[permissions.IsAuthenticated])
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
            return Response(data={"error": "Already Subscribed!!!"})
        instance = Community.objects.filter(Community_name=Community_name).first()
        Subscribe.objects.create(community=instance, user=request.user)
        return Response(data={"success": "Subscribed!!!"})

    @action(methods=['post'], detail=False, url_path='(?P<Community_name>.+)/unsubscribe',
            permission_classes=[permissions.IsAuthenticated])
    def unsubscribe(self, request, Community_name):
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
        member = Subscribe.objects.filter(community__Community_name=Community_name, user=request.user).first()
        if member is not None:
            member.delete()
            return Response(data={"success": "Unsubscribed!!!"})
        else:
            return Response(data={"error": "Did not Subscribe!!!"})
