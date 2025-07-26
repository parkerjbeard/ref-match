#!/usr/bin/env python3
"""
Script to seed the database with sample data for testing
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from app.database import init_db, drop_db, get_db
from app.models import User, QuizQuestion, Certification
from app.models.user import UserRole
from app.models.certification import Sport, CertificationLevel
from app.utils.security import hash_password
import random


def create_quiz_questions(db):
    """Create sample quiz questions for all sports"""
    
    sports = [Sport.BASKETBALL, Sport.FOOTBALL, Sport.SOCCER, 
              Sport.SOFTBALL, Sport.VOLLEYBALL, Sport.BASEBALL]
    levels = [CertificationLevel.ENTRY, CertificationLevel.INTERMEDIATE, 
              CertificationLevel.ADVANCED]
    
    sample_questions = {
        Sport.BASKETBALL: {
            CertificationLevel.ENTRY: [
                {
                    'question': 'How many players are on the court for each team?',
                    'options': ['4', '5', '6', '7'],
                    'correct_answer': 1,
                    'explanation': 'Basketball is played with 5 players per team.'
                },
                {
                    'question': 'How many fouls before a player fouls out?',
                    'options': ['4', '5', '6', '7'],
                    'correct_answer': 2,
                    'explanation': 'A player fouls out after 6 personal fouls.'
                },
                {
                    'question': 'How long is the shot clock?',
                    'options': ['20 seconds', '24 seconds', '30 seconds', '35 seconds'],
                    'correct_answer': 1,
                    'explanation': 'The shot clock is 24 seconds.'
                }
            ],
            CertificationLevel.INTERMEDIATE: [
                {
                    'question': 'What is a technical foul?',
                    'options': [
                        'Hitting another player',
                        'Unsportsmanlike conduct or violations',
                        'Traveling with the ball',
                        'Shot clock violation'
                    ],
                    'correct_answer': 1,
                    'explanation': 'Technical fouls are for unsportsmanlike conduct.'
                }
            ],
            CertificationLevel.ADVANCED: [
                {
                    'question': 'When is a basket interference call made?',
                    'options': [
                        'Ball is touched on downward flight',
                        'Ball is touched while on the rim',
                        'Ball is touched in the cylinder',
                        'All of the above'
                    ],
                    'correct_answer': 3,
                    'explanation': 'Basket interference includes all these scenarios.'
                }
            ]
        }
    }
    
    # Create generic questions for other sports/levels
    question_count = 0
    for sport in sports:
        if sport not in sample_questions:
            sample_questions[sport] = {}
        
        for level in levels:
            if level not in sample_questions[sport]:
                sample_questions[sport][level] = []
            
            # Ensure at least 3 questions per sport/level
            while len(sample_questions[sport][level]) < 3:
                q_num = len(sample_questions[sport][level]) + 1
                sample_questions[sport][level].append({
                    'question': f'{sport.value} {level.value} Question {q_num}',
                    'options': ['Option A', 'Option B', 'Option C', 'Option D'],
                    'correct_answer': random.randint(0, 3),
                    'explanation': f'This is the explanation for {sport.value} {level.value} question {q_num}.'
                })
    
    # Insert questions into database
    for sport in sports:
        for level in levels:
            for idx, q_data in enumerate(sample_questions[sport][level]):
                question = QuizQuestion(
                    sport=sport,
                    level=level,
                    question=f"{q_data['question']} (Question {idx + 1})",
                    options=q_data['options'],
                    correct_answer=q_data['correct_answer'],
                    explanation=q_data['explanation'],
                    is_active=True
                )
                db.add(question)
                question_count += 1
    
    db.commit()
    print(f"Created {question_count} quiz questions")


def create_users(db):
    """Create sample users"""
    
    # Create admin user
    admin = User(
        email='admin@refmatch.com',
        phone='+15555550000',
        password_hash=hash_password('Admin123!'),
        first_name='Admin',
        last_name='User',
        role=UserRole.ADMIN,
        is_active=True,
        email_verified=True,
        phone_verified=True,
        address='100 Admin St',
        city='Phoenix',
        state='AZ',
        zip_code='85001',
        latitude=33.4484,
        longitude=-112.0740
    )
    db.add(admin)
    
    # Create organizers
    organizers = []
    for i in range(3):
        org = User(
            email=f'organizer{i+1}@school.edu',
            phone=f'+1555555010{i}',
            password_hash=hash_password('Organizer123!'),
            first_name=f'Organizer',
            last_name=f'{i+1}',
            role=UserRole.ORGANIZER,
            organization_name=f'School {i+1}',
            organization_type='school',
            is_active=True,
            email_verified=True,
            address=f'{100+i} School St',
            city='Phoenix',
            state='AZ',
            zip_code=f'8500{i}',
            latitude=33.4484 + (i * 0.01),
            longitude=-112.0740 - (i * 0.01)
        )
        db.add(org)
        organizers.append(org)
    
    # Create referees
    referees = []
    for i in range(10):
        ref = User(
            email=f'referee{i+1}@email.com',
            phone=f'+1555555020{i}',
            password_hash=hash_password('Referee123!'),
            first_name=f'Referee',
            last_name=f'{i+1}',
            role=UserRole.REFEREE,
            is_active=True,
            email_verified=True,
            phone_verified=True,
            background_check_status='clear',
            reliability_score=round(0.8 + (random.random() * 0.2), 2),
            total_games_completed=random.randint(0, 50),
            address=f'{200+i} Referee Ave',
            city='Phoenix',
            state='AZ',
            zip_code=f'8501{i%10}',
            latitude=33.4484 + (random.random() * 0.1 - 0.05),
            longitude=-112.0740 + (random.random() * 0.1 - 0.05),
            travel_distance_km=random.choice([25, 30, 40, 50]),
            emergency_pool_opt_in=i < 3  # First 3 refs in emergency pool
        )
        db.add(ref)
        referees.append(ref)
    
    # Commit all users first
    db.commit()
    
    # Create certifications for referees
    sports = [Sport.BASKETBALL, Sport.FOOTBALL, Sport.SOCCER]
    levels = [CertificationLevel.ENTRY, CertificationLevel.INTERMEDIATE, CertificationLevel.ADVANCED]
    
    cert_count = 0
    for ref in referees[:8]:  # First 8 refs get certifications
        # Give each referee 1-3 sport certifications
        num_certs = random.randint(1, 3)
        ref_sports = random.sample(sports, num_certs)
        
        for sport in ref_sports:
            level = random.choice(levels)
            cert = Certification(
                referee_id=ref.id,
                sport=sport,
                level=level,
                is_active=True,
                passed_date=datetime.utcnow() - timedelta(days=random.randint(30, 365)),
                expiry_date=datetime.utcnow() + timedelta(days=365),
                quiz_score=round(0.8 + (random.random() * 0.2), 2)
            )
            db.add(cert)
            cert_count += 1
    
    db.commit()
    print(f"Created {cert_count} certifications")
    
    return {
        'admin': admin,
        'organizers': organizers,
        'referees': referees
    }


def main():
    """Main seeding function"""
    print("Dropping existing database...")
    drop_db()
    
    print("Initializing new database...")
    init_db()
    
    # Use a single session for all operations
    with get_db() as db:
        print("Creating quiz questions...")
        create_quiz_questions(db)
        
        print("Creating users...")
        users = create_users(db)
    
    print("\nDatabase seeded successfully!")
    print(f"Created:")
    print(f"- 1 Admin user (admin@refmatch.com / Admin123!)")
    print(f"- {len(users['organizers'])} Organizers")
    print(f"- {len(users['referees'])} Referees (8 with certifications)")
    print(f"- Quiz questions for all sports and levels")
    
    print("\nYou can now run the application and log in with any of the created users.")


if __name__ == "__main__":
    main()