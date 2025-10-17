# StudyBuddy — Study Group Finder
## Project Description
**StudyBuddy** is a lightweight web application that helps students create, join, and manage study groups for their classes.  
It allows users to add study groups, view existing ones, edit their details, and delete them when no longer needed.  
---
## Objectives 
- Build a complete full-stack app.  
- Follow Agile methodology with short sprints and version control through GitHub.  
- Emphasize clean, simple, and modular code.
---
## Core Features
| Feature | Description | CRUD |
|----------|--------------|------|
| **View Groups** | Display all study groups stored in the database. | Read |
| **Create Group** | Add a new study group with name, subject, and description. | Create |
| **Edit Group** | Modify details of an existing study group. | Update |
| **Delete Group** | Remove a study group from the database. | Delete |
| **Join Group** | Add yourself as a member of a study group. | Update |
---
## Tech Stack
| Layer | Technology |
|-------|-------------|
| **Frontend** | HTML, CSS, Bootstrap (optional), basic JavaScript |
| **Backend** | Python (Flask) |
| **Database** | SQLite (simple, file-based) |
| **Version Control** | Git + GitHub |
---
## Agile Sprint Planning

### Sprint 1: Foundation (Oct 17 - Oct 31)
**Goals:**
- Set up Flask development environment
- Create database schema and models
- Implement "View Groups" feature (READ)
- Create basic HTML templates and navigation
- Set up project documentation

**Deliverables:**
- Working Flask application structure
- SQLite database with StudyGroup table
- Home page displaying all study groups
- Basic CSS styling

---

### Sprint 2: Core CRUD Operations (Nov 1 - Nov 14)
**Goals:**
- Implement "Create Group" feature (CREATE)
- Implement "Edit Group" feature (UPDATE)
- Implement "Delete Group" feature (DELETE)
- Add form validation
- Improve UI with Bootstrap

**Deliverables:**
- Create group form with validation
- Edit group functionality
- Delete group with confirmation
- Responsive Bootstrap styling

--- 

### Sprint 3: Enhancement & Testing (Nov 15 - Dec 5)
**Goals:**
- Implement "Join Group" feature
- Add search/filter functionality
- Write unit tests
- Complete documentation
- Bug fixes and refinements

**Deliverables:**
- Join group functionality
- Search/filter by subject
- Test

---

## Example Data Model
| Column | Type | Description |
|---------|------|-------------|
| `id` | Integer (Primary Key) | Unique group ID |
| `group_name` | Text | Name of the study group |
| `subject` | Text | Subject or course name |
| `description` | Text | Short summary of the group |
| `members` | Text | List of group members |

### Example
```json
{
  "group_name": "Physics 101 Study Group",
  "subject": "Physics",
  "description": "Weekly study sessions for Physics 101",
  "members": ["Jose", "Adan"]
}
```

## Installation & Setup

### Option 1 — Using Python venv
```bash
# 1️ Create virtual environment
python -m venv venv
# 2️ Activate the environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
# 3️ Install dependencies
pip install -r requirements.txt
# 4️ Run the Flask app
python app.py
```
### Option 2 — Using Conda
```bash
# 1 Create the environment from YAML file
conda env create -n studybuddy -f environment.yml
# 2️ Activate the environment
conda activate studybuddy
# 3️ Run the Flask app
python app.py
```
