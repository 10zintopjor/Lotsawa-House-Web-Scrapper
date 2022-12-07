from pathlib import Path
from uuid import uuid4
import logging
from openpecha.core.ids import get_alignment_id
from datetime import date, datetime
from openpecha.core.ids import get_base_id
from openpecha.utils import dump_yaml, load_yaml


class Alignment:
    def __init__(self,path):
        self.root_opa_path = f"{path}/opas"
        self.root_opf_path = f"{path}/opfs"

    def create_alignment_yml(self,parrallel_pechas):
        seg_pairs = self.get_segment_pairs(parrallel_pechas)
        segment_sources = {}
        for pecha in parrallel_pechas:
            source = {
                pecha["pecha_id"]:{
                    "type": "origin_type",
                    "relation": "translation",
                    "language": pecha["lang"],
                    "base":f"{pecha['base_id']}"
                }
            }
            segment_sources.update(source)

        alignments = {
            "segment_sources": segment_sources,
            "segment_pairs": seg_pairs
        }    

        return alignments       

    def get_segment_pairs(self,parallel_pechas):
        seg_pairs = {}
        annotations = [list(pecha["annotations"].keys()) for pecha in parallel_pechas]
        pecha_ids = [pecha["pecha_id"] for pecha in parallel_pechas]
        annotations_pair_iter = iter(self.get_annoation_pair(annotations,pecha_ids))
        for i in range(0,len(annotations[0])):
            seg_pairs.update({uuid4().hex:next(annotations_pair_iter)})

        return seg_pairs
    
    def get_annoation_pair(self,annotations,pecha_ids):
        for i in range(0,len(annotations[0])):
            pechaId_segId_map = {}
            for pecha_id,annotation in zip(pecha_ids,annotations):
                pechaId_segId_map.update({pecha_id:annotation[i]})
            yield pechaId_segId_map
        

    def create_alignment(self,parrallel_pechas,pecha_name):
        alignment_id = get_alignment_id()
        alignment_path = f"{self.root_opa_path}/{alignment_id}/{alignment_id}.opa"
        self._mkdir(Path(alignment_path))
        base_id = get_base_id()
        alignments = self.create_alignment_yml(parrallel_pechas)
        meta = self.create_alignment_meta(alignment_id,parrallel_pechas,base_id,pecha_name)
        dump_yaml(alignments,Path(f"{alignment_path}/{base_id}.yml"))
        dump_yaml(meta,Path(f"{alignment_path}/meta.yml"))
        self.create_readme_for_opa(alignment_id,pecha_name,parrallel_pechas) 
        #logging.info(f"{alignment_id}:{pechaids}")    
        return alignment_id,alignments

    def _mkdir(self,path: Path):
        path.mkdir(parents=True, exist_ok=True)
        return path


    def create_alignment_meta(self,alignment_id,parallel_pechas,base_id,pecha_name):
        alignment_map = {}
        for pecha in parallel_pechas:
            alignment_map.update({f"{pecha['pecha_id']}/{pecha['base_id']}":base_id})

        pechas_ids = [pecha["pecha_id"] for pecha in parallel_pechas]
        langs = [pecha["lang"] for pecha in parallel_pechas]
        metadata = {
            "id": alignment_id,
            "type": "translation",
            "pechas":pechas_ids,
            "source_metadata":{
                "title":pecha_name,
                "languages":langs,
                "datatype":"PlainText",
                "created_at":datetime.now(),
                "last_modified_at":datetime.now(),
                "alignment_to_base":alignment_map
                },
        }
        return metadata

    def create_readme_for_opa(self, alignment_id, pecha_name,parallel_pechas):
        lang  = [pecha["lang"] for pecha in parallel_pechas]
        type = "translation"
        alignment = f"|Alignment id | {alignment_id}"
        Table = "| --- | --- "
        Title = f"|Title | {pecha_name} "
        type = f"|Type | {type}"
        languages = f"|Languages | {lang}"
        
        readme = f"{alignment}\n{Table}\n{Title}\n{type}\n{languages}"
        Path(f"{self.root_opa_path}/{alignment_id}/readme.md").touch(exist_ok=True)
        Path(f"{self.root_opa_path}/{alignment_id}/readme.md").write_text(readme)