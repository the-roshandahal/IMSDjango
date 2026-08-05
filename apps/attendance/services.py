from django.db import IntegrityError
from django.utils import timezone

from apps.attendance.models import ClockEvent, DutySheet, DutySheetAssignment, DutySheetTask, TaskCompletion, operating_date_for


class ClockInError(Exception):
    """Raised for any reason clocking in/out can't proceed -- always caught
    and shown as a plain message, never lets an inconsistent ClockEvent
    through."""


def employees_assigned_to_station(station):
    """Employees who can clock in at this station -- reuses SiteAssignment
    (already exactly "which sites can this user act on") via each
    employee's linked login, rather than a second assignment table."""
    from apps.employees.models import Employee

    return Employee.objects.filter(
        is_active=True, user__isnull=False, user__site_assignments__station=station
    ).distinct().order_by("first_name", "last_name")


def is_employee_assigned_to_station(employee, station) -> bool:
    if not employee.user_id:
        return False
    return employee.user.site_assignments.filter(station=station).exists()


def kiosk_eligible_employees(station):
    """Employees who can identify themselves at the shared NFC kiosk --
    assigned to the station AND have a PIN set up (see set_kiosk_pin)."""
    return employees_assigned_to_station(station).exclude(kiosk_pin_hash="")


def create_duty_sheet(*, station, name, start_time, end_time, task_descriptions, order=0):
    """One-off setup, done from the station page -- the resulting checklist
    is permanent and reused every day (see TaskCompletion for what varies
    day to day)."""
    duty_sheet = DutySheet.objects.create(station=station, name=name, start_time=start_time, end_time=end_time, order=order)
    tasks = [
        DutySheetTask(duty_sheet=duty_sheet, description=desc.strip(), order=i)
        for i, desc in enumerate(task_descriptions) if desc.strip()
    ]
    DutySheetTask.objects.bulk_create(tasks)
    return duty_sheet


def add_task(*, duty_sheet, description):
    last = duty_sheet.tasks.order_by("-order").first()
    order = (last.order + 1) if last else 0
    return DutySheetTask.objects.create(duty_sheet=duty_sheet, description=description, order=order)


def toggle_task_active(task: DutySheetTask):
    task.is_active = not task.is_active
    task.save(update_fields=["is_active"])
    return task


def toggle_duty_sheet_active(duty_sheet: DutySheet):
    duty_sheet.is_active = not duty_sheet.is_active
    duty_sheet.save(update_fields=["is_active"])
    return duty_sheet


def tasks_with_today_status(*, duty_sheet, date=None, include_inactive=False):
    """This duty sheet's tasks, each annotated with `.today` (the
    TaskCompletion for `date`, or None if nobody has touched it yet).
    Active-only by default (what an employee should see and act on);
    `include_inactive` is for the supervisor's manage page, which also
    needs to show retired tasks so there's a way back to reactivate them."""
    date = date or timezone.now().date()
    qs = duty_sheet.tasks.all() if include_inactive else duty_sheet.tasks.filter(is_active=True)
    tasks = list(qs)
    completions = {c.task_id: c for c in TaskCompletion.objects.filter(task__duty_sheet=duty_sheet, date=date)}
    for task in tasks:
        task.today = completions.get(task.pk)
    return tasks


def carried_over_tasks(*, station, exclude_duty_sheet=None, date=None):
    """Active tasks, from this station's OTHER duty sheets, not yet done
    today -- what the next person on shift needs to see and can pick up.
    A task with no TaskCompletion row at all for today counts as not done,
    same as one with an explicit is_completed=False row."""
    date = date or timezone.now().date()
    tasks = DutySheetTask.objects.filter(duty_sheet__station=station, is_active=True).select_related("duty_sheet")
    if exclude_duty_sheet is not None:
        tasks = tasks.exclude(duty_sheet=exclude_duty_sheet)
    completed_today_ids = set(
        TaskCompletion.objects.filter(task__in=tasks, date=date, is_completed=True).values_list("task_id", flat=True)
    )
    return [t for t in tasks if t.pk not in completed_today_ids]


def open_clock_event_for(employee):
    return ClockEvent.objects.filter(employee=employee, clock_out_at__isnull=True).select_related("station", "duty_sheet").first()


def assign_duty_sheet(*, duty_sheet, date, employee, assigned_by):
    """Claims a duty sheet for a date -- either the employee claiming it
    themself at clock-in, or a supervisor assigning it ahead of time.
    Reassigning (a supervisor picking someone new) just overwrites."""
    assignment, _ = DutySheetAssignment.objects.update_or_create(
        duty_sheet=duty_sheet, date=date, defaults={"employee": employee, "assigned_by": assigned_by},
    )
    return assignment


def unassign_duty_sheet(*, duty_sheet, date):
    DutySheetAssignment.objects.filter(duty_sheet=duty_sheet, date=date).delete()


def assignments_for_station(*, station, date=None):
    """{duty_sheet_id: DutySheetAssignment} for this station on this date --
    for supervisor browsing, which works by plain calendar date (they pick
    a date and see it, rather than the per-sheet overnight logic below)."""
    date = date or timezone.now().date()
    return {
        a.duty_sheet_id: a
        for a in DutySheetAssignment.objects.filter(duty_sheet__station=station, date=date).select_related("employee")
    }


def my_assigned_duty_sheets(*, station, employee):
    """Duty sheets already claimed BY this employee, checked against each
    sheet's own current operating date (so an overnight shift they claimed
    last evening still counts after midnight). If this returns anything,
    the employee should go straight to clocking in -- no need to pick."""
    sheets = station.duty_sheets.filter(is_active=True)
    result = []
    for ds in sheets:
        if DutySheetAssignment.objects.filter(duty_sheet=ds, date=operating_date_for(ds), employee=employee).exists():
            result.append(ds)
    return result


def pickable_duty_sheets(*, station, employee):
    """Duty sheets nobody has claimed yet, each checked against its own
    current operating date -- what shows in the picker when the employee
    has no pre-existing claim of their own (see my_assigned_duty_sheets)."""
    sheets = station.duty_sheets.filter(is_active=True)
    result = []
    for ds in sheets:
        if not DutySheetAssignment.objects.filter(duty_sheet=ds, date=operating_date_for(ds)).exists():
            result.append(ds)
    return result


def clock_in(*, employee, station, duty_sheet, method=ClockEvent.Method.WEB):
    if duty_sheet.station_id != station.id:
        raise ClockInError("That duty sheet doesn't belong to this station.")
    if not duty_sheet.is_active:
        raise ClockInError("That duty sheet is no longer active.")
    if not is_employee_assigned_to_station(employee, station):
        raise ClockInError("You're not assigned to this station.")
    if open_clock_event_for(employee):
        raise ClockInError("Already clocked in -- clock out first.")

    shift_date = operating_date_for(duty_sheet)
    existing = DutySheetAssignment.objects.filter(duty_sheet=duty_sheet, date=shift_date).first()
    if existing and existing.employee_id != employee.id:
        raise ClockInError(f"{duty_sheet.name} is already taken by {existing.employee.full_name} today.")
    if not existing:
        try:
            assign_duty_sheet(duty_sheet=duty_sheet, date=shift_date, employee=employee, assigned_by=employee.user)
        except IntegrityError:
            # lost a race with someone else claiming it in the same instant
            winner = DutySheetAssignment.objects.filter(duty_sheet=duty_sheet, date=shift_date).first()
            name = winner.employee.full_name if winner else "someone else"
            raise ClockInError(f"{duty_sheet.name} was just taken by {name}.")

    try:
        return ClockEvent.objects.create(
            employee=employee, station=station, duty_sheet=duty_sheet, clock_in_method=method,
        )
    except IntegrityError:
        raise ClockInError("Already clocked in -- clock out first.")


def clock_out(*, clock_event, method=ClockEvent.Method.WEB):
    if not clock_event.is_open:
        raise ClockInError("Already clocked out.")
    clock_event.clock_out_at = timezone.now()
    clock_event.clock_out_method = method
    clock_event.save(update_fields=["clock_out_at", "clock_out_method"])
    return clock_event


def mark_task_complete(*, task: DutySheetTask, employee, clock_event, date=None, notes="", photo=None):
    date = date or timezone.now().date()
    completion, _ = TaskCompletion.objects.get_or_create(task=task, date=date)
    completion.is_completed = True
    completion.completed_by = employee
    completion.completed_at = timezone.now()
    completion.completed_during_clock_event = clock_event
    if notes:
        completion.notes = notes
    if photo:
        completion.photo = photo
    completion.save()
    return completion


def mark_task_incomplete(*, task: DutySheetTask, date=None):
    date = date or timezone.now().date()
    TaskCompletion.objects.filter(task=task, date=date).update(
        is_completed=False, completed_by=None, completed_at=None, completed_during_clock_event=None,
    )
