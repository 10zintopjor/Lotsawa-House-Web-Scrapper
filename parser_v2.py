
from openpecha.core.pecha import OpenPechaFS
from bs4 import BeautifulSoup
from openpecha.core.ids import get_initial_pecha_id,get_base_id
from openpecha.core.layer import Layer, LayerEnum
from openpecha.core.annotation import AnnBase, Span
from openpecha import github_utils,config
from openpecha.utils import load_yaml,dump_yaml
from openpecha.core.metadata import InitialPechaMetadata,InitialCreationType
from serialize_to_tmx import Tmx
from datetime import datetime
from uuid import uuid4
from index import Alignment
from pathlib import Path
from zipfile import ZipFile
from index import Alignment
import re
import shutil
import requests
import logging
import csv
import os
import itertools
from index import Alignment


def set_up_logger(logger_name):
    logger = logging.getLogger(logger_name)
    formatter = logging.Formatter("%(message)s")
    fileHandler = logging.FileHandler(f"./logs/{logger_name}.log")
    fileHandler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(fileHandler)

    return logger

pechas_catalog = set_up_logger("pechas_catalog")
alignment_catalog =set_up_logger("alignment_catalog")
err_log = set_up_logger('err')

class LHParser(Alignment):
    start_url = 'https://www.lotsawahouse.org'
    root_path = "./zot_dir"

    def __init__(self):
        self.root_opf_path = f"{self.root_path}/opfs"
        self.root_tmx_path = f"{self.root_path}/tmx"
        self.root_tmx_zip_path = f"{self.root_path}/tmxZip"
        self.root_source_path = f"{self.root_path}/source"
        super().__init__(self.root_path)

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


    def parse_collection(self,url):
        has_alignment = None
        collection_page = self.make_request(url)
        self.collection_name = collection_page.select_one('div#content h1').text
        self.collection_description = collection_page.select_one("div#content b").text.strip("\n")
        main_div = collection_page.find('div',{'id':'content'})
        pecha_links = main_div.select('div.index-container ul li>a:first-child')
        for pecha_link in pecha_links:
            try:
                print("    "+pecha_link.text)
                parrallel_pechas,has_alignment,pecha_name = self.parse_page_content(pecha_link.get("href"),pecha_link.text)
            except Exception as e:
                err_log.info(f"{pecha_link.get('href')},{e}")
            if has_alignment:
                alignment_id,_ = self.create_alignment(parrallel_pechas,pecha_name)
                #tmx_path = self.create_tmx(alignments,pecha_name)
                publish_repo(Path(f"{self.root_opa_path}/{alignment_id}"))
                alignment_catalog.info(f"{alignment_id},{pecha_name},https://github.com/OpenPecha-Data/{alignment_id}")
                print(f"{pecha_name} ALIGNMENT CREATED")
                self.update_collection(alignment_id)
            else:
                for pecha in parrallel_pechas:
                    self.update_collection(pecha['pecha_id'])

    def update_collection(self,item_id):
        collection_yml_path = Path("./logs/collections.yml")
        if os.path.exists("./logs/collections.yml"):
            collections_dict = load_yaml(collection_yml_path)
        else:
            collections_dict = {}

        if self.collection_name in collections_dict.keys():
            new_list = collections_dict[self.collection_name]
            new_list.append(item_id)
            collections_dict[self.collection_name] = new_list
        else:
            collections_dict[self.collection_name] = [item_id]
        if self.main_collection in collections_dict.keys():
            new_list = collections_dict[self.main_collection]
            new_list.append(item_id)
            collections_dict[self.main_collection]  = new_list
        else:
            collections_dict[self.main_collection] = [item_id]
        dump_yaml(collections_dict,collection_yml_path)


        
    def create_tmx(self,alignments,pecha_name):
        tmxObj = Tmx(self.root_opf_path,self.root_tmx_path)
        self._mkdir(Path(self.root_tmx_path))
        tmx_path = tmxObj.create_tmx(alignments,pecha_name.replace(" ","_"))
        return tmx_path

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

    def parse_page_content(self,pecha_link,pecha_name):
        page = self.make_request(self.start_url+pecha_link)
        page_urls = []
        base_texts = []
        has_alignment = False
        lang_elems = page.select('p#lang-list a')
        language_pages = [[self.get_lang_code(lang_elem.text),lang_elem['href']] for lang_elem in lang_elems]
        languages = []
        for language_page in language_pages:
            lang,href = language_page
            base_text,has_alignment = self.extract_page_text(self.start_url+href,lang,has_alignment)
            base_texts.append(base_text)
            languages.append(lang)
            page_urls.append(self.start_url+href)
        #self.test_base_text(base_texts)
        if has_alignment:
            has_alignment = self.verify_alignmnet(base_texts,pecha_link)
        parrallel_pechas = self.create_multlingual_opf(base_texts,languages,page_urls,pecha_name)
        return parrallel_pechas,has_alignment,pecha_name


    def test_base_text(self,base_texts):
        for combination in itertools.zip_longest(*base_texts):
            print(combination)

    @staticmethod
    def verify_alignmnet(base_texts,pecha_link):
        it = iter(base_texts)
        the_len = len(next(it))
        if not all(len(l) == the_len for l in it):
            err_log.info(f"{pecha_link},in")
            return False
        return True

    def create_multlingual_opf(self,base_texts:list,langs:list,page_urls:list,pecha_name:str):
        parrallel_pechas = []
        for base_text,lang,page_url in zip(base_texts,langs,page_urls):
            pecha_id = get_initial_pecha_id()
            base_id = get_base_id()
            segment_annotaions = self.create_opf(pecha_id,base_id,base_text,pecha_name,lang)
            self.create_readme(lang,pecha_name,pecha_id)
            source_file_path = self.create_source_file(pecha_id,page_url,base_id)
            publish_repo(Path(f"{self.root_opf_path}/{pecha_id}"),asset_paths=[Path(source_file_path)])
            pechas_catalog.info(f"{pecha_id},{pecha_name},https://github.com/OpenPecha-Data/{pecha_id}")
            parrallel_pechas.append({
            "pecha_id":pecha_id,
            "base_id":base_id,  
            "annotations":segment_annotaions,
            "lang":lang})
            
        return parrallel_pechas
    
    def create_readme(self,lang,pecha_name,pecha_id):
        Pecha_id = f"|Pecha id | {pecha_id}"
        Table = "| --- | --- "
        Title = f"|Title | {pecha_name} "
        language = f"|Language | {lang}"
        readme = f"{Pecha_id}\n{Table}\n{Title}\n{language}"
        Path(f"{self.root_opf_path}/{pecha_id}/readme.md").touch(exist_ok=True)
        Path(f"{self.root_opf_path}/{pecha_id}/readme.md").write_text(readme)


    def get_base_text(self,base_text_list:list):
        base_text = base_text_list[0]
        for text in base_text_list[1:]:
            base_text+="\n"+text

        return base_text

    def create_opf(self,pecha_id:str,base_id:str,base_text_list:list,pecha_name:str,lang:str):
        opf_path = f"{self.root_opf_path}/{pecha_id}/{pecha_id}.opf"
        base_text = self.get_base_text(base_text_list)
        opf = OpenPechaFS(path=opf_path)
        opf.bases = {base_id:base_text}
        segment_layer,segment_annotations = self.get_segment_layer(base_text_list)
        opf.layers ={f"{base_id}": {LayerEnum.segment: segment_layer}}
        opf._meta = self.get_metadata(pecha_id,pecha_name,base_id,lang)
        opf.save_base()
        opf.save_layers()
        opf.save_meta()
    
        return segment_annotations

    def get_metadata(self,pecha_id,pecha_name,base_id,lang):
        meta = InitialPechaMetadata(
            id=pecha_id,
            source = self.start_url,
            initial_creation_type=InitialCreationType.web_scrap,
            default_language=lang,
            bases={
                base_id:{"title":pecha_name,
                "base_file":f"{base_id}.txt",
                "order":1}
                    },
            source_metadata={
                "collections":[self.collection_name,self.main_collection]
            })
        return meta


    def create_source_file(self,pecha_id,page_url,base_id):
        page_html = requests.get(page_url)
        self._mkdir(Path(self.root_source_path))
        source_file_path = f"{self.root_source_path}/{base_id}.html"
        Path(source_file_path).write_text(page_html.text)
        return source_file_path

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
        translation_page = self.parse_home(self.start_url)
        links = self.get_links(translation_page)
        bool_try = True
        i=0
        for link in links:
            main_title = link
            self.main_collection = main_title
            pecha_links = links[link] 
            """ if pecha_link in err_list:
                bool_try = True """
            for pecha_link in pecha_links:
                if link == "Works of Tibetan Masters":
                    self.parse_collection(self.start_url+pecha_link)
                    if i%200 == 0 and i!=0:
                        shutil.rmtree("./zot_dir/")
                
                
    def get_err_list(self):
        with open("old_err.log", 'r') as f:
            err_list = [line for line in f.read().splitlines()]
        return err_list

def publish_repo(pecha_path, asset_paths=None):
    github_utils.github_publish(
        pecha_path,
        message="initial commit",
        not_includes=[],
        layers=[],
        org=os.environ.get("OPENPECHA_DATA_GITHUB_ORG"),
        token=os.environ.get("GITHUB_TOKEN")
       )
    if asset_paths:
        repo_name = pecha_path.stem
        #asset_name = asset_path.stem
        #shutil.make_archive(asset_path.parent / asset_name, "zip", asset_path)
        #asset_paths.append(f"{asset_path.parent / asset_name}.zip")
        github_utils.create_release(
            repo_name,
            prerelease=False,
            asset_paths=asset_paths, 
            org=os.environ.get("OPENPECHA_DATA_GITHUB_ORG"),
            token=os.environ.get("GITHUB_TOKEN")
        )
if __name__ == "__main__":
    obj = LHParser()
    #obj.collection_name = "demo"
    obj.main()
    #obj.parse_collection("https://www.lotsawahouse.org/tibetan-masters/lhundrup-tso/")
    #obj.parse_page_content("/tibetan-masters/alak-zenkar/swift-rebirth-prayer-for-pewar-rinpoche","test")
    #obj.parse_page_content("https://www.lotsawahouse.org/tibetan-masters/adeu-rinpoche/white-jambhala")
    #obj.parse_collection("https://www.lotsawahouse.org/tibetan-masters/dilgo-khyentse/")