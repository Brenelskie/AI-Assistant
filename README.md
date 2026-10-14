# AI Assistant — The Study Desk

A separate Django application for the **individual AI Assistant with PWA** activity. It does not change Hangarin or PSUSphere. The paired OpenWeather app and October 21 RESTful lab are separate activities.

It accepts a question and requests a real answer from Google Gemini. It has question/answer bubbles, starter questions, a loading indicator, clear errors, keyboard controls, and an installable offline interface. There is no login or database. Each question is independent; earlier messages are not sent as context.

## 1. Open the project

In VS Code, choose **File → Open Folder → `C:\AIAssistant`**, then **Terminal → New Terminal**. Run these commands one at a time:

```powershell
cd C:\AIAssistant
.\.venv\Scripts\Activate.ps1
```

The environment has already been created on this computer. You should see `(.venv)` before the terminal prompt.

If PowerShell says scripts are disabled, run this in that terminal, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

On a new computer, install Python 3.13 and create the environment first:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 2. Add your private Gemini API key

An API key gives the backend permission to ask Gemini a question. It is not your Google password.

1. Open [Google AI Studio's API keys page](https://aistudio.google.com/api-keys) and sign in.
2. Choose **Create API key**, selecting or creating a Google project. Use a project eligible for the free tier; you do not need to enable paid billing just to try the activity.
3. Copy the key privately. Do not paste it in a chat, screenshot, classroom answer, or GitHub.
4. In VS Code, open this project's **`.env`** file. If absent, copy `.env.example` to `.env` first. Do not overwrite an existing configured `.env`.
5. Find this line and put your key immediately after the equals sign:

   ```ini
   GEMINI_API_KEY=PASTE_YOUR_PRIVATE_KEY_HERE
   ```

6. Keep the default model:

   ```ini
   GEMINI_MODEL=gemini-3.5-flash-lite
   ```

7. Save with **Ctrl+S**. If the server is running, stop it with **Ctrl+C** and start it again. Changes to `.env` need a restart.

The default model is permitted by the PDF and was listed on Google's free tier when this project was built. Access and quotas depend on your Google project. A missing key does not crash startup; sending shows a setup message instead.

## 3. Start the app

In the activated terminal:

```powershell
python manage.py runserver
```

Leave the terminal open and visit [http://127.0.0.1:8000/](http://127.0.0.1:8000/) in Edge or Chrome.

If Hangarin or another app is using port 8000:

```powershell
python manage.py runserver 8010
```

Then visit [http://127.0.0.1:8010/](http://127.0.0.1:8010/). Stop with **Ctrl+C**. No `migrate` or `createsuperuser` is needed.

## 4. Test a real AI answer

1. Type **Explain photosynthesis in three simple sentences.**
2. Choose **Send question**, or press **Ctrl+Enter**.
3. You should see **Thinking…**, then your question and a model response.
4. Try a second question. Choose **Clear** to remove the conversation.
5. Refresh: the previous questions and answers should disappear.

This uses your API quota. Automated tests use fake provider responses, so they do **not** prove your key or quota works. A real Gemini answer remains unverified until this step is performed.

## 5. Test the PWA and offline screen

A PWA is a website that a supported browser can install and open in its own app window. The AI model itself does not run offline.

1. Visit online and wait for the app to load fully.
2. If **Install app** appears in the header, click it. Otherwise, check the address-bar install icon or browser menu. In Edge, look under **… → Apps**. Labels and availability vary by browser.
3. Open the installed app from its new icon. It should use its own app window.
4. Press **F12 → Application**. Inspect **Manifest** and **Service Workers**: a manifest and activated `/serviceworker.js` worker should be present.
5. Disconnect Wi-Fi, or choose DevTools **Network → Offline**, then refresh.
6. The styled interface should open with an offline notice. Old conversations are not retained after refresh.
7. Enter a question and send. Expect a connection error with your draft kept, not an invented offline answer.
8. Reconnect, or select **No throttling**, and send again. Only this new send should contact the server; failed questions are not queued.

Localhost is allowed for development; a published PWA needs HTTPS. Private/incognito windows, browser policy, or an already-installed app may hide installation.

## 6. Explain the project

| File or folder | Purpose |
| --- | --- |
| `templates/assistant/index.html` | Conversation, question box, buttons, and help dialog. |
| `static/assistant/css/app.css` | Desktop/mobile styling; Bootstrap CSS is also served locally. |
| `static/assistant/js/app.js` | Question submission, loading/errors/answers, installation. |
| `assistant/views.py` | Public page, CSRF token, AI endpoint, manifest, worker. |
| `assistant/services.py` | Server-side Gemini request and completed-answer extraction. |
| `config/settings.py` | Private environment settings and production safeguards. |
| `static/assistant/js/serviceworker.js` | Offline public interface and named presentation assets. |
| `assistant/tests/` | Configuration, backend, manifest, and worker checks. |

Flow: **question box → Django → Gemini → Django → answer bubble**. The browser never receives the API key. A fresh CSRF token protects each POST.

Questions and replies are literal text, not executable HTML. They stay only in current-page memory. The worker never caches `/api/` requests, CSRF tokens, questions, or answers.

Google receives submitted questions. `store:false` disables stored Interactions state; it does not override Google's free-tier data policies. Do not submit sensitive information. AI can make mistakes.

## 7. Run automated checks

With the environment activated:

```powershell
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py collectstatic --dry-run --noinput
node --test assistant/tests/serviceworker.test.cjs
```

Node.js is needed only for the last test. Browser checks additionally cover pending/success/error states, safe text, keyboard use, mobile layout, offline opening, and reconnecting after cookie removal. Mock browser answers are not a real-provider demonstration.

### Verified on October 14, 2026

- 48 Django tests and 6 service-worker tests passed.
- Django checks, migration drift check, JavaScript syntax check, and collectstatic dry-run passed (8 static files).
- Desktop and 320px/375px layouts, keyboard sending, duplicate prevention, clear/help, draft recovery, and literal HTML text passed real-browser checks.
- Offline reopening, local styles, API/cache separation, cookie-clearing/reconnection, and absence of stored conversation data passed browser checks.
- Chrome's manifest and installability checks returned no errors in a normal persistent test profile; the **Install app** button appeared. Actual OS installation is still a manual demo step.
- **Not yet verified:** a real Gemini answer with your private key, or deployment to a chosen host.

## 8. Save and submit

This folder has its own Git repository. **Never add `.env` or `.venv` to Git.** Before publishing:

```powershell
git status --short
git check-ignore .env .venv
git ls-files .env
```

The ignore command should list both paths; the last command should print nothing. A new GitHub repository and hosting target still need to be selected before publication.

Prepare screenshots of a **real answer**, the **installed app**, and the **offline message**. Follow Classroom's requested format. If it asks for links, submit this app's **own repository and deployed URL**, not Hangarin's links or a local `127.0.0.1` address.

The professor's announcement sets **October 19, 2026** for the AI assistant and paired weather app. This project covers only the individual AI assistant.

### Deployment boundary

Do not replace `bren11.pythonanywhere.com`: it runs Hangarin, and a PythonAnywhere free account has one web-app slot. Select a separate permitted hosting target or an appropriate paid plan before deployment. Do not copy Hangarin's OAuth credentials: this app has no Google/GitHub login.

For Django hosting, install `requirements.txt`, use `config.wsgi.application`, map `/static/` to collected `staticfiles`, and supply private production settings:

```ini
DJANGO_ENV=production
DJANGO_SECRET_KEY=YOUR_NEW_PRIVATE_RANDOM_SECRET_AT_LEAST_50_CHARACTERS
DJANGO_ALLOWED_HOSTS=YOUR_ACTUAL_HOSTNAME
DJANGO_CSRF_TRUSTED_ORIGINS=https://YOUR_ACTUAL_HOSTNAME
GEMINI_API_KEY=YOUR_PRIVATE_GEMINI_KEY
GEMINI_MODEL=gemini-3.5-flash-lite
```

Use `DJANGO_BEHIND_HTTPS_PROXY=True` only if the host strips untrusted forwarded headers and sets `X-Forwarded-Proto` correctly. Production redirects HTTP to HTTPS and uses secure CSRF cookies.

Before widely public deployment, add host-side rate limits and review Gemini quotas so others cannot exhaust your shared key. Check actual hosted Gemini connectivity, HTTPS, installation, and a real answer; local tests cannot prove these work.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| API key not configured | Put your Gemini key in this project's `.env`, save, restart. |
| Quota reached | Wait for quota reset or inspect the Google project's quota. Repeated clicks will not fix it. |
| Key rejected | Check the key's project and Gemini permissions. Do not share the key. |
| Model unavailable | Check project access against [official model documentation](https://ai.google.dev/gemini-api/docs/models). |
| Connection error / timeout | Reconnect and retry manually. Your draft remains. |
| No install option | Visit online in a supported browser, inspect the manifest/worker, check whether already installed. |
| Old assets after an update | Bump the cache version in `serviceworker.js`; during development, unregister this app's worker in DevTools and reload. |

## Dependencies and references

Python versions are pinned in `requirements.txt`. Bootstrap 5.3.8 CSS is unmodified; its MIT license is in `static/vendor/LICENSE.bootstrap`.

Requirements: supplied **Individual Activity AI Assistant.pdf**. Technical references: [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [Interactions API](https://ai.google.dev/api/interactions-api), [Django CSRF](https://docs.djangoproject.com/en/5.2/howto/csrf/), [MDN PWA caching](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Caching).
