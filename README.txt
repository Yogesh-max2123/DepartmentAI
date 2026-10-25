DepartmentAI Module II - Temporary Chatbot UI
=============================================

This package adds only the new folder:
    module2/chatbot_ui/

It does not edit backend/main.py, backend/api/routes.py, Module I files, or the database.
The temporary UI runs as a separate FastAPI server on http://127.0.0.1:8001.

Install
-------
1. Download the ZIP.
2. Extract its contents into the DepartmentAI project root so that the files land in:
       DepartmentAI\module2\chatbot_ui\
3. Open PowerShell in the project root and activate the existing environment:
       .\venv\Scripts\Activate.ps1
4. Start the UI:
       python -m module2.chatbot_ui.server
5. Open in a browser:
       http://127.0.0.1:8001

The server reuses the existing Module II retrieval corpus and Gemini answer generator.
It expects the existing project dependencies, database configuration, faculty retrieval
cache/model, and GEMINI_API_KEY to be configured as they are for the faculty assistant.
If FastAPI or Uvicorn is missing from the existing venv, install only those missing packages.

Temporary scope and limitations
------------------------------
- Intended for testing the Module II CSED faculty question-answering flow.
- It uses retrieved evidence and the existing Gemini answer generator.
- It is not a replacement for the CLI assistant and does not expose all structured analytics,
  export commands, or all special-case workflows from the CLI assistant.
- Verify important information against official sources.
- Stop the server with Ctrl+C in the terminal.
