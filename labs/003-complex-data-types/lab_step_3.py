"""
Lab Step 3: Range & Array Types (Specialized Data Types)

This script demonstrates:
- PostgreSQL specialized Array types (text[]) and Range types (tstzrange)
- Database-level non-overlapping bounds using GiST exclusion constraints
- Catching and analyzing Unique/Exclusion Violation errors when double-bookings are attempted
- Querying arrays via the GIN containment operator (@>)
- Querying ranges via the GiST overlap operator (&&)
"""

from datetime import UTC, datetime

from app.dependencies import get_session_factory, init_db
from app.models import RoomBooking
from loguru import logger
from psycopg.types.range import Range
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def print_separator(title: str) -> None:
    """Print a visual separator for log sections."""
    logger.info(f"{'=' * 20} {title} {'=' * 20}")


def demonstrate_exclusion_constraint() -> None:
    """Demonstrate database-level double-booking prevention using GiST exclusion constraints."""
    print_separator("DATABASE-LEVEL DOUBLE-BOOKING BLOCKED BY EXCLUSION CONSTRAINT")

    session_factory = get_session_factory()

    # Define booking times using python timezone-aware datetimes
    monday_09_00 = datetime(2026, 6, 1, 9, 0, 0, tzinfo=UTC)
    monday_11_00 = datetime(2026, 6, 1, 11, 0, 0, tzinfo=UTC)

    monday_12_00 = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    monday_14_00 = datetime(2026, 6, 1, 14, 0, 0, tzinfo=UTC)

    monday_10_00 = datetime(2026, 6, 1, 10, 0, 0, tzinfo=UTC)
    monday_13_00 = datetime(2026, 6, 1, 13, 0, 0, tzinfo=UTC)

    # 1. Insert valid non-overlapping bookings
    logger.info("[Action] Inserting valid, non-overlapping bookings for Room 'Ada'...")
    with session_factory() as session:
        booking1 = RoomBooking(
            room_name="Ada",
            booking_period=Range(monday_09_00, monday_11_00),
            amenities=["projector", "whiteboard", "ac"],
        )
        booking2 = RoomBooking(
            room_name="Ada",
            booking_period=Range(monday_12_00, monday_14_00),
            amenities=["projector", "whiteboard", "video-conference"],
        )
        session.add_all([booking1, booking2])
        session.commit()
        logger.info("[Success] Room 'Ada' booked successfully for 09:00-11:00 and 12:00-14:00")

    # 2. Attempt double-booking
    logger.info("\n[Action] Attempting to double-book Room 'Ada' for 10:00-13:00 (Overlaps both bookings!)...")
    with session_factory() as session:
        bad_booking = RoomBooking(
            room_name="Ada",
            booking_period=Range(monday_10_00, monday_13_00),
            amenities=["projector"],
        )
        session.add(bad_booking)
        try:
            session.commit()
            logger.error("[Failed] CRITICAL: Overlapping booking was allowed! Exclusion constraint failed!")
        except IntegrityError as ex:
            session.rollback()
            logger.info("[Blocked] SUCCESS! PostgreSQL exclusion constraint blocked the double-booking.")
            logger.warning(f"  [Error Details] {ex.orig}")


def demonstrate_array_and_range_queries() -> None:
    """Demonstrate how GIN indexes accelerate array containment and GiST range overlap searches."""
    print_separator("GIN ON ARRAYS & GIST ON RANGE QUERY BENCHMARKS")

    session_factory = get_session_factory()

    with session_factory() as session:

        def t_day(hour: int) -> datetime:
            return datetime(2026, 6, 2, hour, 0, 0, tzinfo=UTC)

        b1 = RoomBooking(room_name="Turing", booking_period=Range(t_day(9), t_day(10)), amenities=["whiteboard", "ac"])
        b2 = RoomBooking(
            room_name="Lovelace", booking_period=Range(t_day(10), t_day(12)), amenities=["projector", "ac"]
        )
        b3 = RoomBooking(
            room_name="Hopper", booking_period=Range(t_day(14), t_day(16)), amenities=["projector", "whiteboard"]
        )

        session.add_all([b1, b2, b3])
        session.commit()

        # Run ANALYZE to update statistics
        session.execute(text("ANALYZE room_bookings"))
        session.commit()

    with session_factory() as session:
        # Create GIN index on amenities array column
        logger.info("[Action] Creating GIN index on amenities array column...")
        session.execute(text("CREATE INDEX idx_room_bookings_amenities ON room_bookings USING GIN (amenities)"))
        session.commit()

        # Force GIN usage by disabling sequential scans for demonstration
        session.execute(text("SET enable_seqscan = off"))

        # Array containment query (@>)
        logger.info("\n[Query 1] Array containment search: Find rooms with 'projector' AND 'whiteboard':")
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT room_name, amenities
            FROM room_bookings
            WHERE amenities @> ARRAY['projector', 'whiteboard']::varchar[]
        """)
        )
        for row in result:
            logger.info(f"  {row[0]}")

        # Range overlap query (&&)
        logger.info("\n[Query 2] Range overlap search: Find bookings overlapping Tuesday 11:00-15:00:")
        target_range = Range(
            datetime(2026, 6, 2, 11, 0, 0, tzinfo=UTC),
            datetime(2026, 6, 2, 15, 0, 0, tzinfo=UTC),
        )
        result = session.execute(
            text("""
            EXPLAIN (ANALYZE, BUFFERS)
            SELECT room_name, booking_period
            FROM room_bookings
            WHERE booking_period && :target_period
        """),
            {"target_period": target_range},
        )
        for row in result:
            logger.info(f"  {row[0]}")

        session.execute(text("SET enable_seqscan = on"))


def main() -> None:
    """Main entry point for Step 3."""
    logger.info("=" * 60)
    logger.info("LAB STEP 3: Range & Array Types (Specialized Data Types)")
    logger.info("=" * 60)

    logger.info("==> [Phase 1] Initializing database...")
    init_db()

    # Execute step routines
    logger.info("==> [Phase 2] Demonstrating double-booking blocked by exclusion constraints...")
    demonstrate_exclusion_constraint()

    logger.info("==> [Phase 3] Demonstrating specialized range and array query executions...")
    demonstrate_array_and_range_queries()

    logger.info("\n" + "=" * 60)
    logger.info("Lab Step 3 Complete!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
