# Individual AI Assistant

A Django class assistant for the individual API integration and PWA activity due October 19, 2026. It uses Gemini for answers and a public cached interface for offline access.

The project is independent of Hangarin. No account, database, or saved conversation is required. Each question is independent, and refreshing clears the visible conversation.

## Start on Windows

Open PowerShell in this project folder and run each command separately:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. A private Gemini API key must be configured before the app can return real answers. Keep it in `.env` and never paste it into a public repository or frontend JavaScript.

If activation is blocked, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`, then activate again. Stop the server with Ctrl+C.
