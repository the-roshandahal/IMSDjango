from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from apps.trains import services
from apps.trains.services import TrainApiError


class TrainLookupView(LoginRequiredMixin, TemplateView):
    """Live train departure lookup for any station (SRS out-of-scope
    extra, added on request) -- not gated behind a capability, any
    signed-in user can look up a station."""

    template_name = "trains/lookup.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "").strip()
        station_id = self.request.GET.get("station", "").strip()
        station_name = self.request.GET.get("name", "").strip()

        ctx["query"] = query
        ctx["station_id"] = station_id
        ctx["station_name"] = station_name

        try:
            if station_id:
                ctx["board"] = services.get_departure_board(station_id, station_name=station_name or None)
            elif query:
                ctx["results"] = services.search_stations(query)
        except TrainApiError as exc:
            messages.error(self.request, str(exc))

        return ctx
