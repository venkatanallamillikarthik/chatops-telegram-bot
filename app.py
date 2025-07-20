# Full AI Telegram GitHub Assistant with PRs, Branch Handling, Auto-Code Review, ASCII Art, and Email Support

import os
import re
import logging
import requests
import wikipedia
import base64
import smtplib
from email.message import EmailMessage
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
eval_env = os.environ

OLLAMA_API_URL = eval_env.get("OLLAMA_API_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL   = eval_env.get("OLLAMA_MODEL", "phi")
SEARCH_API_URL = eval_env.get('SEARCH_API_URL', 'https://api.duckduckgo.com/')
TELEGRAM_API_URL = eval_env.get("TELEGRAM_API_URL", "https://api.telegram.org/bot")
GITHUB_API_URL   = eval_env.get("GITHUB_API_URL", "https://api.github.com/repos/")
EMAIL_HOST       = eval_env.get("EMAIL_HOST")
EMAIL_PORT       = int(eval_env.get("EMAIL_PORT", "587"))
EMAIL_USER       = eval_env.get("EMAIL_USER")
EMAIL_PASSWORD   = eval_env.get("EMAIL_PASSWORD")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=[logging.StreamHandler()])
logger = logging.getLogger(__name__)

app = Flask(__name__)

# AI Model Query
def query_phi_model(prompt: str) -> str:
    try:
        resp = requests.post(OLLAMA_API_URL, json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}, timeout=60)
        resp.raise_for_status()
        return resp.json().get("response", "No response from model.")
    except Exception as e:
        logger.exception("AI model error")
        return f"AI Error: {e}"

# ASCII Art Generator
def generate_ascii_art(subject):
    instruction = f"Generate a simple but clear ASCII art of {subject}. Only use plain text characters. Keep it under 50 lines."
    return query_phi_model(instruction)

# Email Sending
def send_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg.set_content(body)

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        return "Email sent successfully."
    except Exception as e:
        logger.exception("Error sending email")
        return f"Email error: {e}"

# Web Search
def search_web(query: str) -> str:
    try:
        url = f"{SEARCH_API_URL}?q={requests.utils.quote(query)}&format=json&no_html=1"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json().get("AbstractText") or wikipedia.summary(query, sentences=2)
    except Exception:
        return "No good search result found."

# GitHub Functions
def github_headers():
    return {"Authorization": f"token {os.getenv('GITHUB_PAT')}", "Accept": "application/vnd.github.v3+json"}

def create_repo(repo_name: str) -> str:
    try:
        url = "https://api.github.com/user/repos"
        data = {"name": repo_name, "private": False}
        resp = requests.post(url, headers=github_headers(), json=data)
        resp.raise_for_status()
        return resp.json().get("html_url", "Repo created")
    except Exception as e:
        logger.exception("Error creating repo")
        return f"Error creating repo: {e}"

def create_file(repo_full: str, filepath: str, content: str, commit_msg: str) -> str:
    try:
        url = f"https://api.github.com/repos/{repo_full}/contents/{filepath}"
        data = {"message": commit_msg, "content": base64.b64encode(content.encode()).decode(), "branch": "main"}
        resp = requests.put(url, headers=github_headers(), json=data)
        resp.raise_for_status()
        return resp.json().get("content", {}).get("html_url", "File created")
    except Exception as e:
        logger.exception("Error creating file")
        return f"Error creating file: {e}"

def delete_file(repo_full: str, filepath: str, sha: str, commit_msg: str) -> str:
    try:
        url = f"https://api.github.com/repos/{repo_full}/contents/{filepath}"
        data = {"message": commit_msg, "sha": sha, "branch": "main"}
        resp = requests.delete(url, headers=github_headers(), json=data)
        resp.raise_for_status()
        return f"Deleted {filepath}"
    except Exception as e:
        logger.exception("Error deleting file")
        return f"Error deleting file: {e}"

def get_sha(repo_full: str, filepath: str) -> str:
    try:
        resp = requests.get(f"https://api.github.com/repos/{repo_full}/contents/{filepath}", headers=github_headers())
        resp.raise_for_status()
        return resp.json().get("sha", "")
    except Exception as e:
        logger.exception("Error fetching SHA")
        return ""

def create_pr(repo_full: str, title: str, head: str, base: str) -> str:
    try:
        url = f"https://api.github.com/repos/{repo_full}/pulls"
        data = {"title": title, "head": head, "base": base}
        resp = requests.post(url, headers=github_headers(), json=data)
        resp.raise_for_status()
        return resp.json().get("html_url", "PR created")
    except Exception as e:
        logger.exception("Error creating PR")
        return f"Error creating PR: {e}"

def create_branch(repo_full: str, new_branch: str, source_branch: str = "main") -> str:
    try:
        base_ref = requests.get(f"https://api.github.com/repos/{repo_full}/git/ref/heads/{source_branch}", headers=github_headers()).json()['object']['sha']
        url = f"https://api.github.com/repos/{repo_full}/git/refs"
        data = {"ref": f"refs/heads/{new_branch}", "sha": base_ref}
        resp = requests.post(url, headers=github_headers(), json=data)
        resp.raise_for_status()
        return f"Branch '{new_branch}' created from '{source_branch}'."
    except Exception as e:
        logger.exception("Error creating branch")
        return f"Error creating branch: {e}"

def ai_code_review(code: str) -> str:
    prompt = f"Review the following code and highlight any bugs or improvements:\n\n{code}"
    return query_phi_model(prompt)

def send_message(chat_id: int, text: str) -> None:
    try:
        url = f"{TELEGRAM_API_URL}{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": text})
        resp.raise_for_status()
    except Exception as e:
        logger.exception("Error sending Telegram message")

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        chat_id = data.get('message', {}).get('chat', {}).get('id')
        msg = data.get('message', {}).get('text', '').lower().strip()
        response = ""

        if msg.startswith('ascii'):
            subject = msg.replace('ascii', '').strip()
            response = generate_ascii_art(subject)

        elif msg.startswith('email '):
            parts = msg.split(" ", 3)
            if len(parts) >= 4:
                to_email, subject, body = parts[1], parts[2], parts[3]
                response = send_email(to_email, subject, body)
            else:
                response = "Usage: email <recipient_email> <subject> <body>"

        elif 'create repo' in msg:
            repo = msg.split()[-1]
            response = create_repo(repo)

        elif 'add file' in msg or '.py' in msg:
            filename = msg.split()[2]
            repo_name = msg.split()[-1]
            code = query_phi_model(f"Write complete {filename} code in Python.")
            repo_full = f"{os.getenv('GITHUB_USERNAME')}/{repo_name}"
            response = create_file(repo_full, filename, code, f"Add {filename} via bot")

        elif 'delete file' in msg:
            filename = msg.split()[2]
            repo_name = msg.split()[-1]
            repo_full = f"{os.getenv('GITHUB_USERNAME')}/{repo_name}"
            sha = get_sha(repo_full, filename)
            response = delete_file(repo_full, filename, sha, f"Delete {filename} via bot")

        elif 'create pr' in msg:
            repo_name = msg.split()[-1]
            repo_full = f"{os.getenv('GITHUB_USERNAME')}/{repo_name}"
            response = create_pr(repo_full, "PR via Bot", "feature", "main")

        elif 'create branch' in msg:
            repo_name = msg.split()[-1]
            repo_full = f"{os.getenv('GITHUB_USERNAME')}/{repo_name}"
            response = create_branch(repo_full, "feature")

        elif 'review code' in msg:
            code_snippet = msg.split('review code')[-1].strip()
            response = ai_code_review(code_snippet)

        elif msg.startswith("search"):
            response = search_web(msg[6:].strip())

        else:
            response = query_phi_model(msg)

        send_message(chat_id, response)
        return jsonify({'status': 'ok'})

    except Exception as e:
        logger.exception("Webhook error")
        return jsonify({'status': 'error', 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8443)
