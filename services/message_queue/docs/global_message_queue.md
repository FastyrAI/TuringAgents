Global Message Queue - Architecture Decision Record
Project: AI Agent OS Framework
 Component: Global Message Queue
 Date Created: August 14, 2025
 Status: In Progress

Core Decision Points
1. Queue Technology & Infrastructure
1.1 Message broker selection: Redis Streams vs RabbitMQ vs Kafka vs AWS SQS vs custom implementation
Decision: RabbitMQ - native priority queues, built-in retry/DLQ, acknowledgments, proven reliability
1.2 Persistence strategy: In-memory with snapshots vs full persistence vs hybrid
Decision: Full persistence for all messages
All queues durable, all messages persistent (delivery_mode=2)
Skip publisher confirms for P0 (fire-and-forget for <10ms latency)
Use publisher confirms for P1-P3 (reliability over speed)
Minimal performance impact due to RabbitMQ's write batching
Required for audit trail and replay functionality
1.3 Deployment model: Single instance vs clustered vs distributed
Decision: [PENDING]
1.4 Failure recovery: How to handle queue failures without losing messages
Decision: [PENDING]
2. Message Schema & Types
2.1 Message format: Protocol buffers vs JSON vs MessagePack
Decision: JSON
Human readable for debugging
LLM-friendly for conflict resolution
Native PostgreSQL JSONB support for audit logs
Easy schema evolution
Size overhead acceptable for agent operations
2.2 Type taxonomy: What are ALL the message types? (tool_call, chat_completion, agent_communication, memory_save, context_retrieval, etc.)
Decision: Two categories of messages:

 Request Messages (8 types - go to org queue):


model_call - Invoke AI model (text/image/audio/video generation)
tool_call - Execute MCP tool/integration
agent_message - Agent-to-agent communication
memory_save - Store to knowledge graph
memory_retrieve - Query knowledge graph
memory_update - Modify knowledge graph
agent_spawn - Create new agent
agent_terminate - Kill agent
Response Messages (6 types - go to agent response queues):


result - Complete result for non-streaming operations
stream_chunk - Partial streaming response chunk
stream_complete - Indicates streaming finished
error - Operation failed with error details
progress - Progress update for long-running operations
acknowledgment - Confirms message received/started
Response Message Schema Example:

 {
  "request_id": "123",  // Links to original request
  "type": "stream_chunk",
  "chunk": "Response text...",
  "chunk_index": 0,
  "timestamp": "2025-08-14T10:00:00Z"
}


2.3 Metadata requirements: Timestamps, correlation IDs, parent/child relationships, priority levels
Decision: Complete metadata schema:
message_id - Unique identifier
goal_id - Always present (auto-generated for simple requests)
task_id - Always present (auto-generated for simple requests)
parent_message_id - For message chains/dependencies
created_by - Object with type (user/agent/system) and ID
org_id, user_id, agent_id - Routing and ownership
priority - 0-3 for P0-P3
created_at, expires_at - Timing
retry_count, max_retries - Error handling
version - Schema version
context - Session/environment data
metadata - Debugging information
2.4 Versioning strategy: How to handle schema evolution without breaking existing agents
Decision: Hybrid approach
Semantic versioning (major.minor.patch) in each message
Minor versions: Additive only, never remove fields
Major versions: Breaking changes allowed with migration path
Support current major + previous major version (2 versions)
Auto-migration for older message formats
Example Implementation:
 class MessageProcessor:    def process(self, msg):        version = msg.get('version', '1.0.0')        major = version.split('.')[0]                # Handle major versions        if major == "1":            return self.process_v1(msg)        elif major == "2":            # Auto-migrate v1 to v2 format            migrated = self.migrate_v1_to_v2(msg)            return self.process_v2(migrated)        else:            raise UnsupportedVersionError(f"Version {version} not supported")        def migrate_v1_to_v2(self, msg):        # Transform v1 message to v2 format        return {            **msg,            'version': '2.0.0',            # Add new required fields, transform old ones            'new_required_field': 'default_value'        }


3. Processing Architecture
3.1 Worker model: Single worker vs worker pool vs specialized workers per message type
Decision: Homogeneous worker pool. All workers check P0→P1→P2→P3 in priority order. Auto-scale based on queue depth and promotion rates. No dedicated workers for specific priorities.
3.2 Concurrency handling: Pure sequential vs selective parallelization (which operations can run in parallel?)
Decision: Queue is concurrency-agnostic; agents self-serialize when needed. Org-level parallelism allowed. No queue-level per-agent FIFO or locking.
Agents are responsible for enforcing any ordering/causality they require (e.g., awaiting responses, sequence numbers, local locks).
Multiple agents within an org can work in parallel; workers may process messages from different agents simultaneously.
No queue-enforced dependency tracking.

Implementation knobs (M1.5):
- Worker prefetch (AMQP QoS): `WORKER_PREFETCH` (default 10)
- Worker in-flight handlers bound: `WORKER_CONCURRENCY` (default 10)
- Effective concurrency ≈ `min(WORKER_PREFETCH, WORKER_CONCURRENCY)`
- Best-effort ordering only; application/agent must serialize if required
Example (agent-side serialization, optional):
 # Agent enforces its own sequenceclass Agent:    async def execute_task(self):        result1 = await self.queue_and_wait({"type": "model_call"})        result2 = await self.queue_and_wait({"type": "tool_call"})        result3 = await self.queue_and_wait({"type": "memory_save"})


3.3 Priority queues: Do some messages need expedited processing?
Decision: Yes - 4 priority levels:
P0: <10ms overhead (voice, real-time)
P1: <50ms overhead (chat, user-facing)
P2: <100ms overhead (agent communication, memory ops)
P3: <500ms overhead (bulk, batch operations)
Time-based promotion: P3→P2 (30s), P2→P1 (15s), P1→P0 (5s)
3.4 Backpressure handling: What happens when the queue backs up?
Decision: Autoscale with progressive safeguards

 Strategy: Tiered response based on queue depth thresholds


Stage 1: Scale workers incrementally
Stage 2: Max workers + throttle P3 messages
Stage 3: Max workers + throttle all non-critical (P2, P3)
Stage 4: Emergency mode - reject all except P0
Configuration:

 backpressure_config = {
    "max_workers": 50,  # Cap to prevent runaway costs
    "scale_increment": 5,  # Workers to add at a time
    "scale_threshold": 100,  # Start scaling
    "light_throttle_threshold": 500,  # Throttle P3
    "heavy_throttle_threshold": 1000,  # Throttle P2+P3
    "emergency_threshold": 5000,  # Reject all except P0
}
 Implementation:

 def handle_backpressure(config):
    """
    Scale workers based on queue depth, with progressive safeguards.
    
    Uses tiered thresholds to balance throughput with system stability.
    Early stages focus on adding capacity, later stages protect the system
    from collapse by throttling and rejecting work.
    """
    queue_depth = get_queue_depth()
    current_workers = get_worker_count()
    
    # Extract configuration values for cleaner logic
    max_workers = config['max_workers']
    scale_increment = config['scale_increment']
    scale_threshold = config['scale_threshold']
    light_throttle_threshold = config['light_throttle_threshold']
    heavy_throttle_threshold = config['heavy_throttle_threshold']
    emergency_threshold = config['emergency_threshold']
    
    # Stage 4: Emergency mode - system at risk of collapse
    if queue_depth > emergency_threshold:
        scale_to(max_workers)
        reject_new_messages(preserve=['P0'])  # Voice/real-time only
        alert_operators("EMERGENCY: Queue overflow")
        
    # Stage 3: Heavy throttling - likely hitting external bottlenecks
    elif queue_depth > heavy_throttle_threshold:
        scale_to(max_workers)
        apply_rate_limiting(non_critical=True)  # P2 and P3 throttled
        alert_operators("Queue depth critical")
        
    # Stage 2: Light throttling - preserve capacity for important work
    elif queue_depth > light_throttle_threshold:
        scale_to(max_workers)
        apply_rate_limiting(P3_only=True)  # Only background tasks throttled
        
    # Stage 1: Normal scaling - add workers incrementally
    elif queue_depth > scale_threshold:
        new_workers = min(current_workers + scale_increment, max_workers)
        scale_to(new_workers)
    
    # Stage 0: Normal operation - no action needed
 Safeguards:


Worker cap prevents runaway costs
Per-org limits prevent single org from overwhelming system
Cooldown period between scaling events
Automatic poison message detection at emergency levels
4. Execution Context & Sandboxing
4.1 Sandbox strategy: When to create new sandboxes vs reuse existing ones
Decision: Pre-create sandboxes at agent startup for P0 operations (voice agents). Identify sandboxing needs during agent creation based on available tools.
4.2 Resource limits: CPU, memory, time limits per message type
Decision: Deferred - Architecture supports adding limits later
Message schema includes optional resource_limits field
Worker execution wrapped in async functions that can add timeouts
No hardcoded assumptions preventing future limits
Can add enforcement at worker level without message format changes
Future Implementation Path:
 # Message already supports limitsmessage = {    "type": "model_call",    "resource_limits": {  # Optional field        "time": 120,        "memory": "1GB"    }}# Worker can add enforcement laterasync def execute(message):    if limits := message.get('resource_limits'):        # Future: Add timeout/memory enforcement        pass    return await process(message)


4.3 Isolation levels: Full VM isolation (Firecracker) vs containers vs process isolation
Decision: [PENDING]
4.4 State management: How to pass context between related messages
Decision: [PENDING]
5. Error Handling & Recovery
5.1 Retry policies: Exponential backoff? Max retries? Dead letter queues?


Decision: Hybrid approach - message type defaults with error-based overrides
Message types have default retry configs (max_retries, strategy, delay)
Error types can override (e.g., ValidationError never retries, RateLimitError waits 60s)
Priority demotion: Each retry demotes by one level (P0→P1→P2→P3)
Exception: LLM can override demotion for critical operations
Example:
 RETRY_CONFIGS = {    'model_call': {'max_retries': 3, 'strategy': 'exponential'},    'tool_call': {'max_retries': 5, 'strategy': 'exponential'},    'memory_save': {'max_retries': 10, 'strategy': 'linear'}}


5.2 Partial failure handling: What if step 3 of 5 fails in a workflow?


Decision: LLM-powered intelligent recovery using recovery tools
LLM analyzes failure context and dependent tasks
Uses recovery tools to handle failures creatively
Can restart goals, modify agents, try alternatives
Recovery Tools Pattern:
 @recovery_tooldef restart_entire_goal(goal_id, modifications=None):    """Kill all tasks and restart with lessons learned"""    @recovery_tooldef modify_agent_prompts(agent_id, prompt_additions):    """Add context to agent about what went wrong"""    @recovery_tooldef create_alternative_agent(task, specialized_for):    """Create new agent specifically for handling this failure"""


5.3 Rollback mechanisms: Can you undo executed actions?


Decision: Checkpoint-based rollback with branched knowledge graph

 Rollback Classification via LLM:


LLM dynamically analyzes available tools to find reversal methods
Three classifications:
REVERSIBLE: Clean undo (delete_calendar_invite)
COMPENSATABLE: Undo with side effects (refund shows on statement)
IRREVERSIBLE: Cannot undo (email already sent)
Branched Knowledge Graph:


Each goal gets isolated graph branch (like Git)
Three scopes for memory operations:
GOAL_LOCAL: Discarded when goal completes (temp reasoning)
STAGED: Merged to main on success (default)
IMMEDIATE: Bypasses branch, straight to main (urgent facts)
No separate scratchpad - use graph with GOAL_LOCAL scope
LLM-powered merge conflict resolution on commit
Checkpoint Strategy:


Auto-checkpoint after expensive operations (>10s)
Auto-checkpoint after task boundaries
Auto-checkpoint before irreversible operations
Can rollback to any checkpoint, preserve learned context
Example Recovery Tool:

 @recovery_tool
def rollback_to_checkpoint(checkpoint_id, preserve_learning=True):
    # Discard graph branch
    branches.delete(f"goal-{goal_id}")
    
    # Restore to checkpoint
    restore_state(checkpoint_id)
    
    # Keep learned context
    if preserve_learning:
        context['previous_failure'] = failure_info
        context['avoid_approaches'] = failed_approaches


5.4 Circuit breakers: When to stop accepting new messages


Decision: Per-service circuit breakers
Track failures per external service (Google Calendar, Slack, etc.)
After threshold (5 failures in 60s), circuit opens for that service
Cooldown period (5 minutes) before testing with single message
Other services remain unaffected
Example:
 # Google Calendar down → reject calendar calls# Slack still works → accept Slack calls# Model calls unaffected → accept normally


5.5 Dead Letter Queue:


Decision: Structured DLQ with replay capability
Messages that exceed max retries go to DLQ
Include full error history and original message
90-day retention in DLQ
LLM can analyze DLQ patterns for systematic issues
DLQ Message Structure:
 {  "original_message": {...},  "failure_reason": "Max retries exceeded",  "error_history": [...],  "can_replay": true,  "dlq_timestamp": "2025-08-14T10:00:00Z"}


5.6 Poison Pill Handling:


Decision: Automatic detection and quarantine
If message crashes multiple workers, quarantine it
Alert developers immediately
LLM analyzes pattern to prevent similar issues
6. Monitoring & Observability
6.1 Metrics to track: Queue depth, processing latency, error rates, throughput
Decision: Track all standard metrics plus message lifecycle events
6.2 Distributed tracing: How to trace a user request through multiple messages
Decision: Full message lifecycle tracking with correlation IDs
6.3 Replay/debugging: How to replay specific message sequences for debugging
Decision: Complete audit log of all messages and events stored in PostgreSQL
Event types: created, enqueued, promoted, dequeued, conflict_detected, conflict_resolved, conflict_resolution_failed, execution_started/completed/failed, retry_scheduled, dead_letter
Storage adapter pattern for flexibility (PostgreSQL, S3, GCS, etc.)
90-day active retention, then archive based on configuration
Replay engine for debugging and recovery
Flame graph generation for performance analysis
6.4 Audit logging: What needs to be logged for compliance/security?
Decision: Log all messages with configurable PII redaction
Batch writes for performance (100 events or 1 second flush interval)
Configurable redaction levels: none (dev), medium (staging), full (prod)
Custom redaction patterns per deployment
Encrypted storage option for sensitive data
7. Integration Points
7.1 MCP integration: How do MCP tool calls translate to queue messages?
Decision: [PENDING]
7.2 Database coordination: When to checkpoint to FalkorDB/PostgreSQL
Decision: [PENDING]
7.3 Memory system hooks: How does the queue trigger memory saves/retrievals?
Decision: [PENDING]
7.4 Context management: How does the queue interact with Usman's context engineering?
Decision: [PENDING]
7.5 Agent Response Handling: How agents receive results from processed messages
Decision: Agent Coordinator pattern for distributed response delivery

 Architecture:


One Agent Coordinator per server manages all local agents
Coordinator maintains single RabbitMQ connection
Agents register with local coordinator
Coordinator subscribes to response queues for all local agents
Routes responses to appropriate agents
Benefits:


Agents don't need direct RabbitMQ access
Efficient connection pooling (1 per server vs 1 per agent)
Clean abstraction layer
Centralized monitoring/debugging point
Example Implementation:

 # One coordinator per server
class AgentCoordinator:
    def __init__(self):
        self.rabbitmq = RabbitMQConnection()
        self.local_agents = {}  # agent_id -> Agent instance
    
    async def response_distributor(self):
        # Subscribe to all local agent response queues
        for agent_id in self.local_agents:
            await self.rabbitmq.subscribe(f"agent_{agent_id}_responses")
        
        # Route responses to agents
        while True:
            msg = await self.rabbitmq.consume_any()
            agent_id = extract_agent_id(msg.queue)
            await self.local_agents[agent_id].handle_response(msg)

# Agents work through coordinator
class Agent:
    async def queue_and_wait(self, message):
        await self.coordinator.send_message(message)
        return await self.coordinator.get_response_for(self.id)
 Streaming Support:


Coordinator handles stream chunks
Forwards chunks to agent in real-time
Agent doesn't know if response is streamed or complete
8. Performance & Scaling
8.1 Throughput requirements: Messages per second target?
Decision: [PENDING]
8.2 Latency SLAs: Max acceptable delay for different message types
Decision: [PENDING]
8.3 Batching strategy: When to batch similar operations
Decision: [PENDING]
8.4 Horizontal scaling triggers: When/how to add more workers
Decision: [PENDING]
8.5 Token Allocation & Rate Limiting: Managing LLM token usage across agents
Decision: Priority and importance-based allocation system

 Core Components:


Token reservations by priority tier (P0-P3)
Importance scoring based on blocked tasks and retry count
Borrowing mechanism for high-importance tasks
Multi-provider/model fallback support
Importance Calculation (MVP):


Primary factor: Number of dependent/blocked tasks
Secondary factor: Retry count
Score range: 0.0 to 1.0
High importance tasks can borrow tokens from lower priority tiers
Allocation Flow:

 # Pseudo-code for allocation logic
def allocate_tokens(message):
    # 1. Check message priority (P0-P3)
    # 2. Calculate importance (blocked tasks + retries)
    # 3. Try to allocate from priority tier
    # 4. If insufficient, borrow based on importance
    # 5. Select model based on availability
    # 6. Handle shortage (queue, degrade, or defer)
 Integration:


Messages include token requirements and model preferences
Workers request allocation before processing
System monitors usage and rebalances periodically
Supports multiple LLM providers with different rate limits

Critical Technical Considerations
Race Condition Prevention
Agent-managed sequencing reduces many race conditions, but consider:
What about read-after-write consistency with the knowledge graph?
How to handle concurrent user sessions modifying shared business knowledge?
Agent discovery/registration race conditions
Decision: LLM-based conflict resolution with shared operation registry
Shared registry (Redis/PostgreSQL) tracks all active operations across workers
Workers check registry before processing to detect conflicts
Mechanical detection of structural conflicts (same target, resource conflicts, constraint violations)
LLM reasons through resolution with business context
Provides explainable reasoning for decisions
Can escalate to humans when confidence is low
Learns from patterns over time to auto-resolve common conflicts
Message Ordering Guarantees
FIFO per user vs global FIFO vs causal ordering
How to maintain order while allowing some parallelization
Handling out-of-order message arrivals from distributed agents
Decision: Best-effort ordering; no queue-level per-key FIFO guarantees
Agents enforce ordering/causality as needed (e.g., per-agent/resource locks, sequence numbers)
Different keys within an organization may process in parallel; priority and promotions can reorder globally
Any per-key serialization is implemented at the agent/application layer, not the queue
State Machine Design
Each message type needs clear state transitions:
QUEUED → PROCESSING → COMPLETED
              ↓
           FAILED → RETRYING
              ↓
         DEAD_LETTER

Security Boundaries
Authentication/authorization at queue level
Message encryption in transit and at rest
Preventing queue poisoning attacks
Rate limiting per user/tenant

Key Questions to Answer First
Latency tolerance: Can users wait 100ms vs 1s vs 10s for operations?


Answer: Queue overhead must be <100ms for all operations. P0 (voice) requires <10ms queue overhead. Total user-facing latency <1s for chat, immediate for voice.
Consistency model: Eventually consistent or strongly consistent?


Answer: Strong consistency is achieved at the application/agent layer via:
Agent-managed sequencing and/or per-resource locks (not enforced by the queue)
Branched knowledge graphs (isolation during execution)
LLM-powered conflict resolution for cross-key parallel operations
Atomic commits when goals complete
Multi-tenancy: Separate queues per customer or shared with isolation?


Answer: Separate queue per organization for isolation. Within an org, use sharded partitions keyed by agent/goal/resource to preserve per-key FIFO and allow parallelism; strict org-level FIFO is not enforced.
Recovery time objective: How fast must you recover from failures?


Answer: [PENDING]
Message retention: How long to keep processed messages for replay?


Answer: Configurable by deployment and pricing tier
Framework default: 7 days (configurable)
Hosted tiers (example):
Free: 7 days
Starter: 30 days
Pro: 90 days
Enterprise: Custom/unlimited
Archive strategy after retention period (S3, GCS, etc.)
Separate retention for failed messages (typically longer)

Integration with Your Existing Architecture
Given your FalkorDB + PostgreSQL decision:
Queue should checkpoint critical state changes to FalkorDB
Use PostgreSQL for message persistence/audit logs
Consider using PostgreSQL's LISTEN/NOTIFY for lightweight pub/sub
Since you're using E2B with Firecracker:
Message executor can spawn Firecracker VMs on demand
Pool warm VMs for common operations
Use mock mode for testing without real execution

Notes
[Space for additional notes as we work through decisions]

Known Limitations & Future Considerations
MVP Limitations to Address Later
1. Agent Lifecycle Management
No defined process for agent registration with coordinators
No dead agent detection/cleanup mechanism
Orphaned response queues could grow indefinitely
No agent restart/recovery strategy after crashes
2. Coordinator Reliability
Single point of failure per server
No coordinator failover/restart strategy defined
Agents lose queue access if coordinator dies
3. Knowledge Graph Branch Visibility
Unclear read permissions across agent branches
Potential visibility issues for shared data during execution
Read-only operations behavior with branches undefined
4. Message Deduplication
No idempotency strategy for duplicate messages
Network timeouts could cause double execution
No deduplication key or mechanism defined
5. Sandbox Management
Pre-creation timing for voice agents unclear
Sandbox pool sizing not defined
No sandbox lifecycle management
Failure handling for sandbox creation missing
6. Token Allocation Edge Cases
No strategy for all providers rate-limited simultaneously
Streaming response token allocation unclear
Token borrowing cost allocation undefined
7. Response Queue Scaling
Potential RabbitMQ limits with thousands of queues
Queue creation/deletion overhead not considered
Memory usage could be significant at scale
8. Rollback Edge Cases
Partial rollback with irreversible operations complex
No rollback failure recovery strategy
Rollback state communication to agents undefined
9. Development & Testing
No local development strategy defined
Missing mock strategies for distributed testing
Load testing approach not specified
Rollback scenario testing complex
10. Operational Observability
Agent health monitoring not defined
System-wide visualization tools needed
Performance benchmarking targets missing
Chaos testing strategy not planned
Suggested Simplifications for MVP
Single global coordinator instead of per-server
Agent limits (e.g., 100 per org initially)
Synchronous responses option for simpler cases
Defer graph branching if too complex initially
Skip sandboxing in MVP, add security later
Basic deduplication using message IDs
Migration & Evolution Considerations
Plan for message schema evolution beyond versioning
Strategy for upgrading coordinators without downtime
Approach for migrating from MVP to full architecture
Performance benchmarks to trigger architectural changes

