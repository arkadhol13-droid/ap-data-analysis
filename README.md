# 📊 Data Analysis Dashboard

A modern Streamlit-based Data Analysis Platform designed for data exploration, cleaning, visualization, SQL analysis, and AI-powered insights. The application provides an end-to-end workflow from raw data upload to cleaned datasets and interactive business intelligence dashboards.

---

## 🚀 Key Features

### 📂 Data Upload
- CSV File Support
- Excel File Support (.xlsx)
- Instant Dataset Loading
- Large Dataset Handling

### 📊 Dashboard
- Dataset Preview
- Row & Column Count
- Missing Value Analysis
- Data Quality Score
- Statistical Summary
- Dynamic Filters
- Quick Insights

### 📈 Chart Builder
Supports multiple chart types:
- Bar Chart
- Line Chart
- Multi-Line Comparison Chart
- Scatter Plot
- Pie Chart
- Histogram
- Box Plot
- Treemap

### 📋 Pivot Builder
- Dynamic Pivot Tables
- Aggregation Functions
- Interactive Analysis
- Excel Export

### 🛠 Data Cleaning Center
Manual Cleaning:
- Mean
- Median
- Mode
- Standard Deviation
- Quartiles (25%, 50%, 75%)
- Forward Fill
- Backward Fill

AI Cleaning:
- Missing Value Detection
- Null / None / NaN Handling
- Negative Value Correction
- Duplicate Removal
- Auto Data Type Detection
- Data Quality Improvement

Additional Features:
- Undo / Redo
- Dataset Reset
- Download Cleaned Dataset

### 🤖 AI Insights
Ask questions directly from your dataset:
- Highest Value
- Lowest Value
- Average
- Total Records
- Dataset Summary
- Dynamic Column-Based Queries

### 🗄 SQL Studio
- Run SQL Queries on Uploaded Data
- SQLite Engine
- Instant Results
- Interactive Tables

---

## 🏗 Project Structure

```text
data_analysis_app/

├── app.py
├── config/
├── auth/
├── core/
├── pages/
├── services/
├── assets/
├── .streamlit/
├── requirements.txt
└── README.md