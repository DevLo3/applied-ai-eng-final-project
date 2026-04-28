import os

import streamlit as st

from pawpal_system import BusyPeriod, Parent, Pet, PRIORITY_ORDER, Recurrence, Schedule, Scheduler, Task, TimePreference
import rag

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered", initial_sidebar_state="collapsed")

st.title("🐾 PawPal+")

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------

if "owner" not in st.session_state:
    st.session_state.owner = None

if "pets" not in st.session_state:
    st.session_state.pets = []

if "tasks" not in st.session_state:
    st.session_state.tasks = []

if "schedule" not in st.session_state:
    st.session_state.schedule = None

if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

if "gemini_key_valid" not in st.session_state:
    st.session_state.gemini_key_valid = None  # None = unchecked, True = valid, False = invalid

if "gemini_key_error" not in st.session_state:
    st.session_state.gemini_key_error = ""

# ---------------------------------------------------------------------------
# Section 1: Owner
# ---------------------------------------------------------------------------

st.subheader("Owner")

if st.session_state.owner is None:
    with st.form("owner_form"):
        owner_name = st.text_input("Name", value="Jordan")
        owner_email = st.text_input("Email", value="jordan@example.com")
        owner_location = st.text_input("Location", value="Portland, OR")
        pref_options = [p.value for p in TimePreference]
        selected_prefs = st.multiselect("Time preferences", pref_options, default=["morning", "evening"])
        submitted = st.form_submit_button("Save Owner")

    if submitted:
        prefs = [TimePreference(p) for p in selected_prefs]
        st.session_state.owner = Parent(
            name=owner_name,
            email=owner_email,
            location=owner_location,
            time_preferences=prefs,
        )
        st.rerun()
else:
    owner = st.session_state.owner
    st.success(f"Owner: **{owner.name}** — {owner.email} ({owner.location})")
    if st.button("Edit Owner"):
        st.session_state.owner = None
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Section 2: Pets
# ---------------------------------------------------------------------------

st.subheader("Pets")

with st.form("pet_form"):
    pet_name = st.text_input("Pet name", value="Mochi")
    pet_age = st.number_input("Age (years)", min_value=0, max_value=30, value=3)
    pet_breed = st.text_input("Breed", value="Shiba Inu")
    pet_weight = st.number_input("Weight (lbs)", min_value=0.1, max_value=300.0, value=20.5)
    add_pet = st.form_submit_button("Add Pet")

if add_pet:
    new_pet = Pet(name=pet_name, age=int(pet_age), breed=pet_breed, weight=float(pet_weight))
    st.session_state.pets = st.session_state.pets + [new_pet]
    if st.session_state.owner is not None:
        st.session_state.owner.pets = st.session_state.pets

if st.session_state.pets:
    for pet in st.session_state.pets:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.write(f"**{pet.name}** — {pet.breed}, {pet.age} yrs, {pet.weight} lbs")
        with col2:
            if st.button("Remove", key=f"remove_pet_{pet.name}"):
                pet.delete_pet()
                st.session_state.pets = [p for p in st.session_state.pets if p.name != pet.name]
                st.rerun()
else:
    st.info("No pets added yet.")

st.divider()

# ---------------------------------------------------------------------------
# Section 3: Tasks
# ---------------------------------------------------------------------------

st.subheader("Tasks")

pet_names = [p.name for p in st.session_state.pets]

with st.form("task_form"):
    task_title = st.text_input("Task title", value="Morning walk")
    task_type = st.text_input("Task type", value="exercise")
    col1, col2, col3 = st.columns(3)
    with col1:
        duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
    with col2:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
    with col3:
        daily_freq = st.number_input("Daily frequency", min_value=1, max_value=10, value=1)
    min_interval_hrs = st.number_input(
        "Min hours between occurrences (0 = no constraint)",
        min_value=0, max_value=24, value=0,
    )
    col1, col2 = st.columns(2)
    with col1:
        target_pet_name = st.selectbox("For pet", options=pet_names if pet_names else ["(add a pet first)"])
    with col2:
        recurrence_str = st.selectbox("Recurrence", ["none"] + [r.value for r in Recurrence])
    add_task = st.form_submit_button("Add Task")

if add_task and pet_names:
    duplicate = any(
        t.name == task_title and (t.target_pet.name if t.target_pet else "") == target_pet_name
        for t in st.session_state.tasks
    )
    if duplicate:
        st.warning(f"A task named '{task_title}' for {target_pet_name} already exists.")
    else:
        target_pet = next((p for p in st.session_state.pets if p.name == target_pet_name), None)
        new_task = Task(
            name=task_title,
            task_type=task_type,
            duration=int(duration),
            priority=priority,
            daily_frequency=int(daily_freq),
            min_interval=int(min_interval_hrs) * 60,
            target_pet=target_pet,
            recurrence=Recurrence(recurrence_str) if recurrence_str != "none" else None,
            responsible_parents=[st.session_state.owner] if st.session_state.owner else [],
        )
        if target_pet is not None:
            target_pet.add_task(new_task)
        st.session_state.tasks = st.session_state.tasks + [new_task]

if st.session_state.tasks:
    st.write("Current tasks:")
    for i, task in enumerate(sorted(st.session_state.tasks, key=lambda t: PRIORITY_ORDER.get(t.priority, 99))):
        col1, col2 = st.columns([5, 1])
        with col1:
            pet_label = task.target_pet.name if task.target_pet else "—"
            recur_label = f" · {task.recurrence.value}" if task.recurrence else ""
            due_label = f" (next due {task.next_due})" if task.next_due else ""
            label = (
                f"{task.name} ({pet_label}) — {task.duration} min x{task.daily_frequency}"
                f" [{task.priority}]{recur_label}{due_label}"
            )
            checked = st.checkbox(label, value=task.is_complete, key=f"task_{i}")
            if checked and not task.is_complete:
                next_occ = task.mark_complete()
                if next_occ is not None:
                    if next_occ.target_pet is not None:
                        next_occ.target_pet.add_task(next_occ)
                    st.session_state.tasks = st.session_state.tasks + [next_occ]
                    st.rerun()
            elif not checked and task.is_complete:
                task.mark_incomplete()
        with col2:
            if st.button("Delete", key=f"delete_task_{i}"):
                task.delete()
                st.session_state.tasks = [t for t in st.session_state.tasks if t is not task]
                st.rerun()
else:
    st.info("No tasks added yet.")

st.divider()

# ---------------------------------------------------------------------------
# Section 4: Generate Schedule
# ---------------------------------------------------------------------------

st.subheader("Generate Schedule")

if st.button("Generate Schedule"):
    if not st.session_state.owner:
        st.warning("Please add an owner before generating a schedule.")
    elif not st.session_state.pets:
        st.warning("Please add at least one pet before generating a schedule.")
    elif not st.session_state.tasks:
        st.warning("Please add at least one task before generating a schedule.")
    else:
        for t in st.session_state.tasks:
            t.mark_incomplete()
        scheduler = Scheduler(
            target_pets=st.session_state.pets,
            parents=[st.session_state.owner],
            tasks=st.session_state.tasks,
        )
        st.session_state.schedule = scheduler.generate_schedule()

if st.session_state.schedule:
    schedule = st.session_state.schedule

    # ── Header ────────────────────────────────────────────────────────────────
    st.success(
        f"Schedule covers **{', '.join(schedule.effective_days)}** — "
        f"{schedule.start_time.strftime('%I:%M %p')} to {schedule.end_time.strftime('%I:%M %p')}"
    )

    # ── Conflict warnings ─────────────────────────────────────────────────────
    if schedule.conflicts:
        st.markdown("#### Scheduling Conflicts")
        for conflict in schedule.conflicts:
            st.warning(conflict)
    else:
        st.success(
            f"No conflicts detected across {schedule.calculate_task_count()} scheduled tasks."
        )

    # ── Full sorted schedule table ────────────────────────────────────────────
    st.markdown(
        f"#### Full Schedule "
        f"({schedule.calculate_task_count()} of {len(st.session_state.tasks)} tasks placed)"
    )
    sorted_tasks = sorted(schedule.tasks_scheduled)
    st.dataframe(
        [
            {
                "Time":     t.scheduled_time.strftime("%I:%M %p") if t.scheduled_time else "—",
                "Task":     t.name,
                "Pet":      t.target_pet.name if t.target_pet else "—",
                "Duration": f"{t.duration} min",
                "×/day":    t.daily_frequency,
                "Priority": t.priority.capitalize(),
                "Recurs":   t.recurrence.value if t.recurrence else "—",
            }
            for t in sorted_tasks
        ],
        use_container_width=True,
        hide_index=True,
    )

    # ── Per-pet filtered tabs (uses Schedule.filter_tasks) ────────────────────
    pet_names_in_schedule = sorted({
        t.target_pet.name for t in schedule.tasks_scheduled if t.target_pet
    })
    if pet_names_in_schedule:
        st.markdown("#### By Pet")
        for tab, pet_name in zip(st.tabs(pet_names_in_schedule), pet_names_in_schedule):
            with tab:
                pet_tasks = sorted(schedule.filter_tasks(pet_name=pet_name))
                st.dataframe(
                    [
                        {
                            "Time":     t.scheduled_time.strftime("%I:%M %p") if t.scheduled_time else "—",
                            "Task":     t.name,
                            "Duration": f"{t.duration} min",
                            "×/day":    t.daily_frequency,
                            "Priority": t.priority.capitalize(),
                            "Recurs":   t.recurrence.value if t.recurrence else "—",
                        }
                        for t in pet_tasks
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

    # ── Reasoning expander ────────────────────────────────────────────────────
    with st.expander("Scheduling reasoning"):
        st.text(schedule.generate_reasoning_text())

st.divider()

# ---------------------------------------------------------------------------
# Section 5: Gemini API key
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Gemini API Key")
    key_input = st.text_input(
        "Enter your Gemini API key",
        value=st.session_state.gemini_api_key,
        type="password",
        help="Required for Pet Documents Q&A. Get a free key at aistudio.google.com.",
    )
    if key_input != st.session_state.gemini_api_key:
        st.session_state.gemini_api_key = key_input
        st.session_state.gemini_key_valid = None
        st.session_state.gemini_key_error = ""
        os.environ["GEMINI_API_KEY"] = key_input

    if st.session_state.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = st.session_state.gemini_api_key.strip()
        if st.button("Validate Key"):
            with st.spinner("Checking…"):
                try:
                    rag.validate_key()
                    st.session_state.gemini_key_valid = True
                    st.session_state.gemini_key_error = ""
                except Exception as exc:
                    st.session_state.gemini_key_valid = False
                    st.session_state.gemini_key_error = str(exc)

    if st.session_state.gemini_key_valid is True:
        st.success("API key is valid.")
    elif st.session_state.gemini_key_valid is False:
        st.error("Validation failed.")
        if st.session_state.get("gemini_key_error"):
            st.caption(st.session_state.gemini_key_error)
    elif st.session_state.gemini_api_key:
        st.info("Key entered — click Validate Key to confirm.")
    else:
        st.warning("No API key set. The Q&A features will be disabled.")

# ---------------------------------------------------------------------------
# Section 6: Pet Documents
# ---------------------------------------------------------------------------

st.subheader("Pet Documents")

if not st.session_state.pets:
    st.info("Add a pet above before uploading documents.")
else:
    pet_names_for_docs = [p.name for p in st.session_state.pets]
    doc_pet = st.selectbox("Pet", pet_names_for_docs, key="doc_pet_select")

    existing_sources = rag.list_sources(doc_pet)
    if existing_sources:
        st.caption("Already ingested: " + ", ".join(existing_sources))

    uploaded_file = st.file_uploader(
        "Upload a document (PDF, DOCX, TXT, or MD)",
        type=["pdf", "docx", "txt", "md"],
        key="doc_uploader",
    )

    if st.button("Ingest Document", disabled=uploaded_file is None):
        if not st.session_state.gemini_api_key:
            st.error("Enter your Gemini API key in the sidebar first.")
        else:
            with st.spinner(f"Embedding {uploaded_file.name}…"):
                try:
                    n = rag.ingest(doc_pet, uploaded_file.getvalue(), uploaded_file.name)
                    st.success(f"Stored {n} chunks from **{uploaded_file.name}** for {doc_pet}.")
                except Exception as exc:
                    st.error(f"Ingestion failed: {exc}")

st.divider()

# ---------------------------------------------------------------------------
# Section 7: Ask About a Pet
# ---------------------------------------------------------------------------

st.subheader("Ask About a Pet")

if not st.session_state.pets:
    st.info("Add a pet above to use the Q&A feature.")
else:
    qa_pet = st.selectbox("Pet", [p.name for p in st.session_state.pets], key="qa_pet_select")
    question = st.text_input("Question", placeholder="When was the last rabies vaccination?")
    use_general = st.checkbox(
        "Supplement with Gemini's general knowledge if documents don't cover the answer",
        value=False,
    )

    if st.button("Ask", disabled=not question.strip()):
        if not st.session_state.gemini_api_key:
            st.error("Enter your Gemini API key in the sidebar first.")
        else:
            with st.spinner("Searching documents and generating answer…"):
                try:
                    answer, sources = rag.query(qa_pet, question, general_knowledge=use_general)
                    st.markdown(answer)
                    if sources:
                        st.caption("Sources: " + ", ".join(sources))
                except Exception as exc:
                    st.error(f"Query failed: {exc}")
