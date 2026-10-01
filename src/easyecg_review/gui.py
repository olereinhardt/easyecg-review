"""Tk desktop UI with explicit, source-bound session selection."""
import json
import math
import queue
import subprocess
import sys
import threading
from pathlib import Path
from .io import list_recordings


def build_run_command(source,output,selected,gain=2.,notch='auto',full=False):
    """Pure helper shared by GUI tests; an empty selection never means all."""
    if not source or not output:raise ValueError('Bitte Eingang und Ausgabe wählen.')
    ids=sorted(set(map(int,selected)))
    if not ids:raise ValueError('Bitte mindestens eine Messreihe auswählen.')
    gain=float(gain)
    if not math.isfinite(gain) or not .25<=gain<=8:raise ValueError('Verstärkungsfaktor muss zwischen 0,25 und 8 liegen.')
    if notch not in ('auto','off','50','60'):raise ValueError('Ungültige Netzfilter-Auswahl.')
    cmd=[sys.executable,'-m','easyecg_review','run',source,'-o',output,'--recordings',*[str(i) for i in ids],
         '--gain-factor',str(gain),'--notch',notch]
    if full:cmd.append('--full-curves')
    return cmd


def launch():
    try:
        import tkinter as tk
        from tkinter import ttk,filedialog,messagebox
    except ImportError as ex:raise ValueError('GUI requires tkinter: sudo apt install python3-tk') from ex
    try:app=tk.Tk()
    except tk.TclError as ex:raise ValueError('GUI needs a graphical desktop; use easyecg run for headless operation') from ex
    app.title('Easy ECG Review 0.2');app.geometry('1020x790');app.minsize(800,650)
    source=tk.StringVar();output=tk.StringVar();full=tk.BooleanVar(value=False)
    gain=tk.StringVar(value='2.0');notch=tk.StringVar(value='auto');status=tk.StringVar(value='Eingang wählen, Messreihen laden und auswählen.')
    frame=ttk.Frame(app,padding=16);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='PC-80B: Konvertieren und Prüfbericht erstellen',font=('Sans',15,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Experimentelle Auswertung, keine Diagnose.').pack(anchor='w',pady=(4,8))
    controls=[];messages=queue.Queue();process=[None];inventory={'source':None,'generation':0};loading=[False]
    def browse_input(directory=False):
        path=filedialog.askdirectory() if directory else filedialog.askopenfilename(filetypes=[('ZIP','*.zip'),('Alle Dateien','*')])
        if path:source.set(path);load()
    def browse_output():
        path=filedialog.askdirectory(title='Übergeordneten Ausgabeordner wählen')
        if path:output.set(str(Path(path)/'easyecg-result'))
    for label,var in [('Eingang (ZIP oder Geräteordner)',source),('Neuer oder leerer Ausgabeordner',output)]:
        ttk.Label(frame,text=label).pack(anchor='w');entry=ttk.Entry(frame,textvariable=var);entry.pack(fill='x',pady=3);controls.append(entry)
    row=ttk.Frame(frame);row.pack(fill='x',pady=6)
    for text,command in [('ZIP wählen',lambda:browse_input()),('Geräteordner wählen',lambda:browse_input(True)),('Ausgabe wählen',browse_output)]:
        b=ttk.Button(row,text=text,command=command);b.pack(side='left',padx=(0,6));controls.append(b)
    table_frame=ttk.Frame(frame);table_frame.pack(fill='both',expand=True,pady=6)
    columns=('id','start','end','duration','files','state')
    tree=ttk.Treeview(table_frame,columns=columns,show='headings',selectmode='extended',height=8)
    for col,title,width in zip(columns,('Nr.','Beginn (Gerätezeit)','Ende (Gerätezeit)','Dauer ca.','Dateien','Inventar'),(45,175,175,85,85,230)):
        tree.heading(col,text=title);tree.column(col,width=width,minwidth=40,stretch=col=='state')
    scroll=ttk.Scrollbar(table_frame,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
    tree.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
    ttk.Label(frame,text='Mehrfachauswahl mit Strg / Umschalt. Zeitbasis: Geräteuhr; Inventar prüft nur Randdateien.').pack(anchor='w')
    selection_status=tk.StringVar(value='0 ausgewählt')
    def update_selection(*_):selection_status.set(f'{len(tree.selection())} von {len(tree.get_children())} ausgewählt')
    tree.bind('<<TreeviewSelect>>',update_selection)
    def load():
        if process[0] is not None:return
        if not source.get():messagebox.showerror('Fehlender Eingang','Bitte einen Eingang wählen.');return
        path=str(Path(source.get()).expanduser().resolve());inventory['generation']+=1;ticket=inventory['generation']
        inventory['source']=None;loading[0]=True;tree.delete(*tree.get_children());status.set('Lade Messreihen-Inventar ...');start_button.configure(state='disabled')
        def worker():
            try:messages.put(('inventory',ticket,path,list_recordings(Path(path)),None))
            except Exception as ex:messages.put(('inventory',ticket,path,None,str(ex)))
        threading.Thread(target=worker,daemon=True).start()
    selectrow=ttk.Frame(frame);selectrow.pack(fill='x',pady=6)
    for label,command in [('Messreihen laden',load),('Alle auswählen',lambda:tree.selection_set(tree.get_children())),('Keine auswählen',lambda:tree.selection_remove(tree.selection()))]:
        b=ttk.Button(selectrow,text=label,command=command);b.pack(side='left',padx=(0,6));controls.append(b)
    ttk.Label(selectrow,textvariable=selection_status).pack(side='left',padx=10)
    options=ttk.Frame(frame);options.pack(fill='x',pady=6)
    ttk.Label(options,text='PDF-Verstärkungsfaktor').pack(side='left');spin=ttk.Spinbox(options,from_=.25,to=8,increment=.25,textvariable=gain,width=7);spin.pack(side='left',padx=6);controls.append(spin)
    ttk.Label(options,text='2 = 20 mm/mV; 1 = bisherige Darstellung').pack(side='left')
    ttk.Label(options,text='Netzfilter').pack(side='left',padx=(16,4));combo=ttk.Combobox(options,textvariable=notch,values=('auto','off','50','60'),state='readonly',width=6);combo.pack(side='left');controls.append(combo)
    b=ttk.Checkbutton(frame,text='Zusätzlich vollständiges Rohkurven-PDF (viele Seiten)',variable=full);b.pack(anchor='w',pady=4);controls.append(b)
    ttk.Label(frame,text='Verstärkung verändert nur PDFs. EDF+/WFDB bleiben in originalen mV.').pack(anchor='w')
    log=tk.Text(frame,height=10,wrap='word');log.pack(fill='both',expand=True,pady=8)
    ttk.Label(frame,textvariable=status).pack(anchor='w')
    def enable_controls(enabled):
        for widget in controls:widget.configure(state='readonly' if enabled and widget is combo else 'normal' if enabled else 'disabled')
        start_button.configure(state='normal' if enabled and inventory['source'] else 'disabled')
    def reader(proc):
        for line in proc.stdout:messages.put(('log',line))
        messages.put(('done',proc.wait()))
    def start():
        if process[0] is not None or loading[0]:return
        try:
            path=str(Path(source.get()).expanduser().resolve())
            if inventory['source']!=path:raise ValueError('Eingang wurde geändert. Bitte Messreihen erneut laden.')
            command=build_run_command(path,output.get(),tree.selection(),gain.get().replace(',','.'),notch.get(),full.get())
            log.delete('1.0','end');process[0]=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        except (ValueError,OSError) as ex:messagebox.showerror('Start nicht möglich',str(ex));return
        enable_controls(False);status.set('Verarbeitung läuft ...');threading.Thread(target=reader,args=(process[0],),daemon=True).start()
    def stop():
        if process[0] is not None:process[0].terminate();status.set('Abbruch angefordert; fertige Messreihen bleiben erhalten.')
    def poll():
        while not messages.empty():
            item=messages.get()
            if item[0]=='log':log.insert('end',item[1]);log.see('end')
            elif item[0]=='done':
                process[0]=None;enable_controls(True);status.set('Fertig' if item[1]==0 else f'Beendet mit Status {item[1]}: Details im Protokoll.')
                if item[1]==0:messagebox.showinfo('Fertig','summary.pdf enthält die Übersicht. Die Auswertung ist unbestätigt.')
            elif item[0]=='inventory':
                _,ticket,path,rows,error=item
                if ticket!=inventory['generation']:continue
                loading[0]=False
                if error:status.set('Inventar konnte nicht geladen werden.');messagebox.showerror('Eingangsfehler',error);continue
                if path!=str(Path(source.get()).expanduser().resolve()):status.set('Eingang geändert; bitte erneut laden.');continue
                inventory['source']=path
                for r in rows:
                    state=r['error'] or (f"{r['missing_files']} fehlen" if r['missing_files'] else 'Randdateien OK; Rest bei Konvertierung')
                    tree.insert('', 'end',iid=str(r['index']),values=(r['index'],r['start_device_local'] or '?',r['end_device_local'] or '?',f"{r['duration_estimate_s']/60:g} min",f"{r['from']}..{r['to']}",state))
                tree.selection_set(tree.get_children());update_selection();start_button.configure(state='normal');status.set('Messreihen geladen. Auswahl vor dem Start prüfen.')
        app.after(100,poll)
    def invalidate(*_):
        inventory['source']=None;start_button.configure(state='disabled');status.set('Eingang geändert: Messreihen laden.')
    source.trace_add('write',invalidate)
    def close():
        if process[0] is not None:
            if not messagebox.askyesno('Abbrechen','Verarbeitung läuft. Beenden?'):return
            stop()
        app.destroy()
    footer=ttk.Frame(frame);footer.pack(fill='x',pady=8)
    start_button=ttk.Button(footer,text='Ausgewählte Messreihen konvertieren',command=start,state='disabled');start_button.pack(side='left')
    ttk.Button(footer,text='Abbrechen',command=stop).pack(side='left',padx=8)
    app.protocol('WM_DELETE_WINDOW',close);poll();app.mainloop()
