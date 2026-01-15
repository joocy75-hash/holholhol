import asyncio
from app.database import AdminSessionLocal
from app.services.admin_user_service import AdminUserService
from app.models.admin_user import AdminRole


async def create_default_admin():
    async with AdminSessionLocal() as session:
        service = AdminUserService(session)

        # Check if admin already exists
        admin = await service.get_by_username("admin")
        if admin:
            print("Admin user already exists.")
            return

        # Create default admin
        print("Creating default admin user...")
        await service.create_admin_user(
            username="admin", email="admin@example.com", password="admin", role=AdminRole.admin
        )
        print("Default admin user created successfully!")
        print("Username: admin")
        print("Email: admin@example.com")
        print("Password: admin")


if __name__ == "__main__":
    asyncio.run(create_default_admin())
