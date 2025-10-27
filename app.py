import os
import requests
import logging
import smtplib 
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
from requests.exceptions import RequestException

# === Logging Configuration ===
# Устанавливаем формат логирования, включая метку времени
logging.basicConfig(level=logging.INFO, 
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

# === Configuration ===
TAIGA_URL = os.getenv("TAIGA_URL", "https://taiga.site.az")
TAIGA_USERNAME = os.getenv("TAIGA_USERNAME")
TAIGA_PASSWORD = os.getenv("TAIGA_PASSWORD")
FALLBACK_EMAIL = os.getenv("FALLBACK_EMAIL") 

# === НОВЫЕ НАСТРОЙКИ ДЛЯ ОТПРАВКИ EMAIL (Требуются в .env) ===
SMTP_SERVER = os.getenv("SMTP_SERVER")      
SMTP_PORT = int(os.getenv("SMTP_PORT", 587)) 
SMTP_LOGIN = os.getenv("SMTP_LOGIN")        
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_LOGIN)

app = Flask(__name__)
app.config['DEBUG'] = False 
AUTH_TOKEN = None

# === Taiga API Functions ===

def taiga_authenticate() -> str:
    """Authenticates with Taiga and retrieves the AUTH_TOKEN."""
    global AUTH_TOKEN
    url = f"{TAIGA_URL}/api/v1/auth"
    payload = {"type": "normal", "username": TAIGA_USERNAME, "password": TAIGA_PASSWORD}
    
    if AUTH_TOKEN:
        return AUTH_TOKEN
        
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        AUTH_TOKEN = r.json().get("auth_token")
        logger.info("✅ Taiga authenticated")
        return AUTH_TOKEN
    except RequestException as e:
        logger.error(f"❌ Authentication error. Check TAIGA_URL, USERNAME, and PASSWORD in .env: {e}")
        return ""

def get_task_details(item_id: int, item_type: str, token: str) -> dict:
    """Fetches full details for a given User Story, Task, or Issue ID."""
    endpoint_map = {
        "task": "tasks",
        "userstory": "userstories",
        "issue": "issues",
    }
    
    endpoint = endpoint_map.get(item_type)
    if not endpoint:
        raise ValueError(f"Unknown item type: {item_type}")

    url = f"{TAIGA_URL}/api/v1/{endpoint}/{item_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    except RequestException as e:
        logger.error(f"❌ API details fetch failed for {item_type} {item_id}. Response status: {e.response.status_code if e.response else 'N/A'}")
        raise 

def get_user_emails_by_ids(user_ids: list, token: str) -> list:
    """Fetches user emails by making an individual API request for each user ID."""
    if not user_ids:
        return []
    
    emails = []
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    for user_id in set(user_ids):
        if user_id is None:
            continue
        
        url = f"{TAIGA_URL}/api/v1/users/{user_id}" 
        try:
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            user_data = r.json()
            email = user_data.get("email")
            
            if email:
                emails.append(email)
            else:
                logger.warning(f"⚠️ User ID {user_id} ({user_data.get('username', 'Unknown')}) found, but email is empty in profile.")

        except RequestException as e:
            logger.error(f"❌ Failed to fetch detailed profile for user ID {user_id}: {e}")
            continue
            
    return list(set(emails))

def send_email(recipients: list, subject: str, body: str) -> None:
    """Sends an email using the configured SMTP server or falls back to mock."""
    if not recipients:
        logger.warning("⚠️ No recipients for email.")
        return

    # Проверка обязательных настроек SMTP
    if not all([SMTP_SERVER, SMTP_LOGIN, SMTP_PASSWORD]):
        logger.warning("⚠️ SMTP credentials missing. Using mock send.")
        logger.info("--- EMAIL CONTENT (MOCKED) ---")
        logger.info(f"TO: {', '.join(recipients)}")
        logger.info(f"SUBJECT: {subject}")
        logger.info("---------------------")
        logger.info("✅ Email sent (Mocked)")
        return

    logger.info("--- EMAIL CONTENT (ATTEMPTING SEND) ---")
    logger.info(f"TO: {', '.join(recipients)}")
    logger.info(f"SUBJECT: {subject}")
    logger.info("---------------------------------------")

    try:
        msg = MIMEText(body, "html")   #msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL         # ✅ Используем FROM_EMAIL вместо SMTP_LOGIN
        msg['To'] = ', '.join(recipients)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_LOGIN, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, recipients, msg.as_string())  # ✅ И здесь FROM_EMAIL

        logger.info("✅ Email sent successfully via SMTP.")
    except Exception as e:
        logger.critical(f"❌ CRITICAL ERROR: Failed to send email via SMTP: {e}")



# === Webhook Handler (УСИЛЕННОЕ ЛОГИРОВАНИЕ) ===
@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handles incoming Taiga webhooks."""
    global AUTH_TOKEN
    
    # 0. Самая первая проверка
    try:
        data = request.json
        if data is None:
             logger.error("❌ Request received, but JSON payload is NULL or invalid.")
             return jsonify({"status": "Invalid JSON payload"}), 400
    except Exception as e:
        logger.error(f"❌ Failed to parse JSON payload (Exception): {e}")
        return jsonify({"status": "Invalid JSON payload"}), 400
        
    logger.info(f"📥 === NEW WEBHOOK EVENT (Type: {data.get('type')}) ===")

    # 1. Authentication Check
    if AUTH_TOKEN is None:
        AUTH_TOKEN = taiga_authenticate()
        if not AUTH_TOKEN:
            logger.error("❌ Webhook aborted: Taiga authentication failed.")
            return jsonify({"status": "Error: Taiga authentication failed"}), 500

    # Handle Taiga test webhook
    if data.get('type') == 'test':
        logger.info("➡️ Taiga test webhook received. Responding OK.")
        to_email = [FALLBACK_EMAIL] if FALLBACK_EMAIL else ["Taiga system"]
        # Отправляем тестовое письмо, используя функцию send_email
        send_email(to_email, "Taiga Webhook Test Success", "The webhook watcher service is operational.")
        return jsonify({
            "status": "Webhook test received and OK",
            "emails_sent": 1,
            "to": to_email
        }), 200
    
    # === Standard Webhook Processing ===
    task_type = data.get("type")
    task_action = data.get("action")
    task_id = data.get("data", {}).get("id")
    
    if not task_type or not task_id:
        logger.warning(f"⚠️ Missing type or ID in payload. Keys: {data.keys()}")
        return jsonify({"status": "Missing type or ID"}), 400
    
    # 2. Fetch details and Collect IDs
    try:
        logger.info(f"🔍 Fetching details for {task_type} {task_id}")
        details = get_task_details(task_id, task_type, AUTH_TOKEN)
        
        assigned_id = details.get("assigned_to")
        watcher_ids = details.get("watchers", [])
        
        all_user_ids = [assigned_id] if assigned_id else []
        all_user_ids.extend(watcher_ids)
        
    except RequestException:
        logger.error(f"❌ CRITICAL: RequestException when fetching details for {task_type} {task_id}. Proceeding with fallback.")
        recipient_emails = [FALLBACK_EMAIL] if FALLBACK_EMAIL else []
        
        subject = f"[{task_type.upper()} {task_id}]: Action {task_action} - ERROR"
        if recipient_emails:
            send_email(recipient_emails, subject, "Error fetching details. Check Taiga service status.")
        return jsonify({"status": "Processed with fallback (details fetch failed)"}), 200
    
    except Exception as e:
        logger.critical(f"❌ UNEXPECTED ERROR during detail fetching/parsing: {e}")
        return jsonify({"status": f"Internal error: {e}"}), 500


    # 3. Get user emails
    recipient_emails = get_user_emails_by_ids(all_user_ids, AUTH_TOKEN)

    if not recipient_emails and FALLBACK_EMAIL:
        logger.warning(f"⚠️ No user emails found for IDs {all_user_ids}. Using fallback: {FALLBACK_EMAIL}")
        recipient_emails = [FALLBACK_EMAIL]
    
    elif not recipient_emails and FALLBACK_EMAIL == "":
        logger.warning("⚠️ No recipients found and fallback is disabled. Exiting.")
        return jsonify({"status": "No recipients found, no email sent"}), 200

    logger.info(f"📬 Recipients: {recipient_emails}")
    
    # 4. Prepare and send email
    subject = f"[{task_type.upper()} {details.get('ref', task_id)}]: Action {task_action} - {details.get('subject', 'N/A')}"
    
    project_slug = details.get('project_extra_info', {}).get('slug', 'default')
    item_ref = details.get('ref') or task_id
    item_prefix = task_type[:2]
    
    body_html = f"""
<html>
  <body style="font-family:Segoe UI,Arial,sans-serif; color:#2d2d2d; background:#f7f8fa; padding:24px;">
    <table width="100%" style="max-width:600px; margin:auto; background:white; border-radius:10px; box-shadow:0 2px 5px rgba(0,0,0,0.1); padding:24px;">
      <tr>
        <td>
          <h2 style="color:#007acc; margin-bottom:10px;">Taiga item updated</h2>
          <p style="font-size:14px; color:#555;">
            <b>Type:</b> {task_type.upper()}<br>
            <b>ID:</b> {item_ref}<br>
            <b>Subject:</b> {details.get('subject', 'N/A')}<br>
            <b>Action:</b> change by {data.get('by', {}).get('full_name', 'Unknown')}<br>
            <b>Status:</b> {details.get('status_extra_info', {}).get('name', 'N/A')}<br>
          </p>
          <p style="margin-top:20px;">
            <a href="{TAIGA_URL}/project/{project_slug}/{item_prefix}/{item_ref}" 
               style="display:inline-block; background:#007acc; color:white; text-decoration:none; 
                      padding:10px 16px; border-radius:6px;">
               🔗 Open in Taiga
            </a>
          </p>
        </td>
      </tr>
    </table>
    <p style="text-align:center; color:#999; font-size:12px; margin-top:20px;">
      Sent automatically by Taiga Watcher Service
    </p>
  </body>
</html>
"""



    send_email(recipient_emails, subject, body_html)

    logger.info("✅ Webhook processing successfully completed.")
    return jsonify({
        "status": "Processed successfully", 
        "emails_sent": len(recipient_emails), 
        "success_count": 1
    }), 200

# === Initial Run ===
if __name__ == '__main__':
    logger.info("🚀 Taiga Watcher (Assigned + Watchers) starting...")
    if not all([TAIGA_USERNAME, TAIGA_PASSWORD]):
        logger.critical("❌ CRITICAL: TAIGA_USERNAME or TAIGA_PASSWORD is not set in environment.")
        exit(1)
        
    taiga_authenticate()
    app.run(host='0.0.0.0', port=8080)
