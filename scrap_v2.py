
from bs4 import BeautifulSoup
from openpecha.utils import load_yaml,dump_yaml
from pathlib import Path
import random
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

err_log = set_up_logger('err')

class LHParser():
    start_url = 'https://www.lotsawahouse.org'
    root_path = "./zot_dir"


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


    def parse_collection(self,url):
        collection_page = self.make_request(url)
        self.collection_name = collection_page.select_one('div#content h1').text
        main_div = collection_page.find('div',{'id':'content'})
        pecha_links = self.filter_pecha_links(main_div)
        for pecha_link in pecha_links:
            print(pecha_link)
            self.parse_page_content(pecha_link)
            
            

    def filter_pecha_links(self,main_div):
        pecha_links = []
        index_containers = main_div.select('div.index-container')
        for index_container in index_containers:
            if index_container.find_previous_sibling("h4").text != "Related Topics":
                li_elements = index_container.find_all('li')
                for li in li_elements:
                    a_element = li.find('a')
                    href_value = a_element['href']
                    pecha_links.append(href_value)
        return pecha_links



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

        page = self.make_request(self.start_url+pecha_link)
        ids = []
        has_alignment = None
        lang_elems = page.select('p#lang-list a')
        language_pages = [[self.get_lang_code(lang_elem.text),lang_elem['href']] for lang_elem in lang_elems]
        for language_page in language_pages:
            lang,href = language_page
            if lang not in ["en","bo"]:
                continue
            base_text,has_alignment = self.extract_page_text(self.start_url+href,lang,has_alignment)
            text_id = random.randint(10000, 99999)
            Path(f"data/{text_id}.txt").write_text(base_text)
            id = (lang,f"{text_id}.txt")
            ids.append(id)
        self.log(ids)
    
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
        merged_text = ""
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
            return text.strip(),has_alignment

        elif lang == "bo":
            base_text = self.parse_tibetan_page(childrens,has_alignment)
        elif lang =="en":
            base_text,has_alignment = self.parse_non_tibetan_page(childrens)   
        for text in base_text:
            merged_text+=text+"\n"

        return merged_text.strip(),has_alignment

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
        for link in links:
            try:
                print(link)
                self.parse_collection(self.start_url+link)

            except Exception as e:
                err_log.info(f"{link},{e}")
                

if __name__ == "__main__":
    obj = LHParser()
    obj.main()
