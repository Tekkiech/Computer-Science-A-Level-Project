# Revision Quiz

## Overview
A web-based revision quiz application for students studying GCSE and A-Level subjects. Built with Python and Flask.

## Project Structure
```
web-revision_quiz/       # Main web application
  webui.py              # Flask web server (port 5000)
  main.py               # Core quiz logic and utilities
  questions/            # JSON question files
  performance.json      # User performance tracking

main-revision_quiz/      # CLI version
testing-revision_quiz/   # Test version
```

## Tech Stack
- Python 3.11
- Flask web framework
- JSON for data storage

## Running the Application
The web app runs on port 5000 via the "Web App" workflow:
```
cd web-revision_quiz && python webui.py
```

## Features
- Quiz mode with questions for various subjects
- Performance tracking across sessions
- Support for GCSE and A-Level content
- Topics: Maths, Further Maths, Physics, Biology, Chemistry, Computer Science

## Recent Changes
- 2026-02-05: Initial setup for Replit environment
