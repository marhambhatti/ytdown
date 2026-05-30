import yt_dlp

url = "https://youtu.be/9PvO1I-ld64?si=O9qHpdT0xqTBI46d"

with yt_dlp.YoutubeDL({
    'quiet': True, 
    'skip_download': True,
    'extractor_args': {'youtube': {'js_runtimes': ['nodejs']}}
}) as ydl:
    info = ydl.extract_info(url, download=False)
    formats = info.get('formats', [])
    
    print(f"Total formats: {len(formats)}")
    print("\n--- All formats ---")
    for f in formats:
        print(f"height={f.get('height')} | vcodec={f.get('vcodec')} | acodec={f.get('acodec')} | ext={f.get('ext')}")