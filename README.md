# Hierarchical Agent Teams - Streaming Response Demo

## Features

- Hierarchical agent teams implemented with reference to LangGraph tutorials
- Streaming responses implemented with FastAPI
- Real-time display of agent output in frontend using Server-Sent Events (SSE)
- Support for both GET and POST request methods
- Both synchronous and asynchronous API endpoints

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running

1. Start the backend API server:

```bash
python backend/main.py --api
```

2. Start the frontend server:

```bash
python frontend/server.py
```

3. Access in browser: `http://localhost:9000`

## API Documentation

After starting the backend server, you can view the API documentation at `http://localhost:8000/docs`.

### Main API Endpoints

- `GET /query?query=<query>&recursion_limit=<limit>` - Stream agent responses
- `POST /query` - Stream agent responses (using JSON request body)
- `POST /query_sync` - Synchronously return all agent responses (return all results at once)

## Usage Example

1. Enter a question in the frontend page
2. Click the "Submit" button
3. View the streaming output from the agent team in real-time
4. Download generated files in the workspace

## Technical Implementation

- Backend uses FastAPI's `StreamingResponse` for streaming responses
- Frontend uses the `EventSource` API to receive server-sent events
- Communication uses the `text/event-stream` media type 