# Post-Mortem Generator

AI-powered tool that converts raw incident notes into structured, blameless post-mortems.

## Features

- Paste free-form notes (Slack threads, alert text, on-call logs — anything)
- Streams a structured post-mortem in real time
- Download output as **Markdown** or **PDF**

## Generated Sections

- Incident Overview (severity, duration, status)
- Executive Summary
- Timeline
- Root Cause Analysis + 5 Whys
- Impact Assessment
- Resolution
- Action Items
- Lessons Learned

## Setup

```bash
pip install anthropic streamlit fpdf2 python-dotenv
```

Copy `.env.example` to `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=your_key_here
```

## Usage

### Local

```bash
streamlit run app.py
```

### Docker

```bash
docker build -t postmortem-generator .
docker run -p 8501:8501 -e ANTHROPIC_API_KEY=your_key_here postmortem-generator
```

Open [http://localhost:8501](http://localhost:8501), paste your incident notes, and click **Generate Post-Mortem**.
