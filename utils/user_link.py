from typing import Optional
from utils.user_storage import UserStorage

user_storage = UserStorage()

def get_user_link(user_id: int, custom_text: Optional[str] = None) -> str:
    user_info = user_storage.get_user_info(user_id)
    
    if custom_text:
        link_text = custom_text
    elif user_info:
        if user_info.get('first_name'):
            link_text = user_info['first_name']
            if user_info.get('last_name'):
                link_text += f" {user_info['last_name']}"
        else:
            link_text = f"ID: {user_id}"
    else:
        link_text = f"ID: {user_id}"
    
    # Ситуация если есть юзернейм и нет (спиздил у ириса)
    if user_info and user_info.get('username'):
        url = f"https://t.me/{user_info['username']}"
    else:
        url = f"tg://openmessage?user_id={user_id}"
    
    return f'<a href="{url}">{link_text}</a>'
