# FlaskSQLAlchemyBaseModel

## Project Title

**FlaskSQLAlchemyBaseModel**

## Short Description

`FlaskSQLAlchemyBaseModel` is a Python package designed to simplify the creation and management of SQLAlchemy-based ORM models within Flask applications. It provides a robust `BaseModel` class that encapsulates common functionalities such as automatic ID generation (UUID), timestamp management (`created_at`, `updated_at`), and a comprehensive suite of convenience methods for standard database operations (CRUD). By inheriting from this base class, developers can significantly reduce boilerplate code and ensure consistency across their application's data models.

## Features Overview

This package streamlines Flask-SQLAlchemy development with the following key features:

*   **UUID Primary Key:** Automatically generates a unique, immutable identifier (UUID) for each new record, ensuring global uniqueness and easy referencing.
*   **Automatic Timestamps:** Manages `created_at` and `updated_at` fields, automatically populating the creation timestamp and updating the modification timestamp on every save operation.
*   **Simplified CRUD Operations:** Offers intuitive instance methods (`save`, `delete`, `update`) for persisting, removing, and modifying records.
*   **Data Serialization:** Provides a `to_dict()` method to easily convert model instances into Python dictionaries, including handling of related objects for seamless API responses.
*   **Comprehensive Querying Utilities:** Includes a variety of class methods for efficient data retrieval:
    *   `all()`: Fetch all records of a model.
    *   `get(id)`: Retrieve a single record by its primary key ID.
    *   `get_or_404(id)`: Retrieve a single record by ID, raising a 404 HTTP error if not found.
    *   `filter_one(**kwargs)`: Get a single record matching specific criteria.
    *   `filter_all(**kwargs)`: Get all records matching specific criteria.
    *   `filter_and_count_all(**kwargs)`: Count records matching specific criteria.
    *   `count_all()`: Get the total count of all records for a model.
    *   `exists(**kwargs)`: Check if a record matching certain criteria exists.
    *   `paginate(page, per_page)`: Efficiently paginate query results, returning items, total count, pages, current page, and items per page.

## Installation Instructions

To install `FlaskSQLAlchemyBaseModel`, use `pip`:

```bash
pip install FlaskSQLAlchemyBaseModel
```

## Usage Examples

### 1. Initializing with Your Flask Application

Integrate the `db` instance provided by `FlaskSQLAlchemyBaseModel` with your Flask application:

```python
from flask import Flask
from flasksqlalchemybasemodel import db

# Create your Flask app instance
app = Flask(__name__)

# Configure your database URI (e.g., SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///your_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize db with your Flask app
db.init_app(app)

# Recommended: Create tables within an application context
with app.app_context():
    db.create_all()
```

### 2. Defining Your Models

Inherit from `BaseModel` to create your application's data models:

```python
from flasksqlalchemybasemodel import db, BaseModel

class User(BaseModel):
    __tablename__ = 'users'
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    # Add other model-specific columns here
```

### 3. Performing CRUD Operations

Leverage the inherited methods for database interactions:

```python
from your_app_module import db, User # Assuming User model is in your app module

# --- Create (Save) ---
# Create a new user instance
new_user = User(name="Alice Smith", email="alice@example.com")
# Save the user to the database
new_user.save()
print(f"Created user: {new_user.name} with ID: {new_user.id}")

# --- Read (Retrieve) ---
# Get a user by ID
user_by_id = User.get(new_user.id)
if user_by_id:
    print(f"Retrieved user by ID: {user_by_id.name}")

# Filter users by name
alice = User.filter_one(name="Alice Smith")
if alice:
    print(f"Filtered user by name: {alice.email}")

# Get all users
all_users = User.all()
print(f"Total users in DB: {len(all_users)}")

# --- Update ---
# Update an existing user's email
if alice:
    alice.update({"email": "alice.smith@example.com"})
    print(f"Updated user email to: {alice.email}")

# --- Delete ---
# Delete the user
if alice:
    alice.delete()
    print(f"Deleted user: {alice.name}")

# Verify deletion
deleted_user = User.get(new_user.id)
if deleted_user is None:
    print("User successfully deleted.")

# --- To Dictionary Conversion ---
another_user = User(name="Bob Johnson", email="bob@example.com")
another_user.save()
user_dict = another_user.to_dict()
print("User as dictionary:", user_dict)

# --- Pagination ---
# (Assume many users are created for this example)
# first_page = User.paginate(page=1, per_page=10)
# print(f"First page items: {len(first_page['items'])}, Total: {first_page['total']}")
```

## File Structure Summary

The project follows a standard Python package structure:

```
.
├── .github/                 # GitHub Actions workflows for CI/CD
│   ├── workflows/
│   │   ├── installation.yml # Workflow to install the package dependencies
│   │   └── tests.yml        # Workflow to run tests across Python versions
├── flasksqlalchemybasemodel/ # The core Python package source code
│   ├── __init__.py          # Package initialization
│   └── src.py               # Contains the BaseModel class and db instance
├── tests/                   # Unit and integration tests for the package
│   ├── __init__.py
│   ├── app.py               # Test Flask application setup
│   ├── database/
│   │   └── README.md        # Note about the test database
│   └── testAll.py           # Comprehensive tests for BaseModel functionalities
├── .gitignore               # Files and directories to be ignored by Git
├── LICENSE                  # MIT License file
├── README.md                # This README file
├── pyproject.toml           # Poetry project configuration and dependencies
└── requirements.txt         # Pip dependency list (generated from pyproject.toml)
```

## Important Notes

*   **Dependencies:** This package relies on `Flask`, `Flask-SQLAlchemy`, and `SQLAlchemy`. Ensure these are installed in your environment.
*   **Testing:** The `tests/` directory provides extensive unit tests using Python's `unittest` framework, demonstrating the expected behavior of all `BaseModel` methods.
*   **CI/CD:** GitHub Actions workflows are configured to automatically test the module's installation and run its test suite against multiple Python versions (`3.9`, `3.10`, `3.11`, `3.12`) on every push and pull request to the `master` branch, ensuring reliability and compatibility.
*   **Licensing:** The project is open-source and distributed under the MIT License, allowing for broad usage and modification.