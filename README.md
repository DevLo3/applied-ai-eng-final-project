# PawPal Chat

**Demo:** [Watch on Loom](https://www.loom.com/share/99901bf63d8d4a0796c7b012eae1ad96)

A Streamlit app that combines rule-based pet-care scheduling with Gemini-powered document Q&A, so pet owners can plan their day *and* ask questions grounded in their pet's actual records.

---

## Origin: PawPal+

PawPal Chat builds directly on **PawPal+**, the original Module 2 project. PawPal+ let a busy pet owner enter their pets and daily care tasks, then automatically generated a priority-sorted, conflict-checked daily schedule with plain-English reasoning. It handled recurring tasks (daily / weekly), enforced minimum intervals between repeated tasks, and grouped tasks by pet to keep the owner's attention focused. PawPal Chat extends that foundation by adding a full RAG (Retrieval-Augmented Generation) pipeline powered by the Gemini API, so owners can upload vet records or care documents and ask natural-language questions answered directly from those files.

---

## Title and Summary

**PawPal Chat** helps pet owners stay on top of care without juggling spreadsheets or memory. It does two things:

1. **Scheduling** — enter your pets, tasks, and time preferences; the app produces a priority-ordered daily plan with conflict warnings and a collapsible reasoning log.
2. **Document Q&A** — upload a PDF, DOCX, TXT, or MD file (vaccination records, care guides, vet notes) and ask questions in plain English; Gemini retrieves the most relevant passages and generates a grounded answer with source attribution.

Together these features turn a generic to-do list into a context-aware pet-care assistant that knows your specific animal's history.

---

## Architecture Overview

```
assets/system_diagram.md
```

The system has three main data flows:

**Scheduling flow** — The Streamlit UI collects owner, pet, and task data. The `Scheduler` (in `pawpal_system.py`) sorts tasks by priority (high → medium → low), groups them by pet, spaces recurring tasks evenly across the available window, subtracts busy periods, and runs a conflict check. The resulting `Schedule` object is rendered in the UI as a sortable table, per-pet tabs, and a reasoning expander.

**Document ingestion flow** — An uploaded file is parsed into raw text (PDF via pypdf, DOCX via python-docx, or plain text), split into 400-word overlapping chunks, embedded via `gemini-embedding-001`, and stored in a per-pet ChromaDB collection on disk.

**Q&A flow** — The user's question is embedded with the same model, a top-k similarity search retrieves the most relevant chunks from ChromaDB, those chunks are assembled into a grounded prompt, and `gemini-2.5-flash` generates a natural-language answer. Sources (filenames) are shown below the answer.

Human judgment is involved at two points: reviewing the generated schedule for conflicts and verifying AI-generated answers against the source documents. The automated test suite (`tests/test_pawpal.py`) validates the scheduler, conflict detection, recurrence, and task sorting independently of the UI.

---

## Setup Instructions

### Prerequisites

- Python 3.9+
- A free Gemini API key from [aistudio.google.com](https://aistudio.google.com)

### Install

```bash
git clone <repo-url>
cd applied-ai-eng-final-project

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### Run

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. Enter your Gemini API key in the sidebar to enable document ingestion and Q&A.

### Run tests

```bash
python -m pytest tests/test_pawpal.py -v
```

---

## Sample Interactions

### 1 — Schedule generation

**Input:**
- Owner: Jordan, morning + evening preferences
- Pet: Mochi (Shiba Inu, 3 yrs, 20.5 lbs)
- Tasks: Morning walk (20 min, high, daily ×1), Feeding (10 min, high, daily ×2), Enrichment toy (15 min, medium, daily ×1), Grooming brush (10 min, low, weekly)

**AI output (schedule table, excerpt):**
```
07:00 AM  Feeding        Mochi   10 min  ×2  high
07:10 AM  Morning walk   Mochi   20 min  ×1  high
07:30 AM  Enrichment toy Mochi   15 min  ×1  medium
06:00 PM  Feeding        Mochi   10 min  ×2  high
06:10 PM  Grooming brush Mochi   10 min  ×1  low   (weekly)

✅ No conflicts detected across 5 scheduled tasks.
```

**Reasoning log excerpt:**
> Placed "Feeding" at 07:00 AM (high priority, first available morning slot).
> Placed "Morning walk" at 07:10 AM immediately after feeding.
> Placed "Grooming brush" at 06:10 PM (low priority, last remaining slot).

---

### 2 — RAG Q&A: vaccination lookup

**Uploaded document:** `mochi_vet_records.pdf` (annual wellness visit notes)

**User question:** "When was Mochi's last rabies vaccination?"

**AI answer:**
> According to the uploaded records, Mochi received a 3-year rabies vaccination on **March 14, 2023**, administered by Dr. Chen at Eastside Animal Clinic. The next booster is due by March 2026.
>
> *Sources: mochi_vet_records.pdf*

---

### 3 — RAG Q&A: diet guidance with general-knowledge supplement

**Uploaded document:** `shiba_care_guide.md` (breed care tips)

**User question:** "How many calories should a 20-pound Shiba Inu eat per day?"

**AI answer (general-knowledge supplement enabled):**
> The uploaded care guide does not specify a calorie target. Based on general veterinary guidelines, a moderately active 20-pound adult dog typically needs approximately **520–620 kcal/day**. For Mochi specifically, I'd recommend confirming this with your vet since individual metabolism, activity level, and health conditions can shift the range.
>
> *Sources: shiba_care_guide.md (general knowledge supplemented)*

---

## Design Decisions

**Greedy first-fit scheduler** — Tasks are placed into the earliest available slot in priority order without backtracking. This is fast, deterministic, and produces reasoning text that maps directly to the decisions made — a pet owner can read "Grooming was skipped because no 10-minute slot remained after high-priority tasks" and understand exactly what happened. A globally optimal solver would be harder to explain and unjustified for a typical household with fewer than 20 tasks.

**Separate `Scheduler` and `Schedule` classes** — Scheduling logic lives in `Scheduler`; the result lives in `Schedule`. This keeps the data object simple and testable independently of the algorithm, and makes it easy to swap in a different strategy later.

**RAG over fine-tuning** — Pet records are personal and change frequently (new vaccines, weight checks, medication changes). Embedding and retrieving documents at query time means the app always answers from the latest uploaded file without any model retraining.

**Per-pet ChromaDB collections** — Isolating each pet's documents into its own ChromaDB collection prevents cross-contamination (Mochi's vaccination history can't bleed into Kona's query results) and makes it trivial to delete or update one pet's data independently.

**REST embedding calls instead of the SDK** — The `google-genai` SDK ≥1.x routes `embed_content` to `batchEmbedContents`, which is not supported by `gemini-embedding-001`. Calling the REST endpoint directly avoids that routing issue without pinning to an older SDK version.

---

## Testing Summary

### What worked

The automated suite (`tests/test_pawpal.py`) covers 23 tests across three areas:

- **Sorting** — tasks sort chronologically by `scheduled_time`; tasks without a time always sort last.
- **Recurrence** — `mark_complete()` on a `daily` task returns a new task due tomorrow; `weekly` returns one due in 7 days; the spawned task is incomplete with no scheduled time; non-recurring tasks return `None`.
- **Conflict detection** — overlapping intervals are flagged with task and pet names; back-to-back tasks (touching but not overlapping) are not flagged; tasks without a `scheduled_time` are safely skipped.

All 23 tests pass consistently.

### What didn't have coverage

The Streamlit UI layer (`app.py`) has no automated tests. Session-state transitions, form resubmission, `st.rerun()` triggers, and the API-key validation flow were verified only by manually clicking through the app. This is the biggest gap — a UI bug here (e.g., a task added twice after a rerun) would not be caught until a human noticed it.

The RAG pipeline also has no automated tests. Embedding quality, retrieval relevance, and Gemini answer correctness can't easily be unit-tested without hitting the live API, so they were validated manually by uploading real documents and checking whether the answers matched the source text.

### What I learned

Testing the scheduler in isolation — before wiring it to the UI — caught several off-by-one errors in the interval overlap check and an edge case where a task with `daily_frequency=2` and a tight `min_interval` was being placed twice in the same slot. Finding those bugs via pytest (with instant feedback) was far faster than finding them by clicking through the app.

---

## Reflection

**On AI as a collaborator** — The most important thing I learned is that naming is load-bearing when working with AI. Renaming the `Block` class to `BusyPeriod` changed how the model reasoned about it in every subsequent prompt: it stopped suggesting the class manage collections of tasks and started suggesting it carve out unavailable time windows — exactly what I needed. Front-loading *intent* in prompts ("add logic so that marking a recurring task complete automatically creates the next occurrence") consistently produced better designs than describing *what to write* ("add a `next_due` field").

**On human-in-the-loop design** — The Q&A feature was built with deliberate friction: the user must explicitly enable general-knowledge supplementation, and sources are always shown. That design choice came from recognizing that a confident wrong answer about a pet's medication or diet is worse than no answer. Keeping the human in the loop — reading the source, deciding whether to trust the answer — is the right default for health-adjacent information.

**On problem-solving** — Building incrementally (UML → class stubs → logic → tests → UI → RAG) and verifying at each layer kept the project manageable. The times I skipped verification and moved straight to the next layer were the times I introduced bugs that took much longer to track down than if I had caught them immediately.

