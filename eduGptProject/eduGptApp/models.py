from django.db import models
from django.contrib.auth.models import User
from rest_framework import serializers
from django.utils.timezone import now
import time
import json
from pgvector.django import VectorField


class School(models.Model):
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    address = models.TextField()
    board = models.TextField()

    def __str__(self):
        return self.name

class Subject(models.Model):
    name = models.CharField(max_length=100)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='subjects')

    def __str__(self):
        return self.name
    
class Book(models.Model):
    name = models.CharField(max_length=255)
    publisher = models.CharField(max_length=255)
    link = models.URLField()
    subject = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class SchoolClass(models.Model):
    designation = models.CharField(max_length=10)  # Like '8-A', '8-B', etc.
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='classes')
    subjects = models.ManyToManyField(Subject, related_name='classes')
    books = models.JSONField()
    def __str__(self):
        return f"{self.school.name} - {self.designation}"


class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='teachers')
    classesInfo = models.JSONField()
    # Removed the password field because the User model already handles passwords

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='students')
    class_assigned = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='students')

    def __str__(self):
        return self.name

class Chapter(models.Model):
    name = models.CharField(max_length=255)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='book')
    assistant = models.JSONField(blank=True, null=True, max_length=1000)

    def __str__(self):
        return self.name


class ChatHeader(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    userId = models.IntegerField()
    name = models.CharField(max_length=100, default="hello")
    type = models.CharField(max_length=100)  # Student/Teacher
    category = models.CharField(max_length=100)  # Lecture Planner / Ask ..
    class_name = models.CharField(max_length=100, db_column='class')  # 'class' is a reserved word in Python, so use 'class_name' and specify the actual db column name to be 'class'
    subject = models.CharField(max_length=100)
    chapter = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp of creation
    created_at_text = models.CharField(max_length=30, blank=True, default='')  # For storing the textual date format
    created_at_unix = models.IntegerField(default=0)  # For storing the Unix timestamp
    threads = models.JSONField(max_length=1000)

    '''
        "threads": {
        "Ask Textbooks" : "asst_ESO9HMFgz4svsKAuAF5st2BW",
        "Teaching Methods Generator" : "asst_qNYY9zTGQ1tN8xajGOBS5VVT",
        "Lecture Planner" : "asst_FyV5STel5nmOpvGGHKZSt6d7",
        "Create Tests" : "asst_FyV5STel5nmOpvGGHKZSt6d7"
    }
    '''

    def save(self, *args, **kwargs):
        # If it's a new record, created_at would not be set yet, so we use 'now' as fallback
        date = self.created_at if self.created_at else now()
        self.created_at_text = date.strftime("%d %b, %Y")  # e.g., "24 Mar, 2024"
        self.created_at_unix = int(time.mktime(date.timetuple()))
        super().save(*args, **kwargs)

    
class Chats(models.Model):

    class QuestionType(models.TextChoices):
        SNIP = 'SNIP', 'snip'
        QUIZ = 'QUIZ', 'quiz'
        NORMAL_QUESTION = 'QUESTION', 'Question'

    user = models.JSONField() #question
    eduGpt = models.JSONField() #answer
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp of creation
    chat_header = models.ForeignKey(ChatHeader, on_delete=models.CASCADE, related_name='chats')
    referenceData = models.JSONField(default={})
    snipData = models.JSONField(default={})
    usedForRevision = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp of creation
    created_at_text = models.CharField(max_length=30, blank=True, default='')  # For storing the textual date format
    created_at_unix = models.IntegerField(default=0)  # For storing the Unix timestamp
    conceptCovered = models.TextField(null=True) # this field is used to know the area from which the student asked questions in the chapter from
    ques_type = models.CharField(
        max_length=200,
        choices=QuestionType.choices,
        default=QuestionType.QUIZ,
    )
    '''
    for Ask TextBook:
        user = {
        "question" : "sfdsfkd fds
        }
        eduGpt = {
        "answer" : "sdfsdlkfjdsfsdfkdfslksj df "
        }

    for Lecture Planner:
        user = {
        "teaching_methods" : ["sdfkjd", "sdfkjsdf"],
        "question" : "sdfkjdhf sdfh dkj dsj",
        }

        eduGpt = {
            "default" : {
                "answer" : "sfsdjfn fdskf djf sdjf "
            },
            "role play" : {
                "answer" : "sjfhs shf dsfh sjfdk"
            },
            "flow_chart" : {
                "nodes" : [1,2,4,5,8]
            }
        }
    '''

class FeedBack(models.Model):
    feedBack = models.JSONField(null=True)
    chatHeader = models.CharField(null=True)
    chat = models.ForeignKey(Chats, on_delete=models.CASCADE, related_name='chats')
    version = models.IntegerField(null=True)
    completed = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp of creation

class ChapterContent(models.Model):
    htmlString = models.TextField()
    page = models.IntegerField()
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='chapter')

class ChapterImages(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='snipChapter')
    snipImgUrl = models.TextField()
    snipImgName = models.CharField(max_length=300)
    description = models.TextField()
    relevantTextFromChapter = models.TextField()
    scale = models.FloatField()
    imgNum = models.IntegerField() 

#### Model for reference data

class ChapterReferenceData(models.Model):
    referenceData = models.JSONField() # to store the json of span id and text for highlighting purpose later
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='chapterReferenceData')

class ChapterReferenceText(models.Model):
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='chapter_reference_texts')
    chunk_text = models.TextField()  # Store the chunk of the chapter text
    metadata = models.TextField()
    embedding = VectorField(dimensions=1536)  # Adjust the dimension as necessary
    conceptName = models.TextField(null=True)

    def __str__(self):
        return f"Reference text for {self.chapter.name}"

# class ChapterReferenceText(models.Model):
#     referenceText = models.JSONField() # to store the json of span id and text for highlighting purpose later
#     chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name='chapterReferenceText')

#### Model for reference data


class QueryContext(models.Model):
    chatHeaderId = models.TextField()
    context = models.JSONField()
    snips = models.JSONField()
    query = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)  # Automatically set the field to now when the object is first created.

    def __str__(self):
        return f"QueryContext {self.id}"
    
class TestQuestion(models.Model):
    # Define the type of question, using choices for better validation
    QUESTION_TYPES = [
        ('MCQ', 'Multiple Choice Question'),
        ('LONG', 'Long Question'),
        ('SHORT', 'Short Question'),
    ]

    type = models.CharField(max_length=5, choices=QUESTION_TYPES)
    question_text = models.TextField()
    options = models.TextField(blank=True, null=True, help_text="For MCQs, store options as JSON.")
    marks = models.IntegerField()
    answer = models.TextField(blank=True, null=True)
    chapter = models.CharField(max_length=1000, blank=True, null=True)
    subject = models.CharField(max_length=1000, blank=True, null=True)
    standard = models.CharField(max_length=1000, blank=True, null=True)

    def set_options(self, options):
        """Stores options as a JSON string."""
        self.options = json.dumps(options)

    def get_options(self):
        """Retrieves options as a Python list after converting from JSON string."""
        return json.loads(self.options) if self.options else None

    def __str__(self):
        """String representation of the model, which helps in debugging."""
        return f"{self.get_type_display()} - {self.question_text[:50]}..."  # Shows type and truncates question text

    class Meta:
        verbose_name = "Test Question"
        verbose_name_plural = "Test Questions"

class Test(models.Model):
    name = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    class_field = models.CharField(max_length=50)  # 'class' is a reserved word in Python, hence 'class_field'
    subject = models.CharField(max_length=100)
    chapter = models.CharField(max_length=100)
    questions = models.ManyToManyField(TestQuestion, related_name='tests')

    def __str__(self):
        """String representation of the model, which helps in debugging."""
        return f"{self.name} - {self.subject} {self.chapter} ({self.class_field})"
    
class PushedMaterial(models.Model):
    content = models.JSONField()
    name = models.CharField(max_length=1000)