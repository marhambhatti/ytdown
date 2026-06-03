from flask import Flask, jsonify, request, send_file, send_from_directory, Response
from flask_cors import CORS
import base64
import yt_dlp
import threading
import uuid
import os
import time
import re
import shutil
import zipfile
import requests as req_lib

app = Flask(__name__, static_folder='templates', static_url_path='')
CORS(app, resources={r"/api/*": {"origins": "*"}})

jobs = {}

COOKIE_FILE = os.environ.get(
    'YT_COOKIES_FILE',
    '/app/cookies.txt' if os.path.exists('/app') else 'cookies.txt'
)
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', '')


def resolve_node_runtime():
    configured_node = os.environ.get('NODE_PATH', '').strip()
    if configured_node and os.path.exists(configured_node):
        return f'node:{configured_node}'

    node_path = shutil.which('node')
    if node_path:
        return f'node:{node_path}'

    return None


NODE_RUNTIME = resolve_node_runtime()


def write_cookie_file(content):
    content = (content or '').replace('\r\n', '\n').strip() + '\n'
    cookie_dir = os.path.dirname(os.path.abspath(COOKIE_FILE))
    if cookie_dir:
        os.makedirs(cookie_dir, exist_ok=True)

    with open(COOKIE_FILE, 'w', encoding='utf-8') as cookie_file:
        cookie_file.write(content)


def ensure_cookie_file_from_env():
    cookies_b64 = os.environ.get('YT_COOKIES_B64', '').strip()
    cookies_text = os.environ.get('YT_COOKIES', '').strip()

    if not cookies_b64 and not cookies_text:
        return

    try:
        if cookies_b64:
            cookies_text = base64.b64decode(cookies_b64).decode('utf-8')

        write_cookie_file(cookies_text)
    except Exception as error:
        print(f"Cookie env load failed: {error}", flush=True)


def cookies_available():
    return os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 20


def cookie_diagnostics():
    if not cookies_available():
        return {
            "status": "not found",
            "has_youtube_domain": False,
            "auth_cookie_names": [],
        }

    auth_names = {
        "SID",
        "HSID",
        "SSID",
        "APISID",
        "SAPISID",
        "__Secure-1PSID",
        "__Secure-3PSID",
        "__Secure-1PAPISID",
        "__Secure-3PAPISID",
    }
    found_names = set()
    has_youtube_domain = False

    try:
        with open(COOKIE_FILE, 'r', encoding='utf-8', errors='ignore') as cookie_file:
            for line in cookie_file:
                if "youtube.com" in line:
                    has_youtube_domain = True

                parts = line.strip().split('\t')
                if len(parts) >= 7 and parts[5] in auth_names:
                    found_names.add(parts[5])
    except OSError:
        return {
            "status": "unreadable",
            "has_youtube_domain": False,
            "auth_cookie_names": [],
        }

    return {
        "status": "loaded",
        "has_youtube_domain": has_youtube_domain,
        "auth_cookie_names": sorted(found_names),
    }


def cookie_opts():
    if cookies_available():
        return {'cookiefile': COOKIE_FILE}
    return {}


def youtube_extractor_args(skip_manifests=False):
    youtube_args = {}
    if NODE_RUNTIME:
        youtube_args['js_runtimes'] = [NODE_RUNTIME]
    if skip_manifests:
        youtube_args['skip'] = ['hls', 'dash']

    return {'youtube': youtube_args} if youtube_args else {}


ensure_cookie_file_from_env()

# Fast fetch opts — video ke liye
def make_info_opts():
    opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'simulate': True,
    }

    extractor_args = youtube_extractor_args(skip_manifests=True)
    if extractor_args:
        opts['extractor_args'] = extractor_args

    opts.update(cookie_opts())
    return opts

if not os.path.exists('downloads'):
    os.makedirs('downloads')


def cleanup_old_jobs():
    """Delete jobs older than 30 minutes and their folders"""
    while True:
        time.sleep(300)
        now = time.time()
        expired = []

        for jid in list(jobs.keys()):
            if now - jobs[jid].get('created_at', now) > 1800:
                expired.append(jid)

        for jid in expired:
            try:
                output_path = jobs[jid].get('output_path') or f'downloads/{jid}'
                if os.path.exists(output_path):
                    shutil.rmtree(output_path, ignore_errors=True)
                del jobs[jid]
            except Exception:
                pass


cleanup_daemon = threading.Thread(target=cleanup_old_jobs, daemon=True)
cleanup_daemon.start()


@app.route('/api/health', methods=['GET'])
def health():
    cookie_status = cookie_diagnostics()
    return jsonify({
        "status": "ok",
        "version": "2.0",
        "cookies": cookie_status["status"],
        "cookies_path": COOKIE_FILE,
        "cookies_has_youtube_domain": cookie_status["has_youtube_domain"],
        "cookies_auth_names": cookie_status["auth_cookie_names"],
        "node_runtime": "loaded" if NODE_RUNTIME else "not found",
    })


@app.route('/api/cookies', methods=['POST'])
def update_cookies():
    if not ADMIN_TOKEN:
        return jsonify({"error": "ADMIN_TOKEN env var set nahi hai"}), 500

    token = request.headers.get('X-Admin-Token', '')
    if token != ADMIN_TOKEN:
        return jsonify({"error": "Invalid admin token"}), 401

    data = request.get_json(silent=True) or {}
    content = data.get('cookies', '')
    if not content or not content.strip():
        return jsonify({"error": "cookies empty hain"}), 400

    if 'youtube.com' not in content and '.youtube.com' not in content:
        return jsonify({"error": "Yeh YouTube cookies.txt nahi lag raha"}), 400

    try:
        write_cookie_file(content)
    except Exception as error:
        return jsonify({"error": f"Cookies save nahi hui: {error}"}), 500

    return jsonify({
        "success": True,
        "path": COOKIE_FILE,
        "size": os.path.getsize(COOKIE_FILE),
    })


@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')


# ✅ Thumbnail Proxy — YouTube CORS bypass karne ke liye
@app.route('/api/thumb')
def proxy_thumb():
    url = request.args.get('url', '')
    if not url or 'ytimg.com' not in url:
        return '', 400
    try:
        r = req_lib.get(url, timeout=8, headers={
            'Referer': 'https://www.youtube.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        return Response(
            r.content,
            status=200,
            headers={
                'Content-Type': r.headers.get('Content-Type', 'image/jpeg'),
                'Cache-Control': 'public, max-age=3600'
            }
        )
    except Exception:
        return '', 502


def validate_youtube_url(url):
    if not url or not isinstance(url, str):
        return False
    pattern = r'^(https?://)?(www\.)?(youtube\.com/watch\?v=|youtube\.com/playlist\?list=|youtu\.be/|youtube\.com/shorts/)[A-Za-z0-9_\-?=&%.]+'
    return bool(re.match(pattern, url.strip()))


def format_duration(seconds):
    if not seconds:
        return "0:00"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_view_count(count):
    if count is None:
        return "0"
    count = int(count)
    if count >= 1000000000:
        return f"{count / 1000000000:.1f}B".replace(".0", "")
    if count >= 1000000:
        return f"{count / 1000000:.1f}M".replace(".0", "")
    if count >= 1000:
        return f"{count / 1000:.1f}K".replace(".0", "")
    return str(count)


def format_upload_date(upload_date):
    if not upload_date or len(upload_date) != 8:
        return ""
    return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"


def format_filesize(size):
    if not size:
        return ""
    size_mb = size / (1024 * 1024)
    if size_mb >= 1024:
        return f"~{size_mb / 1024:.1f} GB"
    return f"~{size_mb:.0f} MB"


def estimate_filesize(quality):
    estimates = {
        "8K":         "~3.0 GB",
        "4K":         "~800 MB",
        "2K":         "~400 MB",
        "1080p":      "~120 MB",
        "720p":       "~70 MB",
        "480p":       "~40 MB",
        "360p":       "~25 MB",
        "Audio Only": "~5 MB",
    }
    return estimates.get(quality, "~50 MB")


def get_format_list(formats):
    if not formats:
        return []

    height_to_quality = {
        4320: "8K",
        2160: "4K",
        1440: "2K",
        1080: "1080p",
        720:  "720p",
        480:  "480p",
        360:  "360p",
    }

    video_formats = [
        fmt for fmt in formats
        if fmt.get('vcodec') and fmt.get('vcodec') != 'none'
    ]

    clean_formats = []
    seen_heights = set()

    for fmt in video_formats:
        height = fmt.get('height')
        if not height or height in seen_heights:
            continue
        quality_label = height_to_quality.get(height)
        if not quality_label:
            continue
        filesize = fmt.get('filesize') or fmt.get('filesize_approx')
        clean_formats.append({
            "quality": quality_label,
            "height": height,
            "format_id": fmt.get('format_id'),
            "ext": fmt.get('ext', 'mp4'),
            "filesize": format_filesize(filesize) if filesize else estimate_filesize(quality_label),
        })
        seen_heights.add(height)

    audio_only = next(
        (fmt for fmt in formats
         if fmt.get('vcodec') in (None, 'none')
         and fmt.get('acodec') and fmt.get('acodec') != 'none'),
        None
    )
    if audio_only:
        filesize = audio_only.get('filesize') or audio_only.get('filesize_approx')
        clean_formats.append({
            "quality": "Audio Only",
            "height": 0,
            "format_id": audio_only.get('format_id'),
            "ext": audio_only.get('ext', 'mp3'),
            "filesize": format_filesize(filesize) if filesize else "~5 MB",
        })

    quality_order = ["8K", "4K", "2K", "1080p", "720p", "480p", "360p", "Audio Only"]
    clean_formats.sort(key=lambda x: quality_order.index(x["quality"]) if x["quality"] in quality_order else 99)
    return clean_formats


def youtube_video_url(entry):
    if entry.get('webpage_url'):
        return entry.get('webpage_url')
    if entry.get('url') and entry.get('url').startswith('http'):
        return entry.get('url')
    if entry.get('id'):
        return f"https://www.youtube.com/watch?v={entry.get('id')}"
    return ""


def yt_dlp_error_message(error):
    message = str(error).lower()
    if "sign in to confirm" in message or "not a bot" in message or "use --cookies" in message:
        if cookies_available():
            return "YouTube ne cookies accept nahi ki. Fresh logged-in YouTube cookies export karke dobara upload karein."
        return "YouTube login cookies required hain. Railway par cookies upload karein."
    if "private" in message:
        return "Yeh video private hai"
    if "age" in message or "sign in to confirm your age" in message:
        return "Age restricted video — login required"
    if "not available" in message or "unavailable" in message or "removed" in message:
        return "Video available nahi hai"
    if "invalid" in message or "url" in message:
        return "Galat YouTube URL hai"
    if "network" in message or "timed out" in message or "connection" in message or "temporary failure" in message:
        return "Internet check karein"
    return "Kuch masla hua: " + str(error)


def clean_progress_text(value):
    if value is None:
        return ""
    return re.sub(r'\x1b\[[0-9;]*m', '', str(value)).strip()


def format_eta(seconds):
    if seconds is None:
        return ""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return ""
    minutes = seconds // 60
    secs = seconds % 60
    hours = minutes // 60
    minutes = minutes % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def make_progress_hook(job_id):
    def progress_hook(data):
        job = jobs.get(job_id)
        if not job:
            return
        if job.get('cancelled'):
            raise Exception("Download cancelled")

        status = data.get('status')
        if status == 'downloading':
            total_bytes = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
            downloaded_bytes = data.get('downloaded_bytes') or 0
            percent = 0

            if total_bytes:
                percent = round((downloaded_bytes / total_bytes) * 100, 1)
            elif data.get('_percent_str'):
                percent_text = clean_progress_text(data.get('_percent_str')).replace('%', '')
                try:
                    percent = round(float(percent_text), 1)
                except ValueError:
                    percent = job.get('percent', 0)

            job.update({
                "percent": percent,
                "speed": clean_progress_text(data.get('_speed_str')),
                "eta": clean_progress_text(data.get('_eta_str')) or format_eta(data.get('eta')),
                "current_file": os.path.basename(data.get('filename') or ""),
                "bytes_downloaded": downloaded_bytes,
                "status": "downloading",
                "retrying": False,
            })
        elif status == 'finished':
            job.update({
                "percent": max(job.get('percent', 0), 100),
                "current_file": os.path.basename(data.get('filename') or job.get('current_file') or ""),
                "bytes_downloaded": data.get('downloaded_bytes') or job.get('bytes_downloaded', 0),
                "status": "downloading",
            })

    return progress_hook


def retry_sleep(job_id, attempt):
    job = jobs.get(job_id)
    if job:
        job['retry_count'] = attempt
        job['retrying'] = True
    return min(2**attempt, 30)


def build_ydl_opts(job_id, quality, fmt, output_path):
    quality_heights = {
        "8K":    4320,
        "4K":    2160,
        "2K":    1440,
        "1080p": 1080,
        "720p":  720,
        "480p":  480,
        "360p":  360,
    }

    selected_quality = quality or "720p"
    requested_format = str(fmt or "").lower()

    is_audio_only = (
        str(selected_quality).lower() in ("audio", "audio only", "mp3")
        or requested_format in ("audio", "audio only", "mp3")
    )

    if is_audio_only:
        format_str = "bestaudio/best"
    else:
        max_height = quality_heights.get(selected_quality, 720)
        format_str = (
            f"bestvideo[height<={max_height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/"
            "best"
        )

    opts = {
        'continuedl': True,
        'retries': 10,
        'fragment_retries': 10,
        'file_access_retries': 5,
        'socket_timeout': 30,
        'retry_sleep_functions': {'http': lambda n: retry_sleep(job_id, n)},
        'outtmpl': output_path + '/%(playlist_index)s-%(title)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [make_progress_hook(job_id)],
        'format': format_str,
        'merge_output_format': 'mp4' if requested_format == 'mp4' else requested_format,
    }

    extractor_args = youtube_extractor_args()
    if extractor_args:
        opts['extractor_args'] = extractor_args

    opts.update(cookie_opts())

    if is_audio_only:
        opts.update({
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })

    return opts


def cleanup_download_folder(job_id):
    time.sleep(15 * 60)
    job = jobs.get(job_id)
    output_path = job.get('output_path') if job else f'downloads/{job_id}'
    if output_path and os.path.exists(output_path):
        shutil.rmtree(output_path, ignore_errors=True)


def run_download(job_id, url, opts):
    try:
        if jobs.get(job_id, {}).get('cancelled'):
            jobs[job_id]['status'] = 'cancelled'
            return

        jobs[job_id]['status'] = 'downloading'
        jobs[job_id]['last_cancel_check'] = time.time()

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        if jobs.get(job_id, {}).get('cancelled'):
            jobs[job_id]['status'] = 'cancelled'
        else:
            jobs[job_id]['status'] = 'complete'
            jobs[job_id]['percent'] = 100
    except Exception as error:
        if jobs.get(job_id, {}).get('cancelled') or "cancelled" in str(error).lower():
            jobs[job_id]['status'] = 'cancelled'
        else:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = yt_dlp_error_message(error)
    finally:
        cleanup_thread = threading.Thread(target=cleanup_download_folder, args=(job_id,))
        cleanup_thread.daemon = True
        cleanup_thread.start()


@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()

    if not validate_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL"}), 400

    is_playlist = 'playlist' in url or 'list=' in url

    try:
        if is_playlist:
            flat_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extract_flat': True,
            }
            extractor_args = youtube_extractor_args()
            if extractor_args:
                flat_opts['extractor_args'] = extractor_args
            flat_opts.update(cookie_opts())

            with yt_dlp.YoutubeDL(flat_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            entries = [e for e in info.get('entries', []) if e]

            videos = []
            for index, entry in enumerate(entries, start=1):
                videos.append({
                    "index": index,
                    "title": entry.get('title') or "",
                    "duration": format_duration(entry.get('duration')),
                    "thumbnail": entry.get('thumbnail') or "",
                    "url": youtube_video_url(entry),
                })

            first_formats = []
            if videos and videos[0]['url']:
                with yt_dlp.YoutubeDL(make_info_opts()) as ydl2:
                    first_info = ydl2.extract_info(videos[0]['url'], download=False)
                    first_formats = get_format_list(first_info.get('formats', []))

            return jsonify({
                "type": "playlist",
                "title": info.get('title') or "",
                "channel": info.get('channel') or info.get('uploader') or "",
                "thumbnail": entries[0].get('thumbnail') or info.get('thumbnail') or "" if entries else "",
                "video_count": len(videos),
                "videos": videos,
                "formats": first_formats,
            })

        else:
            with yt_dlp.YoutubeDL(make_info_opts()) as ydl:
                info = ydl.extract_info(url, download=False)

            return jsonify({
                "type": "video",
                "title": info.get('title') or "",
                "channel": info.get('channel') or info.get('uploader') or "",
                "thumbnail": info.get('thumbnail') or "",
                "duration": format_duration(info.get('duration')),
                "duration_seconds": info.get('duration') or 0,
                "view_count": format_view_count(info.get('view_count')),
                "upload_date": format_upload_date(info.get('upload_date')),
                "formats": get_format_list(info.get('formats', [])),
            })

    except Exception as error:
        return jsonify({"error": yt_dlp_error_message(error)}), 400


@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    quality = data.get('quality', '720p')
    fmt = data.get('format', 'mp4')
    video_indices = data.get('video_indices') or []

    if not validate_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL"}), 400

    active = [j for j in jobs.values() if j['status'] == 'downloading']
    if len(active) >= 3:
        return jsonify({"error": "Zyada downloads chal rahe hain"}), 429

    job_id = str(uuid.uuid4())
    output_path = f'downloads/{job_id}'
    jobs[job_id] = {
        'status': 'preparing',
        'percent': 0,
        'speed': '',
        'eta': '',
        'current_file': '',
        'bytes_downloaded': 0,
        'retry_count': 0,
        'retrying': False,
        'cancelled': False,
        'created_at': time.time(),
        'output_path': output_path,
    }

    os.makedirs(output_path)
    opts = build_ydl_opts(job_id, quality, fmt, output_path)

    if video_indices:
        opts['playlist_items'] = ','.join(str(int(index) + 1) for index in video_indices)

    thread = threading.Thread(target=run_download, args=(job_id, url, opts))
    thread.daemon = False
    thread.start()

    return jsonify({"job_id": job_id})


@app.route('/api/progress/<job_id>', methods=['GET'])
def get_progress(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify(job)


@app.route('/api/cancel/<job_id>', methods=['POST'])
def cancel_download(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    job['cancelled'] = True
    return jsonify({"cancelled": True})


def get_downloaded_files(output_path):
    if not os.path.exists(output_path):
        return []
    skipped_extensions = {'.part', '.ytdl', '.temp', '.tmp', '.zip'}
    files = []
    for name in os.listdir(output_path):
        path = os.path.join(output_path, name)
        _, ext = os.path.splitext(name)
        if os.path.isfile(path) and ext.lower() not in skipped_extensions:
            files.append(path)
    return files


@app.route('/api/file/<job_id>', methods=['GET'])
def download_file(job_id):
    job = jobs.get(job_id)
    if not job or job.get('status') != 'complete':
        return jsonify({"error": "File not found"}), 404

    output_path = job.get('output_path') or f'downloads/{job_id}'
    files = get_downloaded_files(output_path)

    if not files:
        return jsonify({"error": "File not found"}), 404

    if len(files) == 1:
        return send_file(files[0], as_attachment=True)

    zip_path = os.path.join(output_path, f'{job_id}.zip')
    if not os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in files:
                zip_file.write(file_path, os.path.basename(file_path))

    return send_file(zip_path, as_attachment=True, download_name=f'{job_id}.zip')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
