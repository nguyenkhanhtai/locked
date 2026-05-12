# Study Toolkit App

This is a local study-toolkit app that I made for my IT003 subject. This toolkit includes many tools designed to aid my studies, including website blocking, task lists, and an AI chatbot. I plan to expand this further in the future when I have more ideas.

### Tech Stack
- **Model:** Gemini, OpenAI, OpenRouter
- **Database:** SQLite
- **Backend:** Python Starlette
- **Frontend:** HTML, CSS, and JavaScript

### Core Idea
The application maintains two concurrent servers: one to handle the backend APIs and databases, and another to act as a background window listener to observe and block distracting websites.

# Installation Guide

```bash
pip install uv
git clone https://github.com/nguyenkhanhtai/locked.git
cd locked
uv sync

scripts\activate.bat
```

# Functions

As a comprehensive study toolkit, Locked is designed to minimize distractions and maximize learning efficiency. Here are the core features:

## Blocklist & Time Tracking
- **Website Blocking**: Temporarily or permanently block distracting websites to maintain focus during study sessions. The app actively monitors your active browser window to prevent access to locked URLs.
- **Time Tracking**: Automatically tracks the time you spend on various domains, providing a top-sites consumption chart to help you stay aware of your browsing habits.

## Task Management
- **Task Tracking**: Add, edit, and organize tasks with priorities, labels, and deadlines.
- **Gantt / Calendar View**: Visualize your upcoming deadlines on a monthly timeline to plan your study schedule effectively.

## Study Room
- **Memorize (Flashcards)**: Create projects and flashcards to review concepts. It features an AI-graded test mode that uses semantic similarity (via Embeddings or LLM Prompting) to accurately evaluate your typed answers against the ground truth.
- **Thinking Workspace**: A dedicated space to break down complex problems. You can define a problem statement and organize your thoughts into 'Knowledge', 'Inferences' (derived from multiple sources), and 'Questions/Hypotheses' to map out your logical reasoning.

## AI Chatbot
- **Context-Aware Assistant**: An integrated AI assistant (supporting Google Gemini, OpenAI, and OpenRouter) that helps you study, code, and solve problems.
- **Web & App Integration**: Equipped with MCP (Model Context Protocol) tools, the AI can seamlessly search the web, read webpages, check your schedule, and view your blocklist to provide highly contextual answers.

# Hotkeys

To keep your workflow seamless and uninterrupted, Locked supports global hotkeys that open quick-action popups directly over your active windows. 

By default, they are configured as follows:

- **Quick Block** (`Ctrl + Alt + Shift + B`): Instantly block the website you are currently viewing.
- **Quick Task** (`Ctrl + Alt + Shift + T`): Quickly add a new task or deadline without opening the main app.
- **Quick Flashcard** (`Ctrl + Alt + Shift + M`): Instantly save a new term or concept into your Memorize flashcards.

*(Note: You can fully customize these keybindings inside the app's Settings).*
