# 📊 AP Data Analysis Platform

A Streamlit-based data analytics app that lets users upload datasets,
clean data, build pivot tables and charts, run SQL queries, and get
AI-generated insights — all behind an enterprise-grade authentication
and role-based access control (RBAC) layer.

---

## 🚀 Live Demo

**App:** https://ap-data-analysis-cjsgeny2huax9pj4u4siqk.streamlit.app/?embed=true

**Demo login (limited "User" role — data analysis features only):**

| Field | Value |
|---|---|
| Username | `user` |
| Password | `<user123>` |

> Admin credentials are kept private (they unlock user management,
> session control, and audit logs) — available on request, or run your
> own instance in a few minutes using the setup steps below.

---

## ✨ Features

- **📁 Data Upload** — CSV/Excel upload with automatic preview and dataset summary
- **🧹 Data Cleaning** — handle missing values, remove duplicates, fix data types
- **📊 Pivot Builder** — dynamic pivot tables (Sum, Mean, Count, Max, Min) with Excel export
- **📈 Chart Builder** — interactive visualizations powered by Plotly
- **🗄 SQL Studio** — run SQL queries directly on your uploaded data, sandboxed to safe read-only `SELECT` statements
- **🤖 AI Insights** — automated analytical summaries, rate-limited to prevent abuse

---

## 🔐 Security Architecture

This app includes a full authentication & authorization subsystem
designed around the OWASP Top 10 — see [`SECURITY.md`](./SECURITY.md)
for the full architecture, flow diagrams, and test coverage.

| Capability | Implementation |
|---|---|
| Password security | bcrypt hashing + strength policy, auto-migration from legacy plaintext |
| RBAC | Admin / Manager / User roles, enforced server-side on every request |
| Session management | Server-side session registry — sessions can be revoked individually or in bulk |
| Auto logout | Idle sessions expire after 30 minutes automatically |
| Admin force logout | Admin can log out a single device, selected users, or everyone, instantly |
| Login protection | 5 failed attempts → 15-minute lockout, generic error messages |
| Rate limiting | Sliding-window limits on login and AI Insights |
| Audit logging | Every security event logged; secrets auto-scrubbed before writing |
| SQL sandboxing | SQL Studio locked to read-only queries, blocks injection/escape attempts |
| Test coverage | 44 automated unit + integration tests, all passing |

---

## 🛠 Technology Stack

Python · Streamlit · Pandas · NumPy · Plotly · SQLite · bcrypt · Docker · pytest

---

## ⚙️ Local Installation

```bash
git clone https://github.com/arkadhol13-droid/ap-data-analysis.git
cd ap-data-analysis
pip install -r requirements.txt
cp .env.example .env
```
GitHub: [github.com/arkadhol13-droid](https://github.com/arkadhol13-droid)
