# Data dictionary

All intervals are [start, end), ISO 8601 +05:30. PKs are immutable. SQLite STRICT tables, checks, uniqueness constraints and FKs enforce basic integrity; temporal and lifecycle rules are validated in Python.

## Dataset

One immutable generation configuration per database.

Primary key: `dataset_id`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| dataset_id | TEXT | yes | as validated | none | PK | Non-empty text; dataset_id = 'DATASET-000001' |
| schema_version | TEXT | yes | as validated | none | not unique | Non-empty text |
| seed | INTEGER | yes | as validated | none | not unique | Nonnegative PRNG seed; seed >= 0 |
| profile | TEXT | yes | starter, full | none | not unique | Non-empty text |
| scale | REAL | yes | as validated | none | not unique | Positive scale multiplier; scale > 0 |
| config_json | TEXT | yes | as validated | none | not unique | Canonical JSON configuration, no labels |
| timezone | TEXT | yes | Asia/Kolkata | none | not unique | Non-empty text |
| generated_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |

## Cohort



Primary key: `cohort_id`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| cohort_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. COH-000001 |
| name | TEXT | yes | as validated | none | unique(name) | Non-empty text |

## Student



Primary key: `student_id`.

Foreign keys: `cohort_id` -> `Cohort(cohort_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| student_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. STU-000001 |
| synthetic_name | TEXT | yes | as validated | none | not unique | Non-empty text |
| cohort_id | TEXT | yes | as validated | none | not unique | Non-empty text |
| status | TEXT | yes | ACTIVE, INACTIVE | none | not unique | Non-empty text |
| effective_from | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| effective_to | TEXT | no | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |

Cross-field checks: `effective_to IS NULL OR effective_to > effective_from`.

## Course



Primary key: `course_id`.

Foreign keys: `cohort_id` -> `Cohort(cohort_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| course_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. CRS-000001 |
| title | TEXT | yes | as validated | none | not unique | Non-empty text |
| category | TEXT | yes | CORE, ELECTIVE | none | not unique | Non-empty text |
| cohort_id | TEXT | no | as validated | none | not unique | Required for CORE; null for shared ELECTIVE |

Cross-field checks: `(category = 'CORE' AND cohort_id IS NOT NULL) OR (category = 'ELECTIVE' AND cohort_id IS NULL)`.

## Enrollment

Student N:M Course bridge; current states are stable across the scheduling horizon.

Primary key: `enrollment_id`.

Foreign keys: `student_id` -> `Student(student_id)`; `course_id` -> `Course(course_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| enrollment_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. ENR-000001 |
| student_id | TEXT | yes | as validated | none | unique(student_id,course_id) | Non-empty text |
| course_id | TEXT | yes | as validated | none | unique(student_id,course_id) | Non-empty text |
| status | TEXT | yes | ACTIVE, WITHDRAWN | none | not unique | Non-empty text |
| effective_from | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| effective_to | TEXT | no | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |

Cross-field checks: `effective_to IS NULL OR effective_to > effective_from`; `(status = 'ACTIVE' AND effective_to IS NULL) OR (status = 'WITHDRAWN' AND effective_to IS NOT NULL)`.

## Exam

One examination per course in this assessment period; no retakes.

Primary key: `exam_id`.

Foreign keys: `course_id` -> `Course(course_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| exam_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. EXAM-2026-000001 |
| course_id | TEXT | yes | as validated | none | unique(course_id) | Non-empty text |
| title | TEXT | yes | as validated | none | not unique | Non-empty text |
| base_duration_minutes | INTEGER | yes | as validated | minutes | not unique | Positive base writing duration; base_duration_minutes > 0 |
| window_start | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| window_end | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| status | TEXT | yes | PLANNED, CANCELLED | none | not unique | Non-empty text |

Cross-field checks: `window_end > window_start`.

## Equipment



Primary key: `equipment_id`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| equipment_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. EQ-COMPUTER |
| name | TEXT | yes | as validated | none | unique(name) | Non-empty text |

## ExamEquipmentRequirement

Exam N:M Equipment bridge. Equipment is a binary capability, not a seat count.

Primary key: `exam_id, equipment_id`.

Foreign keys: `exam_id` -> `Exam(exam_id)`; `equipment_id` -> `Equipment(equipment_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| exam_id | TEXT | yes | as validated | none | part of composite PK | Non-empty text |
| equipment_id | TEXT | yes | as validated | none | part of composite PK | Non-empty text |

## Room



Primary key: `room_id`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| room_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. ROOM-000001 |
| name | TEXT | yes | as validated | none | unique(name) | Non-empty text |
| accessible | INTEGER | yes | 0, 1 | none | not unique | Boolean physical accessibility |
| status | TEXT | yes | OPEN, RETIRED | none | not unique | Non-empty text |
| effective_from | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| effective_to | TEXT | no | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |

Cross-field checks: `effective_to IS NULL OR effective_to > effective_from`.

## RoomCapacity

Room 1:N capacity versions, which must not overlap. Capacity must cover the whole exam.

Primary key: `capacity_id`.

Foreign keys: `room_id` -> `Room(room_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| capacity_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. CAP-000001 |
| room_id | TEXT | yes | as validated | none | unique(room_id,effective_from) | Non-empty text |
| seats | INTEGER | yes | as validated | seats | not unique | Positive usable exam seats; seats > 0 |
| effective_from | TEXT | yes | as validated | Asia/Kolkata timestamp | unique(room_id,effective_from) | ISO 8601 with +05:30 offset; half-open intervals |
| effective_to | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |

Cross-field checks: `effective_to > effective_from`.

## RoomEquipment



Primary key: `room_id, equipment_id`.

Foreign keys: `room_id` -> `Room(room_id)`; `equipment_id` -> `Equipment(equipment_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| room_id | TEXT | yes | as validated | none | part of composite PK | Non-empty text |
| equipment_id | TEXT | yes | as validated | none | part of composite PK | Non-empty text |

## RoomOpening



Primary key: `opening_id`.

Foreign keys: `room_id` -> `Room(room_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| opening_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. OPN-000001 |
| room_id | TEXT | yes | as validated | none | unique(room_id,starts_at) | Non-empty text |
| starts_at | TEXT | yes | as validated | Asia/Kolkata timestamp | unique(room_id,starts_at) | ISO 8601 with +05:30 offset; half-open intervals |
| ends_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |

Cross-field checks: `ends_at > starts_at`.

## RoomClosure



Primary key: `closure_id`.

Foreign keys: `room_id` -> `Room(room_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| closure_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. CLS-000001 |
| room_id | TEXT | yes | as validated | none | unique(room_id,starts_at) | Non-empty text |
| starts_at | TEXT | yes | as validated | Asia/Kolkata timestamp | unique(room_id,starts_at) | ISO 8601 with +05:30 offset; half-open intervals |
| ends_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| reason | TEXT | yes | MAINTENANCE, CAMPUS_EVENT | none | not unique | Non-empty text |

Cross-field checks: `ends_at > starts_at`.

## Invigilator



Primary key: `invigilator_id`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| invigilator_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. INV-000001 |
| synthetic_name | TEXT | yes | as validated | none | not unique | Non-empty text |
| status | TEXT | yes | ACTIVE, INACTIVE | none | not unique | Non-empty text |
| effective_from | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| effective_to | TEXT | no | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |

Cross-field checks: `effective_to IS NULL OR effective_to > effective_from`.

## Availability



Primary key: `availability_id`.

Foreign keys: `invigilator_id` -> `Invigilator(invigilator_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| availability_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. AVL-000001 |
| invigilator_id | TEXT | yes | as validated | none | unique(invigilator_id,starts_at) | Non-empty text |
| starts_at | TEXT | yes | as validated | Asia/Kolkata timestamp | unique(invigilator_id,starts_at) | ISO 8601 with +05:30 offset; half-open intervals |
| ends_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| status | TEXT | yes | AVAILABLE, CANCELLED | none | not unique | Non-empty text |

Cross-field checks: `ends_at > starts_at`.

## Accommodation



Primary key: `accommodation_id`.

Foreign keys: `student_id` -> `Student(student_id)`; `exam_id` -> `Exam(exam_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| accommodation_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. ACC-000001 |
| student_id | TEXT | yes | as validated | none | not unique | Non-empty text |
| exam_id | TEXT | no | as validated | none | not unique | Null applies to all enrolled exams; otherwise applies to this exam only |
| kind | TEXT | yes | EXTRA_TIME, ACCESSIBLE_ROOM | none | not unique | Non-empty text |
| extra_percent | INTEGER | yes | 0, 25, 50 | percent | not unique | 0 for accessibility; 25 or 50 for extra time |
| status | TEXT | yes | PENDING, APPROVED, REJECTED | none | not unique | Non-empty text |
| effective_from | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| effective_to | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |

Cross-field checks: `effective_to > effective_from`; `(kind = 'EXTRA_TIME' AND extra_percent > 0) OR (kind = 'ACCESSIBLE_ROOM' AND extra_percent = 0)`.

## ExamRequirement

Exam 1:1 derived requirement; never a feature carrying anomaly labels.

Primary key: `exam_id`.

Foreign keys: `exam_id` -> `Exam(exam_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| exam_id | TEXT | yes | as validated | none | PK | Non-empty text |
| enrolled_count | INTEGER | yes | as validated | students | not unique | Derived active enrollment count at window_start; enrolled_count >= 0 |
| duration_minutes | INTEGER | yes | as validated | minutes | not unique | ceil(base_duration * (100 + max_extra_percent) / 100); duration_minutes > 0 |
| max_extra_percent | INTEGER | yes | 0, 25, 50 | percent | not unique | Maximum approved applicable extra time; 0 if none |
| accessible_required | INTEGER | yes | 0, 1 | none | not unique | Any enrolled learner with approved accessibility support |
| invigilators_required | INTEGER | yes | as validated | people | not unique | ceil(enrolled_count / 40); invigilators_required >= 0 |

## LifecycleEvent

Append-only typed event history; all entity references have actual FKs.

Primary key: `event_id`.

Foreign keys: `student_id` -> `Student(student_id)`; `enrollment_id` -> `Enrollment(enrollment_id)`; `exam_id` -> `Exam(exam_id)`; `room_id` -> `Room(room_id)`; `invigilator_id` -> `Invigilator(invigilator_id)`; `availability_id` -> `Availability(availability_id)`; `accommodation_id` -> `Accommodation(accommodation_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| event_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. LFE-000001 |
| student_id | TEXT | no | as validated | none | not unique | Exactly one entity FK is non-null |
| enrollment_id | TEXT | no | as validated | none | not unique | Exactly one entity FK is non-null |
| exam_id | TEXT | no | as validated | none | not unique | Exactly one entity FK is non-null |
| room_id | TEXT | no | as validated | none | not unique | Exactly one entity FK is non-null |
| invigilator_id | TEXT | no | as validated | none | not unique | Exactly one entity FK is non-null |
| availability_id | TEXT | no | as validated | none | not unique | Exactly one entity FK is non-null |
| accommodation_id | TEXT | no | as validated | none | not unique | Exactly one entity FK is non-null |
| from_state | TEXT | no | as validated | none | not unique | Previous enum state; null only on creation |
| to_state | TEXT | yes | ACTIVE, INACTIVE, WITHDRAWN, PLANNED, CANCELLED, OPEN, RETIRED, AVAILABLE, PENDING, APPROVED, REJECTED | none | not unique | Non-empty text |
| occurred_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |

Cross-field checks: `(student_id IS NOT NULL) + (enrollment_id IS NOT NULL) + (exam_id IS NOT NULL) + (room_id IS NOT NULL) + (invigilator_id IS NOT NULL) + (availability_id IS NOT NULL) + (accommodation_id IS NOT NULL) = 1`.

## SchedulingRun

Committed atomically only after all decisions; both start/completion events retained.

Primary key: `run_id`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| run_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. RUN-000001 |
| algorithm | TEXT | yes | degree-greedy-v1 | none | not unique | Non-empty text |
| status | TEXT | yes | COMPLETED | none | not unique | Non-empty text |
| started_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| completed_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| config_json | TEXT | yes | as validated | none | not unique | Canonical candidate-start policy and immutable source configuration |

Cross-field checks: `completed_at >= started_at`.

## ScheduleAssignment

Immutable decisions. Natural assignment ID can repeat in separate runs; composite PK prevents collisions.

Primary key: `run_id, assignment_id`.

Foreign keys: `run_id` -> `SchedulingRun(run_id)`; `exam_id` -> `Exam(exam_id)`; `room_id` -> `Room(room_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| run_id | TEXT | yes | as validated | none | part of composite PK; unique(run_id,exam_id) | Non-empty text |
| assignment_id | TEXT | yes | as validated | none | part of composite PK | Immutable deterministic identifier, e.g. ASN-EXAM-2026-000001-ROOM-000001 |
| exam_id | TEXT | yes | as validated | none | unique(run_id,exam_id) | Non-empty text |
| room_id | TEXT | yes | as validated | none | not unique | Non-empty text |
| starts_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| ends_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| status | TEXT | yes | ACCEPTED | none | not unique | Non-empty text |

Cross-field checks: `ends_at > starts_at`; `assignment_id = 'ASN-' || exam_id || '-' || room_id`.

## InvigilatorAllocation

Assignment N:M Invigilator bridge, scoped to one scheduling run.

Primary key: `run_id, assignment_id, invigilator_id`.

Foreign keys: `run_id,assignment_id` -> `ScheduleAssignment(run_id,assignment_id)`; `invigilator_id` -> `Invigilator(invigilator_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| run_id | TEXT | yes | as validated | none | part of composite PK | Non-empty text |
| assignment_id | TEXT | yes | as validated | none | part of composite PK | Non-empty text |
| invigilator_id | TEXT | yes | as validated | none | part of composite PK | Non-empty text |

## ExamOutcome



Primary key: `run_id, exam_id`.

Foreign keys: `run_id` -> `SchedulingRun(run_id)`; `exam_id` -> `Exam(exam_id)`; `run_id,assignment_id` -> `ScheduleAssignment(run_id,assignment_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| run_id | TEXT | yes | as validated | none | part of composite PK | Non-empty text |
| exam_id | TEXT | yes | as validated | none | part of composite PK | Non-empty text |
| status | TEXT | yes | SCHEDULED, UNASSIGNED | none | not unique | Non-empty text |
| assignment_id | TEXT | no | as validated | none | not unique | Required iff SCHEDULED |
| reason_code | TEXT | no | NO_ENROLLMENTS, NO_COMPATIBLE_ROOM, NO_FEASIBLE_SLOT | none | not unique | Required iff UNASSIGNED |
| evidence_json | TEXT | yes | as validated | none | not unique | JSON counters and human-readable evidence; never ground truth |

Cross-field checks: `(status = 'SCHEDULED' AND assignment_id IS NOT NULL AND reason_code IS NULL) OR (status = 'UNASSIGNED' AND assignment_id IS NULL AND reason_code IS NOT NULL)`.

## DecisionEvent

Append-only audit trail.

Primary key: `event_id`.

Foreign keys: `run_id` -> `SchedulingRun(run_id)`; `exam_id` -> `Exam(exam_id)`.

| Field | Type | Required | Allowed values | Units | Uniqueness | Validation |
|---|---|---|---|---|---|---|
| event_id | TEXT | yes | as validated | none | PK | Immutable deterministic identifier, e.g. DEC-RUN-000001-000001 |
| run_id | TEXT | yes | as validated | none | not unique | Non-empty text |
| exam_id | TEXT | no | as validated | none | not unique | Null for run-wide events |
| kind | TEXT | yes | RUN_STARTED, EXAM_ASSIGNED, EXAM_UNASSIGNED, RUN_COMPLETED | none | not unique | Non-empty text |
| occurred_at | TEXT | yes | as validated | Asia/Kolkata timestamp | not unique | ISO 8601 with +05:30 offset; half-open intervals |
| payload_json | TEXT | yes | as validated | none | not unique | Canonical JSON decision and rejection evidence |
