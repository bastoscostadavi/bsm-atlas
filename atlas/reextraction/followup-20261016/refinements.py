"""Add source-link clarification without regenerating any candidate/preflight."""
from stage import *

def main():
    path=HERE/'mssm-matter-evidence.json'
    ev=load(path);p22=load(HISTORICAL/'P22/checkpoint.json')
    ev['additional_source_review']={'paper_id':'P22','arxiv_version':p22['arxiv_version'],'checkpoint_path':'atlas/reextraction/P22/checkpoint.json','checkpoint_sha256':sha256((HISTORICAL/'P22/checkpoint.json').read_bytes()).hexdigest(),'source':p22['source'],'inspection':p22['inspection'],'claim':next(x for x in p22['claims'] if x['id']=='rpv'),'reason':'The paired source-field IDs256-263 are from this actual source review, not merely name matching to P21. RPV operators do not alter its R_MSSM inventory.'}
    emit(path,ev)

if __name__=='__main__':main()
