
from bs4 import BeautifulSoup
from openpecha.utils import load_yaml,dump_yaml
from openpecha.core.ids import get_initial_pecha_id,get_base_id
from openpecha.core.metadata import InitialPechaMetadata,InitialCreationType
from openpecha import github_utils
from openpecha.core.layer import Layer, LayerEnum
from openpecha.core.pecha import OpenPechaFS
from openpecha.core.annotation import AnnBase, Span
from pathlib import Path
from index import Alignment
from uuid import uuid4
import os
import json
import requests
import logging
import itertools



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
        self.root_source_path = f"{self.root_path}/source"


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
        links = []
        page = self.make_request(url)
        main_divs = page.select_one('div#maintext')
        comp_names = main_divs.select('h2 a,h3 a')
        for comp_name in comp_names:
            main_name = comp_name.get_text().strip()
            if comp_name.parent.find_next_sibling('ul').find_all('li'):
                for elem in comp_name.parent.find_next_sibling('ul').select('li a'):
                    links.append(elem['href'])
            else:
                links.append(comp_name['href'])
        return links  

            
    def create_multlingual_opf(self,base_texts:list,langs:list,page_urls:list,pecha_name:str):
        parrallel_pechas = []
        for base_text,lang,page_url in zip(base_texts,langs,page_urls):
            pecha_id = get_initial_pecha_id()
            base_id = get_base_id()
            segment_annotaions = self.create_opf(pecha_id,base_id,base_text,pecha_name,lang)
            self.create_readme(lang,pecha_name,pecha_id)
            source_file_path = self.get_source_file(page_url,base_id)
            publish_repo(repo_path=Path(f"{self.root_opf_path}/{pecha_id}"),asset_paths=[Path(source_file_path)])
            pechas_catalog.info(f"{pecha_id},{pecha_name}")
            parrallel_pechas.append({
            "pecha_id":pecha_id,
            "base_id":base_id,  
            "annotations":segment_annotaions,
            "lang":lang})
            
        return parrallel_pechas     
    
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
    
    def get_metadata(self,pecha_id,pecha_name,base_id,lang):
        meta = InitialPechaMetadata(
            id=pecha_id,
            source = self.start_url,
            initial_creation_type=InitialCreationType.web_scrap,
            default_language=lang,
            source_metadata={
                "title":pecha_name
            },
            bases={
                base_id:{
                "base_file":f"{base_id}.txt",
                "order":1}
                    })
        return meta

    def filter_pecha_links(self,main_div):
        pecha_tags = []
        index_containers = main_div.select('div.index-container')
        for index_container in index_containers:
            if index_container.find_previous_sibling("h4").text != "Related Topics":
                li_elements = index_container.find_all('li')
                for li in li_elements:
                    a_element = li.find('a')
                    href_value = a_element['href']
                    pecha_name = a_element.get_text()
                    pecha_tags.append([pecha_name,href_value])
        return pecha_tags

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
    
    def get_source_file(self, page_url, base_id):
        page_response = requests.get(page_url)
        page_response.encoding = 'utf-8'  # Set the encoding to UTF-8
        page_html = page_response.text

        self._mkdir(Path(self.root_source_path))
        source_file_path = f"{self.root_source_path}/{base_id}.html"

        with open(source_file_path, 'w', encoding='utf-8') as file:
            file.write(page_html)

        return source_file_path


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


    def parse_page_content(self,pecha_tag):
        page_urls = []
        base_texts = []
        langs=[]
        pecha_name,pecha_link = pecha_tag
        page = self.make_request(self.start_url+pecha_link)
        has_alignment = None
        lang_elems = page.select('p#lang-list a')
        language_pages = [[self.get_lang_code(lang_elem.text),lang_elem['href']] for lang_elem in lang_elems]
        for language_page in language_pages:
            lang,href = language_page
            if lang not in ["en","bo"]:
                continue
            base_text,has_alignment = self.extract_page_text(self.start_url+href,lang,has_alignment)
            base_texts.append(base_text)
            langs.append(lang)
            page_urls.append(self.start_url+href)  
        if has_alignment:
            has_alignment = self.verify_alignment(base_texts,pecha_link)
        parrallel_pechas = self.create_multlingual_opf(base_texts,langs,page_urls,pecha_name)
        return parrallel_pechas,has_alignment      
    
    
    @staticmethod
    def verify_alignment(base_texts,pecha_link):
        it = iter(base_texts)
        the_len = len(next(it))
        if not all(len(l) == the_len for l in it):
            err_log.info(f"{pecha_link},in")
            return False
        return True
    

    def log(self,ids):
        json_file_path = Path('data.json')
        if json_file_path.exists():
            with open(json_file_path, 'r') as f:
                data = json.load(f)
        else:
            data = {}
            data["ids"] = []
        data["ids"].append(ids)        

        with open(json_file_path, 'w') as f:
            json.dump(data, f)


    def test_base_text(self,base_texts):
        for combination in itertools.zip_longest(*base_texts):
            print(combination)

    

    def get_base_text(self,base_text_list:list):
        base_text = base_text_list[0]
        for text in base_text_list[1:]:
            base_text+="\n"+text

        return base_text


    @staticmethod
    def remove_endlines(text):
        prev = ''
        while prev != text.strip("\n"):
            prev =text.strip("\n")
        return prev 

    def has_alignment(self,url):
        soup = self.make_request(url)
        try:
            tib_verse =soup.select("div#maintext p.TibetanVerse")
            tib_heading = soup.select("div#maintext p.HeadingTib")
            if tib_heading and tib_verse:
                return True
        except ValueError:
            pass
        return False


    def extract_page_text(self,url,lang,has_alignment):
        page = self.make_request(url)
        div_main = page.select_one('div#maintext')
        childrens = div_main.findChildren(recursive=False)
        if len(childrens) == 1 and childrens[0].name == "div":
            childrens = childrens[0].findChildren(recursive=False)

        if has_alignment is None:
            has_alignment = self.has_alignment(url)

        if has_alignment is False:
            res = self.make_request(url=url)
            text = res.select_one("div#maintext").get_text()
            base_text = text.split("\n\n")
        elif lang == "bo":
            base_text = self.parse_tibetan_page(childrens,has_alignment)
        elif lang =="en":
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

    def parse_collection(self,url):
        collection_page = self.make_request(url)
        self.collection_name = collection_page.select_one('div#content h1').text
        main_div = collection_page.find('div',{'id':'content'})
        pecha_tags = self.filter_pecha_links(main_div)
        for pecha_tag in pecha_tags:
            pecha_name,_ = pecha_tag
            parrallel_pechas,has_alignment = self.parse_page_content(pecha_tag)
            if has_alignment:
                alignment_id = self.create_alignment(parrallel_pechas,pecha_name)
                alignment_path = f"{self.root_opa_path}/{alignment_id}"
                publish_repo(repo_path=Path(alignment_path))
                alignment_catalog.info(f"{alignment_id},{pecha_name}")


    def main(self):
        translation_page = self.parse_home(self.start_url)
        links = self.get_links(translation_page)
        for link in links:
            try:
                print(link)
                self.parse_collection(self.start_url+link)

            except Exception as e:
                err_log.info(f"{link},{e}")
                

def publish_repo(repo_path, asset_paths=None):
    github_utils.github_publish(
        repo_path,
        message="initial commit",
        not_includes=[],
        layers=[],
        org=os.environ.get("OPENPECHA_DATA_GITHUB_ORG"),
        token=os.environ.get("GITHUB_TOKEN")
       )
    if asset_paths:
        repo_name = repo_path.stem
        github_utils.create_release(
            repo_name,
            prerelease=False,
            asset_paths=asset_paths, 
            org=os.environ.get("OPENPECHA_DATA_GITHUB_ORG"),
            token=os.environ.get("GITHUB_TOKEN")
        )

if __name__ == "__main__":
    obj = LHParser()
    obj.main()
