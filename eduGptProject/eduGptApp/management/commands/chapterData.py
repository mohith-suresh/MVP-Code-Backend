import os
from django.conf import settings
import json

def split_html_by_div(html_string):
    # Splitting the HTML string by "<div id="pf"
    split_html = html_string.split('<div id="pf')

    # Prepending '<div id="pf' to all split parts except the first one to reconstruct the original divisions
    split_html_corrected = [split_html[0]] + [f'<div id="pf{s}' for s in split_html[1:]]

    # Concatenating the 0th and 1st indices for the final result, and adjusting the rest of the list accordingly
    if len(split_html_corrected) > 1:
        split_html_corrected[0] += split_html_corrected[1]
        del split_html_corrected[1]

    return split_html_corrected


# Using Django's BASE_DIR setting to construct the path to the folder dynamically
directory_path = os.path.join(settings.BASE_DIR, 'eduGptProject', 'eduGptApp', 'management', 'commands', 'bookHtml', 'EngLit')

json_data = {}

for filename in os.listdir(directory_path):
    if filename.endswith(".html"):
        file_path = os.path.join(directory_path, filename)
        
        with open(file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        base_name = os.path.splitext(os.path.basename(filename))[0]
        
        json_data[base_name] = split_html_by_div(html_content)

json_string = json.dumps(json_data, indent=4)
print(json_string)