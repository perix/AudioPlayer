
import tkinter as tk
from tkinter import filedialog, ttk
import pygame
import mutagen
from mutagen.mp3 import MP3
from mutagen.wave import WAVE
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.mp4 import MP4
import os
from datetime import datetime

class AudioMetadataPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Metadata Analyzer & Player")
        self.root.geometry("900x750")
        self.root.configure(bg="#f8f0fc")
        
        # Initialize pygame mixer for audio playback
        pygame.mixer.init()
        
        self.current_file = None
        self.is_playing = False
        self.audio_length = 0
        self.current_tooltip = None
        
        # Track the absolute start position (in seconds) of the current playback session.
        # This lets us compute the true position as: play_start_pos + get_pos().
        self.play_start_pos = 0.0
        
        # Tooltips dictionary
        self.tooltips = {
            'Nome File': 'Il nome del file audio che hai caricato',
            'Percorso': 'La posizione completa del file sul tuo computer',
            'Dimensione': 'Lo spazio che il file occupa sul disco, misurato in megabyte (MB)',
            'Formato': 'Il tipo di file audio (MP3, WAV, FLAC, ecc.)',
            'Durata': 'La lunghezza totale del brano in minuti e secondi',
            'Bit Rate': 'La quantità di dati elaborati al secondo. Più alto è, migliore è la qualità audio (es: 320 kbps è qualità molto alta)',
            'Sample Rate': 'Il numero di "campioni" audio registrati ogni secondo. 44100 Hz è lo standard dei CD audio',
            'Canali': 'Mono significa un solo canale audio, Stereo significa due canali (sinistro e destro) per un suono più spaziale',
            'Bits per Sample': 'La precisione di ogni campione audio. 16 bit è standard, 24 bit è qualità professionale',
            'Codec': 'Il metodo di compressione usato per ridurre le dimensioni del file mantenendo la qualità audio',
            'Data Modifica': "L'ultima volta che il file è stato modificato o salvato",
            'Titolo': 'Il nome della canzone come salvato nei metadati del file',
            'Artista': 'Il nome dell\'artista o della band',
            'Album': 'Il nome dell\'album da cui proviene la canzone',
            'Anno': 'L\'anno di pubblicazione della canzone',
            'Genere': 'Il genere musicale (Pop, Rock, Jazz, ecc.)'
        }
        
        self.create_widgets()
        self.update_progress()
    
    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#d4b5e8", pady=15)
        header_frame.pack(fill=tk.X)
        
        title_label = tk.Label(
            header_frame, 
            text="🎵 Audio Metadata Analyzer", 
            font=("Helvetica", 24, "bold"),
            bg="#d4b5e8",
            fg="#5a2d82"
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            header_frame,
            text="Carica un file audio per analizzarne i metadati e riprodurlo",
            font=("Helvetica", 11),
            bg="#d4b5e8",
            fg="#7a4d9e"
        )
        subtitle_label.pack()
        
        # Upload button
        button_frame = tk.Frame(self.root, bg="#f8f0fc", pady=20)
        button_frame.pack()
        
        self.upload_btn = tk.Button(
            button_frame,
            text="📁 Carica File Audio",
            command=self.load_file,
            font=("Helvetica", 14, "bold"),
            bg="#9b6dcc",
            fg="white",
            padx=30,
            pady=15,
            relief=tk.FLAT,
            cursor="hand2",
            borderwidth=0,
            activebackground="#8c60bd",
            highlightthickness=0
        )
        self.upload_btn.pack()
        
        # File info and player frame
        self.player_frame = tk.Frame(self.root, bg="#e8d9f5", pady=15)
        self.player_frame.pack(fill=tk.X, padx=20, pady=10)
        self.player_frame.pack_forget()  # Hidden initially
        
        # File name
        self.file_label = tk.Label(
            self.player_frame,
            text="",
            font=("Helvetica", 12, "bold"),
            bg="#e8d9f5",
            fg="#5a2d82"
        )
        self.file_label.pack(pady=(0, 10))
        
        # Progress bar frame
        progress_frame = tk.Frame(self.player_frame, bg="#e8d9f5")
        progress_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Time labels
        time_frame = tk.Frame(progress_frame, bg="#e8d9f5")
        time_frame.pack(fill=tk.X)
        
        self.current_time_label = tk.Label(
            time_frame,
            text="0:00",
            font=("Helvetica", 10),
            bg="#e8d9f5",
            fg="#5a2d82"
        )
        self.current_time_label.pack(side=tk.LEFT)
        
        self.total_time_label = tk.Label(
            time_frame,
            text="0:00",
            font=("Helvetica", 10),
            bg="#e8d9f5",
            fg="#5a2d82"
        )
        self.total_time_label.pack(side=tk.RIGHT)
        
        # Progress bar (canvas for custom styling)
        self.progress_canvas = tk.Canvas(
            progress_frame,
            height=30,
            bg="#d4b5e8",
            highlightthickness=0,
            cursor="hand2"
        )
        self.progress_canvas.pack(fill=tk.X, pady=5)
        self.progress_canvas.bind("<Button-1>", self.seek_audio)
        
        # Control buttons frame
        controls_frame = tk.Frame(self.player_frame, bg="#e8d9f5")
        controls_frame.pack(pady=10)
        
        # --- Transparent-looking icon buttons (same bg as parent, no borders) ---
        common_btn_kwargs = dict(
            master=controls_frame,
            font=("Helvetica", 16, "bold"),
            fg="#5a2d82",
            bg="#e8d9f5",              # same as parent to "blend"
            activebackground="#e8d9f5", # keep "transparent" feel on hover/press
            bd=0,
            relief=tk.FLAT,
            highlightthickness=0,
            cursor="hand2",
            padx=8,
            pady=2
        )
        
        # Backward 10s
        self.backward_btn = tk.Button(
            **common_btn_kwargs,
            text="⏪ 10s",
            command=lambda: self.skip_seconds(-10)
        )
        self.backward_btn.pack(side=tk.LEFT, padx=10)
        
        # Play/Pause
        self.play_btn = tk.Button(
            **common_btn_kwargs,
            text="▶",
            command=self.toggle_play
        )
        self.play_btn.pack(side=tk.LEFT, padx=10)
        
        # Forward 10s
        self.forward_btn = tk.Button(
            **common_btn_kwargs,
            text="10s ⏩",
            command=lambda: self.skip_seconds(10)
        )
        self.forward_btn.pack(side=tk.LEFT, padx=10)
        
        # Metadata frame with canvas for scrolling
        canvas_frame = tk.Frame(self.root, bg="#f8f0fc")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        canvas = tk.Canvas(canvas_frame, bg="#f8f0fc", highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        
        self.metadata_frame = tk.Frame(canvas, bg="#f8f0fc")
        
        canvas.create_window((0, 0), window=self.metadata_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.metadata_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
    
    def load_file(self):
        filename = filedialog.askopenfilename(
            title="Seleziona un file audio",
            filetypes=[
                ("File Audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aac"),
                ("Tutti i file", "*.*")
            ]
        )
        
        if filename:
            self.current_file = filename
            self.is_playing = False
            pygame.mixer.music.stop()
            pygame.mixer.music.load(filename)
            
            # Get audio length
            try:
                audio = mutagen.File(filename)
                if audio and hasattr(audio.info, 'length'):
                    self.audio_length = float(audio.info.length)
                else:
                    self.audio_length = 0.0
            except:
                self.audio_length = 0.0
            
            # Reset absolute start position
            self.play_start_pos = 0.0
            
            # Update UI
            self.player_frame.pack(fill=tk.X, padx=20, pady=10)
            self.file_label.config(text=f"🎵 {os.path.basename(filename)}")
            self.play_btn.config(text="▶")
            
            # Update time labels
            mins = int(self.audio_length // 60)
            secs = int(self.audio_length % 60)
            self.total_time_label.config(text=f"{mins}:{secs:02d}")
            self.current_time_label.config(text="0:00")
            
            # Extract and display metadata
            self.extract_metadata(filename)
    
    def extract_metadata(self, filename):
        # Clear previous metadata
        for widget in self.metadata_frame.winfo_children():
            widget.destroy()
        
        # Title
        title = tk.Label(
            self.metadata_frame,
            text="📊 Metadati Audio",
            font=("Helvetica", 18, "bold"),
            bg="#f8f0fc",
            fg="#5a2d82"
        )
        title.grid(row=0, column=0, columnspan=2, pady=15, sticky="w")
        
        metadata = {}
        
        # Basic file info
        metadata['Nome File'] = os.path.basename(filename)
        metadata['Percorso'] = filename
        file_size = os.path.getsize(filename) / (1024 * 1024)
        metadata['Dimensione'] = f"{file_size:.2f} MB"
        
        # Get modification date
        mod_time = os.path.getmtime(filename)
        metadata['Data Modifica'] = datetime.fromtimestamp(mod_time).strftime("%d/%m/%Y %H:%M:%S")
        
        # Try to extract metadata using mutagen
        try:
            audio = mutagen.File(filename)
            
            if audio is not None:
                # Format
                metadata['Formato'] = audio.mime[0].split('/')[-1].upper() if getattr(audio, "mime", None) else "Sconosciuto"
                
                # Duration
                if hasattr(audio.info, 'length'):
                    duration = int(audio.info.length)
                    mins = duration // 60
                    secs = duration % 60
                    metadata['Durata'] = f"{mins}:{secs:02d}"
                
                # Bitrate
                if hasattr(audio.info, 'bitrate') and audio.info.bitrate:
                    metadata['Bit Rate'] = f"{audio.info.bitrate // 1000} kbps"
                
                # Sample rate
                if hasattr(audio.info, 'sample_rate'):
                    metadata['Sample Rate'] = f"{audio.info.sample_rate} Hz"
                
                # Channels
                if hasattr(audio.info, 'channels'):
                    channels = audio.info.channels
                    metadata['Canali'] = f"{'Stereo' if channels == 2 else 'Mono'} ({channels})"
                
                # Bits per sample (for WAV/FLAC)
                if hasattr(audio.info, 'bits_per_sample') and audio.info.bits_per_sample:
                    metadata['Bits per Sample'] = f"{audio.info.bits_per_sample} bit"
                
                # Codec info
                if isinstance(audio, MP3):
                    metadata['Codec'] = "MP3 (MPEG Audio Layer 3)"
                elif isinstance(audio, WAVE):
                    metadata['Codec'] = "WAV (Waveform Audio)"
                elif isinstance(audio, FLAC):
                    metadata['Codec'] = "FLAC (Free Lossless Audio Codec)"
                elif isinstance(audio, OggVorbis):
                    metadata['Codec'] = "Ogg Vorbis"
                elif isinstance(audio, MP4):
                    metadata['Codec'] = "AAC (Advanced Audio Coding)"
                
                # ID3 tags
                if audio.tags:
                    tag_mapping = {
                        'title': 'Titolo',
                        'TIT2': 'Titolo',
                        '©nam': 'Titolo',
                        'artist': 'Artista',
                        'TPE1': 'Artista',
                        '©ART': 'Artista',
                        'album': 'Album',
                        'TALB': 'Album',
                        '©alb': 'Album',
                        'date': 'Anno',
                        'TDRC': 'Anno',
                        '©day': 'Anno',
                        'genre': 'Genere',
                        'TCON': 'Genere',
                        '©gen': 'Genere'
                    }
                    
                    for tag_key, display_name in tag_mapping.items():
                        if tag_key in audio.tags:
                            value = audio.tags[tag_key]
                            if isinstance(value, list):
                                value = value[0]
                            metadata[display_name] = str(value)
        
        except Exception as e:
            print(f"Errore nell'estrazione dei metadati: {e}")
        
        # Display metadata in grid
        row = 1
        for key, value in metadata.items():
            self.create_metadata_row(row, key, value)
            row += 1
        
        # Info label
        info_label = tk.Label(
            self.metadata_frame,
            text="💡 Passa il mouse sopra ogni campo per vedere la spiegazione",
            font=("Helvetica", 10, "italic"),
            bg="#e8d9f5",
            fg="#7a4d9e",
            pady=10,
            padx=10
        )
        info_label.grid(row=row, column=0, columnspan=2, pady=15, sticky="ew")
    
    def create_metadata_row(self, row, key, value):
        # Frame for each metadata row
        frame = tk.Frame(self.metadata_frame, bg="#ffffff", relief=tk.FLAT, borderwidth=1)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=5, pady=3)
        self.metadata_frame.grid_columnconfigure(0, weight=1)
        
        # Key label
        key_label = tk.Label(
            frame,
            text=key,
            font=("Helvetica", 10, "bold"),
            bg="#ffffff",
            fg="#9b6dcc",
            anchor="w",
            padx=15,
            pady=10
        )
        key_label.pack(side=tk.TOP, fill=tk.X)
        
        # Value label
        value_label = tk.Label(
            frame,
            text=str(value),
            font=("Helvetica", 11),
            bg="#ffffff",
            fg="#333333",
            anchor="w",
            padx=15,
            pady=5,
            wraplength=800,
            justify=tk.LEFT
        )
        value_label.pack(side=tk.TOP, fill=tk.X)
        
        # Create tooltip
        if key in self.tooltips:
            self.create_tooltip(frame, self.tooltips[key])
    
    def create_tooltip(self, widget, text):
        def show_tooltip(event):
            # Destroy any existing tooltip
            self.hide_tooltip()
            
            self.current_tooltip = tk.Toplevel()
            self.current_tooltip.wm_overrideredirect(True)
            self.current_tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(
                self.current_tooltip,
                text=text,
                background="#2d2d2d",
                foreground="white",
                relief=tk.FLAT,
                padx=10,
                pady=8,
                font=("Helvetica", 10),
                wraplength=300,
                justify=tk.LEFT
            )
            label.pack()
        
        def on_leave(event):
            self.hide_tooltip()
        
        widget.bind("<Enter>", show_tooltip)
        widget.bind("<Leave>", on_leave)
    
    def hide_tooltip(self):
        if self.current_tooltip:
            self.current_tooltip.destroy()
            self.current_tooltip = None
    
    def _current_absolute_pos(self):
        """Calcola la posizione assoluta corrente in secondi usando il riferimento play_start_pos."""
        # get_pos() restituisce i millisecondi dall'ultimo avvio/unpause.
        rel = pygame.mixer.music.get_pos() / 1000.0
        pos = self.play_start_pos + (rel if rel >= 0 else 0.0)
        # Clipping tra 0 e durata
        return max(0.0, min(pos, self.audio_length or 0.0))
    
    def toggle_play(self):
        if not self.current_file:
            return
        
        if self.is_playing:
            pygame.mixer.music.pause()
            self.play_btn.config(text="▶")
            self.is_playing = False
        else:
            if pygame.mixer.music.get_busy():
                # stava in pausa -> unpause
                pygame.mixer.music.unpause()
            else:
                # avvio da dove eravamo (play_start_pos)
                pygame.mixer.music.play(start=self.play_start_pos)
            self.play_btn.config(text="⏸")
            self.is_playing = True
    
    def _seek_to(self, new_pos, keep_state=True):
        """Salta a new_pos (s) mantenendo lo stato (play/pausa) se richiesto."""
        new_pos = max(0.0, min(float(new_pos), self.audio_length or 0.0))
        was_playing = self.is_playing
        
        # Fermiamo e ripartiamo dal nuovo punto
        pygame.mixer.music.stop()
        pygame.mixer.music.play(start=new_pos)
        self.play_start_pos = new_pos  # aggiorniamo il riferimento assoluto
        
        if keep_state and not was_playing:
            # Rimettiamo in pausa se prima era in pausa
            pygame.mixer.music.pause()
            self.is_playing = False
            self.play_btn.config(text="▶")
        else:
            self.is_playing = True
            self.play_btn.config(text="⏸")
    
    def skip_seconds(self, seconds):
        if self.current_file and (self.audio_length or 0) > 0:
            curr = self._current_absolute_pos()
            self._seek_to(curr + seconds, keep_state=True)
    
    def seek_audio(self, event):
        if self.current_file and (self.audio_length or 0) > 0:
            # Calculate position based on click
            canvas_width = max(1, self.progress_canvas.winfo_width())
            click_ratio = max(0.0, min(event.x / canvas_width, 1.0))
            new_pos = click_ratio * self.audio_length
            self._seek_to(new_pos, keep_state=True)
    
    def update_progress(self):
        if self.current_file and (self.audio_length or 0) > 0:
            if pygame.mixer.music.get_busy() or self.is_playing:
                # Get absolute current position
                current_pos = self._current_absolute_pos()
                
                # Update time label
                mins = int(current_pos // 60)
                secs = int(current_pos % 60)
                self.current_time_label.config(text=f"{mins}:{secs:02d}")
                
                # Update progress bar
                canvas_width = self.progress_canvas.winfo_width()
                canvas_height = self.progress_canvas.winfo_height()
                
                progress_ratio = min(current_pos / self.audio_length, 1.0) if self.audio_length else 0.0
                progress_width = canvas_width * progress_ratio
                
                # Clear canvas
                self.progress_canvas.delete("all")
                
                # Draw background
                self.progress_canvas.create_rectangle(
                    0, 0, canvas_width, canvas_height,
                    fill="#d4b5e8",
                    outline=""
                )
                
                # Draw progress
                self.progress_canvas.create_rectangle(
                    0, 0, progress_width, canvas_height,
                    fill="#9b6dcc",
                    outline=""
                )
                
                # Se finita la riproduzione, aggiorna stato
                # (alcuni formati potrebbero non aggiornare get_busy() istantaneamente)
                if current_pos >= self.audio_length - 0.05:
                    self.is_playing = False
                    self.play_btn.config(text="▶")
                    pygame.mixer.music.stop()
        
        # Schedule next update
        self.root.after(100, self.update_progress)

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioMetadataPlayer(root)
    root.mainloop()
