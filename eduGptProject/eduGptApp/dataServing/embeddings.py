from django.core.management.base import BaseCommand

import pandas as pd
from openai import OpenAI
import scipy.spatial.distance as sp
import json,os
import ast
import numpy as np
import inspect

# Construct the path to the JSON file dynamically
current_script_directory = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

# Initialize OpenAI client
client = OpenAI(api_key='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')

def readEmbeddingJsonFile(file_path):
    # Read the JSON file
    with open(file_path, 'r') as file:
        data = json.load(file)
    
    questions = []
    assistants = []
    for d in data:
        user_content = d["messages"][1]["content"]
        assistant_content = d["messages"][2]["content"]
        questions.append(user_content)
        assistants.append(assistant_content)

    return questions, assistants


def find_answer_from_json(QnA_file_path, reference_file_path, incident, question):
    """
    Reads a JSON file from the specified path and searches for an answer
    based on the given incident and question.

    Parameters:
    - file_path: The path to the JSON file.
    - incident: The incident to filter on.
    - question: The question to find the answer to.

    Returns:
    - The answer as a string if found.
    - A message indicating that the answer could not be found otherwise.
    """

    answer = []

    try:
        # Load the JSON data from the file
        with open(reference_file_path, 'r') as file:
            dataReference = json.load(file)

        for entry in dataReference:
            if entry["Label"] == incident:
                answer.append(entry["ExtractedText"])

        # Load the JSON data from the file
        with open(QnA_file_path, 'r') as file:
            data = json.load(file)

        # Search for the specified incident
        for entry in data:
            if entry["Incident"] == incident:
                # Within the incident, search for the question
                for qna in entry["QnA"]:
                    if qna["Question"] == question:
                        answer.append(qna["Answer"])
                        return answer
        
        return "Answer not found for the given incident and question."

    except FileNotFoundError:
        return f"File not found: {QnA_file_path}"
    except json.JSONDecodeError:
        return "Error decoding JSON from the file."
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"
    

def getReferenceText():
    pass

# Function to get embedding
def create_embedding(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model=model).data[0].embedding

def createDataFrame(user_list, assistant_list):
    df = pd.DataFrame({
        'question': user_list,
        'reference': assistant_list    
        })
    return df

def computeEmbeddingAndStore(df, csvFilePath):
    # Compute embeddings and store in the DataFrame
    df['ada_embedding'] = df['question'].apply(lambda x: create_embedding(x, model='text-embedding-3-small'))

    # Save the DataFrame to a CSV file
    df.to_csv(csvFilePath, index=False)

def search_reviews(df, product_description, n=3, pprint=True):
   embedding = create_embedding(product_description, model='text-embedding-3-small')
   df['similarities'] = df.ada_embedding.apply(lambda x: 1-sp.cosine(x, embedding))
   res = df.sort_values('similarities', ascending=False).head(n)
   res_with_reference = res[['question', 'reference', 'similarities']]
#    return res
   return res_with_reference

def convert_string_to_array(embed_str):
    try:
        return ast.literal_eval(embed_str)
    except:
        return np.nan  # or some other way to handle errors

def getAnswer(question):
    json_file_path = os.path.join(current_script_directory, 'chapterData/embeddingJsonData/theLastLesson.json')
    csv_file_path = os.path.join(current_script_directory, 'chapterData/csvData/theLastLesson.csv')
    QnA_file_path =  os.path.join(current_script_directory, 'chapterData/QnAData/theLastLesson.json')
    reference_file_path = os.path.join(current_script_directory, 'chapterData/referenceData/theLastLesson.json')

    # Check if the CSV file already exists
    if not os.path.exists(csv_file_path):
        questions, assistants = readEmbeddingJsonFile(json_file_path)
        df = createDataFrame(questions, assistants)
        computeEmbeddingAndStore(df, csv_file_path)
    else:
        # Read the existing CSV file into a DataFrame
        df = pd.read_csv(csv_file_path)
        df['ada_embedding'] = df['ada_embedding'].apply(convert_string_to_array)

    res = search_reviews(df, question, n=3)

    main_reference = res['reference'].iloc[0]
    main_question = res['question'].iloc[0]
    QnA_file_path =  os.path.join(current_script_directory, 'chapterData/QnAData/theLastLesson.json')
    answer = find_answer_from_json(QnA_file_path, reference_file_path, main_reference, main_question)
    return answer
    # print("REFERENCE IS:", answer[0])
    # print("CLOSEST ANSWER IS:", answer[1])

if __name__ == "__main__":
    getAnswer("Why was Franz afraid?")