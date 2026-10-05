"""Embedded Unicode fonts and line-wise Arabic shaping after logical wrapping."""
from functools import lru_cache
from importlib.resources import files
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable
from .i18n import get_language

def font_path():
    name='wqy-zenhei.ttc' if get_language() in ('zh','ja') else 'DejaVuSans.ttf'
    return str(files('easyecg_review').joinpath('fonts',name))

@lru_cache(maxsize=3)
def _register(group):
    root=files('easyecg_review').joinpath('fonts')
    if group=='cjk':
        pdfmetrics.registerFont(TTFont('ECGCJK',str(root.joinpath('wqy-zenhei.ttc')),subfontIndex=0))
        return 'ECGCJK','ECGCJK'
    pdfmetrics.registerFont(TTFont('ECGUnicode',str(root.joinpath('DejaVuSans.ttf'))))
    pdfmetrics.registerFont(TTFont('ECGUnicodeBold',str(root.joinpath('DejaVuSans-Bold.ttf'))))
    return 'ECGUnicode','ECGUnicodeBold'

def register_fonts():return _register('cjk' if get_language() in ('zh','ja') else 'latin')

def visual(text,language=None):
    if (language or get_language())!='ar':return str(text)
    import arabic_reshaper
    from bidi.algorithm import get_display
    return get_display(arabic_reshaper.reshape(str(text)),base_dir='R')

class Text(Flowable):
    """Plain text with predictable multilingual line breaking and RTL alignment."""
    def __init__(self,text,size=9,leading=None,bold=False,color=None,after=7):
        Flowable.__init__(self);self.text=str(text);self.size=size;self.leading=leading or size*1.45
        self.font=register_fonts()[int(bold)];self.color=color;self.spaceAfter=after;self.language=get_language()
    def wrap(self,width,height):
        self.width=width;self.lines=[]
        for paragraph in self.text.split('\n'):
            # Character breaks for CJK; whitespace breaks elsewhere, splitting
            # long tokens only when they cannot fit on a line by themselves.
            tokens=list(paragraph) if self.language in ('zh','ja') else paragraph.split(' ')
            separator='' if self.language in ('zh','ja') else ' '
            line=''
            for token in tokens:
                proposed=line+separator+token if line else token
                if line and pdfmetrics.stringWidth(visual(proposed,self.language),self.font,self.size)>width:
                    self.lines.append(line);line=''
                while token and pdfmetrics.stringWidth(visual(token,self.language),self.font,self.size)>width:
                    count=1
                    while count<len(token) and pdfmetrics.stringWidth(visual(token[:count+1],self.language),self.font,self.size)<=width:count+=1
                    self.lines.append(token[:count]);token=token[count:]
                line=line+separator+token if line else token
            self.lines.append(line)
        self.height=len(self.lines)*self.leading
        return width,self.height
    def split(self,width,height):
        self.wrap(width,height);count=int(height//self.leading)
        if count<1 or count>=len(self.lines):return []
        def part(lines):return Text('\n'.join(lines),self.size,self.leading,self.font==register_fonts()[1],self.color,self.spaceAfter)
        return [part(self.lines[:count]),part(self.lines[count:])]
    def draw(self):
        c=self.canv;c.setFont(self.font,self.size)
        if self.color is not None:c.setFillColor(self.color)
        for i,line in enumerate(self.lines):
            y=self.height-(i+1)*self.leading+self.leading-self.size
            if self.language=='ar':c.drawRightString(self.width,y,visual(line,self.language))
            else:c.drawString(0,y,line)

def line(c,x,y,text,width,size=8,bold=False,right=False):
    font=register_fonts()[int(bold)];text=visual(text)
    measured=pdfmetrics.stringWidth(text,font,size)
    if measured>width:size=max(4.5,size*width/measured)
    c.setFont(font,size)
    if right or get_language()=='ar':c.drawRightString(x+width,y,text)
    else:c.drawString(x,y,text)


def load_gui_fonts():
    """Register bundled fonts privately with Linux Fontconfig for Tk/Xft.

    PDF fonts are always embedded. On other platforms Tk uses its installed
    Unicode font fallback; missing optional font APIs never block the CLI.
    """
    import ctypes,ctypes.util,sys
    if not sys.platform.startswith('linux'):return
    name=ctypes.util.find_library('fontconfig')
    if not name:return
    try:
        fc=ctypes.CDLL(name)
        fc.FcConfigGetCurrent.restype=ctypes.c_void_p
        fc.FcConfigAppFontAddFile.argtypes=[ctypes.c_void_p,ctypes.c_char_p];fc.FcConfigAppFontAddFile.restype=ctypes.c_int
        fc.FcConfigBuildFonts.argtypes=[ctypes.c_void_p];fc.FcConfigBuildFonts.restype=ctypes.c_int
        config=fc.FcConfigGetCurrent()
        for font in ('DejaVuSans.ttf','DejaVuSans-Bold.ttf','wqy-zenhei.ttc'):
            fc.FcConfigAppFontAddFile(config,str(files('easyecg_review').joinpath('fonts',font)).encode())
        fc.FcConfigBuildFonts(config)
    except (OSError,AttributeError):pass
