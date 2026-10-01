from app.models.models import Notification
async def create_notification(db,user_id,type,title,message):
    n=Notification(user_id=user_id,type=type,title=title,message=message); db.add(n); return n
