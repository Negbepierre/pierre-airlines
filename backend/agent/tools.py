# tools.py — The agent's hands
# Each function here is one thing the agent can DO
# Think of these like buttons the agent can press

from datetime import datetime

# ── SIMULATED DATABASE ──
# In production this would be real AWS calls
# For now we simulate realistic data

BOOKINGS = {
    "PR-48291": {
        "passenger": "Mr James Chen",
        "route": "London LHR → Paris CDG",
        "flight": "PA2847",
        "date": "24 March 2026",
        "class": "Economy",
        "passengers": 2,
        "status": "Confirmed",
        "miles": 12500
    },
    "PR-55102": {
        "passenger": "Ms Sarah Williams",
        "route": "London LHR → Dubai DXB",
        "flight": "PA1043",
        "date": "30 March 2026",
        "class": "Business",
        "passengers": 1,
        "status": "Confirmed",
        "miles": 45000
    }
}

FLIGHTS = {
    "PA2847": {
        "route": "LHR → CDG",
        "scheduled": "09:00",
        "status": "Delayed",
        "delay_minutes": 220,
        "reason": "Operational",
        "upgrade_available": True,
        "upgrade_price": 180,
        "next_available": "PA2849 — tomorrow 10:15"
    },
    "PA1043": {
        "route": "LHR → DXB",
        "scheduled": "14:30",
        "status": "On Time",
        "delay_minutes": 0,
        "upgrade_available": True,
        "upgrade_price": 420,
        "next_available": "PA1045 — tomorrow 16:00"
    }
}

# ── TOOL FUNCTIONS ──
# Each one returns a string the agent reads and uses to form its reply

def check_booking(booking_ref: str) -> str:
    """Look up a booking by reference number"""
    ref = booking_ref.upper().strip()
    if ref in BOOKINGS:
        b = BOOKINGS[ref]
        return f"""
BOOKING FOUND: {ref}
Passenger: {b['passenger']}
Route: {b['route']}
Flight: {b['flight']}
Date: {b['date']}
Class: {b['class']}
Passengers: {b['passengers']}
Status: {b['status']}
Pierre Miles balance: {b['miles']:,}
        """.strip()
    return f"No booking found for reference {ref}. Please check and try again."


def check_flight_status(flight_number: str) -> str:
    """Check live flight status and delay information"""
    fn = flight_number.upper().strip()
    if fn in FLIGHTS:
        f = FLIGHTS[fn]
        if f['delay_minutes'] > 0:
            hours = f['delay_minutes'] // 60
            mins = f['delay_minutes'] % 60
            return f"""
FLIGHT STATUS: {fn}
Route: {f['route']}
Scheduled: {f['scheduled']}
Status: ⚠️ DELAYED by {hours}h {mins}m
Reason: {f['reason']}
Upgrade available: {'Yes — £' + str(f['upgrade_price']) + 'pp' if f['upgrade_available'] else 'No'}
Next available flight: {f['next_available']}
            """.strip()
        return f"Flight {fn} | Route: {f['route']} | Status: ✅ On Time | Departure: {f['scheduled']}"
    return f"Flight {fn} not found. Please verify the flight number."


def check_upgrade_availability(flight_number: str, cabin_class: str = "Business") -> str:
    """Check if upgrades are available on a flight"""
    fn = flight_number.upper().strip()
    if fn in FLIGHTS:
        f = FLIGHTS[fn]
        if f['upgrade_available']:
            return f"""
UPGRADE AVAILABILITY: {fn}
Upgrade to {cabin_class}: AVAILABLE
Price: £{f['upgrade_price']} per person
To confirm: reply with 'confirm upgrade on {fn}'
Note: Price is guaranteed for 10 minutes
            """.strip()
        return f"No upgrades currently available on flight {fn}."
    return f"Flight {fn} not found."


def calculate_compensation(flight_number: str) -> str:
    """Calculate EU261 compensation entitlement for a delayed flight"""
    fn = flight_number.upper().strip()
    if fn in FLIGHTS:
        f = FLIGHTS[fn]
        delay = f['delay_minutes']
        if delay >= 180:
            # LHR-CDG is under 1500km
            amount = 250
            return f"""
COMPENSATION ENTITLEMENT: {fn}
Delay: {delay} minutes ({delay//60}h {delay%60}m)
Distance: Under 1500km
EU261 Entitlement: €{amount} per passenger
Pierre Miles bonus: 500 miles (already credited)
Lounge voucher: Issued (valid today)
To claim: I can raise a compensation request now
            """.strip()
        elif delay >= 120:
            return f"Flight {fn} delayed {delay} mins — entitled to meals/refreshments but not cash compensation (threshold is 3 hours)."
        else:
            return f"Flight {fn} delay of {delay} mins does not qualify for EU261 compensation."
    return f"Flight {fn} not found."


def rebook_flight(booking_ref: str, flight_number: str) -> str:
    """Rebook a passenger onto the next available flight"""
    ref = booking_ref.upper().strip()
    fn = flight_number.upper().strip()
    if ref in BOOKINGS and fn in FLIGHTS:
        next_flight = FLIGHTS[fn]['next_available']
        return f"""
REBOOKING CONFIRMED: {ref}
Original flight: {fn}
New flight: {next_flight}
No change fee applied (operational delay)
Confirmation email sent to passenger
New boarding pass will be issued at check-in
        """.strip()
    return "Unable to process rebooking — please verify booking reference and flight number."


def create_support_ticket(
    booking_ref: str,
    issue_type: str,
    description: str,
    priority: str = "Normal"
) -> str:
    """Create a support ticket and escalate to human specialist"""
    import random
    ticket_id = f"PA-{random.randint(10000, 99999)}"
    timestamp = datetime.now().strftime("%d %b %Y %H:%M")

    specialists = {
        "refund": "Refunds & Compensation Team",
        "complaint": "Customer Relations Team",
        "medical": "Special Assistance Team",
        "legal": "Legal & Compliance Team",
        "baggage": "Baggage Services Team",
        "default": "Senior Support Specialist"
    }

    team = specialists.get(issue_type.lower(), specialists["default"])

    return f"""
🎫 TICKET CREATED: [{ticket_id}]
Issue: {description}
Booking: {booking_ref}
Priority: {priority}
Assigned to: {team}
Created: {timestamp}
ETA: Within 2 hours (business hours) / Next morning (out of hours)
Email confirmation sent to passenger
    """.strip()