import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config.config import Config
from app.models.base import Base

# Create database engine
engine = create_engine(
    Config.DATABASE_URL,
    connect_args={'check_same_thread': False} if 'sqlite' in Config.DATABASE_URL else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create scoped session for thread safety
db_session = scoped_session(SessionLocal)


def init_db():
    """Initialize database, create all tables"""
    import app.models  # Import all models
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all tables"""
    Base.metadata.drop_all(bind=engine)


@contextmanager
def get_db():
    """Provide a transactional scope for database operations"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class DatabaseManager:
    """Database manager for CRUD operations"""
    
    def __init__(self, model_class):
        self.model_class = model_class
    
    def create(self, **kwargs):
        """Create a new record"""
        with get_db() as db:
            instance = self.model_class(**kwargs)
            db.add(instance)
            db.flush()
            db.refresh(instance)
            return instance
    
    def get(self, id):
        """Get record by ID"""
        with get_db() as db:
            return db.query(self.model_class).filter(self.model_class.id == id).first()
    
    def get_by(self, **kwargs):
        """Get record by field values"""
        with get_db() as db:
            query = db.query(self.model_class)
            for key, value in kwargs.items():
                query = query.filter(getattr(self.model_class, key) == value)
            return query.first()
    
    def filter(self, **kwargs):
        """Filter records by field values"""
        with get_db() as db:
            query = db.query(self.model_class)
            for key, value in kwargs.items():
                query = query.filter(getattr(self.model_class, key) == value)
            return query.all()
    
    def update(self, id, **kwargs):
        """Update a record"""
        with get_db() as db:
            instance = db.query(self.model_class).filter(self.model_class.id == id).first()
            if instance:
                for key, value in kwargs.items():
                    setattr(instance, key, value)
                db.flush()
                db.refresh(instance)
            return instance
    
    def delete(self, id):
        """Delete a record"""
        with get_db() as db:
            instance = db.query(self.model_class).filter(self.model_class.id == id).first()
            if instance:
                db.delete(instance)
                return True
            return False
    
    def count(self, **kwargs):
        """Count records"""
        with get_db() as db:
            query = db.query(self.model_class)
            for key, value in kwargs.items():
                query = query.filter(getattr(self.model_class, key) == value)
            return query.count()
    
    def exists(self, **kwargs):
        """Check if record exists"""
        return self.count(**kwargs) > 0