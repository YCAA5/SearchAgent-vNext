"""Local comparison; reports contain timings/counts, never document text."""
import importlib.util
import json
import os
import statistics
import time
from pathlib import Path

from local_catalog import rebuild_catalog
from model_runtime import LocalEmbedder
from semantic_search import semantic_search, build_semantic_index

original = Path(os.environ['SEARCH_AGENT_BASELINE'])
output = Path(os.environ['SEARCH_AGENT_BENCH_OUTPUT'])
output.mkdir(parents=True, exist_ok=True)
def legacy(name, filename):
    spec=importlib.util.spec_from_file_location(name,original/filename)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
old=legacy('legacy_semantic','semantic_search.py')
old_catalog=legacy('legacy_catalog','local_catalog.py')
catalog=original/'data/indexes/desktop.db'; vectors=original/'data/indexes/semantic.db'
query='personel ulaşım maliyeti ve yıllık giderlerin değerlendirildiği belge'
report={'search':{},'index':{},'scope':'one office PC; warm model; identical catalog, vectors and query'}
expected=None
for label,function in [('old',old.semantic_search),('new',semantic_search)]:
    durations=[]
    for n in range(6):
        started=time.perf_counter(); result=function(catalog,vectors,query); durations.append(time.perf_counter()-started)
        order=[row['file_path'] for row in result['results']]
        if expected is None: expected=order
        assert order==expected, 'Ranking changed'
    report['search'][label]={'first_s':durations[0],'warm_median_s':statistics.median(durations[1:]),'runs_s':durations}
report['search']['same_top_30_order']=True
documents=output/'generated-documents'; documents.mkdir(exist_ok=True)
for n in range(40):
    (documents/f'budget-{n:02}.txt').write_text(
        f'Annual personnel transport budget. Project {n}. Personel servis giderleri, ulaşım maliyeti ve yıllık harcama değerlendirmesi. ' * 10,encoding='utf-8')
for label,scan,build in [('old',old_catalog.rebuild_catalog,old.build_semantic_index),('new',rebuild_catalog,build_semantic_index)]:
    cat=output/f'{label}-catalog.db'; sem=output/f'{label}-semantic.db'
    started=time.perf_counter(); read=scan([documents],cat); scan_s=time.perf_counter()-started
    started=time.perf_counter(); built=build(cat,sem); build_s=time.perf_counter()-started
    started=time.perf_counter(); reread=scan([documents],cat); rescan_s=time.perf_counter()-started
    started=time.perf_counter(); rebuild=build(cat,sem); resume_s=time.perf_counter()-started
    report['index'][label]={'documents':built['documents'],'chunks':built['chunks'],'scan_s':scan_s,'embedding_index_s':build_s,'unchanged_scan_s':rescan_s,'unchanged_semantic_s':resume_s,'reused':reread['reused']}
report['gpu']=[{'name':m['name'],'size_vram':m.get('size_vram'),'size':m.get('size')} for m in LocalEmbedder().request('/api/ps')['models']]
(output.parent.parent/'reports'/'performance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
