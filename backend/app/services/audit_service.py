from app.models.models import AuditLog
async def audit(db,organization_id,user_id,action,entity_type,entity_id,metadata=None):
    db.add(AuditLog(organization_id=organization_id,user_id=user_id,action=action,entity_type=entity_type,entity_id=str(entity_id),metadata_=metadata or {}))
