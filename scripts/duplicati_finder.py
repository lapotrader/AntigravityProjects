#!/usr/bin/env python3
"""
Interfaccia Grafica per trovare e gestire file duplicati.
Identifica i file per: nome, dimensione e data di modifica.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from collections import defaultdict
from datetime import datetime
import threading
import hashlib

def formatta_dimensione(byte):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if byte < 1024.0:
            return f"{byte:.2f} {unit}"
        byte /= 1024.0
    return f"{byte:.2f} PB"

def formatta_data(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

class DuplicatiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ricerca Duplicati Pro")
        self.root.geometry("1000x750")
        
        self.duplicati = {}
        self.directory = tk.StringVar()
        self.sempre_conferma = tk.BooleanVar(value=True)
        
        self.setup_ui()

    def setup_ui(self):
        # Frame Superiore: Configurazione
        frame_top = ttk.LabelFrame(self.root, text=" Configurazione Scansione ", padding=10)
        frame_top.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(frame_top, text="Percorso:").pack(side="left")
        ttk.Entry(frame_top, textvariable=self.directory, width=60).pack(side="left", padx=5)
        ttk.Button(frame_top, text="Sfoglia...", command=self.seleziona_cartella).pack(side="left")
        ttk.Button(frame_top, text="AVVIA SCAN", command=self.avvia_scansione_thread).pack(side="left", padx=10)
        self.btn_auto = ttk.Button(frame_top, text="PULIZIA AUTOMATICA", command=self.conferma_e_pulisci_tutto, state="disabled")
        self.btn_auto.pack(side="left")

        ttk.Checkbutton(frame_top, text="Chiedi sempre conferma", 
                        variable=self.sempre_conferma).pack(side="right", padx=10)

        # Status bar
        self.status_label = ttk.Label(self.root, text="Seleziona una cartella per iniziare.")
        self.status_label.pack(anchor="w", padx=15)
        
        # Tabella Risultati (Treeview)
        self.tree = ttk.Treeview(self.root, columns=("nome", "dim", "copie", "data"), show="headings", height=15)
        self.tree.heading("nome", text="Nome File")
        self.tree.heading("dim", text="Dimensione")
        self.tree.heading("copie", text="Copie")
        self.tree.heading("data", text="Data Modifica")
        self.tree.column("nome", width=350)
        self.tree.column("dim", width=100)
        self.tree.column("copie", width=60)
        self.tree.column("data", width=150)
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.mostra_dettagli_gruppo)

        # Frame Inferiore: Dettagli e Azione
        frame_bottom = ttk.LabelFrame(self.root, text=" Gestione Duplicati: Scegli quale file LASCIARE ", padding=10)
        frame_bottom.pack(fill="x", padx=10, pady=10)

        self.listbox_percorsi = tk.Listbox(frame_bottom, height=5, font=("Consolas", 9))
        self.listbox_percorsi.pack(fill="x", side="left", expand=True)
        
        scrollbar = ttk.Scrollbar(frame_bottom, orient="vertical", command=self.listbox_percorsi.yview)
        scrollbar.pack(side="left", fill="y")
        self.listbox_percorsi.config(yscrollcommand=scrollbar.set)

        self.btn_elimina = ttk.Button(frame_bottom, text="ELIMINA ALTRI\n(Mantieni selezionato)", 
                                     command=self.conferma_ed_elimina, state="disabled")
        self.btn_elimina.pack(side="right", padx=10)

    def seleziona_cartella(self):
        cartella = filedialog.askdirectory()
        if cartella:
            self.directory.set(cartella)

    def calcola_hash(self, percorso):
        """Calcola hash MD5 per verifica integrità contenuto."""
        hash_md5 = hashlib.md5()
        try:
            with open(percorso, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except:
            return None

    def avvia_scansione_thread(self):
        path = self.directory.get()
        if not os.path.isdir(path):
            messagebox.showerror("Errore", "Per favore seleziona un percorso valido.")
            return
        
        self.status_label.config(text="Analisi metadati in corso...")
        self.tree.delete(*self.tree.get_children())
        self.btn_elimina.config(state="disabled")
        self.btn_auto.config(state="disabled")
        threading.Thread(target=self.esegui_scansione, args=(path,), daemon=True).start()

    def esegui_scansione(self, directory):
        temp_dict = defaultdict(list)
        count = 0
        
        # Fase 1: Scansione veloce metadati (Nome, Dimensione, Data)
        for root, _, files in os.walk(directory):
            for filename in files:
                full_path = os.path.join(root, filename)
                try:
                    stat = os.stat(full_path)
                    chiave = (filename, stat.st_size, stat.st_mtime)
                    temp_dict[chiave].append(full_path)
                    count += 1
                    if count % 1000 == 0:
                        self.root.after(0, lambda c=count: self.status_label.config(text=f"Analizzati {c} file..."))
                except:
                    continue

        # Fase 2: Verifica Reale Contenuto (Hash MD5) solo per i sospetti
        self.duplicati = {}
        sospetti = [v for v in temp_dict.items() if len(v[1]) > 1]
        
        self.root.after(0, lambda: self.status_label.config(text=f"Verifica binaria di {len(sospetti)} gruppi di file..."))
        
        for i, (chiave_meta, percorsi) in enumerate(sospetti):
            hash_groups = defaultdict(list)
            for p in percorsi:
                h = self.calcola_hash(p)
                if h:
                    nuova_chiave = chiave_meta + (h,)
                    hash_groups[nuova_chiave].append(p)
            
            # Aggiorna lo stato per mostrare il progresso della verifica binaria
            self.root.after(0, lambda idx=i: self.status_label.config(text=f"Verifica binaria: {idx + 1}/{len(sospetti)} gruppi analizzati."))

            for k, v in hash_groups.items():
                if len(v) > 1:
                    self.duplicati[k] = v

        self.root.after(0, self.mostra_risultati)

    def mostra_risultati(self):
        self.status_label.config(text=f"Analisi completata. Trovati {len(self.duplicati)} gruppi identici al 100%.")
        for chiave, percorsi in self.duplicati.items():
            nome, dim, data, h = chiave
            self.tree.insert("", "end", values=(nome, formatta_dimensione(dim), len(percorsi), formatta_data(data)), iid=str(chiave))
        
        if self.duplicati:
            self.btn_auto.config(state="normal")

    def mostra_dettagli_gruppo(self, event):
        selected = self.tree.selection()
        if not selected: return
        
        self.listbox_percorsi.delete(0, tk.END)
        chiave_str = selected[0]
        
        # Cerchiamo la chiave nel dizionario
        for k, v in self.duplicati.items():
            if str(k) == chiave_str:
                for p in v:
                    self.listbox_percorsi.insert(tk.END, p)
                self.listbox_percorsi.select_set(0) # Default: lascia il primo
                self.btn_elimina.config(state="normal")
                break

    def conferma_ed_elimina(self):
        selected_tree = self.tree.selection()
        if not selected_tree: return
        
        keep_idx = self.listbox_percorsi.curselection()
        if not keep_idx:
            messagebox.showwarning("Attenzione", "Seleziona il file che vuoi mantenere!")
            return
        
        idx = keep_idx[0]
        chiave_str = selected_tree[0]
        
        # Identifica i file da eliminare
        percorsi_tutti = []
        chiave_vera = None
        for k, v in self.duplicati.items():
            if str(k) == chiave_str:
                percorsi_tutti = v
                chiave_vera = k
                break
        
        file_da_mantenere = percorsi_tutti[idx]
        file_da_cancellare = [p for i, p in enumerate(percorsi_tutti) if i != idx]

        if self.sempre_conferma.get():
            conferma = messagebox.askyesno("Conferma", 
                f"Elimino {len(file_da_cancellare)} file e lascio solo:\n{file_da_mantenere}\n\nSei sicuro?")
            if not conferma: return

        # Procedi con l'eliminazione
        errori = 0
        for f in file_da_cancellare:
            try:
                os.remove(f)
            except Exception as e:
                print(f"Errore su {f}: {e}")
                errori += 1

        if errori == 0:
            messagebox.showinfo("Fatto", f"Eliminati {len(file_da_cancellare)} file con successo.")
        else:
            messagebox.showwarning("Completato con errori", f"Eliminati {len(file_da_cancellare)-errori} file. {errori} errori riscontrati.")

        # Pulisci UI
        self.tree.delete(chiave_str)
        self.listbox_percorsi.delete(0, tk.END)
        self.btn_elimina.config(state="disabled")
        del self.duplicati[chiave_vera]
        self.status_label.config(text=f"Duplicati rimanenti: {len(self.duplicati)}")

    def conferma_e_pulisci_tutto(self):
        """Mantiene il primo file di ogni gruppo e cancella tutti gli altri automaticamente."""
        if not self.duplicati: return
        
        count_file_da_eliminare = sum(len(v) - 1 for v in self.duplicati.values())
        
        if self.sempre_conferma.get():
            domanda = f"Stai per avviare la pulizia automatica.\n\n" \
                      f"Verranno eliminati {count_file_da_eliminare} file duplicati.\n" \
                      f"Per ogni gruppo, il sistema manterrà solo la prima copia trovata.\n\n" \
                      f"Vuoi procedere?"
            if not messagebox.askyesno("Conferma Pulizia Totale", domanda):
                return

        eliminati = 0
        for chiave in list(self.duplicati.keys()):
            percorsi = self.duplicati[chiave]
            # Il primo [0] si salva, gli altri [1:] vengono eliminati
            for f in percorsi[1:]:
                try:
                    os.remove(f)
                    eliminati += 1
                except: pass
            del self.duplicati[chiave]

        self.tree.delete(*self.tree.get_children())
        self.status_label.config(text=f"Pulizia completata: rimossi {eliminati} file.")
        messagebox.showinfo("Fine Lavoro", f"Operazione conclusa.\nFile eliminati: {eliminati}")

if __name__ == "__main__":
    root = tk.Tk()
    # Stile un po' più moderno
    style = ttk.Style()
    if 'winnative' in style.theme_names():
        style.theme_use('winnative')
    
    app = DuplicatiApp(root)
    root.mainloop()