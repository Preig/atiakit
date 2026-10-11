"""Booking data adapters. The CSV adapter is the default and the only one that is built.

Every adapter returns rows that contain only allow-listed columns
(see csv_adapter.BOOKING_COLUMNS) and logs what it dropped.
"""
