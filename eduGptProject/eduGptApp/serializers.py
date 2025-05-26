from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Student, School, SchoolClass, Teacher, Subject, Book, Chapter, ChatHeader, Chats, ChapterContent, QueryContext, TestQuestion, PushedMaterial, FeedBack


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = '__all__'

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['name']  # This serializer will only return the name of the subject.

class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = '__all__'

class SchoolClassSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    subjects = SubjectSerializer(many=True, read_only=True)  # Use the updated SubjectSerializer here

    class Meta:
        model = SchoolClass
        fields = ['id', 'designation', 'school_name', 'subjects', 'books']

class ChapterSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Chapter
        fields = '__all__'

class ChatHeaderSerializer(serializers.ModelSerializer):    
    class Meta:
        model = ChatHeader
        fields = '__all__'

class ChatSerializer(serializers.ModelSerializer):    
    class Meta:
        model = Chats
        fields = '__all__'

class ChapterContentSerializer(serializers.ModelSerializer):    
    class Meta:
        model = ChapterContent
        fields = '__all__'

class QueryContextSerializer(serializers.ModelSerializer):    
    class Meta:
        model = QueryContext
        fields = '__all__'

class TestQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestQuestion
        fields = '__all__'

class PushedMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushedMaterial
        fields = '__all__'


class TeacherSerializer(serializers.ModelSerializer):

    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    school= serializers.IntegerField(write_only=True)

    class Meta:
        model = Teacher
        fields = ('username', 'password', 'email', 'name', 'school', 'classesInfo')

    def create(self, validated_data):
        user_data = {
            'username': validated_data.pop('username'),
            'email': validated_data.pop('email'),
            'password': validated_data.pop('password'),
        }
        user = User.objects.create_user(**user_data)

        school_id = validated_data.pop('school')
        school = School.objects.get(id=school_id)

        teacher = Teacher.objects.create(user=user, school=school, **validated_data)
        return teacher

class StudentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    school = serializers.IntegerField(write_only=True)
    class_assigned = serializers.IntegerField(write_only=True)

    school_details = serializers.SerializerMethodField()
    class_assigned_details = SchoolClassSerializer(source='class_assigned', read_only=True)

    class Meta:
        model = Student
        fields = ('id', 'username', 'password', 'email', 'name', 'school', 'class_assigned',
                  'school_details', 'class_assigned_details')

    def get_school_details(self, obj):
        """
        Custom method to serialize school using SchoolSerializer.
        """
        if obj.school:
            return SchoolSerializer(obj.school).data
        return None

    def validate_school_id(self, value):
        try:
            School.objects.get(id=value)
        except School.DoesNotExist:
            raise serializers.ValidationError("School with the given ID does not exist.")
        return value

    def validate_class_assigned_id(self, value):
        try:
            SchoolClass.objects.get(id=value)
        except SchoolClass.DoesNotExist:
            raise serializers.ValidationError("SchoolClass with the given ID does not exist.")
        return value

    def create(self, validated_data):
        user_data = {
            'username': validated_data.pop('username'),
            'email': validated_data.pop('email'),
            'password': validated_data.pop('password'),
        }
        user = User.objects.create_user(**user_data)

        school = School.objects.get(id=validated_data.pop('school'))
        class_assigned = SchoolClass.objects.get(id=validated_data.pop('class_assigned'))

        student = Student.objects.create(
            user=user,
            school=school,
            class_assigned=class_assigned,
            **validated_data
        )
        return student
    
class FeedBackSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedBack
        fields = '__all__'