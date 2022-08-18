from urllib import response
from openpecha import github_utils
import csv
import requests
from pathlib import Path
from pkg_resources import DEVELOP_DIST


def get_ids(path):
    github_utils.delete_repo(path)
    print("deleted")
            

def remove_duplicates():
    del_id = []
    to_insert = []

    with open("tobedelete.csv","r") as f:
        obj = csv.reader(f)
        for row in obj:
            del_id.append(row[0])

    with open("pechas_catalog.csv","r") as f1:
        obj1 = csv.reader(f1)
        for row1 in obj1:
            if row1[0] not in del_id:
                to_insert.append(row1)

    with open("new_pechas_catalog.csv","w") as f:
        obj =csv.writer(f)
        for elem in to_insert:
            obj.writerow(elem)

def check_url():
    new_li =[]
    with open("old_alignment_catalog.csv","r") as f:
        obj =csv.reader(f)
        for row in obj:
            try:
                response = requests.get(row[2])
                print("wokring ",row[0])
            except:
                print("Failed ",row[0])
                pass

    """ with open("id.csv","w") as f:
        obj =csv.writer(f) 
        for row in new_li:
            obj.writerow(row) """


if __name__ == "__main__":
     with open("alignment_catalog.csv","r") as f1:
        obj1 = csv.reader(f1)
        for row1 in obj1:
            get_ids(row1[0])
    #remove_duplicates()
    #check_url()