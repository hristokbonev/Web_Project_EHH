from __future__ import annotations
from fastapi import Form, HTTPException
from pydantic import ValidationError
from data.models.reply import Reply
from data.models.topic import TopicResponse, TopicCreate
from data.database import read_query, update_query, insert_query
import logging

from data.models.user import User

logging.basicConfig(level=logging.INFO)


DEFAULT_BEST_REPLY_NONE = None


#WORKS
def exists(topic_id: int):
    """
    Checks if a topic with the provided ID exists.
    """
    return any(read_query('''SELECT 1 FROM topics WHERE topic_id=?''', (id,)))


#WORKS
def fetch_all_topics(
        search: str = None,
        username: str = None,
        category: str = None,
        status: str = None,
        sort: str = None,
        sort_by: str = None,
        page: int = 1,
        per_page: int = 10,
        current_user: User = None
    ):
    """
    Fetches all topics based on the provided filters and sorting options.
    -search: Search by topic title
    -username: Filter by username of the topic creator
    -category: Filter by category name
    -status: Filter by topic status: 'open' or 'closed'
    -sort: Sort order: 'asc' or 'desc' (use with sort_by)
    -sort_by: Field to sort by, e.g., 'topic_id', 'user_id'
    """
    params, filters = [], []
    sql = (
        '''SELECT DISTINCT t.topic_id, t.title, t.user_id, u.username, t.is_locked, 
           t.best_reply_id, t.category_id, c.name
        FROM topics t
        JOIN users u ON t.user_id = u.user_id
        JOIN categories c ON t.category_id = c.category_id
        LEFT JOIN users_categories_permissions ucp ON ucp.category_id = c.category_id AND ucp.user_id = ?'''
    )

    if not current_user:
        return None
    
    params.append(current_user.id)

    if not current_user.is_admin:
        filters.append('(c.is_private = 0 or (c.is_private = 1 AND ucp.write_access > 0))')

    if search:
        filters.append('t.title LIKE ?')
        params.append(f'%{search}%')
    if username:
        filters.append('u.username = ?')
        params.append(username)
    if category:
        filters.append('c.name = ?')
        params.append(category)
    if status:
        if status in ['open', 'closed']:
            filters.append('t.is_locked = ?')
            params.append(1 if status == 'closed' else 0)

    sql += (" WHERE " + " AND ".join(filters) if filters else "")

    # Get total count for pagination
    count_sql = f"SELECT COUNT(*) FROM ({sql}) as count_table"
    total_count = read_query(count_sql, tuple(params))[0][0]
    total_pages = (total_count + per_page - 1) // per_page

    # Add sorting and pagination
    if sort_by and sort_by in ['topic_id', 'user_id', 'category_id', 'status']:
        order = "ASC" if sort == "asc" else "DESC"
        sql += f' ORDER BY {sort_by} {order}'
    
    sql += ' LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])

    data = read_query(sql, tuple(params))
    topics = [TopicResponse.from_query(*row) for row in data]

    return {
        'topics': topics,
        'total_pages': total_pages,
        'current_page': page,
        'total_count': total_count
    }


#WORKS
def fetch_topic_by_id(topic_id: int) -> TopicResponse | None:
    '''
    Fetches a topic by its ID and returns a TopicResponse object with all the replies.
    '''
    data = read_query(
        '''SELECT t.topic_id, t.title, t.user_id, u.username, t.is_locked, t.best_reply_id, t.category_id, c.name
         FROM topics t
         JOIN users u ON t.user_id = u.user_id
         JOIN categories c ON t.category_id = c.category_id 
         WHERE t.topic_id = ?''', (topic_id,)
    )

    return next((TopicResponse.from_query(*row) for row in data), None)


#WORKS
def create_new_topic(topic: TopicCreate, user_id: int):
    """
    Creates a new topic with the provided data.
    Parameters:
    - topic: TopicCreate - the data for the new topic
    - user_id: int - the ID of the user creating the topic
    Returns:
    - dict: status and message
    New topic and first reply are created successfully.
    """
    existing_category = read_query('''SELECT 1 FROM categories WHERE category_id = ? LIMIT 1''', (topic.category_id,))
    if not existing_category:
        raise HTTPException(status_code=404, detail="Category does not exist")

    try:        
        topic_id = insert_query(
            '''INSERT INTO topics(title, user_id, is_locked, best_reply_id, category_id) 
               VALUES(?,?,?,?,?)''',
            (topic.title, user_id, 0, None, topic.category_id)
        )
        
        if not topic_id:
            raise HTTPException(status_code=500, detail="Topic creation failed")

        reply_id = insert_query(
            '''INSERT INTO replies(text, user_id, topic_id, edited) 
               VALUES(?,?,?,?)''',
            (topic.text, user_id, topic_id, 0)
        )

        if not reply_id:
            raise HTTPException(status_code=500, detail="First reply creation failed")

        return {
            "topic_id": topic_id,
            "status": "success",
            "message": "Topic and first reply created successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during topic creation: {str(e)}")
    

#WORKS
def update_topic_title(topic_id: int, new_title: str):
    """
    Updates the title of a topic.
    """
    update_query('''UPDATE topics SET title = ? WHERE topic_id = ?''', (new_title, topic_id))

    return f"Topic {topic_id} title updated to {new_title}"


#WORKS
def update_best_reply_for_topic(topic_id: int, reply_id: int):
    """
    Updates the best reply for a topic.
    """
    update_query('''UPDATE topics SET best_reply_id = ? WHERE topic_id = ?''', (reply_id, topic_id))

    return f"Best reply for topic {topic_id} updated to {reply_id}"


#WORKS
def fetch_replies_for_topic(topic_id: int):
    """
    Fetches all replies for a specific topic.
    """
    data = read_query(
        '''SELECT r.reply_id, r.text, r.user_id, r.topic_id, r.created, r.edited
        FROM replies r
        WHERE r.topic_id = ?''',
        (topic_id,)
    )
    
    return [Reply.from_query_result(*row) for row in data]
# korekcii gore.

#WORKS
def check_topic_access_permissions(user_id: int, topic_id: input):
    """
    Checks if the user has the necessary permissions to edit a topic.
    """
    existing_topic = fetch_topic_by_id(topic_id)
    if not existing_topic:
        return False, f"Topic #ID:{topic_id} does not exist!"

    if existing_topic.user_id != user_id:
        return False, 'You are not allowed to edit this topic.'

    if existing_topic.status == "closed":
        return False, 'This topic is locked.'

    return True, 'OK'


#WORKS
def lock_or_unlock_topic(topic_id: int, lock_status: bool):
    """
    Locks or unlocks a topic based on the provided status.
    """
    update_query('''UPDATE topics SET is_locked = ? WHERE topic_id = ?''',
                 (lock_status, topic_id))


#WORKS
def verify_topic_owner(user_id: int, topic_id: int):
    """
    Verifies if the user is the owner of the topic.
    """
    data = read_query('''SELECT * FROM topics WHERE topic_id = ? AND user_id = ?''',
                      (topic_id, user_id))

    if not data:
        return False
    return True


#WORKS
def count_all_topics():
    """
    Counts the total number of topics.
    """
    data = read_query('''SELECT COUNT(*) FROM topics''')
    return data[0][0] if data else 0


#WORKS
def delete_topic(topic_id: int):
    """
    Deletes a topic by its ID.
    First removes best_reply reference, then deletes replies, then the topic.
    """
    try:
        update_query(
            '''UPDATE topics SET best_reply_id = NULL WHERE topic_id = ?''', 
            (topic_id,)
        )

        update_query(
            '''DELETE FROM replies WHERE topic_id = ?''', 
            (topic_id,)
        )

        update_query(
            '''DELETE FROM topics WHERE topic_id = ?''', 
            (topic_id,)
        )

        return f"Topic {topic_id} deleted successfully"
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


#WORKS
def topic_create_form(title: str = Form(...), text: str = Form(...), category_id: int = Form(...)) -> TopicCreate:
    try:
        return TopicCreate(title=title, text=text, category_id=category_id)
    except ValidationError as exc:
        error_messages = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in exc.errors()])
        raise HTTPException(status_code=400, detail=f"{error_messages}")


def remove_best_reply(reply_id: int):

    update_query('''UPDATE topics SET best_reply_id = NULL WHERE best_reply_id = ?''', (reply_id,))