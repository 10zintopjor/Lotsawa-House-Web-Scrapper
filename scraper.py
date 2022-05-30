from cgi import test
from ctypes import alignment
from email.mime import base
from pydoc import pager
from socket import has_dualstack_ipv6
from urllib import response
from bs4 import BeautifulSoup
from openpecha.core.ids import get_pecha_id
from openpecha.core.layer import InitialCreationEnum, Layer, LayerEnum, PechaMetaData
from openpecha.core.pecha import OpenPechaFS 
from openpecha.core.annotation import AnnBase, Span
from openpecha import github_utils,config
from datetime import datetime
from uuid import uuid4
from index import Alignment
from pathlib import Path
from zipfile import ZipFile
import re
import requests
import serialize_to_tmx
import logging
import csv


pechas_catalog = ''
alignment_catalog = ''
err_log = ''
start_url= 'https://www.lotsawahouse.org'
root_path = ''


def make_request(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content,'html.parser')
    return soup


def parse_home(url):
    page = make_request(url)
    headers = page.select('div#header-links1 a')
    for header in headers:
        if header.get_text() == "Translations":
            return url+header['href']


def get_links(url):
    links = {}
    page = make_request(url)
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


def parse_page(url):
    global root_path
    page_meta={}
    chapter_subtitle_map = {}
    has_alignment = {}
    page = make_request(url)
    lang_elems = page.select('p#lang-list a')
    languages = [lang_elem.text for lang_elem in lang_elems]
    pecha_name = page.select_one('div#content h1').text
    pecha_ids = get_pecha_ids(languages)
    page_meta.update({
        "main_title":page.select_one('div#content h1').text,
        "description":page.select_one("div#content b").text.strip("\n")
        })
    main_div = page.find('div',{'id':'content'})
    headings = main_div.find_all('h4')
    root_path=f"./opfs/{page.select_one('div#content h1').text}"
    print(pecha_name)
    for heading in headings:
        if heading.get_text() == "Related Topics":
            continue
        chapter_elems = heading.find_next_sibling('div').select('ul > li > a:first-child')
        heading_title = heading.get_text()
        c_s_m,h_a = get_chapters(chapter_elems,pecha_ids,pecha_name,heading_title)
        chapter_subtitle_map.update(c_s_m)
        has_alignment.update(h_a)        
    
    if not headings:
        chapter_elems = main_div.select('div.index-container > ul > li > a:first-child')
        c_s_m,h_a = get_chapters(chapter_elems,pecha_ids,pecha_name)
        chapter_subtitle_map.update(c_s_m)
        has_alignment.update(h_a) 

    page_meta.update({"chapter_subtitle":chapter_subtitle_map})
    for pecha_id in pecha_ids:
        lang,pechaid = pecha_id
        create_meta(pechaid,page_meta,lang)
        create_readme(pechaid,lang,pecha_name)

    return pecha_ids,pecha_name,has_alignment



def get_chapters(chapter_elems,pecha_ids,pecha_name,heading_title=None):
    chapter_subtitle_map = {}
    has_alignment = {}
    for chapter_elem in chapter_elems:
        chapter_subtitle_map.update({chapter_elem.text:heading_title})
        href = chapter_elem['href']
        base_text,bool_alignment = get_text(start_url+href)
        if bool_alignment:
            has_alignment.update({chapter_elem.text:bool_alignment})
        for pecha_id in pecha_ids:
            language,pechaid = pecha_id
            if language in base_text:
                chapter = chapter_elem.text
                try:
                    create_opf(pechaid,base_text[language],chapter)
                except:
                    err_log.info(f"Opf Error : {pecha_name}:{chapter}:{language}") 
    return chapter_subtitle_map,has_alignment


def get_text(url):
    page = make_request(url)
    base_text = {}
    has_alignment = []
    lang_elems = page.select('p#lang-list a')
    language_pages = [[lang_elem.text,lang_elem['href']] for lang_elem in lang_elems]
    for language_page in language_pages:
        language,href = language_page
        lang_code = get_lang_code(language)
        text,bool_alignment = extract_page_text(start_url+href,lang_code,has_alignment)
        if bool_alignment == True:
            has_alignment.append(lang_code) 
        base_text.update({lang_code :text})
    if has_alignment:
        has_alignment.append("bo")
    return base_text,has_alignment


def extract_page_text(url,lang_code,prev_alignment):
    base_text=""
    has_alignment = None
    page = make_request(url)
    div_main = page.select_one('div#maintext')
    childrens = div_main.findChildren(recursive=False)
    if len(childrens) == 1 and childrens[0].name == "div":
        childrens = childrens[0].findChildren(recursive=False)
    for children in childrens:
        text = remove_endlines(children.get_text())
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
            text = change_text_format(text)
        base_text+=text.strip(" ")
        base_text+="\n\n" if has_alignment != True and not prev_alignment else "\n"

    return base_text.strip("\n").strip(),has_alignment


def create_opf(pecha_id,base_text,chapter):
    opf_path = f"{root_path}/{pecha_id}/{pecha_id}.opf"
    opf = OpenPechaFS(opf_path=opf_path)
    bases= {f"{chapter}":base_text}
    opf.base = bases
    opf.save_base()
    layers = {f"{chapter}": {LayerEnum.segment: get_segment_layer(base_text)}}
    opf.layers = layers
    opf.save_layers()


def get_segment_layer(base_text):
    segment_annotations= {}
    char_walker = 0
    splited_texts = base_text.split("\n\n")
    for text in splited_texts:
        if text == "":
            continue
        segment_annotation,char_walker = get_segment_annotation(char_walker,text)
        segment_annotations.update(segment_annotation)
    segment_layer = Layer(annotation_type= LayerEnum.segment,annotations=segment_annotations)   

    return segment_layer   


def get_segment_annotation(char_walker,text):
    start = char_walker
    end = char_walker +len(text)
    segment_annotation = {uuid4().hex:AnnBase(span=Span(start=start,end=end))}
    return (segment_annotation,end+2)


def create_meta(pecha_id,page_meta,lang):
    opf_path = f"{root_path}/{pecha_id}/{pecha_id}.opf"
    opf = OpenPechaFS(opf_path=opf_path)
    vol_meta = get_volume_meta(page_meta['chapter_subtitle'])
    instance_meta = PechaMetaData(
        id=pecha_id,
        initial_creation_type=InitialCreationEnum.input,
        created_at=datetime.now(),
        last_modified_at=datetime.now(),
        source_metadata={
            "title":page_meta['main_title'],
            "language": lang,
            "description":page_meta["description"],
            "volume":vol_meta
        })    

    opf._meta = instance_meta
    opf.save_meta()

def create_readme(pecha_id,lang,pecha_name):

    id = f"|pecha id | {pecha_id}"
    Table = "| --- | --- "
    Title = f"|Title | {pecha_name} "
    language = f"|Languages | {lang}"
    
    readme = f"{id}\n{Table}\n{Title}\n{language}"
    
    Path(f"{root_path}/{pecha_id}/readme.md").write_text(readme)

def get_volume_meta(chapter_subtitle):
    meta={}
    for chapter in chapter_subtitle:
        meta.update({uuid4().hex:{
            "title":chapter,
            "parent": chapter_subtitle[chapter],
        }}) 

    return meta


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


def remove_endlines(text):
    prev = ''
    while prev != text.strip("\n"):
        prev =text.strip("\n")
    return prev    


def get_pecha_ids(languages):
    pecha_ids = []
    for language in languages:
        lang_code = get_lang_code(language)
        pecha_ids.append([lang_code,get_pecha_id()])
    return pecha_ids


def get_lang_code(lang):
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


def create_alignment(pecha_ids,pecha_name,alignment):
    obj = Alignment(root_path)
    alignment_id,alignment_vol_map = obj.create_alignment(pecha_ids,pecha_name,alignment)
    alignment_catalog.info(f"{alignment_id},{pecha_name}")
    create_csv(alignment_id,pecha_ids)
    tmx_path = Path(f"./tmx/{pecha_name}")
    obj._mkdir(tmx_path)
    create_tmx(alignment_vol_map,tmx_path,root_path)
    zip_path = create_tmx_zip(tmx_path,pecha_name)
    return alignment_id,zip_path

def create_csv(alignment_id,pecha_ids):
    filename = ""
    for i,pecha_id in enumerate(pecha_ids):
        lang,pechaid =pecha_id
        filename+=lang
        if len(pecha_ids) > i+1:
            filename+='-'
    with open(f"{root_path}/{alignment_id}/{filename}.csv",'w') as f:
        writer = csv.writer(f)
        writer.writerow(["pecha id","language","url"])
        for pecha_id in pecha_ids:
            lang,pechaid = pecha_id
            url = f"https://github.com/OpenPecha/{pechaid}"
            writer.writerow([pechaid,lang,url])

def create_tmx(alignment_vol_map,tmx_path,root_path):
    for map in alignment_vol_map:
        alignment,volume = map   
        serialize_to_tmx.create_tmx(alignment,volume,tmx_path,root_path)


def create_tmx_zip(tmx_path,pecha_name):
    zip_path = f"{root_path}/{pecha_name}.zip"
    zipObj = ZipFile(zip_path, 'w')
    tmxs = list(Path(f"{tmx_path}").iterdir())
    for tmx in tmxs:
        zipObj.write(tmx)
    return zip_path


def publish_opf(id):
    pecha_path = f"{root_path}/{id}"
    github_utils.github_publish(
    pecha_path,
    not_includes=[],
    message="initial commit"
    )  
    print(f"{id} PUBLISHED")


def create_realease(id,zipped_dir):
    assest_path =[f"{zipped_dir}"]
    github_utils.create_release(
    repo_name=id,
    asset_paths=assest_path,
    )
    print(f"Updated asset to {id}")

def set_up_logger(logger_name):
    logger = logging.getLogger(logger_name)
    formatter = logging.Formatter("%(message)s")
    fileHandler = logging.FileHandler(f"{logger_name}.log")
    fileHandler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(fileHandler)

    return logger

def main():
    global pechas_catalog,alignment_catalog,err_log
    pechas_catalog = set_up_logger("pechas_catalog")
    alignment_catalog =set_up_logger("alignment_catalog")
    err_log = set_up_logger('err')
    translation_page = parse_home(start_url)
    links = get_links(translation_page)
    """ try:
        pecha_ids,pecha_name,alignment = parse_page('https://www.lotsawahouse.org/tibetan-masters/adeu-rinpoche/')
        for pecha_id in pecha_ids:
            lang,pechaid =pecha_id
            pechas_catalog.info(f"{pechaid},{lang},{pecha_name}")
            publish_opf(pechaid)    
    except:
        err_log.info(f"main error: {test}")
        pass
    
    if bool(alignment):
        alignment_id,zipped_path = create_alignment(pecha_ids,pecha_name,alignment)
        publish_opf(alignment_id)
        create_realease(alignment_id,zipped_path) """

    for link in links:
        main_title = link
        print(main_title)
        pecha_links = links[link]
        
        for pecha_link in pecha_links:
            try:
                pecha_ids,pecha_name,alignment = parse_page(start_url+pecha_link)
                for pecha_id in pecha_ids:
                    lang,pechaid =pecha_id
                    pechas_catalog.info(f"{pechaid},{lang},{pecha_name}")
                    publish_opf(pechaid)
            except:
                err_log.info(f"main error: {start_url+pecha_link}")
                pass
        
            if bool(alignment):
                try:
                    alignment_id,zipped_path = create_alignment(pecha_ids,pecha_name,alignment)
                    publish_opf(alignment_id)
                    create_realease(alignment_id,zipped_path)
                except:
                    err_log.info(f"alignment error: {pecha_name}") 


if __name__ == "__main__":
    main()
