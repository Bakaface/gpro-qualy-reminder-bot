#!/usr/bin/env python3
import json
import os

def pretty_users():
    if os.path.exists('users_data.json'):
        with open('users_data.json', 'r') as f:
            data = json.load(f)
        with open('users_data.json', 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        print("✅ users_data.json → Pretty (1 line/entry)")

def pretty_calendar():
    if os.path.exists('gpro_calendar.json'):
        with open('gpro_calendar.json', 'r') as f:
            data = json.load(f)
        with open('gpro_calendar.json', 'w') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        print("✅ gpro_calendar.json → Pretty (1 line/entry)")

if __name__ == '__main__':
    pretty_users()
    pretty_calendar()
    print("🎨 ALL JSON PRETTIFIED!")
