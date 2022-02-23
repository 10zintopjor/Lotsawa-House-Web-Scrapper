from email.mime import base
from pydoc import pager
from urllib import response
from bs4 import BeautifulSoup
from openpecha.core.ids import get_pecha_id
from openpecha.core.layer import InitialCreationEnum, Layer, LayerEnum, PechaMetaData
from openpecha.core.pecha import OpenPechaFS 
from datetime import datetime
from uuid import uuid4

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
        chapter_elems = heading.find_next_sibling('div').select('ul > li > a')
        for chapter_elem in chapter_elems:
            chapter_subtitle_map.update({chapter_elem.text:heading.get_text()})
            href = chapter_elem['href']
            base_text = get_text(start_url+href)
            for pecha_id in pecha_ids:
                language,pechaid = pecha_id
                create_opf(pechaid,base_text[language],chapter_elem.text)
    page_meta.update({"chapter_subtitle":chapter_subtitle_map})
    for pecha_id in pecha_ids:
        lang,pechaid = pecha_id
        create_meta(pechaid,page_meta,lang)


def create_opf(pecha_id,base_text,chapter):
    opf_path = f"{root_path}/{pecha_id}/{pecha_id}.opf"
    opf = OpenPechaFS(opf_path=opf_path)
    bases= {f"{chapter}":base_text}
    opf.base = bases
    opf.save_base()


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
    lang_elems = page.select('p#lang-list a')
    language_pages = [[lang_elem.text,lang_elem['href']] for lang_elem in lang_elems]
    for language_page in language_pages:
        language,href = language_page
        base_text.update({language:extract_page_text(start_url+href)})

    return base_text


def extract_page_text(url):
    page = make_request(url)
    text = page.select_one('div#maintext').text

    return text.strip("\n")


def get_pecha_ids(languages):
    pecha_ids = []
    for language in languages:
        pecha_ids.append([language,get_pecha_id()])
    return pecha_ids


def main():
    translation_page = parse_home(start_url)
    links = get_links(translation_page)
    for link in links:
        main_title = link
        pecha_links = links[link]
        for pecha_link in pecha_links:
            parse_page(start_url+pecha_link)
            break
        break


if __name__ == "__main__":
    main()
