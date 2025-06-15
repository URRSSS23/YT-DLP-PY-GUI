import os
import shutil
import sys
from PyInstaller.__main__ import run

# Configuration
APP_NAME = 'yt-dlp_gui'
SCRIPT_FILE = 'youtube_downloader.py'
ICON_FILE = 'app_icon.ico'  # Create or download an icon file
FFMPEG_DIR = 'ffmpeg'  # Place FFmpeg binaries here

# Create build directory
BUILD_DIR = 'build'
DIST_DIR = 'dist'
os.makedirs(BUILD_DIR, exist_ok=True)
os.makedirs(DIST_DIR, exist_ok=True)

# PyInstaller options with all required hidden imports
opts = [
    f'--name={APP_NAME}',
    '--onefile',
    '--windowed',
    '--noconsole',
    f'--icon={ICON_FILE}',
    f'--add-data={FFMPEG_DIR};{FFMPEG_DIR}',
    '--add-data=app_icon.ico;.',
    '--hidden-import=mutagen.id3',
    '--hidden-import=mutagen.oggvorbis',
    '--hidden-import=mutagen.mp3',
    '--hidden-import=mutagen.flac',
    '--hidden-import=PIL.Image',
    '--hidden-import=PIL._imaging',
    '--hidden-import=requests',
    '--collect-all=yt_dlp',
    SCRIPT_FILE
]

# Add platform-specific flags
if sys.platform == 'win32':
    opts.append('--uac-admin')  # Request admin privileges if needed

# Run PyInstaller
run(opts)

print("\nBuild completed successfully!")
