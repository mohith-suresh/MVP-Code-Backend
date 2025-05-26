from django.http import JsonResponse
from django.views import View
from eduGptApp.models import Chapter, ChapterContent, ChatHeader, Student, Chats
import random
import time
import math
from celery import shared_task
import sys
import os
from django.core.management import call_command
from openai import OpenAI
import uuid
from django.shortcuts import get_object_or_404
import json, re
import random
from .serializers import ChatSerializer
from .utils import check_or_create_chat_header, jsonFormat, getRevisionContent, generate_random_question_query, getTests, create_Revision_Data
from .models import ChatHeader


client = OpenAI(api_key='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')

@shared_task
def addRevision(data):
    check_or_create_chat_header(data)

@shared_task
def insertRevisionData():
    print("1111111111111")
    students = Student.objects.all()
    for s in students:
        chatHistory_SubjectWise = {}
        
        print("STUDENTS ARE",s.user_id)
        chat_headers = ChatHeader.objects.filter(userId=s.user_id)
        for ch_Headers in chat_headers:
            chatHistory = {}
            # Check if 'class' key exists in the dictionary
            if 'class' not in chatHistory_SubjectWise:
                # Create the 'class' key and assign it a specific value, e.g., a string
                chatHistory_SubjectWise['class'] = ch_Headers.class_name
                    
            chats = Chats.objects.filter(chat_header_id=ch_Headers.id)
            for chat in chats:
                if chat.ques_type == Chats.QuestionType.NORMAL_QUESTION:

                    if chat.conceptCovered not in chatHistory and not chat.usedForRevision:
                        concept = chat.conceptCovered
                        chatHistory[concept] = []
                        jsonData = {
                            "question": chat.user.get("question", ""),
                            "answer": chat.eduGpt.get("answer", "")
                        }
                        chatHistory[chat.conceptCovered].append(jsonData)
                        chat.usedForRevision = True
                        chat.save()  # Save the chat to update the usedForRevision flag

                        print("CHAT HISTORY IS 00000 ---->", chatHistory)
                    # print("THE JSON DATA IS", jsonData)
            print("CHAT HISTORY IS 1111---->", chatHistory)
            if ch_Headers.subject not in  chatHistory_SubjectWise:
                chatHistory_SubjectWise[ch_Headers.subject] = []
                chapterName = {
                        "chapter" : ch_Headers.chapter
                    }
                chatHistory_SubjectWise[ch_Headers.subject].append(chapterName)
                print("++++++++++++++++++++++", chatHistory_SubjectWise)
            if chatHistory:  # Only append if chatHistory is not empty

                    chatHistory_SubjectWise[ch_Headers.subject].append(chatHistory) 
            else :
                    chatHistory_SubjectWise = {}

        print("[[[[[]]]]]", chatHistory)
        print("((((((()))))))", chatHistory_SubjectWise)

        if chatHistory_SubjectWise:
            create_Revision_Data(chatHistory_SubjectWise, s.user_id)

@shared_task(bind=True, default_retry_delay=30 * 60, max_retries=3)
def addThreadsToChatHeader(self, chatHeaderId):
    try:
        # List of thread names
        print("HELOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOoo")
        thread_names = [
            "Ask Textbooks", 
            "Teaching Methods Generator", 
            "Lecture Planner", 
            "Create Tests", 
            "Column", 
            "AI_Tutor", 
            "Feedback", 
            "Reference"
        ]

        # Dictionary to hold thread IDs
        threadData = {}

        # Loop over the thread names and create threads
        for thread_name in thread_names:
            thread = client.beta.threads.create()
            thread_id = thread.id  # Assuming 'id' is the attribute holding the thread_id
            threadData[thread_name] = thread_id

        # Update the ChatHeader instance with the thread data
        chat_header = ChatHeader.objects.get(id=chatHeaderId)
        chat_header.threads = threadData
        chat_header.save()
    except Exception as exc:
        self.retry(exc=exc)

# threadData now contains the thread IDs mapped to their names


#start worker --> celery -A tgBot worker -l info
#start beat --> celery -A tgBot beat -l info
# celery -A eduGptProject worker --loglevel=info -Q high_priority,default

# purge all queries --> celery -A your_project_name purge
# Purge Specific Queue --> celery -A your_project_name -Q high_priority purge
# starting flower --> celery -A your_project_name flower
 

'''
# Worker 1: Listening to high_priority and default queues
celery -A your_project_name worker --loglevel=info -Q high_priority,default --hostname=worker1@%h &

# Worker 2: Listening to high_priority queue only
celery -A your_project_name worker --loglevel=info -Q high_priority --hostname=worker2@%h &

# Worker 3: Listening to default queue only
celery -A your_project_name worker --loglevel=info -Q default --hostname=worker3@%h &

--loglevel=info: Sets the logging level to info.
-Q high_priority,default: Specifies the queues the worker will listen to.
--hostname=workerX@%h: Assigns a unique hostname to each worker to differentiate them.

'''

'''

Configuring Worker Concurrency
To configure the concurrency level (number of worker threads/processes), use the --concurrency option:

celery -A your_project_name worker --loglevel=info -Q high_priority,default --hostname=worker1@%h --concurrency=4 &
celery -A your_project_name worker --loglevel=info -Q high_priority --hostname=worker2@%h --concurrency=4 &
celery -A your_project_name worker --loglevel=info -Q default --hostname=worker3@%h --concurrency=4 &


'''