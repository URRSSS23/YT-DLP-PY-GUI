import os
import sys
import subprocess
import json
import re
import shutil
import time
import tempfile
import requests
import base64
from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QComboBox, QProgressBar, QTextEdit, QFileDialog,
    QMessageBox, QGroupBox, QCheckBox, QMenuBar, QMenu, QDialog, QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QTextCursor, QFont, QCloseEvent

from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC
from mutagen.mp3 import MP3
from mutagen.oggvorbis import OggVorbis
from mutagen.flac import FLAC, Picture
from PIL import Image

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout()
        
        self.path_label = QLabel("Default Download Path:")
        self.path_edit = QLineEdit()
        self.path_browse = QPushButton("Browse...")
        self.path_browse.clicked.connect(self.browse_download_path)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.path_browse)
        
        self.ffmpeg_label = QLabel("FFmpeg Directory:")
        self.ffmpeg_edit = QLineEdit()
        self.ffmpeg_browse = QPushButton("Browse...")
        self.ffmpeg_browse.clicked.connect(self.browse_ffmpeg_path)
        
        ffmpeg_layout = QHBoxLayout()
        ffmpeg_layout.addWidget(self.ffmpeg_edit)
        ffmpeg_layout.addWidget(self.ffmpeg_browse)
        
        self.format_label = QLabel("Preferred Format:")
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Best Quality",
            "1080p",
            "720p",
            "480p",
            "360p",
            "Audio Only (MP3)",
            "Audio Only (OGG)"
        ])
        
        self.container_label = QLabel("Video Container:")
        self.container_combo = QComboBox()
        self.container_combo.addItems(["MP4", "WEBM", "MKV", "Original"])
        
        self.metadata_label = QLabel("Metadata Options:")
        self.metadata_check = QCheckBox("Add metadata to audio files")
        self.thumbnail_check = QCheckBox("Embed thumbnails in audio files")
        
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addWidget(self.path_label)
        layout.addLayout(path_layout)
        layout.addSpacing(10)
        layout.addWidget(self.ffmpeg_label)
        layout.addLayout(ffmpeg_layout)
        layout.addSpacing(10)
        layout.addWidget(self.format_label)
        layout.addWidget(self.format_combo)
        layout.addSpacing(10)
        layout.addWidget(self.container_label)
        layout.addWidget(self.container_combo)
        layout.addSpacing(15)
        layout.addWidget(self.metadata_label)
        layout.addWidget(self.metadata_check)
        layout.addWidget(self.thumbnail_check)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def browse_download_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if path:
            self.path_edit.setText(path)
    
    def browse_ffmpeg_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select FFmpeg Directory")
        if path:
            self.ffmpeg_edit.setText(path)
    
    def get_settings(self):
        return {
            "download_path": self.path_edit.text(),
            "ffmpeg_path": self.ffmpeg_edit.text(),
            "preferred_format": self.format_combo.currentText(),
            "container": self.container_combo.currentText(),
            "add_metadata": self.metadata_check.isChecked(),
            "embed_thumbnails": self.thumbnail_check.isChecked()
        }
    
    def set_settings(self, settings):
        self.path_edit.setText(settings.get("download_path", ""))
        self.ffmpeg_edit.setText(settings.get("ffmpeg_path", ""))
        
        format_text = settings.get("preferred_format", "Best Quality")
        index = self.format_combo.findText(format_text)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
            
        container_text = settings.get("container", "MP4")
        index = self.container_combo.findText(container_text)
        if index >= 0:
            self.container_combo.setCurrentIndex(index)
            
        self.metadata_check.setChecked(settings.get("add_metadata", True))
        self.thumbnail_check.setChecked(settings.get("embed_thumbnails", True))

class DownloadThread(QThread):
    progress_signal = pyqtSignal(int, str)
    output_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, url, options, ffmpeg_dir=None, settings=None):
        super().__init__()
        self.url = url
        self.options = options
        self.ffmpeg_dir = ffmpeg_dir
        self.settings = settings or {}
        self.is_running = True
        self.downloaded_files = []
    
    def run(self):
        try:
            cmd = ["yt-dlp", self.url]
            
            format_map = {
                "Best Quality": ["-f", "bestvideo+bestaudio/best"],
                "1080p": ["-f", "bestvideo[height<=1080]+bestaudio[height<=1080]/best[height<=1080]"],
                "720p": ["-f", "bestvideo[height<=720]+bestaudio[height<=720]/best[height<=720]"],
                "480p": ["-f", "bestvideo[height<=480]+bestaudio[height<=480]/best[height<=480]"],
                "360p": ["-f", "bestvideo[height<=360]+bestaudio[height<=360]/best[height<=360]"],
                "Audio Only (MP3)": ["-x", "--audio-format", "mp3"],
                "Audio Only (OGG)": ["-x", "--audio-format", "ogg"]
            }
            
            format_option = self.options.get("format", "Best Quality")
            if format_option in format_map:
                cmd.extend(format_map[format_option])
            else:
                cmd.extend(["-f", "bestvideo+bestaudio/best"])
            
            output_path = self.options.get("output_path", "")
            if output_path:
                abs_path = os.path.abspath(output_path)
                cmd.extend(["-o", f"{abs_path}/%(title)s [%(id)s].%(ext)s"])
            
            if self.ffmpeg_dir:
                cmd.extend(["--ffmpeg-location", self.ffmpeg_dir])
            
            if self.options.get("is_playlist", False):
                cmd.append("--yes-playlist")
            else:
                cmd.append("--no-playlist")
            
            if format_option not in ["Audio Only (MP3)", "Audio Only (OGG)"]:
                container = self.options.get("container", "MP4")
                if container != "Original":
                    cmd.extend(["--merge-output-format", container.lower()])
            
            if format_option in ["Audio Only (MP3)", "Audio Only (OGG)"]:
                if self.settings.get("add_metadata", True):
                    cmd.append("--add-metadata")
                if self.settings.get("embed_thumbnails", True):
                    cmd.append("--embed-thumbnail")
            
            self.output_signal.emit(f"Command: {' '.join(cmd)}\n")
            
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
            except FileNotFoundError:
                self.output_signal.emit("Error: yt-dlp not found. Please ensure it's installed.")
                self.finished_signal.emit(False, "yt-dlp not installed")
                return
            except Exception as e:
                self.output_signal.emit(f"Error starting process: {str(e)}")
                self.finished_signal.emit(False, f"Process error: {str(e)}")
                return
            
            if process.stdout is None:
                self.output_signal.emit("Error: No output stream available from process")
                self.finished_signal.emit(False, "No process output")
                return
            
            while True:
                if not self.is_running:
                    process.terminate()
                    break
                
                try:
                    line = process.stdout.readline()
                except Exception as e:
                    self.output_signal.emit(f"Error reading output: {str(e)}")
                    break
                
                if not line:
                    break
                
                self.output_signal.emit(line)
                
                if "[download]" in line or "[ExtractAudio]" in line or "[Merger]" in line:
                    match = re.search(r'(\d+\.\d+)%', line)
                    if match:
                        progress = float(match.group(1))
                        self.progress_signal.emit(int(progress), line.strip())
                
                if "Destination:" in line:
                    match = re.search(r'Destination:\s+(.+)', line)
                    if match:
                        self.downloaded_files.append(match.group(1))
            
            process.wait()
            
            if process.returncode == 0:
                if format_option in ["Audio Only (MP3)", "Audio Only (OGG)"] and self.downloaded_files:
                    try:
                        info_cmd = ["yt-dlp", "--skip-download", "-j", self.url]
                        info_output = subprocess.check_output(info_cmd, text=True, stderr=subprocess.STDOUT)
                        video_info = json.loads(info_output)
                        
                        for file_path in self.downloaded_files:
                            if os.path.exists(file_path):
                                self.add_metadata(file_path, video_info)
                                
                                if self.settings.get("embed_thumbnails", True):
                                    self.embed_thumbnail(file_path, video_info)
                    except Exception as e:
                        self.output_signal.emit(f"Metadata processing error: {str(e)}")
                
                self.finished_signal.emit(True, "Download completed successfully!")
            else:
                self.finished_signal.emit(False, f"Download failed with code {process.returncode}")
        
        except Exception as e:
            self.finished_signal.emit(False, f"Error: {str(e)}")
    
    def add_metadata(self, file_path, video_info):
        """Add enhanced metadata to audio files"""
        try:
            title = video_info.get('title', 'Unknown Title')
            artist = video_info.get('uploader', 'Unknown Artist')
            album = "YouTube Downloads"
            date = video_info.get('upload_date', '')[:4]  
            
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.mp3':
                try:
                    audio = MP3(file_path, ID3=EasyID3)
                except:
                    audio = MP3(file_path)
                    try:
                        audio.add_tags(ID3=EasyID3)
                    except Exception as e:
                        self.output_signal.emit(f"Error adding tags: {str(e)}")
                        return
                    audio = MP3(file_path, ID3=EasyID3)
                
                audio["title"] = title
                audio["artist"] = artist
                audio["album"] = album
                if date:
                    audio["date"] = date
                audio.save()
                
            elif ext == '.ogg':
                audio = OggVorbis(file_path)
                audio["title"] = title
                audio["artist"] = artist
                audio["album"] = album
                if date:
                    audio["date"] = date
                audio.save()
                
            self.output_signal.emit(f"Added metadata to: {os.path.basename(file_path)}")
        except Exception as e:
            self.output_signal.emit(f"Metadata error: {str(e)}")
    
    def embed_thumbnail(self, file_path, video_info):
        """Embed thumbnail into audio file"""
        try:
            thumbnail_url = video_info.get('thumbnail')
            if not thumbnail_url:
                return
                
            response = requests.get(thumbnail_url, stream=True)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_file:
                shutil.copyfileobj(response.raw, tmp_file)
                thumb_path = tmp_file.name
            
            img = Image.open(thumb_path)
            img.thumbnail((500, 500))
            img.save(thumb_path, "JPEG")
            
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.mp3':
                try:
                    audio = MP3(file_path, ID3=ID3)
                except:
                    audio = MP3(file_path)
                    try:
                        audio.add_tags()
                    except Exception as e:
                        self.output_signal.emit(f"Error adding tags: {str(e)}")
                        return
    
                if audio.tags is not None:
                    apic = APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3, 
                        desc='Cover',
                        data=open(thumb_path, 'rb').read()
                    )
                    audio.tags.add(apic)
                    audio.save()

            elif ext == '.ogg':
                audio = OggVorbis(file_path)
                with open(thumb_path, "rb") as f:
                    image_data = f.read()
                audio["METADATA_BLOCK_PICTURE"] = [
                    base64.b64encode(image_data).decode('utf-8')
                ]
                audio.save()
                
            os.unlink(thumb_path)
            self.output_signal.emit(f"Embedded thumbnail in: {os.path.basename(file_path)}")
        except Exception as e:
            self.output_signal.emit(f"Thumbnail error: {str(e)}")
    
    def stop(self):
        self.is_running = False

class YouTubeDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Modern YouTube Downloader")
        self.setGeometry(100, 100, 900, 700)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2d2d2d;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
                color: #ddd;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
            }
            QLabel {
                color: #ddd;
            }
            QLineEdit, QComboBox, QTextEdit, QProgressBar {
                background-color: #3a3a3a;
                color: #eee;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4a4a4a;
                color: #eee;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #777;
            }
            QProgressBar {
                border: 1px solid #444;
                border-radius: 3px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4caf50;
                width: 10px;
            }
        """)
        
        self.settings_file = "settings.json"
        self.settings = self.load_settings()
        
        self.download_queue = []
        self.current_download = None
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        self.create_menu()
        
        url_group = QGroupBox("Download URLs (one per line)")
        url_layout = QVBoxLayout()
        
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("Paste YouTube URLs here, one per line...")
        url_layout.addWidget(self.url_input)
        
        self.playlist_check = QCheckBox("Treat all as playlists")
        self.batch_check = QCheckBox("Batch download mode")
        url_layout.addWidget(self.playlist_check)
        url_layout.addWidget(self.batch_check)
        
        url_group.setLayout(url_layout)
        main_layout.addWidget(url_group)
        
        format_group = QGroupBox("Download Options")
        format_layout = QFormLayout()
        format_layout.setSpacing(10)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems([
            "Best Quality",
            "1080p",
            "720p",
            "480p",
            "360p",
            "Audio Only (MP3)",
            "Audio Only (OGG)"
        ])
        
        default_format = self.settings.get("preferred_format", "Best Quality")
        index = self.format_combo.findText(default_format)
        if index >= 0:
            self.format_combo.setCurrentIndex(index)
        
        self.container_combo = QComboBox()
        self.container_combo.addItems(["MP4", "WEBM", "MKV", "Original"])
        
        default_container = self.settings.get("container", "MP4")
        index = self.container_combo.findText(default_container)
        if index >= 0:
            self.container_combo.setCurrentIndex(index)
        
        self.output_edit = QLineEdit()
        self.output_edit.setText(self.settings.get("download_path", ""))
        self.output_button = QPushButton("Browse...")
        self.output_button.clicked.connect(self.browse_output_path)
        
        output_layout = QHBoxLayout()
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_button)
        
        format_layout.addRow("Format:", self.format_combo)
        format_layout.addRow("Container:", self.container_combo)
        format_layout.addRow("Output Folder:", output_layout)
        
        format_group.setLayout(format_layout)
        main_layout.addWidget(format_group)
        
        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.queue_label = QLabel("Queue: 0")
        self.queue_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.queue_label)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        console_group = QGroupBox("Download Log")
        console_layout = QVBoxLayout()
        
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Courier New", 10))
        
        console_layout.addWidget(self.console_output)
        console_group.setLayout(console_layout)
        main_layout.addWidget(console_group)
        
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start Download")
        self.start_button.clicked.connect(self.start_download)
        self.start_button.setStyleSheet("background-color: #4caf50;")
        
        self.stop_button = QPushButton("Stop Download")
        self.stop_button.clicked.connect(self.stop_download)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("background-color: #f44336;")
        
        self.clear_button = QPushButton("Clear Log")
        self.clear_button.clicked.connect(self.clear_log)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addStretch()
        button_layout.addWidget(self.clear_button)
        
        main_layout.addLayout(button_layout)
        
        self.download_thread = None
        
        self.check_dependencies()
    
    def create_menu(self):
        menu_bar = QMenuBar(self)
        self.setMenuBar(menu_bar)
        
        file_menu = QMenu("File", self)
        menu_bar.addMenu(file_menu)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        settings_menu = QMenu("Settings", self)
        menu_bar.addMenu(settings_menu)
        
        settings_action = QAction("Preferences", self)
        settings_action.triggered.connect(self.open_settings)
        settings_menu.addAction(settings_action)
        
        help_menu = QMenu("Help", self)
        menu_bar.addMenu(help_menu)
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r") as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def save_settings(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            self.log_message(f"Error saving settings: {str(e)}")
    
    def browse_output_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if path:
            self.output_edit.setText(path)
    
    def validate_ffmpeg_dir(self, path):
        """Verify if FFmpeg directory contains necessary executables"""
        if not path:
            return False
            
        required_files = ["ffmpeg", "ffprobe"]
        for file in required_files:
            for ext in ["", ".exe", ".bat"]:
                full_path = os.path.join(path, file + ext)
                if os.path.exists(full_path):
                    return True
        return False
    
    def check_dependencies(self):
        if not shutil.which("yt-dlp"):
            self.log_message("Warning: yt-dlp not found in PATH. Please install it.")
        
        ffmpeg_dir = self.settings.get("ffmpeg_path", "")
        
        if ffmpeg_dir and self.validate_ffmpeg_dir(ffmpeg_dir):
            self.log_message(f"FFmpeg found in: {ffmpeg_dir}")
            return True
        
        app_dir = os.path.dirname(os.path.abspath(__file__))
        possible_dirs = [
            os.path.join(app_dir, "ffmpeg"),
            os.path.join(app_dir, "ffmpeg", "bin"),
            os.path.join(app_dir, "bin"),
            os.path.join(app_dir)
        ]
        
        for dir_path in os.get_exec_path():
            possible_dirs.append(dir_path)
        
        for dir_path in possible_dirs:
            if self.validate_ffmpeg_dir(dir_path):
                self.settings["ffmpeg_path"] = dir_path
                self.save_settings()
                self.log_message(f"Using bundled FFmpeg in: {dir_path}")
                return True
        
        self.log_message("Warning: FFmpeg directory not found or incomplete. Some formats may not work properly.")
        self.log_message("FFmpeg directory must contain both ffmpeg and ffprobe executables")
        return False
    
    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.set_settings(self.settings)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_settings = dialog.get_settings()
            self.settings.update(new_settings)
            self.save_settings()
            
            self.output_edit.setText(self.settings.get("download_path", ""))
            self.check_dependencies()
    
    def disable_controls(self):
        """Disable UI controls during download"""
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.url_input.setEnabled(False)
        self.format_combo.setEnabled(False)
        self.container_combo.setEnabled(False)
        self.output_edit.setEnabled(False)
        self.output_button.setEnabled(False)
        self.playlist_check.setEnabled(False)
        self.batch_check.setEnabled(False)
    
    def enable_controls(self):
        """Enable UI controls after download"""
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.url_input.setEnabled(True)
        self.format_combo.setEnabled(True)
        self.container_combo.setEnabled(True)
        self.output_edit.setEnabled(True)
        self.output_button.setEnabled(True)
        self.playlist_check.setEnabled(True)
        self.batch_check.setEnabled(True)
    
    def start_download(self):
        """Start download process - handles single or batch downloads"""
        urls = [url.strip() for url in self.url_input.toPlainText().splitlines() if url.strip()]
        
        if not urls:
            QMessageBox.warning(self, "Input Error", "Please enter at least one valid URL")
            return
        
        output_path = self.output_edit.text().strip() or self.settings.get("download_path", "")
        if not output_path:
            QMessageBox.warning(self, "Input Error", "Please select an output directory")
            return
        
        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create directory: {str(e)}")
                return
        
        options = {
            "format": self.format_combo.currentText(),
            "container": self.container_combo.currentText(),
            "output_path": output_path,
            "is_playlist": self.playlist_check.isChecked()
        }
        
        ffmpeg_dir = self.settings.get("ffmpeg_path", "")
        
        self.console_output.clear()
        
        if self.batch_check.isChecked() and len(urls) > 1:
            self.download_queue = urls
            self.current_download = None
            self.queue_label.setText(f"Queue: {len(self.download_queue)}")
            self.log_message(f"Starting batch download of {len(urls)} items")
            self.process_next_download()
        else:
            self.download_queue = []
            self.start_single_download(urls[0], options, ffmpeg_dir)
    
    def start_single_download(self, url, options, ffmpeg_dir):
        """Start download for a single URL"""
        self.disable_controls()
        
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Starting download: {url[:50]}...")
        self.log_message(f"Starting download: {url}")
        
        self.download_thread = DownloadThread(
            url, 
            options, 
            ffmpeg_dir,
            {
                "add_metadata": self.settings.get("add_metadata", True),
                "embed_thumbnails": self.settings.get("embed_thumbnails", True)
            }
        )
        self.download_thread.progress_signal.connect(self.update_progress)
        self.download_thread.output_signal.connect(self.log_message)
        self.download_thread.finished_signal.connect(self.download_finished)
        self.download_thread.start()
    
    def process_next_download(self):
        """Process next item in download queue"""
        if self.download_queue:
            url = self.download_queue.pop(0)
            self.queue_label.setText(f"Queue: {len(self.download_queue)}")
            self.start_single_download(
                url,
                {
                    "format": self.format_combo.currentText(),
                    "container": self.container_combo.currentText(),
                    "output_path": self.output_edit.text().strip() or self.settings.get("download_path", ""),
                    "is_playlist": self.playlist_check.isChecked()
                },
                self.settings.get("ffmpeg_path", "")
            )
        else:
            self.enable_controls()
            self.status_label.setText("Batch download completed!")
            QMessageBox.information(self, "Batch Complete", "All downloads finished successfully!")
    
    def stop_download(self):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.status_label.setText("Download stopped by user")
            self.log_message("Download stopped by user")
    
    def download_finished(self, success, message):
        self.status_label.setText(message)
        self.log_message(message)
        
        if success:
            self.progress_bar.setValue(100)
            
            if self.download_queue:
                QApplication.processEvents()
                time.sleep(1) 
                self.process_next_download()
                return
        else:
            QMessageBox.warning(self, "Download Failed", message)
            
            self.download_queue = []
            self.queue_label.setText("Queue: 0")
        
        self.enable_controls()
    
    def update_progress(self, value, status):
        self.progress_bar.setValue(value)
        self.status_label.setText(status)
    
    def log_message(self, message):
        self.console_output.append(message.strip())
        self.console_output.moveCursor(QTextCursor.MoveOperation.End)
    
    def clear_log(self):
        self.console_output.clear()
    
    def show_about(self):
        about_text = """
        <h2>GUI YouTube Downloader</h2>
        <p>A modern GUI application for downloading YouTube videos using yt-dlp.</p>
        <p><b>Features:</b></p>
        <ul>
            <li>Download videos or playlists</li>
            <li>Multiple format and quality options</li>
            <li>Audio extraction (MP3/OGG)</li>
            <li>Batch download support</li>
            <li>Metadata embedding (ID3 tags)</li>
            <li>Thumbnail embedding</li>
            <li>Real-time progress tracking</li>
            <li>Download log console</li>
            <li>FFmpeg integration</li>
            <li>Video container selection (MP4, WEBM, MKV)</li>
        </ul>
        <p><b>Powered by:</b></p>
        <ul>
            <li>yt-dlp - https://github.com/yt-dlp/yt-dlp</li>
            <li>FFmpeg - https://ffmpeg.org/</li>
            <li>Mutagen - https://github.com/quodlibet/mutagen</li>
            <li>Audioread - https://github.com/beetbox/audioread</li>
        </ul>
        <p>Version 2.0.0</p>
        """
        QMessageBox.about(self, "About", about_text)
    
    def closeEvent(self, a0: Optional[QCloseEvent]) -> None:
        """Handle window close event"""
        if self.download_thread and self.download_thread.isRunning():
            reply = QMessageBox.question(
                self, "Download in Progress",
                "A download is in progress. Are you sure you want to quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.download_thread.stop()
                self.download_thread.wait(2000) 
                if a0:
                    a0.accept()
            else:
                if a0:
                    a0.ignore()
        else:
            if a0:
                a0.accept()

def main():
    app = QApplication(sys.argv)
    
    app.setStyle("Fusion")
    
    dark_palette = app.palette()
    dark_palette.setColor(dark_palette.ColorRole.Window, Qt.GlobalColor.darkGray)
    dark_palette.setColor(dark_palette.ColorRole.WindowText, Qt.GlobalColor.white)
    app.setPalette(dark_palette)
    
    window = YouTubeDownloaderApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
