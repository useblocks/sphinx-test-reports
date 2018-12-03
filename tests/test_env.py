from sphinx_testing import with_app


@with_app(buildername='html', srcdir='doc_test/env_report_doc')
def test_doc_env_report_build_html(app, status, warning):
    app.build()
    html = (app.outdir / 'index.html').read_text()
    assert '<h1>Test-Env report' in html
    assert '<th class="head">Variable</th>' in html
