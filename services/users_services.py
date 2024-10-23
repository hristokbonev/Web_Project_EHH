from datetime import timedelta, datetime
from typing import Optional
from fastapi import Depends
from jose import JWTError, jwt
from common.exceptions import ForbiddenException, NotFoundException
from common.responses import Forbidden, Unauthorized
from config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from data.models.user import User, UserResponse
from services import replies_services
from data.database import insert_query, read_query
from data.models.vote import Vote
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer


pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/users/login', auto_error=False)
token_blacklist = set()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
    

def create_user(user: User) -> int:
    return insert_query(
        'INSERT INTO users (username, password, email, first_name, last_name) VALUES (?, ?, ?, ?, ?)',
        (user.username, user.password, user.email, user.first_name, user.last_name)
    )


def login_user(username: str, password: str) -> Optional[UserResponse]:
    user_data = read_query('SELECT * FROM users WHERE username=?', (username,))
    
    if not user_data or not verify_password(password, user_data[0][2]):
        return None
    return UserResponse.from_query_result(user_data[0])


def get_user(username: str) -> UserResponse:
    data = read_query( 'SELECT * FROM users WHERE username=?',(username,))
    if not data:
        return None
    return UserResponse.from_query_result(data[0])

def get_admin_user(username: str) -> User:
    data = read_query('SELECT * FROM users WHERE username=? AND is_admin=1', (username,))
    if not data:
        return None
    return User.from_query_result(*data[0])
    

def get_user_by_id(user_id: int) -> User:
    data = read_query('SELECT * FROM users WHERE user_id=?', (user_id,))
    if not data:
        return None
    return User.from_query_result(*data[0])


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        if username is None:
            raise username
        is_admin: bool = payload.get('is_admin')
        if is_admin is None:
            raise is_admin
    except JWTError:
        raise Unauthorized("Could not validate credentials")
    return get_user(username)

def get_current_admin_user(user_id: int = Depends(get_current_user)):
    data = read_query('SELECT * FROM users WHERE user_id=? AND is_admin=1', (user_id,))
    if not data:
        raise ForbiddenException('You do not have permission to access this')
    return User.from_query_result(*data[0])

def get_users():
    data = read_query('SELECT * FROM users')
    return [UserResponse.from_query_result(row) for row in data]
    

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({'exp': expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str):
    if token in token_blacklist:
        raise ForbiddenException("Token has been revoked")
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get('sub')
        is_admin = payload.get('is_admin')
        if username is None:
            raise username
        if is_admin is None:
            raise is_admin
    except JWTError:
            raise Unauthorized("Could not validate credentials")


def authenticate_user(username: str, password: str):
    user = login_user(username, password)
    if not user or not verify_password(password, user.password):
        return None
    return user



def has_voted(user_id: int, reply_id: int) -> Vote | None:
    
    """
    Checks if a user has voted on a specific reply.

    Args:
        user_id (int): The ID of the user.
        reply_id (int): The ID of the reply.

    Returns:
        Vote | None: A Vote object if the user has voted on the reply, otherwise None.

    Raises:
        NotFoundException: If the user or the reply does not exist.
    """

    if not exists(user_id):
        raise NotFoundException(detail='User does not exist')
    
    if not replies_services.exists(reply_id):
        raise NotFoundException(detail='Reply does not exist')
    
    vote = read_query('''SELECT user_id, reply_id, type FROM votes WHERE user_id = ? AND reply_id = ?''', (user_id, reply_id))

    return next((Vote.from_query_result(*row) for row in vote), None)


def exists(user_id: int) -> bool:
    
    user = read_query('''SELECT user_id FROM users WHERE user_id = ?''', (user_id,))

    return bool(user)