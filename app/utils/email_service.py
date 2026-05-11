

# ______________________________________________

import sendgrid
from sendgrid.helpers.mail import Mail
from flask import current_app
import os

def _send_email(recipient, subject, html_content):
    """
    A centralized helper function to send emails via SendGrid.
    """
    # Ensure the API key is present in the configuration
    api_key = current_app.config.get('MAIL_PASSWORD')
    if not api_key:
        print("[EMAIL_SERVICE_ERROR] SendGrid API Key ('MAIL_PASSWORD') is not set in the configuration.")
        current_app.logger.error("Email sending failed: MAIL_PASSWORD not configured.")
        return False
        
    try:
        sg = sendgrid.SendGridAPIClient(api_key=api_key)
        
        message = Mail(
            from_email=current_app.config['MAIL_DEFAULT_SENDER'],
            to_emails=recipient,
            subject=subject,
            html_content=html_content
        )
        
        response = sg.send(message)
        
        # SendGrid's API returns a 202 status code for a successful send request.
        if response.status_code == 202:
            print(f"Successfully sent email to {recipient} with subject '{subject}'")
            return True
        else:
            print(f"[EMAIL_SERVICE_ERROR] SendGrid failed to send email. Status: {response.status_code}, Body: {response.body}")
            current_app.logger.error(f"SendGrid error: {response.status_code} {response.body}")
            return False

    except Exception as e:
        print(f"[EMAIL_SERVICE_ERROR] An exception occurred: {e}")
        current_app.logger.error(f"Email sending failed: {str(e)}")
        return False

def send_credentials_email(recipient, name, email, password):
    """Sends new user credentials with an enhanced template."""
    subject = "Welcome to the Training Management System!"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #0d6efd; text-align: center;">Welcome, {name}!</h2>
            <p>We are thrilled to have you on board. An account has been created for you in our Training Management System.</p>
            <p>Please use the following credentials to log in and begin your journey:</p>
            <div style="background-color: #f8f9fa; padding: 15px; border-left: 5px solid #0d6efd; margin: 20px 0;">
                <p style="margin: 5px 0;"><strong>Username:</strong> {email}</p>
                <p style="margin: 5px 0;"><strong>Temporary Password:</strong> <span style="font-weight: bold; color: #dc3545;">{password}</span></p>
            </div>
            <p>For your security, we strongly recommend that you change this temporary password immediately after your first login.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{os.getenv('APP_URL', 'http://127.0.0.1:5000')}/login" 
                   style="background-color: #0d6efd; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Login to Your Account
                </a>
            </div>
            <p>If you have any questions, please don't hesitate to contact your administrator.</p>
            <hr style="border: none; border-top: 1px solid #eee;">
            <p style="font-size: 0.8em; color: #777; text-align: center;">The Digital Mitraz Training Team</p>
        </div>
    </body>
    </html>
    """
    return _send_email(recipient, subject, html_content)




def send_password_reset_email(recipient, name, reset_token):
    subject = "Password Reset Request for Your Account"
    reset_url = f"{os.getenv('APP_URL', 'http://127.0.0.1:5000')}/reset_password/{reset_token}"
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: #0d6efd; text-align: center;">Reset Your Password</h2>
            <p>Hello {name},</p>
            <p>We received a request to reset the password for your account. If you did not make this request, you can safely ignore this email.</p>
            <p>To set a new password, please click the button below. This link is only valid for the next 60 minutes.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" 
                   style="background-color: #198754; color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Set a New Password
                </a>
            </div>
            <p>If the button above does not work, you can copy and paste the following link into your browser:</p>
            <p style="font-size: 0.9em; word-break: break-all; color: #555;">{reset_url}</p>
            <hr style="border: none; border-top: 1px solid #eee;">
            <p style="font-size: 0.8em; color: #777; text-align: center;">The Training Management Team</p>
        </div>
    </body>
    </html>
    """
    return _send_email(recipient, subject, html_content)

def send_leave_status_email(recipient, name, leave_details, status):
    """Sends a notification about the status of a leave application with an enhanced template."""
    status_text = status.capitalize()
    status_color = '#198754' if status == 'approved' else '#dc3545'
    subject = f"Your Leave Application has been {status_text}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 20px auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
            <h2 style="color: {status_color}; text-align: center;">Leave Application {status_text}</h2>
            <p>Hello {name},</p>
            <p>This is an update regarding your recent leave application. Your request has been reviewed and its status is now <strong>{status_text}</strong>.</p>
            <h4 style="color: #333; border-bottom: 2px solid #eee; padding-bottom: 5px; margin-top: 25px;">Application Details</h4>
            <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 15px 0;">
                <p style="margin: 5px 0;"><strong>Leave Period:</strong> {leave_details['start_date'].strftime('%B %d, %Y')} to {leave_details['end_date'].strftime('%B %d, %Y')}</p>
                <p style="margin: 5px 0;"><strong>Reason Provided:</strong> {leave_details['reason']}</p>
                <p style="margin: 5px 0;"><strong>Final Status:</strong> <span style="font-weight: bold; color: {status_color};">{status_text}</span></p>
                
                {'<p style="margin: 5px 0;"><strong>Admin Comments:</strong> ' + leave_details.get('admin_comments', 'N/A') + '</p>' if leave_details.get('admin_comments') else ''}
            </div>
            <p>You can view your complete leave history by logging into your student dashboard.</p>
            <hr style="border: none; border-top: 1px solid #eee;">
            <p style="font-size: 0.8em; color: #777; text-align: center;">The Digital Mitraz Training Team</p>
        </div>
    </body>
    </html>
    """
    return _send_email(recipient, subject, html_content)