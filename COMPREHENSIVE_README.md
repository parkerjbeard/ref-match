# RefMatch - Automated Referee Management Platform

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" />
  <img src="https://img.shields.io/badge/python-3.8+-green.svg" />
  <img src="https://img.shields.io/badge/flask-3.1.0-red.svg" />
  <img src="https://img.shields.io/badge/license-proprietary-orange.svg" />
</p>

## 🏀 Project Overview

RefMatch is a comprehensive automated referee management system designed to revolutionize how middle school sports leagues in the Phoenix area handle referee assignments. The platform eliminates the manual coordination nightmare of matching qualified referees to games by using an intelligent algorithm that considers distance, certifications, reliability, and availability.

### The Problem We Solve

Traditional referee assignment involves:
- 📞 Countless phone calls and texts
- 📋 Manual tracking in spreadsheets
- ❌ Last-minute cancellations with no backup
- 💸 Complex payment reconciliation
- 🚗 Referees driving excessive distances
- 📊 No performance tracking

RefMatch automates this entire process, reducing hours of manual work to minutes.

## 🌟 Key Features

### For Sports Organizers
- **Easy Game Submission**: Submit games with just a few clicks
- **Automated Assignments**: No more manual referee coordination
- **Real-time Updates**: Track assignment status instantly
- **Integrated Payments**: Automatic payment processing through Stripe
- **Performance Reviews**: Rate referees after each game
- **Emergency Coverage**: Automatic backup referee system

### For Referees
- **Smart Matching**: Only get assigned games that match your skills and location
- **Flexible Availability**: Set your schedule once, update anytime
- **Quick Confirmations**: Accept/reject assignments with one click
- **Automated Payments**: Get paid within 48 hours of game completion
- **Performance Tracking**: Build your reputation score
- **Emergency Pool**: Opt-in for last-minute games at premium rates

### For Administrators
- **Complete Oversight**: Monitor all games, assignments, and users
- **Manual Override**: Intervene when needed
- **Comprehensive Reports**: Revenue, performance, and assignment analytics
- **User Management**: Add, edit, or deactivate users
- **System Health**: Real-time monitoring and alerts

## 🏗️ Technical Architecture

### Technology Stack

#### Backend
- **Framework**: Flask 3.1.0 (Python)
- **Database**: SQLite (development) / PostgreSQL (production-ready)
- **Authentication**: JWT tokens with bcrypt password hashing
- **Task Scheduling**: APScheduler for automated processes

#### Integrations
- **Payment Processing**: Stripe API
- **SMS Notifications**: Twilio
- **Email Service**: SendGrid
- **Background Checks**: Checkr
- **Geocoding**: Geopy with Haversine distance calculations

#### Frontend
- **UI**: Responsive HTML/CSS/JavaScript
- **API Communication**: RESTful JSON APIs
- **Real-time Updates**: Webhook handlers

### System Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│   Web Frontend  │────▶│   Flask API     │────▶│    Database     │
│                 │     │                 │     │                 │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
              ┌─────▼─────┐           ┌───────▼───────┐
              │           │           │               │
              │ Scheduler │           │  Integrations │
              │           │           │               │
              └───────────┘           └───────────────┘
                                            │
                         ┌──────────────────┼──────────────────┐
                         │                  │                  │
                    ┌────▼────┐      ┌─────▼─────┐     ┌──────▼──────┐
                    │ Stripe  │      │  Twilio   │     │  SendGrid   │
                    └─────────┘      └───────────┘     └─────────────┘
```

## 🚀 The Matching Algorithm

### Core Algorithm Logic

The matching algorithm is the heart of RefMatch, using a weighted scoring system:

```python
Final Score = (Reliability × 50%) + (Distance × 30%) + (Experience × 20%)
```

#### 1. Reliability Score (50% weight)
- Historical performance tracking
- `(completed_games - no_shows) / total_assignments`
- New referees start at 85%
- Bonuses for completion streaks
- Penalties for recent no-shows

#### 2. Distance Score (30% weight)
- Precise calculation using Haversine formula
- Scoring bands:
  - 0-10km: 100%
  - 10-20km: 80%
  - 20-30km: 60%
  - 30-40km: 40%
  - 40-50km: 20%
  - >50km: 0% (excluded)

#### 3. Experience Score (20% weight)
- Games completed in specific sport
- Certification level matching
- Recent activity bonus

### Special Features

#### Emergency Pool
- For games <24 hours away
- Modified weights: Emergency availability (40%), Reliability (25%), Distance (20%), Experience (15%)
- Surge pricing up to 1.5x normal rate
- Only available to opted-in referees

#### Load Balancing
- Prevents over-assignment to single referees
- Ensures fair distribution of games
- Considers weekly assignment limits

## 📁 Project Structure

```
ref-match/
├── app/                        # Main application directory
│   ├── models/                 # Database models
│   │   ├── user.py            # User model (referees, organizers, admins)
│   │   ├── game.py            # Game events
│   │   ├── assignment.py      # Referee-game assignments
│   │   ├── certification.py   # Referee certifications
│   │   ├── payment.py         # Financial transactions
│   │   └── review.py          # Post-game reviews
│   ├── routes/                 # API endpoints
│   │   ├── auth.py            # Authentication endpoints
│   │   ├── games.py           # Game management
│   │   ├── assignments.py     # Assignment handling
│   │   ├── users.py           # User management
│   │   └── admin.py           # Admin functions
│   ├── services/              # Business logic
│   │   ├── matching_service.py    # Core matching algorithm
│   │   ├── assignment_service.py  # Assignment workflow
│   │   ├── payment_service.py     # Payment processing
│   │   └── notification_service.py # SMS/Email handling
│   ├── integrations/          # External service wrappers
│   │   ├── stripe_client.py   # Stripe integration
│   │   ├── twilio_client.py   # SMS service
│   │   ├── sendgrid_client.py # Email service
│   │   └── checkr_client.py   # Background checks
│   ├── templates/             # HTML templates
│   │   ├── index.html         # Main application
│   │   └── admin_dashboard.html # Admin interface
│   └── utils/                 # Utility functions
│       ├── validators.py      # Input validation
│       ├── security.py        # JWT and encryption
│       └── distance.py        # Geolocation calculations
├── config/                    # Configuration
│   └── config.py             # App configuration
├── scripts/                   # Utility scripts
│   ├── seed_database.py      # Database seeding
│   └── run_assignment_cron.py # Cron job script
├── tests/                     # Test suite
│   ├── test_auth.py          # Authentication tests
│   ├── test_matching.py      # Algorithm tests
│   └── test_payment.py       # Payment tests
├── logs/                      # Application logs
├── requirements.txt           # Python dependencies
├── run.py                    # Application entry point
└── README.md                 # This file
```

## 🔧 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Virtual environment (recommended)
- API keys for Stripe, Twilio, SendGrid, and Checkr

### Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ref-match
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

5. **Initialize the database**
   ```bash
   python scripts/seed_database.py
   ```

6. **Run the application**
   ```bash
   python run.py
   ```

7. **Access the application**
   - Web Interface: http://localhost:5001
   - Admin Dashboard: http://localhost:5001/admin
   - API Documentation: http://localhost:5001/api

### Default Credentials (Development)
- **Admin**: admin@refmatch.com / Admin123!
- **Organizer**: organizer1@school.edu / Organizer123!
- **Referee**: referee1@email.com / Referee123!

## 🔄 Workflow Examples

### Game Submission to Completion

1. **Organizer submits game**
   - Sport: Basketball
   - Level: 7th Grade
   - Date: Next Tuesday, 4:00 PM
   - Location: Phoenix Middle School

2. **System processes (automatic)**
   - Validates game data
   - Calculates referee fee ($60 base)
   - Adds to assignment pool

3. **Assignment process runs** (hourly cron)
   - Finds 15 eligible referees
   - Scores each referee
   - Top scorer: John Doe (Score: 92/100)
     - Reliability: 95%
     - Distance: 8km
     - Experience: 45 games

4. **Notification sent**
   - SMS to John: "New assignment: Basketball at Phoenix MS..."
   - Email with full details

5. **Referee confirms** (within 24 hours)
   - Clicks confirmation link
   - Assignment locked

6. **Game day**
   - 2-hour reminder sent
   - Referee arrives and officiates
   - Marks game complete

7. **Post-game**
   - Organizer submits 5-star review
   - Payment processed ($60 to referee)
   - Reliability score updated

## 📊 API Reference

### Authentication
```
POST /api/auth/register    - Register new user
POST /api/auth/login       - Login user
GET  /api/auth/verify-email/<token> - Verify email
POST /api/auth/verify-phone - Verify phone with code
```

### Games
```
POST /api/games           - Create new game
GET  /api/games           - List games (filtered by role)
PUT  /api/games/:id       - Update game details
POST /api/games/:id/cancel - Cancel game
```

### Assignments
```
GET  /api/assignments/my-assignments - Get referee's assignments
POST /api/assignments/:id/confirm    - Confirm assignment
POST /api/assignments/:id/reject     - Reject assignment
POST /api/assignments/process        - Trigger assignment process (admin)
```

### Users
```
GET  /api/users/profile    - Get user profile
PUT  /api/users/profile    - Update profile
GET  /api/users/availability - Get availability
POST /api/users/availability - Update availability
POST /api/users/quiz/:sport/:level - Start certification quiz
```

### Admin
```
GET  /api/admin/dashboard  - Dashboard statistics
GET  /api/admin/reports/assignments - Assignment report
GET  /api/admin/reports/referees    - Referee performance
GET  /api/admin/reports/revenue     - Financial report
POST /api/admin/assignments/manual  - Manual assignment
```

## 🛡️ Security Measures

- **Password Security**: bcrypt hashing with salt
- **JWT Tokens**: Expire after 24 hours
- **API Rate Limiting**: 100 requests per minute per IP
- **Input Validation**: Comprehensive sanitization
- **HTTPS**: Required for production
- **PII Encryption**: Sensitive data encrypted at rest
- **Webhook Verification**: Signature validation for all webhooks

## 📈 Performance & Scaling

### Current Performance
- Assignment algorithm: <100ms for 100 referees
- API response time: <200ms average
- Database queries: Optimized with indexes

### Scaling Considerations
- **Database**: Migrate to PostgreSQL for production
- **Caching**: Redis for session management
- **Background Jobs**: Celery for async processing
- **Load Balancing**: Nginx for multiple workers
- **Monitoring**: Integration with DataDog or New Relic

## 🧪 Testing

### Running Tests
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_matching.py
```

### Test Coverage
- Unit tests for all services
- Integration tests for API endpoints
- Algorithm verification tests
- Payment flow testing

## 🚢 Deployment

### Production Checklist
- [ ] Update environment variables
- [ ] Switch to PostgreSQL
- [ ] Enable HTTPS
- [ ] Set up monitoring
- [ ] Configure backup strategy
- [ ] Set up CI/CD pipeline
- [ ] Configure rate limiting
- [ ] Enable production logging

### Recommended Hosting
- **Application**: AWS EC2 or Heroku
- **Database**: AWS RDS or Heroku Postgres
- **File Storage**: AWS S3
- **Monitoring**: DataDog or New Relic
- **CI/CD**: GitHub Actions or CircleCI

## 📝 License & Legal

Copyright 2024 RefMatch. All rights reserved.

This software is proprietary and confidential. Unauthorized copying, modification, distribution, or use of this software, via any medium, is strictly prohibited.

## 🤝 Contributing

This is a private repository. For contribution guidelines, please contact the development team.

## 📞 Support

- **Technical Issues**: tech@refmatch.com
- **Business Inquiries**: info@refmatch.com
- **Emergency Support**: (555) 123-4567

---

*Built with ❤️ for the Phoenix middle school sports community*