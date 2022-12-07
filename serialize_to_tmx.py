from logging import root
from xml.etree import ElementTree
from openpecha.utils import dump_yaml, load_yaml
from xml.dom import minidom
from pathlib import Path
from openpecha import config
import datetime

class Tmx:
    def __init__(self,root_opf_path,root_tmx_path):
        self.root_opf_path = root_opf_path
        self.root_tmx_path =  root_tmx_path

    def create_body(self,body,seg_pairs,pecha_langs,segment_sources):
        for seg_id in seg_pairs:
            tu =ElementTree.SubElement(body,'tu',{"seg_id":seg_id})
            for elem in seg_pairs[seg_id]:
                pecha_id = elem
                segment_id = seg_pairs[seg_id][elem]
                text = self.get_text(pecha_id,segment_id,segment_sources["pecha_id"]["base"])
                if text!="":
                    tuv = ElementTree.SubElement(tu,"tuv",{"xml:lang":pecha_langs[pecha_id],"creationdate":str(datetime.datetime.now()),"creationid":"esukhia"})     
                    tuv.text=text


    def get_text(self,pecha_id,seg_id,volume):
        if seg_id == None:
            return ""
        else:
            try:
                pecha_path = f"{self.root_opf_path}/{pecha_id}/{pecha_id}.opf"    
                base_text_path = f"{pecha_path}/base/{volume}.txt"
                layer_path = f"{pecha_path}/layers/{volume}/Segment.yml"
                segment_yml = load_yaml(Path(layer_path))
            except:
                return ""    
            annotations = segment_yml.get("annotations",{})
            for id in annotations:
                if id == seg_id:
                    span = annotations[id]['span']
                    base_text = self.get_base_text(span,base_text_path)
                    return base_text


    def get_base_text(self,span,base_text_path):
        base_text = Path(base_text_path).read_text()
        start = span['start']
        end = span['end']

        return base_text[start:end+1]

    def create_main(self,seg_pairs,pecha_langs,segment_sources):
        root = ElementTree.Element('tmx')
        ElementTree.SubElement(root,'header',{"datatype":"Text","creationdate":str(datetime.datetime.now())})
        body = ElementTree.SubElement(root,'body')
        self.create_body(body,seg_pairs,pecha_langs,segment_sources)
        tree = self.prettify(root)
        return tree

    def create_tmx(self,alignment,tmx_path):
        seg_pairs = alignment['segment_pairs']
        segment_sources = alignment["segment_sources"]
        pecha_langs = self.get_pecha_langs(alignment['segment_sources'])
        tree = self.create_main(seg_pairs,pecha_langs,segment_sources)
        Path(f"{tmx_path}/{volume}.tmx").write_text(tree)   


    def get_pecha_langs(self,segment_srcs):
        pecha_lang = {}
        for seg in segment_srcs:
            pecha_lang.update({seg:segment_srcs[seg]['language']})
        return pecha_lang


    def prettify(self,elem):
        """Return a pretty-printed XML string for the Element.
        """
        rough_string = ElementTree.tostring(elem, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")