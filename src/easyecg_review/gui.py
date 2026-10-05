"""Tk desktop UI with source-bound selection and live language switching."""
import math
import queue
import subprocess
import sys
import threading
from pathlib import Path
from .io import list_recordings
from .pdftext import visual,load_gui_fonts
from .i18n import LANGUAGES,tr,get_language,set_language,preferred_language,save_language,error_text


def build_run_command(source,output,selected,gain=2.,notch='auto',full=False,language=None):
    if not source or not output:raise ValueError(tr('missing_input'))
    ids=sorted(set(map(int,selected)))
    if not ids:raise ValueError(tr('empty_selection'))
    gain=float(gain)
    if not math.isfinite(gain) or not .25<=gain<=8:raise ValueError(tr('invalid_gain'))
    if notch not in ('auto','off','50','60'):raise ValueError(tr('invalid_notch'))
    cmd=[sys.executable,'-m','easyecg_review','run',source,'-o',output,'--recordings',*[str(i) for i in ids],
         '--gain-factor',str(gain),'--notch',notch,'--language',language or get_language()]
    if full:cmd.append('--full-curves')
    return cmd


def launch(language=None):
    set_language(language or preferred_language())
    load_gui_fonts()
    try:
        import tkinter as tk
        from tkinter import ttk,filedialog,messagebox
        import tkinter.font as tkfont
    except ImportError as ex:raise ValueError(tr('gui_tk')) from ex
    try:app=tk.Tk()
    except tk.TclError as ex:raise ValueError(tr('gui_display')) from ex
    app.title('Easy ECG Review 0.3');app.geometry('1120x880');app.minsize(850,750)
    def ui(key,**values):return visual(tr(key,**values))
    display_languages={code:visual(name,'ar') if code=='ar' else name for code,name in LANGUAGES.items()}
    source=tk.StringVar();output=tk.StringVar();full=tk.BooleanVar(value=False)
    gain=tk.StringVar(value='2.0');notch=tk.StringVar(value='auto')
    status=tk.StringVar();status_message=['ready',{}]
    frame=ttk.Frame(app,padding=16);frame.pack(fill='both',expand=True)
    bindings=[];controls=[];messages=queue.Queue();process=[None]
    inventory={'source':None,'generation':0};loading=[False];inventory_rows=[]
    def status_set(key,**values):status_message[:]=[key,values];status.set(ui(key,**values))
    def widget(cls,parent,key,**kwargs):
        w=cls(parent,text=ui(key),**kwargs);bindings.append((w,key));return w
    langrow=ttk.Frame(frame);langrow.pack(fill='x',pady=(0,8))
    widget(ttk.Label,langrow,'language').pack(side='left')
    language_var=tk.StringVar(value=display_languages[get_language()])
    language_combo=ttk.Combobox(langrow,textvariable=language_var,values=list(display_languages.values()),state='readonly',width=22)
    language_combo.pack(side='left',padx=8);controls.append(language_combo)
    widget(ttk.Label,frame,'heading',font=('Sans',15,'bold')).pack(anchor='w')
    widget(ttk.Label,frame,'warning',wraplength=1050).pack(fill='x',pady=(4,8))
    def browse_input(directory=False):
        path=filedialog.askdirectory() if directory else filedialog.askopenfilename(filetypes=[('ZIP','*.zip'),(ui('all_files'),'*')])
        if path:source.set(path);load()
    def browse_output():
        path=filedialog.askdirectory(title=ui('choose_output'))
        if path:output.set(str(Path(path)/'easyecg-result'))
    for key,var in [('source',source),('output',output)]:
        widget(ttk.Label,frame,key).pack(anchor='w')
        entry=ttk.Entry(frame,textvariable=var);entry.pack(fill='x',pady=3);controls.append(entry)
    row=ttk.Frame(frame);row.pack(fill='x',pady=6)
    for key,command in [('zip',lambda:browse_input()),('folder',lambda:browse_input(True)),('choose_output',browse_output)]:
        b=widget(ttk.Button,row,key,command=command);b.pack(side='left',padx=(0,6));controls.append(b)
    table_frame=ttk.Frame(frame);table_frame.pack(fill='both',expand=True,pady=6)
    columns=('id','start','end','duration','files','inventory')
    tree=ttk.Treeview(table_frame,columns=columns,show='headings',selectmode='extended',height=8)
    for col,width in zip(columns,(55,175,175,90,90,320)):
        tree.heading(col,text=ui(col));tree.column(col,width=width,minwidth=40,stretch=col=='inventory')
    scroll=ttk.Scrollbar(table_frame,orient='vertical',command=tree.yview)
    hscroll=ttk.Scrollbar(table_frame,orient='horizontal',command=tree.xview)
    tree.configure(yscrollcommand=scroll.set,xscrollcommand=hscroll.set)
    tree.grid(row=0,column=0,sticky='nsew');scroll.grid(row=0,column=1,sticky='ns');hscroll.grid(row=1,column=0,sticky='ew')
    table_frame.rowconfigure(0,weight=1);table_frame.columnconfigure(0,weight=1)
    widget(ttk.Label,frame,'select_help',wraplength=1050).pack(fill='x')
    selection_status=tk.StringVar()
    def update_selection(*_):selection_status.set(ui('selection',selected=len(tree.selection()),total=len(tree.get_children())))
    tree.bind('<<TreeviewSelect>>',update_selection)
    def populate():
        selected=tree.selection();tree.delete(*tree.get_children())
        for r in inventory_rows:
            state=visual(error_text(r['error'])) if r['error'] else ui('missing_files',count=r['missing_files']) if r['missing_files'] else ui('boundary_ok')
            tree.insert('', 'end',iid=str(r['index']),values=(r['index'],r['start_device_local'] or '?',r['end_device_local'] or '?',
                f"{r['duration_estimate_s']/60:g} min",f"{r['from']}..{r['to']}",state))
        tree.selection_set([i for i in selected if tree.exists(i)]);update_selection()
    def change_language(*_):
        code=next(k for k,v in display_languages.items() if v==language_var.get());set_language(code)
        family='WenQuanYi Zen Hei' if code in ('zh','ja') else 'DejaVu Sans'
        for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont','TkCaptionFont'):
            tkfont.nametofont(name).configure(family=family,size=10)
        try:save_language(code)
        except OSError as ex:log.insert('end',str(ex)+'\n')
        for w,key in bindings:
            w.configure(text=ui(key))
            if isinstance(w,ttk.Label):w.configure(anchor='e' if code=='ar' else 'w',justify='right' if code=='ar' else 'left')
        for col,width in zip(columns,(55,175,175,90,90,320)):
            tree.heading(col,text=ui(col))
            tree.column(col,width=max(width,tkfont.nametofont('TkHeadingFont').measure(ui(col))+18))
        status_label.configure(anchor='e' if code=='ar' else 'w')
        log.tag_configure('rtl',justify='right')
        status_set(status_message[0],**status_message[1]);populate()
    language_combo.bind('<<ComboboxSelected>>',change_language)
    def load():
        if process[0] is not None:return
        if not source.get():messagebox.showerror(ui('error'),ui('missing_input'));return
        path=str(Path(source.get()).expanduser().resolve());inventory['generation']+=1;ticket=inventory['generation']
        inventory['source']=None;loading[0]=True;inventory_rows.clear();tree.delete(*tree.get_children());update_selection()
        status_set('loading');start_button.configure(state='disabled')
        def worker():
            try:messages.put(('inventory',ticket,path,list_recordings(Path(path)),None))
            except Exception as ex:messages.put(('inventory',ticket,path,None,str(ex)))
        threading.Thread(target=worker,daemon=True).start()
    selectrow=ttk.Frame(frame);selectrow.pack(fill='x',pady=6)
    for key,command in [('load',load),('all',lambda:tree.selection_set(tree.get_children())),('none',lambda:tree.selection_remove(tree.selection()))]:
        b=widget(ttk.Button,selectrow,key,command=command);b.pack(side='left',padx=(0,6));controls.append(b)
    ttk.Label(selectrow,textvariable=selection_status).pack(side='left',padx=10)
    options=ttk.Frame(frame);options.pack(fill='x',pady=6)
    widget(ttk.Label,options,'gain').pack(side='left')
    spin=ttk.Spinbox(options,from_=.25,to=8,increment=.25,textvariable=gain,width=7);spin.pack(side='left',padx=6);controls.append(spin)
    widget(ttk.Label,options,'gain_help').pack(side='left')
    widget(ttk.Label,options,'notch').pack(side='left',padx=(16,4))
    combo=ttk.Combobox(options,textvariable=notch,values=('auto','off','50','60'),state='readonly',width=6);combo.pack(side='left');controls.append(combo)
    b=widget(ttk.Checkbutton,frame,'full',variable=full);b.pack(anchor='w',pady=4);controls.append(b)
    widget(ttk.Label,frame,'raw_help',wraplength=1050).pack(fill='x')
    log=tk.Text(frame,height=8,wrap='word');log.pack(fill='both',expand=True,pady=8)
    status_label=ttk.Label(frame,textvariable=status,wraplength=1050,anchor='e' if get_language()=='ar' else 'w');status_label.pack(fill='x')
    def enable_controls(enabled):
        for w in controls:w.configure(state='readonly' if enabled and w in (combo,language_combo) else 'normal' if enabled else 'disabled')
        start_button.configure(state='normal' if enabled and inventory['source'] else 'disabled')
    def reader(proc):
        for line in proc.stdout:messages.put(('log',line))
        messages.put(('done',proc.wait()))
    def start():
        if process[0] is not None or loading[0]:return
        try:
            path=str(Path(source.get()).expanduser().resolve())
            if inventory['source']!=path:raise ValueError(tr('changed'))
            cmd=build_run_command(path,output.get(),tree.selection(),gain.get().replace(',','.'),notch.get(),full.get())
            log.delete('1.0','end');process[0]=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8',bufsize=1)
        except (ValueError,OSError) as ex:messagebox.showerror(ui('error'),visual(error_text(ex)));return
        enable_controls(False);status_set('processing');threading.Thread(target=reader,args=(process[0],),daemon=True).start()
    def stop():
        if process[0] is not None:process[0].terminate();status_set('stopped')
    def poll():
        while not messages.empty():
            item=messages.get()
            if item[0]=='log':log.insert('end',visual(item[1]),'rtl' if get_language()=='ar' else ());log.see('end')
            elif item[0]=='done':
                process[0]=None;enable_controls(True)
                status_set('done') if item[1]==0 else status_set('failed',code=item[1])
                if item[1]==0:messagebox.showinfo(ui('done'),ui('finish_info'))
            elif item[0]=='inventory':
                _,ticket,path,rows,error=item
                if ticket!=inventory['generation']:continue
                loading[0]=False
                if error:status_set('error');messagebox.showerror(ui('error'),visual(error_text(error)));continue
                if path!=str(Path(source.get()).expanduser().resolve()):status_set('changed');continue
                inventory['source']=path;inventory_rows[:]=rows;populate();tree.selection_set(tree.get_children());update_selection()
                start_button.configure(state='normal');status_set('loaded')
        app.after(100,poll)
    def invalidate(*_):
        inventory['source']=None;start_button.configure(state='disabled');status_set('changed')
    source.trace_add('write',invalidate)
    def close():
        if process[0] is not None:
            if not messagebox.askyesno(ui('cancel'),ui('close_question')):return
            stop()
        app.destroy()
    footer=ttk.Frame(frame);footer.pack(fill='x',pady=8)
    start_button=widget(ttk.Button,footer,'convert',command=start,state='disabled');start_button.pack(side='left')
    widget(ttk.Button,footer,'cancel',command=stop).pack(side='left',padx=8)
    app.protocol('WM_DELETE_WINDOW',close);status_set('ready');update_selection();change_language();poll();app.mainloop()
