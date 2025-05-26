from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .serializers import SchoolSerializer, SubjectSerializer, SchoolClassSerializer, TeacherSerializer, BookSerializer, StudentSerializer, ChapterSerializer, ChatHeaderSerializer, ChatSerializer, ChapterContentSerializer, QueryContextSerializer, TestQuestionSerializer, PushedMaterialSerializer, FeedBackSerializer
from .models import School, Subject, SchoolClass, Teacher, Book, Student, User, Chapter, ChatHeader, Chats, ChapterContent, QueryContext, TestQuestion, PushedMaterial, FeedBack
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import authenticate
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Max
from openai import OpenAI
import time
import uuid
from .tasks import addRevision, addThreadsToChatHeader

client = OpenAI(api_key='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')

@csrf_exempt
@api_view(['GET'])
def dummyData(request):

    # text="\n\n # Heading One\n\nThis is a paragraph with *emphasis* and **strong emphasis**.\n\n## Heading Two\n\n1. List item one\n2. List item two\n3. List item three"

    text = '''

# Heading One

This is a paragraph with *emphasis* and **strong emphasis**.

## 4. Heading Two

1. List item one
2. List item two
3. List item three

### Code Block

```js

const components = {
    // Override how code blocks are rendered to apply syntax highlighting
    code: ({ node, inline, className, children, ...props }) => {
        if (!children || typeof children !== 'string') {
            // If children is not provided or not a string, return regular <code> element
            return inline ? <code>{children}</code> : <pre><code>{children}</code></pre>;
        }

        const language = className ? className.replace("language-", "") : "";
        const highlightedCode = hljs.highlightAuto(children.trim(), [language]).value;
        return <pre><code  dangerouslySetInnerHTML={{ __html: highlightedCode }} /></pre>;
    }
};
```

### Math Equations


Here is an inline LaTeX equation: $E=mc^2$.

And here is a block LaTeX equation:

$$
x = \\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}
$$

```js

const components = {
    // Override how code blocks are rendered to apply syntax highlighting
    code: ({ node, inline, className, children, ...props }) => {
        if (!children || typeof children !== 'string') {
            // If children is not provided or not a string, return regular <code> element
            return inline ? <code>{children}</code> : <pre><code>{children}</code></pre>;
        }

        const language = className ? className.replace("language-", "") : "";
        const highlightedCode = hljs.highlightAuto(children.trim(), [language]).value;
        return <pre><code  dangerouslySetInnerHTML={{ __html: highlightedCode }} /></pre>;
    }
};
```

### Table

| Column 1 Header | Column 2 Header |
| --------------- | --------------- |
| Row 1, Cell 1  asjash hask sak,h as,k js | Row 1, Cell 2   |
| Row 2, Cell 1   | Row 2, Cell 2   |
| Row 3, Cell 1   | Row 3, Cell 2   |


| 📅 Date | 🏷️ Tag | 📝 Description |
| ------ | ------ | -------------- |
| 2024-04-02 | Info | Sample entry |

```

### Math Equations


Here is an inline LaTeX equation: $E=mc^2$.

And here is a block LaTeX equation:
```


$$
x = \\frac{-b \pm \sqrt{b^2-4ac}}{2a} \\

x = \\frac{-b \pm \sqrt{b^2-4ac}}{2a}
$$



'''

    if(request.method == 'GET'):
        return JsonResponse({"data": text})

@csrf_exempt
@api_view(['GET', 'POST'])
def school_list(request):
    # Fetch the school_name from query parameters
        # return JsonResponse({'message': 'Test response'})

    school_name  = request.query_params.get('school')
    all  = request.query_params.get('all')


    if school_name is not None:
        if request.method == 'GET':
            try:
                school = School.objects.get(name=school_name)
                serializer = SchoolSerializer(school)
                return Response(serializer.data)
            except School.DoesNotExist:
                return Response({'message': 'School not found'}, status=status.HTTP_404_NOT_FOUND)
            
    elif all is not None:
        if request.method == 'GET':
            schools = School.objects.all()
            serializer = SchoolSerializer(schools, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            serializer = SchoolSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@csrf_exempt
@api_view(['PUT', 'DELETE'])
def update_school(request):
    # Fetch the school_name from query parameters
    school_name = request.query_params.get('school')
    if not school_name:
        return Response({'message': 'Missing school_name query parameter'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        school = School.objects.get(name=school_name)
    except School.DoesNotExist:
        return Response({'message': 'School not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PUT':
        serializer = SchoolSerializer(school, data=request.data, partial=True)  # Allow partial updates
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        school.delete()
        return Response({'message': 'School deleted successfully'}, status=status.HTTP_204_NO_CONTENT)

@csrf_exempt
@api_view(['GET', 'POST'])
def subject_list(request):

    school_name  = request.query_params.get('school')

    if school_name is not None:
        if request.method == 'GET':
            try:
                subjects = Subject.objects.filter(school__name=school_name)
                if subjects.exists():
                    # Serialize the subject queryset
                    serializer = SubjectSerializer(subjects, many=True)
                    return Response(serializer.data)
                else:
                    # If no subjects found for the given school name
                    return Response({'message': 'No subjects found for the specified school'}, status=status.HTTP_404_NOT_FOUND)
            except Subject.DoesNotExist:
                return Response({'message': 'Subject not found'}, status=status.HTTP_404_NOT_FOUND)


    if request.method == 'GET':
        subjects = Subject.objects.all()
        serializer = SubjectSerializer(subjects, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = SubjectSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@csrf_exempt
@api_view(['GET', 'POST'])
def school_class_list(request):

    school_name  = request.query_params.get('school')
    class_designation = request.query_params.get('class')  # Get class designation from query params

    if school_name and class_designation:
        try:
            school_class = SchoolClass.objects.get(school__name=school_name, designation=class_designation)
            # Now, serialize the subjects associated with this class
            # subjects = school_class.subjects.all()
            # serializer = SubjectSerializer(subjects, many=True)
            serializer = SchoolClassSerializer(school_class)
            return Response(serializer.data)
        except SchoolClass.DoesNotExist:
            return Response({'message': 'No class found for the specified school and designation'}, status=status.HTTP_404_NOT_FOUND)


    elif school_name is not None:
        if request.method == 'GET':
            try:
                schoolClass = SchoolClass.objects.filter(school__name=school_name)
                if schoolClass.exists():
                    # Serialize the subject queryset
                    serializer = SchoolClassSerializer(schoolClass, many=True)
                    return Response(serializer.data)
                else:
                    # If no subjects found for the given school name
                    return Response({'message': 'No class found for the specified school'}, status=status.HTTP_404_NOT_FOUND)
            except SchoolClass.DoesNotExist:
                return Response({'message': 'School not found'}, status=status.HTTP_404_NOT_FOUND)
            
    else :
        if request.method == 'GET':
            school_classes = SchoolClass.objects.all()
            serializer = SchoolClassSerializer(school_classes, many=True)
            return Response(serializer.data)
        elif request.method == 'POST':
            serializer = SchoolClassSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt       
@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def teacher_list(request):
    username = request.query_params.get('username')
    
    if username:
        teachers = Teacher.objects.filter(user__username=username)
    else:
        # If no username is provided, return all teachers
        teachers = Teacher.objects.all()

    serializer = TeacherSerializer(teachers, many=True)
    return Response(serializer.data)

@csrf_exempt       
@api_view(['POST'])
def registerTeacher(request):
    if request.method == 'POST':
        serializer = TeacherSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt        
@api_view(['POST'])
def check_user_teacher(request):
    # Extract username and password from request.data
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    # Use Django's authenticate method to verify username and password
    user = authenticate(username=username, password=password)
    if user is not None:
        # The credentials are valid, now check if the user is a teacher
        try:
            teacher = Teacher.objects.get(user=user)
            # If the above line does not raise an exception, the user is a teacher
            return Response({"message": "User exists", "Type": "Teacher"}, status=status.HTTP_200_OK)
        except Teacher.DoesNotExist:
            # The user exists but is not a teacher
            return Response({"error": "User is not a teacher."}, status=status.HTTP_200_OK)
    else:
        # The credentials are invalid
        return Response({"error": "Invalid username or password."}, status=status.HTTP_404_NOT_FOUND)
    
@csrf_exempt
@api_view(['PUT'])
def update_teacher(request):
    if request.method == 'PUT':
        serializer = TeacherSerializer(data=request.data, partial=True)  # Allow partial updates
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt       
@api_view(['POST'])
def addBook(request):
    if request.method == 'POST':
        serializer = BookSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt       
@api_view(['GET', 'POST'])
def book_list(request):
    if request.method == 'GET':
        books = Book.objects.all()
        serializer = BookSerializer(books, many=True)
        return Response(serializer.data)

    

@csrf_exempt       
@api_view(['GET'])
# @permission_classes([IsAuthenticated])
def student_list(request):
    if request.method == 'GET':

        username = request.query_params.get('username')

        if username:
            students = Student.objects.filter(user__username=username)
        else:
            # If no username is provided, return all teachers
            students = Student.objects.all()
            
        serializer = StudentSerializer(students, many=True)
        return Response(serializer.data)
    
@csrf_exempt       
@api_view(['POST'])
def registerStudent(request):
    if request.method == 'POST':
        serializer = StudentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@csrf_exempt        
@api_view(['POST'])
def check_user_student(request):
    # Extract username and password from request.data
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    # Use Django's authenticate method to verify username and password
    user = authenticate(username=username, password=password)
    if user is not None:
        # The credentials are valid, now check if the user is a teacher
        try:
            teacher = Student.objects.get(user=user)
            # If the above line does not raise an exception, the user is a teacher
            return Response({"message": "User exists", "Type": "Student"}, status=status.HTTP_200_OK)
        except Student.DoesNotExist:
            # The user exists but is not a teacher
            return Response({"error": "User is not a student."}, status=status.HTTP_404_NOT_FOUND)
    else:
        # The credentials are invalid
        return Response({"error": "Invalid username or password."}, status=status.HTTP_404_NOT_FOUND)
    
@csrf_exempt
@api_view(['PUT'])
def update_student(request):
    if request.method == 'PUT':
        serializer = StudentSerializer(data=request.data, partial=True)  # Allow partial updates
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@csrf_exempt       
@api_view(['POST'])
def addChapter(request):
    if request.method == 'POST':
        serializer = ChapterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
def chapter_list(request):
    schoolId = request.query_params.get('schoolId')
    standard = request.query_params.get('standard')
    subject_name = request.query_params.get('subject')

    if schoolId and standard and subject_name:
        # Find the subject ID based on the provided subject name and school ID
        try:
            subject = Subject.objects.get(name=subject_name, school_id=schoolId)
        except Subject.DoesNotExist:
            return JsonResponse({"error": f"Subject named '{subject_name}' not found in school ID {schoolId}."}, status=404)
        
        # Filter SchoolClass by school and designation
        school_classes = SchoolClass.objects.filter(school_id=schoolId, designation=standard).distinct()

        classes_info = []
        for school_class in school_classes:
            # Get the book ID from the 'books' JSONField using the subject ID
            book_id = school_class.books.get(str(subject.id))
            
            chapters_info = []
            if book_id:
                # Retrieve all chapters related to the book ID
                chapters = Chapter.objects.filter(book_id=book_id)
                chapters_info = [{"id": chapter.id, "name": chapter.name} for chapter in chapters]

            classes_info.append({
                "designation": school_class.designation,
                "subject": subject_name,
                "book_id": book_id,
                "chapters": chapters_info if chapters_info else "No chapters found for this book."
            })

        return JsonResponse({"classes": classes_info})
    
    else :
        chapters = Chapter.objects.all()
        serializer = StudentSerializer(chapters, many=True)
        return Response(serializer.data)

    return JsonResponse({"error": "Missing parameters."}, status=400)
    

@api_view(['GET', 'POST'])
def chat_header_list(request):
    # Handle GET request: List all chat headers with optional filtering and pagination
    if request.method == 'GET':
        # Define allowed filter keys based on query parameters
        allowed_filters = ['type', 'category', 'class_name', 'subject', 'chapter', 'userId']
        
        # Dynamically build a dictionary of filters from query parameters
        filters = {key: value for key, value in request.query_params.items() if key in allowed_filters}

        # Apply filters to the queryset
        chat_headers = ChatHeader.objects.filter(**filters).order_by('-created_at')

        print(request.query_params.get('_page'), "====", request.query_params.get('_per_page'))

        # Pagination
        # Get pagination parameters with default values if not provided
        page_number = int(request.query_params.get('_page', 1))  # Default to page 1 if not specified
        per_page = int(request.query_params.get('_per_page', 13))  # Default to 13 items per page if not specified
        
        # Create Paginator object
        paginator = Paginator(chat_headers, per_page)
        
        # Get the page
        try:
            chat_headers_page = paginator.page(page_number)
        except:
            # If the page is out of range (e.g., too high), return an empty list
            chat_headers_page = []
        
        # Serialize and return the paginated queryset
        serializer = ChatHeaderSerializer(chat_headers_page, many=True)
        return Response(serializer.data)

    # Handle POST request: Create a new chat header
    elif request.method == 'POST':
        data = request.data.copy()  # Create a mutable copy of the data
        data['threads'] = {}  # Add the thread_id to the data

        serializer = ChatHeaderSerializer(data=data)
        if serializer.is_valid():
            chat_header = serializer.save()

            # Trigger the Celery task to create threads and push to high-priority queue
            # addThreadsToChatHeader.delay(chat_header.id)

            addThreadsToChatHeader.apply_async(args=[chat_header.id], queue='high_priority')


            # Trigger the Celery task to add a revision
            # addRevision.delay(serializer.data)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['DELETE'])
def chat_header_delete(request):

    ChatHeaderId = request.query_params.get('id')

    try:
        chat_header = ChatHeader.objects.get(pk=ChatHeaderId)
    except ChatHeader.DoesNotExist:
        return Response({'error': f'ChatHeader with id={ChatHeaderId} not found.'}, status=status.HTTP_404_NOT_FOUND)

    chat_header.delete()
    return Response({'message': f'ChatHeader with id={ChatHeaderId} has been deleted.'}, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
def chat_header_update(request):
    # Retrieve query parameters
    chat_header_id = request.query_params.get('id')
    name = request.query_params.get('name')

    # Find the ChatHeader instance
    try:
        chat_header = ChatHeader.objects.get(pk=chat_header_id)
    except ChatHeader.DoesNotExist:
        return Response({'error': 'ChatHeader not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Optionally update the name if provided
    if name:
        chat_header.name = name

    # For simplicity, use request.data for other updates, assuming it's a dictionary of fields to update.
    # This example assumes the request.data contains valid fields for the ChatHeader model.
    # For a PUT request, you might want to ensure all fields are provided or set default values.
    # For a PATCH request, partial updates are acceptable.
    serializer = ChatHeaderSerializer(chat_header, data=request.data, partial=(request.method == 'PATCH'))
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
def chats_list_create(request):
    """
    Retrieve all chats for a given ChatHeader id or create a new chat under it.
    """

    chat_header_id = request.query_params.get('id')

    if request.method == 'GET':
        chat_header = get_object_or_404(ChatHeader, pk=chat_header_id)
        chats = Chats.objects.filter(chat_header=chat_header).order_by('created_at')
        serializer = ChatSerializer(chats, many=True)
        return Response(serializer.data)

    if request.method == 'POST':
        serializer = ChatSerializer(data=request.data)
        if serializer.is_valid():
            # Ensure the new chat is associated with our chat_header
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@api_view(['GET'])
def chapter_content_list(request):
    """
    Retrieve chapter content for a given Chapter id and optional page number.
    """
    # Fetching the 'id' of the Chapter and 'page' number if provided
    chapter_id = request.query_params.get('id')
    page_number = request.query_params.get('page', None)  # 'page' is optional

    if request.method == 'GET':
        if chapter_id is not None:
            # Get the Chapter object, or return 404 if not found
            chapter = get_object_or_404(Chapter, pk=chapter_id)

            # If a 'page' number is provided, filter by it, otherwise, get all contents for the chapter
            if page_number is not None:
                chapterContents = ChapterContent.objects.filter(chapter=chapter, page=page_number)
            else:
                chapterContents = ChapterContent.objects.filter(chapter=chapter)

            # Serialize the chapter contents
            serializer = ChapterContentSerializer(chapterContents, many=True)
            return Response(serializer.data)
        else:
            # If no specific chapter_id is provided, return an error message
            return Response({"error": "Chapter id is required"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def chapter_pages_num(request):
    '''
    Retrieve the highest page number in a chapter.
    '''
    chapter_id = request.query_params.get('id')

    if not chapter_id:
        return Response({"error": "Chapter id is required"}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'GET':
        # Aggregate to find the maximum page number for the given chapter
        max_page = ChapterContent.objects.filter(chapter_id=chapter_id).aggregate(Max('page'))

        max_page_number = max_page.get('page__max')  # This will be None if no pages are found

        if max_page_number is None:
            return Response({"error": "No pages found for the given chapter"}, status=status.HTTP_404_NOT_FOUND)

        return Response({"max_page_number": max_page_number})
    
@api_view(['GET'])
def gpt(request):
    # Retrieve 'id' from the query parameters
    chat_header_id = request.query_params.get('id')
    query = request.query_params.get('query')
    
    if not chat_header_id:
        # If no 'id' is provided in the query parameters, return a 400 Bad Request
        return Response({'error': 'No id provided'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Fetch the corresponding ChatHeader object using the provided id
        chat_header = ChatHeader.objects.get(pk=chat_header_id)
    except ChatHeader.DoesNotExist:
        # If the ChatHeader with the provided id does not exist, return a 404 Not Found
        return Response({'error': 'ChatHeader not found'}, status=status.HTTP_404_NOT_FOUND)

    # Assuming 'thread_id' is an attribute of ChatHeader
    thread_id = chat_header.thread_id

    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=query,
    )

    chapter = get_object_or_404(Chapter, name=chat_header.chapter)
    assistant_id = chapter.assistant_id

    # Run the assistant
    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )

    # Wait for completion
    while run.status != "completed":
        # Be nice to the API
        time.sleep(0.5)
        run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)

    # Retrieve the Messages
    messages = client.beta.threads.messages.list(thread_id=thread_id)
    new_message = messages.data[0].content[0].text.value
    print(f"Generated message: {new_message}")
    
    # Continue with your logic, for now, let's just return the thread_id
    return Response({'message': new_message}, status=status.HTTP_200_OK)

@api_view(['POST'])
def query_context_create(request):
    if request.method == 'POST':
        serializer = QueryContextSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@api_view(['GET'])
def get_questions(request):
    """
    Retrieve all test questions.
    """
    if request.method == 'GET':
        questions = TestQuestion.objects.all()
        serializer = TestQuestionSerializer(questions, many=True)
        return JsonResponse(serializer.data, safe=False)

@api_view(['POST'])
def post_question(request):
    """
    Create a new test question.
    """
    if request.method == 'POST':
        # Using request.data instead of parsing JSON manually
        serializer = TestQuestionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(['POST'])
def create_test(request):
    if request.method == 'POST':
        if(request.data):
            print("Test data is" ,request.data)
            ## extract the answers
        
        serializer = PushedMaterialSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({'status': 'running'}, status=status.HTTP_201_CREATED)
        
@api_view(['GET'])
def get_pushed_material(request):
    if request.method == 'GET':
        materials = PushedMaterial.objects.all()
        serializer = PushedMaterialSerializer(materials, many=True)
        return JsonResponse(serializer.data, safe=False)

@api_view(['GET'])
def get_feedback(request):
    chat_header_id = request.query_params.get('chatHeaderId')
    chat_convo_id = request.query_params.get('chatId')

    # Filtering the FeedBack objects based on the provided parameters
    feedback = FeedBack.objects.all()
    if chat_header_id:
        feedback = feedback.filter(chatHeader=chat_header_id)
    if chat_convo_id:
        feedback = feedback.filter(chat_id=chat_convo_id)
        
    serializer = FeedBackSerializer(feedback, many=True)
    return JsonResponse(serializer.data, safe=False)