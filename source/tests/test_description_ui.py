from types import SimpleNamespace

import pytest

from desktop_app import SearchApp


def make_app(description):
    app = SearchApp.__new__(SearchApp)
    app.busy = False
    app.query = SimpleNamespace(get=lambda start, end: description)
    app.extension = SimpleNamespace(get=lambda: '')
    app.start_task = lambda kind, function, message: function()
    return app


def test_main_search_always_uses_semantics_and_preserves_summary(monkeypatch):
    summary = 'Aklımda dosyanın başındaki değerlendirme kaldı.\nSonra ayrı bir bölümde sonuçlar açıklanıyordu.'
    calls = []
    def semantic(catalog, index, query, extension):
        calls.append(query)
        return {'results': [], 'total_count': 0}
    def literal(*args, **kwargs):
        raise AssertionError('Ana arama tam kelime aramasına dönmemeli')
    monkeypatch.setattr('desktop_app.semantic_search', semantic)
    monkeypatch.setattr('desktop_app.search_catalog', literal)
    make_app(summary).search()
    assert calls == [summary]


def test_model_failure_never_silently_falls_back_to_words(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError('Model erişilemiyor')
    def literal(*args, **kwargs):
        raise AssertionError('Model hatasında kelime araması yapılmamalı')
    monkeypatch.setattr('desktop_app.semantic_search', unavailable)
    monkeypatch.setattr('desktop_app.search_catalog', literal)
    with pytest.raises(RuntimeError, match='Model erişilemiyor'):
        make_app('Hatırladığım bölümün kısa özeti').search()
