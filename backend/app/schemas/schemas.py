from datetime import date, time
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from app.models.models import Role, Status, TokenStatus, AppointmentStatus
class ORM(BaseModel): model_config=ConfigDict(from_attributes=True)
class RegisterIn(BaseModel): name:str=Field(min_length=2,max_length=120); email:EmailStr; password:str=Field(min_length=8,max_length=128); role:Role=Role.CUSTOMER
class LoginIn(BaseModel): email:EmailStr; password:str; role:Role|None=None
class ForgotPasswordIn(BaseModel): email:EmailStr
class ResetPasswordIn(BaseModel): token:str=Field(min_length=20,max_length=300); password:str=Field(min_length=8,max_length=128)
class TokenOut(BaseModel): access_token:str; refresh_token:str; token_type:str="bearer"
class UserOut(ORM): id:UUID; name:str; email:EmailStr; role:Role; org_id:UUID|None=None
class OrgCreate(BaseModel): name:str; description:str|None=None; address:str|None=None; timezone:str="UTC"
class OrgOut(ORM): id:UUID; name:str; description:str|None; address:str|None; timezone:str; status:Status
class ServiceCreate(BaseModel): name:str; code:str=Field(min_length=1,max_length=8); description:str|None=None; average_service_time:int=Field(default=10,ge=1,le=240); queue_capacity:int=Field(default=100,ge=1,le=10000); operating_hours:dict={}
class ServiceOut(ORM): id:UUID; organization_id:UUID; name:str; code:str; description:str|None; average_service_time:int; queue_capacity:int; status:Status
class QueueOut(BaseModel): id:UUID; service_id:UUID; queue_date:date; status:Status; current_token:str|None; people_waiting:int; last_token_number:int
class JoinOut(BaseModel): id:UUID; queue_id:UUID; token_code:str; position:int; estimated_wait:int; status:TokenStatus; wait_minutes:int|None=None; service_minutes:int|None=None
class TokenOutDetail(ORM): id:UUID; queue_id:UUID; user_id:UUID; token_number:int; token_code:str; status:TokenStatus; estimated_wait:int; joined_at:object; called_at:object|None; service_started_at:object|None; completed_at:object|None
class AppointmentCreate(BaseModel): service_id:UUID; appointment_date:date; start_time:time; end_time:time
class AppointmentOut(ORM): id:UUID; service_id:UUID; user_id:UUID; appointment_date:date; start_time:time; end_time:time; status:AppointmentStatus; service_name:str|None=None
class NotificationOut(ORM): id:UUID; type:str; title:str; message:str; status:str; created_at:object; read_at:object|None
class AnalyticsOut(BaseModel): total_customers:int; average_wait:float; average_service_time:float; completed_tokens:int; skipped_tokens:int; cancelled_appointments:int; peak_hour:int|None; queue_length:int

class OrganizationRegisterIn(BaseModel):
    organization_name:str=Field(min_length=2,max_length=160)
    description:str|None=None
    address:str|None=None
    timezone:str="UTC"
    name:str=Field(min_length=2,max_length=120)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
class StaffCreate(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
    service_ids:list[UUID]=[]
