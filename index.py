from asyncore import read
from ctypes import alignment
from pathlib import Path
from uuid import uuid4
import os
import logging
from openpecha.core.ids import get_alignment_id
from openpecha.utils import dump_yaml, load_yaml
from copy import deepcopy
from datetime import date, datetime


logging.basicConfig(
    filename="alignment_opf_map.log",
    format="%(levelname)s: %(message)s",
    level=logging.INFO,
)

class Alignment:
    def __init__(self,path):
        self.root_path = path

    def create_alignment_yml(self,pechas,volume):
        seg_pairs = self.get_segment_pairs(pechas,volume)
        self.segment_sources = {}
        for pecha in pechas:
            alignment = {
                pecha['pecha_id']:{
                    "type": "origin_type",
                    "relation": "translation",
                    "language": pecha['lang'],
                }

            }
            self.segment_sources.update(alignment)

        alignments = {
            "segment_sources": self.segment_sources,
            "segment_pairs":seg_pairs
        }    

        return alignments        

    def create_alignment(self,pechas,pecha_name):
        volumes = self.get_volumes(pechas[0])
        alignment_id = get_alignment_id()
        alignment_path = f"{self.root_path}/{alignment_id}/{alignment_id}.opa"
        alignment_vol_map=[]
        for volume in volumes:
            alignment = self.create_alignment_yml(pechas,volume)
            meta = self.create_alignment_meta(alignment_id,volume,pechas)
            self.write_alignment_repo(f"{alignment_path}/{volume}",alignment,meta)
            list2 = [alignment,volume]
            alignment_vol_map.append(list2)

        readme = self.create_readme_for_opa(alignment_id,pecha_name,pechas)
        Path(f"{self.root_path}/{alignment_id}/readme.md").touch(exist_ok=True)
        Path(f"{self.root_path}/{alignment_id}/readme.md").write_text(readme)

        logging.info(f"{alignment_id}:{list(set([pecha['pecha_id'] for pecha in pechas]))}")    

        return alignment_vol_map,alignment_id


    def get_volumes(self,pecha):
        volumes = []
        _,pecha_id = pecha
        paths = list(Path(f"{self.root_path}/{pecha_id}/{pecha_id}.opf/base").iterdir())
        for path in sorted(paths):
            volumes.append(path.stem)
        return volumes

    def get_segment_pairs(self,pechas,volume):
        segments_ids = {}
        segment_length = ""
        _,pecha_id = pechas

        for pecha in pechas:
            try:
                pecha_yaml = load_yaml(
                    Path(f"{self.root_path}/{pecha['pecha_id']}/{pecha['pecha_id']}.opf/layers/{volume}/Segment.yml")
                )
                ids = self.get_ids(pecha_yaml["annotations"])
                segment_length = len(ids)
                segments_ids[pecha['pecha_id']]= ids
            except:
                segments_ids[pecha['pecha_id']]= None  

        cur_pair = {}
        pair= {}
        seg_pairs = {}
        
        if segment_length == "":
            return seg_pairs

        for num in range(1,segment_length+1):
            for pecha in pechas:
                try:
                    cur_pair[pecha['pecha_id']]=segments_ids[pecha['pecha_id']][num]
                except:
                    cur_pair[pecha['pecha_id']]="None"
            pair[uuid4().hex] = deepcopy(cur_pair)
            seg_pairs.update(pair)

        return seg_pairs

    @staticmethod
    def _mkdir(path: Path):
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_ids(self,annotations):
        final_segments = {}
        num = 1
        for uid, _ in annotations.items():
            final_segments.update({num:uid})
            num += 1
        return final_segments 
   

    def write_alignment_repo(self,alignment_path,alignment,meta=None):
        alignment_path = Path(f"{alignment_path}")
        self._mkdir(alignment_path)
        dump_yaml(alignment, Path(f"{alignment_path}/Alignment.yml"))
        if meta:
            dump_yaml(meta, Path(f"{alignment_path}/meta.yml"))


    def create_alignment_meta(self,alignment_id,volume,pechas):
        lang  = list(set([pecha['lang'] for pecha in pechas]))

        metadata = {
            "id": alignment_id,
            "title": volume,
            "type": "translation",
            "source_metadata":{
                "languages":lang,
                "datatype":"PlainText",
                "created_at":datetime.now(),
                "last_modified_at":datetime.now()
                },
        }
        return metadata

    def create_readme_for_opa(self, alignment_id, pecha_name,pechas):
        lang  = list(set([pecha['lang'] for pecha in pechas]))

        type = "translation"
        alignment = f"|Alignment id | {alignment_id}"
        Table = "| --- | --- "
        Title = f"|Title | {pecha_name} "
        type = f"|Type | {type}"
        languages = f"|Languages | {lang}"
        
        readme = f"{alignment}\n{Table}\n{Title}\n{type}\n{languages}"
        return readme