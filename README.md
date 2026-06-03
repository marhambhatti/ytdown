# YTDown — Railway Deployment Guide

## Files Structure

```
ytdown/
├── app.py              ← Backend (cookies support included)
├── requirements.txt    ← Python dependencies
├── Dockerfile          ← Railway ke liye (ffmpeg included)
├── railway.toml        ← Railway config
├── cookies.txt         ← YouTube cookies (gitignore me hai!)
├── update_cookies.py   ← Cookies update karne ka script
└── templates/
    └── index.html      ← Frontend
```

---

## Step 1: Railway pe Deploy Karo

### Option A: GitHub se (Recommended)

1. GitHub repo banao
2. Yeh sab files push karo (`cookies.txt` push MAT karo — .gitignore me hai)
3. Railway.app pe jaao → New Project → Deploy from GitHub
4. Repo select karo → Deploy

### Option B: Railway CLI se

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

---

## Step 2: Environment Variables Set Karo

Railway Dashboard → Your Service → Variables → Add:

| Variable          | Value              | Description                             |
| ----------------- | ------------------ | --------------------------------------- |
| `PORT`            | `8080`             | Auto-set hoti hai Railway pe            |
| `ADMIN_TOKEN`     | `koi-bhi-secret`   | Cookies update API ko protect karta hai |
| `YT_COOKIES_FILE` | `/app/cookies.txt` | Cookies file path (default sahi hai)    |

---

## Step 3: Cookies Setup (ZAROORI!)

### Cookies Export Karna:

1. Chrome/Firefox me yeh extension install karo:
   - **"Get cookies.txt LOCALLY"** (Chrome Web Store)
   - **"cookies.txt"** (Firefox Add-ons)

2. YouTube.com pe apne Google account se login karo

3. Extension icon click karo → cookies export karo

4. Saved file ka content `cookies.txt` me paste karo

### Cookies Railway pe Upload Karna:

**Script se (easy):**

```bash
python update_cookies.py \
  --url https://your-app.railway.app \
  --token your-admin-token \
  --cookies cookies.txt
```

**Manual (curl se):**

```bash
curl -X POST https://your-app.railway.app/api/cookies \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: your-admin-token" \
  -d "{\"cookies\": \"$(cat cookies.txt | sed 's/\"/\\"/g')\"}"
```

---

## Step 4: Health Check

Deploy ke baad verify karo:

```
https://your-app.railway.app/api/health
```

Response agar sahi hai:

```json
{
  "status": "ok",
  "version": "2.0",
  "cookies": "loaded",
  "cookies_path": "/app/cookies.txt"
}
```

Agar `"cookies": "not found"` aaye to Step 3 dobara karo.

---

## Cookies Kab Refresh Karni Padti Hai?

| Error Message                        | Matlab                | Solution             |
| ------------------------------------ | --------------------- | -------------------- |
| "YouTube ne block kiya"              | Bot detection         | Cookies refresh karo |
| "Age restricted — cookies.txt lagao" | Age-restricted video  | Cookies refresh karo |
| "Login required"                     | Sign-in required      | Cookies refresh karo |
| Download 403 error                   | Cookie expire ho gayi | Cookies refresh karo |

**Har 2-4 hafte me cookies refresh karna recommend kiya jata hai.**

---

## Common Issues

### ffmpeg nahi mila

- Dockerfile me `ffmpeg` already included hai
- Agar custom deployment hai to: `apt-get install ffmpeg`

### 1080p+ nahi chal raha

- Railway pe Node.js available nahi hota
- `player_skip: ['js']` already set hai jo is issue ko handle karta hai
- 720p reliably kaam karta hai; 1080p ke liye cookies zaroori hain

### Downloads slow hain

- Railway free tier pe bandwidth limit hai
- Paid plan upgrade consider karo agar zyada use hai
