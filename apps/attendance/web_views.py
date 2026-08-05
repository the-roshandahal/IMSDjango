from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.attendance import services
from apps.attendance.forms import AddTaskForm, DutySheetEditForm, DutySheetForm
from apps.attendance.models import ClockEvent, DutySheet, DutySheetTask
from apps.core.mixins import CapabilityRequiredMixin
from apps.core.permissions import SITE_SCOPE_EXEMPT_ROLES, assigned_site_ids, has_capability
from apps.warehouses.models import Station


def _ensure_station_access(user, station):
    if user.role in SITE_SCOPE_EXEMPT_ROLES:
        return
    if station.pk not in set(assigned_site_ids(user, "station")):
        raise PermissionDenied()


def _visible_stations(user):
    qs = Station.objects.filter(is_active=True)
    if user.role in SITE_SCOPE_EXEMPT_ROLES:
        return qs.order_by("name")
    return qs.filter(pk__in=list(assigned_site_ids(user, "station"))).order_by("name")


def _parse_date(value):
    if value:
        try:
            return timezone.datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            pass
    return timezone.now().date()


# ---------------------------------------------------------------------
# Supervisor-facing: set up duty sheets once, assign or watch employees
# claim them, see who did what per day.
# ---------------------------------------------------------------------

class AttendanceOverviewView(CapabilityRequiredMixin, View):
    capability = "attendance.view"
    template_name = "attendance/overview.html"

    def get(self, request):
        today = timezone.now().date()
        stations = list(_visible_stations(request.user))
        rows = []
        for station in stations:
            active_tasks = DutySheetTask.objects.filter(duty_sheet__station=station, is_active=True)
            completed_today = active_tasks.filter(completions__date=today, completions__is_completed=True).distinct().count()
            rows.append({
                "station": station,
                "clocked_in_count": ClockEvent.objects.filter(station=station, clock_out_at__isnull=True).count(),
                "duty_sheet_count": DutySheet.objects.filter(station=station, is_active=True).count(),
                "open_task_count": active_tasks.count() - completed_today,
            })
        return render(request, self.template_name, {"rows": rows, "today": today})


class StationAttendanceHubView(CapabilityRequiredMixin, View):
    capability = "attendance.view"
    template_name = "attendance/station_hub.html"

    def get(self, request, pk):
        station = get_object_or_404(Station, pk=pk)
        _ensure_station_access(request.user, station)

        date = _parse_date(request.GET.get("date"))
        assignments = services.assignments_for_station(station=station, date=date)
        assignable_employees = list(services.employees_assigned_to_station(station))
        # an employee already claimed on ANOTHER duty sheet that date shouldn't
        # also be offered for this one -- but stays available on their own
        claimed_elsewhere = {a.employee_id: ds_id for ds_id, a in assignments.items()}
        duty_sheets = list(station.duty_sheets.all())
        for ds in duty_sheets:
            ds.today_tasks = services.tasks_with_today_status(duty_sheet=ds, date=date)
            ds.assignment = assignments.get(ds.pk)
            ds.available_employees = [
                e for e in assignable_employees if claimed_elsewhere.get(e.pk) in (None, ds.pk)
            ]
        open_events = ClockEvent.objects.filter(station=station, clock_out_at__isnull=True).select_related("employee", "duty_sheet")

        return render(request, self.template_name, {
            "station": station, "duty_sheets": duty_sheets, "open_events": open_events,
            "date": date, "can_manage": has_capability(request.user, "attendance.duty_sheet.manage"),
        })


class DutySheetCreateView(CapabilityRequiredMixin, View):
    capability = "attendance.duty_sheet.manage"
    template_name = "attendance/duty_sheet_form.html"

    def get(self, request, pk):
        station = get_object_or_404(Station, pk=pk)
        _ensure_station_access(request.user, station)
        return render(request, self.template_name, {"station": station, "form": DutySheetForm(station=station)})

    def post(self, request, pk):
        station = get_object_or_404(Station, pk=pk)
        _ensure_station_access(request.user, station)
        form = DutySheetForm(request.POST, station=station)
        if not form.is_valid():
            return render(request, self.template_name, {"station": station, "form": form})

        duty_sheet = services.create_duty_sheet(
            station=station, name=form.cleaned_data["name"], start_time=form.cleaned_data["start_time"],
            end_time=form.cleaned_data["end_time"], task_descriptions=form.task_descriptions(),
        )
        messages.success(request, f"Duty sheet \"{duty_sheet.name}\" created.")
        return redirect(reverse("attendance_web:station-hub", args=[station.pk]))


class DutySheetEditView(CapabilityRequiredMixin, View):
    capability = "attendance.duty_sheet.manage"
    template_name = "attendance/duty_sheet_edit_form.html"

    def get(self, request, pk):
        duty_sheet = get_object_or_404(DutySheet.objects.select_related("station"), pk=pk)
        _ensure_station_access(request.user, duty_sheet.station)
        return render(request, self.template_name, {
            "duty_sheet": duty_sheet, "form": DutySheetEditForm(instance=duty_sheet),
        })

    def post(self, request, pk):
        duty_sheet = get_object_or_404(DutySheet.objects.select_related("station"), pk=pk)
        _ensure_station_access(request.user, duty_sheet.station)
        form = DutySheetEditForm(request.POST, instance=duty_sheet)
        if not form.is_valid():
            return render(request, self.template_name, {"duty_sheet": duty_sheet, "form": form})
        form.save()
        messages.success(request, f"{duty_sheet.name} updated.")
        return redirect(reverse("attendance_web:duty-sheet-detail", args=[duty_sheet.pk]))


class DutySheetDeleteView(CapabilityRequiredMixin, View):
    """Permanently removes a duty sheet -- only possible while it has no
    real clock-in history (ClockEvent.duty_sheet is PROTECT), same
    audit-trail-can't-be-destroyed rule as everywhere else in the system.
    A duty sheet that's actually been used should be deactivated instead,
    not deleted."""

    capability = "attendance.duty_sheet.manage"

    def post(self, request, pk):
        duty_sheet = get_object_or_404(DutySheet, pk=pk)
        _ensure_station_access(request.user, duty_sheet.station)
        station_id = duty_sheet.station_id
        name = duty_sheet.name
        try:
            duty_sheet.delete()
        except ProtectedError:
            messages.error(
                request,
                f"Can't delete {name} -- it has clock-in history. Deactivate it instead.",
            )
            return redirect(reverse("attendance_web:duty-sheet-detail", args=[pk]))
        messages.success(request, f"{name} deleted.")
        return redirect(reverse("attendance_web:station-hub", args=[station_id]))


class DutySheetToggleActiveView(CapabilityRequiredMixin, View):
    capability = "attendance.duty_sheet.manage"

    def post(self, request, pk):
        duty_sheet = get_object_or_404(DutySheet, pk=pk)
        _ensure_station_access(request.user, duty_sheet.station)
        services.toggle_duty_sheet_active(duty_sheet)
        messages.success(request, f"{duty_sheet.name} {'reactivated' if duty_sheet.is_active else 'deactivated'}.")
        return redirect(reverse("attendance_web:station-hub", args=[duty_sheet.station_id]))


class DutySheetAssignView(CapabilityRequiredMixin, View):
    """A supervisor claiming a duty sheet for an employee ahead of time --
    the other way (besides the employee picking it themself at clock-in)
    a duty sheet gets claimed for a date."""

    capability = "attendance.duty_sheet.manage"

    def post(self, request, pk):
        duty_sheet = get_object_or_404(DutySheet, pk=pk)
        _ensure_station_access(request.user, duty_sheet.station)
        date = _parse_date(request.POST.get("date"))
        employee_id = request.POST.get("employee")

        if employee_id:
            from apps.employees.models import Employee

            employee = get_object_or_404(Employee, pk=employee_id)
            if not services.is_employee_assigned_to_station(employee, duty_sheet.station):
                messages.error(request, f"{employee.full_name} isn't assigned to this station.")
                return redirect(reverse("attendance_web:station-hub", args=[duty_sheet.station_id]) + f"?date={date}")
            services.assign_duty_sheet(duty_sheet=duty_sheet, date=date, employee=employee, assigned_by=request.user)
            messages.success(request, f"{duty_sheet.name} assigned to {employee.full_name} for {date}.")
        else:
            services.unassign_duty_sheet(duty_sheet=duty_sheet, date=date)
            messages.success(request, f"{duty_sheet.name} unassigned for {date}.")
        return redirect(reverse("attendance_web:station-hub", args=[duty_sheet.station_id]) + f"?date={date}")


class DutySheetAddTaskView(CapabilityRequiredMixin, View):
    capability = "attendance.duty_sheet.manage"

    def post(self, request, pk):
        duty_sheet = get_object_or_404(DutySheet, pk=pk)
        _ensure_station_access(request.user, duty_sheet.station)
        form = AddTaskForm(request.POST)
        if form.is_valid():
            services.add_task(duty_sheet=duty_sheet, description=form.cleaned_data["description"])
            messages.success(request, "Task added.")
        else:
            messages.error(request, "Enter a task description.")
        return redirect(reverse("attendance_web:duty-sheet-detail", args=[pk]))


class DutySheetTaskToggleActiveView(CapabilityRequiredMixin, View):
    capability = "attendance.duty_sheet.manage"

    def post(self, request, pk):
        task = get_object_or_404(DutySheetTask, pk=pk)
        _ensure_station_access(request.user, task.duty_sheet.station)
        services.toggle_task_active(task)
        messages.success(request, f"Task {'reactivated' if task.is_active else 'retired'}.")
        return redirect(reverse("attendance_web:duty-sheet-detail", args=[task.duty_sheet_id]))


class DutySheetDetailView(CapabilityRequiredMixin, View):
    capability = "attendance.view"
    template_name = "attendance/duty_sheet_detail.html"

    def get(self, request, pk):
        duty_sheet = get_object_or_404(DutySheet.objects.select_related("station"), pk=pk)
        _ensure_station_access(request.user, duty_sheet.station)
        date = _parse_date(request.GET.get("date"))
        tasks = services.tasks_with_today_status(duty_sheet=duty_sheet, date=date, include_inactive=True)
        return render(request, self.template_name, {
            "duty_sheet": duty_sheet, "tasks": tasks, "date": date,
            "can_manage": has_capability(request.user, "attendance.duty_sheet.manage"),
            "add_task_form": AddTaskForm(),
        })


# ---------------------------------------------------------------------
# Employee-facing: log in, clock in/out, tick off duty sheet tasks. One
# screen (`/attendance/clock/`) for everything -- an NFC tag is just a
# shortcut that lands here with the station pre-picked (see KioskEntryView).
# ---------------------------------------------------------------------

def _clock_screen_context(request, station):
    employee = getattr(request.user, "employee_profile", None)
    if employee is None or not employee.is_active:
        return {"station": station, "no_employee_profile": True}
    if not services.is_employee_assigned_to_station(employee, station):
        return {"station": station, "not_assigned": True}

    open_event = services.open_clock_event_for(employee)
    if open_event and open_event.station_id != station.id:
        return {"station": station, "clocked_in_elsewhere": open_event}

    if open_event:
        own_tasks = services.tasks_with_today_status(duty_sheet=open_event.duty_sheet, date=open_event.shift_date)
        carried_over = services.carried_over_tasks(
            station=station, exclude_duty_sheet=open_event.duty_sheet, date=open_event.shift_date,
        )
        return {
            "station": station, "employee": employee, "open_event": open_event,
            "own_tasks": own_tasks, "carried_over_tasks": carried_over,
        }

    # Already claimed (self-picked earlier, or a supervisor assigned it) --
    # go straight to clocking in, no need to choose again.
    assigned = services.my_assigned_duty_sheets(station=station, employee=employee)
    if assigned:
        return {"station": station, "employee": employee, "assigned_duty_sheets": assigned}

    duty_sheets = services.pickable_duty_sheets(station=station, employee=employee)
    return {"station": station, "employee": employee, "duty_sheets": duty_sheets}


def _visible_employee_stations(employee):
    if not employee.user_id:
        return Station.objects.none()
    ids = list(assigned_site_ids(employee.user, "station"))
    return Station.objects.filter(pk__in=ids, is_active=True).order_by("name")


class SelfClockView(CapabilityRequiredMixin, View):
    capability = "attendance.clock"
    template_name = "attendance/clock_screen.html"

    def get(self, request):
        employee = getattr(request.user, "employee_profile", None)
        if employee is None:
            return render(request, self.template_name, {"no_employee_profile": True})

        station_id = request.GET.get("station")
        stations = list(_visible_employee_stations(employee))

        if station_id:
            # An explicit station was requested (e.g. an NFC tag deep-link) --
            # resolve it as a real station even if it's not one of the
            # employee's own, so _clock_screen_context can give the proper
            # "not assigned here" message instead of silently falling back.
            station = Station.objects.filter(pk=station_id, is_active=True).first()
            if station is None:
                return render(request, self.template_name, {"stations": stations, "pick_station": True})
            ctx = _clock_screen_context(request, station)
            ctx["other_stations"] = stations if len(stations) > 1 else []
            return render(request, self.template_name, ctx)

        if not stations:
            return render(request, self.template_name, {"no_stations": True})
        if len(stations) == 1:
            ctx = _clock_screen_context(request, stations[0])
            return render(request, self.template_name, ctx)
        return render(request, self.template_name, {"stations": stations, "pick_station": True})

    def post(self, request):
        employee = getattr(request.user, "employee_profile", None)
        if employee is None:
            raise PermissionDenied()
        station = get_object_or_404(Station, pk=request.POST.get("station_id"))
        duty_sheet = get_object_or_404(DutySheet, pk=request.POST.get("duty_sheet"), station=station)
        method = ClockEvent.Method.NFC if request.POST.get("via") == "nfc" else ClockEvent.Method.WEB
        try:
            services.clock_in(employee=employee, station=station, duty_sheet=duty_sheet, method=method)
            messages.success(request, f"Clocked in for {duty_sheet.name}.")
        except services.ClockInError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("attendance_web:clock") + f"?station={station.pk}")


class KioskEntryView(View):
    """NFC entry point on a SHARED device -- the tag itself can't tell who's
    tapping it, so this is where that gets resolved: pick your name, enter
    your PIN, and that PIN-check IS the login (no username/password typed,
    ever). Once identified, it hands off to the normal clock screen exactly
    like a regular session would.

    If the browser is already logged in (a previous tap on this same
    device that hasn't clocked out yet, or someone using their own phone
    normally), skip straight through -- that's the "tap again, see your
    tasks" behaviour."""

    template_name = "attendance/kiosk_identify.html"

    def get(self, request, token):
        station = get_object_or_404(Station, nfc_token=token, is_active=True)
        if request.user.is_authenticated:
            return redirect(reverse("attendance_web:clock") + f"?station={station.pk}&via=nfc")

        employees = services.kiosk_eligible_employees(station)
        picked_id = request.GET.get("employee")
        if picked_id:
            picked = employees.filter(pk=picked_id).first()
            if picked:
                return render(request, self.template_name, {"station": station, "token": token, "picked": picked})
        return render(request, self.template_name, {"station": station, "token": token, "employees": employees})

    def post(self, request, token):
        from apps.employees import services as employee_services

        station = get_object_or_404(Station, nfc_token=token, is_active=True)
        if request.user.is_authenticated:
            return redirect(reverse("attendance_web:clock") + f"?station={station.pk}&via=nfc")

        employees = services.kiosk_eligible_employees(station)
        employee = get_object_or_404(employees, pk=request.POST.get("employee"))
        pin = request.POST.get("pin", "")

        result = employee_services.verify_kiosk_pin(employee=employee, pin=pin)
        if result != employee_services.PinLoginResult.OK:
            error_messages = {
                employee_services.PinLoginResult.LOCKED: "Too many wrong attempts -- ask your supervisor to unlock your account.",
                employee_services.PinLoginResult.INACTIVE: "This account isn't active. Ask your supervisor.",
                employee_services.PinLoginResult.NO_PIN_SET: "No PIN set up yet. Ask your supervisor.",
            }
            messages.error(request, error_messages.get(result, "Incorrect PIN."))
            back = reverse("attendance_web:kiosk", args=[token])
            if result == employee_services.PinLoginResult.INVALID_PIN:
                back += f"?employee={employee.pk}"  # let them retry without re-picking their name
            return redirect(back)

        login(request, employee.user)
        request.session["kiosk_token"] = token
        return redirect(reverse("attendance_web:clock") + f"?station={station.pk}&via=nfc")


class ClockOutView(LoginRequiredMixin, View):
    def post(self, request, pk):
        employee = getattr(request.user, "employee_profile", None)
        clock_event = get_object_or_404(ClockEvent, pk=pk, employee=employee)
        kiosk_token = request.session.get("kiosk_token")
        try:
            services.clock_out(clock_event=clock_event)
            messages.success(request, "Clocked out.")
            if kiosk_token:
                # Signed in via a shared-device PIN tap -- don't leave the
                # device logged in as this person once they're done.
                logout(request)
                messages.success(request, "Tap the tag again to sign someone else in.")
                return redirect(reverse("attendance_web:kiosk", args=[kiosk_token]))
        except services.ClockInError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("attendance_web:clock") + f"?station={clock_event.station_id}")


class DutySheetTaskCompleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        employee = getattr(request.user, "employee_profile", None)
        task = get_object_or_404(DutySheetTask, pk=pk)
        open_event = services.open_clock_event_for(employee) if employee else None
        # Only the duty sheet an employee is actually clocked in for is
        # theirs to tick off -- leftover tasks from another duty sheet are
        # shown as a heads-up for whoever picks that one up next, not
        # something a passer-by can tick on someone else's behalf.
        if not open_event or open_event.duty_sheet_id != task.duty_sheet_id:
            raise PermissionDenied()
        services.mark_task_complete(
            task=task, employee=employee, clock_event=open_event, date=open_event.shift_date,
            notes=request.POST.get("notes", ""), photo=request.FILES.get("photo"),
        )
        return redirect(reverse("attendance_web:clock") + f"?station={task.duty_sheet.station_id}")


class DutySheetTaskUndoView(LoginRequiredMixin, View):
    def post(self, request, pk):
        employee = getattr(request.user, "employee_profile", None)
        task = get_object_or_404(DutySheetTask, pk=pk)
        open_event = services.open_clock_event_for(employee) if employee else None
        if not open_event or open_event.duty_sheet_id != task.duty_sheet_id:
            raise PermissionDenied()
        services.mark_task_incomplete(task=task, date=open_event.shift_date)
        return redirect(reverse("attendance_web:clock") + f"?station={task.duty_sheet.station_id}")
