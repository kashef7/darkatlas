from app.database import SessionLocal
from app.models.user import User, Role
from app.core.security import get_password_hash

def seed():
    """Seed default users. Requires schema to exist (run `alembic upgrade head` first)."""
    db = SessionLocal()
    try:
        # Create admin user
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            admin_user = User(
                username="admin",
                hashed_password=get_password_hash("adminpassword"),
                role=Role.admin
            )
            db.add(admin_user)
            print("Created admin user: username='admin', password='adminpassword'")
        else:
            print("Admin user already exists")

        # Create editor user
        editor_user = db.query(User).filter(User.username == "editor").first()
        if not editor_user:
            editor_user = User(
                username="editor",
                hashed_password=get_password_hash("editorpassword"),
                role=Role.editor
            )
            db.add(editor_user)
            print("Created editor user: username='editor', password='editorpassword'")
        else:
            print("Editor user already exists")

        # Create viewer user
        viewer_user = db.query(User).filter(User.username == "viewer").first()
        if not viewer_user:
            viewer_user = User(
                username="viewer",
                hashed_password=get_password_hash("viewerpassword"),
                role=Role.viewer
            )
            db.add(viewer_user)
            print("Created viewer user: username='viewer', password='viewerpassword'")
        else:
            print("Viewer user already exists")

        db.commit()
        print("Database seeding completed successfully.")
    except Exception as e:
        print(f"Error during seeding: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
