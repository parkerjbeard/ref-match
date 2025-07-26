import requests
from typing import Dict, Optional
from config.config import Config
from app.utils.logger import get_logger
import base64

logger = get_logger(__name__)


class CheckrClient:
    """Wrapper for Checkr background check operations"""
    
    def __init__(self):
        self.api_key = Config.CHECKR_API_KEY
        self.base_url = "https://api.checkr.com/v1"
        self.headers = {
            'Content-Type': 'application/json'
        }
        
        if self.api_key:
            # Checkr uses Basic Auth with API key as username
            auth_string = f"{self.api_key}:"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            self.headers['Authorization'] = f"Basic {encoded_auth}"
        else:
            logger.warning("Checkr API key not configured")
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Optional[Dict]:
        """Make API request to Checkr"""
        if not self.api_key:
            logger.error("Checkr API key not configured")
            return None
            
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Checkr API error: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Response: {e.response.text}")
            return None
    
    def create_candidate(self, email: str, first_name: str, last_name: str, 
                        dob: str, ssn: str, zipcode: str, phone: str = None) -> Optional[Dict]:
        """Create a candidate for background check"""
        data = {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'dob': dob,  # Format: YYYY-MM-DD
            'ssn': ssn,
            'zipcode': zipcode
        }
        
        if phone:
            data['phone'] = phone
            
        return self._make_request('POST', '/candidates', data)
    
    def create_invitation(self, candidate_id: str, package: str = 'tasker_pro') -> Optional[Dict]:
        """Create invitation for candidate to complete background check"""
        data = {
            'candidate_id': candidate_id,
            'package': package,  # Package determines what checks are run
            'work_locations': [{'country': 'US', 'state': 'AZ'}]  # Phoenix region
        }
        
        return self._make_request('POST', '/invitations', data)
    
    def create_report(self, candidate_id: str, package: str = 'tasker_pro') -> Optional[Dict]:
        """Create a background check report directly (if candidate already verified)"""
        data = {
            'candidate_id': candidate_id,
            'package': package
        }
        
        return self._make_request('POST', '/reports', data)
    
    def get_report(self, report_id: str) -> Optional[Dict]:
        """Get background check report status and details"""
        return self._make_request('GET', f'/reports/{report_id}')
    
    def get_candidate(self, candidate_id: str) -> Optional[Dict]:
        """Get candidate details"""
        return self._make_request('GET', f'/candidates/{candidate_id}')
    
    def list_reports(self, candidate_id: str = None) -> Optional[Dict]:
        """List all reports, optionally filtered by candidate"""
        endpoint = '/reports'
        if candidate_id:
            endpoint += f'?candidate_id={candidate_id}'
        
        return self._make_request('GET', endpoint)
    
    def parse_report_status(self, report: Dict) -> str:
        """Parse report to determine overall status"""
        if not report:
            return 'pending'
            
        status = report.get('status', 'pending')
        
        if status == 'complete':
            # Check if report is clear
            if report.get('adjudication') == 'engaged':
                return 'clear'
            elif report.get('adjudication') == 'adverse':
                return 'failed'
            else:
                # Check individual report sections
                clear = True
                for section in ['criminal_search', 'motor_vehicle_report', 'national_criminal_search']:
                    section_data = report.get(section, {})
                    if section_data.get('status') == 'consider':
                        clear = False
                        break
                
                return 'clear' if clear else 'consider'
        
        return status
    
    def webhook_handler(self, webhook_data: Dict) -> Dict:
        """Handle Checkr webhook events"""
        event_type = webhook_data.get('type')
        data = webhook_data.get('data', {})
        
        result = {
            'event_type': event_type,
            'processed': False,
            'action_required': None
        }
        
        if event_type == 'report.completed':
            report_id = data.get('object', {}).get('id')
            if report_id:
                report = self.get_report(report_id)
                status = self.parse_report_status(report)
                result['processed'] = True
                result['report_status'] = status
                result['report_id'] = report_id
                
                if status == 'failed' or status == 'consider':
                    result['action_required'] = 'manual_review'
                    
        elif event_type == 'report.upgraded':
            result['processed'] = True
            result['action_required'] = 'check_report_status'
            
        elif event_type == 'invitation.completed':
            result['processed'] = True
            result['action_required'] = 'create_report'
            
        return result