# Sample Chat Exports

This directory contains sample chat transcripts for testing the import feature.

## Files

### sample_conversations.json

ChatGPT-style export format with multiple conversations about a fictional "Project Lighthouse" team. Demonstrates:
- Overlapping entities (people, technologies, companies)
- Entity relationships (who works on what, who manages whom)
- Temporal updates (pricing changes, team additions)

### sample_transcript.md

Markdown transcript format about an ML pipeline. Uses `User:` and `Bot:` prefixes.

## Usage

Import via the API:

```bash
# JSON format
curl -X POST http://localhost:8000/v1/imports/chats \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d @- << EOF
{
  "content": $(cat sample_conversations.json | jq -Rs .),
  "source_prefix": "chat-import"
}
EOF

# Or upload a file
curl -X POST http://localhost:8000/v1/imports/chats/upload \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@sample_conversations.json"
```

Or use the dashboard Import page at `/dashboard/import`.
