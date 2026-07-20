# 📊 AP Data Analysis Platform

A powerful Streamlit-based data analytics application that enables users to upload datasets, clean data, create pivot tables, build charts, run SQL queries, and generate analytical insights through an intuitive web interface.

## 🚀 Live Demo

https://ap-data-analysis-cjsgeny2huax9pj4u4siqk.streamlit.app/?embed=true

---

## ✨ Features

### 📁 Data Upload
- Upload CSV and Excel files
- Automatic data preview
- Dataset information summary

### 🧹 Data Cleaning
- Handle missing values
- Remove duplicates
- Data type optimization
- Column filtering

### 📊 Pivot Builder
- Dynamic pivot table creation
- Multiple aggregation options:
  - Sum
  - Mean
  - Count
  - Max
  - Min
- Export pivot results to Excel

### 📈 Chart Builder
- Interactive visualizations
- Multiple chart types
- Custom chart configuration

### 🗄 SQL Studio
- Run SQL queries directly on uploaded datasets
- Instant query results
- Data exploration capabilities

### 🤖 AI Insights
- Automated analytical summaries
- Dataset intelligence
- Business insights generation

### 🔐 Authentication
- Secure login system
- User access management

---

## 🛠 Technology Stack

| Technology | Purpose |
|------------|----------|
| Python | Backend Logic |
| Streamlit | Web Application Framework |
| Pandas | Data Processing |
| Plotly | Interactive Charts |
| SQLite | SQL Query Engine |
| Docker | Containerization |
| GitHub | Version Control |
| Streamlit Community Cloud | Deployment |

---

## 📂 Project Structure

```text
AP_Data_Analysis_App/
│
├── app.py
├── requirements.txt
├── Dockerfile
│
├── app_pages/
│   ├── dashboard.py
│   ├── data_cleaning.py
│   ├── pivot_builder.py
│   ├── chart_builder.py
│   ├── sql_studio.py
│   └── ai_insights.py
│
├── auth/
│   ├── login.py
│   └── users.py
│
├── services/
│   ├── cleaning_service.py
│   ├── chart_service.py
│   └── sql_service.py
│
├── core/
│   └── file_loader.py
│
└── assets/
```

---

## ⚙️ Local Installation

### Clone Repository

```bash
git clone https://github.com/arkadhol13-droid/ap-data-analysis.git
cd ap-data-analysis
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Application

```bash
streamlit run app.py
```

---

## 🐳 Docker Deployment

### Build Docker Image

```bash
docker build -t ap-analysis .
```

### Run Container

```bash
docker run -p 8501:8501 ap-analysis
```

Application will be available at:

```text
http://34.224.99.117:8501

## 👨‍💻 Author

**Arka Dhol**

GitHub:
https://github.com/arkadhol13-droid
App Link - https://ap-data-analysis-cjsgeny2huax9pj4u4siqk.streamlit.app/?embed=true
App Credential id-user
password- user123

