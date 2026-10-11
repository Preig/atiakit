"""Stub interfaces for booking platforms. NOT BUILT. Their APIs are not verified here.

Each stub shows the shape a real adapter needs. To build one:
  1. Ask the platform for API access and read its API terms (Contractual: your platform
     agreement and its API or developer terms decide what you may pull and store).
  2. Pull open bookings with only the fields in csv_adapter.BOOKING_COLUMNS.
     Never request guest names, emails, phones, addresses or payment data.
  3. Write them to a CSV with those column names, then run: python pilot.py score --bookings that.csv
     (or return the same typed rows that csv_adapter.load_bookings returns).
  4. Keep the drop log. Test with a sandbox account before touching live data.

A real platform adapter takes weeks, mostly in access, field mapping and testing.
"""
from __future__ import annotations


class PlatformAdapter:
    platform = "generic"
    docs_hint = "Ask the vendor for API documentation and terms."

    def fetch_open_bookings(self):
        raise NotImplementedError(
            "%s adapter is not built. %s Export a CSV instead and use the CSV adapter."
            % (self.platform, self.docs_hint)
        )

    def fetch_outcomes(self):
        raise NotImplementedError("%s adapter is not built." % self.platform)


class FareHarborAdapter(PlatformAdapter):
    platform = "FareHarbor"
    docs_hint = "FareHarbor API access is granted by FareHarbor; request it through your account contact."


class PeekAdapter(PlatformAdapter):
    platform = "Peek"
    docs_hint = "Ask Peek which API or export covers bookings, rate type and channel."


class CheckfrontAdapter(PlatformAdapter):
    platform = "Checkfront"
    docs_hint = "Ask Checkfront for API credentials and the booking fields it exposes."


class CloudbedsAdapter(PlatformAdapter):
    platform = "Cloudbeds"
    docs_hint = "Ask Cloudbeds for API access; lodging data may include more personal fields, so map carefully."


ADAPTERS = {
    "fareharbor": FareHarborAdapter,
    "peek": PeekAdapter,
    "checkfront": CheckfrontAdapter,
    "cloudbeds": CloudbedsAdapter,
}
