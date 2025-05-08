import streamlit as st
import sqlalchemy
from sqlalchemy import text
import os
import time

# Import Connector from Google Cloud
from google.cloud.sql.connector import Connector, IPTypes

# Initialize Connector globally
# This allows it to be reused without re-initializing on every Streamlit rerun.
# The connector itself manages a connection pool internally for efficiency.
if "connector" not in st.session_state:
    st.session_state.connector = Connector()

# Function to get a SQLAlchemy engine
def get_engine():
    # Use the connector from session_state to ensure it's the same instance
    connector_instance = st.session_state.connector

    def connect_with_connector():
        # This is the 'creator' function that SQLAlchemy will use
        # to obtain new DBAPI connections.
        return connector_instance.connect(
            os.environ["INSTANCE_CONNECTION_NAME"],
            "pg8000",  # DBAPI driver name
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASS"],
            db=os.environ["DB_NAME"],
            ip_type=IPTypes.PRIVATE if os.environ.get("PRIVATE_IP") == "true" else IPTypes.PUBLIC,
            enable_iam_auth=os.environ.get("DB_IAM_AUTH") == "true"
        )

    try:
        # Primary method: Cloud SQL Connector with SQLAlchemy
        if all(k in os.environ for k in ("INSTANCE_CONNECTION_NAME", "DB_USER", "DB_NAME")):
            engine = sqlalchemy.create_engine(
                "postgresql+pg8000://",  # SQLAlchemy dialect + DBAPI driver
                creator=connect_with_connector,
                pool_size=5, # Example: configure pool size
                max_overflow=2,
                pool_timeout=30,
                pool_recycle=1800 # Example: recycle connections periodically
            )
            return engine
        # Fallback for local testing with DB_HOST (e.g., via local proxy or direct IP)
        elif os.environ.get("DB_HOST") and all(k in os.environ for k in ("DB_USER", "DB_PASS", "DB_NAME")):
            st.sidebar.warning("Using fallback local connection (DB_HOST).")
            db_user = os.environ["DB_USER"]
            db_pass = os.environ["DB_PASS"]
            db_name = os.environ["DB_NAME"]
            db_host = os.environ["DB_HOST"]
            db_port = os.environ.get("DB_PORT", "5432")
            engine_url_str = f"postgresql+pg8000://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
            engine = sqlalchemy.create_engine(engine_url_str)
            return engine
        else:
            st.error("Database connection parameters not fully configured. Check INSTANCE_CONNECTION_NAME or DB_HOST and related credentials.")
            return None
    except Exception as e:
        st.error(f"Error creating database engine: {e}")
        return None

# Create a global engine instance.
# In Streamlit, this will re-run, but get_engine() is designed to be idempotent
# or use cached components like the connector from st.session_state.
engine = get_engine()

# --- Database Initialization ---
def init_db():
    if engine is None:
        # Error already shown by get_engine() or during its call
        return
    try:
        with engine.connect() as conn:
            with conn.begin():  # Begin transaction
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        title VARCHAR(255) NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """))
            # Transaction is committed automatically upon exiting 'conn.begin()'
            # No explicit conn.commit() needed here.
        st.success("Tasks table initialized (or already exists).")
    except Exception as e:
        st.error(f"Error initializing table: {e}")
        # Transaction is rolled back automatically on exception by 'conn.begin()'

# --- CRUD Operations ---
def add_task(title, description):
    if engine is None: return
    try:
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(
                    text("INSERT INTO tasks (title, description) VALUES (:title, :description)"),
                    {"title": title, "description": description}
                )
            st.success(f"Task '{title}' added successfully!")
    except Exception as e:
        st.error(f"Error adding task: {e}")

def view_tasks():
    if engine is None: return []
    tasks_list = []
    try:
        with engine.connect() as conn:
            # No explicit transaction needed for SELECT, but consistent use of connect() is fine.
            result = conn.execute(text("SELECT id, title, description, TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at FROM tasks ORDER BY created_at DESC"))
            for row in result:
                # Access columns by name or index. Using ._asdict() or ._mapping for dict conversion.
                tasks_list.append(row._asdict())
        return tasks_list
    except Exception as e:
        st.error(f"Error fetching tasks: {e}")
        return []

def delete_task(task_id):
    if engine is None: return
    try:
        with engine.connect() as conn:
            with conn.begin():
                conn.execute(
                    text("DELETE FROM tasks WHERE id = :task_id"),
                    {"task_id": task_id}
                )
            st.success(f"Task ID {task_id} deleted successfully!")
    except Exception as e:
        st.error(f"Error deleting task: {e}")

# --- Streamlit UI ---
st.set_page_config(page_title="Cloud Run Task Manager", layout="wide")
st.title("📝 Cloud Run Task Manager")
st.subheader("A Streamlit app connected to Cloud SQL, secured with IAP")

if engine:
    init_db() # Initialize DB on first load or if table doesn't exist
else:
    st.error("Database engine is not available. CRUD operations will fail. Please check configurations.")
    st.stop()


# Sidebar for IAP User Info (if available through headers)
st.sidebar.title("User Info (via IAP)")
# ... (rest of your IAP user info code remains the same) ...
# Sidebar for IAP User Info (if available through query parameters)
st.sidebar.title("User Info (via IAP)")
try:
    # Access query parameters using the stable st.query_params API
    # st.query_params.get() returns the first value of the query parameter as a string, or None if not found.
    user_email_str = st.query_params.get("X-Goog-Authenticated-User-Email")
    user_id_str = st.query_params.get("X-Goog-Authenticated-User-Id")

    user_email = user_email_str.replace("accounts.google.com:", "") if user_email_str else "Not Authenticated"
    user_id = user_id_str.replace("accounts.google.com:", "") if user_id_str else "N/A"
    
    st.sidebar.write(f"**Email:** {user_email}")
    st.sidebar.write(f"**User ID:** {user_id}")
except Exception as e:
    # Catching a generic exception might hide specific issues. Consider more specific error handling if needed.
    st.sidebar.warning(f"Could not retrieve IAP user info from query parameters. Error: {e}")
    st.sidebar.info("This info is typically available when deployed behind IAP and if IAP is configured to pass identity as query parameters.")


# --- Main App Sections ---
menu = ["View Tasks", "Add Task", "Delete Task"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Add Task":
    st.subheader("Add New Task")
    with st.form("add_task_form"):
        task_title = st.text_input("Task Title", max_chars=250)
        task_description = st.text_area("Task Description")
        submit_button = st.form_submit_button(label="Add Task")

        if submit_button:
            if not task_title:
                st.warning("Task title is required.")
            else:
                add_task(task_title, task_description)


elif choice == "View Tasks":
    st.subheader("Current Tasks")
    all_tasks = view_tasks()
    if all_tasks:
        for task in all_tasks:
            with st.expander(f"{task['title']} (ID: {task['id']}) - Created: {task['created_at']}"):
                st.write(task['description'] if task['description'] else "_No description_")
                # Use a unique key for buttons inside loops
                if st.button(f"Delete Task ID {task['id']}", key=f"del_{task['id']}"):
                    delete_task(task['id'])
                    st.rerun() # Rerun to refresh the task list immediately
        st.info(f"Total tasks: {len(all_tasks)}")
    else:
        st.info("No tasks found. Add some!")


elif choice == "Delete Task":
    st.subheader("Delete a Task")
    all_tasks_for_delete = view_tasks() # Get tasks to populate dropdown
    if all_tasks_for_delete:
        task_options = {task['id']: f"ID: {task['id']} - {task['title']}" for task in all_tasks_for_delete}
        if not task_options: # Handles case where tasks become empty after initial fetch
            st.info("No tasks available to delete.")
        else:
            task_to_delete_id = st.selectbox("Select Task to Delete", options=list(task_options.keys()), format_func=lambda x: task_options[x])
            if st.button("Delete Selected Task", type="primary"):
                delete_task(task_to_delete_id)
                st.rerun() # Rerun to refresh
    else:
        st.info("No tasks to delete.")

st.markdown("---")
st.caption(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

# The global Connector instance in st.session_state will be cleaned up
# automatically when the session ends or can be explicitly closed if needed,
# though for Cloud Run, per-request handling is typical and the connector manages its pool.