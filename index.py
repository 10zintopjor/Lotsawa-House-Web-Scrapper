from asyncore import read
from ctypes import alignment
from distutils.command.config import LANG_EXT
from pathlib import Path
from pydoc import source_synopsis
from uuid import uuid4
import os
import logging
from openpecha.core.ids import get_alignment_id
from openpecha.utils import dump_yaml, load_yaml
from copy import deepcopy
from datetime import date, datetime



class Alignment:
    def __init__(self,path):
        self.root_path = path

    def create_alignment_yml(self,pecha_ids,volume,al):
        self.seg_pairs = self.get_segment_pairs(pecha_ids,volume,al[volume])
        self.segment_sources = {}
        language = []
        for pecha_id in pecha_ids:
            lang,pechaid = pecha_id
            if lang not in al[volume]:
                continue
            source = {
                pechaid:{
                    "type": "origin_type",
                    "relation": "translation",
                    "language": lang,
                }
            }
            language.append(lang)
            self.segment_sources.update(source)

        alignments = {
            "segment_sources": self.segment_sources,
            "segment_pairs":self.seg_pairs
        }    

        return alignments,language        

    def get_segment_pairs(self,pecha_ids,volume,lang_with_algnmt):
        segments_ids = {}
        cur_pair = {}
        pair= {}
        seg_pairs = {}
        segment_length = ""

        for pecha_id in pecha_ids:
            lang,pechaid = pecha_id
            if lang in lang_with_algnmt:
                segment_layer_path = f"{self.root_path}/{pechaid}/{pechaid}.opf/layers/{volume}/Segment.yml"
                pecha_yaml = load_yaml(Path(segment_layer_path))
                ids = self.get_ids(pecha_yaml["annotations"])
                if lang == "bo":
                    segment_length = len(ids)
                segments_ids[pechaid]= ids
 
        if segment_length == "":
            return seg_pairs

        for num in range(1,segment_length+1):
            for pecha_id in pecha_ids:
                lang,pechaid = pecha_id
                if lang in lang_with_algnmt: 
                    cur_pair[pechaid]=segments_ids[pechaid][num] if num in segments_ids[pechaid] else 'None'
            pair[uuid4().hex] = deepcopy(cur_pair)
            seg_pairs.update(pair)

        return seg_pairs

    def create_alignment(self,pecha_ids,pecha_name,al):
        volumes = self.get_volumes(pecha_ids)
        alignment_id = get_alignment_id()
        alignment_path = f"{self.root_path}/{alignment_id}/{alignment_id}.opa"
        alignment_vol_map=[]
        for volume in volumes:
            if volume not in al:
                continue
            alignments,language = self.create_alignment_yml(pecha_ids,volume,al)
            meta = self.create_alignment_meta(alignment_id,volume,language)
            self.write_alignment_repo(f"{alignment_path}/{volume}",alignments,meta)
            alignment_vol = [alignments,volume]
            alignment_vol_map.append(alignment_vol)

        self.create_readme_for_opa(alignment_id,pecha_name,pecha_ids) 
        pechaids = self.get_pecha_ids(pecha_ids)
        #logging.info(f"{alignment_id}:{pechaids}")    

        return alignment_id,alignment_vol_map


    def get_languages(self,pecha_ids: list):
        lang=[]
        for pecha_id in pecha_ids:
            language,_=pecha_id
            lang.append(language)
        return lang


    def get_pecha_ids(self,pecha_ids: list):
        pechaids=[]
        for pecha_id in pecha_ids:
            _,pechaid=pecha_id
            pechaids.append(pechaid)
        return pechaids


    def get_volumes(self,pecha_ids):
        volumes = []
        pechaid = ""
        for pecha_id in pecha_ids:
            lang,id = pecha_id
            if lang == "bo":
                pechaid = id
                break

        paths = list(Path(f"{self.root_path}/{pechaid}/{pechaid}.opf/base").iterdir())
        for path in sorted(paths):
            volumes.append(path.stem)
        return volumes


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


    def create_alignment_meta(self,alignment_id,volume,language):
        
        metadata = {
            "id": alignment_id,
            "title": volume,
            "type": "translation",
            "source_metadata":{
                "languages":language,
                "datatype":"PlainText",
                "created_at":datetime.now(),
                "last_modified_at":datetime.now()
                },
        }
        return metadata

    def create_readme_for_opa(self, alignment_id, pecha_name,pecha_ids):
        lang  = self.get_languages(pecha_ids)

        type = "translation"
        alignment = f"|Alignment id | {alignment_id}"
        Table = "| --- | --- "
        Title = f"|Title | {pecha_name} "
        type = f"|Type | {type}"
        languages = f"|Languages | {lang}"
        
        readme = f"{alignment}\n{Table}\n{Title}\n{type}\n{languages}"
        
        Path(f"{self.root_path}/{alignment_id}/readme.md").touch(exist_ok=True)
        Path(f"{self.root_path}/{alignment_id}/readme.md").write_text(readme)