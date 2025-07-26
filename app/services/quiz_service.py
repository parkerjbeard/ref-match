import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.database import DatabaseManager, get_db
from app.models import QuizQuestion, QuizAttempt, Certification, User
from app.models.certification import Sport, CertificationLevel
from app.integrations import SendGridClient
from config.config import Config
from app.utils.logger import get_logger

logger = get_logger(__name__)


class QuizService:
    """Service for managing certification quizzes"""
    
    def __init__(self):
        self.question_db = DatabaseManager(QuizQuestion)
        self.attempt_db = DatabaseManager(QuizAttempt)
        self.cert_db = DatabaseManager(Certification)
        self.sendgrid = SendGridClient()
    
    def create_quiz(self, referee_id: int, sport: str, level: str) -> Dict:
        """Create a new quiz for referee"""
        try:
            # Convert strings to enums
            sport_enum = Sport[sport.upper()]
            level_enum = CertificationLevel[level.upper()]
            
            # Get random questions
            questions = self._get_random_questions(sport_enum, level_enum)
            
            if len(questions) < Config.QUIZ_QUESTIONS_PER_TEST:
                return {'error': f'Not enough questions available for {sport} {level}'}
            
            # Create quiz attempt
            attempt = self.attempt_db.create(
                referee_id=referee_id,
                sport=sport_enum,
                level=level_enum,
                questions=[q.id for q in questions],
                answers=[],
                created_at=datetime.utcnow()
            )
            
            return {
                'quiz_id': attempt.id,
                'questions': [self._format_question(q) for q in questions],
                'total_questions': len(questions),
                'passing_score': int(Config.QUIZ_PASS_THRESHOLD * 100)
            }
            
        except Exception as e:
            logger.error(f"Error creating quiz: {str(e)}")
            return {'error': 'Failed to create quiz'}
    
    def submit_quiz(self, quiz_id: int, answers: List[int]) -> Dict:
        """Submit quiz answers and calculate score"""
        try:
            attempt = self.attempt_db.get(quiz_id)
            if not attempt:
                return {'error': 'Quiz not found'}
            
            if attempt.completed_at:
                return {'error': 'Quiz already completed'}
            
            # Get questions
            with get_db() as db:
                questions = db.query(QuizQuestion).filter(
                    QuizQuestion.id.in_(attempt.questions)
                ).all()
            
            # Calculate score
            correct = 0
            for i, question in enumerate(questions):
                if i < len(answers) and answers[i] == question.correct_answer:
                    correct += 1
            
            score = correct / len(questions)
            passed = score >= Config.QUIZ_PASS_THRESHOLD
            
            # Update attempt
            self.attempt_db.update(
                quiz_id,
                answers=answers,
                score=score,
                passed=passed,
                completed_at=datetime.utcnow()
            )
            
            # If passed, create or update certification
            if passed:
                self._create_certification(attempt.referee_id, attempt.sport, attempt.level, score)
            
            return {
                'score': round(score * 100, 2),
                'passed': passed,
                'correct': correct,
                'total': len(questions),
                'passing_score': int(Config.QUIZ_PASS_THRESHOLD * 100)
            }
            
        except Exception as e:
            logger.error(f"Error submitting quiz: {str(e)}")
            return {'error': 'Failed to submit quiz'}
    
    def get_quiz_results(self, quiz_id: int) -> Dict:
        """Get detailed quiz results"""
        try:
            attempt = self.attempt_db.get(quiz_id)
            if not attempt:
                return {'error': 'Quiz not found'}
            
            if not attempt.completed_at:
                return {'error': 'Quiz not completed'}
            
            # Get questions with answers
            with get_db() as db:
                questions = db.query(QuizQuestion).filter(
                    QuizQuestion.id.in_(attempt.questions)
                ).all()
            
            results = []
            for i, question in enumerate(questions):
                user_answer = attempt.answers[i] if i < len(attempt.answers) else None
                results.append({
                    'question': question.question,
                    'options': question.options,
                    'user_answer': user_answer,
                    'correct_answer': question.correct_answer,
                    'correct': user_answer == question.correct_answer,
                    'explanation': question.explanation
                })
            
            return {
                'quiz_id': quiz_id,
                'sport': attempt.sport.value,
                'level': attempt.level.value,
                'score': round(attempt.score * 100, 2),
                'passed': attempt.passed,
                'completed_at': attempt.completed_at.isoformat(),
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Error getting quiz results: {str(e)}")
            return {'error': 'Failed to get results'}
    
    def send_quiz_link(self, referee_id: int, sport: str, level: str) -> Dict:
        """Send quiz link to referee via email"""
        try:
            # Get referee
            with get_db() as db:
                referee = db.query(User).filter_by(id=referee_id).first()
                if not referee:
                    return {'error': 'Referee not found'}
            
            # Generate quiz link
            quiz_link = f"{Config.APP_URL}/quiz/{sport}/{level}?referee_id={referee_id}"
            
            # Send email
            result = self.sendgrid.send_quiz_link(
                referee.email,
                referee.first_name,
                sport,
                level,
                quiz_link
            )
            
            if result:
                return {'success': True, 'message': 'Quiz link sent'}
            else:
                return {'error': 'Failed to send email'}
                
        except Exception as e:
            logger.error(f"Error sending quiz link: {str(e)}")
            return {'error': 'Failed to send quiz link'}
    
    def _get_random_questions(self, sport: Sport, level: CertificationLevel) -> List[QuizQuestion]:
        """Get random questions for quiz"""
        with get_db() as db:
            all_questions = db.query(QuizQuestion).filter_by(
                sport=sport,
                level=level,
                is_active=True
            ).all()
            
            # Randomly select questions
            num_questions = min(len(all_questions), Config.QUIZ_QUESTIONS_PER_TEST)
            return random.sample(all_questions, num_questions)
    
    def _format_question(self, question: QuizQuestion) -> Dict:
        """Format question for API response"""
        return {
            'id': question.id,
            'question': question.question,
            'options': question.options
        }
    
    def _create_certification(self, referee_id: int, sport: Sport, level: CertificationLevel, score: float):
        """Create or update certification"""
        try:
            # Check if certification exists
            existing = self.cert_db.get_by(
                referee_id=referee_id,
                sport=sport,
                level=level
            )
            
            if existing:
                # Update existing certification
                self.cert_db.update(
                    existing.id,
                    quiz_score=score,
                    passed_date=datetime.utcnow(),
                    expiry_date=datetime.utcnow() + timedelta(days=365),
                    is_active=True
                )
            else:
                # Create new certification
                self.cert_db.create(
                    referee_id=referee_id,
                    sport=sport,
                    level=level,
                    quiz_score=score,
                    passed_date=datetime.utcnow(),
                    expiry_date=datetime.utcnow() + timedelta(days=365),
                    is_active=True
                )
                
        except Exception as e:
            logger.error(f"Error creating certification: {str(e)}")
    
    def seed_quiz_questions(self):
        """Seed database with sample quiz questions"""
        sports = ['basketball', 'football', 'soccer', 'softball', 'volleyball', 'baseball']
        levels = ['entry', 'intermediate', 'advanced']
        
        sample_questions = {
            'basketball': {
                'entry': [
                    {
                        'question': 'How many players are on the court for each team during play?',
                        'options': ['4', '5', '6', '7'],
                        'correct_answer': 1,
                        'explanation': 'Basketball is played with 5 players per team on the court.'
                    },
                    {
                        'question': 'What is the duration of a standard NBA quarter?',
                        'options': ['10 minutes', '12 minutes', '15 minutes', '20 minutes'],
                        'correct_answer': 1,
                        'explanation': 'NBA quarters are 12 minutes long.'
                    }
                ],
                'intermediate': [
                    {
                        'question': 'What constitutes a defensive three-second violation?',
                        'options': [
                            'Defender in paint for 3 seconds without guarding',
                            'Any player in paint for 3 seconds',
                            'Offensive player in paint for 3 seconds',
                            'Defender holding the ball for 3 seconds'
                        ],
                        'correct_answer': 0,
                        'explanation': 'A defensive player cannot remain in the paint for more than 3 seconds unless actively guarding an opponent.'
                    }
                ],
                'advanced': [
                    {
                        'question': 'In which situation would you NOT call a backcourt violation?',
                        'options': [
                            'Ball deflected by defense into backcourt',
                            'Player dribbles from frontcourt to backcourt',
                            'Pass from frontcourt to teammate in backcourt',
                            'Player jumps from frontcourt and lands in backcourt with ball'
                        ],
                        'correct_answer': 0,
                        'explanation': 'If the defense deflects the ball into the backcourt, there is no violation.'
                    }
                ]
            }
        }
        
        # Add more sports and questions as needed
        for sport in sports:
            sport_enum = Sport[sport.upper()]
            sport_questions = sample_questions.get(sport, {})
            
            for level in levels:
                level_enum = CertificationLevel[level.upper()]
                questions = sport_questions.get(level, [])
                
                # Create at least 20 questions per sport/level
                for i, q in enumerate(questions):
                    self.question_db.create(
                        sport=sport_enum,
                        level=level_enum,
                        question=q['question'],
                        options=q['options'],
                        correct_answer=q['correct_answer'],
                        explanation=q['explanation'],
                        is_active=True
                    )