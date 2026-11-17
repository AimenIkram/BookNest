# BookNest

A responsive, feature-rich Library Management System built with Python, Django, and MySQL. BookNest provides an intuitive interface for managing book collections, patron registrations, and daily circulation workflows.

---

## About the Project

BookNest is designed to simplify and streamline core library operations. It replaces manual or disorganized book tracking with a centralized digital system that manages book inventory, tracks reader borrowing history, monitors due dates, and prevents inventory discrepancies through automated stock adjustments.

---

## Features

- **Book Management:** Add, view, edit, and delete books with details including title, author, ISBN, category, publication date, and copy counts.
- **Category Management:** Organize books by genres and categories with duplicate prevention and protected deletion.
- **Reader Management:** Register patrons with contact information and track their borrowing history.
- **Issue and Return Books:** Issue available books to registered readers and process returns with automatic inventory updates.
- **Track Active and Overdue Loans:** Monitor current borrowings with dedicated status views for active and overdue loans.
- **Search, Filter, Sort, and Pagination:** Quickly locate books by title, author, or ISBN, filter by category and availability, sort columns, and browse with paginated results.
- **Dashboard with Library Statistics:** View real-time metrics including total books, registered readers, active borrowings, overdue counts, and inventory utilization.
- **User Authentication and Staff Permissions:** Secure login with role-based access control restricting administrative actions (add, edit, delete, issue, return) to staff members.

---

## Tech Stack

- **Backend:** Python, Django
- **Database:** MySQL
- **Frontend:** HTML5, CSS3

---

## Screenshots

> *Screenshots will be added soon.*

- **Dashboard**  
  `[ Placeholder: Dashboard overview with statistics and recent activity ]`

- **Book Catalog**  
  `[ Placeholder: Book catalog with search, filters, and sorting ]`

- **Book Details**  
  `[ Placeholder: Detailed book profile and inventory information ]`

- **Reader Management**  
  `[ Placeholder: Reader directory and patron details ]`

- **Borrowing / Returns**  
  `[ Placeholder: Circulation desk managing active and overdue loans ]`

---

## Getting Started

Follow these steps to set up and run BookNest locally on Windows.

### 1. Clone the Repository
```powershell
git clone https://github.com/AimenIkram/BookNest.git
cd BookNest
```

### 2. Create and Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Requirements
```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to create your local `.env` file:
```powershell
Copy-Item .env.example .env
```
Open `.env` and configure your MySQL database credentials:
```ini
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

DB_NAME=booknest_db
DB_USER=booknest_user
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
```

> **Note:** Make sure you have created your database in MySQL (`CREATE DATABASE booknest_db;`).

### 5. Run Migrations
```powershell
python manage.py migrate
```

### 6. Create Superuser
```powershell
python manage.py createsuperuser
```

---

## Demo Data

Populate the database with realistic sample categories, books, readers, and borrowing records:

```powershell
python manage.py seed_demo_data
```

This command seeds 10 categories, 40 books, 20 readers, and 25 circulation records (active, overdue, and returned) without generating duplicates if run again.

---

## Run Locally

Start the development server:

```powershell
python manage.py runserver
```

Open your browser and visit: `http://127.0.0.1:8000/`

---

## Author

**Aimen Ikram**  
- GitHub: [https://github.com/AimenIkram](https://github.com/AimenIkram)  
- Repository: [https://github.com/AimenIkram/BookNest](https://github.com/AimenIkram/BookNest)
