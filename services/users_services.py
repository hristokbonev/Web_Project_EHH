from common.exceptions import NotFoundException
from services import replies_services
from data.database import read_query
from data.models.vote import Vote


def has_voted(user_id: int, reply_id: int) -> Vote:

    """
    Checks if a user has voted on a specific reply.
    
    Args:
        user_id (int): The ID of the user.
        reply_id (int): The ID of the reply.
    
    Returns:
        Vote: The vote object if the user has voted on the reply, otherwise None.
    
    Raises:
        NotFoundException: If the user does not exist.
        NotFoundException: If the reply does not exist.
    """

    if not exists(user_id):
        raise NotFoundException(detail='User does not exist')
    
    if not replies_services.exists(reply_id):
        raise NotFoundException(detail='Reply does not exist')
    
    vote = read_query('''SELECT user_id, reply_id, type FROM votes WHERE user_id = ? AND reply_id = ?''', (user_id, reply_id))

    return next((Vote.from_query_result(*row) for row in vote), None)


def exists(user_id: int) -> bool:
    
    """
    Check if a user exists in the database.
    
    Args:
        user_id (int): The ID of the user to check.
    
    Returns:
        bool: True if the user exists, False otherwise.
    """
    
    user = read_query('''SELECT user_id FROM users WHERE user_id = ?''', (user_id,))

    return bool(user)