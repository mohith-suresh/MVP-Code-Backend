from openai import OpenAI
import logging
import json, re
import urllib.parse
from eduGptApp.models import Chapter, ChatHeader, QueryContext, TestQuestion, ChapterReferenceData, ChapterReferenceText, Chats
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework import status
import time
from queue import Queue, Empty
from threading import Thread, Event
import random
from pgvector.django import L2Distance

import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image
from PIL import Image, ImageDraw


client = OpenAI(api_key='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')

# Get an instance of a logger
logger = logging.getLogger('django')

# Configure logging
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_json_from_text(text):
    try:
        # Preprocess the text to replace single quotes with double quotes around keys and string values
        # This step assumes the original text incorrectly uses single quotes for JSON formatting
        # Note: This is a simplistic approach and might not work for complex cases where single quotes are part of the data
        processed_text = re.sub(r"'([^']+?)'(?=:|,|})", r'"\1"', text)

        # Attempt to extract JSON from the text using a regex that captures everything inside the outermost curly braces
        json_str = re.search(r'\{.*?\}', processed_text, re.DOTALL).group()

        # Parse the JSON string
        return json.loads(json_str)
    except AttributeError:
        # No JSON found
        return "No JSON found"
    except json.JSONDecodeError:
        # JSON is malformed
        return "Malformed JSON"

def replace_newlines(input_string):
    # Replace all newline characters with '||<-'
    return input_string.replace('\n', '||<-')


def find_integers_in_string(text):
    # Regular expression that matches digits
    pattern = r'\d+'  # \d matches a digit, + makes it match one or more digits
    numbers = re.findall(pattern, text)
    return [int(num) for num in numbers]  # Convert to integers

def extract_feedback_and_marks(api_response):
    # Regular expression to capture feedback
    # feedback_pattern = r"(?i)\*\*Feedback:\*\*(.*?)(?i)\*\*Marks"
    feedback_pattern = r"(?i)feedback(.*?)(?i)marks"
    
    # Regular expression to capture marks, now checking for any characters between ':' and the digits
    marks_pattern = r"\*\*Marks Given for the Student's Answer:\*\*.*?(\d+) out of 5"
    
    # Extracting feedback
    feedback_match = re.search(feedback_pattern, api_response, re.S)
    if feedback_match:
        feedback = feedback_match.group(1).strip()
    else:
        feedback = "Feedback not found."

    print("THE FEEDBACK IS", feedback)
    
    # Extracting marks
    marks = find_integers_in_string(api_response)[-2]
    
    # Return the extracted information in the specified format
    return {
        "feedback": feedback,
        "marks": marks
    }

# Sample API response
# api_response = """
# **Feedback:**
# The student's answer is incomplete and lacks depth. The response does not adequately describe the author's experiences during the monsoon season as depicted in the diary entry. The student should have mentioned specific incidents and observations detailed in the diary, such as the change in nature during the monsoon, encounters with wildlife like leopards and leeches, the continuous rain leading to lush growth of flora, and the author's emotional and sensory responses to the monsoon.

# **Key Points the Student Missed:**
# 1. Specific incidents like the leopard attacking a cow and the presence of scarlet minivets and drongos.
# 2. The author's emotional responses and interactions with nature during the monsoon season.
# 3. The transformation of the hills and vegetation during the monsoon.
# 4. The author's reflections on solitude and tranquility during rainy days.

# **Areas of Improvement:**
# 1. The student should include more detailed descriptions of the author's interactions with nature and wildlife during the monsoon.
# 2. Adding examples and quotes from the diary entry would enhance the response.
# 3. Exploring the author's perceptions of nature, solitude, and the changes brought about by the monsoon in more depth.

# **Marks Given for the Student's Answer: 2 out of 5** 
# """

# # Calling the function
# result = extract_feedback_and_marks(api_response)
# print(result)


def extract_json_from_text(text):
    try:
        # This regex pattern assumes the JSON object starts with { and ends with }
        # It is a very basic pattern and might need to be adjusted based on actual content specifics.
        json_str = re.search(r'\{.*\}', text, re.DOTALL).group()
        return json.loads(json_str)
    except AttributeError:
        # No JSON found
        return "No JSON found"
    except json.JSONDecodeError:
        # JSON is malformed
        return "Malformed JSON"


def decode_json_from_url(encoded_json):
    # Step 1: Decode the URL-encoded JSON string
    decoded_json = urllib.parse.unquote(encoded_json)
    
    # Step 2: Parse the JSON string into a Python dictionary
    json_data = json.loads(decoded_json)
    
    return json_data

def get_latest_query_context(chat_header_id):
    try:
        latest_entry = QueryContext.objects.filter(chatHeaderId=chat_header_id).order_by('-created_at').first()
        return latest_entry
    except QueryContext.DoesNotExist:
        return None
    
def extract_context_and_query(chat_header_id):
    latest_entry = get_latest_query_context(chat_header_id)
    if latest_entry:
        print("Found latest entry")
        context = latest_entry.context  # This is the JSON field
        query = latest_entry.query       # This is the text field
        snips = latest_entry.snips

        print("CONTEXT::: ", type(context),"---", len(context), " ::::: QUERY ::::: ",query, " ::::: SNIPS :::: ")

        return context, query, snips
    else:
        return None, None
    
def delete_all_query_context_entries():
    # This will delete all entries in the QueryContext table
    QueryContext.objects.all().delete()
    logger.info("All entries in QueryContext have been successfully deleted.")

def getTeachingMethods(query, chat_header_id):

    jsonFormat = '''
    {
        "teaching_methods": ["Inquiry-Based Learning", "Thematic Learning", "Project-Based Learning", "Reflective Writing"],
        "Inquiry-Based Learning": "Students can investigate various aspects of nature and wildlife mentioned in the diary, such as the impact of monsoon on flora and fauna, the behavior of different animals during the rainy season, and the ecological significance of rainfall.", 
        "Thematic Learning": "As the diary covers recurring themes about nature, monsoon, wildlife, and the author's observations, thematic learning can help students understand the interconnectedness of these themes throughout the diary.", 
        "Project-Based Learning": "Students can work on projects like creating a visual representation of the different birds and plants mentioned in the diary, conducting a weather observation project during the monsoon season, or presenting a comparative analysis of monsoon diaries from different authors.", 
        "Reflective Writing": "Encouraging students to write reflections on their own experiences related to nature, monsoon, or wildlife can help deepen their understanding and personal connection to the themes discussed in the diary."
        }
        '''
    instruction = "Given the query below generate best teaching methods along with its description in json format as instructed below \n" + jsonFormat + '\nQuery :\n'
    query = instruction + query

    logger.info("------------------->>>>>>> QUERY IS %s", query)


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

    threadId = chat_header.threads['Teaching Methods Generator']

    message = client.beta.threads.messages.create(
        thread_id=threadId,
        role="user",
        content=query,
    )

    assistantId = chapter.assistant['Teaching Methods Generator']

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

    jsonTeachingMethods = extract_json_from_text(new_message)
    if jsonTeachingMethods == "Malformed JSON" or jsonTeachingMethods == "No JSON found":
        return ""
    else: 
        return jsonTeachingMethods

def contains_column(text):
    # Convert text to lowercase to make the search case-insensitive
    text = text.lower()
    
    # Search for pattern that matches the number of column questions
    match = re.search(r'(\d+)\s*(match the )?column', text)
    
    if match:
        # Extract the number (first group in the match)
        num_columns = int(match.group(1))
        return num_columns, True
    else:
        # Return 0, False if 'column' is not found
        return 0, False


def filter_questions(data, requirements):
    # Extract the types and respective questions from the data
    question_types = data['types']
    filtered_data = {'types': []}

    # Iterate over each type in requirements to adjust the number of questions or remove the type
    for q_type, required_count in requirements.items():
        if q_type.capitalize() in question_types:
            # Check if the type has questions and the required count is not zero
            if required_count > 0 and q_type.capitalize() in data:
                # Get the questions for the type and trim to required count
                current_questions = data[q_type.capitalize()]
                # Slice the dictionary to the required number of questions
                filtered_questions = dict(list(current_questions.items())[:required_count])
                filtered_data[q_type.capitalize()] = filtered_questions
                filtered_data['types'].append(q_type.capitalize())
            elif required_count == 0:
                # Remove the type entirely if count is zero
                question_types.remove(q_type.capitalize())
                # Continue without adding the type or its questions
                continue

    return filtered_data

def remove_column_related_text(text):
    # Regular expression to find variations including "match the column", "match", or "column" with any preceding numbers
    pattern = r'\s*\d+\s+(match the column|match|column)'

    # Replace the found pattern with an empty string
    cleaned_text = re.sub(pattern, '', text)

    # Optionally, clean up any excess commas and spaces left over after removal
    cleaned_text = re.sub(r'\s*,\s*,', ', ', cleaned_text)  # Replace double commas with a single
    cleaned_text = cleaned_text.strip(', ')  # Strip any trailing or leading commas

    return cleaned_text

def parse_question_counts(text):
    # Create a dictionary to store the counts of each question type
    question_counts = {}

    # Patterns to look for each type of question, including various descriptions for MCQs
    patterns = {
        'long': r'(\d+)\s+long',
        'short': r'(\d+)\s+short',
        'mcq': r'(\d+)\s+(mcq|multiple choice question|multiple|choice of multiple choice)',
        'fill' : r'(\d+)\s+(fill|blank|fill blank|fill in the blank)'
    }

    # Use regular expressions to find the counts for each question type
    for q_type, pattern in patterns.items():
        regex = re.compile(pattern)
        match = regex.search(text)

        if match:
            # Convert the matched number to an integer and store it in the dictionary
            question_counts[q_type] = int(match.group(1))
        else:
            # Assume zero for this question type if no match is found
            question_counts[q_type] = 0

    return question_counts

def generate_question_json_template(counts):
    typesArray = []
    if counts['long'] > 0:
        typesArray.append("Long Question")
    if counts['short'] > 0:
        typesArray.append("Short Question")
    if counts['fill'] > 0:
        typesArray.append("Fill")
    if counts['mcq'] > 0:
        typesArray.append("MCQ")

    template = {
        "types": typesArray,
        "Fill": {},
        "Long Question": {},
        "MCQ": {},
        "Short Question": {}
    }

    # Example content for questions
    mcq_question_template = {
        "question": "<question_text>",
        "options": ["Option1", "Option2", "Option3", "Option4"],
        "marks": 1
    }

    long_question_template = {
        "question": "<question_text>",
        "marks": 5
    }

    short_question_template = {
        "question": "<question_text>",
        "marks": 3
    }

    fill_question_template = {
        "question": "<question_text>",
        "marks": 1
    }

    # Populate MCQs
    if counts['mcq'] > 0:
        for i in range(1, counts.get('mcq', 0) + 1):
            template['MCQ'][str(i)] = mcq_question_template.copy()
    else:
        template.pop('MCQ', None)

    # Populate Long Questions
    if counts['long'] > 0:
        for i in range(1, counts.get('long', 0) + 1):
            template['Long Question'][str(i)] = long_question_template.copy()
    else:
        template.pop('Long Question', None)

    # Populate Short Questions
    if counts['short'] > 0:
        for i in range(1, counts.get('short', 0) + 1):
            template['Short Question'][str(i)] = short_question_template.copy()
    else:
        template.pop('Short Question', None)

    # Populate Fill Questions
    if counts['fill'] > 0:
        for i in range(1, counts.get('fill', 0) + 1):
            template['Fill'][str(i)] = fill_question_template.copy()
    else:
        template.pop("Fill", None)

    return template

def detect_quiz_length_and_keyword_presence(query):
    # Regex pattern to find numbers followed by one of several keywords
    # Include variations of "practice/practise" with "quiz", "question", "test"
    pattern = r'(\d+)\s*(question|questions|quiz|quizzes|test|tests|(?:practi[cs]e)\s+(question|questions|quiz|quizzes))'
    keyword_pattern = r'\b(question|questions|quiz|quizzes|test|tests|practi[cs]e)\b'
    
    # Find if any relevant keyword exists
    keyword_match = re.search(keyword_pattern, query, re.IGNORECASE)
    
    # Find if there is a numeric pattern followed by a keyword
    match = re.search(pattern, query, re.IGNORECASE)
    if match:
        # If a match is found, return the number and True indicating keyword presence
        return (int(match.group(1)), True)
    elif keyword_match:
        # If only keyword is found without a number, return default length and True
        return (0, True)
    else:
        # If neither a number nor a keyword is found, return default length and False
        return (0, False)
    
def generate_random_question_query(total_questions):
    types = ['mcq', 'long', 'column', 'blank', 'short']
    questions = {t: 0 for t in types}

    # Randomly allocate questions
    for _ in range(total_questions):
        chosen_type = random.choice(types)
        questions[chosen_type] += 1

    # Generate a descriptive query
    query_parts = [f"{count} {type} type questions" for type, count in questions.items() if count > 0]
    query = ", ".join(query_parts)
    return query



def getColumnTypeQuestionS(context, query, chat_header, chapter):

    jsonOutput = '''

    If 2 column question are demanaded then this will be the structure of the output.

    For n number of column question demanded, there will be n keys from '1', 2' till .... 'n'

Example Structure:

{
    "types": ["Column"],
    
    "Column": {
        
        "1": {
            "question": "Match the following terms with their meanings:",
            "columnData": {
                "ColumnA": ["melancholy", "blankets", "fern", "bloodletting"],
                "ColumnB": ["covers", "very sad", "a flowerless plant with feathery green leaves", "losing blood"]
            },
            "answer": {
                "melancholy": "very sad",
                "blankets": "covers",
                "fern": "a flowerless plant with feathery green leaves",
                "bloodletting": "losing blood"
            }
        },
        '2': {
            'question': 'Match the emotions with their descriptions:', 
            'columnData': {
                'ColumnA': ['excitement', 'apprehension', 'worry', 'awe'], 
                'ColumnB': ['anticipation of something good', 'fear or anxiety', 'feeling uneasy about something', 'respect mixed with fear or wonder']
            }, 
            'answer': {
                'excitement': 'anticipation of something good', 
                'apprehension': 'fear or anxiety', 
                'worry': 'feeling uneasy about something', 
                'awe': 'respect mixed with fear or wonder'
            }
        }
        
    }
} 
'''


    if(context != ""):
        instruction = f"Given the following context \n" + f"{context} \n" + f"Generate questions based on the the chapter {chapter.name} as instructed here \n {query}. \n Always give the output in the following json template \n {jsonOutput} \n Attach the correct answer and marks to each question."
    else :
        instruction = f"Generate questions based on the {chapter.name} as instructed here \n {query}. \n Always give the output in the following json template \n {jsonOutput} \n Attach the correct answer and marks to each question."
    query = instruction

    threadId = chat_header.threads['Column']

    message = client.beta.threads.messages.create(
        thread_id=threadId,
        role="user",
        content=query,
    )

    assistantId = chapter.assistant['Column Tests']

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
    columnQuestions = extract_json_from_text(new_message)
    print("PPPPPPPPPPP000000000000000 BEFORE----->", columnQuestions)

    # Function to shuffle columnB while maintaining original answers
    for key, value in columnQuestions['Column'].items():
        # Shuffle the columnB data
        columnB = value['columnData']['ColumnB']
        random.shuffle(columnB)
        value['columnData']['ColumnB'] = columnB

    print("PPPPPPPPPPP000000000000000 AFTER----->", columnQuestions)

    return columnQuestions

def getTests(context, query, chat_header_id):
    print("7777777777777777 ", chat_header_id)
    instruction = None
    column_type_data = {}

    quesCount = parse_question_counts(query)

    jsonTeachingMethods = {}

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
    chapterName = chapter.name

    numOfColumnQuestion = 0
    
    # Helper function to run in a separate thread
    def fetch_column_type_data():
        numOfColumnQuestion, wanted = contains_column(query)

        if wanted and numOfColumnQuestion > 0:  
            # print("333333333333333333333333", numOfColumnQuestion)
            preQues  = f"Generate {numOfColumnQuestion} column type question based on the following query \n"
            queryColumn= preQues + query
            nonlocal column_type_data
            column_type_data = getColumnTypeQuestionS(context, queryColumn, chat_header,chapter)
        else :
            pass

    # Start the thread for getColumnTypeQuestionS
    column_thread = Thread(target=fetch_column_type_data)
    column_thread.start()

    if (quesCount['long'] + quesCount['short'] + quesCount['mcq']  + quesCount['fill']> 0):

        jsonOutput = generate_question_json_template(quesCount)

        if(context != ""):        
            query = remove_column_related_text(query)
            instruction = f"Given the following context \n" + f"{context} \n" + f"Generate questions based on the the chapter {chapterName} as instructed here \n {query}. \n Always give the output in the following json template \n {jsonOutput} \n Attach the correct answer and marks to each question."
        else :
            query = remove_column_related_text(query)
            instruction = f"Generate questions based on the {chapter} as instructed here \n {query}. \n Always give the output in the following json template \n {jsonOutput} \n Attach the correct answer and marks to each question."
        query = instruction

        logger.info("------------------->>>>>>> QUERY IS %s", query)
        

        threadId = chat_header.threads['Create Tests']

        message = client.beta.threads.messages.create(
            thread_id=threadId,
            role="user",
            content=query,
        )

        assistantId = chapter.assistant['Create Tests']

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

        # print("skjdfjs dlfldsf", new_message)

        print("9999999999999999", column_type_data, type(column_type_data))

        print("iiiiiiiiiiiiiiiii", new_message)
        jsonTeachingMethods = extract_json_from_text(new_message)

    # Wait for the column data thread to finish 
    column_thread.join()

    # Add column questions with marks to the existing JSON
    if column_type_data != {}:
        for key, value in column_type_data['Column'].items():
            value['marks'] = 4  # Assigning 4 marks to each column question

        if 'types' in jsonTeachingMethods:
            if 'Column' not in jsonTeachingMethods['types']:
                jsonTeachingMethods['types'].append('Column')
        else:
            jsonTeachingMethods['types'] = ['Column']

        jsonTeachingMethods['Column'] = column_type_data['Column']

    print("jsonjo form hua hue hue hue bhai", jsonTeachingMethods)

    if jsonTeachingMethods == "Malformed JSON" or jsonTeachingMethods == "No JSON found":
        return ""
    else: 
        return jsonTeachingMethods
    
def extract_indexes(response):
    # Use regex to find the list of indexes within square brackets
    match = re.search(r'\[(\d+(?:,\s*\d+)*)\]', response)
    if match:
        # Extract the matched string and convert it to a list of integers
        index_list = match.group(1).split(',')
        return [int(index.strip()) for index in index_list]
    return []

def getEmbedding(text):
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )

        return response.data[0].embedding
    
def getReferenceText(context, query, chat_header_id, referenceData_queue, chapterConcept_queue):
        
        try:
            # Fetch the corresponding ChatHeader object using the provided id
            chat_header = ChatHeader.objects.get(pk=chat_header_id)
        except ChatHeader.DoesNotExist:
            # If the ChatHeader with the provided id does not exist, return a 404 Not Found
            return Response({'error': 'ChatHeader not found'}, status=status.HTTP_404_NOT_FOUND)
    
        chapter = get_object_or_404(Chapter, name=chat_header.chapter)
        chapterName = chapter.name

        threadId = chat_header.threads['Reference']

        # chapterReferenceText = get_object_or_404(ChapterReferenceText, pk=chapter.id)
        # json_data = chapterReferenceText.referenceText
        # json_data = json.loads(json_data)
        # keys_list = list(json_data.keys())
        # keys_string = '[' + ', '.join(keys_list) + ']'

        # print("8888888", keys_string)

        # query_01 = f'''
        #     Query: {query}
        #     Elements to Check: {keys_string}

        #     Instructions:You are an expert in the chapter {chapterName}
        #     Analyze the provided list of elements based on the content knowledge of the chapter to identify which consecutive segments contain the answer to the query. Return the answer as a list of consecutive indexes, ensuring they form a continuous sequence. Only provide indexes like [0, 1] or [2, 3, 4]; non-consecutive sequences like [0, 2] are not allowed.

        #     Example:

        #     Query: "When does the author describe interactions between humans and wildlife during the monsoon?"
        #     Elements to Check: ["June 24", "June 25 and June 27", "August 2 to August 3", "August 12 and August 31", "October 3", "January 26 and March 23"]

        #     Given the query, determine the consecutive elements in the list that contain the answer. Return the index list in the format [index1, index2, ...], e.g., [1, 2] or [3, 4, 5].
        # '''

        query_01 = f'''
        Given the following query : {query}
        and context : {context}
        Give a very brief answer to the query in words and keywords
        '''

        print("p;;;;;;;;;",query_01)

        message = client.beta.threads.messages.create(
            thread_id=threadId,
            role="user",
            content=query_01,
        )

        assistantId = chapter.assistant['Reference']

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

        print("THE ANSWER FROM THE REFERECNE AI IS", new_message)

        # Query the database to find the nearest neighbor based on vector distance
        nearest_chunk = ChapterReferenceText.objects.filter(chapter=chapter.id).order_by(L2Distance('embedding', getEmbedding(new_message))).first()
        print("00000000000000000 THE CHUNK IS", nearest_chunk.chunk_text)
        # list_of_indexes = extract_indexes(new_message)

        # print("[[[[[[[[[[[[[[[[]]]]]]]]]]]]]]]]=============", list_of_indexes)

        # extracted_keys = [keys_list[i] for i in list_of_indexes]
        # referenceText = ''

        # for key in extracted_keys:
        #     referenceText = referenceText + json_data[key]


        
        spanIds = getReferenceTextSpanId(nearest_chunk.chunk_text, chat_header_id)

        print("The span IDs generated are bro++++++++++++", spanIds)

        jsonData = {
                "referenceData" : spanIds
            }
        
        jsonStr = json.dumps(jsonData)
        
        referenceData_queue.put(f'data: {jsonStr}\n\n')
        chapterConcept_queue.put(f'data: {nearest_chunk.conceptName}\n\n')


        # return new_message

def get_Reference_Text(chat_header_id, referenceData_queue):

            # prompt = f"You are an expert at the chapter {chapter.name}. \n Now given the following query: \n {initialQuery} \n go through the entire chapter text and give the exact text from the chapter which has the answer to the query {initialQuery}. Do not summarise or answer the question, just output the exact text from the chapter which has the asnwer to the quesiton."
            # referenceText = getReferenceText("", prompt, chat_header_id)

            # print("The reference text from the chapter is ]]]]]]]]]]]]]]]]", referenceText)

            referenceTexts = [
                "Through the mist Bijju is calling to his sister. I can hear him running about on the hillside but I cannot see him",
                "June 25 Some genuine early- monsoon rain, warm and humid, and not that cold high-altitude stuff we’ve been having all year. The plants seem to know it too, and the first cobra lily rears its head from the ferns as I walk up to the bank and post office.",
                "A tree creeper moves rapidly up the trunk of the oak tree, snapping up insects all the way. Now that the rains are here, there is no dearth of food for the insectivorous birds.",
                "As for the leeches, I shall soon get used to a little bloodletting every day. Other new arrivals are the scarlet minivets (the females are yellow), flitting silently among the leaves like brilliant jewels.",
                "A school boy asked me to describe the hill station and valley in one sentence, and all I could say was: “A paradise that might have been.”"
            ]

            referenceText = referenceTexts[random.randint(0, 4)]

            spanIds = getReferenceTextSpanId(referenceText, chat_header_id)

            jsonData = {
                "referenceData" : spanIds
            }

            jsonStr = json.dumps(jsonData)

            print("The highlighting span IDs for the chapter is", spanIds)

            referenceData_queue.put(f'data: {jsonStr}\n\n')

################################ UTILS For Tasks of Celery #########################################

def extract_response(text):
    # Adjust regex patterns to match keys with or without quotation marks and make ':' optional
    user_pattern = r'["]?user["]?\s*[:=]?\s*(.*?)(?=\s*["]?\s*answer["]?|\s*})'
    answer_pattern = r'["]?answer["]?\s*[:=]?\s*(.*?)(?=\s*})'
    
    user_match = re.search(user_pattern, text, re.DOTALL)
    answer_match = re.search(answer_pattern, text, re.DOTALL)
    
    response = {}
    
    if user_match:
        response['user'] = user_match.group(1).strip().strip('",')
    if answer_match:
        response['answer'] = answer_match.group(1).strip().strip('",')
    
    return response

import uuid

jsonFormat = {
   "user": "<brief_summary>",
   "eduGpt": "<detailed_revision_materials>"
}

def check_or_create_chat_header(chatHeaderData):

    print("---------------", chatHeaderData)

    userId = chatHeaderData['userId']  # example user ID
    created_at_text = chatHeaderData['created_at_text']  # example created_at_text

    thread_Ask_Textbooks = client.beta.threads.create()
    thread_Teaching_Methods_Generator = client.beta.threads.create()
    thread_Lecture_Planner = client.beta.threads.create()
    thread_Create_Tests = client.beta.threads.create()
    thread_Column_Question = client.beta.threads.create()
    thread_AI_Tutor = client.beta.threads.create()
    thread_Feedback = client.beta.threads.create()
    thread_Revision = client.beta.threads.create()

    # Get the thread_id from the created thread object
    thread_id_Ask_Textbooks = thread_Ask_Textbooks.id  # Assuming 'id' is the attribute holding the thread_id
    thread_id_Teaching_Methods_Generator = thread_Teaching_Methods_Generator.id
    thread_id_Lecture_Planner = thread_Lecture_Planner.id
    thread_id_Create_Tests = thread_Create_Tests.id
    thread_id_Column_Question = thread_Column_Question.id
    thread_id_AI_Tutor = thread_AI_Tutor.id
    thread_id_Feedback = thread_Feedback.id
    thread_id_Revision = thread_Revision.id

    # Prepare the data for serialization, adding the 'thread_id'

    threadData =  {
        "Ask Textbooks" : thread_id_Ask_Textbooks,
        "Teaching Methods Generator" : thread_id_Teaching_Methods_Generator,
        "Lecture Planner" : thread_id_Lecture_Planner,
        "Create Tests" : thread_id_Create_Tests,
        "Column" : thread_id_Column_Question,
        "AI_Tutor" : thread_id_AI_Tutor,
        "Feedback" : thread_id_Feedback,
        "Revision" : thread_id_Revision
    }
    # Attempt to get or create a ChatHeader instance
    chat_header, created = ChatHeader.objects.get_or_create(
        userId=userId,
        created_at_text=created_at_text,
        category="Revision",
        defaults={
            'id': uuid.uuid4(),  # You'll need to ensure this is unique
            'name': created_at_text,
            'type': chatHeaderData['type'],  # or 'Teacher' depending on your logic
            'class_name': chatHeaderData['class_name'],
            'subject': chatHeaderData['subject'],
            'chapter': chatHeaderData['chapter'],
            'created_at_unix': chatHeaderData['created_at_unix'],  # example Unix timestamp
            'threads': threadData  # Assuming an empty JSON object for new creation
        }
    )

def getRevisionContent(query,chat_header):

        threadId = chat_header.threads['Feedback']

        chapter = get_object_or_404(Chapter, name=chat_header.chapter)

        message = client.beta.threads.messages.create(
            thread_id=threadId,
            role="user",
            content=query,
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

        print("-------------------", new_message)

        jsonRes = extract_json_from_text(new_message)
        return jsonRes

def preprocess(text):
    """Remove all non-alphanumeric characters and convert text to lowercase."""
    return re.sub(r'\W+', '', text).lower()


def getReferenceTextSpanId(referenceText, chatHeaderId):
    chat_header = ChatHeader.objects.get(pk=chatHeaderId)
    chapter = get_object_or_404(Chapter, name=chat_header.chapter)

    chapterReferenceData = get_object_or_404(ChapterReferenceData, chapter=chapter)
    json_data = chapterReferenceData.referenceData

    json_data = json.loads(json_data)

    # print("THE REFERENCE DATA IN JSON IS:::::", json_data)

    # Normalize the query to a sequence of characters
    normalized_query = preprocess(referenceText)
    keys = sorted(json_data.keys(), key=lambda x: int(x.split('_')[1]))

    # Concatenate all texts with their keys, skipping empty entries
    full_text = ''
    index_map = []  # Maps character index in full_text to key index
    for key in keys:
        text = preprocess(json_data[key])
        if text:  # Append only if the text is not empty
            full_text += text
            index_map.extend([key] * len(text))  # Map each character to its key

    # Find the start position of the query in the full text
    start_pos = full_text.find(normalized_query)
    if start_pos == -1:
        return []  # Query not found

    # Find the range of keys that encompass the query
    start_key = index_map[start_pos]
    end_key = index_map[start_pos + len(normalized_query) - 1]

    # Collect and return the range of keys from start to end
    start_index = keys.index(start_key)
    end_index = keys.index(end_key)
    return keys[start_index:end_index + 1]


# Function to create threads (this will be run in parallel)
def create_thread(client, thread_name):
    thread = client.beta.threads.create()
    return thread_name, thread.id

############ SNIP IMAGE UTILS ###############

def base64_to_image(base64_str):
    image_data = base64.b64decode(base64_str.split(',')[1])
    image = Image.open(BytesIO(image_data))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

def image_to_base64(image):
    _, buffer = cv2.imencode('.jpg', image)
    image_base64 = base64.b64encode(buffer).decode('utf-8')
    return 'data:image/jpeg;base64,' + image_base64

def scale_image(image, scale_factor):
    width = int(image.shape[1] * scale_factor)
    height = int(image.shape[0] * scale_factor)
    dim = (width, height)
    return cv2.resize(image, dim, interpolation=cv2.INTER_AREA)

def draw_bounding_box_on_base64_image(original_base64, top_left, bottom_right):
    try:
        # Remove the data URL prefix if it exists
        if original_base64.startswith('data:image'):
            original_base64 = original_base64.split(',')[1]
        
        # Decode the base64 string
        original_image_data = base64.b64decode(original_base64)
        
        # Open the image using PIL
        original_image = Image.open(BytesIO(original_image_data))
        
        # Extract the coordinates
        x1, y1 = top_left
        x2, y2 = bottom_right
        
        # Draw a green bounding box on the original image
        draw = ImageDraw.Draw(original_image)
        draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
        
        # Convert the modified image back to base64
        buffered = BytesIO()
        original_image.save(buffered, format="PNG")
        result_base64 = 'data:image/png;base64,' + base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        return result_base64
        
    except base64.binascii.Error as e:
        print(f"Error decoding base64 string: {e}")
    except Image.UnidentifiedImageError as e:
        print(f"Error identifying image: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def match_and_draw(original_base64, snip_base64, snip_scale_factor, original_scale_factor):
    # Convert base64 strings to OpenCV images
    original_image = base64_to_image(original_base64)
    snip = base64_to_image(snip_base64)
    
    # Determine the maximum scale factor
    max_scale_factor = max(snip_scale_factor, original_scale_factor)
    
    # Scale both images according to the maximum scale factor
    scaled_original_image = scale_image(original_image, max_scale_factor)
    scaled_snip_image = scale_image(snip, max_scale_factor)
    
    # Convert images to grayscale
    scaled_original_gray = cv2.cvtColor(scaled_original_image, cv2.COLOR_BGR2GRAY)
    scaled_snip_gray = cv2.cvtColor(scaled_snip_image, cv2.COLOR_BGR2GRAY)
    
    # Apply template matching with the scaled snip
    result = cv2.matchTemplate(scaled_original_gray, scaled_snip_gray, cv2.TM_CCOEFF_NORMED)
    
    # Get the location of the best match
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    
    # Get the coordinates of the top-left corner of the matched region on the scaled image
    top_left_scaled = max_loc
    bottom_right_scaled = (top_left_scaled[0] + scaled_snip_gray.shape[1], top_left_scaled[1] + scaled_snip_gray.shape[0])
    
    # Convert the coordinates back to the original image scale
    top_left = (int(top_left_scaled[0] / max_scale_factor), int(top_left_scaled[1] / max_scale_factor))
    bottom_right = (int(bottom_right_scaled[0] / max_scale_factor), int(bottom_right_scaled[1] / max_scale_factor))
    
    return top_left, bottom_right

def imgDetailsGpt(original_base64, snip_base64, snip_scale_factor, original_scale_factor, imgDescription, imgNum, queueSnip):

    topLeft, bottomRight = match_and_draw(original_base64, snip_base64, snip_scale_factor, original_scale_factor)
    imgDataUrl = draw_bounding_box_on_base64_image(original_base64, topLeft,  bottomRight)


    response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {
        "role": "user",
        "content": [
            {
            "type": "text", 
            "text": f'''
                    The image description and details are :\n
                    {imgDescription}    \n
                    This image is  {imgNum}th image of the chapter \n
                    Now the image has a red bouding box which depicts the snip on the original image taken.

                    Generate a description and give details about the snip on the originial image taken
    '''
            },
            {
            "type": "image_url",
            "image_url": {
                "url": imgDataUrl,
            },
            },
        ],
        }
    ],
    max_tokens=500,
    )

    # return response.choices[0].message.content
    queueSnip.put(response.choices[0].message.content)

# Function to get and print all messages from the queue without blocking
def print_all_messages_from_queue(q):
    while True:
        try:
            message = q.get_nowait()
            return message
        except Empty:
            break

# Function to determine the next id
def get_next_id(data_list):
    if not data_list:
        return 0
    max_id = max(item['id'] for item in data_list)
    return max_id + 1

def iterate_in_batches(array, batch_size):
    """
    Generator function to iterate over an array in batches of specified size.
    
    :param array: List of elements to iterate over.
    :param batch_size: Size of each batch.
    :yield: Batch of elements from the array.
    """
    for i in range(0, len(array), batch_size):
        yield array[i:i + batch_size]


############# This is for creating the Revision Data ###################
def create_Revision_Data(data, userId):
    print("THE USER ID IS::: ", userId)
    print("The students chat history is", data)
    
    className = data['class']
    print("THE CLASS NAME IS ---  ", className)
    for keys in data:
        print("0000", keys)
        if keys.strip() != 'class' and keys.strip() != 'chapter':

            chapterName = data[keys][0]['chapter']
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

            # Generate a unique ID
            id = uuid.uuid4()

            # Create a new ChatHeader instance
            chat_header = ChatHeader.objects.create(
                id=id,  # Ensure this is unique
                userId=userId,
                name=f"Chat__{id}",
                type='Student',  # or 'Teacher' depending on your logic
                class_name=className,
                subject=keys,
                chapter=chapterName,
                category="Revision",
                threads=threadData  # Assuming an empty JSON object for new creation
            )

            addRevisionChats(chat_header, data[keys])

## manages the generated revision data and adds them to the correct chatHeader
def addRevisionChats(chatHeader, data):
    print("THE ID FOR CHAT HEADER IS", chatHeader.id, " ---  chats data is ", data)
    chapterName = data[0]['chapter']
    threadData = []

    for d in data[1:]:
        for key, value in d.items():
            getRevisionChats(key, value, chatHeader, chapterName)

## gets the generated revision chats and QnA from gpt
def getRevisionChats(conceptCovered, data, chat_header, chapterName):

    chapter = get_object_or_404(Chapter, name=chat_header.chapter)

    print("DATA IS getRevisionChats", data)

    for batch in iterate_in_batches(data, 3):
        print(batch)

        query = f'''
            Given the following set of Question Answer pairs from the chapter "{chapterName}":
            
            Question Answer pairs:
            {batch}
            
            Generate a single question that helps to revise the concepts covered in the above question-answer pairs. The question should be comprehensive and cover the main points from each pair. The nature of the question should look as if a person asked it.

            The format should be strictly:
            {{
                "user": "Generated question that summarizes the batch and prompts the user to recall the answers",
                "answer": "A comprehensive answer that encapsulates the main points from the batch of question-answer pairs"
            }}
        '''

        threadId = chat_header.threads['Ask Textbooks']

        message = client.beta.threads.messages.create(
            thread_id=threadId,
            role="user",
            content=query,
        )

        assistantId = chapter.assistant['Ask Textbooks']

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

        print("THE NEW REVISION MESSAGE IS", new_message)

        extractedResponse = extract_response(new_message)

        print(extractedResponse, " ---==== ", type(extractedResponse), " 000000 ", extractedResponse.get('user'), " 1111 ", extractedResponse.get('answer'))

        referencetext = None
        try:
            referencetext = ChapterReferenceText.objects.get(conceptName=conceptCovered)
            print("THE REFERENCE CHUNK IS =====>", referencetext.chunk_text)
        except ChapterReferenceText.DoesNotExist:
            print("No reference text found for the given concept.")
        referenceData = getReferenceTextSpanId(referencetext.chunk_text, chat_header.id)

        newChat = Chats.objects.create(
            user = {"question" : extractedResponse.get('user')},
            eduGpt = {"answer" : extractedResponse.get('answer')},
            chat_header = chat_header,
            snipData = {},
            referenceData = {"referenceData" : referenceData},
            conceptCovered=conceptCovered,
            usedForRevision=True,
            ques_type=Chats.QuestionType.NORMAL_QUESTION
        )

        testContext = f'''
            Given the following set of Question Answer pairs from the chapter "{chapterName} as the context":
            
            Question Answer pairs:
            {batch}
                        '''
        random_integer = random.randint(1, 5)
        testQuery  = generate_random_question_query(random_integer)

        testJson = getTests(testContext, testQuery, chat_header.id)
        testJson = json.dumps(testJson)
        print("THE TEST JSON IS 99999 ", testJson, " ------ ", type(testJson))

        # Create the new structure
        transformed_json = {
            "answer": json.dumps({
                "type": "Quiz",
                "Qestions": testJson
            })
        }

        newChatTest = Chats.objects.create(
            user = {"question" : testQuery},
            eduGpt = transformed_json,
            chat_header = chat_header,
            snipData = {},
            referenceData = {"referenceData" : referenceData},
            conceptCovered=conceptCovered,
            ques_type=Chats.QuestionType.QUIZ
        )
