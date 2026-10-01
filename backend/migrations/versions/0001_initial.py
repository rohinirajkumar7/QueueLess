"""initial schema"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="0001_initial"; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    bind = op.get_bind()
    role = postgresql.ENUM("CUSTOMER", "STAFF", "ORG_ADMIN", name="role", create_type=False)
    status = postgresql.ENUM("ACTIVE", "INACTIVE", name="status", create_type=False)
    token = postgresql.ENUM("WAITING", "CALLED", "SERVING", "COMPLETED", "SKIPPED", "CANCELLED", name="tokenstatus", create_type=False)
    appt = postgresql.ENUM("BOOKED", "CONFIRMED", "CHECKED_IN", "COMPLETED", "CANCELLED", "NO_SHOW", name="appointmentstatus", create_type=False)
    notif = postgresql.ENUM("PENDING", "SENT", "READ", "FAILED", name="notificationstatus", create_type=False)
    for values, name in [
        (["CUSTOMER", "STAFF", "ORG_ADMIN"], "role"),
        (["ACTIVE", "INACTIVE"], "status"),
        (["WAITING", "CALLED", "SERVING", "COMPLETED", "SKIPPED", "CANCELLED"], "tokenstatus"),
        (["BOOKED", "CONFIRMED", "CHECKED_IN", "COMPLETED", "CANCELLED", "NO_SHOW"], "appointmentstatus"),
        (["PENDING", "SENT", "READ", "FAILED"], "notificationstatus"),
    ]:
        postgresql.ENUM(*values, name=name, create_type=True).create(bind, checkfirst=True)
    uid=sa.Uuid(); now=sa.DateTime(timezone=True)
    op.create_table("organizations",sa.Column("id",uid,primary_key=True),sa.Column("name",sa.String(160),nullable=False),sa.Column("description",sa.Text),sa.Column("address",sa.String(300)),sa.Column("timezone",sa.String(64),nullable=False),sa.Column("status",status,nullable=False),sa.Column("created_at",now),sa.Column("updated_at",now))
    op.create_table("users",sa.Column("id",uid,primary_key=True),sa.Column("name",sa.String(120),nullable=False),sa.Column("email",sa.String(255),unique=True,nullable=False),sa.Column("password_hash",sa.Text,nullable=False),sa.Column("role",role,nullable=False),sa.Column("org_id",uid,sa.ForeignKey("organizations.id",ondelete="SET NULL")),sa.Column("created_at",now),sa.Column("updated_at",now)); op.create_index("ix_users_email","users",["email"])
    op.create_table("services",sa.Column("id",uid,primary_key=True),sa.Column("organization_id",uid,sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(120),nullable=False),sa.Column("code",sa.String(8),nullable=False),sa.Column("description",sa.Text),sa.Column("average_service_time",sa.Integer,nullable=False),sa.Column("queue_capacity",sa.Integer,nullable=False),sa.Column("status",status,nullable=False),sa.Column("operating_hours",sa.JSON),sa.Column("created_at",now),sa.Column("updated_at",now)); op.create_index("ix_services_organization_id","services",["organization_id"])
    op.create_table("staff_services",sa.Column("id",uid,primary_key=True),sa.Column("staff_id",uid,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("service_id",uid,sa.ForeignKey("services.id",ondelete="CASCADE"),nullable=False),sa.Column("created_at",now),sa.UniqueConstraint("staff_id","service_id"))
    op.create_table("queues",sa.Column("id",uid,primary_key=True),sa.Column("service_id",uid,sa.ForeignKey("services.id",ondelete="CASCADE"),nullable=False),sa.Column("queue_date",sa.Date,nullable=False),sa.Column("status",status,nullable=False),sa.Column("current_token",sa.String(30)),sa.Column("last_token_number",sa.Integer,nullable=False),sa.Column("created_at",now),sa.Column("updated_at",now),sa.UniqueConstraint("service_id","queue_date"))
    op.create_table("queue_tokens",sa.Column("id",uid,primary_key=True),sa.Column("queue_id",uid,sa.ForeignKey("queues.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",uid,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("token_number",sa.Integer,nullable=False),sa.Column("token_code",sa.String(30),nullable=False),sa.Column("status",token,nullable=False),sa.Column("joined_at",now),sa.Column("called_at",now),sa.Column("service_started_at",now),sa.Column("completed_at",now),sa.Column("estimated_wait",sa.Integer,nullable=False),sa.UniqueConstraint("queue_id","token_number")); op.create_index("ix_queue_status_joined","queue_tokens",["queue_id","status","joined_at"]); op.create_index("ix_queue_tokens_queue_id","queue_tokens",["queue_id"]); op.create_index("ix_queue_tokens_status","queue_tokens",["status"]); op.create_index("ix_queue_tokens_user_id","queue_tokens",["user_id"])
    op.create_table("appointments",sa.Column("id",uid,primary_key=True),sa.Column("service_id",uid,sa.ForeignKey("services.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",uid,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("appointment_date",sa.Date,nullable=False),sa.Column("start_time",sa.Time,nullable=False),sa.Column("end_time",sa.Time,nullable=False),sa.Column("status",appt,nullable=False),sa.Column("created_at",now),sa.Column("updated_at",now)); op.create_index("ix_appointments_service_id","appointments",["service_id"]); op.create_index("ix_appointments_appointment_date","appointments",["appointment_date"])
    op.create_table("notifications",sa.Column("id",uid,primary_key=True),sa.Column("user_id",uid,sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("type",sa.String(60),nullable=False),sa.Column("title",sa.String(160),nullable=False),sa.Column("message",sa.Text,nullable=False),sa.Column("status",notif,nullable=False),sa.Column("created_at",now),sa.Column("read_at",now)); op.create_index("ix_notifications_user_id","notifications",["user_id"])
    op.create_table("audit_logs",sa.Column("id",uid,primary_key=True),sa.Column("organization_id",uid,sa.ForeignKey("organizations.id",ondelete="SET NULL")),sa.Column("user_id",uid,sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("action",sa.String(80),nullable=False),sa.Column("entity_type",sa.String(80),nullable=False),sa.Column("entity_id",sa.String(80),nullable=False),sa.Column("metadata",sa.JSON),sa.Column("created_at",now))

def downgrade():
    for t in ["audit_logs","notifications","appointments","queue_tokens","queues","staff_services","services","users","organizations"]: op.drop_table(t)
    for n in ["notificationstatus","appointmentstatus","tokenstatus","status","role"]: sa.Enum(name=n).drop(op.get_bind(),checkfirst=True)
