import json
import argparse

ASCII_JSON_PATH = 'ascii_art.json'

parser = argparse.ArgumentParser(description='Adds ASCII art to ascii_art.json under given name', epilog='Example usage: ascii_add.py shipit.txt ship')
parser.add_argument('ascii_file', help='path to ASCII art text to add')
parser.add_argument('ascii_name', help='name for ASCII art to be added')


args = parser.parse_args()

# open text file and flatten ascii art into one string 
ascii_textfile = open(args.ascii_file)
ascii_text = ''
for line in ascii_textfile:
	ascii_text += line
ascii_textfile.close()

# dump into json under given ascii_name

ascii_json_file = open(ASCII_JSON_PATH)
ascii_json = json.load(ascii_json_file)
ascii_json_file.close()
ascii_json_file = open(ASCII_JSON_PATH, 'w')
found = False
for pair in ascii_json:
    if pair['name'] == args.ascii_name:
        pair['text'] = ascii_text
        found = True
        break
if found == False:
    ascii_json.append({'name': args.ascii_name, 'text': ascii_text})
json.dump(ascii_json, ascii_json_file)
ascii_json_file.close()
