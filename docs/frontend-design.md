# Frontend design

The workspace serves both technical users and beginners. Starting a scan and
understanding its results are the primary tasks. Dark neutral surfaces, a muted
blue accent, balanced spacing, and compact top navigation apply across the app.
There is no logo.

- **Overview** (`/dashboard`): landing page, a new-scan action, recent requests,
  and the latest scan's status and timing. Counts explicitly describe the loaded
  recent requests; they are not global totals.
- **Scans** (`/scans`): a visible compact form, server-side target/status/date
  filters, paginated requests, and expandable selected results below the list.
  Ports start empty, with editable presets and collapsed advanced options.
- **Report details** (`/scans/<id>/report`): connection evidence, SSH identification,
  confidence, escaped raw bytes, and scan configuration. Minimal result tables
  remain numerically ordered by port, then IP.
- **Target history** (`/history`): all completed runs, newest first, with changed
  runs highlighted. Each expands into differences against its older predecessor.
  Failed and queued jobs are not comparison evidence.
- **Profile** (`/profile`): read-only account details. Registration and login use
  the same theme. Login returns to Overview or the requested protected page.

Status labels accompany color. Unknown is inconclusive; missing coverage is not
closure. Banner identity is self-reported, not a vulnerability conclusion. The
API retains the earlier ascending history default; the UI requests descending
presentation explicitly. No schema migration is needed for these API changes.

Desktop layouts collapse to stacked controls on narrow screens, with horizontally
scrollable tables and visible keyboard focus. JWTs remain in memory and refresh
through the existing endpoint; a page reload still requires signing in again.

The research references informed navigation and progressive detail, not scanner
capabilities: [Nessus result/history views](https://docs.tenable.com/nessus/Content/ScanResults.htm),
[Zenmap host and service views](https://nmap.org/book/zenmap-results.html), and
[Greenbone report comparisons](https://docs.greenbone.net/GSM-Manual/gos-25.0/en/reports.html).
