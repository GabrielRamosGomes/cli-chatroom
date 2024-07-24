from sqlalchemy import create_engine, Column, String, Table, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.exc import IntegrityError
import hashlib, uuid

Base = declarative_base()

user_room_table = Table('user_room', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('room_id', Integer, ForeignKey('rooms.id'))
)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # Add password field
    rooms = relationship('Room', secondary=user_room_table, back_populates='users')

    def set_password(self, password):
        salt = uuid.uuid4().hex
        self.password = hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt

    def check_password(self, password):
        password_hash, salt = self.password.split(':')
        return password_hash == hashlib.sha256(salt.encode() + password.encode()).hexdigest()
        
class Room(Base):
    __tablename__ = 'rooms'
    id = Column(Integer, primary_key=True, autoincrement=True)
    room = Column(String, unique=True, nullable=False)
    users = relationship('User', secondary=user_room_table, back_populates='rooms')
    messages = relationship('Message', back_populates='room')

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    room_id = Column(Integer, ForeignKey('rooms.id'))
    username = Column(String, nullable=False)
    message = Column(String, nullable=False)
    room = relationship('Room', back_populates='messages')

class PrivateMessage(Base):
    __tablename__ = 'private_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    to_user = Column(String, nullable=False)
    from_user = Column(String, nullable=False)
    message = Column(String, nullable=False)

class Database:
    def __init__(self):
        self.engine = create_engine('sqlite:///chat.db')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_session(self):
        return self.Session()

db = Database()
