"""The strict temporal-slider contract: journey-temporal-v1.

This criterion judges the observation the committed collector
(temporal_capture.py) writes, against the Python 1.66.1 wire measured on
2026-10-25 with the official frontend and recorded in .codex/compatibility.md
(Slider type coverage). The collector states no verdict; this module owns it:

* six sliders render with the exact measured wire configs: DATE/TIME/DATETIME
  enums, epoch-microsecond doubles, value-+-14-day default windows (a
  datetime window keeps the time-of-day and microseconds), the full-day
  off-grid time window, 15-minute time steps, and a range window hanging off
  the first endpoint alone;
* every stage carries exactly one rerun_script whose widget-state snapshot
  equals the accumulated measured values (the page-load run sends no states);
  End/Home land on the measured points (a time snaps to the 23:45 grid, not
  the off-grid max);
* the DOM echoes the measured Python-repr strings, the hidden native range
  inputs hold the frontend's grid-snapped values, no exception renders, and
  every stage's run finishes FINISHED_SUCCESSFULLY.
"""

from __future__ import annotations

import hashlib
import pathlib

TEMPORAL_CASE = "temporal-sequence"
TEMPORAL_CONTRACT = "journey-temporal-v1"

TEMPORAL_STAGES = ["01-load", "02-date-end", "03-date-home", "04-time-end", "05-time-home", "06-datetime-end", "07-datetime-home", "08-date-range-left-home", "09-date-range-right-end", "10-time-range-left-home", "11-time-range-right-end", "12-datetime-range-left-home", "13-datetime-range-right-end"]

# The exact measured wire config of each slider on first render.
TEMPORAL_WIRE = {
 "date": {
  "format": "YYYY-MM-DD",
  "dataType": "DATE",
  "default": [
   1710460800000000.0
  ],
  "min": 1709251200000000.0,
  "max": 1711670400000000.0,
  "step": 86400000000.0
 },
 "time": {
  "format": "HH:mm",
  "dataType": "TIME",
  "default": [
   946729807123456.0
  ],
  "min": 946684800000000.0,
  "max": 946771199999999.0,
  "step": 900000000.0
 },
 "datetime": {
  "format": "YYYY-MM-DD",
  "dataType": "DATETIME",
  "default": [
   1710505807123456.0
  ],
  "min": 1709296207123456.0,
  "max": 1711715407123456.0,
  "step": 86400000000.0
 },
 "date-range": {
  "format": "YYYY-MM-DD",
  "dataType": "DATE",
  "default": [
   1710028800000000.0,
   1710892800000000.0
  ],
  "min": 1708819200000000.0,
  "max": 1711238400000000.0,
  "step": 86400000000.0
 },
 "time-range": {
  "format": "HH:mm",
  "dataType": "TIME",
  "default": [
   946718100000000.0,
   946748700000000.0
  ],
  "min": 946684800000000.0,
  "max": 946771199999999.0,
  "step": 900000000.0
 },
 "datetime-range": {
  "format": "YYYY-MM-DD",
  "dataType": "DATETIME",
  "default": [
   1710063007123456.0,
   1710956707654321.0
  ],
  "min": 1708853407123456.0,
  "max": 1711272607123456.0,
  "step": 86400000000.0
 }
}

# The widget-state snapshot each stage's single rerun_script carries. The
# initial page-load run sends one rerun_script with no states at all.
TEMPORAL_STATES = {
 "01-load": {},
 "02-date-end": {
  "date": [
   1711670400000000.0
  ],
  "time": [
   946729807123456.0
  ],
  "datetime": [
   1710505807123456.0
  ],
  "date-range": [
   1710028800000000.0,
   1710892800000000.0
  ],
  "time-range": [
   946718100000000.0,
   946748700000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "03-date-home": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946729807123456.0
  ],
  "datetime": [
   1710505807123456.0
  ],
  "date-range": [
   1710028800000000.0,
   1710892800000000.0
  ],
  "time-range": [
   946718100000000.0,
   946748700000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "04-time-end": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946770300000000.0
  ],
  "datetime": [
   1710505807123456.0
  ],
  "date-range": [
   1710028800000000.0,
   1710892800000000.0
  ],
  "time-range": [
   946718100000000.0,
   946748700000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "05-time-home": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946684800000000.0
  ],
  "datetime": [
   1710505807123456.0
  ],
  "date-range": [
   1710028800000000.0,
   1710892800000000.0
  ],
  "time-range": [
   946718100000000.0,
   946748700000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "06-datetime-end": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946684800000000.0
  ],
  "datetime": [
   1711715407123456.0
  ],
  "date-range": [
   1710028800000000.0,
   1710892800000000.0
  ],
  "time-range": [
   946718100000000.0,
   946748700000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "07-datetime-home": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946684800000000.0
  ],
  "datetime": [
   1709296207123456.0
  ],
  "date-range": [
   1710028800000000.0,
   1710892800000000.0
  ],
  "time-range": [
   946718100000000.0,
   946748700000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "08-date-range-left-home": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946684800000000.0
  ],
  "datetime": [
   1709296207123456.0
  ],
  "date-range": [
   1708819200000000.0,
   1710892800000000.0
  ],
  "time-range": [
   946718100000000.0,
   946748700000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "09-date-range-right-end": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946684800000000.0
  ],
  "datetime": [
   1709296207123456.0
  ],
  "date-range": [
   1708819200000000.0,
   1711238400000000.0
  ],
  "time-range": [
   946718100000000.0,
   946748700000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "10-time-range-left-home": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946684800000000.0
  ],
  "datetime": [
   1709296207123456.0
  ],
  "date-range": [
   1708819200000000.0,
   1711238400000000.0
  ],
  "time-range": [
   946684800000000.0,
   946748700000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "11-time-range-right-end": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946684800000000.0
  ],
  "datetime": [
   1709296207123456.0
  ],
  "date-range": [
   1708819200000000.0,
   1711238400000000.0
  ],
  "time-range": [
   946684800000000.0,
   946770300000000.0
  ],
  "datetime-range": [
   1710063007123456.0,
   1710956707654321.0
  ]
 },
 "12-datetime-range-left-home": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946684800000000.0
  ],
  "datetime": [
   1709296207123456.0
  ],
  "date-range": [
   1708819200000000.0,
   1711238400000000.0
  ],
  "time-range": [
   946684800000000.0,
   946770300000000.0
  ],
  "datetime-range": [
   1708853407123456.0,
   1710927007123456.0
  ]
 },
 "13-datetime-range-right-end": {
  "date": [
   1709251200000000.0
  ],
  "time": [
   946684800000000.0
  ],
  "datetime": [
   1709296207123456.0
  ],
  "date-range": [
   1708819200000000.0,
   1711238400000000.0
  ],
  "time-range": [
   946684800000000.0,
   946770300000000.0
  ],
  "datetime-range": [
   1708853407123456.0,
   1711272607123456.0
  ]
 }
}

# The touched slider of each driven stage and its measured landing value.
TEMPORAL_TOUCHED = {
 "02-date-end": [
  "date",
  [
   1711670400000000.0
  ]
 ],
 "03-date-home": [
  "date",
  [
   1709251200000000.0
  ]
 ],
 "04-time-end": [
  "time",
  [
   946770300000000.0
  ]
 ],
 "05-time-home": [
  "time",
  [
   946684800000000.0
  ]
 ],
 "06-datetime-end": [
  "datetime",
  [
   1711715407123456.0
  ]
 ],
 "07-datetime-home": [
  "datetime",
  [
   1709296207123456.0
  ]
 ],
 "08-date-range-left-home": [
  "date-range",
  [
   1708819200000000.0,
   1710892800000000.0
  ]
 ],
 "09-date-range-right-end": [
  "date-range",
  [
   1708819200000000.0,
   1711238400000000.0
  ]
 ],
 "10-time-range-left-home": [
  "time-range",
  [
   946684800000000.0,
   946748700000000.0
  ]
 ],
 "11-time-range-right-end": [
  "time-range",
  [
   946684800000000.0,
   946770300000000.0
  ]
 ],
 "12-datetime-range-left-home": [
  "datetime-range",
  [
   1708853407123456.0,
   1710927007123456.0
  ]
 ],
 "13-datetime-range-right-end": [
  "datetime-range",
  [
   1708853407123456.0,
   1711272607123456.0
  ]
 ]
}

# The hidden native range inputs the official frontend holds after each
# stage: grid-snapped display values, distinct from the wire states.
TEMPORAL_INPUTS = {
 "01-load": {
  "date": [
   "1710460800000000"
  ],
  "time": [
   "946729800000000"
  ],
  "datetime": [
   "1710505807123456"
  ],
  "date-range": [
   "1710028800000000",
   "1710892800000000"
  ],
  "time-range": [
   "946718100000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "02-date-end": {
  "date": [
   "1711670400000000"
  ],
  "time": [
   "946729800000000"
  ],
  "datetime": [
   "1710505807123456"
  ],
  "date-range": [
   "1710028800000000",
   "1710892800000000"
  ],
  "time-range": [
   "946718100000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "03-date-home": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946729800000000"
  ],
  "datetime": [
   "1710505807123456"
  ],
  "date-range": [
   "1710028800000000",
   "1710892800000000"
  ],
  "time-range": [
   "946718100000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "04-time-end": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946770300000000"
  ],
  "datetime": [
   "1710505807123456"
  ],
  "date-range": [
   "1710028800000000",
   "1710892800000000"
  ],
  "time-range": [
   "946718100000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "05-time-home": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946684800000000"
  ],
  "datetime": [
   "1710505807123456"
  ],
  "date-range": [
   "1710028800000000",
   "1710892800000000"
  ],
  "time-range": [
   "946718100000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "06-datetime-end": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946684800000000"
  ],
  "datetime": [
   "1711715407123456"
  ],
  "date-range": [
   "1710028800000000",
   "1710892800000000"
  ],
  "time-range": [
   "946718100000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "07-datetime-home": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946684800000000"
  ],
  "datetime": [
   "1709296207123456"
  ],
  "date-range": [
   "1710028800000000",
   "1710892800000000"
  ],
  "time-range": [
   "946718100000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "08-date-range-left-home": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946684800000000"
  ],
  "datetime": [
   "1709296207123456"
  ],
  "date-range": [
   "1708819200000000",
   "1710892800000000"
  ],
  "time-range": [
   "946718100000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "09-date-range-right-end": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946684800000000"
  ],
  "datetime": [
   "1709296207123456"
  ],
  "date-range": [
   "1708819200000000",
   "1711238400000000"
  ],
  "time-range": [
   "946718100000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "10-time-range-left-home": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946684800000000"
  ],
  "datetime": [
   "1709296207123456"
  ],
  "date-range": [
   "1708819200000000",
   "1711238400000000"
  ],
  "time-range": [
   "946684800000000",
   "946748700000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "11-time-range-right-end": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946684800000000"
  ],
  "datetime": [
   "1709296207123456"
  ],
  "date-range": [
   "1708819200000000",
   "1711238400000000"
  ],
  "time-range": [
   "946684800000000",
   "946770300000000"
  ],
  "datetime-range": [
   "1710063007123456",
   "1710927007123456"
  ]
 },
 "12-datetime-range-left-home": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946684800000000"
  ],
  "datetime": [
   "1709296207123456"
  ],
  "date-range": [
   "1708819200000000",
   "1711238400000000"
  ],
  "time-range": [
   "946684800000000",
   "946770300000000"
  ],
  "datetime-range": [
   "1708853407123456",
   "1710927007123456"
  ]
 },
 "13-datetime-range-right-end": {
  "date": [
   "1709251200000000"
  ],
  "time": [
   "946684800000000"
  ],
  "datetime": [
   "1709296207123456"
  ],
  "date-range": [
   "1708819200000000",
   "1711238400000000"
  ],
  "time-range": [
   "946684800000000",
   "946770300000000"
  ],
  "datetime-range": [
   "1708853407123456",
   "1711272607123456"
  ]
 }
}

# The measured Python-repr echo lines of each stage end state, identical on
# both runtimes because the driven applications are mirrors.
TEMPORAL_REPRS = {
 "01-load": [
  "date=datetime.date(2024, 3, 15)|date",
  "time=datetime.time(12, 30, 7, 123456)|time",
  "datetime=datetime.datetime(2024, 3, 15, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 3, 10), datetime.date(2024, 3, 20))|tuple",
  "time_pair=(datetime.time(9, 15), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "02-date-end": [
  "date=datetime.date(2024, 3, 29)|date",
  "time=datetime.time(12, 30, 7, 123456)|time",
  "datetime=datetime.datetime(2024, 3, 15, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 3, 10), datetime.date(2024, 3, 20))|tuple",
  "time_pair=(datetime.time(9, 15), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "03-date-home": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(12, 30, 7, 123456)|time",
  "datetime=datetime.datetime(2024, 3, 15, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 3, 10), datetime.date(2024, 3, 20))|tuple",
  "time_pair=(datetime.time(9, 15), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "04-time-end": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(23, 45)|time",
  "datetime=datetime.datetime(2024, 3, 15, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 3, 10), datetime.date(2024, 3, 20))|tuple",
  "time_pair=(datetime.time(9, 15), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "05-time-home": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(0, 0)|time",
  "datetime=datetime.datetime(2024, 3, 15, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 3, 10), datetime.date(2024, 3, 20))|tuple",
  "time_pair=(datetime.time(9, 15), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "06-datetime-end": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(0, 0)|time",
  "datetime=datetime.datetime(2024, 3, 29, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 3, 10), datetime.date(2024, 3, 20))|tuple",
  "time_pair=(datetime.time(9, 15), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "07-datetime-home": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(0, 0)|time",
  "datetime=datetime.datetime(2024, 3, 1, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 3, 10), datetime.date(2024, 3, 20))|tuple",
  "time_pair=(datetime.time(9, 15), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "08-date-range-left-home": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(0, 0)|time",
  "datetime=datetime.datetime(2024, 3, 1, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 2, 25), datetime.date(2024, 3, 20))|tuple",
  "time_pair=(datetime.time(9, 15), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "09-date-range-right-end": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(0, 0)|time",
  "datetime=datetime.datetime(2024, 3, 1, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 2, 25), datetime.date(2024, 3, 24))|tuple",
  "time_pair=(datetime.time(9, 15), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "10-time-range-left-home": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(0, 0)|time",
  "datetime=datetime.datetime(2024, 3, 1, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 2, 25), datetime.date(2024, 3, 24))|tuple",
  "time_pair=(datetime.time(0, 0), datetime.time(17, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "11-time-range-right-end": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(0, 0)|time",
  "datetime=datetime.datetime(2024, 3, 1, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 2, 25), datetime.date(2024, 3, 24))|tuple",
  "time_pair=(datetime.time(0, 0), datetime.time(23, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 3, 10, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 17, 45, 7, 654321))|tuple"
 ],
 "12-datetime-range-left-home": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(0, 0)|time",
  "datetime=datetime.datetime(2024, 3, 1, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 2, 25), datetime.date(2024, 3, 24))|tuple",
  "time_pair=(datetime.time(0, 0), datetime.time(23, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 2, 25, 9, 30, 7, 123456), datetime.datetime(2024, 3, 20, 9, 30, 7, 123456))|tuple"
 ],
 "13-datetime-range-right-end": [
  "date=datetime.date(2024, 3, 1)|date",
  "time=datetime.time(0, 0)|time",
  "datetime=datetime.datetime(2024, 3, 1, 12, 30, 7, 123456)|datetime",
  "date_pair=(datetime.date(2024, 2, 25), datetime.date(2024, 3, 24))|tuple",
  "time_pair=(datetime.time(0, 0), datetime.time(23, 45))|tuple",
  "datetime_pair=(datetime.datetime(2024, 2, 25, 9, 30, 7, 123456), datetime.datetime(2024, 3, 24, 9, 30, 7, 123456))|tuple"
 ]
}

# Application paths label the captured roles; source content is not a gate.
TEMPORAL_SOURCE_FILES = {
    "python": "tests/reference/temporal_app.py",
    "native": "streamlit/examples/temporal.rs",
}

TEMPORAL_REQUIRED = (
    "contract", "stage_set", "wire_configs", "state_snapshots",
    "end_home_landings", "returned_reprs", "dom_input_values", "no_exceptions",
    "finishes", "png_sources",
)


def _record(checks, name, ok, expected, actual):
    checks.append({"step": TEMPORAL_CASE, "check": name, "expected": expected, "actual": actual, "ok": bool(ok)})


def _need(condition, message):
    if not condition:
        raise ValueError(message)


def _slider_wires(frames):
    wires = {}
    for frame in frames:
        delta = (frame.get("summary") or {}).get("delta") or {}
        widget = delta.get("widget") or {}
        if delta.get("element") == "slider":
            wires[widget.get("label")] = {field: widget.get(field) for field in ("format", "dataType", "default", "min", "max", "step")}
    return wires


def _state_snapshot(frames):
    snapshot = {}
    reruns = 0
    for frame in frames:
        summary = frame.get("summary") or {}
        reruns += summary.get("type") == "rerun_script"
        for state in (summary.get("rerun_script") or {}).get("widget_states") or []:
            data = (state.get("value_full") or {}).get("data")
            if data is not None:
                snapshot[state.get("id")] = data
    return snapshot, reruns


def _dom_inputs(dom):
    inputs = {}
    for slider in dom.get("sliders") or []:
        inputs[slider.get("label")] = [item.get("value") for item in slider.get("inputs") or []]
    return inputs


def temporal_checks(*, observation=None):
    checks = []
    verified = set()

    def mark(name):
        verified.add(name)
        _record(checks, name, True, "the measured 1.66.1 temporal slider wire", "contract verified")

    def fail(name, actual):
        _record(checks, name, False, "the measured 1.66.1 temporal slider wire", str(actual))

    try:
        _need(isinstance(observation, dict), "observation must be a dict")
        _need(observation.get("journey") == TEMPORAL_CASE and observation.get("contract") == TEMPORAL_CONTRACT,
              "missing versioned temporal contract identity")
        _need(bool(observation.get("scope")) and bool(observation.get("url")), "missing scope/url")
        mark("contract")

        stages = observation.get("stages")
        _need(isinstance(stages, list) and tuple(s.get("name") for s in stages) == tuple(TEMPORAL_STAGES),
              f"stages must be exactly the {len(TEMPORAL_STAGES)} measured stages in order")
        for stage in stages:
            _need(isinstance(stage.get("dom"), dict) and isinstance(stage.get("screenshot"), dict)
                  and isinstance(stage.get("new_frames"), list), f"stage {stage.get('name')} lacks dom/screenshot/new_frames")
        mark("stage_set")

        _need(_slider_wires(stages[0]["new_frames"]) == TEMPORAL_WIRE,
              "the six first-render slider wire configs differ from the measured table")
        mark("wire_configs")

        label_by_id = {}
        for frame in stages[0]["new_frames"]:
            delta = (frame.get("summary") or {}).get("delta") or {}
            widget = delta.get("widget") or {}
            if delta.get("element") == "slider":
                label_by_id[widget.get("id")] = widget.get("label")
        for stage in stages:
            snapshot, reruns = _state_snapshot(stage["new_frames"])
            _need(reruns == 1, f"stage {stage['name']} must carry exactly one rerun_script")
            _need({label_by_id.get(i): v for i, v in snapshot.items()} == TEMPORAL_STATES[stage["name"]],
                  f"stage {stage['name']} widget-state snapshot differs from the measured accumulation")
        mark("state_snapshots")

        for name, (label, landing) in TEMPORAL_TOUCHED.items():
            stage = next(s for s in stages if s["name"] == name)
            snapshot, _ = _state_snapshot(stage["new_frames"])
            _need(next(v for i, v in snapshot.items() if label_by_id.get(i) == label) == landing,
                  f"stage {name}: {label} must land on the measured {landing}")
        mark("end_home_landings")

        for stage in stages:
            echo = [line for line in (stage["dom"].get("markdowns") or []) if "=" in line]
            _need(echo == TEMPORAL_REPRS[stage["name"]], f"stage {stage['name']} echo reprs differ")
        mark("returned_reprs")

        for stage in stages:
            _need(_dom_inputs(stage["dom"]) == TEMPORAL_INPUTS[stage["name"]],
                  f"stage {stage['name']} native range input values differ from the frontend grid")
        mark("dom_input_values")

        for stage in stages:
            _need(not (stage["dom"].get("exceptions") or []),
                  f"stage {stage['name']} renders an exception")
            for frame in stage["new_frames"]:
                delta = (frame.get("summary") or {}).get("delta") or {}
                _need(delta.get("element") != "exception", f"stage {stage['name']} streams an exception element")
        mark("no_exceptions")

        for stage in stages:
            finishes = [((frame.get("summary") or {}).get("script_finished") or {}).get("status")
                        for frame in stage["new_frames"]
                        if (frame.get("summary") or {}).get("type") == "script_finished"]
            _need(finishes == [0], f"stage {stage['name']} must finish exactly once with FINISHED_SUCCESSFULLY")
        mark("finishes")

        root = pathlib.Path(observation.get("ipc_dir", ".")).resolve()
        for stage in stages:
            record = stage.get("screenshot") or {}
            _need(not pathlib.Path(record.get("file", "")).is_absolute(), "screenshot path must be relative")
            png = (root / record.get("file", "")).resolve()
            _need(png.is_relative_to(root) and png.is_file(), f"missing stage PNG {record.get('file')}")
            data = png.read_bytes()
            _need(data.startswith(b"\x89PNG\r\n\x1a\n") and hashlib.sha256(data).hexdigest() == record.get("sha256"),
                  f"stage PNG sha/magic mismatch for {record.get('file')}")
        mark("png_sources")
    except (ValueError, TypeError, KeyError, IndexError, OSError, AttributeError, StopIteration) as exc:
        for name in TEMPORAL_REQUIRED:
            if name not in verified:
                fail(name, str(exc))
        return checks
    return checks


def temporal_result(*, observation=None):
    """Aggregate the contract checks the way the shared journey judge does."""
    checks = temporal_checks(observation=observation)
    failures = [check for check in checks if not check["ok"]]
    return {
        "checks": checks,
        "counts": {"expected": len(checks), "executed": len(checks), "asserted": len(checks) - len(failures)},
        "failures": failures,
        "ok": not failures and len(checks) == len(TEMPORAL_REQUIRED),
    }
