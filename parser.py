from cgi import test
from ctypes import alignment
from email.mime import base
from pydoc import pager
from socket import has_dualstack_ipv6
from urllib import response
from bs4 import BeautifulSoup
from openpecha.core.ids import get_initial_pecha_id,get_base_id
from openpecha.core.layer import Layer, LayerEnum
from openpecha.core.pecha import OpenPechaFS 
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

    def parse_page(self,url):
        page_meta={}
        has_alignment = {}
        base_chapter_map =[]
        page = self.make_request(url)
        lang_elems = page.select('p#lang-list a')
        langs = [lang_elem.text for lang_elem in lang_elems]
        self.pecha_name = page.select_one('div#content h1').text
        self.pecha_ids = self.get_pecha_ids(langs)
        page_meta.update({
            "main_title":page.select_one('div#content h1').text,
            "description":page.select_one("div#content b").text.strip("\n")
            })
        main_div = page.find('div',{'id':'content'})
        headings = main_div.find_all('h4')
        print(self.pecha_name)
        order = 1
        if not headings:
            chapter_elems = main_div.select('div.index-container > ul > li > a:first-child')
            h_a,base_chapter_map,order= self.get_chapters(chapter_elems,order)
            has_alignment.update(h_a)

        for heading in headings:
            if heading.get_text() == "Related Topics":
                continue
            chapter_elems = heading.find_next_sibling('div').select('ul > li > a:first-child')
            heading_title = heading.get_text()
            h_a,b_c,order = self.get_chapters(chapter_elems,order,heading_title)
            base_chapter_map.extend(b_c)
            has_alignment.update(h_a) 
        
        for pecha_id in self.pecha_ids:
            self.create_meta(pecha_id,page_meta,base_chapter_map)
            self.create_readme(pecha_id)

        return has_alignment


    def get_chapters(self,chapter_elems,order,heading_title=None):
        has_alignment = {}
        base_chapter_map = []
        for chapter_elem in chapter_elems:
            base_id = get_base_id()
            chapter = chapter_elem.text
            base_chapter_map.append([base_id,chapter,order,heading_title])
            href = chapter_elem['href']
            base_text,bool_alignment = self.get_text(self.start_url+href)
            if bool_alignment:
                has_alignment.update({base_id:bool_alignment})
            for pecha_id in self.pecha_ids:
                language,pechaid = pecha_id
                if language in base_text:
                    try:
                        self.create_opf(pechaid,base_text[language],base_id)
                    except:
                        self.err_log.info(f"Opf Error : {self.pecha_name}:{chapter}:{language}") 
            order+=1
        return has_alignment,base_chapter_map,order


    def get_text(self,url):
        page = self.make_request(url)
        base_text = {}
        has_alignment = []
        lang_elems = page.select('p#lang-list a')
        language_pages = [[lang_elem.text,lang_elem['href']] for lang_elem in lang_elems]
        for language_page in language_pages:
            language,href = language_page
            lang_code = self.get_lang_code(language)
            text,bool_alignment = self.extract_page_text(self.start_url+href,lang_code,has_alignment)
            if bool_alignment == True:
                has_alignment.append(lang_code) 
            base_text.update({lang_code :text})
        if has_alignment:
            has_alignment.append("bo")
        return base_text,has_alignment

    
    def extract_page_text(self,url,lang_code,prev_alignment):
        base_text=""
        has_alignment = None
        page = self.make_request(url)
        div_main = page.select_one('div#maintext')
        childrens = div_main.findChildren(recursive=False)
        if len(childrens) == 1 and childrens[0].name == "div":
            childrens = childrens[0].findChildren(recursive=False)
        for children in childrens:
            text = self.remove_endlines(children.get_text())
            if children.has_attr('class'):
                if children['class'][0] in ('HeadingTib','TibetanVerse','TibetanExplanation') and lang_code != "bo":
                    has_alignment=True
                    continue
            if text in ("Bibliography","Bibliographie"):
                break
            elif text == "\xa0":
                base_text+="\n"
                continue
            elif text == "":
                continue
            if len(text)>90:
                text = self.change_text_format(text)
            base_text+=text.strip(" ")
            base_text+="\n\n" if has_alignment != True and not prev_alignment else "\n"

        return base_text.strip("\n").strip(),has_alignment

    
    def create_opf(self,pecha_id,base_text,chapter):
        opf_path = f"{self.root_opf_path}/{pecha_id}/{pecha_id}.opf"
        opf = OpenPechaFS(path=opf_path)
        bases= {f"{chapter}":base_text}
        opf.base = bases
        opf.save_base()
        layers = {f"{chapter}": {LayerEnum.segment: self.get_segment_layer(base_text)}}
        opf.layers = layers
        opf.save_layers()

    def get_segment_layer(self,base_text):
        segment_annotations= {}
        char_walker = 0
        splited_texts = base_text.split("\n\n")
        for text in splited_texts:
            if text == "":
                continue
            segment_annotation,char_walker = self.get_segment_annotation(char_walker,text)
            segment_annotations.update(segment_annotation)
        segment_layer = Layer(annotation_type= LayerEnum.segment,annotations=segment_annotations)   

        return segment_layer 


    def get_segment_annotation(self,char_walker,text):
        start = char_walker
        end = char_walker +len(text)
        segment_annotation = {uuid4().hex:AnnBase(span=Span(start=start,end=end))}
        return (segment_annotation,end+2)

    def create_meta(self,pecha_id,page_meta,base_chapter_map):
        lang,pechaid = pecha_id
        opf_path = f"{self.root_opf_path}/{pechaid}/{pechaid}.opf"
        opf = OpenPechaFS(path=opf_path)
        base_meta = self.get_base_meta(base_chapter_map)
        instance_meta = InitialPechaMetadata(
            id=pechaid,
            initial_creation_type=InitialCreationType.input,
            source_metadata={
                "title":page_meta['main_title'],
                "language": lang,
                "description":page_meta["description"],
                "volume":base_meta
            })    

        opf._meta = instance_meta
        opf.save_meta()

    def create_readme(self,pecha_id):
        lang,pechaid = pecha_id
        id = f"|pecha id | {pechaid}"
        Table = "| --- | --- "
        Title = f"|Title | {self.pecha_name} "
        language = f"|Languages | {lang}"
        readme = f"{id}\n{Table}\n{Title}\n{language}"
        Path(f"{self.root_opf_path}/{pechaid}/readme.md").write_text(readme)


    def get_base_meta(self,base_chapter_map):
        meta={}
        for base_cahapter in base_chapter_map:
            base_id,chapter,order,parent = base_cahapter
            meta.update({base_id:{
                "title":chapter,
                "base_file": f"{base_id}.txt",
                "order":order,
                "parent": parent,
            }}) 

        return meta

    @staticmethod
    def change_text_format(text):
        base_text=""
        prev= ""
        text = text.replace("\n","") 
        ranges = iter(range(len(text)))
        for i in ranges:
            if i<len(text)-1:
                if i%90 == 0 and i != 0 and re.search("\s",text[i+1]):
                    base_text+=text[i]+"\n"
                elif i%90 == 0 and i != 0 and re.search("\S",text[i+1]):
                    while i < len(text)-1 and re.search("\S",text[i+1]):
                        base_text+=text[i]
                        i = next(ranges) 
                    base_text+=text[i]+"\n" 
                elif prev == "\n" and re.search("\s",text[i]):
                    continue
                else:
                    base_text+=text[i]
            else:
                base_text+=text[i]
            prev = base_text[-1]
        return base_text[:-1] if base_text[-1] == "\n" else base_text

    @staticmethod
    def remove_endlines(text):
        prev = ''
        while prev != text.strip("\n"):
            prev =text.strip("\n")
        return prev 
    
    def get_pecha_ids(self,languages):
        pecha_ids = []
        for language in languages:
            lang_code = self.get_lang_code(language)
            pecha_ids.append([lang_code,get_initial_pecha_id()])
        return pecha_ids

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

    def get_alignment(self,pecha_ids,pecha_name,alignment):
        alignment_id,alignment_vol_map = self.create_alignment(pecha_ids,pecha_name,alignment)
        self.alignment_catalog.info(f"{alignment_id},{pecha_name}")
        self.create_csv(alignment_id,pecha_ids)
        tmx_zip_path = self.create_tmx(alignment_vol_map)
        return alignment_id,tmx_zip_path

    def create_csv(self,alignment_id,pecha_ids):
        filename = ""
        for i,pecha_id in enumerate(pecha_ids):
            lang,pechaid =pecha_id
            filename+=lang
            if len(pecha_ids) > i+1:
                filename+='-'
        with open(f"{self.root_opa_path}/{alignment_id}/{filename}.csv",'w') as f:
            writer = csv.writer(f)
            writer.writerow(["pecha id","language","url"])
            for pecha_id in pecha_ids:
                lang,pechaid = pecha_id
                url = f"https://github.com/OpenPecha/{pechaid}"
                writer.writerow([pechaid,lang,url])

    def create_tmx(self,alignment_vol_map):
        tmxObj = Tmx(self.root_opf_path,self.root_tmx_path)
        tmx_path = f"{self.root_tmx_path}/{self.pecha_name}"
        self._mkdir(Path(tmx_path))
        for map in alignment_vol_map:
            alignment,volume = map   
            tmxObj.create_tmx(alignment,volume,tmx_path)
        zip_path = self.create_tmx_zip(tmx_path)
        return zip_path    


    def create_tmx_zip(self,tmx_path):
        zip_path = f"{self.root_tmx_path}/{self.pecha_name}_tmx.zip"
        zipObj = ZipFile(zip_path, 'w')
        tmxs = list(Path(f"{tmx_path}").iterdir())
        for tmx in tmxs:
            zipObj.write(tmx)
        return zip_path

    @staticmethod
    def set_up_logger(logger_name):
        logger = logging.getLogger(logger_name)
        formatter = logging.Formatter("%(message)s")
        fileHandler = logging.FileHandler(f"{logger_name}.log")
        fileHandler.setFormatter(formatter)
        logger.setLevel(logging.INFO)
        logger.addHandler(fileHandler)

        return logger

    def main(self):
        self.pechas_catalog = self.set_up_logger("pechas_catalog")
        self.alignment_catalog =self.set_up_logger("alignment_catalog")
        self.err_log = self.set_up_logger('err')
        translation_page = self.parse_home(self.start_url)
        links = self.get_links(translation_page)

        for link in links:
            main_title = link
            print(main_title)
            pecha_links = links[link]
            
            for pecha_link in pecha_links:
                print(self.start_url+pecha_link)
                alignment = self.parse_page(self.start_url+pecha_link)
                for pecha_id in self.pecha_ids:
                    lang,pechaid =pecha_id
                    self.pechas_catalog.info(f"{pechaid},{lang},{self.pecha_name}")
                if bool(alignment):
                    print("HAS ALIGNMENT")
                    alignment_id,zipped_path = self.get_alignment(self.pecha_ids,self.pecha_name,alignment)
                break

                """ try:
                    pecha_ids,pecha_name,alignment = self.parse_page(self.start_url+pecha_link)
                    for pecha_id in pecha_ids:
                        lang,pechaid =pecha_id
                        self.pechas_catalog.info(f"{pechaid},{lang},{pecha_name}")
                        #publish_opf(pechaid)
                except:
                    self.err_log.info(f"main error: {self.start_url+pecha_link}")
                    pass
            
                if bool(alignment):
                    try:
                        alignment_id,zipped_path = self.create_alignment(pecha_ids,pecha_name,alignment)
                        #publish_opf(alignment_id)
                        #create_realease(alignment_id,zipped_path)
                    except:
                        self.err_log.info(f"alignment error: {pecha_name}") """


if __name__ == "__main__":
    obj = LHParser("./root")
    obj.main()