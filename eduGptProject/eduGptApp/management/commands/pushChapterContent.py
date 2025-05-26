from django.core.management.base import BaseCommand
from eduGptApp.models import ChapterContent, Chapter, ChapterReferenceData, ChapterReferenceText, ChapterImages
import os
import inspect
from openai import OpenAI
import json

client = OpenAI(api_key='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')


class Command(BaseCommand):
    help = 'Inserts HTML content into ChapterContent'

    def getEmbedding(self, text):
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )

        return response.data[0].embedding

    def split_html_by_div(self, html_string):
        # Your existing logic
        split_html = html_string.split('<div id="pf')
        split_html_corrected = [split_html[0]] + [f'<div id="pf{s}' for s in split_html[1:]]
        if len(split_html_corrected) > 1:
            split_html_corrected[0] += split_html_corrected[1]
            del split_html_corrected[1]
        return split_html_corrected

    def handle(self, *args, **kwargs):
        # Getting the directory where the current script is located
        current_script_directory = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

        # Path to the 'bookHtml' directory
        book_html_directory = os.path.join(current_script_directory, 'bookHtml')

        # Loop through each subdirectory in 'bookHtml'
        for subdir in os.listdir(book_html_directory):
            subdir_path = os.path.join(book_html_directory, subdir)

            # Ensure it's a directory
            if os.path.isdir(subdir_path):
        
            # Adjusting the path to the 'bookHtml/EngLit' directory
                directory_path = os.path.join(subdir_path)
                directory_path_ReferenceData =  os.path.join(current_script_directory, 'referenceData', subdir)
                directory_path_ReferenceText =  os.path.join(current_script_directory, 'referenceText', subdir)
                directory_path_SnipData = os.path.join(current_script_directory, 'snipData', subdir)
                
                print(directory_path)
                print(directory_path_ReferenceData)
                print(directory_path_ReferenceText)
                print(directory_path_SnipData)

                try:
                    for filename in os.listdir(directory_path):
                        if filename.endswith(".html"):
                            file_path = os.path.join(directory_path, filename)
                            with open(file_path, 'r', encoding='utf-8') as file:
                                html_content = file.read()
                            
                            split_content = self.split_html_by_div(html_content)
                            chapter_name = os.path.splitext(filename)[0].replace("_", " ")
                            chapter_instance, created = Chapter.objects.get_or_create(name=chapter_name)

                            referenceData_FilePath = os.path.join(directory_path_ReferenceData, filename.split(".")[0] + ".json")
                            referenceText_FilePath = os.path.join(directory_path_ReferenceText, filename.split(".")[0] + ".json")
                            snipData_FilePath = os.path.join(directory_path_SnipData, filename.split(".")[0] + ".json")

                            if os.path.exists(referenceData_FilePath):
                                with open(referenceData_FilePath, 'r', encoding='utf-8') as file:
                                    referenceData = file.read()
                                    ChapterReferenceData.objects.create(
                                        referenceData = referenceData,
                                        chapter=chapter_instance
                                    )
                            if os.path.exists(referenceText_FilePath):
                                with open(referenceText_FilePath, 'r', encoding='utf-8') as file:
                                    referenceData = json.load(file)

                                    for metadata, chunk_text in referenceData.items():
                                        # Compute the embedding for the chunk_text
                                        embedding = self.getEmbedding(chunk_text)
                                        
                                        # Create the ChapterReferenceText instance
                                        ChapterReferenceText.objects.create(
                                            chapter=chapter_instance,
                                            chunk_text=chunk_text,
                                            metadata=metadata,
                                            embedding=embedding,
                                            conceptName=metadata
                                        )

                                    self.stdout.write(self.style.SUCCESS('ChapterReferenceText instances created successfully'))
                                    
                            if os.path.exists(snipData_FilePath):
                                with open(snipData_FilePath, 'r', encoding='utf-8') as file:
                                    snipData = json.load(file)  # Parse the JSON data

                                    for entry in snipData:
                                        ChapterImages.objects.create(
                                            chapter=chapter_instance,
                                            snipImgUrl=entry.get('snipImgUrl', ''),
                                            snipImgName=entry.get('snipImgName', ''),
                                            description=entry.get('description', ''),
                                            relevantTextFromChapter=entry.get('relevantTextFromChapter', ''),
                                            scale=entry.get('scale', ''),
                                            imgNum=entry.get('imgNum', '')
                                        )

                            for index, data in enumerate(split_content):
                                ChapterContent.objects.create(
                                    htmlString=data,
                                    page=index + 1,
                                    chapter=chapter_instance
                                )

                            self.stdout.write(self.style.SUCCESS(f'Successfully inserted content for "{chapter_name}"'))
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'An error occurred: {e}'))
