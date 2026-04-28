# Model Card: PawPal Chat

## 1. Model Name

**PawPal Chat** — a pet-care assistant that combines a rule-based daily scheduler with a Gemini-powered document Q&A system.

---

## 2. Intended Use

PawPal Chat is designed for busy pet owners who want help staying consistent with pet care routines and quick access to their pet's records without digging through files.

- **Scheduling** — the system generates a priority-ordered daily care plan based on the owner's pets, tasks, and time preferences. It assumes the owner knows their constraints (when they're available, how long each task takes, how often it needs to happen) and wants a conflict-free, reasoned plan rather than just a to-do list.
- **Document Q&A** — the system answers questions about a specific pet using documents the owner has uploaded (vet records, care guides, vaccination history). It assumes those documents are the source of truth and stays grounded in them by default.

This project was built for a university course exploring applied AI engineering, so it is intended for educational exploration as much as real use. That said, the scheduling logic and RAG pipeline are fully functional.

---

## 3. How the Model Works

There are two distinct AI components working together.

**The scheduler** is rule-based, not learned. It takes all the tasks an owner has entered and sorts them from most to least important. Then it works through the day from the owner's earliest available time, placing each task into the first open slot that fits — like a human working through a to-do list in order of priority. It automatically spreads tasks that repeat throughout the day (like feeding twice daily) so they aren't all stacked at the start. If two tasks end up overlapping, it flags that conflict and tells the owner exactly which tasks are colliding and why.

**The Q&A system** uses a technique called Retrieval-Augmented Generation (RAG). When a document is uploaded, the system breaks it into smaller overlapping passages and converts each one into a numerical fingerprint (called an embedding) using Google's Gemini embedding model. Those fingerprints are stored in a local database for that pet. When the owner asks a question, the question gets the same treatment — converted to a fingerprint — and the system finds the passages whose fingerprints are closest to the question's. Those passages are handed to Gemini, which reads them and writes a natural-language answer. The answer is grounded in the document; the model doesn't invent details that aren't there.

The owner can optionally allow Gemini to supplement with general knowledge if the documents don't cover the question, but this is turned off by default and flagged explicitly when used.

---

## 4. Data

The system does not use a fixed song catalog or pre-built dataset. Instead, each pet owner builds their own private data store by uploading files.

- **Supported formats** — PDF, DOCX, TXT, and Markdown files (vet records, care guides, wellness visit summaries, breed information sheets).
- **Storage** — each pet gets its own isolated ChromaDB vector collection stored locally on disk. Documents are chunked into 400-word passages with a 40-word overlap before embedding.
- **Coverage gaps** — the system only knows what the owner has uploaded. If a vaccination was given but the record was never uploaded, the system will say it has no information rather than guess. There is no shared catalog of breed-specific care defaults, so general questions (like calorie targets) require either an uploaded document or the general-knowledge toggle enabled.
- **No training data** — the Gemini embedding and generation models were not fine-tuned for this project. They are used as-is via the Gemini API.

---

## 5. Strengths

**Scheduling:**
- Works well for owners with a clear set of daily tasks and predictable availability. Priority ordering means medication and feeding reliably land before lower-stakes tasks like enrichment toys.
- Conflict detection catches overlapping tasks automatically and reports them in plain English, which is more useful than a raw error.
- The reasoning log gives a full step-by-step account of every placement and skip decision, so the schedule is never a black box.

**Q&A:**
- Answers stay grounded in uploaded documents by default, which prevents the model from confidently making things up about a specific pet.
- Source attribution (showing which file the answer came from) makes it easy to verify the answer directly.
- Graceful failure: when no documents are uploaded, the system returns a clear message rather than crashing or producing an empty response.

---

## 6. Limitations and Bias

**Scheduler:**
The greedy first-fit algorithm has no backtracking. A long high-priority task placed early in the morning can silently crowd out several shorter medium or low-priority tasks, even when a different ordering would have fit everything. The reasoning log surfaces this, but it still requires the owner to notice and react. There's also no concept of task dependencies — the scheduler doesn't know that a bath should follow a walk, not precede it.

**Q&A:**
Answer quality is entirely bounded by what gets uploaded. Incomplete records, outdated information, or documents that use abbreviations the embedding model doesn't link well to the question will produce unhelpful or misleading answers. There is no medical validation layer — the system repeats what the document says, even if the document is wrong.

**Misuse potential:**
The most realistic misuse scenario is uploading fabricated or misleading documents to generate authoritative-sounding answers — for example, a false medication history. The current mitigation is source attribution (the owner can always check the original file) and the general-knowledge toggle being off by default. A subtler risk is overreliance: a pet owner following a dosage answer without confirming it with their vet. A visible disclaimer in the Q&A section would help address this; it's currently missing.

**Underrepresentation:**
The system has no concept of species beyond what the owner inputs. There's nothing breed- or species-specific in the scheduling logic — a 5-minute task for a goldfish and a 5-minute task for a Great Dane are treated identically.

---

## 7. Evaluation

**Automated tests** — the test suite covers 26 tests across four areas: task sorting (5), recurrence behavior (8), conflict detection (8), and RAG error handling (3). All 26 pass. The RAG tests specifically check that the pipeline returns safe, descriptive responses instead of raising exceptions when a pet has no uploaded documents — the most common real-world failure case.

**Human evaluation** — I tested three scenarios manually:

1. Schedule generation with morning + evening preferences, four tasks across two priority levels. The schedule matched the expected priority ordering, the conflict check came back clean, and the reasoning log accurately described every placement decision.
2. RAG vaccination lookup against an uploaded vet record. The date, doctor name, and clinic in the answer matched the source document exactly.
3. A calorie question against a document that didn't contain the answer, with general-knowledge supplement enabled. The system correctly identified the gap, supplemented from general knowledge, and flagged that it was doing so.

**What surprised me** — I expected the main failure mode to be hallucination (the model inventing a vaccination date or vet's name). What actually surprised me was how clean the graceful-failure path was. When I tested with no documents uploaded, the system returned a plain "No documents have been uploaded for [pet] yet." without crashing or producing an empty UI state. That behavior held up in both manual testing and the automated suite.

---

## 8. Future Work

**Richer scheduling model** — the current scheduler derives a single contiguous time window from the owner's preferences and subtracts busy periods. A better model would represent free time as a sorted list of start/end intervals from the start, making it easier to place tasks that span a gap (like a lunch-break walk between two busy periods) and eliminating re-derivation of available time inside the greedy loop.

**Vet disclaimer** — a visible disclaimer in the Q&A section making clear that answers come from uploaded documents and are not veterinary advice. This is the most important missing safety feature.

**UI tests** — even a small Playwright or Selenium suite covering the happy path (add owner → add pet → add task → generate schedule → upload doc → ask question) would catch session-state bugs that are currently only found by manual clicking.

**Recommendation diversity** — the scheduler currently produces the same schedule for the same inputs every time. Adding slight randomization within the same priority tier (e.g., shuffling equally-ranked tasks) would reduce monotony for owners whose tasks don't have a strict order.

**Multilingual support** — the embedding model handles multilingual text, but the UI and prompts are English-only. Supporting other languages would open the app to a much wider range of pet owners.

---

## 9. Personal Reflection

Building this project taught me that working with AI is less about getting it to write code and more about communicating intent clearly enough that the suggestions actually fit the system you're designing. The most concrete lesson came from a naming decision: I called my unavailability class `Block`, meaning a block of time when the owner was busy. The AI kept interpreting it as a block of tasks — grouping logic — and every suggestion it made for that class was wrong. When I renamed it to `BusyPeriod`, the model's reasoning immediately aligned with what I intended, and the suggestions became useful. That experience changed how I think about naming in a way that working alone never would have: in an AI-assisted workflow, names are not just for human readers, they actively shape how the model reasons about your design in every prompt that follows.

The most unexpected discovery was how much I learned from testing failure cases rather than success cases. I expected to spend most of my evaluation time checking whether the AI gave correct answers. Instead, the more interesting question turned out to be: what does the system do when it *can't* give a correct answer? Watching the RAG pipeline return a calm, clear message instead of hallucinating or crashing when no documents were uploaded gave me more confidence in the system than any successful answer did. That's shaped how I'd approach evaluating any AI system going forward — the failure path is where reliability actually lives.

---

## 10. Reliability and Evaluation

### Automated tests

The test suite (`tests/test_pawpal.py`) covers **26 tests** across four areas:

| Area | Tests | What's verified |
|---|---|---|
| Sorting | 5 | Chronological ordering, untimed tasks sort last, stable sort for equal times |
| Recurrence | 8 | Daily/weekly next-due dates, spawned task attributes, non-recurring returns `None` |
| Conflict detection | 8 | Overlap flagged, back-to-back not flagged, cross-pet conflicts, conflicts stored on `Schedule` |
| RAG reliability | 3 | Graceful error handling when no documents are ingested (no API key required) |

**26 of 26 tests pass.** The RAG tests specifically verify that `rag.query` and `rag.list_sources` return safe, descriptive responses instead of raising exceptions when a pet has no uploaded documents — the most common real-world failure mode.

```bash
$ python -m pytest tests/test_pawpal.py -v
======================== 26 passed, 1 warning in 0.45s =========================
```

### Human evaluation

AI-generated outputs were manually reviewed against their source material in three ways:

**Schedule reasoning** — after each `generate_schedule()` call, the collapsible reasoning log was checked to confirm that every placement and skip decision matched the actual schedule table. All three sample interactions produced reasoning consistent with the output.

**RAG answer accuracy** — each Q&A answer was compared against the uploaded source document. In the vaccination lookup example, the date, doctor name, and clinic matched the vet record exactly. The calorie Q&A correctly identified that the document didn't contain the answer before supplementing with general knowledge, and flagged the supplement explicitly.

**Failure case** — when a question was asked with no documents uploaded, the system returned `"No documents have been uploaded for [pet] yet."` rather than hallucinating an answer. This is the intended safe-failure behavior and was verified both manually and by the automated RAG tests above.

**Summary:** 26 of 26 automated tests pass. Manual review of 3 sample interactions found all AI outputs accurate and source-attributed. The one known limitation — no automated coverage of the Streamlit UI layer — is mitigated by manual click-through testing of the full happy path.
