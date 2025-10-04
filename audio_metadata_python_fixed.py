
import sys
import os
import time
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QSlider, QScrollArea, QFrame, QFormLayout
)

import vlc

# Mutagen è opzionale
try:
    import mutagen
except Exception:
    mutagen = None


def fmt_time(ms: int) -> str:
    if ms is None or ms < 0:
        return "0:00"
    s = ms // 1000
    m = s // 60
    return f"{m}:{int(s % 60):02d}"


class AudioPlayerVLCSilentMeta(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio Player (VLC backend, silent + metadata)")
        self.setMinimumSize(980, 520)

        # VLC instance silenziosa con backend specifico per Qt
        self.instance = vlc.Instance([
            '--quiet',
            '--no-media-library',
            '--verbose=0',
            '--no-xlib',  # Evita problemi di threading con X11
            '--vout=none',  # Disabilita output video
            '--aout=mmdevice',  # Usa Windows Audio Session API
            '--no-video-title-show',  # Evita creazione finestre
            '--no-stats',  # Disabilita statistiche che potrebbero creare finestre
            '--no-sub-autodetect-file'  # Disabilita rilevamento sottotitoli
        ])
        self.mediaplayer = self.instance.media_player_new()
        self.media = None
        self.user_seeking = False

        # ---- UI layout principale
        root = QVBoxLayout(self)

        header = QLabel("🎧 Player VLC con Metadati")
        header.setStyleSheet("font-size: 22px; font-weight: 800; color: #115;")
        root.addWidget(header)

        topbar = QHBoxLayout()
        self.btn_open = QPushButton("📁 Apri")
        self.btn_open.clicked.connect(self.open_file)
        topbar.addWidget(self.btn_open)
        topbar.addStretch()
        root.addLayout(topbar)

        # Sezione player (sinistra) + metadati (destra)
        middle = QHBoxLayout()
        root.addLayout(middle)

        # --- Colonna sinistra: player ---
        left = QVBoxLayout()
        middle.addLayout(left, 3)

        self.lbl_file = QLabel("Nessun file")
        self.lbl_file.setStyleSheet("font-weight: 600;")
        left.addWidget(self.lbl_file)

        time_row = QHBoxLayout()
        self.lbl_curr = QLabel("0:00")
        self.lbl_total = QLabel("0:00")
        time_row.addWidget(self.lbl_curr)
        time_row.addStretch()
        time_row.addWidget(self.lbl_total)
        left.addLayout(time_row)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(self.on_slider_pressed)
        self.slider.sliderReleased.connect(self.on_slider_released)
        self.slider.sliderMoved.connect(self.on_slider_moved)
        left.addWidget(self.slider)

        controls = QHBoxLayout()
        self.btn_back = QPushButton("⏪ 10s")
        self.btn_back.clicked.connect(lambda: self.skip_ms(-10_000))
        controls.addWidget(self.btn_back)

        self.btn_play = QPushButton("▶")
        self.btn_play.clicked.connect(self.toggle_play)
        controls.addWidget(self.btn_play)

        self.btn_fwd = QPushButton("10s ⏩")
        self.btn_fwd.clicked.connect(lambda: self.skip_ms(10_000))
        controls.addWidget(self.btn_fwd)
        controls.addStretch()
        left.addLayout(controls)

        self.status = QLabel("Pronto")
        left.addWidget(self.status)

        # --- Colonna destra: metadati (scroll)
        right_wrap = QFrame()
        right_wrap.setFrameShape(QFrame.StyledPanel)
        right_wrap.setStyleSheet(
            "QFrame { background:#f6f8fb; border-radius: 10px; }")
        right = QVBoxLayout(right_wrap)
        middle.addWidget(right_wrap, 4)

        meta_title = QLabel("📊 Metadati")
        meta_title.setStyleSheet(
            "font-size: 18px; font-weight: 800; color:#113;")
        right.addWidget(meta_title)

        self.meta_scroll = QScrollArea()
        self.meta_scroll.setWidgetResizable(True)
        self.meta_host = QFrame()
        self.meta_form = QFormLayout(self.meta_host)
        self.meta_scroll.setWidget(self.meta_host)
        right.addWidget(self.meta_scroll)

        self.tooltips = {
            'Nome File': 'Il nome del file audio',
            'Percorso': 'Percorso completo su disco',
            'Dimensione': 'Dimensione su disco (MB)',
            'Data Modifica': 'Ultima modifica del file',
            'Formato': 'Tipo di file (MP3, WAV, FLAC, ecc.)',
            'Durata': 'Lunghezza totale della traccia',
            'Bit Rate': 'Bit al secondo (kbps)',
            'Sample Rate': 'Campioni al secondo (Hz)',
            'Canali': 'Mono, Stereo, ecc.',
            'Bits per Sample': 'Profondità in bit dei campioni',
            'Codec': 'Algoritmo di codifica/decodifica',
            'Titolo': 'Titolo traccia',
            'Artista': 'Artista',
            'Album': 'Album',
            'Anno': 'Anno',
            'Genere': 'Genere',
            'Commenti': 'Note/Commenti dal tag'
        }

        # Timer per UI
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start()

        # Buffer metadati
        self.meta_dict = {}

    # ------------------ Utility metadati UI ------------------
    def clear_meta(self):
        while self.meta_form.rowCount():
            self.meta_form.removeRow(0)

    def add_meta_row(self, key, value):
        k = QLabel(f"<b>{key}</b>")
        k.setTextFormat(Qt.RichText)
        v = QLabel(value if value else "-")
        v.setWordWrap(True)
        if key in self.tooltips:
            tip = self.tooltips[key]
            k.setToolTip(tip)
            v.setToolTip(tip)
        self.meta_form.addRow(k, v)

    def render_meta(self):
        self.clear_meta()
        order = [
            "Nome File", "Percorso", "Dimensione", "Data Modifica",
            "Formato", "Durata", "Bit Rate", "Sample Rate",
            "Canali", "Bits per Sample", "Codec",
            "Titolo", "Artista", "Album", "Anno", "Genere", "Commenti"
        ]
        for k in order:
            if k in self.meta_dict:
                self.add_meta_row(k, str(self.meta_dict[k]))

    # ------------------ Player logic ------------------
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file audio", "",
            "Audio (*.mp3 *.wav *.flac *.ogg *.m4a *.aac);;Tutti i file (*.*)"
        )
        if not path:
            return

        self.lbl_file.setText(os.path.basename(path))
        self.status.setText("Caricamento...")
        self.meta_dict = {}

        # Filesystem base
        try:
            self.meta_dict["Nome File"] = os.path.basename(path)
            self.meta_dict["Percorso"] = path
            self.meta_dict["Dimensione"] = f"{os.path.getsize(path)/(1024*1024):.2f} MB"
            self.meta_dict["Data Modifica"] = datetime.fromtimestamp(
                os.path.getmtime(path)
            ).strftime("%d/%m/%Y %H:%M:%S")
        except Exception:
            pass

        # Mutagen (se disponibile) per info tecniche + tag
        if mutagen:
            try:
                a = mutagen.File(path)
                if a is not None:
                    # Formato/Codec
                    if getattr(a, "mime", None):
                        self.meta_dict["Formato"] = a.mime[0].split(
                            '/')[-1].upper()
                    # Durata
                    if getattr(a, "info", None) and hasattr(a.info, "length"):
                        self.meta_dict["Durata"] = fmt_time(
                            int(a.info.length * 1000))
                    # Bitrate
                    if getattr(a, "info", None) and hasattr(a.info, "bitrate") and a.info.bitrate:
                        self.meta_dict["Bit Rate"] = f"{a.info.bitrate//1000} kbps"
                    # Sample rate
                    if getattr(a, "info", None) and hasattr(a.info, "sample_rate") and a.info.sample_rate:
                        self.meta_dict["Sample Rate"] = f"{a.info.sample_rate} Hz"
                    # Canali
                    if getattr(a, "info", None) and hasattr(a.info, "channels") and a.info.channels:
                        ch = a.info.channels
                        self.meta_dict[
                            "Canali"] = f"{'Stereo' if ch == 2 else ('Mono' if ch == 1 else str(ch)+'ch')} ({ch})"
                    # Bits per sample
                    if getattr(a, "info", None) and hasattr(a.info, "bits_per_sample") and a.info.bits_per_sample:
                        self.meta_dict["Bits per Sample"] = f"{a.info.bits_per_sample} bit"

                    # Tag testuali comuni
                    tags_map = {
                        "title": "Titolo", "TIT2": "Titolo", "©nam": "Titolo",
                        "artist": "Artista", "TPE1": "Artista", "©ART": "Artista",
                        "album": "Album", "TALB": "Album", "©alb": "Album",
                        "date": "Anno", "TDRC": "Anno", "©day": "Anno",
                        "genre": "Genere", "TCON": "Genere", "©gen": "Genere",
                        "comment": "Commenti", "COMM::XXX": "Commenti"
                    }
                    if getattr(a, "tags", None):
                        for k, disp in tags_map.items():
                            if k in a.tags:
                                val = a.tags[k]
                                if isinstance(val, list):
                                    val = val[0]
                                self.meta_dict[disp] = str(val)
            except Exception:
                pass

        # Render parziale subito
        self.render_meta()

        # Imposta media VLC e richiedi parsing async per ottenere meta aggiuntivi
        self.media = self.instance.media_new(path)
        em = self.media.event_manager()
        em.event_attach(vlc.EventType.MediaParsedChanged, self.on_media_parsed)
        try:
            # VLC 3.x: parse_async
            self.media.parse_async()
        except Exception:
            pass

        self.mediaplayer.set_media(self.media)
        self.mediaplayer.play()
        self.status.setText("Caricato")
        QTimer.singleShot(250, self.update_ui)

    def on_media_parsed(self, event):
        # Utilizziamo QTimer.singleShot per eseguire l'aggiornamento nel thread principale
        QTimer.singleShot(0, self._update_media_metadata)
        
    def _update_media_metadata(self):
        # Integra metadati da VLC (titolo, artista, album, genere, ecc.)
        meta_fields = {
            vlc.Meta.Title: "Titolo",
            vlc.Meta.Artist: "Artista",
            vlc.Meta.Album: "Album",
            vlc.Meta.Genre: "Genere",
            vlc.Meta.Date: "Anno",
            vlc.Meta.Description: "Commenti"
        }
        changed = False
        for vlc_key, disp in meta_fields.items():
            try:
                val = self.media.get_meta(vlc_key)
                if val and disp not in self.meta_dict:
                    self.meta_dict[disp] = val
                    changed = True
            except Exception:
                pass

        # Durata da VLC (se non presente o più precisa)
        try:
            d = self.mediaplayer.get_length()
            if d and (("Durata" not in self.meta_dict) or (d > 0)):
                self.meta_dict["Durata"] = fmt_time(d)
                changed = True
        except Exception:
            pass

        if changed:
            self.render_meta()

    def toggle_play(self):
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.btn_play.setText("▶")
            self.status.setText("In pausa")
        else:
            self.mediaplayer.play()
            self.btn_play.setText("⏸")
            self.status.setText("In riproduzione")

    def duration_ms(self):
        d = self.mediaplayer.get_length()
        return d if d is not None else 0

    def position_ms(self):
        p = self.mediaplayer.get_time()
        return p if p is not None else 0

    def set_position_ms(self, ms):
        dur = max(0, self.duration_ms())
        ms = max(0, min(ms, dur if dur > 0 else ms))
        self.mediaplayer.set_time(ms)

    def skip_ms(self, delta):
        self.set_position_ms(self.position_ms() + delta)

    def on_slider_pressed(self):
        self.user_seeking = True

    def on_slider_moved(self, value):
        dur = self.duration_ms()
        if dur > 0:
            ms = int(dur * (value / 1000))
            self.lbl_curr.setText(fmt_time(ms))

    def on_slider_released(self):
        self.user_seeking = False
        dur = self.duration_ms()
        if dur > 0:
            ms = int(dur * (self.slider.value() / 1000))
            self.set_position_ms(ms)

    def update_ui(self):
        dur = self.duration_ms()
        pos = self.position_ms()
        if dur > 0:
            self.lbl_total.setText(fmt_time(dur))
        self.lbl_curr.setText(fmt_time(pos))

        if dur > 0 and not self.user_seeking:
            self.slider.blockSignals(True)
            self.slider.setValue(int(1000 * pos / dur))
            self.slider.blockSignals(False)

        self.btn_play.setText("⏸" if self.mediaplayer.is_playing() else "▶")


def main():
    app = QApplication(sys.argv)
    w = AudioPlayerVLCSilentMeta()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
