import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Set
from .models import TaskEvent

DAY_MAP = {
    "MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6
}
REV_DAY_MAP = {v: k for k, v in DAY_MAP.items()}

MAX_RECURRENCE_COUNT = 60


def unfold_ics(text: str) -> List[str]:
    """Unfolds lines in an iCalendar file according to RFC 5545 Section 3.1."""
    lines = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    unfolded = []
    for line in lines:
        if line.startswith((' ', '\t')) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded


def unescape_ics_text(val: str) -> str:
    """Unescapes RFC 5545 text characters."""
    if not val:
        return ""
    return (
        val.replace(r'\n', '\n')
        .replace(r'\N', '\n')
        .replace(r'\,', ',')
        .replace(r'\;', ';')
        .replace(r'\\', '\\')
    )


def escape_ics_text(val: str) -> str:
    """Escapes characters for RFC 5545 text format."""
    if not val:
        return ""
    return (
        val.replace('\\', '\\\\')
        .replace(';', r'\;')
        .replace(',', r'\,')
        .replace('\n', r'\n')
    )


def parse_ics_datetime(val: str) -> Optional[datetime]:
    """
    Parses an iCalendar datetime or date string into a Python datetime object.
    Supports:
    - 20260921T145500Z (UTC)
    - 20260921T145500 (Local/floating)
    - 20260921 (All-day date)
    """
    val = val.strip()
    if not val:
        return None

    # Strip parameters if left in value (e.g. VALUE=DATE:20260921)
    if ":" in val:
        val = val.split(":")[-1]

    # UTC format: 20260921T145500Z
    if val.endswith('Z'):
        val_clean = val[:-1]
        try:
            dt = datetime.strptime(val_clean, "%Y%m%dT%H%M%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    # Standard local format: 20260921T145500
    if 'T' in val:
        try:
            return datetime.strptime(val, "%Y%m%dT%H%M%S")
        except ValueError:
            pass

    # Date-only format: 20260921
    if len(val) == 8 and val.isdigit():
        try:
            return datetime.strptime(val, "%Y%m%d")
        except ValueError:
            pass

    return None


def rfc_priority_to_local(rfc_p: int) -> int:
    """
    Maps RFC 5545 Priority (1-9, 1 highest) to Locked Priority (1-5, 5 highest).
    """
    if rfc_p <= 0:
        return 3
    if rfc_p in (1, 2):
        return 5  # Urgent
    if rfc_p in (3, 4):
        return 4  # High
    if rfc_p == 5:
        return 3  # Medium
    if rfc_p in (6, 7):
        return 2  # Low
    return 1      # Lowest (8, 9)


def local_priority_to_rfc(p: int) -> int:
    """
    Maps Locked Priority (1-5, 5 highest) to RFC 5545 Priority (1-9, 1 highest).
    """
    mapping = {5: 1, 4: 3, 3: 5, 2: 7, 1: 9}
    return mapping.get(p, 5)


def expand_rrule(
    base_start: datetime,
    base_end: datetime,
    rrule_str: str,
    exdates: Set[str]
) -> List[tuple]:
    """
    Expands an RRULE into discrete (start_dt, end_dt) occurrences.
    Supports FREQ=DAILY, WEEKLY, MONTHLY; INTERVAL; COUNT; UNTIL; BYDAY.
    """
    params: Dict[str, str] = {}
    for part in rrule_str.split(';'):
        if '=' in part:
            k, v = part.split('=', 1)
            params[k.upper().strip()] = v.strip()

    freq = params.get("FREQ", "WEEKLY").upper()
    interval = max(1, int(params.get("INTERVAL", 1)))
    count = int(params.get("COUNT", 0))
    until_dt = parse_ics_datetime(params.get("UNTIL", ""))
    byday_str = params.get("BYDAY", "")

    target_weekdays = None
    if byday_str:
        target_weekdays = set()
        for d in byday_str.split(','):
            code = d.strip()[-2:].upper()
            if code in DAY_MAP:
                target_weekdays.add(DAY_MAP[code])

    duration = base_end - base_start
    instances = []

    limit = count if count > 0 else MAX_RECURRENCE_COUNT
    curr_date = base_start.date()
    start_time = base_start.time()

    # Determine tzinfo from base_start
    tz = base_start.tzinfo

    # Maximum search limit in days to prevent runaway execution
    max_days_to_search = 366 * 2
    days_searched = 0

    week_count = 0
    prev_week_num = None

    while len(instances) < limit and days_searched < max_days_to_search:
        # Check week interval increment
        iso_year, iso_week, _ = curr_date.isocalendar()
        curr_week_id = f"{iso_year}-{iso_week}"
        if prev_week_num is None:
            prev_week_num = curr_week_id
        elif curr_week_id != prev_week_num:
            week_count += 1
            prev_week_num = curr_week_id

        # Check if current day qualifies
        qualifies = False
        if freq == "DAILY":
            if days_searched % interval == 0:
                qualifies = True
        elif freq == "WEEKLY":
            if week_count % interval == 0:
                if target_weekdays is not None:
                    if curr_date.weekday() in target_weekdays:
                        qualifies = True
                elif curr_date.weekday() == base_start.weekday():
                    qualifies = True
        elif freq == "MONTHLY":
            # Simple monthly matching on same day of month
            if curr_date.day == base_start.day:
                qualifies = True

        if qualifies:
            dt_start = datetime.combine(curr_date, start_time, tzinfo=tz)
            dt_end = dt_start + duration

            if until_dt and dt_start > until_dt:
                break

            # Check exdate
            date_key = curr_date.strftime("%Y%m%d")
            if date_key not in exdates and dt_start >= base_start:
                instances.append((dt_start, dt_end))

        curr_date += timedelta(days=1)
        days_searched += 1

    return instances if instances else [(base_start, base_end)]


def parse_ics(ics_text: str) -> List[Dict[str, Any]]:
    """
    Parses raw .ics text content and extracts a list of task dicts.
    Expands recurring events according to RRULE.
    """
    lines = unfold_ics(ics_text)
    events = []

    in_vevent = False
    current_props: Dict[str, str] = {}
    current_exdates: Set[str] = set()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line == "BEGIN:VEVENT":
            in_vevent = True
            current_props = {}
            current_exdates = set()
            continue

        if line == "END:VEVENT":
            if in_vevent:
                in_vevent = False
                # Process the VEVENT block
                parsed_tasks = _process_vevent(current_props, current_exdates)
                events.extend(parsed_tasks)
            continue

        if in_vevent:
            if ":" in line:
                key_part, val = line.split(":", 1)
                prop_name = key_part.split(";")[0].upper().strip()
                if prop_name == "EXDATE":
                    # Can be comma separated dates e.g. EXDATE:20260921,20260928
                    for d in val.split(','):
                        d_clean = d.strip()
                        if len(d_clean) >= 8:
                            current_exdates.add(d_clean[:8])
                else:
                    current_props[prop_name] = val.strip()

    return events


def _process_vevent(props: Dict[str, str], exdates: Set[str]) -> List[Dict[str, Any]]:
    """Converts a raw VEVENT properties dictionary into one or more Task dictionaries."""
    name = unescape_ics_text(props.get("SUMMARY", "")).strip() or "Untitled Task"
    description = unescape_ics_text(props.get("DESCRIPTION", "")).strip()
    labels = unescape_ics_text(props.get("CATEGORIES", "")).strip()

    # Priority
    rfc_priority = 0
    if "PRIORITY" in props and props["PRIORITY"].isdigit():
        rfc_priority = int(props["PRIORITY"])
    priority = rfc_priority_to_local(rfc_priority)

    # Status
    status = props.get("STATUS", "").upper()
    done = 1 if status == "COMPLETED" else 0

    # Start and End Dates
    dt_start = parse_ics_datetime(props.get("DTSTART", ""))
    dt_end = parse_ics_datetime(props.get("DTEND", ""))

    now = datetime.now()
    if not dt_start:
        dt_start = now
    if not dt_end:
        dt_end = dt_start + timedelta(hours=1)
    if dt_end < dt_start:
        dt_end = dt_start + timedelta(hours=1)

    rrule_str = props.get("RRULE")
    tasks = []

    if rrule_str:
        occurrences = expand_rrule(dt_start, dt_end, rrule_str, exdates)
        for idx, (occ_start, occ_end) in enumerate(occurrences):
            start_ts = int(occ_start.timestamp())
            end_ts = int(occ_end.timestamp())
            # For recurring events, append instance index or session
            occ_name = name
            if len(occurrences) > 1:
                occ_name = f"{name} (#{idx + 1})"

            tasks.append({
                "name": occ_name,
                "description": description,
                "start_date": start_ts,
                "end_date": end_ts,
                "priority": priority,
                "labels": labels,
                "done": done
            })
    else:
        tasks.append({
            "name": name,
            "description": description,
            "start_date": int(dt_start.timestamp()),
            "end_date": int(dt_end.timestamp()),
            "priority": priority,
            "labels": labels,
            "done": done
        })

    return tasks


def generate_ics(tasks: List[TaskEvent]) -> str:
    """Generates an RFC 5545 compliant iCalendar string from a list of TaskEvent objects."""
    now_utc_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Locked//Study Toolkit//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]

    for t in tasks:
        start_dt = datetime.fromtimestamp(t.start_date, tz=timezone.utc)
        end_dt = datetime.fromtimestamp(t.end_date, tz=timezone.utc)
        dtstart_str = start_dt.strftime("%Y%m%dT%H%M%SZ")
        dtend_str = end_dt.strftime("%Y%m%dT%H%M%SZ")

        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:task-{t.id}@locked.local")
        lines.append(f"DTSTAMP:{now_utc_str}")
        lines.append(f"DTSTART:{dtstart_str}")
        lines.append(f"DTEND:{dtend_str}")
        lines.append(f"SUMMARY:{escape_ics_text(t.name)}")

        if t.description:
            lines.append(f"DESCRIPTION:{escape_ics_text(t.description)}")
        if t.labels:
            cat_items = [x.strip().replace('\\', '\\\\').replace(';', r'\;').replace('\n', r'\n') for x in t.labels.split(',') if x.strip()]
            if cat_items:
                lines.append(f"CATEGORIES:{','.join(cat_items)}")

        rfc_p = local_priority_to_rfc(t.priority)
        lines.append(f"PRIORITY:{rfc_p}")

        status = "COMPLETED" if t.done else "CONFIRMED"
        lines.append(f"STATUS:{status}")

        lines.append("END:VEVENT")

    lines.append("END:VCALENDAR")
    lines.append("")
    return "\r\n".join(lines)
