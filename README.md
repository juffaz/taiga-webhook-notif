Taiga Webhook Watcher (Assigned + Watchers Notifier)

This is a lightweight Python Flask application designed to listen for Taiga webhooks and send real-time email notifications to users involved in a specific task, issue, or user story.

It ensures that both the assigned user and all watchers receive an immediate notification whenever an item is updated, complementing Taiga's internal notification system.
🚀 Features

    Real-time Notifications: Processes Taiga webhooks instantly.

    Targeted Emailing: Retrieves the emails of the item's assigned user and all watchers via the Taiga API.

    SMTP Integration: Uses standard Python SMTP libraries (smtplib) for actual email delivery.

    Fallback Email: Supports a fallback email address for error reporting or when no item recipients are found.

    Docker Ready: Designed to run easily in a containerized environment.

⚙️ Configuration

The application requires configuration via environment variables, typically managed using a .env file or directly in your docker-compose.yml.
1. Taiga API & Authentication (Mandatory)

Variable
	

Description
	

Example

TAIGA_URL
	

Your Taiga instance URL.
	

https://taiga.synapps.az

TAIGA_USERNAME
	

Username for API authentication (must have access to the project).
	

api_user

TAIGA_PASSWORD
	

Password for the API user.
	

secure_password123
2. SMTP Email Configuration (Mandatory for real sending)

These credentials are used by the application to connect to your mail server and send notifications.

Variable
	

Description
	

Example
	


SMTP_SERVER
	

The hostname of your SMTP server.
	

smtp.gmail.com
	


SMTP_PORT
	

The port for your SMTP server (usually 587 for TLS).
	

587
	


SMTP_LOGIN
	

The email address to send notifications from.
	

notifications@yourdomain.com
	


SMTP_PASSWORD
	

The password or App Password for the sending email account.
	

app_password_xyz
	


3. Service Fallback (Optional)

Variable
	

Description
	

Example

FALLBACK_EMAIL
	

Email used if API calls fail or no recipients are found. Set to "" to disable fallback.
	

admin@yourdomain.com
🛠️ Usage
1. Running with Docker Compose

This application is designed to run in a Docker container alongside your main Taiga service.

Create or update your docker-compose.yml to include the watcher service (assuming your Dockerfile or build context is correctly set up):

version: '3.8'
services:
  watcher:
    build: 
      context: ./taiga-watcher 
      dockerfile: Dockerfile
    container_name: taiga-webhook-watcher
    restart: always
    env_file:
      - .env # Ensure your .env file contains all necessary variables
    ports:
      - "8080:8080"
    # Ensure this network allows Taiga (or the outside world) to reach port 8080
    networks:
      - taiga_network 

networks:
  taiga_network:
    external: true # Or define it if part of this compose file

2. Configuring the Taiga Webhook

Once the service is running and accessible (e.g., at http://your-server-ip:8080), you must configure the webhook in your Taiga project:

    Navigate to your Project in Taiga.

    Go to Settings -> Webhooks.

    Click "New Webhook".

    Set the URL to point to your watcher service's endpoint: http://your-server-ip:8080/webhook

    Select the events you wish to trigger notifications (e.g., all Task, User Story, and Issue events).

    Save the webhook and use the Test Webhook button to verify the configuration and SMTP delivery. You should see a successful log in your container output.

💡 Troubleshooting

If you encounter issues, check the Docker logs for the taiga-webhook-watcher container. The application uses detailed, timestamped logging to indicate the exact stage of failure.

Log Message
	

Meaning & Action

❌ Authentication error. Check TAIGA_URL...
	

The API user credentials are wrong or Taiga is unreachable.

❌ CRITICAL: Failed to send email via SMTP: [error]
	

The SMTP configuration (server, port, login, or password) is incorrect, or the port is blocked by a firewall.

❌ API details fetch failed...
	

The Taiga item ID in the webhook payload was valid, but the watcher couldn't retrieve the full details, usually due to a temporary API issue.

✅ Email sent (Mocked)
	

This means the application couldn't find your SMTP_ environment variables and is currently in mock mode. Add the SMTP credentials.
