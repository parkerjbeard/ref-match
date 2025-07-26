from flask import Blueprint, request, jsonify
from app.integrations import StripeClient, CheckrClient, TwilioClient
from app.services.webhook_service import WebhookService
from app.utils.logger import get_logger
import json

bp = Blueprint('webhooks', __name__)
logger = get_logger(__name__)

stripe_client = StripeClient()
checkr_client = CheckrClient()
twilio_client = TwilioClient()
webhook_service = WebhookService()


@bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    if not sig_header:
        return jsonify({'error': 'No signature header'}), 400
    
    # Verify webhook signature
    event = stripe_client.verify_webhook_signature(payload, sig_header)
    if not event:
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Process event
    try:
        result = webhook_service.process_stripe_event(event)
        return jsonify({'received': True, 'result': result}), 200
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/checkr', methods=['POST'])
def checkr_webhook():
    """Handle Checkr webhook events"""
    try:
        webhook_data = request.get_json()
        result = webhook_service.process_checkr_event(webhook_data)
        return jsonify({'received': True, 'result': result}), 200
    except Exception as e:
        logger.error(f"Error processing Checkr webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500


@bp.route('/twilio/sms', methods=['POST'])
def twilio_sms_webhook():
    """Handle incoming SMS messages"""
    try:
        # Get SMS data from Twilio
        from_number = request.form.get('From')
        to_number = request.form.get('To')
        body = request.form.get('Body')
        message_sid = request.form.get('MessageSid')
        
        logger.info(f"Received SMS from {from_number}: {body}")
        
        # Process SMS response
        result = webhook_service.process_sms_response(
            from_number=from_number,
            body=body,
            message_sid=message_sid
        )
        
        # Return empty response to Twilio
        return '', 200
        
    except Exception as e:
        logger.error(f"Error processing Twilio SMS webhook: {str(e)}")
        return '', 500


@bp.route('/twilio/status', methods=['POST'])
def twilio_status_webhook():
    """Handle SMS delivery status updates"""
    try:
        message_sid = request.form.get('MessageSid')
        message_status = request.form.get('MessageStatus')
        error_code = request.form.get('ErrorCode')
        
        logger.info(f"SMS status update: {message_sid} - {message_status}")
        
        if error_code:
            logger.error(f"SMS delivery error: {error_code}")
        
        # Update message status in database if needed
        webhook_service.update_sms_status(message_sid, message_status, error_code)
        
        return '', 200
        
    except Exception as e:
        logger.error(f"Error processing Twilio status webhook: {str(e)}")
        return '', 500


@bp.route('/sendgrid', methods=['POST'])
def sendgrid_webhook():
    """Handle SendGrid email events"""
    try:
        events = request.get_json()
        
        for event in events:
            event_type = event.get('event')
            email = event.get('email')
            
            logger.info(f"SendGrid event: {event_type} for {email}")
            
            # Process email events (delivered, bounced, opened, etc.)
            webhook_service.process_email_event(event)
        
        return jsonify({'received': True}), 200
        
    except Exception as e:
        logger.error(f"Error processing SendGrid webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500