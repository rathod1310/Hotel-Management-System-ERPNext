import frappe
from hospitality_core.hospitality_core.report.house_list.house_list import execute as run_house_list
from hospitality_core.hospitality_core.report.daily_arrivals.daily_arrivals import execute as run_arrivals
from hospitality_core.hospitality_core.report.daily_departures.daily_departures import execute as run_departures
from hospitality_core.hospitality_core.report.room_availability_report.room_availability_report import execute as run_avail
from hospitality_core.hospitality_core.page.front_desk_console.front_desk_console import get_console_data


def test_reports_and_console():
    print("Testing House List report...")
    cols, data, _, _, summary = run_house_list()
    print(f"House List: {len(cols)} columns, {len(data)} rows.")

    print("Testing Daily Arrivals report...")
    cols, data = run_arrivals()
    print(f"Daily Arrivals: {len(cols)} columns, {len(data)} rows.")

    print("Testing Daily Departures report...")
    cols, data = run_departures()
    print(f"Daily Departures: {len(cols)} columns, {len(data)} rows.")

    print("Testing Room Availability report...")
    cols, data = run_avail()
    print(f"Room Availability: {len(cols)} columns, {len(data)} rows.")

    print("Testing Front Desk Console backend...")
    res = get_console_data()
    print(f"Front Desk Console data: stats={res['stats']}")

    print("ALL REPORTS AND FRONT DESK CONSOLE LOADED CLEANLY!")

