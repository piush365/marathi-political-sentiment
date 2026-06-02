from __future__ import annotations

import os
import csv
import random
from collections import Counter
from flask import Flask, jsonify, request, render_template_string

app = Flask(__name__)

PROCESSED_PATH = "data/processed/comments_clean.csv"
LABELED_PATH   = "data/labeled/comments_labeled.csv"
SKIPPED_PATH   = "data/labeled/comments_skipped.csv"
TARGET         = 200   # single source of truth — used in backend AND passed to frontend

LABELS = {"0": "negative", "1": "positive", "2": "neutral"}

# ── in-memory state ───────────────────────────────────────────────────────────
# loaded once at startup, updated incrementally — no per-request file reads

def _load_comments() -> list[dict]:
    with open(PROCESSED_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    random.seed(42)
    random.shuffle(rows)
    return rows

def _load_labeled() -> dict[str, str]:
    """Returns {comment_id: label}"""
    if not os.path.isfile(LABELED_PATH):
        return {}
    with open(LABELED_PATH, encoding="utf-8") as f:
        return {r["comment_id"]: r["label"] for r in csv.DictReader(f)}

def _load_skipped() -> set[str]:
    if not os.path.isfile(SKIPPED_PATH):
        return set()
    with open(SKIPPED_PATH, encoding="utf-8") as f:
        return {r["comment_id"] for r in csv.DictReader(f)}

# module-level state — mutated by label/undo routes
ALL_COMMENTS: list[dict] = _load_comments()
LABELED_MAP:  dict[str, str] = _load_labeled()
SKIPPED_IDS:  set[str]       = _load_skipped()


# ── file helpers ──────────────────────────────────────────────────────────────

def _append_row(row: dict, label: str, filepath: str):
    """Append one row to CSV. Writes header only if file is new."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file_exists = os.path.isfile(filepath)
    fieldnames  = ["comment_id", "video_id", "text", "likes", "label"]
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "comment_id": row["comment_id"],
            "video_id":   row["video_id"],
            "text":       row["text"],
            "likes":      row["likes"],
            "label":      label,
        })

def _delete_last_row(filepath: str) -> dict | None:
    """Remove last row from CSV, return it. Returns None if file empty/missing."""
    if not os.path.isfile(filepath):
        return None
    with open(filepath, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    removed    = rows[-1]
    fieldnames = list(rows[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows[:-1])
    return removed


# ── queue helper ──────────────────────────────────────────────────────────────

def _get_queue() -> list[dict]:
    """Comments not yet labeled or skipped, in shuffled order."""
    done = set(LABELED_MAP.keys()) | SKIPPED_IDS
    return [c for c in ALL_COMMENTS if c["comment_id"] not in done]

def _get_dist() -> dict:
    return dict(Counter(LABELED_MAP.values()))


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML, target=TARGET)

@app.route("/api/status")
def status():
    """Returns current progress — called on page load."""
    labeled = len(LABELED_MAP)
    return jsonify({
        "target":        TARGET,
        "total_labeled": labeled,
        "dist":          _get_dist(),
        "done":          labeled >= TARGET,
    })

@app.route("/api/next")
def next_comment():
    labeled = len(LABELED_MAP)
    if labeled >= TARGET:
        return jsonify({"done": True, "total_labeled": labeled, "dist": _get_dist()})

    queue = _get_queue()
    if not queue:
        return jsonify({"done": True, "total_labeled": labeled, "dist": _get_dist()})

    comment = queue[0]
    return jsonify({
        "done":          False,
        "comment_id":    comment["comment_id"],
        "video_id":      comment["video_id"],
        "text":          comment["text"],
        "likes":         comment["likes"],
        "total_labeled": labeled,
        "target":        TARGET,
        "remaining":     len(queue),
        "dist":          _get_dist(),
    })

@app.route("/api/label", methods=["POST"])
def label():
    global LABELED_MAP, SKIPPED_IDS
    data       = request.get_json(silent=True)
    if not data:
        return jsonify({"ok": False, "error": "invalid JSON"}), 400

    action     = data.get("action", "")
    comment_id = data.get("comment_id", "")

    # ── undo ──────────────────────────────────────────────────────────────────
    if action == "undo":
        removed = _delete_last_row(LABELED_PATH)
        if removed:
            LABELED_MAP.pop(removed["comment_id"], None)
            return jsonify({"ok": True, "removed_id": removed["comment_id"]})
        return jsonify({"ok": False, "error": "nothing to undo"})

    # ── find comment ──────────────────────────────────────────────────────────
    row = next((c for c in ALL_COMMENTS if c["comment_id"] == comment_id), None)
    if not row:
        return jsonify({"ok": False, "error": "comment not found"}), 404

    # ── skip ──────────────────────────────────────────────────────────────────
    if action == "skip":
        _append_row(row, "skip", SKIPPED_PATH)
        SKIPPED_IDS.add(comment_id)
        return jsonify({"ok": True})

    # ── label ─────────────────────────────────────────────────────────────────
    if action in LABELS:
        label_name = LABELS[action]
        _append_row(row, label_name, LABELED_PATH)
        LABELED_MAP[comment_id] = label_name
        return jsonify({"ok": True, "total_labeled": len(LABELED_MAP)})

    return jsonify({"ok": False, "error": f"unknown action: {action}"}), 400


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="mr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Marathi Sentiment Labeler</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Inter', sans-serif;
    background: #0f1117;
    color: #e2e8f0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 24px 16px;
  }

  .container { width: 100%; max-width: 720px; }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }
  .header h1 {
    font-size: 14px;
    font-weight: 600;
    color: #64748b;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  #counter { font-size: 13px; color: #64748b; }

  .progress-bar-wrap {
    background: #1e2330;
    border-radius: 99px;
    height: 6px;
    margin-bottom: 16px;
  }
  .progress-bar-fill {
    height: 6px;
    border-radius: 99px;
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    transition: width 0.4s ease;
    width: 0%;
  }

  .stats {
    display: flex;
    gap: 10px;
    margin-bottom: 24px;
    flex-wrap: wrap;
  }
  .stat {
    background: #1e2330;
    border-radius: 8px;
    padding: 7px 13px;
    font-size: 12px;
    font-weight: 500;
  }
  .stat span { font-weight: 700; font-size: 14px; }
  .pos { color: #4ade80; }
  .neg { color: #f87171; }
  .neu { color: #fbbf24; }
  .tot { color: #a78bfa; }

  .card {
    background: #1a1f2e;
    border: 1px solid #2d3748;
    border-radius: 14px;
    padding: 28px 32px;
    margin-bottom: 24px;
    min-height: 160px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    transition: border-color 0.2s;
  }
  .card.loading { border-color: #4a5568; opacity: 0.6; }

  .card-meta {
    font-size: 11px;
    color: #4a5568;
    margin-bottom: 16px;
    display: flex;
    gap: 16px;
  }

  .comment-text {
    font-family: 'Noto Sans Devanagari', 'Mangal', 'Arial Unicode MS', sans-serif;
    font-size: 22px;
    line-height: 1.8;
    color: #f1f5f9;
    font-weight: 400;
    word-break: break-word;
  }

  .buttons {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
  }
  .btn {
    padding: 16px 12px;
    border-radius: 10px;
    border: 2px solid transparent;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  .btn:hover:not(:disabled) { transform: translateY(-2px); filter: brightness(1.2); }
  .btn:active:not(:disabled) { transform: translateY(0); }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

  .btn small { display: block; font-weight: 400; font-size: 11px; margin-top: 3px; opacity: 0.75; }
  .btn-neg { background: #2d1515; color: #f87171; border-color: #7f1d1d; }
  .btn-pos { background: #142d1a; color: #4ade80; border-color: #14532d; }
  .btn-neu { background: #2d2514; color: #fbbf24; border-color: #78350f; }

  .secondary-buttons {
    display: flex;
    gap: 10px;
    justify-content: center;
    margin-bottom: 16px;
  }
  .btn-sm {
    padding: 8px 18px;
    border-radius: 8px;
    border: 1px solid #2d3748;
    background: #1e2330;
    color: #94a3b8;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
  }
  .btn-sm:hover:not(:disabled) { background: #2d3748; color: #e2e8f0; }
  .btn-sm:disabled { opacity: 0.4; cursor: not-allowed; }

  .hint {
    text-align: center;
    font-size: 11px;
    color: #374151;
    margin-top: 4px;
  }

  .done {
    text-align: center;
    padding: 60px 20px;
    display: none;
  }
  .done h2 { font-size: 28px; margin-bottom: 12px; color: #a78bfa; }
  .done p  { color: #94a3b8; font-size: 15px; line-height: 1.7; }

  .error-msg {
    background: #2d1515;
    color: #f87171;
    border: 1px solid #7f1d1d;
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 13px;
    margin-bottom: 16px;
    display: none;
  }

  .toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(80px);
    background: #1e2330;
    border: 1px solid #374151;
    color: #e2e8f0;
    padding: 10px 20px;
    border-radius: 8px;
    font-size: 13px;
    transition: transform 0.25s ease;
    pointer-events: none;
    z-index: 100;
  }
  .toast.show { transform: translateX(-50%) translateY(0); }
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>Marathi Sentiment Labeler</h1>
    <div id="counter">loading...</div>
  </div>

  <div class="progress-bar-wrap">
    <div class="progress-bar-fill" id="progress"></div>
  </div>

  <div class="stats">
    <div class="stat tot">Total: <span id="s-total">0</span> / {{ target }}</div>
    <div class="stat pos">👍 Positive: <span id="s-pos">0</span></div>
    <div class="stat neg">👎 Negative: <span id="s-neg">0</span></div>
    <div class="stat neu">😐 Neutral: <span id="s-neu">0</span></div>
  </div>

  <div id="error-msg" class="error-msg"></div>

  <div id="labeler">
    <div class="card" id="comment-card">
      <div class="card-meta">
        <span id="meta-video">—</span>
        <span id="meta-likes">—</span>
      </div>
      <div class="comment-text" id="comment-text">Loading...</div>
    </div>

    <div class="buttons">
      <button class="btn btn-neg" id="btn-0" onclick="submitLabel('0')">
        👎 Negative<small>criticism / anger</small>
      </button>
      <button class="btn btn-pos" id="btn-1" onclick="submitLabel('1')">
        👍 Positive<small>support / praise</small>
      </button>
      <button class="btn btn-neu" id="btn-2" onclick="submitLabel('2')">
        😐 Neutral<small>factual / mixed</small>
      </button>
    </div>

    <div class="secondary-buttons">
      <button class="btn-sm" id="btn-skip" onclick="submitLabel('skip')">Skip</button>
      <button class="btn-sm" id="btn-undo" onclick="undoLast()">↩ Undo</button>
    </div>

    <div class="hint">
      Keyboard: <b>0</b> negative &nbsp;·&nbsp;
      <b>1</b> positive &nbsp;·&nbsp;
      <b>2</b> neutral &nbsp;·&nbsp;
      <b>s</b> skip &nbsp;·&nbsp;
      <b>u</b> undo
    </div>
  </div>

  <div id="done-screen" class="done">
    <h2>🎉 All done!</h2>
    <p>{{ target }} comments labeled.<br>You can close this tab and commit your data.</p>
    <div id="final-dist" style="margin-top:24px;font-size:15px;line-height:2.2;color:#94a3b8;"></div>
  </div>

</div>

<div class="toast" id="toast"></div>

<script>
const TARGET = {{ target }};
let currentComment = null;
let busy = false;  // prevents double-clicks / simultaneous requests

// ── UI helpers ────────────────────────────────────────────────────────────────

function setButtons(disabled) {
  ['btn-0','btn-1','btn-2','btn-skip','btn-undo'].forEach(id => {
    document.getElementById(id).disabled = disabled;
  });
}

function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 4000);
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 1400);
}

function updateStats(data) {
  const dist  = data.dist || {};
  const total = data.total_labeled || 0;
  document.getElementById('s-total').textContent = total;
  document.getElementById('s-pos').textContent   = dist.positive || 0;
  document.getElementById('s-neg').textContent   = dist.negative || 0;
  document.getElementById('s-neu').textContent   = dist.neutral  || 0;
  document.getElementById('counter').textContent = `${total} / ${TARGET}`;
  document.getElementById('progress').style.width = `${Math.min(100,(total/TARGET)*100)}%`;
}

function showDone(data) {
  document.getElementById('labeler').style.display      = 'none';
  document.getElementById('done-screen').style.display  = 'block';
  const dist = data.dist || {};
  document.getElementById('final-dist').innerHTML =
    `👍 Positive: <b>${dist.positive||0}</b> &nbsp;·&nbsp;
     👎 Negative: <b>${dist.negative||0}</b> &nbsp;·&nbsp;
     😐 Neutral: <b>${dist.neutral||0}</b>`;
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function loadNext() {
  document.getElementById('comment-card').classList.add('loading');
  setButtons(true);

  try {
    const res  = await fetch('/api/next');
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();

    updateStats(data);

    if (data.done) {
      showDone(data);
      return;
    }

    currentComment = data;
    document.getElementById('comment-text').textContent  = data.text;
    document.getElementById('meta-video').textContent    = `video: ${data.video_id}`;
    document.getElementById('meta-likes').textContent    = `❤️ ${data.likes} likes`;
    document.getElementById('comment-card').classList.remove('loading');
    setButtons(false);

  } catch (err) {
    showError(`Failed to load next comment: ${err.message}`);
    setButtons(false);
  }
}

async function submitLabel(action) {
  if (busy) return;
  if (!currentComment && action !== 'undo') return;

  busy = true;
  setButtons(true);

  try {
    const res = await fetch('/api/label', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        comment_id: currentComment?.comment_id,
        action
      })
    });

    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();

    if (!data.ok) {
      showError(data.error || 'Something went wrong');
      setButtons(false);
      busy = false;
      return;
    }

    if (action === 'skip') showToast('Skipped ⏭');
    await loadNext();

  } catch (err) {
    showError(`Request failed: ${err.message}`);
    setButtons(false);
  }

  busy = false;
}

async function undoLast() {
  if (busy) return;
  busy = true;
  setButtons(true);

  try {
    const res  = await fetch('/api/label', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ action: 'undo' })
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();

    if (data.ok) {
      showToast('↩ Undone');
      await loadNext();
    } else {
      showError(data.error || 'Nothing to undo');
      setButtons(false);
    }
  } catch (err) {
    showError(`Undo failed: ${err.message}`);
    setButtons(false);
  }

  busy = false;
}

// ── keyboard shortcuts ────────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (busy) return;
  if (e.target.tagName === 'INPUT') return;
  const map = { '0': '0', '1': '1', '2': '2', 's': 'skip', 'u': 'undo' };
  if (map[e.key]) {
    e.preventDefault();
    if (e.key === 'u') undoLast();
    else submitLabel(map[e.key]);
  }
});

// ── init ──────────────────────────────────────────────────────────────────────
loadNext();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    os.makedirs("data/labeled", exist_ok=True)
    print("\n── Marathi Sentiment Labeler ─────────────────────────")
    print(f"  Target         : {TARGET} comments")
    print(f"  Labeled so far : {len(LABELED_MAP)}")
    print(f"  Open browser → http://localhost:5000")
    print(f"  Ctrl+C to stop")
    print("──────────────────────────────────────────────────────\n")
    app.run(debug=False, port=5000)