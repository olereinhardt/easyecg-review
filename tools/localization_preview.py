from pathlib import Path
import argparse,sys,json,tempfile
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Generate synthetic localization previews; no patient data.')
parser.add_argument('-o','--output',type=Path,default=Path('language-preview.pdf'))
args=parser.parse_args()
temporary=tempfile.TemporaryDirectory(prefix='easyecg-locales-')
TMP=Path(temporary.name)
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from conftest import synthetic,scp,index
from easyecg_review.io import load_recordings
from easyecg_review.analysis import analyze
from easyecg_review.report import summary_pdf,strips_pdf,full_pdf
from easyecg_review.i18n import LANGUAGES,using_language
from pypdf import PdfReader,PdfWriter
root=TMP/'input';(root/'ECG_0').mkdir(parents=True,exist_ok=True)
raw,words,beats=synthetic(duration=120)
(root/'README.TXT').write_bytes(index([(1,1,1)]));(root/'ECG_0/1.SCP').write_bytes(scp(words))
recordings,manifest=load_recordings(root)
results=[];filtered=[]
for rec in recordings:
 result,signal=analyze(rec.raw,rec.words,rec.fs,rec.scale);results.append(result);filtered.append(signal)
manifest['warnings'].append('SYNTHETIC LOCALIZATION TEST - NOT PATIENT DATA')
manifest['display']={'gain_factor':2,'review_mm_per_mv':20}
base=TMP/'reports';base.mkdir(parents=True,exist_ok=True)
writer=PdfWriter()
for lang in LANGUAGES:
 with using_language(lang):
  directory=base/lang;directory.mkdir(exist_ok=True)
  summary_pdf(directory/'summary.pdf',recordings,results,manifest)
  strips_pdf(directory/'strips.pdf',recordings,results,filtered,max_per_kind=0)
  full_pdf(directory/'full.pdf',recordings,results)
  reader=PdfReader(directory/'summary.pdf')
  for i,page in enumerate(reader.pages):
   writer.add_page(page)
  writer.add_page(PdfReader(directory/'strips.pdf').pages[0])
  print(lang,len(reader.pages),flush=True)
# Each preview page is marked independently so excerpts cannot be mistaken for
# a patient report. This technical test label is deliberately language-neutral.
import io
from reportlab.pdfgen import canvas
for page in writer.pages:
    buffer=io.BytesIO()
    c=canvas.Canvas(buffer,pagesize=(float(page.mediabox.width),float(page.mediabox.height)))
    c.setFont('Helvetica',7);c.setFillColorRGB(.45,.45,.45)
    c.drawString(45,7,'SYNTHETIC TEST ECG - NOT PATIENT DATA')
    c.save();buffer.seek(0)
    page.merge_page(PdfReader(buffer).pages[0])
writer.add_metadata({'/Title':'EasyECG 0.3.0 - synthetic localization previews (18 languages)','/Author':'easyecg-review'})
args.output.parent.mkdir(parents=True,exist_ok=True)
writer.write(args.output)
temporary.cleanup()
