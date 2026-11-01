# Entity relationships, effective dates and states

The authoritative keys and FKs are in `schema.sql` and the field-level dictionary. This table records business cardinality. A child has exactly one referenced parent for a non-null FK; nullable FKs are explicitly noted. “0..N” means optional dependent records.

| Parent -> child | Cardinality | Notes |
|---|---|---|
| Dataset -> generated source | 1 dataset per database | Configuration, not a cross-table identity FK; generator checks row counts |
| Cohort -> Student | 1:N | Each student belongs to exactly one cohort |
| Cohort -> Course | 1:0..N | CORE requires cohort; shared ELECTIVE has null cohort |
| Student -> Enrollment <- Course | N:M | Enrollment has own PK and unique `(student_id,course_id)` |
| Course -> Exam | 1:0..1 | Unique course FK; generation produces exactly one per course |
| Exam -> ExamRequirement | 1:1 | Exam FK is requirement PK; completeness independently checked |
| Exam -> ExamEquipmentRequirement <- Equipment | N:M | Composite bridge PK |
| Room -> RoomEquipment <- Equipment | N:M | Composite bridge PK |
| Room -> RoomCapacity | 1:N | Non-overlapping effective versions, full opening coverage required |
| Room -> RoomOpening / RoomClosure | 1:0..N each | Closures subtract from opening intervals |
| Invigilator -> Availability | 1:0..N | Only AVAILABLE, effective intervals can cover a booking |
| Student -> Accommodation | 1:0..N | Multiple support kinds and approval lifecycles |
| Exam -> Accommodation | 1:0..N, optional FK | Null exam FK means support applies across enrolled exams |
| Tracked master -> LifecycleEvent | 1:N | Exactly one of seven typed FKs non-null; no unvalidated polymorphic entity ID |
| SchedulingRun -> ScheduleAssignment | 1:0..N | Assignment PK is `(run_id,assignment_id)`; exam unique within run |
| Exam / Room -> ScheduleAssignment | 1:0..N each | Across runs, the same source entity can have different decisions |
| ScheduleAssignment -> InvigilatorAllocation <- Invigilator | N:M | Composite assignment FK includes run; composite bridge PK |
| SchedulingRun / Exam -> ExamOutcome | 1:N / 1:0..N | PK `(run_id,exam_id)`; one outcome per planned exam per run |
| ScheduleAssignment -> ExamOutcome | One scheduled outcome by validation | Nullable composite FK; null for UNASSIGNED; exam/assignment consistency checked |
| SchedulingRun -> DecisionEvent | 1:N | Exactly one start/completion and one event per outcome |
| Exam -> DecisionEvent | 1:0..N, optional FK | Null exam for run-wide events |

## Effective dates

Student, Enrollment, Room and Invigilator have `[effective_from,effective_to)` intervals; null end means no known end. RoomCapacity and Accommodation have explicit finite effective intervals. Exams have a start-inclusive/end-exclusive scheduling window. Openings, closures, staff availability and assignments use the same half-open convention. All timestamps use the explicit `+05:30` offset.

The minimum effective room capacity across every intersecting capacity version must suffice throughout an exam, with no coverage gap. Adjacent opening/availability records can jointly cover a booking. Any overlapping closure makes the room unavailable. Resource lifecycle intervals must cover the entire assignment. For the supported frozen assessment snapshot, learner/enrollment/support changes strictly inside an exam window are rejected; capacity versions and availability vary normally.

## Lifecycle states

| Entity | Initial | Legal transitions |
|---|---|---|
| Student / Invigilator | ACTIVE | ACTIVE -> INACTIVE |
| Enrollment | ACTIVE | ACTIVE -> WITHDRAWN |
| Exam | PLANNED | PLANNED -> CANCELLED |
| Room | OPEN | OPEN -> RETIRED |
| Availability | AVAILABLE | AVAILABLE -> CANCELLED |
| Accommodation | PENDING | PENDING -> APPROVED or REJECTED |
| SchedulingRun | Transaction computes decisions | Persist COMPLETED atomically, retain RUN_STARTED/RUN_COMPLETED events |
| ScheduleAssignment | ACCEPTED | Immutable; a later alternative is a new run |
| ExamOutcome | SCHEDULED or UNASSIGNED | Immutable per run; evidence required for unassigned |

Creation has `from_state=null`; later lifecycle events must chain from the previous state. The final state must match the current source row. Withdrawal/retirement event times reconcile to effective end dates. Updates/deletes of event/run/decision/assignment/outcome/allocation history are blocked by triggers. All tables have immutable-primary-key triggers. No master-editing command is exposed; adding an administrative mutation API would require append-only events and derived-data refresh in the same transaction.

## Assignment ID scope

The natural ID follows the required `ASN-<exam-id>-<room-id>` nomenclature. Because an exam can be assigned to the same room in another run, the actual PK is `(run_id,assignment_id)`. Every allocation and outcome reference includes `run_id`. This retains the required human-readable ID without erasing history or allowing collisions within a run.
