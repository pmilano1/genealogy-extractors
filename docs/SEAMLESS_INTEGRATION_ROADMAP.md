# Seamless Integration - Making Research Effortless

## Vision: One-Click Research Workflow

**Constraint**: CDP automation uses your Chrome logins → must run on your local machine (not remote server)

**Current**: Open terminal → run Python script → wait → check logs → copy URLs → paste into browser
**Seamless**: Click "Start Research" in local app → runs in background → get notification when done → review in web UI

---

## Architecture: Local Agent + Remote API

```
┌─────────────────────────────────────────────────────────────┐
│ Your Local Machine (Mac mini / laptop)                      │
│                                                              │
│  ┌──────────────────┐         ┌─────────────────────┐      │
│  │  Chrome Browser  │◄────────│  Research Agent     │      │
│  │  (with logins)   │         │  (Python + CDP)     │      │
│  └──────────────────┘         └─────────────────────┘      │
│                                         │                    │
│                                         │ GraphQL API        │
└─────────────────────────────────────────┼──────────────────┘
                                          │
                                          ▼
                        ┌─────────────────────────────────┐
                        │  Remote Server                  │
                        │  (family.milanese.life)         │
                        │                                 │
                        │  - GraphQL API                  │
                        │  - Database                     │
                        │  - Web UI                       │
                        └─────────────────────────────────┘
```

**Key Insight**: Research agent runs locally, but integrates with remote API for task management and results storage.

---

## Top 10 Seamless Improvements

### 1. **Local Desktop App (One-Click Start)**
**Current**: Run Python script manually from terminal
**Improved**: Desktop app with "Start Research" button that runs locally

**Implementation**:
```python
# Create local desktop app (Electron or Tauri)
# research-agent-app/main.py

import asyncio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn
import webbrowser

app = FastAPI()

# Serve simple web UI
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    """Serve local web UI"""
    return FileResponse("static/index.html")

@app.post("/api/local/research/start")
async def start_local_research(max_people: int = 100):
    """Start research job locally"""
    job_id = str(uuid.uuid4())

    # Run research in background thread (not blocking)
    asyncio.create_task(run_research_job_local(job_id, max_people))

    return {"job_id": job_id, "status": "STARTED"}

async def run_research_job_local(job_id, max_people):
    """Run research using local Chrome with CDP"""
    # Fetch tasks from remote API
    tasks = await fetch_researchable_tasks(max_people)

    # Run CDP orchestrator locally
    orchestrator = CDPOrchestrator(
        chrome_port=9222,  # Local Chrome debug port
        job_id=job_id
    )

    await orchestrator.research_all(tasks)

# Start local server
if __name__ == "__main__":
    # Open browser to local UI
    webbrowser.open("http://localhost:8765")

    # Run local server
    uvicorn.run(app, host="127.0.0.1", port=8765)
```

```html
<!-- static/index.html - Simple local UI -->
<!DOCTYPE html>
<html>
<head>
    <title>Genealogy Research Agent</title>
</head>
<body>
    <h1>Genealogy Research Agent</h1>
    <p>Status: <span id="status">Ready</span></p>

    <label>Max People: <input type="number" id="maxPeople" value="100" /></label>
    <button onclick="startResearch()">Start Research</button>

    <div id="progress" style="display:none">
        <h2>Progress</h2>
        <p>Person: <span id="currentPerson">-</span></p>
        <p>Progress: <span id="progressText">0/0</span></p>
        <p>Matches Found: <span id="matchesFound">0</span></p>
    </div>

    <script>
        async function startResearch() {
            const maxPeople = document.getElementById('maxPeople').value;
            const response = await fetch('/api/local/research/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({max_people: parseInt(maxPeople)})
            });
            const data = await response.json();

            document.getElementById('status').textContent = 'Running...';
            document.getElementById('progress').style.display = 'block';

            // Connect to WebSocket for progress updates
            connectWebSocket(data.job_id);
        }

        function connectWebSocket(jobId) {
            const ws = new WebSocket(`ws://localhost:8765/ws/research/${jobId}`);
            ws.onmessage = (event) => {
                const update = JSON.parse(event.data);
                document.getElementById('currentPerson').textContent = update.person_name;
                document.getElementById('progressText').textContent = `${update.current}/${update.total}`;
                document.getElementById('matchesFound').textContent = update.matches_found;
            };
        }
    </script>
</body>
</html>
```

**Impact**: One-click start from local app, no terminal needed

---

### Alternative: System Tray App

```python
# Even simpler: System tray app (no browser UI)
import pystray
from PIL import Image

def create_tray_app():
    """Create system tray app"""

    def start_research(icon, item):
        """Start research from tray menu"""
        asyncio.run(run_research_job_local(job_id=str(uuid.uuid4()), max_people=100))

    def open_review_queue(icon, item):
        """Open remote review queue in browser"""
        webbrowser.open("https://family.milanese.life/research/review")

    # Create menu
    menu = pystray.Menu(
        pystray.MenuItem("Start Research (100 people)", start_research),
        pystray.MenuItem("Open Review Queue", open_review_queue),
        pystray.MenuItem("Settings", open_settings),
        pystray.MenuItem("Quit", quit_app)
    )

    # Create icon
    icon = pystray.Icon("research-agent", Image.open("icon.png"), "Research Agent", menu)
    icon.run()

if __name__ == "__main__":
    create_tray_app()
```

**Impact**: Always-running background app, right-click tray icon → "Start Research"

---

### 2. **Real-Time Progress Updates (WebSocket)**
**Current**: No visibility into progress until script finishes  
**Improved**: Live updates in UI: "Searching person 47/500... Found 3 matches on Geneanet"

**Implementation**:
```python
# Add WebSocket endpoint
@app.websocket("/ws/research/{job_id}")
async def research_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    
    # Stream progress updates
    async for update in research_job_stream(job_id):
        await websocket.send_json({
            'type': 'PROGRESS',
            'current': update.current_person,
            'total': update.total_people,
            'person_name': update.person_name,
            'matches_found': update.matches_found,
            'eta_seconds': update.eta_seconds
        })

# In cdp_orchestrator.py
class CDPOrchestrator:
    def __init__(self, websocket=None):
        self.websocket = websocket
    
    async def search_person(self, person, ...):
        # Send progress update
        if self.websocket:
            await self.websocket.send_json({
                'type': 'SEARCHING',
                'person': person.name,
                'source': source.name
            })
        
        # Do search...
        
        if found:
            await self.websocket.send_json({
                'type': 'MATCH_FOUND',
                'person': person.name,
                'source': source.name,
                'records': len(records)
            })
```

**Impact**: Know exactly what's happening in real-time, see ETA

---

### 3. **Auto-Resume from Crashes/Interruptions**
**Current**: Script crashes → lose all progress, start over  
**Improved**: Script crashes → restart and resume from last completed person

**Implementation**:
```python
# Add job state persistence
class ResearchJobState:
    def __init__(self, job_id, state_file=".cache/jobs/{job_id}.json"):
        self.job_id = job_id
        self.state_file = Path(state_file)
        self.state = self.load_state()
    
    def load_state(self):
        """Load job state from disk"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {
            'job_id': self.job_id,
            'status': 'PENDING',
            'completed_people': [],
            'current_person_id': None,
            'total_matches': 0
        }
    
    def save_state(self):
        """Save job state to disk"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def mark_person_complete(self, person_id):
        """Mark person as completed"""
        self.state['completed_people'].append(person_id)
        self.save_state()
    
    def get_remaining_people(self, all_people):
        """Get people not yet searched"""
        completed = set(self.state['completed_people'])
        return [p for p in all_people if p.id not in completed]

# In run_research.py
def run_research_job(job_id, ...):
    state = ResearchJobState(job_id)
    
    # Get remaining people (skip completed)
    remaining = state.get_remaining_people(all_people)
    
    print(f"Resuming job {job_id}: {len(remaining)} people remaining")
    
    for person in remaining:
        # Search person...
        state.mark_person_complete(person.id)
```

**Impact**: Never lose progress, resume from any interruption

---

### 4. **Smart Scheduling (Run Automatically on Local Machine)**
**Current**: Manually run script whenever you remember
**Improved**: Local agent runs automatically every night at 2 AM (when your computer is on)

**Implementation**:
```python
# In local research agent app
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class LocalResearchAgent:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.setup_scheduled_jobs()

    def setup_scheduled_jobs(self):
        """Setup automatic research schedule"""
        # Load settings from remote API
        settings = self.fetch_settings()

        if settings['auto_schedule']:
            # Schedule nightly research
            self.scheduler.add_job(
                self.run_nightly_research,
                'cron',
                hour=settings['schedule_hour'],
                minute=0
            )
            print(f"Scheduled nightly research at {settings['schedule_hour']}:00")

    async def run_nightly_research(self):
        """Run research automatically at scheduled time"""
        # Check if Chrome is running with debug port
        if not self.is_chrome_running():
            print("Chrome not running, skipping scheduled research")
            self.send_notification("Scheduled research skipped - Chrome not running")
            return

        # Fetch tasks from remote API
        tasks = await self.fetch_researchable_tasks(limit=100)

        if len(tasks) > 0:
            job_id = str(uuid.uuid4())
            print(f"Starting scheduled research: {len(tasks)} people")
            await self.run_research_job(job_id, tasks)
        else:
            print("No researchable tasks, skipping")

    def is_chrome_running(self):
        """Check if Chrome is running with debug port"""
        try:
            response = requests.get("http://localhost:9222/json/version", timeout=2)
            return response.status_code == 200
        except:
            return False

# Start agent with scheduler
if __name__ == "__main__":
    agent = LocalResearchAgent()
    agent.scheduler.start()

    # Keep running in background
    asyncio.get_event_loop().run_forever()
```

**Alternative: Wake-on-Schedule**
```python
# For Mac: Use launchd to wake computer and run research
# ~/Library/LaunchAgents/com.genealogy.research.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.genealogy.research</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/path/to/research_agent.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>
```

**Impact**: Research happens automatically when your computer is on, no manual intervention

---

### 5. **Email/Push Notifications**
**Current**: Check manually if research is done  
**Improved**: Get email/push notification when research completes or needs attention

**Implementation**:
```python
# Add notification service
class NotificationService:
    async def send_research_complete(self, job_id, stats):
        """Send notification when research job completes"""
        await send_email(
            to="user@example.com",
            subject=f"Research Complete: {stats['matches_found']} matches found",
            body=f"""
            Research job {job_id} completed successfully.
            
            - People searched: {stats['people_searched']}
            - Matches found: {stats['matches_found']}
            - High-confidence matches: {stats['high_confidence']}
            
            Review matches: https://family.milanese.life/research/review
            """
        )
    
    async def send_research_needs_attention(self, job_id, error):
        """Send notification when research job fails"""
        await send_email(
            to="user@example.com",
            subject=f"Research Job Failed: {job_id}",
            body=f"""
            Research job {job_id} encountered an error and needs attention.
            
            Error: {error}
            
            View details: https://family.milanese.life/research/jobs/{job_id}
            """
        )

# In research job
async def run_research_job(job_id, ...):
    try:
        # Run research...
        stats = {...}
        await notifications.send_research_complete(job_id, stats)
    except Exception as e:
        await notifications.send_research_needs_attention(job_id, str(e))
```

**Impact**: Know when research is done without checking manually

---

### 6. **Feedback Loop (Learn from Approvals/Rejections)**
**Current**: Approve/reject matches, but system doesn't learn  
**Improved**: System learns from your decisions and improves future searches

**Implementation**:
```python
# Track approval/rejection patterns
class FeedbackLearner:
    def record_decision(self, person_id, record, decision):
        """Record user's approve/reject decision"""
        await db.execute("""
            INSERT INTO research_feedback (person_id, source, match_score, decision, timestamp)
            VALUES ($1, $2, $3, $4, NOW())
        """, person_id, record['source'], record['match_score'], decision)
    
    def get_confidence_threshold(self, source_name):
        """Learn optimal confidence threshold from past decisions"""
        # Get approval rate by match score
        stats = await db.fetch("""
            SELECT match_score, 
                   COUNT(*) FILTER (WHERE decision = 'APPROVED') as approved,
                   COUNT(*) as total
            FROM research_feedback
            WHERE source = $1
            GROUP BY match_score
        """, source_name)
        
        # Find score where approval rate >= 80%
        for row in sorted(stats, key=lambda x: x['match_score'], reverse=True):
            approval_rate = row['approved'] / row['total']
            if approval_rate >= 0.80:
                return row['match_score']
        
        return 60  # Default threshold

# In record extraction
def extract_records(self, content, source_name, ...):
    # Get learned threshold for this source
    threshold = feedback_learner.get_confidence_threshold(source_name)
    
    # Filter by learned threshold (not hardcoded 60)
    high_quality = [r for r in records if r['match_score'] >= threshold]
```

**Impact**: System gets smarter over time, fewer false positives

---

### 7. **Graceful Error Handling & Auto-Retry**
**Current**: Source is down → entire script fails
**Improved**: Source is down → skip it, retry later, continue with other sources

**Implementation**:
```python
# Add retry logic with exponential backoff
from tenacity import retry, stop_after_attempt, wait_exponential

class CDPOrchestrator:
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    async def search_source_with_retry(self, source, person, ...):
        """Search with automatic retry on failure"""
        try:
            return await self.search_source(source, person, ...)
        except Exception as e:
            print(f"  ⚠️  Error searching {source.name}: {e}")
            raise

    async def search_person_all_sources(self, person, sources):
        """Search all sources, continue even if some fail"""
        results = []

        for source in sources:
            try:
                result = await self.search_source_with_retry(source, person, ...)
                results.append(result)
            except Exception as e:
                # Log failure but continue
                await self.log_source_failure(source.name, person.id, str(e))
                print(f"  ⏭️  Skipping {source.name}, will retry later")
                continue

        return results

    async def retry_failed_searches(self, job_id):
        """Retry searches that failed earlier"""
        failures = await db.fetch("""
            SELECT * FROM search_failures
            WHERE job_id = $1 AND retry_count < 3
        """, job_id)

        for failure in failures:
            # Retry after delay
            await asyncio.sleep(300)  # Wait 5 minutes
            try:
                result = await self.search_source(failure.source, failure.person, ...)
                await db.execute("DELETE FROM search_failures WHERE id = $1", failure.id)
            except:
                await db.execute("""
                    UPDATE search_failures
                    SET retry_count = retry_count + 1
                    WHERE id = $1
                """, failure.id)
```

**Impact**: Resilient to temporary failures, never lose entire job

---

### 8. **Rate Limit Detection & Auto-Backoff**
**Current**: Get blocked by source → script fails
**Improved**: Detect rate limiting → automatically slow down → resume when safe

**Implementation**:
```python
# Add rate limit detector
class RateLimitDetector:
    def __init__(self):
        self.backoff_until = {}  # source -> timestamp

    def is_rate_limited(self, source_name, response):
        """Detect if we're being rate limited"""
        # Check HTTP status
        if response.status == 429:
            return True

        # Check for common rate limit messages
        rate_limit_indicators = [
            'too many requests',
            'rate limit exceeded',
            'please slow down',
            'temporarily blocked'
        ]

        content = response.text.lower()
        return any(indicator in content for indicator in rate_limit_indicators)

    def set_backoff(self, source_name, duration_seconds=3600):
        """Set backoff period for source"""
        self.backoff_until[source_name] = time.time() + duration_seconds
        print(f"  ⏸️  Rate limited on {source_name}, backing off for {duration_seconds/60:.0f} minutes")

    def can_search(self, source_name):
        """Check if we can search this source"""
        if source_name in self.backoff_until:
            if time.time() < self.backoff_until[source_name]:
                return False
            else:
                del self.backoff_until[source_name]
        return True

# In orchestrator
async def search_source(self, source, person, ...):
    # Check if source is in backoff
    if not self.rate_limiter.can_search(source.name):
        print(f"  ⏸️  Skipping {source.name} (rate limited)")
        return None

    # Do search
    response = await page.goto(url)

    # Check for rate limiting
    if self.rate_limiter.is_rate_limited(source.name, response):
        self.rate_limiter.set_backoff(source.name, duration_seconds=3600)
        return None

    # Continue...
```

**Impact**: Never get permanently blocked, automatically recovers

---

### 9. **Configuration UI (No Code Editing)**
**Current**: Edit Python code to change settings
**Improved**: Configure everything in web UI

**Implementation**:
```python
# Add settings API
@app.get("/api/research/settings")
async def get_research_settings():
    """Get current research settings"""
    return await db.fetchrow("SELECT * FROM research_settings WHERE user_id = $1", user_id)

@app.put("/api/research/settings")
async def update_research_settings(settings: ResearchSettings):
    """Update research settings"""
    await db.execute("""
        UPDATE research_settings SET
            enabled_sources = $1,
            min_confidence_score = $2,
            max_people_per_run = $3,
            auto_schedule = $4,
            schedule_time = $5
        WHERE user_id = $6
    """, settings.enabled_sources, settings.min_confidence_score, ...)

# In frontend
<form>
  <h3>Research Settings</h3>

  <label>Enabled Sources:</label>
  <checkbox name="Antenati" checked />
  <checkbox name="Geneanet" checked />
  <checkbox name="WikiTree" checked />
  <checkbox name="FamilySearch" />

  <label>Minimum Confidence Score:</label>
  <slider min="0" max="100" value="60" />

  <label>Max People Per Run:</label>
  <input type="number" value="100" />

  <label>Auto-Schedule:</label>
  <checkbox name="auto_schedule" />
  <input type="time" value="02:00" />

  <button>Save Settings</button>
</form>
```

**Impact**: Non-technical users can configure research

---

### 10. **Batch Review Operations**
**Current**: Approve/reject matches one-by-one
**Improved**: Select multiple matches → approve/reject all at once

**Implementation**:
```python
# Add batch operations API
@app.post("/api/research/batch-approve")
async def batch_approve(record_ids: List[str]):
    """Approve multiple records at once"""
    for record_id in record_ids:
        # Get record
        record = await db.fetchrow("SELECT * FROM research_results WHERE id = $1", record_id)

        # Submit to family tree
        await submit_research(
            person_id=record.person_id,
            parent_data=extract_parent_data(record),
            source_url=record.url
        )

        # Mark as approved
        await db.execute("UPDATE research_results SET status = 'APPROVED' WHERE id = $1", record_id)

    return {"approved": len(record_ids)}

# In frontend
<table>
  <thead>
    <tr>
      <th><input type="checkbox" id="select-all" /></th>
      <th>Person</th>
      <th>Source</th>
      <th>Match Score</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    {matches.map(match => (
      <tr>
        <td><input type="checkbox" value={match.id} /></td>
        <td>{match.person_name}</td>
        <td>{match.source}</td>
        <td>{match.match_score}</td>
        <td><a href={match.url}>View</a></td>
      </tr>
    ))}
  </tbody>
</table>

<button onClick={batchApprove}>Approve Selected</button>
<button onClick={batchReject}>Reject Selected</button>
```

**Impact**: Review 100 matches in 5 minutes instead of 50 minutes

---

## Complete Seamless Workflow (Local Agent + Remote API)

**User Experience**:

1. **Setup (one-time, 10 minutes)**:

   **On your local machine**:
   - Install research agent: `pip install genealogy-research-agent`
   - Start agent: `research-agent start`
   - Agent runs in system tray (Mac menu bar / Windows taskbar)

   **In genealogy web UI** (family.milanese.life):
   - Settings → Research
   - Enable sources: Antenati, Geneanet, WikiTree
   - Set confidence threshold: 60
   - Enable auto-schedule: Every night at 2 AM
   - Save settings (syncs to local agent)

2. **Automatic Research (runs locally)**:
   - **2 AM**: Local agent wakes up (if computer is on)
   - Checks if Chrome is running with debug port
   - Fetches 100 researchable tasks from remote API
   - Searches 100 people across 7 sources using local Chrome
   - Extracts records, scores matches, filters to 60+ confidence
   - Submits ~350 high-quality matches to remote API
   - **4 AM**: Research completes
   - Desktop notification: "Research complete: 350 matches found"
   - Email notification: "Research complete: 350 matches found"

3. **Manual Review (next morning, from anywhere)**:
   - Open genealogy site → Review Queue
   - See 350 matches sorted by confidence score
   - For high-confidence matches (80+):
     - Scan list, select 50 obvious matches
     - Click "Approve Selected" → auto-creates parents/links
   - For medium-confidence matches (60-79):
     - Click URL → verify → approve or reject individually
   - Total review time: 30 minutes

4. **Continuous Improvement**:
   - System learns from your approvals/rejections
   - Next run: Adjusts confidence thresholds per source
   - Fewer false positives over time

**Total Time Investment**:
- Setup: 10 minutes (one-time)
- Daily review: 30 minutes (from anywhere, not tied to local machine)
- Manual intervention: Zero (runs automatically when computer is on)

**Result**: 100 people researched daily with minimal effort

---

## Deployment Options

### Option A: System Tray App (Recommended)
**Best for**: Always-on computer (Mac mini, desktop)

```bash
# Install
pip install genealogy-research-agent

# Start (runs in background)
research-agent start

# Configure auto-start on boot
research-agent install-service
```

**Features**:
- Runs in system tray
- Right-click → "Start Research Now"
- Right-click → "Open Review Queue"
- Auto-starts on boot
- Scheduled research at 2 AM

---

### Option B: Manual Start (Simple)
**Best for**: Laptop, occasional use

```bash
# Run when you want
python run_european_research.py

# Or via local web UI
python research_agent.py
# Opens http://localhost:8765
# Click "Start Research"
```

**Features**:
- No background process
- Run when convenient
- Still integrates with remote API

---

### Option C: Docker Container (Advanced)
**Best for**: Running on home server with Chrome in Docker

```yaml
# docker-compose.yml
services:
  chrome:
    image: browserless/chrome
    ports:
      - "9222:3000"
    environment:
      - CHROME_ARGS=--remote-debugging-port=9222

  research-agent:
    build: .
    depends_on:
      - chrome
    environment:
      - CHROME_URL=http://chrome:9222
      - API_URL=https://family.milanese.life/api/graphql
      - API_KEY=${API_KEY}
    volumes:
      - ./.cache:/app/.cache
```

**Note**: This won't have your logins, so limited to sources that don't require authentication.

---

## Implementation Priority

**Phase 1 (Essential - 1 week)**:
- #1: Local desktop app (system tray or simple web UI)
- #3: Auto-resume from crashes (persistent job state)
- #7: Graceful error handling
- GraphQL API integration (fetch tasks, submit results)

**Phase 2 (Quality of Life - 1 week)**:
- #2: Real-time progress updates (WebSocket to local UI)
- #5: Desktop + email notifications
- #10: Batch review operations (in remote web UI)

**Phase 3 (Advanced - 2 weeks)**:
- #4: Smart scheduling (local cron/launchd)
- #8: Rate limit detection
- #9: Configuration UI (remote web UI, syncs to local agent)
- #6: Feedback loop learning

---

## Expected Impact

**Before** (Manual Script):
- Open terminal
- Run Python script
- Wait with no visibility
- Check logs manually
- Copy/paste URLs
- Review one-by-one
- **Total effort**: High, requires technical knowledge
- **Tied to local machine**: Must be at computer to review

**After** (Seamless Integration - Local Agent + Remote API):
- **Local agent** runs in system tray (or scheduled)
- Click "Start Research" or runs automatically at 2 AM
- See real-time progress in local UI
- Get desktop + email notification when done
- **Review from anywhere** in remote web UI (phone, laptop, work computer)
- Batch operations for fast review
- System learns and improves
- **Total effort**: Minimal, non-technical friendly
- **Not tied to local machine**: Review from anywhere

**Key Advantage**: Research runs locally (uses your Chrome logins), but results are stored remotely (review from anywhere)

**Bottom Line**: Transform from "technical script you run manually at your desk" to "automated research assistant that works while you sleep, review from anywhere"

