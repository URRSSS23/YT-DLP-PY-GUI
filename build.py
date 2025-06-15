import os
import shutil
from PyInstaller.__main__ import run

# Configuration
APP_NAME = 'yt-dlp'
SCRIPT_FILE = 'youtube_downloader.py'
ICON_FILE = 'app_icon.ico'  # Create or download an icon file
FFMPEG_DIR = 'ffmpeg'  # Place FFmpeg binaries here

# Create build directory
BUILD_DIR = 'build'
DIST_DIR = 'dist'
os.makedirs(BUILD_DIR, exist_ok=True)
os.makedirs(DIST_DIR, exist_ok=True)

# PyInstaller options
opts = [
    f'--name={APP_NAME}',
    '--onefile',
    '--windowed',
    '--noconsole',
    f'--icon={ICON_FILE}',
    '--add-data=ffmpeg;ffmpeg',
    '--add-data=app_icon.ico;.',
    '--hidden-import=mutagen.id3',
    '--hidden-import=mutagen.oggvorbis',
    '--hidden-import=PIL',
    '--hidden-import=requests',
    '--collect-all=yt_dlp',
    SCRIPT_FILE
]

# Run PyInstaller
run(opts)

# Copy FFmpeg to dist directory
print("\nCopying FFmpeg to distribution directory...")
shutil.copytree(FFMPEG_DIR, os.path.join(DIST_DIR, APP_NAME, FFMPEG_DIR))