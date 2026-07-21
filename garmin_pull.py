"""
Pulls today's data from Garmin Connect, estimates fitness age, and writes
data.json at the repo root for the dashboard (index.html) to read.

Environment variables required:
    GARMIN_EMAIL
    GARMIN_PASSWORD
    USER_ACTUAL_AGE      e.g. "24"
    USER_SEX              "male" or "female"  (used for fitness-age table)
"""

import os
import json
from datetime import date
from garminconnect import Garmin

# Average VO2max by age bracket (rough population tables, ml/kg/min), used only
# to translate a VO2max value into an equivalent "fitness age". Not medical data.
VO2_BY_AGE_MALE = {20: 52, 30: 48, 40: 44, 50: 40, 60: 36, 70: 32}
VO2_BY_AGE_FEMALE = {20: 46, 30: 42, 40: 38, 50: 34, 60: 30, 70: 26}


def estimate_fitness_age(vo2max, resting_hr, sex):
    table = VO2_BY_AGE_MALE if sex == "male" else VO2_BY_AGE_FEMALE
    ages = sorted(table.keys())

    # Find the age bracket whose average VO2max is closest to the user's value
    best_age = ages[0]
    best_diff = float("inf")
    for age in ages:
        diff = abs(table[age] - vo2max)
        if diff < best_diff:
            best_diff = diff
            best_age = age

    # Linear interpolation between the two nearest brackets for a smoother estimate
    for i in range(len(ages) - 1):
        a1, a2 = ages[i], ages[i + 1]
        v1, v2 = table[a1], table[a2]
        if v2 <= vo2max <= v1:
            frac = (v1 - vo2max) / (v1 - v2) if v1 != v2 else 0
            best_age = round(a1 + frac * (a2 - a1))
            break

    # Small adjustment from resting heart rate (60bpm treated as neutral baseline)
    hr_adjustment = (resting_hr - 60) / 10  # +1 year per 10bpm above 60, etc.
    fitness_age = round(best_age + hr_adjustment)

    return max(15, fitness_age)


def band_label(value, good, ok):
    if value >= good:
        return "GOOD"
    if value >= ok:
        return "MODERATE"
    return "LOW"


def main():
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    actual_age = int(os.environ.get("USER_ACTUAL_AGE", "30"))
    sex = os.environ.get("USER_SEX", "male").lower()

    if not email or not password:
        raise SystemExit("Set GARMIN_EMAIL and GARMIN_PASSWORD environment variables.")

    client = Garmin(email, password)
    client.login()

    today = date.today().isoformat()

    stats = client.get_stats(today) or {}
    sleep = client.get_sleep_data(today) or {}

    steps = stats.get("totalSteps", 0)
    resting_hr = stats.get("restingHeartRate", 60)
    body_battery = stats.get("bodyBatteryMostRecentValue", 50)
    vo2max = (stats.get("vo2MaxValue") or 45)
    training_load = stats.get("activeKilocalories", 0)  # placeholder proxy if load unavailable
    sleep_score = (sleep.get("dailySleepDTO", {}) or {}).get("sleepScores", {}).get("overall", {}).get("value", 70)

    fitness_age = estimate_fitness_age(vo2max, resting_hr, sex)

    data = {
        "date": date.today().strftime("%a %b %d").upper(),
        "bodyBattery": body_battery,
        "bodyBatteryLabel": band_label(body_battery, 70, 40),
        "statusLine": "Synced from your Garmin — this reflects last night's recovery.",
        "sleepScore": sleep_score,
        "restingHR": resting_hr,
        "trainingLoad": training_load,
        "vo2Max": vo2max,
        "steps": round(steps / 1000, 1) if steps else 0,
        "actualAge": actual_age,
        "fitnessAge": fitness_age,
    }

    out_path = os.path.join(os.path.dirname(__file__), "..", "data.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {out_path}")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
