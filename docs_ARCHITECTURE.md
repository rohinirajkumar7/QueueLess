# Architecture Notes

## Data ownership
PostgreSQL owns permanent users, organizations, services, queues, tokens, appointments, notifications and audit records.

## Concurrency
Queue mutations run in database transactions. The queue row serializes token-number allocation; `SELECT ... FOR UPDATE SKIP LOCKED` prevents two staff workers from taking the same waiting token.

## Scaling
API instances are stateless. Shared PostgreSQL and Redis can be used behind a load balancer. WebSocket fan-out can be upgraded to Redis Pub/Sub when multiple API instances need shared connection coordination.
