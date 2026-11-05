import frappe
from hospitality_core.tests.test_flow import TestHotelFlow
from hospitality_core.hospitality_core.report.house_list.house_list import execute as run_house_list
from hospitality_core.hospitality_core.report.daily_arrivals.daily_arrivals import execute as run_arrivals
from hospitality_core.hospitality_core.report.daily_departures.daily_departures import execute as run_departures
from hospitality_core.hospitality_core.report.room_availability_report.room_availability_report import execute as run_avail
from hospitality_core.hospitality_core.page.front_desk_console.front_desk_console import get_console_data


def run_all():
    print("--- 1. Setting up test data ---")
    TestHotelFlow.setUpClass()
    test_instance = TestHotelFlow()

    print("--- 2. Running test_complete_hotel_lifecycle ---")
    test_instance.test_complete_hotel_lifecycle()
    print("SUCCESS: test_complete_hotel_lifecycle passed!")

    print("--- 3. Testing House List report ---")
    cols, data, _, _, summary = run_house_list()
    print(f"House List: {len(cols)} columns, {len(data)} rows.")

    print("--- 4. Testing Daily Arrivals report ---")
    cols, data = run_arrivals()
    print(f"Daily Arrivals: {len(cols)} columns, {len(data)} rows.")

    print("--- 5. Testing Daily Departures report ---")
    cols, data = run_departures()
    print(f"Daily Departures: {len(cols)} columns, {len(data)} rows.")

    print("--- 6. Testing Room Availability report ---")
    cols, data = run_avail()
    print(f"Room Availability: {len(cols)} columns, {len(data)} rows.")

    print("--- 7. Testing Front Desk Console backend ---")
    res = get_console_data()
    print(f"Front Desk Console stats: {res['stats']}")

    print("\n==========================================")
    print("ALL ACCEPTANCE TESTS & REPORTS PASSED 100%!")
    print("==========================================")
