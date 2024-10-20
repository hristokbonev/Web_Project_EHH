from fastapi import HTTPException
from data.database import read_query, insert_query, update_query
from data.models.category import Category, CategoryResponse
from typing import List
from common.exceptions import ConflictException, NotFoundException, BadRequestException


def get_categories(category_id: int = None, name: str = None, 
                   sort_by: str = None, sort: str = None,
                   limit: int = 10, offset: int = 0) -> CategoryResponse | List[CategoryResponse] | None:
    
    """
    Retrieve categories from the database with optional filtering, sorting, and pagination.

    Args:
        category_id (int, optional): Filter by category ID. Defaults to None.
        name (str, optional): Filter by category name using a partial match. Defaults to None.
        sort_by (str, optional): Column name to sort the results by. Defaults to None.
        sort (str, optional): Sort order ('ASC' or 'DESC'). Defaults to None.
        limit (int, optional): Maximum number of results to return. Defaults to 10.
        offset (int, optional): Number of rows to skip before starting to return rows. Defaults to 0.

    Returns:
        CategoryResponse | List[CategoryResponse] | None: A single CategoryResponse if one result is found,
        a list of CategoryResponse objects if multiple results are found, or None if no results are found.
    """
   
    query = '''SELECT category_id, name FROM categories'''
    params = []

    if category_id:
        query += ''' WHERE category_id = ?'''
        params.append(category_id)

    if name:
        query += ''' AND name LIKE ?''' if category_id else ''' WHERE name LIKE ?'''
        params.append(f'%{name}%')

    if sort_by:
        query += f''' ORDER BY {sort_by}'''

    if sort:
        query += f" {sort.upper()}"

    query += ''' LIMIT ? OFFSET ?'''
    params.extend([limit, offset])

    categories = read_query(query, tuple(params))

    if len(categories) > 1: # Return a list of objects if more than one instance is found
        return [CategoryResponse.from_query_result(*obj) for obj in categories]
    
    else: # Otherwise return a single object
        return next((CategoryResponse.from_query_result(*row) for row in categories), None)
    

def create(category: Category) -> Category | None:

    """
    Create a new category in the database.
    
    Args:
        category (Category): The category object to be created. Must contain the name, is_locked, and is_private attributes.
    
    Returns:
        Category | None: The created category object with the generated ID, or None if the category could not be created.
    
    Raises:
        ConflictException: If a category with the same name already exists.
    """

    if exists(name=category.name):
        raise ConflictException(detail='Category with that name already exists')
    
    generated_id = insert_query('''INSERT INTO categories (name, is_locked, is_private) VALUES (?, ?, ?)''',
                                 (category.name, category.is_locked, category.is_private))

    category.id = generated_id

    return category if category else None
    

def exists(category_id: int = None, name: str = None) -> bool:
    
    category = None

    if category_id: # If an id is provided, check the database for the id
        category = read_query('''SELECT category_id FROM categories WHERE category_id = ?
                            LIMIT 1''', (category_id,))
    
    elif name: # Or if a name is provided, check the database for the name
        category = read_query('''SELECT category_id FROM categories WHERE name = ?
                            LIMIT 1''', (name,))
    
    return bool(category)


def delete(category_id: int, delete_topics: bool = False) ->  str | None:
    
    """
    Delete a category and optionally its associated topics and replies.
    
    Args:
        category_id (int): The ID of the category to be deleted.
        delete_topics (bool, optional): If True, deletes topics and replies associated with the category. Defaults to False.
    
    Returns:
        str | None: A message indicating what was deleted, or None if the category was not deleted.
    
    Raises:
        NotFoundException: If the category does not exist.
    """

    if not exists(category_id=category_id):
        raise NotFoundException(detail='Category does not exist')
    
    # Fist delete the category from users_categories_permission table
    update_query('''DELETE FROM users_categories_permissions WHERE category_id = ?''', (category_id,))

    topics = has_topics(category_id)

    delete_from_replies = None
    delete_from_topics = None
    
    if delete_topics == True and topics == True: # If delete topics was selected, check if any exist and then delete them

        delete_from_replies = update_query('''DELETE FROM replies
                        WHERE topic_id IN (SELECT t.topic_id 
                        FROM topics t 
                        WHERE t.category_id = ?)''', (category_id,))
        
        delete_from_topics = update_query('''DELETE FROM topics WHERE category_id = ?''', (category_id,))

    # Finally delete the category itself
    deleted = update_query('''DELETE FROM categories WHERE category_id = ?''', (category_id,))

    if not deleted:
        return None
    
    else:

        if delete_from_replies and delete_from_topics:
            return 'everything deleted' 
    
        return 'only category deleted'
    

def update_name(old_category: CategoryResponse, new_category: CategoryResponse) -> CategoryResponse | None:

    """
    Update the name of an existing category.
    
    Args:
        old_category (CategoryResponse): The current category details, including its name or ID.
        new_category (CategoryResponse): The new category details, including the new name.
    
    Returns:
        CategoryResponse | None: The updated category details if the update was successful, otherwise None.
    
    Raises:
        NotFoundException: If the old category does not exist.
        ConflictException: If a category with the new name already exists.
        BadRequestException: If the new category name is not provided.
    """

    if not (exists(name=old_category.name) or exists(category_id=old_category.id)):
        raise NotFoundException(detail='Category not found')
    
    if exists(name=new_category.name):
        raise ConflictException(detail='Category with such name already exists')
    
    if not new_category.name:
        raise BadRequestException(detail='New name has to be given')

    query = '''UPDATE categories SET name = ?'''
    params = [new_category.name]

    if old_category.id: # Check by id if provided

        query +=  ''' WHERE category_id = ?'''
        params.append(old_category.id)
    
    elif old_category.name: # Otherwise check by name

        query += ''' WHERE name = ?'''
        params.append(old_category.name)

    updated = update_query(query, tuple(params))

    merged = CategoryResponse(id=get_id(new_category.name), name=new_category.name or old_category.name)

    return merged if (merged and updated) else None


def has_topics(category_id: int) -> bool:

    topics = read_query('''SELECT topic_id FROM topics WHERE category_id = ? LIMIT 1''', (category_id,))

    return bool(topics)


def get_name(category_id: int) -> str:

    name = read_query('''SELECT name FROM categories WHERE category_id = ? LIMIT 1''', (category_id,))

    return name[0][0]


def get_id(name: str) -> int:

    id = read_query('''SELECT category_id FROM categories WHERE name = ? LIMIT 1''', (name,))

    return id[0][0]


def lock_unlock(category_id: int) -> str | None:

    """
    Lock or unlock a category based on its current state.
    
    Args:
        category_id (int): The ID of the category to lock or unlock.
    
    Returns:
        str | None: A string indicating the result of the operation:
            - 'unlocked' if the category was successfully unlocked.
            - 'unlock failed' if the unlock operation failed.
            - 'locked' if the category was successfully locked.
            - 'lock failed' if the lock operation failed.
            - None if the category does not exist.
    Raises:
        NotFoundException: If the category with the given ID does not exist.
    """

    if not exists(category_id):
        raise NotFoundException(detail='Category not found')

    if is_locked(category_id): # If the category is already locked, unlock it

        unlock_category = update_query('''UPDATE categories SET is_locked = ? WHERE category_id = ?''', (False, category_id))

        if not unlock_category:
            return 'unlock failed'

        return 'unlocked'

    else: # Otherwise, lock it
        lock_category = update_query('''UPDATE categories SET is_locked = ? WHERE category_id = ?''', (True, category_id))

        if not lock_category:
            return 'lock failed'
        
        return 'locked'


def is_locked(category_id: int) -> bool:

    locked_row = read_query('''SELECT is_locked FROM categories WHERE category_id = ?''', (category_id,))

    locked_bool = locked_row[0][0]

    return locked_bool


def is_private(category_id: int) -> bool:

    private_row = read_query('''SELECT is_private FROM categories WHERE category_id = ?''', (category_id,))

    private_bool = private_row[0][0]

    return private_bool


def privatise_unprivatise(category_id: int) -> str | None:

    """
    Toggles the privacy status of a category based on its current state.

    Args:
        category_id (int): The ID of the category to be toggled.
    
    Returns:
        str | None: A message indicating the result of the operation, or None if the category does not exist.
    
    Raises:
        NotFoundException: If the category with the given ID does not exist.
    """

    if not exists(category_id):
        raise NotFoundException(detail='Category not found')

    if is_private(category_id): # If the category is already private, make it public
            
            make_public = update_query('''UPDATE categories SET is_private = ? WHERE category_id = ?''', (False, category_id))
    
            if not make_public:
                return 'made public failed'
    
            return 'made public'
    
    else: # Otherwise, make it private
    
        make_private = update_query('''UPDATE categories SET is_private = ? WHERE category_id = ?''', (True, category_id))
    
        if not make_private:
            return 'made private failed'
        
        return 'made private'