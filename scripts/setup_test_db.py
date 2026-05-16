import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from core.database import Base
from modules.tenants.models import Client
from modules.form_engine.models import FieldGroup, CustomField
from core.config import settings

# Use SQLite for testing in sandbox
TEST_DB_URL = "sqlite+aiosqlite:///test.db"

async def setup_test_data():
    engine = create_async_engine(TEST_DB_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        client_id = uuid.uuid4()
        client = Client(
            id=client_id,
            name="Ordinary Tech",
            slug="ordinary-tech",
            bot_token="test_token"
        )
        session.add(client)

        group = FieldGroup(
            client_id=client_id,
            name="Site Information",
            key="site_info",
            display_order=1
        )
        session.add(group)
        await session.flush()

        f1 = CustomField(
            client_id=client_id,
            group_id=group.id,
            key="company_name",
            label="Company Name",
            field_type="text",
            is_required=True,
            display_order=1,
            validation_rules=[{"type": "required"}]
        )
        f2 = CustomField(
            client_id=client_id,
            group_id=group.id,
            key="cement_grade",
            label="Cement Grade",
            field_type="dropdown",
            options=[{"label": "M25", "value": "m25"}, {"label": "M30", "value": "m30"}],
            display_order=2
        )
        session.add_all([f1, f2])
        await session.commit()

        print(f"Test data setup complete. Client ID: {client_id}")
        return client_id

if __name__ == "__main__":
    asyncio.run(setup_test_data())
