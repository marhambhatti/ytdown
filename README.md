# YouTube Downloader

## Setup
```bash
pip install -r requirements.txt
```

## Run
```bash
python app.py
```

## Open
Visit `http://localhost:5000` in your browser

## Features
✅ Download single videos, playlists, and shorts  
✅ Multiple quality options (4K, 2K, 1080p, 720p, 480p, 360p, Audio)  
✅ Format selection (MP4, MKV, WebM, MP3, M4A)  
✅ Playlist multi-select  
✅ Real-time download progress  
✅ Subtitle support  
✅ Download history  
✅ Responsive mobile design  
✅ Urdu/English error messages  
✅ Resume on browser reconnect  
✅ Automatic cleanup of old jobs  

## Known Limitations
- YouTube may block downloads occasionally (rate limiting)
- Age-restricted videos need authentication
- Very long playlists (500+) may timeout
- Private/unavailable videos cannot be downloaded
- This tool is for personal use only — respect YouTube's terms of service
- Maximum 3 concurrent downloads
- Jobs older than 30 minutes are automatically deleted

## Troubleshooting
- **"Internet check karein"**: Verify your internet connection
- **"Yeh video private hai"**: Video is not publicly available
- **"Age restricted"**: You need to log in to access this video
- **Download stuck**: Try cancelling and restarting
- **Playlist issues**: Try downloading a single video from the playlist first

## Technical Stack
- **Backend**: Flask + yt-dlp + FFmpeg
- **Frontend**: HTML5 + CSS3 + Vanilla JS
- **Storage**: LocalStorage (history), File system (downloads)
