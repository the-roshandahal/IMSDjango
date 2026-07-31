from datetime import datetime

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from apps.trains import services
from apps.trains.services import SYDNEY_TZ, TrainApiError


class TrainLookupView(LoginRequiredMixin, TemplateView):
    """Live train departure lookup for any station, plus a point-to-point
    trip planner (SRS out-of-scope extras, added on request) -- neither
    is gated behind a capability, any signed-in user can use them."""

    template_name = "trains/lookup.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        self._add_station_lookup(ctx)
        self._add_trip_planner(ctx)
        return ctx

    def _add_station_lookup(self, ctx):
        query = self.request.GET.get("q", "").strip()
        station_id = self.request.GET.get("station", "").strip()
        station_name = self.request.GET.get("name", "").strip()

        ctx["query"] = query
        ctx["station_id"] = station_id
        ctx["station_name"] = station_name

        try:
            if station_id:
                board = services.get_departure_board(station_id, station_name=station_name or None)
                last_trains = services.get_last_trains_today(station_id, station_name=station_name or None)
                for platform in board["platforms"]:
                    platform["last_train_today"] = last_trains.get(platform["platform"])
                ctx["board"] = board
            elif query:
                ctx["results"] = services.search_stations(query)
        except TrainApiError as exc:
            messages.error(self.request, str(exc))

    def _add_trip_planner(self, ctx):
        from_q = self.request.GET.get("from_q", "").strip()
        to_q = self.request.GET.get("to_q", "").strip()
        when_str = self.request.GET.get("when", "").strip()
        arrive_by = self.request.GET.get("arrive_by") == "on"

        ctx["from_q"] = from_q
        ctx["to_q"] = to_q
        ctx["when"] = when_str
        ctx["arrive_by"] = arrive_by

        if not (from_q or to_q):
            return

        try:
            origin = services.resolve_station(from_q) if from_q else None
            destination = services.resolve_station(to_q) if to_q else None
            ctx["trip_origin"] = origin
            ctx["trip_destination"] = destination
            if from_q and not origin:
                ctx["trip_origin_candidates"] = services.search_stations(from_q)
            if to_q and not destination:
                ctx["trip_destination_candidates"] = services.search_stations(to_q)

            if origin and destination:
                when_dt = None
                if when_str:
                    try:
                        naive = datetime.strptime(when_str, "%Y-%m-%dT%H:%M")
                        when_dt = naive.replace(tzinfo=SYDNEY_TZ) if SYDNEY_TZ else naive
                    except ValueError:
                        messages.error(self.request, "That date/time didn't parse -- leaving it blank uses now.")
                ctx["journeys"] = services.get_trip(origin["id"], destination["id"], when=when_dt, arrive_by=arrive_by)
        except TrainApiError as exc:
            messages.error(self.request, str(exc))
