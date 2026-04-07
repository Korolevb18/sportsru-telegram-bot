import asyncio
from db.database import clean_old_sent_items

async def main():
    clean_old_sent_items(7)
    print("Старые записи sent_items удалены")

if __name__ == "__main__":
    asyncio.run(main())