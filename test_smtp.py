"""
Local test script. Verifies SMTP credentials BEFORE you commit to GitHub Actions.

Usage (PowerShell on Windows):
    $env:SMTP_USER="your-email@qq.com"
    $env:SMTP_PASS="your_auth_code"
    python test_smtp.py

Usage (bash on macOS/Linux):
    SMTP_USER=your-email@qq.com SMTP_PASS=your_auth_code python test_smtp.py

Or copy .env.example to .env, fill it in, and run with python-dotenv:
    pip install python-dotenv
    python -c "from dotenv import load_dotenv; load_dotenv()" && python test_smtp.py
"""
from src.email_sender import send_test_email

if __name__ == "__main__":
    send_test_email()
