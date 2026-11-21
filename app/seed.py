"""Demo dataset: 34 employees, 5 pods, 28 brands, 5 processes.

Staffing pattern required by the assessment:
* 23 of 28 brands (82%) are run by ONE dedicated employee handling all of the
  brand's processes (two of those employees run two small brands each).
* 5 brands have 2–3 employees: separate processes (UrbanKicks, PawPantry),
  a shared process (FitFuel, HomeHaven) and a mix incl. day-specific minimums
  (GlowVeda needs 2 on weekdays, 1 at weekends).
* Pod leads own a brand and act as designated backups for their pod.
* Mixed operating calendars: 365-day, daily-except-holidays, Mon–Sat, Mon–Fri,
  plus one evening shift (GreenLeaf) to exercise shift-compatibility checks.

Dates are relative to the current month so the demo always has a roster for
"this month" (published) and "next month" (draft).
"""
from calendar import monthrange
from datetime import date, time, timedelta

from app.extensions import db
from app.models import (Assignment, Availability, Brand, CoverageOverride, Employee,
                        EmployeeWeeklyOff, Holiday, Pod, Process, WorkingRule)

PROCESSES = [
    ("CS", "Customer Support", "Email, chat and phone support for orders and products."),
    ("ACC", "Abandoned Cart Conversions", "Outreach to recover abandoned carts."),
    ("NDR", "NDR Management", "Resolving non-delivery reports with couriers and customers."),
    ("RET", "Retention & Win-back", "Repeat-purchase and churn-prevention campaigns."),
    ("RVW", "Reviews & Social Care", "Marketplace reviews and social-media replies."),
]

# name -> (minimums Mon..Sun, operates on public holidays)
CAL = {
    "365": ((1, 1, 1, 1, 1, 1, 1), True),
    "DAILY": ((1, 1, 1, 1, 1, 1, 1), False),
    "MONSAT": ((1, 1, 1, 1, 1, 1, 0), False),
    "MONFRI": ((1, 1, 1, 1, 1, 0, 0), False),
    "GLOW_CS": ((2, 2, 2, 2, 2, 1, 1), True),
    "HAVEN_CS": ((2, 1, 1, 1, 1, 1, 1), False),
}
EVENING = (time(13, 0), time(22, 0))

PODS = {
    "Pod Atlas": [
        ("Priya Nair", "Pod Lead"), ("Arjun Mehta", None), ("Sneha Kulkarni", None), ("Rohan Das", None),
        ("Kavya Iyer", None), ("Imran Shaikh", None), ("Neha Joshi", None),
    ],
    "Pod Beacon": [
        ("Vikram Singh", "Pod Lead"), ("Ananya Rao", None), ("Karan Malhotra", None), ("Meera Pillai", None),
        ("Farhan Qureshi", None), ("Pooja Bhat", None), ("Siddharth Menon", None),
    ],
    "Pod Cascade": [
        ("Divya Krishnan", "Pod Lead"), ("Aditya Kapoor", None), ("Ishita Sharma", None), ("Manoj Patil", None),
        ("Ritu Agarwal", None), ("Nikhil Jain", None), ("Simran Kaur", None),
    ],
    "Pod Drift": [
        ("Rahul Verma", "Pod Lead"), ("Tanvi Desai", None), ("Harsh Vardhan", None), ("Swati Mishra", None),
        ("Gaurav Saxena", None), ("Kabir Anand", None), ("Mohit Rana", None),
    ],
    "Pod Ember": [
        ("Ayesha Khan", "Pod Lead"), ("Deepak Chauhan", None), ("Lakshmi Reddy", None), ("Yash Thakur", None),
        ("Aman Gupta", None), ("Shreya Banerjee", None),
    ],
}

# brand -> {process: calendar}  (+ optional shift)
BRANDS = {
    "Lumen Skincare": {"CS": "MONSAT", "ACC": "MONSAT"},
    "TrailNest Outdoors": {"CS": "DAILY", "NDR": "MONSAT"},
    "Brewster Coffee": {"CS": "MONSAT", "ACC": "MONSAT", "RET": "MONFRI"},
    "Tiny Tots Toys": {"CS": "MONSAT"},
    "PetalPress Stationery": {"CS": "MONFRI", "RVW": "MONFRI"},
    "UrbanKicks": {"CS": "365", "ACC": "MONSAT", "NDR": "DAILY"},
    "Northwind Apparel": {"CS": "MONSAT", "ACC": "MONSAT"},
    "GlowVeda": {"CS": "GLOW_CS", "NDR": "DAILY", "RET": "MONFRI"},
    "Spice Route Kitchen": {"CS": "365", "NDR": "DAILY"},
    "Aurora Candles": {"CS": "MONSAT", "RVW": "MONSAT"},
    "VoltRide E-Bikes": {"CS": "DAILY", "NDR": "MONSAT"},
    "Hearth & Home Decor": {"CS": "MONSAT", "ACC": "MONSAT"},
    "PawPantry": {"CS": "DAILY", "ACC": "MONSAT"},
    "Crisp Snacks": {"CS": "MONSAT", "ACC": "MONSAT", "NDR": "MONSAT"},
    "Silk & Thread": {"CS": "MONSAT", "RET": "MONFRI"},
    "GreenLeaf Organics": {"CS": "365", "ACC": "MONSAT"},
    "Kettle & Co Teas": {"CS": "DAILY", "ACC": "MONSAT"},
    "Peak Performance Nutrition": {"CS": "MONSAT", "RET": "MONFRI"},
    "FitFuel": {"CS": "DAILY", "ACC": "MONSAT"},
    "Bloom Botanics": {"CS": "MONSAT", "ACC": "MONSAT"},
    "Cloud Nine Bedding": {"CS": "MONFRI"},
    "Zest Juicery": {"CS": "DAILY", "NDR": "MONSAT"},
    "Harbor Watches": {"CS": "MONSAT", "ACC": "MONSAT"},
    "SunnySide Kids": {"CS": "MONFRI", "RET": "MONFRI"},
    "Orbit Gadgets": {"CS": "MONSAT", "ACC": "MONSAT", "NDR": "MONSAT"},
    "HomeHaven": {"CS": "HAVEN_CS", "ACC": "MONSAT"},
    "Velvet Cosmetics": {"CS": "DAILY", "ACC": "MONSAT", "RVW": "MONSAT"},
    "Nomad Luggage": {"CS": "MONSAT", "NDR": "MONSAT"},
}
EVENING_BRANDS = {"GreenLeaf Organics"}

# Single-resource brands: owner handles every process of the brand.
OWNERS = {
    "Lumen Skincare": "Priya Nair", "TrailNest Outdoors": "Arjun Mehta", "Brewster Coffee": "Sneha Kulkarni",
    "Tiny Tots Toys": "Sneha Kulkarni", "PetalPress Stationery": "Neha Joshi", "Northwind Apparel": "Vikram Singh",
    "Spice Route Kitchen": "Farhan Qureshi", "Aurora Candles": "Pooja Bhat", "VoltRide E-Bikes": "Siddharth Menon",
    "Hearth & Home Decor": "Divya Krishnan", "Crisp Snacks": "Manoj Patil", "Silk & Thread": "Ritu Agarwal",
    "GreenLeaf Organics": "Nikhil Jain", "Kettle & Co Teas": "Simran Kaur",
    "Peak Performance Nutrition": "Rahul Verma", "Bloom Botanics": "Swati Mishra",
    "Cloud Nine Bedding": "Swati Mishra", "Zest Juicery": "Gaurav Saxena", "Harbor Watches": "Kabir Anand",
    "SunnySide Kids": "Mohit Rana", "Orbit Gadgets": "Ayesha Khan", "Velvet Cosmetics": "Aman Gupta",
    "Nomad Luggage": "Shreya Banerjee",
}
# Multi-employee brands: (employee, process, priority)
SHARED = {
    "UrbanKicks": [("Rohan Das", "CS", 1), ("Kavya Iyer", "ACC", 1), ("Imran Shaikh", "NDR", 1),
                   ("Kavya Iyer", "CS", 2), ("Rohan Das", "NDR", 2)],
    "GlowVeda": [("Ananya Rao", "CS", 1), ("Karan Malhotra", "CS", 1), ("Meera Pillai", "NDR", 1),
                 ("Meera Pillai", "RET", 1), ("Meera Pillai", "CS", 2)],
    "PawPantry": [("Aditya Kapoor", "CS", 1), ("Ishita Sharma", "ACC", 1), ("Ishita Sharma", "CS", 2)],
    "FitFuel": [("Tanvi Desai", "CS", 1), ("Harsh Vardhan", "CS", 1), ("Tanvi Desai", "ACC", 1),
                ("Harsh Vardhan", "ACC", 1)],
    "HomeHaven": [("Deepak Chauhan", "CS", 1), ("Lakshmi Reddy", "CS", 1), ("Yash Thakur", "ACC", 1),
                  ("Yash Thakur", "CS", 2)],
}
# Designated backups for single-resource brands that run 7 days.
BACKUPS = [
    ("Priya Nair", "TrailNest Outdoors", "CS"), ("Vikram Singh", "Spice Route Kitchen", "CS"),
    ("Meera Pillai", "Spice Route Kitchen", "NDR"), ("Manoj Patil", "Kettle & Co Teas", "CS"),
    ("Rahul Verma", "Zest Juicery", "CS"), ("Ayesha Khan", "Velvet Cosmetics", "CS"),
    ("Divya Krishnan", "GreenLeaf Organics", "CS"),  # incompatible shift: demonstrates detection
]
WEEKLY_OFFS = [  # (employee, weekday, kind)
    ("Rohan Das", 6, "PREFERRED"), ("Ananya Rao", 5, "PREFERRED"), ("Karan Malhotra", 6, "PREFERRED"),
    ("Tanvi Desai", 6, "PREFERRED"), ("Harsh Vardhan", 6, "PREFERRED"), ("Deepak Chauhan", 2, "FIXED"),
    ("Lakshmi Reddy", 6, "PREFERRED"), ("Nikhil Jain", 0, "PREFERRED"), ("Aditya Kapoor", 4, "PREFERRED"),
    ("Siddharth Menon", 6, "PREFERRED"),
]
TWO_OFFS = {"Neha Joshi", "Mohit Rana"}

HOLIDAYS = [
    (date(2026, 1, 26), "Republic Day"), (date(2026, 5, 1), "Maharashtra Day"),
    (date(2026, 8, 15), "Independence Day"), (date(2026, 10, 2), "Gandhi Jayanti"),
    (date(2026, 11, 8), "Diwali (Lakshmi Puja)"), (date(2026, 11, 24), "Guru Nanak Jayanti"),
    (date(2026, 12, 25), "Christmas"), (date(2027, 1, 1), "New Year's Day (company holiday)"),
    (date(2027, 1, 26), "Republic Day"), (date(2027, 5, 1), "Maharashtra Day"),
    (date(2027, 8, 15), "Independence Day"), (date(2027, 10, 2), "Gandhi Jayanti"),
    (date(2027, 12, 25), "Christmas"),
]


def _month_after(d):
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _day(month_start, n):
    last = monthrange(month_start.year, month_start.month)[1]
    return month_start.replace(day=min(n, last))


def _last_weekday(month_start, weekday):
    d = _day(month_start, 31)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def seed_demo(today=None, generate=True):
    today = today or date.today()
    month_a = today.replace(day=1)
    month_b = _month_after(month_a)
    valid_from = date(month_a.year - 1, 1, 1)

    processes = {}
    for code, name, desc in PROCESSES:
        processes[code] = Process(code=code, name=name, description=desc)
    db.session.add_all(processes.values())

    employees, pods, n = {}, {}, 0
    for pod_name, members in PODS.items():
        pod = Pod(name=pod_name)
        db.session.add(pod)
        db.session.flush()
        pods[pod_name] = pod
        for full_name, designation in members:
            n += 1
            first, last = full_name.lower().split()[0], full_name.lower().split()[-1]
            emp = Employee(employee_code=f"RF{n:03d}", full_name=full_name, email=f"{first}.{last}@rosterflow.demo",
                           phone=f"+91 98{n:03d} {10000 + n * 37:05d}", designation=designation or "CX Executive",
                           pod_id=pod.id, weekly_offs_per_week=2 if full_name in TWO_OFFS else 1)
            db.session.add(emp)
            employees[full_name] = emp
    db.session.flush()
    for pod_name, members in PODS.items():
        pods[pod_name].lead_employee_id = employees[members[0][0]].id

    brands = {}
    for name, procs in BRANDS.items():
        brand = Brand(name=name, description=f"D2C brand · {', '.join(procs)}")
        db.session.add(brand)
        brands[name] = brand
    db.session.flush()

    for name, procs in BRANDS.items():
        for code, cal in procs.items():
            minimums, holidays = CAL[cal]
            start, end = EVENING if name in EVENING_BRANDS else (time(10), time(19))
            rule = WorkingRule(brand_id=brands[name].id, process_id=processes[code].id,
                               rule_name=f"{name} {code} – {cal}", operates_public_holidays=holidays,
                               shift_start=start, shift_end=end, effective_from=valid_from)
            rule.minimums = minimums
            db.session.add(rule)

    def assign(emp_name, brand_name, code, priority=1):
        db.session.add(Assignment(employee_id=employees[emp_name].id, brand_id=brands[brand_name].id,
                                  process_id=processes[code].id, priority=priority, effective_from=valid_from))

    for brand_name, owner in OWNERS.items():
        for code in BRANDS[brand_name]:
            assign(owner, brand_name, code)
    for brand_name, rows in SHARED.items():
        for emp_name, code, priority in rows:
            assign(emp_name, brand_name, code, priority)
    for emp_name, brand_name, code in BACKUPS:
        assign(emp_name, brand_name, code, 2)

    for emp_name, weekday, kind in WEEKLY_OFFS:
        db.session.add(EmployeeWeeklyOff(employee_id=employees[emp_name].id, weekday=weekday, kind=kind,
                                         effective_from=valid_from))
    for day, name in HOLIDAYS:
        db.session.add(Holiday(holiday_date=day, name=name, region="India"))

    def absence(emp_name, start, end, kind, status="APPROVED", note=None):
        db.session.add(Availability(employee_id=employees[emp_name].id, start_date=start, end_date=end,
                                    availability_type=kind, approval_status=status, notes=note))

    a, b = month_a, month_b
    absence("Imran Shaikh", _day(a, 26), _day(a, 27), "PLANNED_LEAVE", note="Family function")
    absence("Pooja Bhat", _day(a, 20), _day(a, 20), "COMP_OFF", note="Comp-off for holiday worked")
    absence("Arjun Mehta", _day(b, 8), _day(b, 10), "PLANNED_LEAVE", note="Vacation")
    absence("Karan Malhotra", _day(b, 14), _day(b, 16), "PLANNED_LEAVE", note="Wedding in family")
    absence("Swati Mishra", _day(b, 4), _day(b, 4), "COMP_OFF", note="Comp-off")
    absence("Manoj Patil", _day(b, 21), _day(b, 21), "UNAVAILABLE", note="Courier-partner training")
    absence("Rohan Das", _day(b, 22), _day(b, 23), "PLANNED_LEAVE", "PENDING", note="Personal work – awaiting approval")
    absence("Priya Nair", _day(b, 11), _day(b, 11), "PLANNED_LEAVE", "PENDING", note="Medical appointment")
    absence("Gaurav Saxena", _day(b, 2), _day(b, 3), "PLANNED_LEAVE", "REJECTED", note="Clashes with sale week")

    # Date-specific staffing (sale days): needs more than the normal minimum.
    for month in (a, b):
        sale = _last_weekday(month, 4)  # last Friday of the month
        db.session.add(CoverageOverride(brand_id=brands["UrbanKicks"].id, process_id=processes["CS"].id,
                                        override_date=sale, minimum_staff=2, reason="Month-end sale"))
        db.session.add(CoverageOverride(brand_id=brands["Velvet Cosmetics"].id, process_id=processes["CS"].id,
                                        override_date=_day(month, 15), minimum_staff=2, reason="Mid-month launch"))
    db.session.commit()

    if generate:
        from app.scheduling import service
        current = service.generate_roster(a.year, a.month, notes="Demo roster (seeded)")
        service.auto_assign_covers(current)
        service.publish(current, acknowledge_errors=True)
        service.generate_roster(b.year, b.month, notes="Demo draft for next month (seeded)")
    return dict(employees=len(employees), brands=len(brands), pods=len(pods), processes=len(processes))
