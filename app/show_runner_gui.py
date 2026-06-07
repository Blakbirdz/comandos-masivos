import csv
import difflib
import json
import queue
import re
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    import telnetlib
except ImportError:
    import telnetlib3.telnetlib as telnetlib

try:
    import paramiko
except ImportError:
    paramiko = None

PROMPT_RE = re.compile(r'[>#]\s?$')

class CredentialRow:
    def __init__(self, parent, remove_callback):
        self.frame = tk.Frame(parent, bg='#35343c', bd=1, relief='flat', highlightthickness=1, highlightbackground='#42414a')
        self.user_var = tk.StringVar()
        self.pass_var = tk.StringVar()
        self.type_var = tk.StringVar(value='ssh|telnet')
        self.visible = False
        self.remove_callback = remove_callback
        self.frame.grid_columnconfigure(0, weight=3)
        self.frame.grid_columnconfigure(1, weight=3)
        self.frame.grid_columnconfigure(2, weight=2)
        self.user_entry = tk.Entry(self.frame, textvariable=self.user_var, bg='#17171d', fg='#f4f4f5', insertbackground='#f4f4f5', relief='flat')
        self.pass_entry = tk.Entry(self.frame, textvariable=self.pass_var, show='*', bg='#17171d', fg='#f4f4f5', insertbackground='#f4f4f5', relief='flat')
        self.type_combo = ttk.Combobox(self.frame, textvariable=self.type_var, values=['ssh', 'telnet', 'ssh|telnet'], state='readonly')
        self.toggle_btn = tk.Button(self.frame, text='👁', command=self.toggle_password, bg='#17171d', fg='#d1d5db', relief='flat', activebackground='#24242c', activeforeground='#ffffff', cursor='hand2')
        self.delete_btn = tk.Button(self.frame, text='✕', command=lambda: self.remove_callback(self), bg='#ff8a24', fg='white', relief='flat', activebackground='#e97816', activeforeground='white', cursor='hand2', width=3)
        self.user_entry.grid(row=0, column=0, sticky='ew', padx=(12, 8), pady=10, ipady=8)
        self.pass_entry.grid(row=0, column=1, sticky='ew', padx=(0, 4), pady=10, ipady=8)
        self.toggle_btn.grid(row=0, column=2, sticky='w', padx=(0, 8), pady=10)
        self.type_combo.grid(row=0, column=2, sticky='ew', padx=(42, 52), pady=10)
        self.delete_btn.grid(row=0, column=3, sticky='e', padx=(0, 12), pady=10)

    def toggle_password(self):
        self.visible = not self.visible
        self.pass_entry.config(show='' if self.visible else '*')
        self.toggle_btn.config(text='🙈' if self.visible else '👁')

    def get_data(self):
        return {'username': self.user_var.get().strip(), 'password': self.pass_var.get(), 'protocols': [p.strip().lower() for p in self.type_var.get().split('|') if p.strip()]}

class App:
    def __init__(self, root):
        self.root = root
        self.root.title('SH Masivo')
        self.root.geometry('1460x940')
        self.root.configure(bg='#17171d')
        self.log_queue = queue.Queue()
        self.worker = None
        self.stop_flag = threading.Event()
        self.credential_rows = []
        self.logo_image = self.create_logo()
        self.metrics = {'total': 0, 'processed': 0, 'success': 0, 'failed': 0, 'last_run': '-', 'failed_hosts': []}
        self.build_styles()
        self.build_ui()
        self.root.after(150, self.flush_logs)

    def build_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('Dark.TFrame', background='#17171d')
        self.style.configure('Panel.TFrame', background='#121219')
        self.style.configure('Card.TFrame', background='#24242c')
        self.style.configure('Title.TLabel', background='#17171d', foreground='#f5f5f5', font=('Segoe UI Semibold', 20))
        self.style.configure('Muted.TLabel', background='#17171d', foreground='#9ca3af', font=('Segoe UI', 10))
        self.style.configure('Dark.TButton', font=('Segoe UI', 10), padding=8)
        self.style.map('Dark.TButton', background=[('active', '#34343c')])
        self.style.configure('Accent.TButton', font=('Segoe UI Semibold', 10), padding=10, background='#ff8a24', foreground='white', borderwidth=0)
        self.style.map('Accent.TButton', background=[('active', '#e97816')])
        self.style.configure('Dark.TCombobox', fieldbackground='#17171d', foreground='#f4f4f5', bordercolor='#3d3d45', arrowsize=14)
        self.style.configure('Horizontal.TProgressbar', troughcolor='#17171d', background='#ff8a24', bordercolor='#17171d', lightcolor='#ff8a24', darkcolor='#ff8a24')

    def create_logo(self):
        img = tk.PhotoImage(width=48, height=48)
        img.put('#000000', to=(0, 0, 48, 48))
        for x1, y1, x2, y2, color in [(7, 8, 41, 30, '#ff8a24'), (10, 11, 38, 27, '#1d1d24'), (16, 33, 32, 36, '#ff8a24'), (13, 36, 35, 39, '#c86b19'), (21, 30, 27, 33, '#ffb26b')]:
            img.put(color, to=(x1, y1, x2, y2))
        return img

    def build_ui(self):
        main = ttk.Frame(self.root, style='Dark.TFrame')
        main.pack(fill='both', expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        sidebar = ttk.Frame(main, style='Panel.TFrame', width=240)
        sidebar.grid(row=0, column=0, sticky='nsw')
        sidebar.grid_propagate(False)

        logo_wrap = tk.Frame(sidebar, bg='#121219')
        logo_wrap.pack(fill='x', padx=18, pady=(18, 12))
        tk.Label(logo_wrap, image=self.logo_image, bg='#121219').pack(side='left')
        text_wrap = tk.Frame(logo_wrap, bg='#121219')
        text_wrap.pack(side='left', padx=12)
        tk.Label(text_wrap, text='SH Masivo', fg='#f5f5f5', bg='#121219', font=('Segoe UI Semibold', 16)).pack(anchor='w')
        tk.Label(text_wrap, text='Recolección y comparación', fg='#8f96a3', bg='#121219', font=('Segoe UI', 9)).pack(anchor='w')

        self.nav_var = tk.StringVar(value='runner')
        self.runner_nav = tk.Button(sidebar, text='SH Masivo', command=lambda: self.switch_module('runner'), bg='#2a2a32', fg='#f5f5f5', anchor='w', padx=20, pady=12, font=('Segoe UI', 11, 'bold'), relief='flat', activebackground='#353540', activeforeground='#ffffff', cursor='hand2')
        self.compare_nav = tk.Button(sidebar, text='Comparador TXT', command=lambda: self.switch_module('compare'), bg='#121219', fg='#b7bdc9', anchor='w', padx=20, pady=12, font=('Segoe UI', 11), relief='flat', activebackground='#2a2a32', activeforeground='#ffffff', cursor='hand2')
        self.runner_nav.pack(fill='x', padx=8, pady=(8, 4))
        self.compare_nav.pack(fill='x', padx=8, pady=(0, 8))

        right_wrap = ttk.Frame(main, style='Dark.TFrame')
        right_wrap.grid(row=0, column=1, sticky='nsew')
        right_wrap.columnconfigure(0, weight=1)
        right_wrap.rowconfigure(0, weight=1)

        canvas = tk.Canvas(right_wrap, bg='#17171d', highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_wrap, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')
        canvas.grid(row=0, column=0, sticky='nsew')

        content = ttk.Frame(canvas, style='Dark.TFrame', padding=18)
        content.columnconfigure(0, weight=1)
        canvas_window = canvas.create_window((0, 0), window=content, anchor='nw')

        content.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfig(canvas_window, width=event.width))
        canvas.bind_all('<MouseWheel>', lambda event: canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units'))

        self.runner_frame = ttk.Frame(content, style='Dark.TFrame')
        self.runner_frame.grid(row=0, column=0, sticky='nsew')
        self.runner_frame.columnconfigure(0, weight=1)
        self.build_runner_module(self.runner_frame)

        self.compare_frame = ttk.Frame(content, style='Dark.TFrame')
        self.compare_frame.grid(row=0, column=0, sticky='nsew')
        self.compare_frame.columnconfigure(0, weight=1)
        self.build_compare_module(self.compare_frame)
        self.compare_frame.grid_remove()

    def switch_module(self, name):
        self.nav_var.set(name)
        if name == 'runner':
            self.runner_frame.grid()
            self.compare_frame.grid_remove()
            self.runner_nav.config(bg='#2a2a32', fg='#f5f5f5', font=('Segoe UI', 11, 'bold'))
            self.compare_nav.config(bg='#121219', fg='#b7bdc9', font=('Segoe UI', 11))
        else:
            self.compare_frame.grid()
            self.runner_frame.grid_remove()
            self.compare_nav.config(bg='#2a2a32', fg='#f5f5f5', font=('Segoe UI', 11, 'bold'))
            self.runner_nav.config(bg='#121219', fg='#b7bdc9', font=('Segoe UI', 11))

    def build_runner_module(self, content):
        header = ttk.Frame(content, style='Dark.TFrame')
        header.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text='SH Masivo', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(header, text='Panel de ejecución masiva SSH y Telnet con resultados por hostname.', style='Muted.TLabel').grid(row=1, column=0, sticky='w', pady=(4, 0))

        metrics_grid = ttk.Frame(content, style='Dark.TFrame')
        metrics_grid.grid(row=1, column=0, sticky='ew', pady=(0, 14))
        for i in range(4):
            metrics_grid.columnconfigure(i, weight=1)
        self.total_value = tk.StringVar(value='0')
        self.last_run_value = tk.StringVar(value='-')
        self.success_value = tk.StringVar(value='0')
        self.failed_value = tk.StringVar(value='0')
        self.total_hint = tk.StringVar(value='0 equipos cargados')
        self.last_run_hint = tk.StringVar(value='Sin ejecuciones')
        self.success_hint = tk.StringVar(value='0.0% tasa de éxito')
        self.failed_hint = tk.StringVar(value='Sin fallos')
        self.metric_card(metrics_grid, 0, 'Dispositivos', self.total_value, self.total_hint)
        self.metric_card(metrics_grid, 1, 'Última ejecución', self.last_run_value, self.last_run_hint)
        self.metric_card(metrics_grid, 2, 'Exitosos', self.success_value, self.success_hint)
        self.metric_card(metrics_grid, 3, 'Fallidos', self.failed_value, self.failed_hint)

        top_grid = ttk.Frame(content, style='Dark.TFrame')
        top_grid.grid(row=2, column=0, sticky='ew')
        top_grid.columnconfigure(0, weight=1)
        top_grid.columnconfigure(1, weight=1)
        self.targets_card = self.card(top_grid, 'Equipos', 'IPs o hostnames, uno por línea.')
        self.targets_card.grid(row=0, column=0, sticky='nsew', padx=(0, 10))
        self.commands_card = self.card(top_grid, 'Comandos', 'Comandos show, uno por línea.')
        self.commands_card.grid(row=0, column=1, sticky='nsew', padx=(10, 0))
        self.targets_text = self.dark_text(self.targets_card, 10)
        self.targets_text.pack(fill='both', expand=True, padx=18, pady=(0, 18))
        self.targets_text.bind('<KeyRelease>', self.refresh_target_counter)
        self.commands_text = self.dark_text(self.commands_card, 10)
        self.commands_text.pack(fill='both', expand=True, padx=18, pady=(0, 18))

        self.credentials_card = self.card(content, 'Etiquetas de credenciales', 'Agrega usuario, contraseña y tipo en recuadros separados.')
        self.credentials_card.grid(row=3, column=0, sticky='ew', pady=14)
        header_row = tk.Frame(self.credentials_card, bg='#24242c')
        header_row.pack(fill='x', padx=18, pady=(2, 0))
        tk.Label(header_row, text='Usuario', bg='#24242c', fg='#aeb4c0', font=('Segoe UI Semibold', 10)).grid(row=0, column=0, sticky='w', padx=(0, 8))
        tk.Label(header_row, text='Contraseña', bg='#24242c', fg='#aeb4c0', font=('Segoe UI Semibold', 10)).grid(row=0, column=1, sticky='w', padx=(0, 8))
        tk.Label(header_row, text='Tipo', bg='#24242c', fg='#aeb4c0', font=('Segoe UI Semibold', 10)).grid(row=0, column=2, sticky='w')
        header_row.grid_columnconfigure(0, weight=3)
        header_row.grid_columnconfigure(1, weight=3)
        header_row.grid_columnconfigure(2, weight=2)
        self.rows_container = tk.Frame(self.credentials_card, bg='#24242c')
        self.rows_container.pack(fill='x', padx=18, pady=10)
        actions = tk.Frame(self.credentials_card, bg='#24242c')
        actions.pack(fill='x', padx=18, pady=(0, 18))
        ttk.Button(actions, text='Agregar credencial', style='Dark.TButton', command=self.add_credential_row).pack(side='left')
        self.add_credential_row()

        settings_card = self.card(content, 'Configuración', 'Parámetros generales de conexión y salida.')
        settings_card.grid(row=4, column=0, sticky='ew', pady=(0, 14))
        settings_inner = tk.Frame(settings_card, bg='#24242c')
        settings_inner.pack(fill='x', padx=18, pady=(4, 18))
        settings_inner.columnconfigure(0, weight=1)
        settings_inner.columnconfigure(1, weight=1)
        self.timeout_var = tk.StringVar(value='8')
        self.delay_var = tk.StringVar(value='1.0')
        self.enable_var = tk.StringVar()
        self.output_var = tk.StringVar(value=str(Path.cwd() / 'show_runner_output'))
        self.labeled_entry(settings_inner, 'Timeout (s)', self.timeout_var, 0, 0)
        self.labeled_entry(settings_inner, 'Delay entre comandos (s)', self.delay_var, 0, 1)
        self.labeled_entry(settings_inner, 'Enable password', self.enable_var, 1, 0, show='*')
        self.labeled_path(settings_inner, 'Carpeta base salida', self.output_var, 1, 1)
        buttons = tk.Frame(settings_inner, bg='#24242c')
        buttons.grid(row=2, column=0, columnspan=2, sticky='w', pady=(16, 0))
        self.run_btn = ttk.Button(buttons, text='Ejecutar pruebas', style='Accent.TButton', command=self.start_run)
        self.run_btn.pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Detener', style='Dark.TButton', command=self.stop_run).pack(side='left', padx=8)
        ttk.Button(buttons, text='Guardar configuración', style='Dark.TButton', command=self.save_config).pack(side='left', padx=8)
        self.status_var = tk.StringVar(value='Listo.')
        tk.Label(settings_inner, textvariable=self.status_var, bg='#24242c', fg='#8f96a3', font=('Segoe UI', 10)).grid(row=3, column=0, columnspan=2, sticky='w', pady=(16, 0))

        progress_card = self.card(content, 'Progreso actual', 'Seguimiento consolidado del avance por equipos.')
        progress_card.grid(row=5, column=0, sticky='ew', pady=(0, 14))
        progress_inner = tk.Frame(progress_card, bg='#24242c')
        progress_inner.pack(fill='x', padx=18, pady=(4, 18))
        self.progress_main_var = tk.StringVar(value='0 / 0 dispositivos')
        self.progress_state_var = tk.StringVar(value='En espera')
        tk.Label(progress_inner, textvariable=self.progress_main_var, bg='#24242c', fg='#f5f5f5', font=('Consolas', 20, 'bold')).pack(anchor='w')
        tk.Label(progress_inner, textvariable=self.progress_state_var, bg='#24242c', fg='#8f96a3', font=('Segoe UI', 10)).pack(anchor='w', pady=(8, 10))
        self.progress = ttk.Progressbar(progress_inner, style='Horizontal.TProgressbar', orient='horizontal', mode='determinate', maximum=100, value=0)
        self.progress.pack(fill='x')

        logs_card = self.card(content, 'Logs en tiempo real', 'Estado de conexión, autenticación y ejecución en un bloque independiente.')
        logs_card.grid(row=6, column=0, sticky='ew')
        self.logs = tk.Text(logs_card, height=14, wrap='word', font=('Consolas', 10), bg='#17171d', fg='#d9f99d', insertbackground='#d9f99d', relief='flat')
        self.logs.pack(fill='both', expand=True, padx=18, pady=(0, 12))
        failed_wrap = tk.Frame(logs_card, bg='#24242c')
        failed_wrap.pack(fill='both', expand=True, padx=18, pady=(0, 18))
        tk.Label(failed_wrap, text='INFORME DE EQUIPOS FALLIDOS', bg='#24242c', fg='#8f96a3', font=('Segoe UI Semibold', 9)).pack(anchor='w', pady=(0, 8))
        self.failed_report = tk.Text(failed_wrap, height=7, wrap='word', font=('Consolas', 10), bg='#17171d', fg='#fca5a5', insertbackground='#fca5a5', relief='flat')
        self.failed_report.pack(fill='both', expand=True)
        self.refresh_target_counter()

    def build_compare_module(self, content):
        header = ttk.Frame(content, style='Dark.TFrame')
        header.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text='Comparador TXT', style='Title.TLabel').grid(row=0, column=0, sticky='w')
        ttk.Label(header, text='Compara dos archivos de texto y muestra las líneas donde existen diferencias.', style='Muted.TLabel').grid(row=1, column=0, sticky='w', pady=(4, 0))

        paths = self.card(content, 'Archivos a comparar', 'Selecciona los dos TXT que deseas revisar.')
        paths.grid(row=1, column=0, sticky='ew', pady=(0, 14))
        inner = tk.Frame(paths, bg='#24242c')
        inner.pack(fill='x', padx=18, pady=(4, 18))
        inner.columnconfigure(0, weight=1)
        self.file_a_var = tk.StringVar()
        self.file_b_var = tk.StringVar()
        self.labeled_file(inner, 'Archivo A', self.file_a_var, 0)
        self.labeled_file(inner, 'Archivo B', self.file_b_var, 1)
        buttons = tk.Frame(inner, bg='#24242c')
        buttons.grid(row=2, column=0, sticky='w', pady=(16, 0))
        ttk.Button(buttons, text='Comparar TXT', style='Accent.TButton', command=self.compare_txt_files).pack(side='left', padx=(0, 8))
        ttk.Button(buttons, text='Limpiar resultado', style='Dark.TButton', command=self.clear_compare).pack(side='left', padx=8)

        summary = self.card(content, 'Resultado de comparación', 'Lista de diferencias detectadas por número de línea.')
        summary.grid(row=2, column=0, sticky='ew')
        self.compare_summary_var = tk.StringVar(value='Aún no se ha ejecutado ninguna comparación.')
        tk.Label(summary, textvariable=self.compare_summary_var, bg='#24242c', fg='#b4bac5', font=('Segoe UI', 10)).pack(anchor='w', padx=18, pady=(0, 8))
        self.compare_result = tk.Text(summary, height=24, wrap='none', font=('Consolas', 10), bg='#17171d', fg='#f4f4f5', insertbackground='#f4f4f5', relief='flat')
        self.compare_result.pack(fill='both', expand=True, padx=18, pady=(0, 18))

    def metric_card(self, parent, col, title, value_var, hint_var):
        wrap = tk.Frame(parent, bg='#24242c', highlightthickness=1, highlightbackground='#2e2d36')
        wrap.grid(row=0, column=col, sticky='nsew', padx=(0 if col == 0 else 8, 8 if col < 3 else 0))
        inner = tk.Frame(wrap, bg='#24242c')
        inner.pack(fill='both', expand=True, padx=22, pady=20)
        tk.Label(inner, text=title, bg='#24242c', fg='#8f96a3', font=('Segoe UI Semibold', 10)).pack(anchor='w')
        tk.Label(inner, textvariable=value_var, bg='#24242c', fg='#f5f5f5', font=('Consolas', 27, 'bold')).pack(anchor='w', pady=(10, 6))
        tk.Label(inner, textvariable=hint_var, bg='#24242c', fg='#7f8592', font=('Consolas', 10)).pack(anchor='w')

    def choose_output_dir(self):
        selected = filedialog.askdirectory(initialdir=self.output_var.get().strip() or str(Path.home()), title='Seleccionar carpeta base de salida')
        if selected:
            self.output_var.set(selected)

    def choose_file(self, var):
        selected = filedialog.askopenfilename(title='Seleccionar TXT', filetypes=[('TXT', '*.txt'), ('Todos los archivos', '*.*')])
        if selected:
            var.set(selected)

    def card(self, parent, title, text):
        card = ttk.Frame(parent, style='Card.TFrame', padding=0)
        head = tk.Frame(card, bg='#24242c')
        head.pack(fill='x', padx=18, pady=(18, 10))
        tk.Label(head, text=title.upper(), bg='#24242c', fg='#8f96a3', font=('Segoe UI Semibold', 9)).pack(anchor='w')
        tk.Label(head, text=text, bg='#24242c', fg='#b4bac5', font=('Segoe UI', 10)).pack(anchor='w', pady=(8, 0))
        return card

    def dark_text(self, parent, height):
        return tk.Text(parent, height=height, wrap='none', font=('Consolas', 10), bg='#17171d', fg='#f4f4f5', insertbackground='#f4f4f5', relief='flat')

    def labeled_entry(self, parent, label, var, row, col, show=None):
        wrap = tk.Frame(parent, bg='#24242c')
        wrap.grid(row=row, column=col, sticky='ew', padx=(0 if col == 0 else 10, 10 if col == 0 else 0), pady=8)
        tk.Label(wrap, text=label, bg='#24242c', fg='#aeb4c0', anchor='w', font=('Segoe UI Semibold', 10)).pack(fill='x', pady=(0, 6))
        entry = tk.Entry(wrap, textvariable=var, show=show, bg='#17171d', fg='#f4f4f5', insertbackground='#f4f4f5', relief='flat')
        entry.pack(fill='x', ipady=9)
        return entry

    def labeled_path(self, parent, label, var, row, col):
        wrap = tk.Frame(parent, bg='#24242c')
        wrap.grid(row=row, column=col, sticky='ew', padx=(0 if col == 0 else 10, 10 if col == 0 else 0), pady=8)
        wrap.columnconfigure(0, weight=1)
        tk.Label(wrap, text=label, bg='#24242c', fg='#aeb4c0', anchor='w', font=('Segoe UI Semibold', 10)).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 6))
        entry = tk.Entry(wrap, textvariable=var, bg='#17171d', fg='#f4f4f5', insertbackground='#f4f4f5', relief='flat')
        entry.grid(row=1, column=0, sticky='ew', ipady=9)
        tk.Button(wrap, text='...', command=self.choose_output_dir, bg='#ff8a24', fg='white', relief='flat', activebackground='#e97816', activeforeground='white', cursor='hand2', width=4).grid(row=1, column=1, padx=(8, 0))
        return entry

    def labeled_file(self, parent, label, var, row):
        wrap = tk.Frame(parent, bg='#24242c')
        wrap.grid(row=row, column=0, sticky='ew', pady=8)
        wrap.columnconfigure(0, weight=1)
        tk.Label(wrap, text=label, bg='#24242c', fg='#aeb4c0', anchor='w', font=('Segoe UI Semibold', 10)).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 6))
        tk.Entry(wrap, textvariable=var, bg='#17171d', fg='#f4f4f5', insertbackground='#f4f4f5', relief='flat').grid(row=1, column=0, sticky='ew', ipady=9)
        tk.Button(wrap, text='...', command=lambda: self.choose_file(var), bg='#ff8a24', fg='white', relief='flat', activebackground='#e97816', activeforeground='white', cursor='hand2', width=4).grid(row=1, column=1, padx=(8, 0))

    def add_credential_row(self):
        row = CredentialRow(self.rows_container, self.remove_credential_row)
        row.frame.pack(fill='x', pady=6)
        self.credential_rows.append(row)

    def remove_credential_row(self, row):
        if len(self.credential_rows) == 1:
            messagebox.showwarning('Credenciales', 'Debes dejar al menos una fila de credencial.')
            return
        row.frame.destroy()
        self.credential_rows.remove(row)

    def refresh_target_counter(self, *_args):
        total = len([x.strip() for x in self.targets_text.get('1.0', 'end').splitlines() if x.strip()]) if hasattr(self, 'targets_text') else 0
        self.metrics['total'] = total
        self.update_metrics_visuals()

    def update_metrics_visuals(self):
        total = self.metrics.get('total', 0)
        processed = self.metrics.get('processed', 0)
        success = self.metrics.get('success', 0)
        failed = self.metrics.get('failed', 0)
        self.total_value.set(str(total))
        self.last_run_value.set(self.metrics.get('last_run', '-'))
        self.success_value.set(str(success))
        self.failed_value.set(str(failed).zfill(2) if failed < 100 else str(failed))
        self.total_hint.set(f'{total} equipos cargados')
        self.last_run_hint.set('Sin ejecuciones' if self.metrics.get('last_run', '-') == '-' else datetime.now().strftime('%d-%b').upper())
        rate = (success / total * 100) if total else 0
        self.success_hint.set(f'{rate:.1f}% tasa de éxito')
        self.failed_hint.set('Sin fallos' if failed == 0 else ', '.join(self.metrics.get('failed_hosts', [])[:3]) + ('...' if failed > 3 else ''))
        self.progress_main_var.set(f'{processed} / {total} dispositivos')
        self.progress['value'] = (processed / total * 100) if total else 0
        if processed == 0:
            self.progress_state_var.set('En espera')
        elif processed < total:
            self.progress_state_var.set(f'Procesando, {success} exitosos y {failed} fallidos')
        else:
            self.progress_state_var.set(f'Finalizado, {success} exitosos y {failed} fallidos')

    def update_failed_report(self):
        self.failed_report.delete('1.0', 'end')
        failed_hosts = self.metrics.get('failed_hosts', [])
        if not failed_hosts:
            self.failed_report.insert('end', 'Sin equipos fallidos al momento.\n')
            return
        self.failed_report.insert('end', 'Equipos sin acceso exitoso:\n\n')
        for idx, host in enumerate(failed_hosts, 1):
            self.failed_report.insert('end', f'{idx:02d}. {host}\n')

    def compare_txt_files(self):
        file_a = self.file_a_var.get().strip()
        file_b = self.file_b_var.get().strip()
        if not file_a or not file_b:
            messagebox.showerror('Archivos faltantes', 'Debes seleccionar ambos archivos TXT.')
            return
        try:
            a_lines = Path(file_a).read_text(encoding='utf-8', errors='ignore').splitlines()
            b_lines = Path(file_b).read_text(encoding='utf-8', errors='ignore').splitlines()
        except Exception as exc:
            messagebox.showerror('Error leyendo archivos', str(exc))
            return
        self.compare_result.delete('1.0', 'end')
        max_len = max(len(a_lines), len(b_lines))
        diff_count = 0
        report_lines = []
        for i in range(max_len):
            left = a_lines[i] if i < len(a_lines) else '<SIN CONTENIDO>'
            right = b_lines[i] if i < len(b_lines) else '<SIN CONTENIDO>'
            if left != right:
                diff_count += 1
                report_lines.append(f'Línea {i+1}:')
                report_lines.append(f'  A: {left}')
                report_lines.append(f'  B: {right}')
                report_lines.append('')
        if diff_count == 0:
            self.compare_summary_var.set('No se encontraron diferencias entre ambos TXT.')
            self.compare_result.insert('end', 'Los archivos son idénticos línea por línea.\n')
        else:
            self.compare_summary_var.set(f'Se encontraron {diff_count} diferencias de línea.')
            self.compare_result.insert('end', '\n'.join(report_lines))

    def clear_compare(self):
        self.file_a_var.set('')
        self.file_b_var.set('')
        self.compare_summary_var.set('Aún no se ha ejecutado ninguna comparación.')
        self.compare_result.delete('1.0', 'end')

    def save_config(self):
        cfg = self.collect_config()
        if not cfg:
            return
        path = filedialog.asksaveasfilename(defaultextension='.json', filetypes=[('JSON', '*.json')])
        if path:
            Path(path).write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
            self.log(f'Configuración guardada en {path}')

    def log(self, message):
        stamp = datetime.now().strftime('%H:%M:%S')
        self.log_queue.put(f'[{stamp}] {message}\n')

    def flush_logs(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                self.logs.insert('end', item)
                self.logs.see('end')
        except queue.Empty:
            pass
        self.root.after(150, self.flush_logs)

    def collect_config(self):
        targets = [x.strip() for x in self.targets_text.get('1.0', 'end').splitlines() if x.strip()]
        commands = [x.strip() for x in self.commands_text.get('1.0', 'end').splitlines() if x.strip()]
        credentials = []
        for row in self.credential_rows:
            data = row.get_data()
            if not data['username'] and not data['password']:
                continue
            if not data['username'] or not data['password']:
                messagebox.showerror('Credencial inválida', 'Cada fila debe tener usuario y contraseña.')
                return None
            credentials.append(data)
        if not targets or not commands or not credentials:
            messagebox.showerror('Datos incompletos', 'Debes ingresar equipos, comandos y al menos una credencial.')
            return None
        try:
            timeout = int(self.timeout_var.get().strip())
            delay = float(self.delay_var.get().strip())
        except ValueError:
            messagebox.showerror('Valor inválido', 'Timeout o delay no tienen un formato numérico válido.')
            return None
        return {'targets': targets, 'commands': commands, 'credentials': credentials, 'timeout': timeout, 'enable_password': self.enable_var.get(), 'delay': delay, 'output_base': self.output_var.get().strip()}

    def start_run(self):
        if self.worker and self.worker.is_alive():
            messagebox.showwarning('En ejecución', 'Ya existe una tarea en ejecución.')
            return
        if paramiko is None:
            messagebox.showerror('Dependencia faltante', 'No se encontró paramiko. Instala dependencias antes de ejecutar.')
            return
        cfg = self.collect_config()
        if not cfg:
            return
        self.stop_flag.clear()
        self.metrics.update({'total': len(cfg['targets']), 'processed': 0, 'success': 0, 'failed': 0, 'last_run': datetime.now().strftime('%H:%M:%S'), 'failed_hosts': []})
        self.update_metrics_visuals()
        self.update_failed_report()
        self.logs.delete('1.0', 'end')
        self.run_btn.state(['disabled'])
        self.status_var.set('Ejecutando...')
        self.worker = threading.Thread(target=self.run_job, args=(cfg,), daemon=True)
        self.worker.start()

    def stop_run(self):
        self.stop_flag.set()
        self.log('Solicitud de detención recibida. Se detendrá al finalizar la operación actual.')

    def read_until_prompt_ssh(self, channel, timeout):
        end = time.time() + timeout
        data = ''
        while time.time() < end and not self.stop_flag.is_set():
            if channel.recv_ready():
                data += channel.recv(65535).decode(errors='ignore')
                lines = data.splitlines()
                if lines and PROMPT_RE.search(lines[-1]):
                    break
            else:
                time.sleep(0.2)
        return data

    def get_ssh_hostname(self, channel, timeout, fallback):
        channel.send('\n')
        data = self.read_until_prompt_ssh(channel, timeout)
        for line in reversed([x.strip() for x in data.splitlines() if x.strip()]):
            m = re.match(r'^([A-Za-z0-9_.-]+)[>#]$', line)
            if m:
                return m.group(1)
        return fallback

    def try_ssh(self, host, cred, commands, timeout, enable_password, delay):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            self.log(f'{host}: intentando SSH con {cred["username"]}')
            client.connect(hostname=host, username=cred['username'], password=cred['password'], timeout=timeout, look_for_keys=False, allow_agent=False)
            channel = client.invoke_shell()
            time.sleep(1)
            output = self.read_until_prompt_ssh(channel, timeout)
            detected_hostname = self.get_ssh_hostname(channel, timeout, host)
            channel.send('terminal length 0\n')
            output += self.read_until_prompt_ssh(channel, timeout)
            if enable_password:
                self.log(f'{host}: ejecutando enable por SSH')
                channel.send('enable\n')
                output += self.read_until_prompt_ssh(channel, 2)
                channel.send(enable_password + '\n')
                output += self.read_until_prompt_ssh(channel, timeout)
                detected_hostname = self.get_ssh_hostname(channel, timeout, detected_hostname)
            for cmd in commands:
                if self.stop_flag.is_set():
                    raise RuntimeError('Proceso detenido por el usuario')
                self.log(f'{host}: ejecutando {cmd} por SSH')
                channel.send(cmd + '\n')
                time.sleep(delay)
                output += f"\n{'='*20} {cmd} {'='*20}\n"
                output += self.read_until_prompt_ssh(channel, timeout)
            client.close()
            return True, output, 'ssh', detected_hostname
        except Exception as exc:
            try:
                client.close()
            except Exception:
                pass
            return False, str(exc), 'ssh', host

    def read_telnet(self, tn, timeout):
        end = time.time() + timeout
        data = []
        while time.time() < end and not self.stop_flag.is_set():
            time.sleep(0.25)
            try:
                chunk = tn.read_very_eager()
            except EOFError:
                break
            if not chunk:
                continue
            text = chunk.decode(errors='ignore')
            data.append(text)
            lines = ''.join(data).splitlines()
            if lines and PROMPT_RE.search(lines[-1]):
                break
        return ''.join(data)

    def extract_hostname_from_text(self, text, fallback):
        for line in reversed([x.strip() for x in text.splitlines() if x.strip()]):
            m = re.match(r'^([A-Za-z0-9_.-]+)[>#]$', line)
            if m:
                return m.group(1)
        return fallback

    def try_telnet(self, host, cred, commands, timeout, enable_password, delay):
        try:
            self.log(f'{host}: intentando Telnet con {cred["username"]}')
            tn = telnetlib.Telnet(host, 23, timeout)
            banner = self.read_telnet(tn, timeout)
            lower = banner.lower()
            if 'username' in lower or 'login' in lower:
                tn.write(cred['username'].encode() + b'\n')
                banner += self.read_telnet(tn, timeout)
            if 'password' in banner.lower():
                tn.write(cred['password'].encode() + b'\n')
            output = banner + self.read_telnet(tn, timeout)
            detected_hostname = self.extract_hostname_from_text(output, host)
            tn.write(b'terminal length 0\n')
            output += self.read_telnet(tn, timeout)
            if enable_password:
                self.log(f'{host}: ejecutando enable por Telnet')
                tn.write(b'enable\n')
                output += self.read_telnet(tn, 2)
                tn.write(enable_password.encode() + b'\n')
                output += self.read_telnet(tn, timeout)
                detected_hostname = self.extract_hostname_from_text(output, detected_hostname)
            for cmd in commands:
                if self.stop_flag.is_set():
                    raise RuntimeError('Proceso detenido por el usuario')
                self.log(f'{host}: ejecutando {cmd} por Telnet')
                tn.write(cmd.encode() + b'\n')
                time.sleep(delay)
                output += f"\n{'='*20} {cmd} {'='*20}\n"
                output += self.read_telnet(tn, timeout)
            tn.write(b'exit\n')
            tn.close()
            return True, output, 'telnet', detected_hostname
        except Exception as exc:
            return False, str(exc), 'telnet', host

    def safe_name(self, value):
        return re.sub(r'[^A-Za-z0-9_.-]+', '_', value)

    def run_job(self, cfg):
        base = Path(cfg['output_base'])
        base.mkdir(parents=True, exist_ok=True)
        summary_rows = []
        execution_stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log(f'Carpeta base: {base}')
        for host in cfg['targets']:
            if self.stop_flag.is_set():
                self.log('Ejecución cancelada por el usuario.')
                break
            ok_for_host = False
            detected_hostname = host
            self.log(f'Iniciando host {host}')
            for cred in cfg['credentials']:
                if self.stop_flag.is_set():
                    break
                for proto in cred['protocols']:
                    if self.stop_flag.is_set():
                        break
                    if proto == 'ssh':
                        ok, result, used, detected_hostname = self.try_ssh(host, cred, cfg['commands'], cfg['timeout'], cfg['enable_password'], cfg['delay'])
                    elif proto == 'telnet':
                        ok, result, used, detected_hostname = self.try_telnet(host, cred, cfg['commands'], cfg['timeout'], cfg['enable_password'], cfg['delay'])
                    else:
                        continue
                    if ok:
                        folder_name = self.safe_name(detected_hostname)
                        host_dir = base / folder_name
                        host_dir.mkdir(parents=True, exist_ok=True)
                        txt_name = f'{folder_name}_{execution_stamp}.txt'
                        (host_dir / txt_name).write_text(result, encoding='utf-8', errors='ignore')
                        summary_rows.append({'input': host, 'hostname': detected_hostname, 'status': 'ok', 'protocol': used, 'username': cred['username'], 'folder': folder_name, 'file': txt_name})
                        self.metrics['success'] += 1
                        self.metrics['processed'] += 1
                        self.root.after(0, self.update_metrics_visuals)
                        self.log(f'{host}: éxito con {used}/{cred["username"]}. Archivo: {txt_name}')
                        ok_for_host = True
                        break
                    else:
                        self.log(f'{host}: fallo {proto}/{cred["username"]}: {result}')
                if ok_for_host:
                    break
            if not ok_for_host:
                folder_name = self.safe_name(detected_hostname)
                host_dir = base / folder_name
                host_dir.mkdir(parents=True, exist_ok=True)
                summary_rows.append({'input': host, 'hostname': detected_hostname, 'status': 'error', 'protocol': '', 'username': '', 'folder': folder_name, 'file': ''})
                self.metrics['failed'] += 1
                self.metrics['processed'] += 1
                self.metrics['failed_hosts'].append(host)
                self.root.after(0, self.update_metrics_visuals)
                self.root.after(0, self.update_failed_report)
                self.log(f'{host}: sin acceso con las credenciales configuradas. Carpeta: {folder_name}')
        with open(base / 'summary.csv', 'w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=['input', 'hostname', 'status', 'protocol', 'username', 'folder', 'file'])
            writer.writeheader()
            writer.writerows(summary_rows)
        failed_report_path = base / 'reporte_fallidos.txt'
        if self.metrics['failed_hosts']:
            failed_report_path.write_text('Equipos fallidos\n\n' + '\n'.join(self.metrics['failed_hosts']), encoding='utf-8')
        self.root.after(0, self.update_metrics_visuals)
        self.root.after(0, self.update_failed_report)
        self.log('Proceso finalizado. Los TXT ahora incluyen timestamp para no sobrescribir ejecuciones previas.')
        self.status_var.set(f'Finalizado. Carpeta base: {base}')
        self.run_btn.state(['!disabled'])


def main():
    root = tk.Tk()
    app = App(root)
    root.mainloop()

if __name__ == '__main__':
    main()
