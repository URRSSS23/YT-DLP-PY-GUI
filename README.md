# GUI Downloader

![screenshots](https://github.com/user-attachments/assets/de615cdd-0d84-4b04-ae92-0f3aa2335d17)

A feature-rich YouTube downloader with GUI built using Python and PyQt6. Supports video/audio downloads, playlists, batch processing, metadata embedding, and more.

## Features

- Download videos in multiple resolutions (360p to 1080p)
- Extract audio as MP3/OGG with metadata
- Batch download multiple URLs
- Playlist support
- Thumbnail embedding for audio files
- Metadata tagging (artist, album, title)
- Real-time progress tracking
- Dark mode UI
- Cross-platform (Windows, macOS, Linux)

## Installation

### Prerequisites
- Python 3.9+
- [FFmpeg](https://github.com/yt-dlp/FFmpeg-Builds/releases)
- [Audioread library](https://github.com/beetbox/audioread)
- [mutagen for metadata](https://github.com/quodlibet/mutagen)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)

# Note 
I know yt-dlp has a metadata library, but I didn't realize it =))
```bash

pip install pyinstaller yt-dlp mutagen pillow requests
or: pip install
```

note:
```bash
Tip: For Linux/macOS, replace ; with : in --add-data arguments (ex: --add-data="ffmpeg:ffmpeg"```
```
```bash
pyinstaller --name=yt-dlp_gui --onefile --windowed --noconsole --icon=app_icon.ico --add-data="ffmpeg;ffmpeg" --add-data="app_icon.ico;." --hidden-import=mutagen.id3 --hidden-import=mutagen.oggvorbis --hidden-import=mutagen.mp3 --hidden-import=mutagen.flac --hidden-import=PIL.Image --hidden-import=PIL._imaging --hidden-import=requests --collect-all=yt_dlp --uac-admin youtube_downloader.py OR

(python build.py) just this command in terminal!
```

### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/URRSSS23/YT-DLP-PY-GUI.git
   cd Name_Folder
