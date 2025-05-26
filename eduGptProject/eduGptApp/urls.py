from django.urls import path
from . import views

urlpatterns = [

    path('dummyData', views.dummyData, name='dummyData'),

    path('school', views.school_list, name='school_list'),
    path('updateSchool', views.update_school, name='update_school'),
    path('subject', views.subject_list, name='subject_list'),

    path('addBook', views.addBook, name='addBook'),
    path('book', views.book_list, name='book_list'),

    path('schoolClass', views.school_class_list, name='school_class_list'),

    path('teacher', views.teacher_list, name='teacher_list'),
    path('registerTeacher', views.registerTeacher, name='registerTeacher'),
    path('verifyTeacher', views.check_user_teacher, name='check_user_teacher'),
    path('updateTeacher', views.update_teacher, name='teacher_list'),

    path('student', views.student_list, name='student_list'),
    path('registerStudent', views.registerStudent, name='registerStudent'),
    path('verifyStudent', views.check_user_student, name='check_user_student'),
    path('updateStudent', views.update_student, name='update_student'),

    path('addChapter', views.addChapter, name='addChapter'),
    path('chapter', views.chapter_list, name='chapter_list'),

    path('chatHeader', views.chat_header_list, name='chat_header_list'),
    path('deleteChatHeader', views.chat_header_delete, name='chat_header_delete'),
    path('updateChatHeader', views.chat_header_update, name='chat_header_update'),

    path('chat', views.chats_list_create, name='chats_list_create'),

    path('getChapterContent', views.chapter_content_list, name='chapter_content_list'),
    path('getChapterPagesNum', views.chapter_pages_num, name='chapter_pages_num'),

    path('gpt', views.gpt, name='gpt'),

    path('queryContext', views.query_context_create, name='queryContext'),

    path('questions', views.get_questions, name='get_questions'),
    path('questions/new', views.post_question, name='post_question'),

    path('create/test', views.create_test, name='create_test'),

    path('getPushedMaterial', views.get_pushed_material, name='get_pushed_material'),

    path('getFeedBack', views.get_feedback, name='get_feedback')
]