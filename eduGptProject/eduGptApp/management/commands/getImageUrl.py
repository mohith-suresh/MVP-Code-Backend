from django.core.management.base import BaseCommand
import base64, os, inspect, json
from eduGptApp.models import ChapterContent, Chapter
from django.core.exceptions import ObjectDoesNotExist


current_script_directory = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

def generate_base64_image_url(image_path):
    """
    Encodes an image to a Base64 URL.

    Args:
    - image_path (str): The path to the image file.

    Returns:
    - str: A Base64-encoded image URL.
    """
    # Determine the image format based on the file extension (simplistic approach)
    image_format = image_path.split('.')[-1].lower()
    if image_format not in ['png', 'jpeg', 'jpg', 'gif']:
        raise ValueError("Unsupported image format")

    # Open the image file in binary-read mode and read its contents
    with open(image_path, 'rb') as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')

    # Construct the full Base64 URL
    base64_url = f"data:image/{image_format};base64,{encoded_string}"

    return base64_url

def pushChapterContent(id, json_file_path):
    """
    Load chapter content data from a JSON file and save it to the database.
    Args:
    - json_file_path (str): Path to the JSON file containing chapter content data.
    """
    try:
        chapter = Chapter.objects.get(pk=id)
    except ObjectDoesNotExist:
        print(f"Chapter with {id} does not exist.")
        return

    with open(json_file_path, 'r') as file:
        data = json.load(file)

    for d in data:
        ChapterContent.objects.update_or_create(
            text=d.get('text'),
            img=d.get('img'),
            img_width=d.get('img_width'),
            img_height=d.get('img_height'),  # Assuming this key exists in your data
            left=d.get('left', False),  # Provide a default in case it's missing
            chapter=chapter
        )

    print("Successfully loaded chapter content into the database.")

def main(image_path, json_file_path):
    base64_image_url = generate_base64_image_url(image_path)

    with open(json_file_path, 'r') as file:
        data = json.load(file)

    for d in data:
        d["img"] = base64_image_url

    with open(json_file_path, 'w') as file:
        json.dump(data, file, indent=4)

    print(base64_image_url)



class Command(BaseCommand):
    help = 'Checks if management commands are working.'

    def handle(self, *args, **kwargs):
        # img_folder_file_path = os.path.join(current_script_directory, 'chapterData/chapterText/theLastLesson/images/img_01.jpg')
        # main(img_folder_file_path)

        json_file_path = os.path.join(current_script_directory, 'chapterData/chapterText/theLastLesson/chapter3.json')
        
        pushChapterContent(3, json_file_path)

        self.stdout.write(self.style.SUCCESS('Management command is working fine!'))
