# LinkedIn .NET Job Watcher — Full Setup Guide

This script monitors LinkedIn every 5 minutes for new .NET / C# developer jobs in Egypt and sends you a Telegram notification instantly when one is found.

**What you need to set up (in order):**
1. A Telegram bot (to receive notifications)
2. A GitHub account + private repo (to store the script and track seen jobs)
3. A Railway account (to run the script 24/7 for free)

---

## PART 1 — Create Your Telegram Bot

### Step 1.1 — Create the bot

1. Open Telegram on your phone or PC.
2. In the search bar, search for **@BotFather** and open it (it has a blue checkmark).
3. Send this message: `/newbot`
4. BotFather will ask: *"What name do you want to give to your bot?"*
   - Type any display name, e.g. `My Job Watcher`
5. It will then ask: *"Now choose a username for your bot."*
   - Must end in `bot`, e.g. `my_dotnet_jobs_bot`
6. BotFather will reply with your **bot token**. It looks like this:
   ```
   7412563890:AAFhsomeRandomCharactersMixedHere123
   ```
7. **Copy this token and save it** — you will need it later.

### Step 1.2 — Get your Chat ID

1. In Telegram, search for the bot username you just created (e.g. `@my_dotnet_jobs_bot`) and open it.
2. Press **Start** or send any message like `hello`.
3. Now open this URL in your browser — replace `YOUR_TOKEN` with the token you copied:
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
   Example:
   ```
   https://api.telegram.org/bot7412563890:AAFhsomeRandomCharactersMixedHere123/getUpdates
   ```
4. You will see a JSON response. Look for a section that says `"chat"` and inside it `"id"`. It looks like this:
   ```json
   "chat": {
     "id": 123456789,
     "first_name": "Your Name",
     ...
   }
   ```
5. **Copy that number** (e.g. `123456789`) — this is your **Chat ID**.

> If you see `"result":[]` (empty), go back to Telegram and send another message to the bot, then refresh the URL.

---

## PART 2 — Set Up GitHub

### Step 2.1 — Create a GitHub account

If you don't have one, go to [github.com](https://github.com) and sign up for free.

### Step 2.2 — Create a new private repository

1. After logging in, click the **+** icon at the top right → **New repository**.
2. Fill in:
   - **Repository name**: `job-watcher` (or any name you like)
   - **Visibility**: select **Private**
   - Do NOT check "Add a README file"
3. Click **Create repository**.

### Step 2.3 — Upload the files

You need to upload these 5 files to your new repo:

| File | What it does |
|---|---|
| `watcher.py` | The main script |
| `requirements.txt` | Python packages the script needs |
| `seen_jobs.json` | Stores job IDs already seen (starts empty) |
| `Procfile` | Tells Railway how to run the script |
| `.github/workflows/deploy.yml` | Controls when Railway redeploys |

**How to upload:**

1. On your new repository page, click **uploading an existing file** (or drag and drop).
2. Upload `watcher.py`, `requirements.txt`, `seen_jobs.json`, and `Procfile` all at once.
3. Scroll down and click **Commit changes**.

Now for the workflow file (it's inside a folder):

4. Click **Add file** → **Create new file**.
5. In the filename box at the top, type exactly:
   ```
   .github/workflows/deploy.yml
   ```
   GitHub will automatically create the folders as you type the slashes.
6. Open the `deploy.yml` file from the files you were given, copy its entire content, and paste it into the editor.
7. Click **Commit changes**.

### Step 2.4 — Create a GitHub Personal Access Token

This token lets the script save seen jobs back to your repo. **This is NOT your GitHub password.**

1. Click your profile picture (top right) → **Settings**.
2. Scroll all the way down in the left sidebar → click **Developer settings**.
3. Click **Personal access tokens** → **Tokens (classic)**.
4. Click **Generate new token** → **Generate new token (classic)**.
5. Fill in:
   - **Note**: `job-watcher`
   - **Expiration**: `No expiration` (so it doesn't stop working after 30 days)
   - **Scopes**: check only **`repo`** (the first checkbox — this covers everything under it)
6. Click **Generate token** at the bottom.
7. **Copy the token immediately** — GitHub only shows it once. It looks like:
   ```
   ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ123456
   ```

---

## PART 3 — Set Up Railway

Railway will run your script 24/7 in the cloud for free.

### Step 3.1 — Create a Railway account

1. Go to [railway.app](https://railway.app).
2. Click **Login** → **Login with GitHub** — use the same GitHub account you set up above.
3. Authorize Railway to access your GitHub.

### Step 3.2 — Create a new project

1. On the Railway dashboard, click **New Project**.
2. Select **Deploy from GitHub repo**.
3. If prompted, click **Configure GitHub App** and give Railway access to your repositories. Select your `job-watcher` repo.
4. Back on Railway, select your `job-watcher` repo from the list.
5. Railway will start an initial deploy — **let it fail for now**, that's fine. We need to add the environment variables first.

### Step 3.3 — Add environment variables

1. Click on the service that was created (it will be named after your repo).
2. Click the **Variables** tab.
3. Click **Add a Variable** for each of the following — add them one by one:

| Variable Name | Value |
|---|---|
| `TELEGRAM_TOKEN` | The bot token from Part 1 (e.g. `7412563890:AAFhsome...`) |
| `TELEGRAM_CHAT_ID` | Your chat ID from Part 1 (e.g. `123456789`) |
| `GITHUB_TOKEN` | The GitHub personal access token from Part 2 (e.g. `ghp_aBcD...`) |
| `GITHUB_REPO` | Your repo in this exact format: `yourusername/job-watcher` |

> For `GITHUB_REPO`, replace `yourusername` with your actual GitHub username. Example: `john123/job-watcher`

4. After adding all 4 variables, Railway will automatically redeploy.

### Step 3.4 — Disable Railway's automatic redeploy on every GitHub push

By default, Railway redeploys every single time any file in your repo changes — including when the script updates `seen_jobs.json`. This would restart the watcher constantly. We fix this in two steps:

**Step A — Disable Railway's GitHub auto-deploy:**

1. In your Railway service, click the **Settings** tab.
2. Find the section **"Source"** or **"GitHub"**.
3. Find **"Deploy Triggers"** or the toggle that says "Deploy on push" and **turn it OFF**.

**Step B — Get your Railway token (for GitHub Actions to deploy instead):**

1. Click your profile icon at the top right of Railway → **Account Settings**.
2. Click **Tokens** in the left sidebar.
3. Click **Create Token**.
4. Give it a name: `github-actions`
5. Click **Create** and **copy the token immediately**.

### Step 3.5 — Add the Railway token to GitHub Secrets

This lets GitHub Actions trigger Railway deploys — but only when you change real code files, not when `seen_jobs.json` updates.

1. Go to your `job-watcher` repo on GitHub.
2. Click **Settings** (the tab at the top of the repo page).
3. In the left sidebar, click **Secrets and variables** → **Actions**.
4. Click **New repository secret**.
5. Fill in:
   - **Name**: `RAILWAY_TOKEN`
   - **Secret**: paste the Railway token you just copied
6. Click **Add secret**.

---

## PART 4 — Trigger the First Deployment

Now that everything is connected, trigger a real deploy:

1. Go to your `job-watcher` repo on GitHub.
2. Click on `watcher.py` to open it.
3. Click the pencil icon (Edit) at the top right.
4. Add a comment anywhere — for example, change line 1 from:
   ```python
   import requests
   ```
   to:
   ```python
   # LinkedIn Job Watcher
   import requests
   ```
5. Click **Commit changes**.

This push changes `watcher.py`, which triggers the GitHub Actions workflow, which deploys to Railway. Go to the **Actions** tab on GitHub to watch it run. It takes about 1-2 minutes.

---

## PART 5 — Verify Everything is Working

### Check the Railway logs

1. Go to Railway → your service → **Deployments** tab → click the latest deployment.
2. Click **View Logs**.
3. You should see something like:
   ```
   LinkedIn Job Watcher — Egypt | .NET & C# jobs only
   Watching every 5 minutes...

   [12:00:00] First run — seeding seen jobs (no notifications)...
     47 recent listing(s) found.
     (seed) .NET Developer @ Some Company
     ...
   ```
4. After the first run finishes seeding, it will say `Sleeping 5 minutes...` and then start checking for new jobs every 5 minutes.

### Check your Telegram bot is alive

Send `/status` to your bot in Telegram. You should get a reply like:

```
✅ Watcher is alive!

📊 Jobs scanned: 12
🚨 Matches sent: 2
🕐 Last check: 12:05:00
⏱ Uptime: 0h 10m
📍 Watching: Egypt | .NET & C# jobs only
```

---

## How to Block a Spammy Company in the Future

If you get a notification from a company you don't want, open `watcher.py`, find this section near the top:

```python
BLOCKED_COMPANIES = {
    "bairesdev",
    "micro1",
    "jobs ai",
}
```

Add the company name exactly as it appears on LinkedIn, in lowercase, inside quotes with a comma. For example:

```python
BLOCKED_COMPANIES = {
    "bairesdev",
    "micro1",
    "jobs ai",
    "new spammy company",
}
```

Commit the change to GitHub. Since you changed `watcher.py`, GitHub Actions will automatically redeploy to Railway.

---

## Summary — Which Token Goes Where

This is confusing at first so here it is clearly:

| Token | What it is | Where it goes |
|---|---|---|
| Telegram bot token | Lets the script send messages to Telegram | Railway → Variables → `TELEGRAM_TOKEN` |
| Telegram chat ID | Your personal Telegram ID (where to send messages) | Railway → Variables → `TELEGRAM_CHAT_ID` |
| GitHub personal access token | Lets the script save `seen_jobs.json` to your repo | Railway → Variables → `GITHUB_TOKEN` |
| Railway token | Lets GitHub Actions trigger Railway deploys | GitHub → Secrets → `RAILWAY_TOKEN` |

---

## Files in Your Repo (Summary)

```
job-watcher/
├── watcher.py              ← the main script
├── requirements.txt        ← Python packages
├── seen_jobs.json          ← starts as [] — the script fills this in automatically
├── Procfile                ← tells Railway: run watcher.py as a background worker
└── .github/
    └── workflows/
        └── deploy.yml      ← tells GitHub: only redeploy Railway when real code changes
```
