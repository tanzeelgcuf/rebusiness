import os
import re
import time
import subprocess
import anthropic
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

LOG_PATH = "/Users/apple/Downloads/rebusinessautomationproject/dashboard/logs/submission.log"
PROJECT_ROOT = "/Users/apple/Downloads/rebusinessautomationproject"
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

ERROR_ACTIONS = {
    r"Session expired|cookie invalid|auth_state": "relogin",
    r"DataDome|captcha|slider|blocked|403": "retry_with_free_solver",
    r"Xvfb|DISPLAY|Cannot connect to display": "restart_xvfb",
    r"RFQs processed: 0|No pending RFQs": "diagnose_queue",
    r"ProxyError|ECONNREFUSED|proxy.*fail": "restart_with_new_proxy",
    r"TimeoutError|Target.*closed|browser.*crash": "restart_pipeline"
}


def log_agent(msg):
    entry = f"[AI-AGENT {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(entry)
    with open(f"{PROJECT_ROOT}/dashboard/logs/agent.log", "a") as f:
        f.write(entry + "\n")


def execute_action(action, context):
    if action == "relogin":
        log_agent("Auto-login triggered...")
        subprocess.Popen(
            ["python3", f"{PROJECT_ROOT}/ai_monitor_agent/auto_login.py"],
            cwd=PROJECT_ROOT
        )
    elif action == "retry_with_free_solver":
        log_agent("Retrying with free DataDome solver...")
        subprocess.Popen(
            ["python3", f"{PROJECT_ROOT}/ai_monitor_agent/full_auto_submitter.py"],
            cwd=PROJECT_ROOT
        )
        log_agent("Pipeline restarted with free solver")
    elif action == "restart_xvfb":
        subprocess.run(["pkill", "Xvfb"])
        time.sleep(1)
        subprocess.Popen(["Xvfb", ":99", "-screen", "0", "1920x1080x24"])
        log_agent("Xvfb restarted")
    elif action == "restart_pipeline":
        subprocess.Popen(
            ["python3", f"{PROJECT_ROOT}/ai_monitor_agent/full_auto_submitter.py"],
            cwd=PROJECT_ROOT
        )
        log_agent("Pipeline restarted")

    # Always get Claude diagnosis
    diagnosis = diagnose_with_claude(context, action)
    log_agent(f"CLAUDE DIAGNOSIS: {diagnosis}")


def diagnose_with_claude(log_snippet, action):
    try:
        msg = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=500,
            messages=[{"role": "user", "content": f"""
ThomasNet RFQ automation error. Action triggered: {action}

Log snippet:
{log_snippet[-1500:]}

Give me: ROOT CAUSE | EXACT FIX | CONFIDENCE (1-10)
Be concise, no fluff.
"""}]
        )
        return msg.content[0].text
    except Exception as e:
        return f"Claude diagnosis failed: {e}"


class LogWatcher(FileSystemEventHandler):
    def __init__(self):
        self.last_pos = os.path.getsize(LOG_PATH) if os.path.exists(LOG_PATH) else 0

    def on_modified(self, event):
        if event.src_path != LOG_PATH:
            return
        try:
            with open(LOG_PATH) as f:
                f.seek(self.last_pos)
                new_content = f.read()
                self.last_pos = f.tell()

            if not new_content.strip():
                return

            for pattern, action in ERROR_ACTIONS.items():
                if re.search(pattern, new_content, re.IGNORECASE):
                    log_agent(f"🚨 Detected pattern: {pattern} → Action: {action}")
                    execute_action(action, new_content)
                    break
        except Exception as e:
            log_agent(f"Watcher error: {e}")


def main():
    log_agent("🤖 Self-Healing AI Agent STARTED")
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    if not os.path.exists(LOG_PATH):
        open(LOG_PATH, "w").close()

    observer = Observer()
    observer.schedule(LogWatcher(), path=os.path.dirname(LOG_PATH), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()