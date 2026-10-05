"""Locale resources, isolation, CLI forwarding, and multilingual export checks."""
import json
from concurrent.futures import ThreadPoolExecutor
from string import Formatter
import numpy as np
import pytest
from pypdf import PdfReader
from easyecg_review.i18n import LANGUAGES,catalog,normalize,using_language,tr,get_language,preferred_language
from easyecg_review.gui import build_run_command
from easyecg_review.pdftext import register_fonts,visual,Text
from easyecg_review.cli import main
from conftest import synthetic,scp,index

@pytest.mark.parametrize('lang',LANGUAGES)
def test_complete_catalog_and_format_placeholders(lang):
    base=catalog('en');translated=catalog(lang)
    assert set(translated)==set(base)
    for key,value in translated.items():
        assert value and '\ufffd' not in value
        expected=sorted(field for _,field,_,_ in Formatter().parse(base[key]) if field)
        found=sorted(field for _,field,_,_ in Formatter().parse(value) if field)
        assert found==expected,(lang,key)
        with using_language(lang):assert tr(key,**dict.fromkeys(expected,3))

@pytest.mark.parametrize('lang',LANGUAGES)
def test_embedded_fonts_cover_every_catalog_glyph(lang):
    from reportlab.pdfbase import pdfmetrics
    with using_language(lang):
        for font in set(register_fonts()):
            glyphs=pdfmetrics.getFont(font).face.charToGlyph
            assert not {ch for text in catalog(lang).values() for ch in visual(text) if not ch.isspace() and ord(ch) not in glyphs}

@pytest.mark.parametrize('lang',LANGUAGES)
def test_cli_language_after_subcommand_and_gui_forwarding(lang,capsys):
    with pytest.raises(SystemExit) as ex:main(['run','--language',lang,'--help'])
    assert ex.value.code==0
    help_text=capsys.readouterr().out
    assert catalog(lang)['help_ids'] in ' '.join(help_text.split())
    with using_language(lang):
        cmd=build_run_command('source','output',[2,1])
        assert cmd[cmd.index('--language')+1]==lang
        with pytest.raises(ValueError,match=catalog(lang)['empty_selection'].replace('.','\\.')):build_run_command('s','o',[])

def test_locale_aliases_environment_and_settings(tmp_path,monkeypatch):
    assert normalize('pt-BR')=='pt'
    assert normalize('zh_CN.UTF-8')=='zh'
    assert normalize('no_NO')=='nb'
    with pytest.raises(ValueError):normalize('not-a-language')
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path));monkeypatch.delenv('EASYECG_LANGUAGE',raising=False)
    from easyecg_review.i18n import save_language
    save_language('fr');assert preferred_language()=='fr'
    monkeypatch.setenv('EASYECG_LANGUAGE','ja_JP');assert preferred_language()=='ja'

def test_thread_locale_isolation_and_restoration():
    def translate(lang):
        with using_language(lang):return tr('warning')
    with using_language('de'):
        with ThreadPoolExecutor() as pool:
            assert list(pool.map(translate,LANGUAGES))==[catalog(lang)['warning'] for lang in LANGUAGES]
        assert get_language()=='de'

def test_arabic_wraps_logically_then_shapes_each_line():
    with using_language('ar'):
        text=Text(tr('limitations'));text.wrap(140,800)
        assert len(text.lines)>5
        for logical in text.lines:
            assert len(visual(logical))>0
            assert text.font=='ECGUnicode'

@pytest.mark.parametrize('lang',['en','zh','ja','ar'])
def test_language_does_not_modify_raw_exports(tmp_path,lang):
    import pyedflib
    root=tmp_path/'device';(root/'ECG_0').mkdir(parents=True)
    raw,words,_=synthetic(duration=30)
    (root/'README.TXT').write_bytes(index([(1,1,1)]));(root/'ECG_0/1.SCP').write_bytes(scp(words))
    out=tmp_path/'output'
    assert main(['--language',lang,'run',str(root),'-o',str(out),'--recordings','1','--full-curves','--strips-per-kind','0'])==0
    manifest=json.loads((out/'manifest.json').read_text())
    assert manifest['language']==lang and len(manifest['catalog_sha256'])==64
    with pyedflib.EdfReader(str(next(out.glob('r*/*.edf')))) as reader:np.testing.assert_array_equal(reader.readSignal(0,digital=True),raw)
    for name,key in [('summary.pdf','pdf_title'),('review_strips.pdf','strips'),('full_curves.pdf','full_title')]:
        reader=PdfReader(out/name)
        assert reader.metadata.title==catalog(lang)[key]
        assert reader.pages
        # Font subsets are embedded with Unicode maps, including CJK/Arabic.
        fonts=reader.pages[0]['/Resources']['/Font'].get_object().values()
        assert any('/ToUnicode' in font.get_object() for font in fonts)
