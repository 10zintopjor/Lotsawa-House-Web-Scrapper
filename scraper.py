from ctypes import alignment
from email.mime import base
from pydoc import pager
from urllib import response
from bs4 import BeautifulSoup
from openpecha.core.ids import get_pecha_id
from openpecha.core.layer import InitialCreationEnum, Layer, LayerEnum, PechaMetaData
from openpecha.core.pecha import OpenPechaFS 
from openpecha.core.annotation import AnnBase, Span
from datetime import datetime
from uuid import uuid4
from index import Alignment

import re
import requests


start_url= 'https://www.lotsawahouse.org'
root_path = './opfs'

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
    page_meta={}
    chapter_subtitle_map = {}
    page = make_request(url)
    lang_elems = page.select('p#lang-list a')
    languages = [lang_elem.text for lang_elem in lang_elems]
    pecha_ids = get_pecha_ids(languages)
    page_meta.update({
        "main_title":page.select_one('div#content h1').text,
        "description":page.select_one("div#content b").text 
        })
    main_div = page.find('div',{'id':'content'})
    headings = main_div.find_all('h4')

    for heading in headings:
        if heading.get_text() == "Related Topics":
            continue
        chapter_elems = heading.find_next_sibling('div').select('ul > li > a:first-child')
        for chapter_elem in chapter_elems:
            chapter_subtitle_map.update({chapter_elem.text:heading.get_text()})
            href = chapter_elem['href']
            base_text,has_alignment = get_text(start_url+href)
            for pecha_id in pecha_ids:
                language,pechaid = pecha_id
                if language in base_text:
                    chapter = chapter_elem.text
                    create_opf(pechaid,base_text[language],chapter,has_alignment)
    page_meta.update({"chapter_subtitle":chapter_subtitle_map})
    for pecha_id in pecha_ids:
        lang,pechaid = pecha_id
        create_meta(pechaid,page_meta,lang)

    return pecha_ids,page.select_one('div#content h1').text

def create_opf(pecha_id,base_text,chapter,has_alignment):
    opf_path = f"{root_path}/{pecha_id}/{pecha_id}.opf"
    opf = OpenPechaFS(opf_path=opf_path)
    bases= {f"{chapter}":base_text}
    opf.base = bases
    opf.save_base()
    if False not in has_alignment:
        layers = {f"{chapter}": {LayerEnum.segment: get_segment_layer(base_text)}}
        opf.layers = layers
        opf.save_layers()


def get_segment_layer(base_text):
    segment_annotations= {}
    char_walker = 0
    splited_texts = base_text.split("\n\n")
    for text in splited_texts:
        segment_annotation,end = get_segment_annotation(char_walker,text)
        segment_annotations.update(segment_annotation)
        char_walker += end+1
    segment_layer = Layer(annotation_type= LayerEnum.segment,annotations=segment_annotations)   

    return segment_layer   

def get_segment_annotation(char_walker,text):

    segment_annotation = {uuid4().hex:AnnBase(span=Span(start=char_walker, end=char_walker + len(text) - 2))}

    return (segment_annotation,len(text))


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


def get_volume_meta(chapter_subtitle):
    meta={}
    for chapter in chapter_subtitle:
        meta.update({uuid4().hex:{
            "title":chapter,
            "parent": chapter_subtitle[chapter],
        }}) 

    return meta


def get_text(url):
    page = make_request(url)
    base_text = {}
    has_alignment = set()
    lang_elems = page.select('p#lang-list a')
    language_pages = [[lang_elem.text,lang_elem['href']] for lang_elem in lang_elems]
    for language_page in language_pages:
        language,href = language_page
        text,bool_alignment = extract_page_text(start_url+href,language)
        has_alignment = set.union(has_alignment,bool_alignment)
        base_text.update({language:text})

    return base_text,has_alignment


def extract_page_text(url,language):
    base_text=""
    has_alignment = set()
    page = make_request(url)
    div_main = page.select_one('div#maintext')
    childrens = div_main.findChildren(recursive=False)
    #print(childrens)
    if len(childrens) == 1 and childrens[0].name == "div":
        childrens = childrens[0].findChildren(recursive=False)
    for children in childrens:
        if children.has_attr('class'):
            if children['class'][0] in ('HeadingTib','TibetanVerse','TibetanExplanation') and language != "བོད་ཡིག":
                has_alignment.add(True)
                continue
        text = children.get_text()
        if text == "Bibliography":
            break
        elif text == "\xa0":
            base_text+="\n"
            continue
        if len(text)>90:
            text = change_text_format(text)
        base_text+=text+"\n"

    return base_text.strip("\n"),has_alignment

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


def get_pecha_ids(languages):
    pecha_ids = []
    for language in languages:
        pecha_ids.append([language,get_pecha_id()])
    return pecha_ids


def main():
    obj = Alignment(root_path)
    translation_page = parse_home(start_url)
    links = get_links(translation_page)
    for link in links:
        main_title = link
        pecha_links = links[link]
        for pecha_link in pecha_links:
            #pecha_ids,pecha_name = parse_page(start_url+pecha_link)
            parse_page('https://www.lotsawahouse.org/bo/indian-masters/arya-shura/')
            #obj.create_alignment(pecha_ids,pecha_name)
            break
        break
    

if __name__ == "__main__":
    main()
