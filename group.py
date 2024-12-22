

import json
import re
from icecream import ic
import pandas

groups = []
groups_with_realm = []

def process_file():
    with open("/Users/bwidjojo/Downloads/combined-group.txt","r") as f:
        for line in f.readlines():
            # ic (line)
            match = re.search('group=\"(.+)\"',line)
            if match:
                group = match.group(1)
                # ic(group)
                groups_with_realm.append(group)
                if "\\" in group:
                    groups.append(group.split('\\')[1])
                else:
                    groups.append(group) 
               
    # ic(set(groups))

def process_json():
    # json_file = "/Users/bwidjojo/scripts/panos-to-scm/1914731146-scm-post-rules-2024-11-25_10-56-3.json"
    json_file = "/Users/bwidjojo/scripts/panos-to-scm/1914731146-scm-post-rules-2024-12-11_18-44-41.json"
    df = pandas.read_json(json_file)
    for index, rows in df.iterrows():
        for source_user in rows['source_user']:
            if source_user in groups_with_realm:
                print (f"found group {source_user} in rule {rows['name']}")
            # ic(source_user)
    df.to_excel("/Users/bwidjojo/Downloads/all-rules.xlsx")

process_file()
process_json()
