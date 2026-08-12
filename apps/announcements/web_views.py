from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.announcements import services
from apps.announcements.forms import AnnouncementForm
from apps.announcements.models import Announcement, AnnouncementRecipient
from apps.core.permissions import has_capability


class AnnouncementListView(LoginRequiredMixin, View):
    def get(self, request):
        can_manage = has_capability(request.user, "announcement.manage")
        if can_manage:
            announcements = Announcement.objects.select_related("created_by").prefetch_related("recipients")[:100]
        else:
            announcements = Announcement.objects.filter(recipients__user=request.user).select_related(
                "created_by"
            ).distinct()[:100]
        return render(request, "announcements/list.html", {"announcements": announcements, "can_manage": can_manage})


class AnnouncementCreateView(LoginRequiredMixin, View):
    template_name = "announcements/create.html"

    def dispatch(self, request, *args, **kwargs):
        if not has_capability(request.user, "announcement.manage"):
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {"form": AnnouncementForm()})

    def post(self, request):
        form = AnnouncementForm(request.POST)
        if not form.is_valid():
            for error in form.non_field_errors():
                messages.error(request, error)
            return render(request, self.template_name, {"form": form})
        employees = form.resolve_employees()
        announcement = services.create_announcement(
            title=form.cleaned_data["title"], content=form.cleaned_data["content"],
            created_by=request.user, employees=employees,
        )
        messages.success(request, f"Announcement sent to {announcement.total_count} employee(s).")
        return redirect(reverse("announcements_web:detail", args=[announcement.pk]))


class AnnouncementDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        can_manage = has_capability(request.user, "announcement.manage")
        announcement = get_object_or_404(Announcement, pk=pk)
        my_receipt = AnnouncementRecipient.objects.filter(
            announcement=announcement, user=request.user
        ).select_related("notification").first()
        if not can_manage and my_receipt is None:
            raise PermissionDenied()

        recipients = None
        if can_manage:
            recipients = announcement.recipients.select_related("employee", "user", "notification").all()
        return render(request, "announcements/detail.html", {
            "announcement": announcement, "can_manage": can_manage,
            "my_receipt": my_receipt, "recipients": recipients,
        })


class AnnouncementMarkReadView(LoginRequiredMixin, View):
    """Same effect as the "Open" link on the Notifications page
    (apps.notifications.web_views.NotificationReadView) -- exists so the
    announcement's own detail page has a direct "Mark as read" action too,
    for anyone who navigated here straight from the Announcements list
    rather than via the notification itself."""

    def post(self, request, pk):
        receipt = get_object_or_404(
            AnnouncementRecipient.objects.select_related("notification"), announcement_id=pk, user=request.user,
        )
        if receipt.notification and not receipt.notification.is_read:
            receipt.notification.is_read = True
            receipt.notification.read_at = timezone.now()
            receipt.notification.save(update_fields=["is_read", "read_at"])
        return redirect(reverse("announcements_web:detail", args=[pk]))
