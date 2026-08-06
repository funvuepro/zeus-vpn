"""
One-time migration: create Remnawave accounts for all users with an active subscription
who don't yet have a remnawave_uuid. Safe to re-run (skips already-migrated users).

Usage:
    python scripts/migrate_users.py

Requires REMNAWAVE_URL and REMNAWAVE_API_TOKEN in .env (or environment).
"""
import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def main():
    from bot.config import get_settings
    from bot.database.session import AsyncSessionLocal
    from bot.database.models import Subscription, SubscriptionStatus, User
    from bot.services.remnawave import RemnaWaveClient
    from sqlalchemy import select

    s = get_settings()
    rw = RemnaWaveClient(base_url=s.REMNAWAVE_URL, api_token=s.REMNAWAVE_API_TOKEN)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User, Subscription)
            .join(Subscription, Subscription.user_id == User.id)
            .where(
                Subscription.status == SubscriptionStatus.active,
                User.remnawave_uuid.is_(None),
            )
        )
        rows = result.all()

    print(f"Found {len(rows)} users to migrate.")

    migrated = 0
    failed = 0
    for user, sub in rows:
        username = f"user_{user.telegram_id}"
        expires_at = sub.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if expires_at <= now:
            print(f"  SKIP  {username} — subscription already expired")
            continue

        days_remaining = max(1, int((expires_at - now).total_seconds() / 86400))
        try:
            _, rw_uuid = await rw.create_user(username, expire_days=days_remaining)
            async with AsyncSessionLocal() as session:
                db_user = await session.get(User, user.id)
                db_user.remnawave_uuid = rw_uuid
                await session.commit()
            print(f"  OK    {username}  uuid={rw_uuid}  expires_in={days_remaining}d")
            migrated += 1
        except Exception as e:
            print(f"  FAIL  {username}  {e}")
            failed += 1

    await rw.aclose()
    print(f"\nDone. Migrated: {migrated}, Failed: {failed}, Skipped: {len(rows) - migrated - failed}")


if __name__ == "__main__":
    asyncio.run(main())
