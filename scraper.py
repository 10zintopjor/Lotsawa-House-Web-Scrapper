from urllib import response
from bs4 import BeautifulSoup
import requests


start_url= 'https://www.lotsawahouse.org'

def make_request(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text,'html.parser')

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

def main():
    translation_page = parse_home(start_url)
    links = get_links(translation_page)
    print(links)

if __name__ == "__main__":
    main()
