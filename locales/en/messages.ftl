# GPRO Bot - English Translations

# =======================
# Commands & General
# =======================
start-welcome-new = 👋 **Welcome to GPRO Bot!**

    Let's get you set up. First, choose your preferred language for GPRO race links:

    🌍 **Select your language** (or skip to use English):

start-welcome-existing = 🏁 GPRO Bot LIVE!
    /status - Next race
    /calendar - Full season
    /next - Next season
    /settings - Preferences

start-welcome-existing-buttons = 🏁 **GPRO Bot**

    What would you like to do?

bot-live = 🏁 **GPRO Bot**

# =======================
# Status & Calendar
# =======================
no-races-scheduled = 🔔 No races scheduled
no-upcoming-qualifications = 🔔 No upcoming qualifications
next-season-not-published = 🌟 **Next season not published yet**

calendar-title-full = 🏁 **Full Season**
calendar-title-next = 🌟 **NEXT SEASON** ({ $count } races)

# =======================
# Onboarding
# =======================
onboard-group-title = 🏁 **Group Selection**

    Choose your GPRO group to get personalized race links:

    Select a common group or enter your own:

onboard-group-custom = 🏁 **Custom Group**

    Enter your group in one of these formats:
    • **E** (Elite)
    • **M3** (Master 3)
    • **P15** (Pro 15)
    • **A42** (Amateur 42)
    • **R11** (Rookie 11)

    Numbers can be 1-3 digits.

onboard-complete = ✅ **Setup Complete!**

    🏁 **GPRO Bot is ready!**

    **Available commands:**
    /status - Next race
    /calendar - Full season
    /next - Next season
    /settings - Preferences

    💡 *You can change these settings anytime using /settings*

onboard-complete-with-group = ✅ **Setup Complete!**

    Group: **{ $group }**

    🏁 **GPRO Bot is ready!**

    **Available commands:**
    /status - Next race
    /calendar - Full season
    /next - Next season
    /settings - Preferences

# =======================
# Settings
# =======================
settings-title = ⚙️ **Settings**

    Configure your preferences:

settings-language-title = 🌍 **Language Settings**

    Current: { $language }

    Select your preferred language for GPRO race links:

settings-group-title = 🏁 **Group Settings**

    Current group: **{ $group }**

    Enter your group in one of these formats:
    • **E** (Elite)
    • **M3** (Master 3)
    • **P15** (Pro 15)
    • **A42** (Amateur 42)
    • **R11** (Rookie 11)

    Numbers can be 1-3 digits.

settings-group-set = ✅ **Group set to: { $group }**

    Race and replay notifications will include direct links to your group!

settings-notifications-title = 🔔 **Notification Settings**

    Click to toggle notifications on/off:
    ✅ = Enabled | ❌ = Disabled

    ℹ️ *These are global switches for all races. Use the 'Quali Done' button in notifications to disable a specific race.*

settings-custom-notif-title = ⏱️ **Custom Notifications**

    Set your own notification times ({ $min }m - { $max }h before quali closes).

    You can have up to 2 custom notifications.

    Click a slot to set or edit it.

settings-custom-notif-edit = ⏱️ **Custom Notification { $slot }**{ $current }

    Select a preset time or enter a custom time:

settings-custom-notif-input = ⏱️ **Custom Notification { $slot }**

    Enter your custom notification time.

    **Accepted formats:**
    • `20m` or `45 minutes` (20m-70h)
    • `2h` or `12 hours`
    • `1h 30m` or `2h30m`

    **Examples:**
    • `20m` - 20 minutes before
    • `6h` - 6 hours before
    • `1h 30m` - 1 hour 30 minutes before

# =======================
# Buttons
# =======================
button-ui-language = 💬 Bot Language: { $language }
button-gpro-language = 🌍 GPRO Language: { $language }
button-language = 🌍 Language: { $language }
button-group = 🏁 Group: { $group }
button-notifications = 🔔 Notifications
button-custom-notifications = ⏱️ Custom Notifications
button-back = ◀ Back
button-back-to-settings = ◀ Back to Settings
button-back-to-notifications = ◀ Back to Notifications
button-back-to-custom = ◀ Back to Custom Notifications
button-back-custom-notif = ◀ Back to Custom Notifications
button-main-menu = 🏠 Main Menu
button-reset-group = 🔄 Reset Group
button-custom-slot-set = ⏱️ Custom { $slot }: { $time }
button-custom-slot-empty = ➕ Set Custom Notification { $slot }
button-previous = ◀ Previous
button-next = Next ▶
button-skip = ⏭️ Skip
button-reset-language = 🔄 Reset to Default (English)
button-enable-all = 🔔 Enable All Notifications
button-disable-all = 🔕 Disable All Notifications
button-quali-done = ✅ Quali Done
button-reenable-race = 🔄 Re-enable Race { $raceId } notifications
button-weather = 🌤️ Show Weather
button-enter-custom-group = ✏️ Enter Custom Group
button-enter-custom-time = ✏️ Enter Custom Time
button-disable-notification = 🔕 Disable This Notification
button-cancel = ❌ Cancel
button-got-it = ✅ Got it!
button-try-again = 🔄 Try Again

button-main-menu-status = 📊 Next Race
button-main-menu-calendar = 📅 Full Season
button-main-menu-next = 🌟 Next Season
button-main-menu-settings = ⚙️ Settings

button-group-elite = Elite
button-group-master3 = Master 3
button-group-pro15 = Pro 15
button-group-amateur42 = Amateur 42
button-group-rookie11 = Rookie 11

button-set-custom-notif = ➕ Set Custom Notification { $slot }
button-custom-notif-time = ⏱️ Custom { $slot }: { $time }

# =======================
# Notifications
# =======================
notif-label-48h = 48h before quali closes
notif-label-24h = 24h before quali closes
notif-label-2h = 2h before quali closes
notif-label-10min = 10min before quali closes
notif-label-opens = Quali is open
notif-label-replay = Race replay available
notif-label-live = Race is live
notif-label-results = Race results available

notif-quali-closes = **Quali closes in { $time }!**
notif-quali-opens = **Quali is open (or is opening soon)**

notif-quali-message = { $emoji } { $title }

    🏁 **Race #{ $raceId }**
    📍 **{ $track }**
    📅 **Quali: { $qualiDeadline } | Race: { $raceTime }**

    🔗 [Go to Qualifying]({ $qualiLink })

    Click button to disable notifications for this race

notif-quali-message-disabled = { $emoji } { $title }

    🏁 **Race #{ $raceId }**
    📍 **{ $track }**
    📅 **Quali: { $qualiDeadline } | Race: { $raceTime }**

    🔗 [Go to Qualifying]({ $qualiLink })

    ℹ️ **Automatic notifications disabled** for this race
    Click button to re-enable notifications

notif-race-live = 🏁 **Race #{ $raceId } is LIVE!**

    📍 **{ $track }**
    🕐 **{ $raceTime }**

    🔗 [Watch Live Race]({ $raceLink })

notif-race-live-no-group = 🏁 **Race #{ $raceId } is LIVE!**

    📍 **{ $track }**
    🕐 **{ $raceTime }**

    ⚠️ Set your group in /settings for a direct link!

    🔗 [Watch Live Race]({ $raceLink })

notif-race-replay = 📺 **Race #{ $raceId } Replay Available**

    📍 **{ $track }**
    🕐 **{ $raceTime }**

    If the race has already been calculated, replay is available here:

    🔗 [Watch Replay]({ $replayLink })

notif-race-replay-no-group = 📺 **Race #{ $raceId } Replay Available**

    📍 **{ $track }**
    🕐 **{ $raceTime }**

    If the race has already been calculated, replay is available here:

    ⚠️ For personalized links, set your group in /settings!

    🔗 [Watch Replay]({ $replayLink })

notif-race-results = 📊 **Race #{ $raceId } Results Available**

    📍 **{ $track }**
    🕐 **{ $raceTime }**

    Race results are now available:

    🔗 [Race Analysis]({ $analysisLink })
    🔗 [Race Summary]({ $summaryLink })

notif-race-results-no-group = 📊 **Race #{ $raceId } Results Available**

    📍 **{ $track }**
    🕐 **{ $raceTime }**

    Race results are now available:

    🔗 [Race Analysis]({ $analysisLink })

    ⚠️ For personalized Race Summary, set your group in /settings!

# =======================
# Weather
# =======================
weather-title = 🌤️ **Race Weather Forecast**
weather-practice-q1 = **Practice / Qualify 1:** { $weather }
weather-temp-hum = Temp: { $temp }°C • Humidity: { $hum }%
weather-q2-start = **Qualify 2 / Race Start:** { $weather }
weather-race-conditions = **Race Conditions:**
weather-quarter = **{ $label }:**
weather-race-quarter = Temp: { $temp } • Humidity: { $hum }
    Rain probability: { $rain }
weather-not-available = ⚠️ Weather data not available
weather-cached = ℹ️ Weather already cached for **Race #{ $raceId }: { $track }**

    Use `/weather force` to force update.
    Use /status to see the notification with weather button.
weather-fetching = 🔄 Fetching weather for **Race #{ $raceId }: { $track }**...
weather-force-updating = 🔄 Force updating weather for **Race #{ $raceId }: { $track }**...
weather-success = ✅ Weather data fetched for **Race #{ $raceId }: { $track }**

    Use /status to test the notification with weather button!
weather-failed = ❌ Failed to fetch weather data

    Check if GPRO API token is valid and Practice API is available.

# =======================
# Admin
# =======================
admin-only = ❌ Admin only
admin-calendar-updated = ✅ **Calendar**: { $count } races
    🔄 **{ $userCount } users** reset
admin-next-season-ready = 🌟 **Next season ready!** { $count } races
    Use /next to view
admin-next-season-not-published = ℹ️ **Next season not published**
admin-users-count = 📊 **{ $count } users**:
admin-users-none = 📊 **0 users** in database
admin-no-races = ❌ No races in calendar
admin-no-upcoming-races = ❌ No upcoming races found

# =======================
# Errors & Validation
# =======================
error-invalid-format = ❌ Invalid format!

    Please use:
    • **E** for Elite
    • **M3** (Master 3)
    • **P15**, **A42**, **R11** etc.

    Try again:

error-invalid-format-onboarding = ❌ Invalid format!

    Please use:
    • **E** for Elite
    • **M3** (Master 3)
    • **P15**, **A42**, **R11** etc.

    Try again or use /start to restart:

error-invalid-time = ❌ **Error:** { $error }

    Please try again with a valid format like: `2h`, `30m`, or `1h 30m`

error-custom-notif-failed = ❌ **Error:** { $error }

    Please try again.

error-invalid-race = ❌ Invalid race ID
error-invalid-page = ❌ Invalid page
error-invalid-language = ❌ Invalid language
error-invalid-slot = ❌ Invalid slot
error-invalid-data = ❌ Invalid data
error-reset-failed = ❌ Reset failed
error-race-not-found = ❌ Race not found
error-weather-not-available = ⚠️ Weather data not available yet
error-weather-send-failed = ❌ Failed to send weather

# =======================
# Feedback & Confirmations
# =======================
feedback-all-enabled = ✅ All notifications enabled!
feedback-all-disabled = ✅ All notifications disabled!
feedback-notif-enabled = ✅ { $label } enabled!
feedback-notif-disabled = ✅ { $label } disabled!
feedback-quali-done = ✅ Done!
feedback-reset = 🔄 Reset!
feedback-language-set = ✅ Language set to { $language }
feedback-language-reset = ✅ Language reset to English
feedback-group-set = ✅ Group set to { $group }
feedback-custom-notif-set = ✅ { $message }
feedback-custom-notif-disabled = ✅ Custom notification { $slot } disabled
feedback-skip-language = ⏭️ Using default language (English)
feedback-skip-group = ⏭️ Skipped group selection
feedback-welcome = ✅ Welcome aboard!
feedback-weather-sent = 🌤️ Weather forecast sent!

# =======================
# Time Formatting
# =======================
time-minutes = { $minutes ->
    [one] { $minutes } minute
   *[other] { $minutes } minutes
}
time-hours = { $hours ->
    [one] { $hours } hour
   *[other] { $hours } hours
}
time-hours-minutes = { $hours ->
    [one] { $hours } hour
   *[other] { $hours } hours
} { $minutes ->
    [one] { $minutes } minute
   *[other] { $minutes } minutes
}
time-hours-minutes-short = { $hours }h{ $minutes }m
time-days = { $days ->
    [one] { $days } day
   *[other] { $days } days
}
time-days-hours = { $days ->
    [one] { $days } day
   *[other] { $days } days
} { $hours ->
    [one] { $hours } hour
   *[other] { $hours } hours
}
time-months = { $months ->
    [one] { $months } month
   *[other] { $months } months
}
time-months-days = { $months ->
    [one] { $months } month
   *[other] { $months } months
} { $days ->
    [one] { $days } day
   *[other] { $days } days
}

# =======================
# Group Display
# =======================
group-not-set = Not set
group-elite = Elite
group-master = Master - { $number }
group-pro = Pro - { $number }
group-amateur = Amateur - { $number }
group-rookie = Rookie - { $number }

# =======================
# Custom Notification Messages
# =======================
custom-notif-set = Custom notification { $slot } set to { $time }
custom-notif-set-success = Custom notification { $slot } set to { $time }
custom-notif-not-set = Not set
custom-notif-min-error = Minimum time is 20 minutes
custom-notif-max-error = Maximum time is 70 hours
custom-notif-invalid-slot = Invalid slot (must be 0-{ $max })
custom-notif-empty-error = Time cannot be empty
custom-notif-invalid-format = Invalid format. Use: 2h, 30m, or 1h 30m
custom-notif-enter-time = Please enter a time
custom-notif-error-parsing = ❌ **Error:** { $error }

    Please try again with a valid format like: `2h`, `30m`, or `1h 30m`
custom-notif-success = ✅ **{ $message }**

    Your custom notification has been set!
custom-notif-error-setting = ❌ **Error:** { $error }

    Please try again.

# =======================
# Validation
# =======================
validation-time-empty = Time cannot be empty
validation-time-min = Minimum time is 20 minutes
validation-time-max = Maximum time is 70 hours
validation-enter-time = Please enter a time
validation-invalid-format = Invalid format. Use: 2h, 30m, or 1h 30m
validation-invalid-slot = Invalid slot (must be 0-{ $maxSlots })

# =======================
# Notification Labels
# =======================
notif-label-48h = 48h before quali closes
notif-label-24h = 24h before quali closes
notif-label-2h = 2h before quali closes
notif-label-10min = 10min before quali closes
notif-label-opens-soon = Quali is open
notif-label-race-replay = Race replay available
notif-label-race-live = Race is live
notif-label-race-results = Race results available

# =======================
# Notification Menu
# =======================
notif-menu-title = 🔔 **Notification Settings**

    Click to toggle notifications on/off:
    ✅ = Enabled | ❌ = Disabled

    ℹ️ *These are global switches for all races. Use the 'Quali Done' button in notifications to disable a specific race.*

# =======================
# Group Menu
# =======================
group-menu-title = 🏁 **Group Settings**

    Current group: **{ $groupDisplay }**

    Enter your group in one of these formats:
    • **E** (Elite)
    • **M3** (Master 3)
    • **P15** (Pro 15)
    • **A42** (Amateur 42)
    • **R11** (Rookie 11)

    Numbers can be 1-3 digits.
group-reset-success = ✅ Group reset successfully

# =======================
# Language Menu
# =======================
lang-menu-title = 🌍 **Language Settings**

    Current: { $currentLang }

    Select your preferred language for GPRO race links:

# =======================
# Custom Notification Menu
# =======================
custom-notif-menu-title = ⏱️ **Custom Notifications**

    Set your own notification times ({ $minTime }m - { $maxTime }h before quali closes).

    You can have up to 2 custom notifications.

    Click a slot to set or edit it.

# =======================
# Weather
# =======================
weather-unavailable = ⚠️ Weather data not available
weather-title = 🌤️ **Race Weather Forecast**
weather-practice-q1 = **Practice / Qualify 1:** { $weather }
weather-temp-hum = Temp: { $temp }°C • Humidity: { $hum }%
weather-q2-race-start = **Qualify 2 / Race Start:** { $weather }
weather-race-conditions = **Race Conditions:**
weather-start-0h30m = **Start - 0h30m:**
weather-0h30m-1h00m = **0h30m - 1h00m:**
weather-1h00m-1h30m = **1h00m - 1h30m:**
weather-1h30m-2h00m = **1h30m - 2h00m:**
weather-temp-hum-range = Temp: { $temp } • Humidity: { $hum }
weather-rain-prob = Rain probability: { $rain }
