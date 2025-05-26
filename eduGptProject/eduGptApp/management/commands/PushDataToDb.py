import json
from django.core.management.base import BaseCommand
from eduGptApp.models import School, Subject, Book, Chapter, SchoolClass
from pathlib import Path

# Assuming insert_json_into_model function is defined here, or import it if it's defined elsewhere
def insert_json_into_model(data, model, instance=None):
    """
    Inserts or updates a single JSON object into the specified Django model.
    If an instance is provided, updates it with data instead of creating a new one.

    Args:
    - data: dict representing a single JSON object.
    - model: Django model class to insert data into.
    - instance: Existing model instance to update (optional).
    """
    try:
        if instance:
            for key, value in data.items():
                setattr(instance, key, value)
            instance.save()
        else:
            instance = model.objects.create(**data)

        print(f"Successfully processed {model.__name__}: {data}")
        return instance
    except Exception as e:
        print(f"Error processing {model.__name__}: {str(e)}")
        return None




class Command(BaseCommand):
    help = 'Load JSON data into the School model from a local data.json file'

    def handle(self, *args, **kwargs):
        # Directly reference data.json since it's in the same directory
        json_file_path = Path(__file__).resolve().parent / 'dbLoadData/data.json'
        
        if not json_file_path.is_file():
            self.stdout.write(self.style.ERROR(f'File {json_file_path} does not exist'))
            return

        with open(json_file_path, 'r') as file:
            data = json.load(file)
            
            school_data = data.get("School", [])
            if school_data:
                for item in school_data:
                    insert_json_into_model(item, School)
                self.stdout.write(self.style.SUCCESS('Successfully loaded all data into the School database'))
            else:
                self.stdout.write(self.style.ERROR('No "School" key found in JSON data'))

            subject_data = data.get("Subjects", [])
            if subject_data:
                for item in subject_data:
                    # Attempt to attach the School instance to the item before insertion
                    try:
                        school_instance = School.objects.get(id=item['school'])
                        item['school'] = school_instance  # Replace the ID with the actual instance
                        insert_json_into_model(item, Subject)
                    except School.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f'School with ID {item["school"]} does not exist. Skipping subject {item["name"]}.'))
                        continue  # Skip this item if the corresponding school does not exist
                self.stdout.write(self.style.SUCCESS('Successfully loaded all data into the Subject database'))
            else:
                self.stdout.write(self.style.ERROR('No "Subject" key found in JSON data'))

            books_data = data.get("Books", [])
            if books_data:
                for item in books_data:
                    insert_json_into_model(item, Book)
                self.stdout.write(self.style.SUCCESS('Successfully loaded all data into the Book database'))
            else:
                self.stdout.write(self.style.ERROR('No "Book" key found in JSON data'))

            chapter_data = data.get("Chapters", [])
            if chapter_data:
                for item in chapter_data:
                    # Attempt to attach the School instance to the item before insertion
                    try:
                        book_instance = Book.objects.get(id=item['book'])
                        item['book'] = book_instance  # Replace the ID with the actual instance
                        insert_json_into_model(item, Chapter)
                    except Chapter.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f'Book with ID {item["book"]} does not exist. Skipping Chapter {item["name"]}.'))
                        continue  # Skip this item if the corresponding school does not exist
                self.stdout.write(self.style.SUCCESS('Successfully loaded all data into the Chapter database'))
            else:
                self.stdout.write(self.style.ERROR('No "Chapter" key found in JSON data'))

            school_class_data = data.get("SchoolClass", [])
            if school_class_data:
                for item in school_class_data:
                    # Attempt to find the corresponding School instance
                    try:
                        school_instance = School.objects.get(id=item['school'])
                    except School.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f'School with ID {item["school"]} does not exist. Skipping SchoolClass {item["designation"]}.'))
                        continue

                    # Create SchoolClass instance (without subjects for now)
                    school_class_instance, created = SchoolClass.objects.get_or_create(
                        designation=item['designation'],
                        school=school_instance,
                        defaults={'books': item['books']}
                    )

                    if not created:
                        self.stdout.write(self.style.SUCCESS(f'SchoolClass {item["designation"]} already exists. Updating information.'))
                        # Assuming you might want to update 'books' or other fields here
                        school_class_instance.books = item['books']
                        school_class_instance.save()

                    # Now handle the many-to-many 'subjects' relationship
                    subject_instances = Subject.objects.filter(id__in=item.get('subjects', []))
                    school_class_instance.subjects.set(subject_instances)  # This properly handles the M2M relationship

                    self.stdout.write(self.style.SUCCESS(f'Successfully loaded SchoolClass {item["designation"]} into the database'))
            else:
                self.stdout.write(self.style.ERROR('No "SchoolClass" key found in JSON data'))
