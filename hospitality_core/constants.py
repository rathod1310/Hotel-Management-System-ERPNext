# Hospitality Core Constants

class RoomStatus:
    AVAILABLE = "Available"
    RESERVED = "Reserved"
    OCCUPIED = "Occupied"
    DIRTY = "Dirty"
    OUT_OF_ORDER = "Out of Order"

    ALL = (AVAILABLE, RESERVED, OCCUPIED, DIRTY, OUT_OF_ORDER)


class ReservationStatus:
    RESERVED = "Reserved"
    CHECKED_IN = "Checked In"
    CHECKED_OUT = "Checked Out"
    CANCELLED = "Cancelled"

    ALL = (RESERVED, CHECKED_IN, CHECKED_OUT, CANCELLED)

