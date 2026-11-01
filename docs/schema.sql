-- ExamFlow schema v1.0

PRAGMA foreign_keys = ON;

CREATE TABLE "Dataset" (
  "dataset_id" TEXT NOT NULL CHECK ("dataset_id" IS NULL OR length("dataset_id") > 0) CHECK (dataset_id = 'DATASET-000001'),
  "schema_version" TEXT NOT NULL CHECK ("schema_version" IS NULL OR length("schema_version") > 0),
  "seed" INTEGER NOT NULL CHECK (seed >= 0),
  "profile" TEXT NOT NULL CHECK ("profile" IS NULL OR length("profile") > 0) CHECK ("profile" IN ('starter', 'full')),
  "scale" REAL NOT NULL CHECK (scale > 0),
  "config_json" TEXT NOT NULL CHECK ("config_json" IS NULL OR length("config_json") > 0),
  "timezone" TEXT NOT NULL CHECK ("timezone" IS NULL OR length("timezone") > 0) CHECK ("timezone" IN ('Asia/Kolkata')),
  "generated_at" TEXT NOT NULL CHECK ("generated_at" IS NULL OR length("generated_at") > 0),
  PRIMARY KEY (dataset_id)
) STRICT;

CREATE TABLE "Cohort" (
  "cohort_id" TEXT NOT NULL CHECK ("cohort_id" IS NULL OR length("cohort_id") > 0),
  "name" TEXT NOT NULL CHECK ("name" IS NULL OR length("name") > 0),
  PRIMARY KEY (cohort_id),
  UNIQUE (name)
) STRICT;

CREATE TABLE "Student" (
  "student_id" TEXT NOT NULL CHECK ("student_id" IS NULL OR length("student_id") > 0),
  "synthetic_name" TEXT NOT NULL CHECK ("synthetic_name" IS NULL OR length("synthetic_name") > 0),
  "cohort_id" TEXT NOT NULL CHECK ("cohort_id" IS NULL OR length("cohort_id") > 0),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('ACTIVE', 'INACTIVE')),
  "effective_from" TEXT NOT NULL CHECK ("effective_from" IS NULL OR length("effective_from") > 0),
  "effective_to" TEXT CHECK ("effective_to" IS NULL OR length("effective_to") > 0),
  PRIMARY KEY (student_id),
  FOREIGN KEY (cohort_id) REFERENCES Cohort(cohort_id),
  CHECK (effective_to IS NULL OR effective_to > effective_from)
) STRICT;

CREATE TABLE "Course" (
  "course_id" TEXT NOT NULL CHECK ("course_id" IS NULL OR length("course_id") > 0),
  "title" TEXT NOT NULL CHECK ("title" IS NULL OR length("title") > 0),
  "category" TEXT NOT NULL CHECK ("category" IS NULL OR length("category") > 0) CHECK ("category" IN ('CORE', 'ELECTIVE')),
  "cohort_id" TEXT CHECK ("cohort_id" IS NULL OR length("cohort_id") > 0),
  PRIMARY KEY (course_id),
  FOREIGN KEY (cohort_id) REFERENCES Cohort(cohort_id),
  CHECK ((category = 'CORE' AND cohort_id IS NOT NULL) OR (category = 'ELECTIVE' AND cohort_id IS NULL))
) STRICT;

CREATE TABLE "Enrollment" (
  "enrollment_id" TEXT NOT NULL CHECK ("enrollment_id" IS NULL OR length("enrollment_id") > 0),
  "student_id" TEXT NOT NULL CHECK ("student_id" IS NULL OR length("student_id") > 0),
  "course_id" TEXT NOT NULL CHECK ("course_id" IS NULL OR length("course_id") > 0),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('ACTIVE', 'WITHDRAWN')),
  "effective_from" TEXT NOT NULL CHECK ("effective_from" IS NULL OR length("effective_from") > 0),
  "effective_to" TEXT CHECK ("effective_to" IS NULL OR length("effective_to") > 0),
  PRIMARY KEY (enrollment_id),
  FOREIGN KEY (student_id) REFERENCES Student(student_id),
  FOREIGN KEY (course_id) REFERENCES Course(course_id),
  UNIQUE (student_id,course_id),
  CHECK (effective_to IS NULL OR effective_to > effective_from),
  CHECK ((status = 'ACTIVE' AND effective_to IS NULL) OR (status = 'WITHDRAWN' AND effective_to IS NOT NULL))
) STRICT;

CREATE TABLE "Exam" (
  "exam_id" TEXT NOT NULL CHECK ("exam_id" IS NULL OR length("exam_id") > 0),
  "course_id" TEXT NOT NULL CHECK ("course_id" IS NULL OR length("course_id") > 0),
  "title" TEXT NOT NULL CHECK ("title" IS NULL OR length("title") > 0),
  "base_duration_minutes" INTEGER NOT NULL CHECK (base_duration_minutes > 0),
  "window_start" TEXT NOT NULL CHECK ("window_start" IS NULL OR length("window_start") > 0),
  "window_end" TEXT NOT NULL CHECK ("window_end" IS NULL OR length("window_end") > 0),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('PLANNED', 'CANCELLED')),
  PRIMARY KEY (exam_id),
  FOREIGN KEY (course_id) REFERENCES Course(course_id),
  UNIQUE (course_id),
  CHECK (window_end > window_start)
) STRICT;

CREATE TABLE "Equipment" (
  "equipment_id" TEXT NOT NULL CHECK ("equipment_id" IS NULL OR length("equipment_id") > 0),
  "name" TEXT NOT NULL CHECK ("name" IS NULL OR length("name") > 0),
  PRIMARY KEY (equipment_id),
  UNIQUE (name)
) STRICT;

CREATE TABLE "ExamEquipmentRequirement" (
  "exam_id" TEXT NOT NULL CHECK ("exam_id" IS NULL OR length("exam_id") > 0),
  "equipment_id" TEXT NOT NULL CHECK ("equipment_id" IS NULL OR length("equipment_id") > 0),
  PRIMARY KEY (exam_id,equipment_id),
  FOREIGN KEY (exam_id) REFERENCES Exam(exam_id),
  FOREIGN KEY (equipment_id) REFERENCES Equipment(equipment_id)
) STRICT;

CREATE TABLE "Room" (
  "room_id" TEXT NOT NULL CHECK ("room_id" IS NULL OR length("room_id") > 0),
  "name" TEXT NOT NULL CHECK ("name" IS NULL OR length("name") > 0),
  "accessible" INTEGER NOT NULL CHECK ("accessible" IN (0, 1)),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('OPEN', 'RETIRED')),
  "effective_from" TEXT NOT NULL CHECK ("effective_from" IS NULL OR length("effective_from") > 0),
  "effective_to" TEXT CHECK ("effective_to" IS NULL OR length("effective_to") > 0),
  PRIMARY KEY (room_id),
  UNIQUE (name),
  CHECK (effective_to IS NULL OR effective_to > effective_from)
) STRICT;

CREATE TABLE "RoomCapacity" (
  "capacity_id" TEXT NOT NULL CHECK ("capacity_id" IS NULL OR length("capacity_id") > 0),
  "room_id" TEXT NOT NULL CHECK ("room_id" IS NULL OR length("room_id") > 0),
  "seats" INTEGER NOT NULL CHECK (seats > 0),
  "effective_from" TEXT NOT NULL CHECK ("effective_from" IS NULL OR length("effective_from") > 0),
  "effective_to" TEXT NOT NULL CHECK ("effective_to" IS NULL OR length("effective_to") > 0),
  PRIMARY KEY (capacity_id),
  FOREIGN KEY (room_id) REFERENCES Room(room_id),
  UNIQUE (room_id,effective_from),
  CHECK (effective_to > effective_from)
) STRICT;

CREATE TABLE "RoomEquipment" (
  "room_id" TEXT NOT NULL CHECK ("room_id" IS NULL OR length("room_id") > 0),
  "equipment_id" TEXT NOT NULL CHECK ("equipment_id" IS NULL OR length("equipment_id") > 0),
  PRIMARY KEY (room_id,equipment_id),
  FOREIGN KEY (room_id) REFERENCES Room(room_id),
  FOREIGN KEY (equipment_id) REFERENCES Equipment(equipment_id)
) STRICT;

CREATE TABLE "RoomOpening" (
  "opening_id" TEXT NOT NULL CHECK ("opening_id" IS NULL OR length("opening_id") > 0),
  "room_id" TEXT NOT NULL CHECK ("room_id" IS NULL OR length("room_id") > 0),
  "starts_at" TEXT NOT NULL CHECK ("starts_at" IS NULL OR length("starts_at") > 0),
  "ends_at" TEXT NOT NULL CHECK ("ends_at" IS NULL OR length("ends_at") > 0),
  PRIMARY KEY (opening_id),
  FOREIGN KEY (room_id) REFERENCES Room(room_id),
  UNIQUE (room_id,starts_at),
  CHECK (ends_at > starts_at)
) STRICT;

CREATE TABLE "RoomClosure" (
  "closure_id" TEXT NOT NULL CHECK ("closure_id" IS NULL OR length("closure_id") > 0),
  "room_id" TEXT NOT NULL CHECK ("room_id" IS NULL OR length("room_id") > 0),
  "starts_at" TEXT NOT NULL CHECK ("starts_at" IS NULL OR length("starts_at") > 0),
  "ends_at" TEXT NOT NULL CHECK ("ends_at" IS NULL OR length("ends_at") > 0),
  "reason" TEXT NOT NULL CHECK ("reason" IS NULL OR length("reason") > 0) CHECK ("reason" IN ('MAINTENANCE', 'CAMPUS_EVENT')),
  PRIMARY KEY (closure_id),
  FOREIGN KEY (room_id) REFERENCES Room(room_id),
  UNIQUE (room_id,starts_at),
  CHECK (ends_at > starts_at)
) STRICT;

CREATE TABLE "Invigilator" (
  "invigilator_id" TEXT NOT NULL CHECK ("invigilator_id" IS NULL OR length("invigilator_id") > 0),
  "synthetic_name" TEXT NOT NULL CHECK ("synthetic_name" IS NULL OR length("synthetic_name") > 0),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('ACTIVE', 'INACTIVE')),
  "effective_from" TEXT NOT NULL CHECK ("effective_from" IS NULL OR length("effective_from") > 0),
  "effective_to" TEXT CHECK ("effective_to" IS NULL OR length("effective_to") > 0),
  PRIMARY KEY (invigilator_id),
  CHECK (effective_to IS NULL OR effective_to > effective_from)
) STRICT;

CREATE TABLE "Availability" (
  "availability_id" TEXT NOT NULL CHECK ("availability_id" IS NULL OR length("availability_id") > 0),
  "invigilator_id" TEXT NOT NULL CHECK ("invigilator_id" IS NULL OR length("invigilator_id") > 0),
  "starts_at" TEXT NOT NULL CHECK ("starts_at" IS NULL OR length("starts_at") > 0),
  "ends_at" TEXT NOT NULL CHECK ("ends_at" IS NULL OR length("ends_at") > 0),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('AVAILABLE', 'CANCELLED')),
  PRIMARY KEY (availability_id),
  FOREIGN KEY (invigilator_id) REFERENCES Invigilator(invigilator_id),
  UNIQUE (invigilator_id,starts_at),
  CHECK (ends_at > starts_at)
) STRICT;

CREATE TABLE "Accommodation" (
  "accommodation_id" TEXT NOT NULL CHECK ("accommodation_id" IS NULL OR length("accommodation_id") > 0),
  "student_id" TEXT NOT NULL CHECK ("student_id" IS NULL OR length("student_id") > 0),
  "exam_id" TEXT CHECK ("exam_id" IS NULL OR length("exam_id") > 0),
  "kind" TEXT NOT NULL CHECK ("kind" IS NULL OR length("kind") > 0) CHECK ("kind" IN ('EXTRA_TIME', 'ACCESSIBLE_ROOM')),
  "extra_percent" INTEGER NOT NULL CHECK ("extra_percent" IN (0, 25, 50)),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('PENDING', 'APPROVED', 'REJECTED')),
  "effective_from" TEXT NOT NULL CHECK ("effective_from" IS NULL OR length("effective_from") > 0),
  "effective_to" TEXT NOT NULL CHECK ("effective_to" IS NULL OR length("effective_to") > 0),
  PRIMARY KEY (accommodation_id),
  FOREIGN KEY (student_id) REFERENCES Student(student_id),
  FOREIGN KEY (exam_id) REFERENCES Exam(exam_id),
  CHECK (effective_to > effective_from),
  CHECK ((kind = 'EXTRA_TIME' AND extra_percent > 0) OR (kind = 'ACCESSIBLE_ROOM' AND extra_percent = 0))
) STRICT;

CREATE TABLE "ExamRequirement" (
  "exam_id" TEXT NOT NULL CHECK ("exam_id" IS NULL OR length("exam_id") > 0),
  "enrolled_count" INTEGER NOT NULL CHECK (enrolled_count >= 0),
  "duration_minutes" INTEGER NOT NULL CHECK (duration_minutes > 0),
  "max_extra_percent" INTEGER NOT NULL CHECK ("max_extra_percent" IN (0, 25, 50)),
  "accessible_required" INTEGER NOT NULL CHECK ("accessible_required" IN (0, 1)),
  "invigilators_required" INTEGER NOT NULL CHECK (invigilators_required >= 0),
  PRIMARY KEY (exam_id),
  FOREIGN KEY (exam_id) REFERENCES Exam(exam_id)
) STRICT;

CREATE TABLE "LifecycleEvent" (
  "event_id" TEXT NOT NULL CHECK ("event_id" IS NULL OR length("event_id") > 0),
  "student_id" TEXT CHECK ("student_id" IS NULL OR length("student_id") > 0),
  "enrollment_id" TEXT CHECK ("enrollment_id" IS NULL OR length("enrollment_id") > 0),
  "exam_id" TEXT CHECK ("exam_id" IS NULL OR length("exam_id") > 0),
  "room_id" TEXT CHECK ("room_id" IS NULL OR length("room_id") > 0),
  "invigilator_id" TEXT CHECK ("invigilator_id" IS NULL OR length("invigilator_id") > 0),
  "availability_id" TEXT CHECK ("availability_id" IS NULL OR length("availability_id") > 0),
  "accommodation_id" TEXT CHECK ("accommodation_id" IS NULL OR length("accommodation_id") > 0),
  "from_state" TEXT CHECK ("from_state" IS NULL OR length("from_state") > 0),
  "to_state" TEXT NOT NULL CHECK ("to_state" IS NULL OR length("to_state") > 0) CHECK ("to_state" IN ('ACTIVE', 'INACTIVE', 'WITHDRAWN', 'PLANNED', 'CANCELLED', 'OPEN', 'RETIRED', 'AVAILABLE', 'PENDING', 'APPROVED', 'REJECTED')),
  "occurred_at" TEXT NOT NULL CHECK ("occurred_at" IS NULL OR length("occurred_at") > 0),
  PRIMARY KEY (event_id),
  FOREIGN KEY (student_id) REFERENCES Student(student_id),
  FOREIGN KEY (enrollment_id) REFERENCES Enrollment(enrollment_id),
  FOREIGN KEY (exam_id) REFERENCES Exam(exam_id),
  FOREIGN KEY (room_id) REFERENCES Room(room_id),
  FOREIGN KEY (invigilator_id) REFERENCES Invigilator(invigilator_id),
  FOREIGN KEY (availability_id) REFERENCES Availability(availability_id),
  FOREIGN KEY (accommodation_id) REFERENCES Accommodation(accommodation_id),
  CHECK ((student_id IS NOT NULL) + (enrollment_id IS NOT NULL) + (exam_id IS NOT NULL) + (room_id IS NOT NULL) + (invigilator_id IS NOT NULL) + (availability_id IS NOT NULL) + (accommodation_id IS NOT NULL) = 1)
) STRICT;

CREATE TABLE "SchedulingRun" (
  "run_id" TEXT NOT NULL CHECK ("run_id" IS NULL OR length("run_id") > 0),
  "algorithm" TEXT NOT NULL CHECK ("algorithm" IS NULL OR length("algorithm") > 0) CHECK ("algorithm" IN ('degree-greedy-v1')),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('COMPLETED')),
  "started_at" TEXT NOT NULL CHECK ("started_at" IS NULL OR length("started_at") > 0),
  "completed_at" TEXT NOT NULL CHECK ("completed_at" IS NULL OR length("completed_at") > 0),
  "config_json" TEXT NOT NULL CHECK ("config_json" IS NULL OR length("config_json") > 0),
  PRIMARY KEY (run_id),
  CHECK (completed_at >= started_at)
) STRICT;

CREATE TABLE "ScheduleAssignment" (
  "run_id" TEXT NOT NULL CHECK ("run_id" IS NULL OR length("run_id") > 0),
  "assignment_id" TEXT NOT NULL CHECK ("assignment_id" IS NULL OR length("assignment_id") > 0),
  "exam_id" TEXT NOT NULL CHECK ("exam_id" IS NULL OR length("exam_id") > 0),
  "room_id" TEXT NOT NULL CHECK ("room_id" IS NULL OR length("room_id") > 0),
  "starts_at" TEXT NOT NULL CHECK ("starts_at" IS NULL OR length("starts_at") > 0),
  "ends_at" TEXT NOT NULL CHECK ("ends_at" IS NULL OR length("ends_at") > 0),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('ACCEPTED')),
  PRIMARY KEY (run_id,assignment_id),
  FOREIGN KEY (run_id) REFERENCES SchedulingRun(run_id),
  FOREIGN KEY (exam_id) REFERENCES Exam(exam_id),
  FOREIGN KEY (room_id) REFERENCES Room(room_id),
  UNIQUE (run_id,exam_id),
  CHECK (ends_at > starts_at),
  CHECK (assignment_id = 'ASN-' || exam_id || '-' || room_id)
) STRICT;

CREATE TABLE "InvigilatorAllocation" (
  "run_id" TEXT NOT NULL CHECK ("run_id" IS NULL OR length("run_id") > 0),
  "assignment_id" TEXT NOT NULL CHECK ("assignment_id" IS NULL OR length("assignment_id") > 0),
  "invigilator_id" TEXT NOT NULL CHECK ("invigilator_id" IS NULL OR length("invigilator_id") > 0),
  PRIMARY KEY (run_id,assignment_id,invigilator_id),
  FOREIGN KEY (run_id,assignment_id) REFERENCES ScheduleAssignment(run_id,assignment_id),
  FOREIGN KEY (invigilator_id) REFERENCES Invigilator(invigilator_id)
) STRICT;

CREATE TABLE "ExamOutcome" (
  "run_id" TEXT NOT NULL CHECK ("run_id" IS NULL OR length("run_id") > 0),
  "exam_id" TEXT NOT NULL CHECK ("exam_id" IS NULL OR length("exam_id") > 0),
  "status" TEXT NOT NULL CHECK ("status" IS NULL OR length("status") > 0) CHECK ("status" IN ('SCHEDULED', 'UNASSIGNED')),
  "assignment_id" TEXT CHECK ("assignment_id" IS NULL OR length("assignment_id") > 0),
  "reason_code" TEXT CHECK ("reason_code" IS NULL OR length("reason_code") > 0) CHECK ("reason_code" IN ('NO_ENROLLMENTS', 'NO_COMPATIBLE_ROOM', 'NO_FEASIBLE_SLOT')),
  "evidence_json" TEXT NOT NULL CHECK ("evidence_json" IS NULL OR length("evidence_json") > 0),
  PRIMARY KEY (run_id,exam_id),
  FOREIGN KEY (run_id) REFERENCES SchedulingRun(run_id),
  FOREIGN KEY (exam_id) REFERENCES Exam(exam_id),
  FOREIGN KEY (run_id,assignment_id) REFERENCES ScheduleAssignment(run_id,assignment_id),
  CHECK ((status = 'SCHEDULED' AND assignment_id IS NOT NULL AND reason_code IS NULL) OR (status = 'UNASSIGNED' AND assignment_id IS NULL AND reason_code IS NOT NULL))
) STRICT;

CREATE TABLE "DecisionEvent" (
  "event_id" TEXT NOT NULL CHECK ("event_id" IS NULL OR length("event_id") > 0),
  "run_id" TEXT NOT NULL CHECK ("run_id" IS NULL OR length("run_id") > 0),
  "exam_id" TEXT CHECK ("exam_id" IS NULL OR length("exam_id") > 0),
  "kind" TEXT NOT NULL CHECK ("kind" IS NULL OR length("kind") > 0) CHECK ("kind" IN ('RUN_STARTED', 'EXAM_ASSIGNED', 'EXAM_UNASSIGNED', 'RUN_COMPLETED')),
  "occurred_at" TEXT NOT NULL CHECK ("occurred_at" IS NULL OR length("occurred_at") > 0),
  "payload_json" TEXT NOT NULL CHECK ("payload_json" IS NULL OR length("payload_json") > 0),
  PRIMARY KEY (event_id),
  FOREIGN KEY (run_id) REFERENCES SchedulingRun(run_id),
  FOREIGN KEY (exam_id) REFERENCES Exam(exam_id)
) STRICT;

CREATE INDEX idx_enrollment_course ON Enrollment(course_id, status);

CREATE INDEX idx_accommodation_student ON Accommodation(student_id, status);

CREATE INDEX idx_availability_staff ON Availability(invigilator_id, starts_at);

CREATE INDEX idx_lifecycle_enrollment ON LifecycleEvent(enrollment_id);

CREATE INDEX idx_assignment_exam ON ScheduleAssignment(exam_id);

CREATE TRIGGER immutable_LifecycleEvent_update BEFORE UPDATE ON LifecycleEvent BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_LifecycleEvent_delete BEFORE DELETE ON LifecycleEvent BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_SchedulingRun_update BEFORE UPDATE ON SchedulingRun BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_SchedulingRun_delete BEFORE DELETE ON SchedulingRun BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_ScheduleAssignment_update BEFORE UPDATE ON ScheduleAssignment BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_ScheduleAssignment_delete BEFORE DELETE ON ScheduleAssignment BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_InvigilatorAllocation_update BEFORE UPDATE ON InvigilatorAllocation BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_InvigilatorAllocation_delete BEFORE DELETE ON InvigilatorAllocation BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_ExamOutcome_update BEFORE UPDATE ON ExamOutcome BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_ExamOutcome_delete BEFORE DELETE ON ExamOutcome BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_DecisionEvent_update BEFORE UPDATE ON DecisionEvent BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_DecisionEvent_delete BEFORE DELETE ON DecisionEvent BEGIN SELECT RAISE(ABORT, 'append-only history'); END;

CREATE TRIGGER immutable_pk_Dataset BEFORE UPDATE OF dataset_id ON "Dataset" WHEN NEW."dataset_id" IS NOT OLD."dataset_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Cohort BEFORE UPDATE OF cohort_id ON "Cohort" WHEN NEW."cohort_id" IS NOT OLD."cohort_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Student BEFORE UPDATE OF student_id ON "Student" WHEN NEW."student_id" IS NOT OLD."student_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Course BEFORE UPDATE OF course_id ON "Course" WHEN NEW."course_id" IS NOT OLD."course_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Enrollment BEFORE UPDATE OF enrollment_id ON "Enrollment" WHEN NEW."enrollment_id" IS NOT OLD."enrollment_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Exam BEFORE UPDATE OF exam_id ON "Exam" WHEN NEW."exam_id" IS NOT OLD."exam_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Equipment BEFORE UPDATE OF equipment_id ON "Equipment" WHEN NEW."equipment_id" IS NOT OLD."equipment_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_ExamEquipmentRequirement BEFORE UPDATE OF exam_id,equipment_id ON "ExamEquipmentRequirement" WHEN NEW."exam_id" IS NOT OLD."exam_id" OR NEW."equipment_id" IS NOT OLD."equipment_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Room BEFORE UPDATE OF room_id ON "Room" WHEN NEW."room_id" IS NOT OLD."room_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_RoomCapacity BEFORE UPDATE OF capacity_id ON "RoomCapacity" WHEN NEW."capacity_id" IS NOT OLD."capacity_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_RoomEquipment BEFORE UPDATE OF room_id,equipment_id ON "RoomEquipment" WHEN NEW."room_id" IS NOT OLD."room_id" OR NEW."equipment_id" IS NOT OLD."equipment_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_RoomOpening BEFORE UPDATE OF opening_id ON "RoomOpening" WHEN NEW."opening_id" IS NOT OLD."opening_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_RoomClosure BEFORE UPDATE OF closure_id ON "RoomClosure" WHEN NEW."closure_id" IS NOT OLD."closure_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Invigilator BEFORE UPDATE OF invigilator_id ON "Invigilator" WHEN NEW."invigilator_id" IS NOT OLD."invigilator_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Availability BEFORE UPDATE OF availability_id ON "Availability" WHEN NEW."availability_id" IS NOT OLD."availability_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_Accommodation BEFORE UPDATE OF accommodation_id ON "Accommodation" WHEN NEW."accommodation_id" IS NOT OLD."accommodation_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_ExamRequirement BEFORE UPDATE OF exam_id ON "ExamRequirement" WHEN NEW."exam_id" IS NOT OLD."exam_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_LifecycleEvent BEFORE UPDATE OF event_id ON "LifecycleEvent" WHEN NEW."event_id" IS NOT OLD."event_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_SchedulingRun BEFORE UPDATE OF run_id ON "SchedulingRun" WHEN NEW."run_id" IS NOT OLD."run_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_ScheduleAssignment BEFORE UPDATE OF run_id,assignment_id ON "ScheduleAssignment" WHEN NEW."run_id" IS NOT OLD."run_id" OR NEW."assignment_id" IS NOT OLD."assignment_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_InvigilatorAllocation BEFORE UPDATE OF run_id,assignment_id,invigilator_id ON "InvigilatorAllocation" WHEN NEW."run_id" IS NOT OLD."run_id" OR NEW."assignment_id" IS NOT OLD."assignment_id" OR NEW."invigilator_id" IS NOT OLD."invigilator_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_ExamOutcome BEFORE UPDATE OF run_id,exam_id ON "ExamOutcome" WHEN NEW."run_id" IS NOT OLD."run_id" OR NEW."exam_id" IS NOT OLD."exam_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;

CREATE TRIGGER immutable_pk_DecisionEvent BEFORE UPDATE OF event_id ON "DecisionEvent" WHEN NEW."event_id" IS NOT OLD."event_id" BEGIN SELECT RAISE(ABORT, 'immutable primary key'); END;
