from datetime import datetime, timezone, date
from zoneinfo import ZoneInfo
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.models.models import Queue, QueueToken, TokenStatus, Service, User, Status, Organization
from app.services.notification_service import create_notification

from sqlalchemy.dialects.postgresql import insert as pg_insert

async def get_or_create_queue(db, service_id, qdate=None):
    if qdate is None:
        row=await db.execute(select(Service, Organization.timezone).join(Organization, Organization.id==Service.organization_id).where(Service.id==service_id))
        pair=row.first()
        tz_name=pair[1] if pair else "UTC"
        try: tz=ZoneInfo(tz_name)
        except Exception: tz=timezone.utc
        qdate=datetime.now(tz).date()
    # Atomic insert if not exists
    stmt = (
        pg_insert(Queue)
        .values(service_id=service_id, queue_date=qdate, status=Status.ACTIVE, last_token_number=0)
        .on_conflict_do_nothing(index_elements=["service_id", "queue_date"])
    )
    await db.execute(stmt)
    q=await db.scalar(select(Queue).where(Queue.service_id==service_id,Queue.queue_date==qdate))
    return q

async def join_queue(db:AsyncSession,service_id,user:User):
    service=await db.scalar(select(Service).where(Service.id==service_id,Service.status==Status.ACTIVE).with_for_update())
    if not service: raise HTTPException(404,"Service not found")
    q=await get_or_create_queue(db,service_id)
    q=await db.scalar(select(Queue).where(Queue.id==q.id).with_for_update())
    existing=await db.scalar(select(QueueToken.id).where(QueueToken.queue_id==q.id,QueueToken.user_id==user.id,QueueToken.status.in_([TokenStatus.WAITING,TokenStatus.CALLED,TokenStatus.SERVING])))
    if existing: raise HTTPException(409,"You already have an active token for this queue")
    waiting=await db.scalar(select(func.count()).select_from(QueueToken).where(QueueToken.queue_id==q.id,QueueToken.status.in_([TokenStatus.WAITING,TokenStatus.CALLED,TokenStatus.SERVING]))) or 0
    if waiting>=service.queue_capacity: raise HTTPException(409,"The queue is currently full")
    q.last_token_number+=1
    code=f"{service.code.upper()}-{q.last_token_number:03d}"
    avg=service.average_service_time
    token=QueueToken(queue_id=q.id,user_id=user.id,token_number=q.last_token_number,token_code=code,estimated_wait=waiting*avg)
    db.add(token); await db.flush(); await create_notification(db,user.id,"QUEUE_JOINED","Queue joined",f"Your token is {code}.")
    return token, waiting+1

async def queue_snapshot(db,queue_id):
    q=await db.scalar(select(Queue).where(Queue.id==queue_id));
    if not q: raise HTTPException(404,"Queue not found")
    waiting=await db.scalar(select(func.count()).select_from(QueueToken).where(QueueToken.queue_id==queue_id,QueueToken.status==TokenStatus.WAITING)) or 0
    return q,waiting

async def call_next(db:AsyncSession,queue_id):
    q=await db.scalar(select(Queue).where(Queue.id==queue_id).with_for_update())
    if not q: raise HTTPException(404,"Queue not found")
    token=await db.scalar(select(QueueToken).where(QueueToken.queue_id==queue_id,QueueToken.status==TokenStatus.WAITING).order_by(QueueToken.joined_at).with_for_update(skip_locked=True))
    if not token: raise HTTPException(404,"No waiting customers")
    now=datetime.now(timezone.utc); token.status=TokenStatus.CALLED; token.called_at=now; q.current_token=token.token_code
    await create_notification(db,token.user_id,"TOKEN_CALLED","Your token was called",f"Please proceed for {token.token_code}.")
    return token

async def transition(db,token_id,new_status):
    token=await db.scalar(select(QueueToken).where(QueueToken.id==token_id).with_for_update())
    if not token: raise HTTPException(404,"Token not found")
    allowed={TokenStatus.CALLED:{TokenStatus.SERVING,TokenStatus.SKIPPED},TokenStatus.SERVING:{TokenStatus.COMPLETED},TokenStatus.WAITING:{TokenStatus.SKIPPED,TokenStatus.CANCELLED}} 
    if new_status not in allowed.get(token.status,set()): raise HTTPException(409,f"Cannot move {token.status} to {new_status}")
    token.status=new_status; now=datetime.now(timezone.utc)
    q=await db.scalar(select(Queue).where(Queue.id==token.queue_id).with_for_update())
    if new_status==TokenStatus.SERVING: token.service_started_at=now
    if new_status==TokenStatus.COMPLETED:
        token.completed_at=now
        if q and q.current_token==token.token_code: q.current_token=None
    if new_status==TokenStatus.SKIPPED and q and q.current_token==token.token_code:
        q.current_token=None
    if new_status in {TokenStatus.COMPLETED,TokenStatus.SKIPPED}:
        title="Service completed" if new_status==TokenStatus.COMPLETED else "Queue update"
        await create_notification(db,token.user_id,"SERVICE_COMPLETED",title,f"Token {token.token_code} is {new_status.value.lower()}.")
    return token
