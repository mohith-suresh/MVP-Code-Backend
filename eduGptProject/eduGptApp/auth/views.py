from django.http import JsonResponse
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.core.exceptions import ObjectDoesNotExist


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username

        # Check if the user is linked to a Teacher or Student model
        try:
            teacher = user.teacher
            token['type'] = 'Teacher'
            token['school_id'] = teacher.school.id  # Include the school_id in the token

        except ObjectDoesNotExist:
            try:
                student = user.student
                token['type'] = 'Student'
                token['school_id'] = student.school.id  # Include the school_id in the token

            except ObjectDoesNotExist:
                token['type'] = 'Unknown'

        return token


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer
