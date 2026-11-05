import json
from contextlib import closing
import sqlite3
import threading
from pathlib import Path

import pytest
import customtkinter as ctk

import catalog_state
import desktop_app
import local_catalog
from local_catalog import rebuild_catalog, search_catalog
from preparation import prepare_all, index_status, profile_lock
from scope_paths import normalize_roots, path_key
from semantic_search import build_semantic_index, semantic_search, snapshot
from test_semantic_search import FakeEmbedder


def locations(tmp_path):
    a, b = tmp_path/'disk-a', tmp_path/'disk-b'
    a.mkdir(); b.mkdir()
    (a/'a.txt').write_text('Personel servis ulaşım maliyetleri.', encoding='utf-8')
    (b/'b.txt').write_text('Yemekhane menüsü.', encoding='utf-8')
    return a, b, tmp_path/'catalog.db', tmp_path/'semantic.db'


def test_incremental_scan_preserves_unchanged_rows_and_reads_only_changes(tmp_path, monkeypatch):
    a,b,cat,sem = locations(tmp_path)
    rebuild_catalog([a,b],cat)
    with closing(sqlite3.connect(cat)) as db, db:
        before = db.execute('SELECT file_path,id,indexed_at FROM documents ORDER BY file_path').fetchall()
    def never_read(*args, **kwargs):
        raise AssertionError('unchanged document must not be read')
    monkeypatch.setattr(local_catalog,'extract_content',never_read)
    report = rebuild_catalog([a,b],cat)
    assert report['updated'] == 0 and report['reused'] == 2
    with closing(sqlite3.connect(cat)) as db, db:
        assert db.execute('SELECT file_path,id,indexed_at FROM documents ORDER BY file_path').fetchall() == before
    (a/'a.txt').unlink()
    report = rebuild_catalog([a,b],cat)
    assert report['removed'] == 1 and report['indexed'] == 1


def test_disconnected_root_preserved_and_explicit_removal_prunes_it(tmp_path):
    a,b,cat,sem = locations(tmp_path)
    rebuild_catalog([a,b],cat)
    offline = tmp_path/'unmounted'
    b.rename(offline)
    report = rebuild_catalog([a,b],cat)
    assert report['preserved'] == 1 and report['unavailable_roots'] == [str(b)]
    assert search_catalog(cat,'b.txt','Dosya adı')['total_count'] == 1
    report = rebuild_catalog([a],cat)
    assert report['removed'] == 1 and report['indexed'] == 1
    offline.rename(b)
    assert rebuild_catalog([a,b],cat)['updated'] == 1


def test_all_roots_offline_keep_previous_index(tmp_path):
    a,b,cat,sem = locations(tmp_path)
    rebuild_catalog([a,b],cat)
    a.rename(tmp_path/'off-a'); b.rename(tmp_path/'off-b')
    report = rebuild_catalog([a,b],cat)
    assert report['preserved'] == 2 and report['content'] == 2


def test_walk_permission_error_preserves_subtree_but_deletes_missing_files(tmp_path, monkeypatch):
    a,b,cat,sem = locations(tmp_path)
    child=a/'blocked'; child.mkdir()
    (child/'keep.txt').write_text('keep',encoding='utf-8')
    rebuild_catalog([a],cat)
    original_walk=local_catalog.os.walk
    def walk(root, **kwargs):
        kwargs['onerror'](PermissionError(13,'offline',str(child)))
        yield str(a), [], []
    monkeypatch.setattr(local_catalog.os,'walk',walk)
    report=rebuild_catalog([a],cat)
    assert report['preserved'] == 1
    assert search_catalog(cat,'keep','Dosya adı')['total_count'] == 1
    assert search_catalog(cat,'a.txt','Dosya adı')['total_count'] == 0


def test_volume_change_does_not_reuse_same_size_same_timestamp(tmp_path, monkeypatch):
    a,b,cat,sem = locations(tmp_path)
    monkeypatch.setattr(local_catalog,'volume_identity',lambda root:'disk-1')
    rebuild_catalog([a],cat)
    monkeypatch.setattr(local_catalog,'volume_identity',lambda root:'disk-2')
    report=rebuild_catalog([a],cat)
    assert report['updated'] == 1 and report['reused'] == 0


def test_scope_normalization_handles_overlap_case_and_unc():
    roots=normalize_roots([r'\\NAS\Office\Reports',r'\\nas\office',r'\\NAS\Office'])
    assert len(roots)==1
    assert path_key(roots[0]) == path_key(r'\\NAS\Office')


def test_mapped_and_unc_aliases_are_deduplicated(tmp_path, monkeypatch):
    import scope_paths
    original=scope_paths.canonical_path
    def canonical(path):
        if str(path).lower() in {r'z:\reports',r'\\nas\reports'}:
            return str(tmp_path/'reports')
        return original(path)
    monkeypatch.setattr(scope_paths,'canonical_path',canonical)
    assert len(scope_paths.normalize_roots([r'Z:\Reports',r'\\NAS\Reports'])) == 1


def test_warm_snapshot_reused_and_catalog_change_invalidates(tmp_path, monkeypatch):
    a,b,cat,sem=locations(tmp_path)
    model=FakeEmbedder()
    rebuild_catalog([a,b],cat)
    build_semantic_index(cat,sem,embedder=model)
    first=snapshot(cat,sem)
    monkeypatch.setattr('semantic_search.read_documents',lambda *_: (_ for _ in ()).throw(AssertionError('all text read')))
    assert snapshot(cat,sem) is first
    assert semantic_search(cat,sem,'ulaşım',embedder=model)['results'][0]['file_name']=='a.txt'
    (b/'b.txt').unlink()
    rebuild_catalog([a,b],cat)
    assert snapshot(cat,sem) is not first
    with pytest.raises(ValueError,match='değişmiş'):
        semantic_search(cat,sem,'ulaşım',embedder=model)


def test_snapshot_detects_external_sql_changes(tmp_path):
    a,b,cat,sem=locations(tmp_path); model=FakeEmbedder()
    rebuild_catalog([a],cat); build_semantic_index(cat,sem,embedder=model)
    semantic_search(cat,sem,'ulaşım',embedder=model)
    with closing(sqlite3.connect(cat)) as db, db:
        db.execute("UPDATE documents SET content='new content'")
    with pytest.raises(ValueError,match='değişmiş'):
        semantic_search(cat,sem,'ulaşım',embedder=model)


def test_cancel_preserves_active_index_and_resume_uses_committed_work(tmp_path):
    a,b,cat,sem=locations(tmp_path); model=FakeEmbedder()
    rebuild_catalog([a,b],cat); build_semantic_index(cat,sem,embedder=model)
    before=sem.read_bytes()
    (a/'a.txt').write_text('Updated personnel transport budget and service details.',encoding='utf-8')
    rebuild_catalog([a,b],cat)
    cancel=threading.Event()
    with pytest.raises(InterruptedError):
        build_semantic_index(cat,sem,lambda *args:cancel.set(),cancel,model)
    assert sem.read_bytes()==before
    result=semantic_search(cat,sem,'ulaşım',embedder=model,allow_stale=True,roots=[a])
    assert result['stale'] and len(result['results'])==1
    calls=model.calls
    report=build_semantic_index(cat,sem,embedder=model)
    assert report['cached']==2 and model.calls==calls
    assert not Path(str(sem)+'.pending').exists()


def test_cross_document_batches_reduce_model_calls(tmp_path):
    a,b,cat,sem=locations(tmp_path); model=FakeEmbedder()
    rebuild_catalog([a,b],cat)
    report=build_semantic_index(cat,sem,embedder=model)
    assert model.calls==1 and report['updated']==2


def test_single_preparation_updates_readiness_and_same_profile_lock(tmp_path):
    a,b,cat,sem=locations(tmp_path); model=FakeEmbedder(); updates=[]
    assert not index_status(cat,sem)['can_search']
    report=prepare_all([a,b],cat,sem,updates.append,embedder=model)
    assert report['semantic']['documents']==2
    assert index_status(cat,sem,[a,b],False)['current']
    assert index_status(cat,sem,[a],False)['reason']=='scope'
    assert any(event['stage']=='semantic' for event in updates)
    with profile_lock(cat):
        with pytest.raises(RuntimeError,match='başka'):
            with profile_lock(cat): pass


def test_fresh_ui_guides_to_preparation_and_translates_notice(tk_root,tmp_path,monkeypatch):
    monkeypatch.setattr(desktop_app,'SETTINGS',tmp_path/'settings.json')
    monkeypatch.setattr(desktop_app,'DATABASE',tmp_path/'catalog.db')
    monkeypatch.setattr(desktop_app,'SEMANTIC_DATABASE',tmp_path/'semantic.db')
    window=ctk.CTkToplevel(tk_root); window.withdraw()
    app=desktop_app.SearchApp(window)
    try:
        assert not app.ready_status['can_search']
        assert app.search_button.cget('state')=='disabled'
        assert app.preparation_banner.winfo_manager()=='grid'
        app.query.insert('1.0','Remembered document contents')
        app.search()
        assert app.active_page=='Dizin durumu'
        app.change_language('English')
        assert 'not ready' in app.preparation_notice.get()
        assert app.query.get('1.0','end-1c')=='Remembered document contents'
    finally: app.close()


def test_ui_one_button_runs_pipeline_and_allows_search_during_update(tk_root,tmp_path,monkeypatch):
    import time
    a,b,cat,sem=locations(tmp_path)
    model=FakeEmbedder()
    monkeypatch.setattr(desktop_app,'SETTINGS',tmp_path/'settings.json')
    monkeypatch.setattr(desktop_app,'DATABASE',cat)
    monkeypatch.setattr(desktop_app,'SEMANTIC_DATABASE',sem)
    monkeypatch.setattr(desktop_app,'warm_search',lambda *args:None)
    real_prepare=prepare_all
    monkeypatch.setattr(desktop_app,'prepare_all',lambda *args:real_prepare(*args,embedder=model))
    monkeypatch.setattr(desktop_app,'semantic_search',lambda *args,**kwargs:semantic_search(*args,embedder=model,**kwargs))
    window=ctk.CTkToplevel(tk_root); window.withdraw()
    app=desktop_app.SearchApp(window)
    try:
        app.folders.delete(0,'end'); app.folders.insert('end',str(a)); app.folders.insert('end',str(b))
        app.prepare_all()
        deadline=time.monotonic()+10
        while app.busy and time.monotonic()<deadline:
            window.update(); time.sleep(.02)
        assert not app.busy and app.ready_status['current']
        assert app.search_button.cget('state')=='normal'
        app.query.insert('1.0','servis ulaşım')
        # Keep a replacement preparation pending while the last ready index serves a query.
        app.preparing=app.busy=True
        app.search()
        while app.search_busy and time.monotonic()<deadline:
            window.update(); time.sleep(.02)
        assert not app.search_busy and app.rows
        assert app.busy and app.preparing
    finally:
        app.busy=app.preparing=False
        app.close()


def test_warmup_reports_changed_model_before_search(tmp_path,monkeypatch):
    import semantic_search as engine
    a,b,cat,sem=locations(tmp_path); model=FakeEmbedder()
    rebuild_catalog([a],cat); build_semantic_index(cat,sem,embedder=model)
    model.digest='replacement-model'
    monkeypatch.setattr(engine,'LocalEmbedder',lambda:model)
    with pytest.raises(ValueError,match='Model değişmiş'):
        engine.warm_search(cat,sem)


def test_own_delivery_outputs_are_not_recursively_indexed(tmp_path,monkeypatch):
    root=tmp_path/'scope'; root.mkdir()
    internal=root/'agent'/'validation'; internal.mkdir(parents=True)
    (internal/'private-test.txt').write_text('synthetic agent test',encoding='utf-8')
    ordinary=root/'validation'; ordinary.mkdir()
    (ordinary/'user-report.txt').write_text('real user report',encoding='utf-8')
    monkeypatch.setattr(local_catalog,'INTERNAL_OUTPUTS',(internal,))
    cat=tmp_path/'catalog.db'
    report=rebuild_catalog([root],cat)
    assert report['indexed']==1
    assert search_catalog(cat,'user-report','Dosya adı')['total_count']==1


def test_readiness_never_loads_the_search_matrix(tmp_path,monkeypatch):
    import semantic_search as engine
    a,b,cat,sem=locations(tmp_path); model=FakeEmbedder()
    rebuild_catalog([a],cat); build_semantic_index(cat,sem,embedder=model)
    monkeypatch.setattr(engine,'snapshot',lambda *args:(_ for _ in ()).throw(AssertionError('readiness loaded all vectors')))
    assert index_status(cat,sem,[a],False)['current']


def test_legacy_mapped_paths_are_rewritten_before_disconnect(tmp_path,monkeypatch):
    import scope_paths
    a,b,cat,sem=locations(tmp_path)
    rebuild_catalog([a],cat)
    actual=str(a/'a.txt'); alias=r'Z:\Reports\a.txt'
    with closing(sqlite3.connect(cat)) as db, db:
        db.execute('UPDATE documents SET file_path=?',(alias,))
    original=scope_paths.canonical_path
    monkeypatch.setattr(scope_paths,'canonical_path',lambda p:actual if str(p)==alias else original(p))
    rebuild_catalog([a],cat)
    with closing(sqlite3.connect(cat)) as db:
        assert db.execute('SELECT file_path FROM documents').fetchone()[0]==actual
    monkeypatch.setattr(scope_paths,'canonical_path',original)
    a.rename(tmp_path/'disconnected')
    assert rebuild_catalog([a],cat)['preserved']==1
