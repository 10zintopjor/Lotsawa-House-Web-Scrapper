
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
from index import Alignment


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
            parrallel_pechas,has_alignment,pecha_name = self.parse_page_content(pecha_link)
            if has_alignment:
                self.create_opa(parrallel_pechas,pecha_name)
    
    def create_opa(self,parrallel_pechas:list,pecha_name):
        self.create_alignment(parrallel_pechas,pecha_name)

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

    def parse_page_content(self,pecha_link):
        page = self.make_request(self.start_url+pecha_link.get("href"))
        pecha_name = pecha_link.text
        source_file = {}
        base_texts = []
        has_alignment = False
        lang_elems = page.select('p#lang-list a')
        language_pages = [[self.get_lang_code(lang_elem.text),lang_elem['href']] for lang_elem in lang_elems]
        languages = []
        for language_page in language_pages:
            lang,href = language_page
            languages.append(lang)
            base_text,has_alignment = self.extract_page_text(self.start_url+href,lang,has_alignment)
            base_texts.append(base_text)

        if has_alignment:
            self.verify_alignmnet(base_texts)
            
        parrallel_pechas = self.create_multlingual_opf(base_texts,languages)
        return parrallel_pechas,has_alignment,pecha_name

    @staticmethod
    def verify_alignmnet(base_texts):
        it = iter(base_texts)
        the_len = len(next(it))
        if not all(len(l) == the_len for l in it):
            raise ValueError('not all lists have same length')

    def create_multlingual_opf(self,base_texts:list,langs:list):
        parrallel_pechas = []
        for base_text,lang in zip(base_texts,langs):
            pecha_id = get_initial_pecha_id()
            base_id = get_base_id()
            segment_annotaions = self.create_opf(pecha_id,base_id,base_text)
            parrallel_pechas.append({
            "pecha_id":pecha_id,
            "base_id":base_id,
            "annotations":segment_annotaions,
            "lang":lang})
        
        return parrallel_pechas

    def get_base_text(self,base_text_list:list):
        base_text = base_text_list[0]
        for text in base_text_list[1:]:
            base_text+="\n"+text

        return base_text

    def create_opf(self,pecha_id:str,base_id:str,base_text_list:list):
        opf_path = f"{self.root_opf_path}/{pecha_id}/{pecha_id}.opf"
        base_text = self.get_base_text(base_text_list)
        opf = OpenPechaFS(path=opf_path)
        opf.bases = {base_id:base_text}
        opf.save_base()
        segment_layer,segment_annotations = self.get_segment_layer(base_text_list)
        layers={f"{base_id}": {LayerEnum.segment: segment_layer}}
        opf.layers = layers
        opf.save_layers()
        return segment_annotations

    def get_segment_layer(self,base_text_list):
        segment_annotations = {}
        char_walker = 0 
        for text in base_text_list:
            if text == "":
                continue
            segment_annotation,char_walker = self.get_segment_annotation(char_walker,text) 
            segment_annotations.update(segment_annotation)
        segment_layer = Layer(annotation_type=LayerEnum.segment,annotations=segment_annotations)

        return segment_layer,segment_annotations
    
    def get_segment_annotation(self,char_walker,text):

        start = char_walker
        end = char_walker +len(text)

        segment_annotation = {uuid4().hex:AnnBase(span=Span(start=start,end=end))}
        return (segment_annotation,end+1)


    @staticmethod
    def remove_endlines(text):
        prev = ''
        while prev != text.strip("\n"):
            prev =text.strip("\n")
        return prev 


    def extract_page_text(self,url,lang,has_alignment):
        base_text = ""
        page = self.make_request(url)
        div_main = page.select_one('div#maintext')
        childrens = div_main.findChildren(recursive=False)
        if len(childrens) == 1 and childrens[0].name == "div":
            childrens = childrens[0].findChildren(recursive=False)

        if lang == "bo":
            base_text = self.parse_tibetan_page(childrens,has_alignment)
        else:
            base_text,has_alignment = self.parse_non_tibetan_page(childrens)    
        
        return base_text,has_alignment

    def parse_tibetan_page(self,elems,has_alignment):
        base_text = []
        for elem in elems:
            text = self.remove_endlines(elem.get_text())
            if has_alignment:
                if not elem.has_attr('class'):
                    continue
                if elem['class'][0] in ('HeadingTib','TibetanVerse'):
                    base_text.append(text)
            else:
                base_text.append(text.strip())
        
        return base_text

    def extract_text_from_tag(self,elem):
        base_text = ""
        texts = list(elem.stripped_strings)
        for text in texts:
            base_text+=" "+text
        clean_text = self.remove_endlines(base_text.strip())
        return clean_text
        

    def has_alignmnet(self,elems):
        has_alignment = False
        for elem in elems:
            if not elem.has_attr('class'):
                continue
            elif elem['class'][0] in ('HeadingTib','TibetanVerse','TibetanExplanation'):
                has_alignment=True
                return has_alignment
        
        return has_alignment
    
    def parse_aligned_page(self,elems):
        base_text = []
        heading = ""
        skipped_class = ["HeadingTib","TibetanVerse","TibetanExplanation","EnglishPhonetics","Credit","Explanation","Footnote","Bibliography","Bibliographie"]
        for elem in elems:
            text = self.extract_text_from_tag(elem)
            if not elem.has_attr('class'):
                continue
            elif elem['class'][0] in skipped_class:
                continue
            elif text == "":
                continue
            elif elem['class'][0] == "Heading3":
                heading+=" "+text
                continue
            base_text.append(text.strip())
        
        if heading:
            base_text.insert(0,heading.strip())
        return base_text

    def parse_nonaligned_page(self,elems):
        base_text = []
        for elem in elems:
            base_text.append(elem.text.strip())
        return base_text

    def parse_non_tibetan_page(self,elems):
        has_alignment = self.has_alignmnet(elems)
        if has_alignment:
            base_text = self.parse_aligned_page(elems)
        else:
            base_text = self.parse_nonaligned_page(elems)

        return base_text,has_alignment

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
    #obj.parse_page_content("https://www.lotsawahouse.org/tibetan-masters/adeu-rinpoche/white-jambhala")
    #obj.parse_collection("https://www.lotsawahouse.org/tibetan-masters/dilgo-khyentse/")