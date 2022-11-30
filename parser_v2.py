
from openpecha.core.pecha import OpenPechaFS
from bs4 import BeautifulSoup
from openpecha.core.ids import get_initial_pecha_id,get_base_id
from openpecha.core.layer import Layer, LayerEnum
from openpecha.core.annotation import AnnBase, Span
from openpecha import github_utils,config
from openpecha.core.metadata import InitialPechaMetadata,InitialCreationType
from serialize_to_tmx import Tmx
from datetime import datetime
from uuid import uuid4
from index import Alignment
from pathlib import Path
from zipfile import ZipFile
from index import Alignment
import re
import requests
import logging
import csv



class LHParser(Alignment):
    start_url = 'https://www.lotsawahouse.org'
    root_path = "./root"

    def __init__(self,root_path):
        self.root_opf_path = f"{root_path}/opfs"
        self.root_tmx_path = f"{root_path}/tmx"
        self.root_tmx_zip_path = f"{root_path}/tmxZip"
        self.source_path = f"{root_path}/sourceFile"
        super().__init__(root_path)

    @staticmethod
    def make_request(url):
        response = requests.get(url)
        soup = BeautifulSoup(response.content,'html.parser')
        return soup
    
    @staticmethod
    def set_up_logger(logger_name):
        logger = logging.getLogger(logger_name)
        formatter = logging.Formatter("%(message)s")
        fileHandler = logging.FileHandler(f"{logger_name}.log")
        fileHandler.setFormatter(formatter)
        logger.setLevel(logging.INFO)
        logger.addHandler(fileHandler)

        return logger
    
    def parse_home(self,url):
        page = self.make_request(url)
        headers = page.select('div#header-links1 a')
        for header in headers:
            if header.get_text() == "Translations":
                return url+header['href']


    def get_links(self,url):
        links = {}
        page = self.make_request(url)
        main_divs = page.select_one('div#maintext')
        comp_names = main_divs.select('h2 a,h3 a')
        for comp_name in comp_names:
            links_list = []
            if comp_name.parent.find_next_sibling('ul').find_all('li'):
                main_name = comp_name.get_text().strip()
                for elem in comp_name.parent.find_next_sibling('ul').select('li a'):
                    links_list.append(elem['href'])
                links.update({main_name:links_list})
            else:
                main_name = comp_name.get_text()
                links_list.append(comp_name['href'])
                links.update({main_name:links_list})
        return links 


    def parse_collection(self,url):
        collection_page = self.make_request(url)
        self.collection_name = collection_page.select_one('div#content h1').text
        self.collection_description = collection_page.select_one("div#content b").text.strip("\n")
        main_div = collection_page.find('div',{'id':'content'})
        pecha_links = main_div.select('div.index-container ul li>a')
        for pecha_link in pecha_links:
            self.parse_page_content(pecha_link.get("href"))


    def parse_collection(self,url):
        collection_page = self.make_request(url)
        self.collection_name = collection_page.select_one('div#content h1').text
        self.collection_description = collection_page.select_one("div#content b").text.strip("\n")
        main_div = collection_page.find('div',{'id':'content'})
        pecha_links = main_div.select('div.index-container ul li>a')
        for pecha_link in pecha_links:
            self.parse_page_content(self.start_url+pecha_link.get("href"))

    def get_lang_code(self,lang):
        code = ""
        if lang == "བོད་ཡིག":
            code = "bo"
        elif lang == "English":
            code = "en"
        elif lang == "Deutsch":
            code = "de"  
        elif lang == "Español":
            code = "es"
        elif lang == "Français":
            code = "fr"
        elif lang == "Italiano":
            code = "it"                 
        elif lang == "Nederlands":
            code = "nl"
        elif lang == "Português":
            code = "pt"
        elif lang =="中文":
            code ="zh"
        else:
            code = "un"

        return code

    def parse_page_content(self,url):
        page = self.make_request(url)
        source_file = {}
        base_text = {}
        has_alignment = []
        lang_elems = page.select('p#lang-list a')
        language_pages = [[self.get_lang_code(lang_elem.text),lang_elem['href']] for lang_elem in lang_elems]

        for language_page in language_pages:
            lang,href = language_page
            self.extract_page_text(self.start_url+href,lang)
    
    def extract_page_text(self,url,lang):
        base_text = ""
        page = self.make_request(url)
        div_main = page.select_one('div#maintext')
        childrens = div_main.findChildren(recursive=False)
        if len(childrens) == 1 and childrens[0].name == "div":
            childrens = childrens[0].findChildren(recursive=False)
        
        for children in childrens



    def main(self):
        self.pechas_catalog = self.set_up_logger("pechas_catalog")
        self.alignment_catalog =self.set_up_logger("alignment_catalog")
        self.err_log = self.set_up_logger('err')
        translation_page = self.parse_home(self.start_url)
        links = self.get_links(translation_page)
        bool_try = None
        for link in links:
            main_title = link
            pecha_links = links[link] 
            
            for pecha_link in pecha_links:
                """ if self.start_url+pecha_link == "https://www.lotsawahouse.org/topics/bodhicharyavatara":
                    bool_try = True
                else:
                    bool_try = False
                if not bool_try:
                    continue  """  
                
                self.parse_collection(self.start_url+pecha_link)  
                break
            break

if __name__ == "__main__":
    obj = LHParser("./root")
    obj.main()