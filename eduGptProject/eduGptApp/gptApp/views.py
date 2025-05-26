from django.http import StreamingHttpResponse
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import AllowAny
from eduGptApp.gptApp.server_sent_event_renderer import ServerSentEventRenderer
from openai import OpenAI, AssistantEventHandler
import time
from eduGptApp.serializers import FeedBackSerializer
from eduGptApp.dataServing.embeddings import getAnswer
from rest_framework.response import Response
from rest_framework import status
import re
from eduGptApp.models import Chapter, ChatHeader, QueryContext, TestQuestion, ChapterImages, FeedBack, Chats
from django.shortcuts import get_object_or_404
from typing_extensions import override

from queue import Queue, Empty
from threading import Thread, Event
import logging
import urllib.parse
import json
import asyncio
import random
from django.http import JsonResponse
from eduGptApp.utils import replace_newlines, extract_json_from_text, decode_json_from_url, get_latest_query_context, extract_context_and_query, delete_all_query_context_entries, getTeachingMethods, contains_column, filter_questions, remove_column_related_text, parse_question_counts, generate_question_json_template, detect_quiz_length_and_keyword_presence, generate_random_question_query, getColumnTypeQuestionS, getTests, extract_feedback_and_marks, getReferenceTextSpanId, getReferenceText, get_Reference_Text, imgDetailsGpt, print_all_messages_from_queue, get_next_id
from django.db.models import Max


client = OpenAI(api_key='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')

# Get an instance of a logger
logger = logging.getLogger('django')


# Configure logging
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@api_view(['GET'])
@permission_classes([AllowAny])
@renderer_classes([ServerSentEventRenderer])
def gptStream(request):


    chat_header_id = request.query_params.get('id')
    query = request.query_params.get('query')

    initialQuery = query

    try:
        # Fetch the corresponding ChatHeader object using the provided id
        chat_header = ChatHeader.objects.get(pk=chat_header_id)
    except ChatHeader.DoesNotExist:
        # If the ChatHeader with the provided id does not exist, return a 404 Not Found
        return Response({'error': 'ChatHeader not found'}, status=status.HTTP_404_NOT_FOUND)
    
    chapter = get_object_or_404(Chapter, name=chat_header.chapter)

    print("000000000000000", chat_header_id)
    print("11111111111111111111", query)

    logger.info("Chat Header id is %s",chat_header_id)
    print("IIIIIIIIIIIIIIII",extract_context_and_query(chat_header_id))

    context, Query, snips = extract_context_and_query(chat_header_id)
    snipContext = ''

    print("THE SNIPS ARE BRO ::::::::::::::::;", type(snips), "------------", snips.keys(), "------", len(snips.keys()))

    snipThreads = {}

    # Fetch the Chapter instance using the chapter name from the ChatHeader
    chapter = get_object_or_404(Chapter, name=chat_header.chapter)
    chapterName = chapter.name
    # Iterate over the keys in the snips dictionary and create threads
    for key, details_list in snips.items():
        print("||||||||||||||||",key)
        # Filter ChapterImages by the Chapter instance and snipImgName
        chapter_images = ChapterImages.objects.filter(chapter=chapter, snipImgName=key)
        print("LLLLLLLLLLLLLLL", chapter_images[0])

        # Iterate over each element in the details list
        for i, details in enumerate(details_list):
            # Extract imgData from the details
            original_base64 = chapter_images[0].snipImgUrl
            snip_base64 = details['imgData']
            snip_scale_factor = details["multiplier"]
            original_scale_factor = chapter_images[0].scale
            imgDescription = chapter_images[0].description
            imgNum = chapter_images[0].imgNum
            
            # Create and start a new thread
            thread_name = f'imgThread_{key}_{i}'
            queueName = f'imgThread_{key}_{i}'
            queueSnip = Queue()
            thread = Thread(target=imgDetailsGpt, args=(original_base64, snip_base64, snip_scale_factor, original_scale_factor, imgDescription, imgNum, queueSnip))
            thread.start()
            
            # Store the thread in the dictionary with the key as part of the name
            snipThreads[thread_name] = {"thread" : thread, "queue" : queueSnip, "imgNum": imgNum}
        
    print("THE THREADS UNDER EXECUTION ARE BRO_____------>", snipThreads)

    # Wait for all threads to finish
    for thread_info in snipThreads.values():
        thread_info['thread'].join()

    # Iterate over the snipThreads dictionary and print thread and queue details
    for key, values in snipThreads.items():
        # print(values['thread'], "--------")
        # # Print messages in the queue
        # print(f"Messages in queue for {key}:")
        snipMssg = print_all_messages_from_queue(values['queue'])
        snipImgNum = values['imgNum']

        snipContext = snipContext + '\n' + f'''
        Given the {snipImgNum}th image in the chapter {chapterName} \n
        There was a snip taken on this image.\n
        The details of snip on the {snipImgNum}th image in the chapter {chapterName} are: \n
        {snipMssg}
        '''

    if snipContext != '':
        snipCotxMsg = f'''
        \nSnip Images context : \n
        There is also snip of images from the chapter {chapterName} taken.\n
        The context of those snips on the images of the chapter {chapterName} are:\n
        {snipContext}
        '''
        print("The Context is )))))",  context, "==========", type(context))

        new_entry = {"id": len(context), "textContent": snipCotxMsg}
        context.append(new_entry)
        print("THE CONTEXT IS :::)))))))))))))", context)

    if not snips:
        print("The dictionary is empty")
    else:
        print("The dictionary is not empty")

    if not chat_header_id:
        # If no 'id' is provided in the query parameters, return a 400 Bad Request
        return Response({'error': 'No id provided'}, status=status.HTTP_400_BAD_REQUEST)

    print("Chat header is", chat_header.id)

    thread_id = None
    message = None
    assistant_id = None
    tests = None

    numOfQuizDemandedByStudent, hasKeywordQuiz = detect_quiz_length_and_keyword_presence(query)

    print(":::::::::::::::::::::::::::::::", numOfQuizDemandedByStudent)

    if hasKeywordQuiz == True:
        column_type_data = {}
        query_01 = ''
        queryCounts = parse_question_counts(query)
        if queryCounts['long'] + queryCounts['short'] + queryCounts['mcq'] + queryCounts['fill'] == 0:

            numOfColumnQuestion = 0
            numOfColumnQuestion, wanted = contains_column(query)
            if wanted and numOfColumnQuestion > 0:  
                print("333333333333333333333333", numOfColumnQuestion)
                preQues  = f"Generate {numOfColumnQuestion} column type question based on the following query \n"
                query_01= preQues + query

            
            elif numOfQuizDemandedByStudent > 0:
                print("4444444444444444444", numOfQuizDemandedByStudent)
                query_01 = generate_random_question_query(numOfQuizDemandedByStudent)
            elif numOfQuizDemandedByStudent == 0 :
                print("7777777777777777777777777", numOfQuizDemandedByStudent)
                query_01 = generate_random_question_query(5)
                
            print("[[[[[[[[[[[[[",query_01)
            tests = getTests(context ,query_01, chat_header_id)
        

        elif query ==  Query and context is not None and Query is not None:
                tests = getTests(context ,query, chat_header_id)
            
        else :
            tests = getTests("",query, chat_header_id)

        print("\n\nTESTTSTSE", tests)

        json_data = json.dumps(tests)
        jsonObj = {}
        jsonObj['type'] = 'Quiz'
        jsonObj['Qestions'] = json_data

        json_data_01 = json.dumps(jsonObj)

        def event_stream():
            yield f'data: {json_data_01}\n\n'

            # Wait for 0.5 seconds
            time.sleep(0.5)
            
            # Now send the end of stream event
            yield 'event: stream-end\ndata: {"type": "stream-end"}\n\n'

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
        response['Cache-Control'] = 'no-cache'  # Ensure clients don't cache the data
        return response

    if hasKeywordQuiz == False:

        if context is not None and Query is not None:

            print("Found context and query", context, "---", Query)
            print("Category", chat_header.category)

            if((chat_header.category == "Ask Textbooks") and Query == query):

                instruction = (
                    f"Given the following context for the question: \n {context} \n"
                    f"The context consists of previous questions and answers asked in the thread as well as copied text from the chapter. "
                    f"Based on the given context, answer the following question in relation to this chapter: \n {query}"
                )
                query = instruction
                query = query + f"\nNever include any citation or source from the chapter pdf."

                # Assuming 'thread_id' is an attribute of ChatHeader
                thread_id = chat_header.threads['Ask Textbooks']
                message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
                assistant_id = chapter.assistant['Ask Textbooks']

                print(thread_id, "----", message, "----", assistant_id)

            elif(chat_header.category == "Lecture Planner" and Query == query.split("|")[-1]):

                print("The corerct query to get the lectue planbner is ",  query)

                teachingMethods = query.split("|")
                instruction = 'Given the following teaching lecture planning methods\n'

                for m in teachingMethods[:-1]:
                    instruction = instruction + m  + "\n"

                instruction = instruction + f"Following is the query regarding the lecture planner. \n {teachingMethods[-1]}. \n Read it and generate the best lecture planner to help the teacher teach the class in a more interactive and excellent manner."

                query = instruction
                query = query + f"\nNever include any citation or source from the chapter pdf."

                # Assuming 'thread_id' is an attribute of ChatHeader
                thread_id = chat_header.threads['Lecture Planner']
                message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
                assistant_id = chapter.assistant['Lecture Planner']

                print(thread_id, "----", message, "----", assistant_id)
            elif ((chat_header.category == "AI Tutor" or chat_header.category == "Revision") and Query == query):

                instruction = f'''
                    Given the following context for the question: \n {context} \n
                    The context consists of previous questions and answers asked in the thread as well as copied text from the chapter.
                    You are an AI Tutor, who will not answer directly to the Query : \n {query} \n
                    Instead you will generate extra questions are statements that help the student to think and reach the answer/ Your task is to guide the student to reach the answer and not spoon feed directly with the answer.
                    You may produce a table if required to summarize things that user might require to think and help them find ways to get to the answer, but never give the answer directly
                '''
                query = instruction
                query = query + f"\nNever include any citation or source from the chapter pdf."

                # Assuming 'thread_id' is an attribute of ChatHeader
                thread_id = chat_header.threads['AI_Tutor']
                message = client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
                assistant_id = chapter.assistant['AI Tutor']

                print(thread_id, "----", message, "----", assistant_id)

            # delete_all_query_context_entries()  # Ensure deletion happens here

        event_queue = Queue()
        referenceData_queue = Queue()
        chapterConcept_queue = Queue()

        class EventHandler(AssistantEventHandler):
                @override
                def on_text_created(self, text) -> None:
                    logger.debug(f"\nassistnat > Text created by the assistant")
                    print(f"\nassistant > ", end="", flush=True)

                @override
                def on_text_delta(self, delta, snapshot):
                    logger.debug(f"Received text delta {delta.value}")
                    # print(delta.value, end="", flush=True)
                    event_queue.put(f'data: {replace_newlines(delta.value)}\n\n')
                    logger.debug("Data enqueued successfully ---- Queue size is %d", event_queue.qsize())

                @override
                def on_end(self) -> None:
                    logger.info("AB END HOGYA H STREAMING BETE")
                    event_queue.put("AB END HOGYA H STREAMING BETE __ HUE HUE HUE HUE")


                def on_tool_call_created(self, tool_call):
                    print(f"\nassistant > {tool_call.type}\n", flush=True)

                def on_tool_call_delta(self, delta, snapshot):
                    if delta.type == 'code_interpreter':
                        if delta.code_interpreter.input:
                            print(delta.code_interpreter.input, end="", flush=True)
                    if delta.code_interpreter.outputs:
                        print(f"\n\noutput >", flush=True)
                        for output in delta.code_interpreter.outputs:
                            if output.type == "logs":
                                print(f"\n{output.logs}", flush=True)
                                

        def stream_thread_function():
            try:
                logger.debug("Starting stream thread")
                with client.beta.threads.runs.stream(thread_id=thread_id, assistant_id=assistant_id, event_handler=EventHandler()) as stream:
                    stream.until_done()
                logger.debug("Stream processing completed")
            except Exception as e:
                logger.exception("Exception in stream thread")

        spanIds = []

        def event_stream():
            sentinel_value = "AB END HOGYA H STREAMING BETE __ HUE HUE HUE HUE"  # Define the sentinel value
            thread = Thread(target=stream_thread_function)
            # threadReferenceText = Thread(target=get_Reference_Text, args=(chat_header_id, referenceData_queue))
            threadReferenceText = Thread(target=getReferenceText, args=(context, initialQuery, chat_header_id, referenceData_queue, chapterConcept_queue))

            thread.start()
            threadReferenceText.start()
            
            try:
                while True:
                    try:
                        data = event_queue.get_nowait()
                        if data == sentinel_value:
                            logger.info("End of stream detected. Exiting event_stream.")
                            break  # Break if sentinel value is received
                        if data:
                            logger.info(f"Streaming data: {data}")
                            logger.debug("Queue size is %d", event_queue.qsize())
                            yield data
                        else:
                            logger.debug("Received empty data, continuing...")
                    except Empty:
                        logger.debug("No data received from the queue, sleeping briefly...")
                        time.sleep(0.5)  # Sleep briefly to avoid hogging CPU
            except Exception as e:
                logger.exception("Exception in event_stream")
                yield f'event: error\ndata: {str(e)}\n\n'
            finally:
                thread.join()  # Ensure the thread has completed before closing the stream
                threadReferenceText.join()

                reference_data = referenceData_queue.get_nowait()
                if reference_data:
                    yield f'event: referenceData\n{reference_data}\n\n'
                    # time.sleep(0.1)   

                chapterConcept = chapterConcept_queue.get_nowait()
                if chapterConcept:
                    yield f'event: concept\n{chapterConcept}\n\n'     
                
                yield 'event: stream-end\ndata: {"type": "stream-end"}\n\n'

                        

        response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
        response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
        response['Cache-Control'] = 'no-cache'  # Ensure clients don't cache the data
        return response

@api_view(['GET'])
@permission_classes([AllowAny])
@renderer_classes([ServerSentEventRenderer])
def teachingMethods(request):

    chat_header_id = request.query_params.get('id')

    print("))))))))))))))))", chat_header_id)

    query = request.query_params.get('query')

    logger.debug("---------------- test question %s", query)
    teachingMethods = getTeachingMethods(query, chat_header_id)

    json_data= json.dumps(teachingMethods)
    print("9999999999", json_data)

    def event_stream():
            yield f'data: {json_data}\n\n'

            # Wait for 0.5 seconds
            time.sleep(0.5)
            
            # Now send the end of stream event
            yield 'event: stream-end\ndata: {"type": "stream-end"}\n\n'

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
    response['Cache-Control'] = 'no-cache'  # Ensure clients don't cache the data
    return response


@api_view(['GET'])
@permission_classes([AllowAny])
@renderer_classes([ServerSentEventRenderer])
def generateTests(request):

    chat_header_id = request.query_params.get('id')

    query = request.query_params.get('query')


    print("[[[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]]]",chat_header_id, "=========", query)

    context, Query, snips = extract_context_and_query(chat_header_id)

    referenceData_queue = Queue()
    chapterConcept_queue = Queue()
    threadReferenceText = Thread(target=getReferenceText, args=(context, query, chat_header_id, referenceData_queue, chapterConcept_queue))
    threadReferenceText.start()


    logger.debug("---------------- lecture planner %s", query)

    tests = None

    if query ==  Query and context is not None and Query is not None:
        tests = getTests(context ,query, chat_header_id)
    else :
        tests = getTests("" ,query, chat_header_id)

    print("\n\nTESTTSTSE", tests)

    # pushData(tests)

    json_data = json.dumps(tests)


    def event_stream():
            yield f'data: {json_data}\n\n'

            # Wait for 0.5 seconds
            time.sleep(0.1)

            threadReferenceText.join()

            reference_data = referenceData_queue.get_nowait()
            if reference_data:
                    yield f'event: referenceData\n{reference_data}\n\n'
                    time.sleep(0.1)  
                    
            chapterConcept = chapterConcept_queue.get_nowait()
            if chapterConcept:
                    yield f'event: concept\n{chapterConcept}\n\n'       
            
            # Now send the end of stream event
            yield 'event: stream-end\ndata: {"type": "stream-end"}\n\n'

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response['X-Accel-Buffering'] = 'no'  # Disable buffering in nginx
    response['Cache-Control'] = 'no-cache'  # Ensure clients don't cache the data
    return response

@api_view(['POST'])
def get_feedback(request):

    chat_header_id = request.query_params.get('id')
    chat_convo_id = request.query_params.get('chatId')
    numOfQuestion = request.query_params.get('numOfQues')
    ques_Type = request.query_params.get('Qtype')

    print("The chat Header id is", chat_header_id, " Abd the conversation id in that chat header id is ", chat_convo_id, " The number of quesitons to give feedBack for are: ", numOfQuestion)

    if not chat_header_id:
        # If no 'id' is provided in the query parameters, return a 400 Bad Request
        return Response({'error': 'No id provided'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Fetch the corresponding ChatHeader object using the provided id
        chat_header = ChatHeader.objects.get(pk=chat_header_id)
    except ChatHeader.DoesNotExist:
        # If the ChatHeader with the provided id does not exist, return a 404 Not Found
        return Response({'error': 'ChatHeader not found'}, status=status.HTTP_404_NOT_FOUND)

    chapter = get_object_or_404(Chapter, name=chat_header.chapter)
    chapter_name = chapter.name

    if request.method == 'POST':

        query = request.data

        instruction = f'''
        You have all the knowledge of the chapter {chapter_name}
        Now given the following quesiton:
        {query['question']}
        The student's answer is:
        {query['answer']}
        The question is for a total of {query['marks']}

        Provide feedback and the marks student should get based out of his answer.
        Inside the feedback tell what the student should have mentioned and what all he has missed and which areas did he/she lack.

        Give the response in strictly in this json format:
        {{
            "feedback": "<feedback_message>",
            "marks": "<marks_given_for_the_students_answer>"
        }}
'''
        

        print("THE FINAL QUERY TO GET THE FEEDBACK IS _______________-----------------______>", instruction)        

        threadId = chat_header.threads['Feedback']

        message = client.beta.threads.messages.create(
            thread_id=threadId,
            role="user",
            content=instruction,
        )

        assistantId = chapter.assistant['Feedback']
            
        run = client.beta.threads.runs.create(
            thread_id=threadId,
            assistant_id=assistantId,
        )

        # Wait for completion
        while run.status != "completed":
            # Be nice to the API
            time.sleep(0.5)
            run = client.beta.threads.runs.retrieve(thread_id=threadId, run_id=run.id)

        # Retrieve the Messages
        messages = client.beta.threads.messages.list(thread_id=threadId)
        new_message = messages.data[0].content[0].text.value

        print("The returned message from THE LLM IS BRO-------->", new_message)

        jsonRes = extract_json_from_text(new_message)

        if jsonRes == "No JSON found":
            print("HELLO")
            jsonRes = extract_feedback_and_marks(new_message)

        print("The returned json response to the student is======]]]]]]\n", jsonRes)

        # Assuming you have the chat instance
        chat_instance = Chats.objects.get(id=chat_convo_id)  # Replace with the actual method to get your chat instance

        # Get the FeedBack entry with the highest version number for the given chat instance
        feedback_entry = FeedBack.objects.filter(chat=chat_instance, completed=False).order_by('-version').first()

        if feedback_entry:

            # feedbackJsonToPush = [jsonRes]

            # Key string with random number
            # random_number = random.randint(0, 9999)  # Generates a random number between 0 and 9999
            # key_with_random_number = f"{ques_Type}_{random_number}"
            jsonRes['answer'] = query['answer']

            feedbackJsonToPush = {
                ques_Type: jsonRes
            }

            if len(feedback_entry.feedBack.keys()) < int(numOfQuestion):
                # Retrieve the current feedback array
                current_feedback = feedback_entry.feedBack
                # Append the new feedback data to the current feedback array
                # current_feedback.extend(feedbackJsonToPush)   
                current_feedback.update(feedbackJsonToPush)
    
                feedback_entry.save()  # Save the updated entry

            elif len(feedback_entry.feedBack.keys()) == int(numOfQuestion):
                # Retrieve the current feedback array
                current_feedback = feedback_entry.feedBack
                # Append the new feedback data to the current feedback array
                # current_feedback.extend(feedbackJsonToPush)   
                current_feedback.update(feedbackJsonToPush)
                feedback_entry.completed = True
                feedback_entry.save()
        else:
            # feedbackJsonToPush = [jsonRes]

            # Key string with random number
            # random_number = random.randint(0, 9999)  # Generates a random number between 0 and 9999
            # key_with_random_number = f"{ques_Type}_{random_number}"

            jsonRes['answer'] = query['answer']
            feedbackJsonToPush = {
                ques_Type: jsonRes
            }

            # Get the highest version number
            highest_version = FeedBack.objects.filter(chat=chat_instance).aggregate(Max('version'))['version__max']
            version = 0

            if highest_version is None:
                version = 0
            elif highest_version is not None:
                version = highest_version + 1


            # Create a new FeedBack entry if none exists for the given chat instance
            new_feedback_entry = FeedBack.objects.create(
                chatHeader=chat_header_id,
                chat=chat_instance,
                feedBack=feedbackJsonToPush,  # Replace with actual data
                version=version,  # Initial version number
                completed=False  # Replace with actual data
            )


        return JsonResponse(jsonRes, safe=False)