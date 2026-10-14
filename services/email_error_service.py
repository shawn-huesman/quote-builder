import base64
import functools
import logging
from email.message import EmailMessage

from google.oauth2 import service_account
from googleapiclient.discovery import build


class EmailErrorHandler(logging.Handler):

    def __init__(self, get_key, sender, recipients):
        super().__init__(level=logging.ERROR)
        self.get_key = get_key
        self.sender = sender
        self.recipients = recipients

    def emit(self, record):
        try:
            address = getattr(record, "job_address", None)
            details = getattr(record, "job_details", {})

            if not address:
                import sys
                tb = record.exc_info[2] if record.exc_info else sys.exc_info()[2]
                while tb:
                    frame = tb.tb_frame
                    job = frame.f_locals.get("job")
                    if job:
                        address = job.address
                        details = {
                            "address": job.address,
                            "monday_item_id": job.monday_item_id,
                            "monday_board_id": job.monday_board_id,
                            "workspace_id": frame.f_locals.get("workspace_id", "N/A"),
                            "project_id": getattr(job, "project_id", "N/A")
                        }
                        break
                    tb = tb.tb_next

            address = address or "Unknown Address"
            error_msg = record.getMessage()
            traceback_text = self.format(record)

            msg = EmailMessage()
            msg["Subject"] = f"{address} - [ERROR] {error_msg[:80]}"
            msg["From"] = self.sender
            msg["To"] = ", ".join(self.recipients)

            # Plain text fallback
            msg.set_content(
                f"ERROR: {error_msg}\n\nAddress: {address}\nDetails: {details}\n\nTraceback:\n{traceback_text}")

            # HTML version with the full clean layout, table, and dark traceback box
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.5; margin: 0; padding: 20px;">

                <!-- Main Error Banner Up Top -->
                <div style="background-color: #f8d7da; color: #721c24; padding: 15px; border-radius: 6px; border: 1px solid #f5c6cb; margin-bottom: 20px;">
                    <h2 style="margin: 0 0 5px 0; font-size: 18px;">⚠️ Pipeline Error</h2>
                    <p style="margin: 0; font-family: monospace; font-size: 14px; font-weight: bold;">{error_msg}</p>
                </div>

                <!-- Job Details Table Box -->
                <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #dee2e6; margin-bottom: 20px;">
                    <h3 style="margin-top: 0; font-size: 15px; color: #495057; border-bottom: 1px solid #dee2e6; padding-bottom: 8px;">Job Metadata</h3>
                    <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 4px 0; font-weight: bold; width: 140px; color: #495057;">Address:</td>
                            <td style="padding: 4px 0; color: #212529;">{address}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: bold; color: #495057;">Monday Item ID:</td>
                            <td style="padding: 4px 0; color: #212529;">{details.get('monday_item_id', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: bold; color: #495057;">Monday Board ID:</td>
                            <td style="padding: 4px 0; color: #212529;">{details.get('monday_board_id', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: bold; color: #495057;">Workspace ID:</td>
                            <td style="padding: 4px 0; color: #212529;">{details.get('workspace_id', 'N/A')}</td>
                        </tr>
                        <tr>
                            <td style="padding: 4px 0; font-weight: bold; color: #495057;">Project ID:</td>
                            <td style="padding: 4px 0; color: #212529;">{details.get('project_id', 'N/A')}</td>
                        </tr>
                    </table>
                </div>

                <!-- Traceback Section -->
                <div style="margin-top: 10px;">
                    <h3 style="font-size: 14px; color: #495057; margin-bottom: 5px;">Full Traceback</h3>
                    <pre style="background: #212529; color: #f8f9fa; padding: 15px; border-radius: 6px; font-family: Consolas, Monaco, monospace; font-size: 12px; overflow-x: auto; max-height: 350px; margin: 0;">{traceback_text}</pre>
                </div>

            </body>
            </html>
            """

            msg.add_alternative(html_content, subtype="html")

            creds = service_account.Credentials.from_service_account_info(
                self.get_key(), scopes=["https://www.googleapis.com/auth/gmail.send"]
            ).with_subject(self.sender)
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            build("gmail", "v1", credentials=creds).users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
        except Exception as e:
            print(f"Failed to send error email: {e}")


def log_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Look inside the functions frame when it crashed to grab local variables
            local_vars = {}
            tb = e.__traceback__
            while tb:
                if tb.tb_frame.f_code.co_name == func.__name__:
                    local_vars = tb.tb_frame.f_locals
                tb = tb.tb_next

            # Fallback to event_data argument if needed
            event_data = kwargs.get("event_data") or (args[0] if args and isinstance(args[0], dict) else {})
            job = local_vars.get("job")

            address = (job.address if job else None) or event_data.get("pulseName", "Unknown Address")
            board_id = (job.monday_board_id if job else None) or event_data.get("boardId", "N/A")
            item_id = (job.monday_item_id if job else None) or event_data.get("pulseId", "N/A")
            workspace_id = local_vars.get("workspace_id", "N/A")
            project_id = getattr(job, "project_id", "N/A") if job else "N/A"

            details = {
                "address": address,
                "monday_item_id": item_id,
                "monday_board_id": board_id,
                "workspace_id": workspace_id,
                "project_id": project_id,
            }

            logging.getLogger().exception(
                f"{func.__name__} crashed",
                extra={
                    "job_address": address,
                    "job_details": details
                }
            )
            raise
    return wrapper