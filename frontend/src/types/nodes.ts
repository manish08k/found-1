export interface NodeDef {
  type: string
  label: string
  category: string
  provider: string
  color: string
  description: string
  configFields: ConfigField[]
}

export interface ConfigField {
  key: string
  label: string
  type: 'text' | 'textarea' | 'select' | 'number' | 'boolean' | 'json'
  required?: boolean
  options?: string[]
  placeholder?: string
}

export const PROVIDER_COLORS: Record<string, string> = {
  core: '#6366f1',
  slack: '#4a154b',
  google: '#4285f4',
  gmail: '#ea4335',
  sheets: '#34a853',
  drive: '#4285f4',
  calendar: '#1967d2',
  whatsapp: '#25d366',
  telegram: '#2aabee',
  github: '#24292e',
  notion: '#000000',
  discord: '#5865f2',
  airtable: '#f82b60',
  hubspot: '#ff7a59',
  http: '#10b981',
  ai: '#8b5cf6',
  postgres: '#336791',
  mysql: '#00758f',
  sqlite: '#003b57',
  database: '#336791',
  stripe: '#635bff',
  sendgrid: '#1a82e2',
  twilio: '#f22f46',
  jira: '#0052cc',
  trello: '#0079bf',
  pagerduty: '#06ac38',
  asana: '#f06a6a',
  aws_s3: '#ff9900',
  mcp: '#6366f1',
  // Extended LLM providers
  gemini: '#4285f4',
  ollama: '#7c3aed',
  huggingface: '#ff9d00',
  cohere: '#39594d',
  mistral: '#ff7000',
  groq: '#f55036',
  azure: '#0078d4',
  // Tool nodes
  tool: '#14b8a6',
  // New SaaS integrations
  zendesk: '#03363d',
  linear: '#5e6ad2',
  salesforce: '#00a1e0',
  confluence: '#172b4d',
  zoom: '#2d8cff',
  monday: '#ff3d57',
  mailchimp: '#ffe01b',
  freshdesk: '#25c16f',
  intercom: '#1f8ded',
  typeform: '#262627',
  box: '#0061d5',
  dropbox: '#0061fe',
  // Document loaders and splitters
  loader: '#0d9488',
  splitter: '#6366f1',
  // Agents
  agent: '#7c3aed',
}

export const NODE_CATALOG: NodeDef[] = [
  // ── AI ───────────────────────────────────────────────────────────────────────
  { type: 'ai.chat', label: 'AI Chat', category: 'AI', provider: 'ai', color: '#8b5cf6', description: 'Prompt an LLM (Claude / GPT)', configFields: [
    { key: 'provider', label: 'Provider', type: 'select', options: ['auto', 'anthropic', 'openai'] },
    { key: 'model', label: 'Model (optional)', type: 'text', placeholder: 'claude-sonnet-4-6' },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true, placeholder: 'Summarize this email: {{body}}' },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
    { key: 'temperature', label: 'Temperature', type: 'number' },
  ] },
  { type: 'ai.extract', label: 'AI Extract / Classify', category: 'AI', provider: 'ai', color: '#8b5cf6', description: 'Extract structured JSON from text', configFields: [
    { key: 'provider', label: 'Provider', type: 'select', options: ['auto', 'anthropic', 'openai'] },
    { key: 'model', label: 'Model (optional)', type: 'text', placeholder: 'claude-sonnet-4-6' },
    { key: 'text', label: 'Input Text (optional, supports {{field}})', type: 'textarea', placeholder: '{{body}}' },
    { key: 'schema_description', label: 'Fields to Extract', type: 'textarea', required: true, placeholder: "category: one of 'sales','support','spam'; urgency: 1-5; summary: string" },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
  ] },

  // ── Triggers ────────────────────────────────────────────────────────────────
  { type: 'trigger.manual', label: 'Manual Trigger', category: 'Triggers', provider: 'core', color: '#6366f1', description: 'Start workflow manually', configFields: [] },
  { type: 'trigger.webhook', label: 'Webhook', category: 'Triggers', provider: 'core', color: '#6366f1', description: 'Trigger on HTTP request', configFields: [{ key: 'method', label: 'Method', type: 'select', options: ['POST', 'GET', 'PUT', 'PATCH'] }] },
  { type: 'trigger.schedule', label: 'Schedule', category: 'Triggers', provider: 'core', color: '#6366f1', description: 'Cron or interval trigger', configFields: [{ key: 'cron_expression', label: 'Cron', type: 'text', placeholder: '0 9 * * 1-5' }, { key: 'timezone', label: 'Timezone', type: 'text', placeholder: 'UTC' }] },

  // ── Core ────────────────────────────────────────────────────────────────────
  { type: 'http.request', label: 'HTTP Request', category: 'Core', provider: 'http', color: '#10b981', description: 'Make any HTTP call', configFields: [{ key: 'method', label: 'Method', type: 'select', options: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], required: true }, { key: 'url', label: 'URL', type: 'text', required: true }, { key: 'headers', label: 'Headers (JSON)', type: 'json' }, { key: 'body', label: 'Body (JSON)', type: 'json' }] },
  { type: 'core.filter', label: 'Filter', category: 'Core', provider: 'core', color: '#6366f1', description: 'Filter items by condition', configFields: [{ key: 'field', label: 'Field', type: 'text', required: true }, { key: 'operator', label: 'Operator', type: 'select', options: ['equals', 'not_equals', 'contains', 'not_contains', 'greater_than', 'less_than', 'is_empty', 'is_not_empty', 'regex'], required: true }, { key: 'value', label: 'Value', type: 'text' }] },
  { type: 'core.transform', label: 'Transform', category: 'Core', provider: 'core', color: '#6366f1', description: 'Reshape data with mapping', configFields: [{ key: 'mapping', label: 'Mapping (JSON)', type: 'json', required: true }] },
  { type: 'core.set_variables', label: 'Set Variables', category: 'Core', provider: 'core', color: '#6366f1', description: 'Inject static values', configFields: [{ key: 'variables', label: 'Variables (JSON)', type: 'json', required: true }] },
  { type: 'core.condition', label: 'Condition', category: 'Core', provider: 'core', color: '#6366f1', description: 'Branch true/false', configFields: [{ key: 'field', label: 'Field', type: 'text', required: true }, { key: 'operator', label: 'Operator', type: 'select', options: ['equals', 'not_equals', 'contains', 'greater_than', 'less_than', 'is_true', 'is_false', 'regex'], required: true }, { key: 'value', label: 'Value', type: 'text' }] },
  { type: 'core.delay', label: 'Delay', category: 'Core', provider: 'core', color: '#6366f1', description: 'Wait N seconds', configFields: [{ key: 'seconds', label: 'Seconds', type: 'number', required: true }] },
  { type: 'core.merge', label: 'Merge', category: 'Core', provider: 'core', color: '#6366f1', description: 'Merge multiple inputs', configFields: [{ key: 'mode', label: 'Mode', type: 'select', options: ['merge', 'append', 'zip'] }] },
  { type: 'core.split_in_batches', label: 'Split Batches', category: 'Core', provider: 'core', color: '#6366f1', description: 'Iterate over list', configFields: [{ key: 'batch_size', label: 'Batch Size', type: 'number', required: true }] },
  { type: 'core.run_code', label: 'Run Code', category: 'Core', provider: 'core', color: '#6366f1', description: 'Execute Python snippet', configFields: [{ key: 'code', label: 'Python Code', type: 'textarea', required: true }] },
  { type: 'core.format_date', label: 'Format Date', category: 'Core', provider: 'core', color: '#6366f1', description: 'Format / convert dates', configFields: [{ key: 'output_format', label: 'Output Format', type: 'text', placeholder: 'YYYY-MM-DD HH:mm:ss' }, { key: 'output_timezone', label: 'Output Timezone', type: 'text', placeholder: 'Asia/Kolkata' }] },
  { type: 'core.json_parse', label: 'JSON Parse', category: 'Core', provider: 'core', color: '#6366f1', description: 'Parse JSON string', configFields: [{ key: 'json_string', label: 'JSON String', type: 'textarea' }] },
  { type: 'core.send_email_smtp', label: 'Send Email', category: 'Core', provider: 'core', color: '#6366f1', description: 'Send via SMTP', configFields: [{ key: 'to', label: 'To', type: 'text', required: true }, { key: 'subject', label: 'Subject', type: 'text', required: true }, { key: 'body', label: 'Body', type: 'textarea', required: true }, { key: 'html', label: 'HTML?', type: 'boolean' }] },

  // ── Slack ───────────────────────────────────────────────────────────────────
  { type: 'slack.send_message', label: 'Send Message', category: 'Slack', provider: 'slack', color: '#4a154b', description: 'Post to a channel', configFields: [{ key: 'channel', label: 'Channel', type: 'text', required: true, placeholder: '#general' }, { key: 'text', label: 'Text', type: 'textarea', required: true }] },
  { type: 'slack.send_dm', label: 'Send DM', category: 'Slack', provider: 'slack', color: '#4a154b', description: 'Direct message a user', configFields: [{ key: 'user_email', label: 'User Email', type: 'text', required: true }, { key: 'text', label: 'Text', type: 'textarea', required: true }] },
  { type: 'slack.get_messages', label: 'Get Messages', category: 'Slack', provider: 'slack', color: '#4a154b', description: 'Read channel history', configFields: [{ key: 'channel', label: 'Channel', type: 'text', required: true }, { key: 'limit', label: 'Limit', type: 'number' }] },
  { type: 'slack.create_channel', label: 'Create Channel', category: 'Slack', provider: 'slack', color: '#4a154b', description: 'Create a channel', configFields: [{ key: 'name', label: 'Channel Name', type: 'text', required: true }, { key: 'is_private', label: 'Private?', type: 'boolean' }] },
  { type: 'slack.upload_file', label: 'Upload File', category: 'Slack', provider: 'slack', color: '#4a154b', description: 'Upload file to channel', configFields: [{ key: 'channel', label: 'Channel', type: 'text', required: true }, { key: 'content', label: 'Content', type: 'textarea', required: true }, { key: 'filename', label: 'Filename', type: 'text' }] },
  { type: 'slack.add_reaction', label: 'Add Reaction', category: 'Slack', provider: 'slack', color: '#4a154b', description: 'React to a message', configFields: [{ key: 'channel', label: 'Channel', type: 'text', required: true }, { key: 'ts', label: 'Message TS', type: 'text', required: true }, { key: 'reaction', label: 'Emoji', type: 'text', placeholder: 'white_check_mark' }] },

  // ── Google Sheets ───────────────────────────────────────────────────────────
  { type: 'sheets.read_rows', label: 'Read Rows', category: 'Google Sheets', provider: 'sheets', color: '#34a853', description: 'Read spreadsheet rows', configFields: [{ key: 'spreadsheet_id', label: 'Spreadsheet ID', type: 'text', required: true }, { key: 'range', label: 'Range', type: 'text', placeholder: 'Sheet1' }] },
  { type: 'sheets.append_row', label: 'Append Row', category: 'Google Sheets', provider: 'sheets', color: '#34a853', description: 'Append a row', configFields: [{ key: 'spreadsheet_id', label: 'Spreadsheet ID', type: 'text', required: true }, { key: 'range', label: 'Range', type: 'text', placeholder: 'Sheet1' }, { key: 'row', label: 'Row Data (JSON)', type: 'json', required: true }] },
  { type: 'sheets.update_row', label: 'Update Row', category: 'Google Sheets', provider: 'sheets', color: '#34a853', description: 'Update a specific range', configFields: [{ key: 'spreadsheet_id', label: 'Spreadsheet ID', type: 'text', required: true }, { key: 'range', label: 'Range', type: 'text', required: true }, { key: 'row', label: 'Row Data (JSON)', type: 'json', required: true }] },
  { type: 'sheets.create_spreadsheet', label: 'Create Sheet', category: 'Google Sheets', provider: 'sheets', color: '#34a853', description: 'Create a spreadsheet', configFields: [{ key: 'title', label: 'Title', type: 'text', required: true }] },

  // ── Gmail ───────────────────────────────────────────────────────────────────
  { type: 'gmail.send_email', label: 'Send Email', category: 'Gmail', provider: 'gmail', color: '#ea4335', description: 'Send via Gmail', configFields: [{ key: 'to', label: 'To', type: 'text', required: true }, { key: 'subject', label: 'Subject', type: 'text', required: true }, { key: 'body', label: 'Body', type: 'textarea', required: true }, { key: 'html', label: 'HTML?', type: 'boolean' }, { key: 'cc', label: 'CC', type: 'text' }, { key: 'bcc', label: 'BCC', type: 'text' }] },
  { type: 'gmail.get_emails', label: 'Get Emails', category: 'Gmail', provider: 'gmail', color: '#ea4335', description: 'Fetch emails', configFields: [{ key: 'query', label: 'Query', type: 'text', placeholder: 'is:unread' }, { key: 'max_results', label: 'Max Results', type: 'number' }] },
  { type: 'gmail.reply_email', label: 'Reply Email', category: 'Gmail', provider: 'gmail', color: '#ea4335', description: 'Reply to a thread', configFields: [{ key: 'thread_id', label: 'Thread ID', type: 'text', required: true }, { key: 'to', label: 'To', type: 'text', required: true }, { key: 'body', label: 'Body', type: 'textarea', required: true }] },

  // ── Google Drive ────────────────────────────────────────────────────────────
  { type: 'drive.list_files', label: 'List Files', category: 'Google Drive', provider: 'drive', color: '#4285f4', description: 'List drive files', configFields: [{ key: 'folder_id', label: 'Folder ID', type: 'text' }, { key: 'query', label: 'Query', type: 'text' }] },
  { type: 'drive.upload_file', label: 'Upload File', category: 'Google Drive', provider: 'drive', color: '#4285f4', description: 'Upload to drive', configFields: [{ key: 'name', label: 'Filename', type: 'text', required: true }, { key: 'content', label: 'Content', type: 'textarea', required: true }, { key: 'mime_type', label: 'MIME Type', type: 'text', placeholder: 'text/plain' }, { key: 'folder_id', label: 'Folder ID', type: 'text' }] },
  { type: 'drive.create_folder', label: 'Create Folder', category: 'Google Drive', provider: 'drive', color: '#4285f4', description: 'Create a folder', configFields: [{ key: 'name', label: 'Folder Name', type: 'text', required: true }, { key: 'parent_id', label: 'Parent Folder ID', type: 'text' }] },

  // ── Google Calendar ─────────────────────────────────────────────────────────
  { type: 'calendar.create_event', label: 'Create Event', category: 'Google Calendar', provider: 'calendar', color: '#1967d2', description: 'Create calendar event', configFields: [{ key: 'summary', label: 'Title', type: 'text', required: true }, { key: 'start', label: 'Start (ISO)', type: 'text', required: true }, { key: 'end', label: 'End (ISO)', type: 'text', required: true }, { key: 'description', label: 'Description', type: 'textarea' }, { key: 'timezone', label: 'Timezone', type: 'text', placeholder: 'UTC' }] },
  { type: 'calendar.list_events', label: 'List Events', category: 'Google Calendar', provider: 'calendar', color: '#1967d2', description: 'List events', configFields: [{ key: 'time_min', label: 'From (ISO)', type: 'text' }, { key: 'max_results', label: 'Max Results', type: 'number' }] },
  { type: 'calendar.delete_event', label: 'Delete Event', category: 'Google Calendar', provider: 'calendar', color: '#1967d2', description: 'Delete a calendar event', configFields: [{ key: 'event_id', label: 'Event ID', type: 'text', required: true }] },

  // ── WhatsApp ────────────────────────────────────────────────────────────────
  { type: 'whatsapp.send_text', label: 'Send Text', category: 'WhatsApp', provider: 'whatsapp', color: '#25d366', description: 'Send WA text message', configFields: [{ key: 'to', label: 'To (E.164)', type: 'text', required: true, placeholder: '+919999999999' }, { key: 'text', label: 'Message', type: 'textarea', required: true }] },
  { type: 'whatsapp.send_template', label: 'Send Template', category: 'WhatsApp', provider: 'whatsapp', color: '#25d366', description: 'Send approved template', configFields: [{ key: 'to', label: 'To', type: 'text', required: true }, { key: 'template_name', label: 'Template Name', type: 'text', required: true }, { key: 'language_code', label: 'Language', type: 'text', placeholder: 'en_US' }] },
  { type: 'whatsapp.send_image', label: 'Send Image', category: 'WhatsApp', provider: 'whatsapp', color: '#25d366', description: 'Send image message', configFields: [{ key: 'to', label: 'To', type: 'text', required: true }, { key: 'image_url', label: 'Image URL', type: 'text', required: true }, { key: 'caption', label: 'Caption', type: 'text' }] },
  { type: 'whatsapp.mark_read', label: 'Mark Read', category: 'WhatsApp', provider: 'whatsapp', color: '#25d366', description: 'Mark message as read', configFields: [{ key: 'message_id', label: 'Message ID', type: 'text', required: true }] },

  // ── Telegram ────────────────────────────────────────────────────────────────
  { type: 'telegram.send_message', label: 'Send Message', category: 'Telegram', provider: 'telegram', color: '#2aabee', description: 'Send TG message', configFields: [{ key: 'chat_id', label: 'Chat ID', type: 'text', required: true }, { key: 'text', label: 'Text', type: 'textarea', required: true }, { key: 'parse_mode', label: 'Parse Mode', type: 'select', options: ['HTML', 'Markdown', 'MarkdownV2'] }] },
  { type: 'telegram.send_photo', label: 'Send Photo', category: 'Telegram', provider: 'telegram', color: '#2aabee', description: 'Send a photo', configFields: [{ key: 'chat_id', label: 'Chat ID', type: 'text', required: true }, { key: 'photo', label: 'Photo URL / file_id', type: 'text', required: true }, { key: 'caption', label: 'Caption', type: 'text' }] },
  { type: 'telegram.send_poll', label: 'Send Poll', category: 'Telegram', provider: 'telegram', color: '#2aabee', description: 'Create a poll', configFields: [{ key: 'chat_id', label: 'Chat ID', type: 'text', required: true }, { key: 'question', label: 'Question', type: 'text', required: true }, { key: 'options', label: 'Options (JSON array)', type: 'json', required: true }] },

  // ── GitHub ──────────────────────────────────────────────────────────────────
  { type: 'github.create_issue', label: 'Create Issue', category: 'GitHub', provider: 'github', color: '#24292e', description: 'Open a GitHub issue', configFields: [{ key: 'repo', label: 'Repo (owner/repo)', type: 'text', required: true }, { key: 'title', label: 'Title', type: 'text', required: true }, { key: 'body', label: 'Body', type: 'textarea' }] },
  { type: 'github.add_comment', label: 'Add Comment', category: 'GitHub', provider: 'github', color: '#24292e', description: 'Comment on issue/PR', configFields: [{ key: 'repo', label: 'Repo', type: 'text', required: true }, { key: 'issue_number', label: 'Issue #', type: 'number', required: true }, { key: 'body', label: 'Comment', type: 'textarea', required: true }] },
  { type: 'github.create_pr', label: 'Create PR', category: 'GitHub', provider: 'github', color: '#24292e', description: 'Open a pull request', configFields: [{ key: 'repo', label: 'Repo', type: 'text', required: true }, { key: 'title', label: 'Title', type: 'text', required: true }, { key: 'head', label: 'Head Branch', type: 'text', required: true }, { key: 'base', label: 'Base Branch', type: 'text', placeholder: 'main' }] },
  { type: 'github.create_release', label: 'Create Release', category: 'GitHub', provider: 'github', color: '#24292e', description: 'Create a release', configFields: [{ key: 'repo', label: 'Repo', type: 'text', required: true }, { key: 'tag_name', label: 'Tag', type: 'text', required: true }, { key: 'name', label: 'Name', type: 'text' }, { key: 'body', label: 'Notes', type: 'textarea' }] },

  // ── Notion ──────────────────────────────────────────────────────────────────
  { type: 'notion.query_database', label: 'Query Database', category: 'Notion', provider: 'notion', color: '#000000', description: 'Query a Notion DB', configFields: [{ key: 'database_id', label: 'Database ID', type: 'text', required: true }, { key: 'filter', label: 'Filter (JSON)', type: 'json' }, { key: 'page_size', label: 'Limit', type: 'number' }] },
  { type: 'notion.create_page', label: 'Create Page', category: 'Notion', provider: 'notion', color: '#000000', description: 'Create a Notion page', configFields: [{ key: 'parent_id', label: 'Parent DB/Page ID', type: 'text', required: true }, { key: 'parent_type', label: 'Parent Type', type: 'select', options: ['database_id', 'page_id'] }, { key: 'properties', label: 'Properties (JSON)', type: 'json', required: true }] },
  { type: 'notion.update_page', label: 'Update Page', category: 'Notion', provider: 'notion', color: '#000000', description: 'Update a page', configFields: [{ key: 'page_id', label: 'Page ID', type: 'text', required: true }, { key: 'properties', label: 'Properties (JSON)', type: 'json', required: true }] },
  { type: 'notion.search', label: 'Search', category: 'Notion', provider: 'notion', color: '#000000', description: 'Search Notion', configFields: [{ key: 'query', label: 'Query', type: 'text', required: true }] },

  // ── Discord ─────────────────────────────────────────────────────────────────
  { type: 'discord.send_message', label: 'Send Message', category: 'Discord', provider: 'discord', color: '#5865f2', description: 'Post to channel', configFields: [{ key: 'channel_id', label: 'Channel ID', type: 'text', required: true }, { key: 'content', label: 'Content', type: 'textarea', required: true }] },
  { type: 'discord.send_embed', label: 'Send Embed', category: 'Discord', provider: 'discord', color: '#5865f2', description: 'Send embed card', configFields: [{ key: 'channel_id', label: 'Channel ID', type: 'text', required: true }, { key: 'title', label: 'Title', type: 'text', required: true }, { key: 'description', label: 'Description', type: 'textarea' }, { key: 'color', label: 'Color (hex int)', type: 'number' }] },
  { type: 'discord.assign_role', label: 'Assign Role', category: 'Discord', provider: 'discord', color: '#5865f2', description: 'Assign a role', configFields: [{ key: 'guild_id', label: 'Guild ID', type: 'text', required: true }, { key: 'user_id', label: 'User ID', type: 'text', required: true }, { key: 'role_id', label: 'Role ID', type: 'text', required: true }] },

  // ── Airtable ────────────────────────────────────────────────────────────────
  { type: 'airtable.list_records', label: 'List Records', category: 'Airtable', provider: 'airtable', color: '#f82b60', description: 'List table records', configFields: [{ key: 'base_id', label: 'Base ID', type: 'text', required: true }, { key: 'table', label: 'Table', type: 'text', required: true }, { key: 'filter_formula', label: 'Filter Formula', type: 'text' }, { key: 'max_records', label: 'Max Records', type: 'number' }] },
  { type: 'airtable.create_record', label: 'Create Record', category: 'Airtable', provider: 'airtable', color: '#f82b60', description: 'Create a record', configFields: [{ key: 'base_id', label: 'Base ID', type: 'text', required: true }, { key: 'table', label: 'Table', type: 'text', required: true }, { key: 'fields', label: 'Fields (JSON)', type: 'json', required: true }] },
  { type: 'airtable.update_record', label: 'Update Record', category: 'Airtable', provider: 'airtable', color: '#f82b60', description: 'Update a record', configFields: [{ key: 'base_id', label: 'Base ID', type: 'text', required: true }, { key: 'table', label: 'Table', type: 'text', required: true }, { key: 'record_id', label: 'Record ID', type: 'text', required: true }, { key: 'fields', label: 'Fields (JSON)', type: 'json', required: true }] },
  { type: 'airtable.upsert_record', label: 'Upsert Record', category: 'Airtable', provider: 'airtable', color: '#f82b60', description: 'Create or update', configFields: [{ key: 'base_id', label: 'Base ID', type: 'text', required: true }, { key: 'table', label: 'Table', type: 'text', required: true }, { key: 'fields', label: 'Fields (JSON)', type: 'json', required: true }, { key: 'fields_to_merge_on', label: 'Match Fields (JSON)', type: 'json' }] },

  // ── HubSpot ─────────────────────────────────────────────────────────────────
  { type: 'hubspot.create_contact', label: 'Create Contact', category: 'HubSpot', provider: 'hubspot', color: '#ff7a59', description: 'Create CRM contact', configFields: [{ key: 'properties', label: 'Properties (JSON)', type: 'json', required: true }] },
  { type: 'hubspot.update_contact', label: 'Update Contact', category: 'HubSpot', provider: 'hubspot', color: '#ff7a59', description: 'Update a contact', configFields: [{ key: 'contact_id', label: 'Contact ID', type: 'text', required: true }, { key: 'properties', label: 'Properties (JSON)', type: 'json', required: true }] },
  { type: 'hubspot.create_deal', label: 'Create Deal', category: 'HubSpot', provider: 'hubspot', color: '#ff7a59', description: 'Create a deal', configFields: [{ key: 'properties', label: 'Properties (JSON)', type: 'json', required: true }] },
  { type: 'hubspot.search_contacts', label: 'Search Contacts', category: 'HubSpot', provider: 'hubspot', color: '#ff7a59', description: 'Search CRM contacts', configFields: [{ key: 'filters', label: 'Filters (JSON)', type: 'json', required: true }] },

  // ── Database ────────────────────────────────────────────────────────────────
  { type: 'database.query', label: 'Database Query', category: 'Database', provider: 'database', color: '#336791', description: 'Run a read-only SELECT against your database', configFields: [
    { key: 'query', label: 'SQL (SELECT only)', type: 'textarea', required: true, placeholder: 'SELECT * FROM users WHERE id = :user_id' },
    { key: 'params', label: 'Bind Params (JSON)', type: 'json', placeholder: '{ "user_id": "{{input.id}}" }' },
    { key: 'max_rows', label: 'Max Rows', type: 'number', placeholder: '1000' },
    { key: 'timeout', label: 'Timeout (sec)', type: 'number', placeholder: '20' },
  ] },
  { type: 'database.execute', label: 'Database Execute', category: 'Database', provider: 'database', color: '#336791', description: 'Run INSERT/UPDATE/DELETE/DDL against your database', configFields: [
    { key: 'query', label: 'SQL', type: 'textarea', required: true, placeholder: 'UPDATE users SET status = :status WHERE id = :user_id' },
    { key: 'params', label: 'Bind Params (JSON)', type: 'json', placeholder: '{ "status": "active", "user_id": "{{input.id}}" }' },
    { key: 'timeout', label: 'Timeout (sec)', type: 'number', placeholder: '20' },
  ] },

  // ── Stripe ──────────────────────────────────────────────────────────────────
  { type: 'stripe.create_payment_link', label: 'Create Payment Link', category: 'Stripe', provider: 'stripe', color: '#635bff', description: 'Generate a checkout link for a price', configFields: [
    { key: 'price_id', label: 'Price ID', type: 'text', required: true, placeholder: 'price_1AbC...' },
    { key: 'quantity', label: 'Quantity', type: 'number', placeholder: '1' },
  ] },
  { type: 'stripe.get_customer', label: 'Get Customer', category: 'Stripe', provider: 'stripe', color: '#635bff', description: 'Look up a customer by ID', configFields: [
    { key: 'customer_id', label: 'Customer ID', type: 'text', required: true, placeholder: 'cus_AbC123' },
  ] },
  { type: 'stripe.list_charges', label: 'List Charges', category: 'Stripe', provider: 'stripe', color: '#635bff', description: 'List recent charges, optionally for one customer', configFields: [
    { key: 'customer_id', label: 'Customer ID (optional)', type: 'text' },
    { key: 'limit', label: 'Limit', type: 'number', placeholder: '10' },
  ] },
  { type: 'stripe.create_refund', label: 'Create Refund', category: 'Stripe', provider: 'stripe', color: '#635bff', description: 'Refund a charge, fully or partially', configFields: [
    { key: 'charge_id', label: 'Charge ID', type: 'text', required: true, placeholder: 'ch_AbC123' },
    { key: 'amount', label: 'Amount in cents (blank = full refund)', type: 'number' },
  ] },

  // ── Email ───────────────────────────────────────────────────────────────────
  { type: 'email.send', label: 'Send Email', category: 'Email', provider: 'sendgrid', color: '#1a82e2', description: 'Send an email via SendGrid', configFields: [
    { key: 'to', label: 'To', type: 'text', required: true, placeholder: 'someone@example.com' },
    { key: 'from', label: 'From', type: 'text', required: true, placeholder: 'you@yourdomain.com' },
    { key: 'subject', label: 'Subject', type: 'text', required: true },
    { key: 'body', label: 'Body', type: 'textarea', required: true },
    { key: 'html', label: 'Body is HTML', type: 'boolean' },
  ] },

  // ── Twilio ──────────────────────────────────────────────────────────────────
  { type: 'twilio.send_sms', label: 'Send SMS', category: 'Twilio', provider: 'twilio', color: '#f22f46', description: 'Send a text message', configFields: [
    { key: 'to', label: 'To (E.164, e.g. +14155552671)', type: 'text', required: true },
    { key: 'from', label: 'From (your Twilio number)', type: 'text', required: true },
    { key: 'body', label: 'Message', type: 'textarea', required: true },
  ] },

  // ── Jira ────────────────────────────────────────────────────────────────────
  { type: 'jira.create_issue', label: 'Create Issue', category: 'Jira', provider: 'jira', color: '#0052cc', description: 'Create a new issue in a project', configFields: [
    { key: 'project_key', label: 'Project Key', type: 'text', required: true, placeholder: 'ENG' },
    { key: 'summary', label: 'Summary', type: 'text', required: true },
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'issue_type', label: 'Issue Type', type: 'text', placeholder: 'Task' },
  ] },
  { type: 'jira.search_issues', label: 'Search Issues', category: 'Jira', provider: 'jira', color: '#0052cc', description: 'Search issues with JQL', configFields: [
    { key: 'jql', label: 'JQL Query', type: 'textarea', required: true, placeholder: 'project = ENG AND status = "In Progress"' },
    { key: 'max_results', label: 'Max Results', type: 'number', placeholder: '20' },
  ] },
  { type: 'jira.add_comment', label: 'Add Comment', category: 'Jira', provider: 'jira', color: '#0052cc', description: 'Comment on an existing issue', configFields: [
    { key: 'issue_key', label: 'Issue Key', type: 'text', required: true, placeholder: 'ENG-123' },
    { key: 'comment', label: 'Comment', type: 'textarea', required: true },
  ] },

  // ── Trello ──────────────────────────────────────────────────────────────────
  { type: 'trello.create_card', label: 'Create Card', category: 'Trello', provider: 'trello', color: '#0079bf', description: 'Add a new card to a list', configFields: [
    { key: 'list_id', label: 'List ID', type: 'text', required: true },
    { key: 'name', label: 'Card Name', type: 'text', required: true },
    { key: 'description', label: 'Description', type: 'textarea' },
  ] },
  { type: 'trello.move_card', label: 'Move Card', category: 'Trello', provider: 'trello', color: '#0079bf', description: 'Move a card to a different list', configFields: [
    { key: 'card_id', label: 'Card ID', type: 'text', required: true },
    { key: 'list_id', label: 'Destination List ID', type: 'text', required: true },
  ] },
  { type: 'trello.list_cards', label: 'List Cards', category: 'Trello', provider: 'trello', color: '#0079bf', description: 'Get all cards in a list', configFields: [
    { key: 'list_id', label: 'List ID', type: 'text', required: true },
  ] },

  // ── PagerDuty ───────────────────────────────────────────────────────────────
  { type: 'pagerduty.trigger_incident', label: 'Trigger Incident', category: 'PagerDuty', provider: 'pagerduty', color: '#06ac38', description: 'Open a new PagerDuty incident', configFields: [
    { key: 'summary', label: 'Summary', type: 'text', required: true },
    { key: 'severity', label: 'Severity (critical/error/warning/info)', type: 'text', placeholder: 'error' },
    { key: 'source', label: 'Source', type: 'text', placeholder: 'autoflow' },
    { key: 'dedup_key', label: 'Dedup Key (optional)', type: 'text' },
  ] },
  { type: 'pagerduty.resolve_incident', label: 'Resolve Incident', category: 'PagerDuty', provider: 'pagerduty', color: '#06ac38', description: 'Resolve a previously triggered incident', configFields: [
    { key: 'dedup_key', label: 'Dedup Key', type: 'text', required: true },
  ] },

  // ── Asana ───────────────────────────────────────────────────────────────────
  { type: 'asana.create_task', label: 'Create Task', category: 'Asana', provider: 'asana', color: '#f06a6a', description: 'Add a new task to a project', configFields: [
    { key: 'project_id', label: 'Project ID', type: 'text', required: true },
    { key: 'name', label: 'Task Name', type: 'text', required: true },
    { key: 'notes', label: 'Notes', type: 'textarea' },
  ] },
  { type: 'asana.complete_task', label: 'Complete Task', category: 'Asana', provider: 'asana', color: '#f06a6a', description: 'Mark a task as completed', configFields: [
    { key: 'task_gid', label: 'Task ID', type: 'text', required: true },
  ] },
  { type: 'asana.list_tasks', label: 'List Tasks', category: 'Asana', provider: 'asana', color: '#f06a6a', description: 'Get tasks in a project', configFields: [
    { key: 'project_id', label: 'Project ID', type: 'text', required: true },
  ] },

  // ── AWS S3 ──────────────────────────────────────────────────────────────────
  { type: 's3.put_object', label: 'Put Object', category: 'AWS S3', provider: 'aws_s3', color: '#ff9900', description: 'Upload/write a file to a bucket', configFields: [
    { key: 'bucket', label: 'Bucket', type: 'text', required: true },
    { key: 'key', label: 'Key (path)', type: 'text', required: true, placeholder: 'reports/2026-07.csv' },
    { key: 'body', label: 'Content', type: 'textarea', required: true },
  ] },
  { type: 's3.get_object', label: 'Get Object', category: 'AWS S3', provider: 'aws_s3', color: '#ff9900', description: 'Read a file from a bucket (max 10MB)', configFields: [
    { key: 'bucket', label: 'Bucket', type: 'text', required: true },
    { key: 'key', label: 'Key (path)', type: 'text', required: true },
  ] },
  { type: 's3.list_objects', label: 'List Objects', category: 'AWS S3', provider: 'aws_s3', color: '#ff9900', description: 'List files under a prefix', configFields: [
    { key: 'bucket', label: 'Bucket', type: 'text', required: true },
    { key: 'prefix', label: 'Prefix', type: 'text', placeholder: 'reports/' },
    { key: 'max_keys', label: 'Max Results', type: 'number', placeholder: '100' },
  ] },
  { type: 's3.generate_presigned_url', label: 'Generate Presigned URL', category: 'AWS S3', provider: 'aws_s3', color: '#ff9900', description: 'Create a temporary download link', configFields: [
    { key: 'bucket', label: 'Bucket', type: 'text', required: true },
    { key: 'key', label: 'Key (path)', type: 'text', required: true },
    { key: 'expires_in_seconds', label: 'Expires In (seconds)', type: 'number', placeholder: '3600' },
  ] },

  // ── MCP (client) ────────────────────────────────────────────────────────────
  { type: 'mcp.list_tools', label: 'List MCP Tools', category: 'MCP', provider: 'mcp', color: '#6366f1', description: 'Discover tools exposed by an MCP server', configFields: [] },
  { type: 'mcp.call_tool', label: 'Call MCP Tool', category: 'MCP', provider: 'mcp', color: '#6366f1', description: 'Call a specific tool on an MCP server', configFields: [
    { key: 'tool_name', label: 'Tool Name', type: 'text', required: true },
    { key: 'arguments', label: 'Arguments (JSON)', type: 'json' },
  ] },
  { type: 'mcp.list_resources', label: 'List MCP Resources', category: 'MCP', provider: 'mcp', color: '#6366f1', description: 'Discover data exposed by an MCP server', configFields: [] },
  { type: 'mcp.read_resource', label: 'Read MCP Resource', category: 'MCP', provider: 'mcp', color: '#6366f1', description: 'Read one resource by URI', configFields: [
    { key: 'uri', label: 'Resource URI', type: 'text', required: true },
  ] },
  { type: 'mcp.list_prompts', label: 'List MCP Prompts', category: 'MCP', provider: 'mcp', color: '#6366f1', description: 'Discover prompt templates on an MCP server', configFields: [] },
  { type: 'mcp.get_prompt', label: 'Get MCP Prompt', category: 'MCP', provider: 'mcp', color: '#6366f1', description: 'Render a prompt template with arguments', configFields: [
    { key: 'prompt_name', label: 'Prompt Name', type: 'text', required: true },
    { key: 'arguments', label: 'Arguments (JSON)', type: 'json' },
  ] },

  // ── Vector Store / RAG ──────────────────────────────────────────────────────
  { type: 'vector.upsert', label: 'Store in Vector DB', category: 'Vector Store', provider: 'core', color: '#10b981', description: 'Embed and store text for later retrieval (RAG indexing)', configFields: [
    { key: 'collection', label: 'Collection', type: 'text', required: true, placeholder: 'docs' },
    { key: 'text', label: 'Text', type: 'textarea', required: true },
    { key: 'metadata', label: 'Metadata (JSON)', type: 'json' },
  ] },
  { type: 'vector.search', label: 'Search Vector DB', category: 'Vector Store', provider: 'core', color: '#10b981', description: 'RAG retrieval: find the most relevant stored text for a query', configFields: [
    { key: 'collection', label: 'Collection', type: 'text', required: true, placeholder: 'docs' },
    { key: 'query', label: 'Query', type: 'text', required: true },
    { key: 'top_k', label: 'Top K', type: 'number', placeholder: '5' },
  ] },
  { type: 'vector.delete_collection', label: 'Clear Vector Collection', category: 'Vector Store', provider: 'core', color: '#10b981', description: 'Delete all stored vectors in a collection', configFields: [
    { key: 'collection', label: 'Collection', type: 'text', required: true },
  ] },

  // ── AI: Memory, Moderation ──────────────────────────────────────────────────
  { type: 'ai.chat_with_memory', label: 'AI Chat (with Memory)', category: 'AI', provider: 'ai', color: '#8b5cf6', description: 'Chat that remembers prior turns in a conversation', configFields: [
    { key: 'conversation_id', label: 'Conversation ID', type: 'text', required: true, placeholder: '{{ trigger.body.user_id }}' },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'model', label: 'Model', type: 'text' },
    { key: 'max_history_messages', label: 'Max History Messages', type: 'number', placeholder: '20' },
  ] },
  { type: 'ai.clear_memory', label: 'Clear AI Memory', category: 'AI', provider: 'ai', color: '#8b5cf6', description: 'Wipe a conversation\'s stored history', configFields: [
    { key: 'conversation_id', label: 'Conversation ID', type: 'text', required: true },
  ] },
  { type: 'ai.moderate', label: 'Moderate Content', category: 'AI', provider: 'ai', color: '#8b5cf6', description: 'Flag unsafe content before it goes further (input/output safety)', configFields: [
    { key: 'text', label: 'Text to Check', type: 'textarea', required: true },
  ] },

  // ── Human in the Loop ───────────────────────────────────────────────────────
  { type: 'approval.wait', label: 'Wait for Approval', category: 'Human in the Loop', provider: 'core', color: '#f59e0b', description: 'Pause the workflow until a human approves or rejects', configFields: [
    { key: 'prompt', label: 'What should the approver see?', type: 'textarea', required: true },
    { key: 'timeout_hours', label: 'Auto-expire after (hours, optional)', type: 'number' },
  ] },

  // ── Extended LLM Providers ─────────────────────────────────────────────────
  { type: 'llm.gemini', label: 'Google Gemini', category: 'LLM', provider: 'gemini', color: '#4285f4', description: 'Chat via Google Gemini API', configFields: [
    { key: 'model', label: 'Model', type: 'select', options: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash', 'gemini-2.5-pro'] },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
    { key: 'temperature', label: 'Temperature', type: 'number' },
  ] },
  { type: 'llm.ollama', label: 'Ollama (Local)', category: 'LLM', provider: 'ollama', color: '#7c3aed', description: 'Run local LLMs via Ollama', configFields: [
    { key: 'model', label: 'Model', type: 'text', placeholder: 'llama3', required: true },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'temperature', label: 'Temperature', type: 'number' },
  ] },
  { type: 'llm.huggingface', label: 'HuggingFace', category: 'LLM', provider: 'huggingface', color: '#ff9d00', description: 'HuggingFace Inference API', configFields: [
    { key: 'model', label: 'Model', type: 'text', placeholder: 'mistralai/Mistral-7B-Instruct-v0.3', required: true },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
    { key: 'temperature', label: 'Temperature', type: 'number' },
  ] },
  { type: 'llm.cohere', label: 'Cohere', category: 'LLM', provider: 'cohere', color: '#39594d', description: 'Chat via Cohere AI', configFields: [
    { key: 'model', label: 'Model', type: 'select', options: ['command-r-plus', 'command-r', 'command', 'command-light'] },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
  ] },
  { type: 'llm.mistral', label: 'Mistral AI', category: 'LLM', provider: 'mistral', color: '#ff7000', description: 'Chat via Mistral API', configFields: [
    { key: 'model', label: 'Model', type: 'select', options: ['mistral-large-latest', 'mistral-small-latest', 'open-mistral-7b', 'open-mixtral-8x7b'] },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
  ] },
  { type: 'llm.groq', label: 'Groq', category: 'LLM', provider: 'groq', color: '#f55036', description: 'Ultra-fast inference via Groq', configFields: [
    { key: 'model', label: 'Model', type: 'select', options: ['llama3-8b-8192', 'llama3-70b-8192', 'mixtral-8x7b-32768', 'gemma-7b-it'] },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
  ] },
  { type: 'llm.azure_openai', label: 'Azure OpenAI', category: 'LLM', provider: 'azure', color: '#0078d4', description: 'Azure-hosted OpenAI models', configFields: [
    { key: 'deployment', label: 'Deployment Name', type: 'text', placeholder: 'gpt-4o', required: true },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
    { key: 'temperature', label: 'Temperature', type: 'number' },
  ] },
  { type: 'llm.together_ai', label: 'Together AI', category: 'LLM', provider: 'azure', color: '#6366f1', description: 'Open-source models via Together AI', configFields: [
    { key: 'model', label: 'Model', type: 'text', placeholder: 'meta-llama/Llama-3-8b-chat-hf', required: true },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
  ] },
  { type: 'llm.perplexity', label: 'Perplexity', category: 'LLM', provider: 'groq', color: '#1fb8cd', description: 'Search-augmented AI via Perplexity', configFields: [
    { key: 'model', label: 'Model', type: 'select', options: ['llama-3.1-sonar-small-128k-online', 'llama-3.1-sonar-large-128k-online'] },
    { key: 'prompt', label: 'Prompt', type: 'textarea', required: true },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number' },
  ] },
  { type: 'llm.replicate', label: 'Replicate', category: 'LLM', provider: 'ollama', color: '#6366f1', description: 'Run any model on Replicate', configFields: [
    { key: 'model_version', label: 'Model Version (owner/model:sha256)', type: 'text', required: true },
    { key: 'prompt', label: 'Prompt', type: 'textarea' },
    { key: 'input', label: 'Input (JSON)', type: 'json' },
  ] },

  // ── Tool Nodes ─────────────────────────────────────────────────────────────
  { type: 'tool.calculator', label: 'Calculator', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'Evaluate arithmetic expressions safely', configFields: [
    { key: 'expression', label: 'Expression', type: 'text', required: true, placeholder: 'sqrt(144) + 2^10' },
  ] },
  { type: 'tool.current_datetime', label: 'Current Date/Time', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'Get current UTC date and time', configFields: [
    { key: 'format', label: 'Format', type: 'text', placeholder: 'YYYY-MM-DD HH:mm:ss' },
  ] },
  { type: 'tool.brave_search', label: 'Brave Search', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'Web search via Brave', configFields: [
    { key: 'query', label: 'Query', type: 'text', required: true },
    { key: 'count', label: 'Result Count', type: 'number', placeholder: '5' },
  ] },
  { type: 'tool.serp_api', label: 'Google Search (SerpAPI)', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'Google Search via SerpAPI', configFields: [
    { key: 'query', label: 'Query', type: 'text', required: true },
    { key: 'num', label: 'Results', type: 'number', placeholder: '5' },
  ] },
  { type: 'tool.duckduckgo_search', label: 'DuckDuckGo Search', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'DuckDuckGo instant answers (no key needed)', configFields: [
    { key: 'query', label: 'Query', type: 'text', required: true },
  ] },
  { type: 'tool.wikipedia', label: 'Wikipedia', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'Fetch Wikipedia article summaries', configFields: [
    { key: 'query', label: 'Topic', type: 'text', required: true },
    { key: 'sentences', label: 'Sentences', type: 'number', placeholder: '3' },
    { key: 'lang', label: 'Language', type: 'text', placeholder: 'en' },
  ] },
  { type: 'tool.arxiv', label: 'Arxiv Search', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'Search academic papers on Arxiv', configFields: [
    { key: 'query', label: 'Query', type: 'text', required: true },
    { key: 'max_results', label: 'Max Results', type: 'number', placeholder: '5' },
  ] },
  { type: 'tool.weather', label: 'Weather', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'Get current weather (OpenWeatherMap)', configFields: [
    { key: 'location', label: 'Location', type: 'text', required: true, placeholder: 'London, UK' },
    { key: 'units', label: 'Units', type: 'select', options: ['metric', 'imperial', 'standard'] },
  ] },
  { type: 'tool.tavily_search', label: 'Tavily Search', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'AI-optimized search via Tavily', configFields: [
    { key: 'query', label: 'Query', type: 'text', required: true },
    { key: 'max_results', label: 'Max Results', type: 'number', placeholder: '5' },
    { key: 'search_depth', label: 'Depth', type: 'select', options: ['basic', 'advanced'] },
  ] },
  { type: 'tool.exa_search', label: 'Exa Search', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'Neural web search via Exa', configFields: [
    { key: 'query', label: 'Query', type: 'text', required: true },
    { key: 'num_results', label: 'Results', type: 'number', placeholder: '5' },
  ] },
  { type: 'tool.code_interpreter', label: 'Code Interpreter', category: 'Tools', provider: 'tool', color: '#14b8a6', description: 'Execute Python code in a sandbox', configFields: [
    { key: 'code', label: 'Python Code', type: 'textarea', required: true },
  ] },
  { type: 'tool.aws_sns', label: 'AWS SNS', category: 'Tools', provider: 'aws_s3', color: '#ff9900', description: 'Publish to AWS SNS topic', configFields: [
    { key: 'topic_arn', label: 'Topic ARN', type: 'text', required: true },
    { key: 'message', label: 'Message', type: 'textarea', required: true },
    { key: 'subject', label: 'Subject', type: 'text' },
  ] },
  { type: 'tool.aws_dynamodb_kv', label: 'AWS DynamoDB KV', category: 'Tools', provider: 'aws_s3', color: '#ff9900', description: 'Key-value store on DynamoDB', configFields: [
    { key: 'table_name', label: 'Table Name', type: 'text', required: true },
    { key: 'operation', label: 'Operation', type: 'select', options: ['get', 'put', 'delete', 'scan'], required: true },
    { key: 'key', label: 'Key', type: 'text' },
    { key: 'item', label: 'Item (JSON, for put)', type: 'json' },
  ] },

  // ── Document Loaders ────────────────────────────────────────────────────────
  { type: 'loader.text', label: 'Text Loader', category: 'Document Loaders', provider: 'loader', color: '#0d9488', description: 'Wrap raw text as a document', configFields: [
    { key: 'text', label: 'Text', type: 'textarea', required: true },
    { key: 'chunk_size', label: 'Chunk Size (0=none)', type: 'number', placeholder: '0' },
  ] },
  { type: 'loader.json', label: 'JSON Loader', category: 'Document Loaders', provider: 'loader', color: '#0d9488', description: 'Parse JSON to documents', configFields: [
    { key: 'json', label: 'JSON Data', type: 'json' },
    { key: 'text_keys', label: 'Text Keys (JSON array)', type: 'json' },
    { key: 'pointer', label: 'JSON Pointer (e.g. /items)', type: 'text' },
  ] },
  { type: 'loader.csv', label: 'CSV Loader', category: 'Document Loaders', provider: 'loader', color: '#0d9488', description: 'Parse CSV rows to documents', configFields: [
    { key: 'content', label: 'CSV Content', type: 'textarea', required: true },
    { key: 'text_columns', label: 'Text Columns (JSON array)', type: 'json' },
  ] },
  { type: 'loader.pdf', label: 'PDF Loader', category: 'Document Loaders', provider: 'loader', color: '#0d9488', description: 'Extract text from a PDF', configFields: [
    { key: 'url', label: 'PDF URL', type: 'text' },
    { key: 'pdf_base64', label: 'PDF (Base64)', type: 'textarea' },
    { key: 'chunk_size', label: 'Chunk Size', type: 'number', placeholder: '1000' },
  ] },
  { type: 'loader.web_scrape', label: 'Web Scraper', category: 'Document Loaders', provider: 'loader', color: '#0d9488', description: 'Scrape text from a URL', configFields: [
    { key: 'url', label: 'URL', type: 'text', required: true },
    { key: 'selector', label: 'CSS Selector (optional)', type: 'text' },
    { key: 'chunk_size', label: 'Chunk Size', type: 'number', placeholder: '1000' },
  ] },
  { type: 'loader.sitemap', label: 'Sitemap Crawler', category: 'Document Loaders', provider: 'loader', color: '#0d9488', description: 'Crawl a sitemap and scrape pages', configFields: [
    { key: 'sitemap_url', label: 'Sitemap URL', type: 'text', required: true },
    { key: 'max_pages', label: 'Max Pages', type: 'number', placeholder: '20' },
  ] },
  { type: 'loader.github_repo', label: 'GitHub Repo Loader', category: 'Document Loaders', provider: 'github', color: '#24292e', description: 'Load files from a GitHub repo', configFields: [
    { key: 'repo', label: 'Repo (owner/name)', type: 'text', required: true },
    { key: 'branch', label: 'Branch', type: 'text', placeholder: 'main' },
    { key: 'file_patterns', label: 'File Patterns (JSON)', type: 'json', placeholder: '["*.py","*.md"]' },
  ] },
  { type: 'loader.youtube', label: 'YouTube Transcript', category: 'Document Loaders', provider: 'loader', color: '#ff0000', description: 'Load YouTube video transcript', configFields: [
    { key: 'url', label: 'YouTube URL', type: 'text' },
    { key: 'video_id', label: 'Video ID', type: 'text' },
    { key: 'chunk_size', label: 'Chunk Size', type: 'number', placeholder: '1000' },
  ] },
  { type: 'loader.notion_page', label: 'Notion Page Loader', category: 'Document Loaders', provider: 'notion', color: '#000000', description: 'Load a Notion page as documents', configFields: [
    { key: 'page_id', label: 'Page ID', type: 'text', required: true },
    { key: 'chunk_size', label: 'Chunk Size', type: 'number', placeholder: '1000' },
  ] },
  { type: 'loader.s3_file', label: 'S3 File Loader', category: 'Document Loaders', provider: 'aws_s3', color: '#ff9900', description: 'Load and parse a file from S3', configFields: [
    { key: 'bucket', label: 'Bucket', type: 'text', required: true },
    { key: 'key', label: 'S3 Key', type: 'text', required: true },
  ] },

  // ── Text Splitters ──────────────────────────────────────────────────────────
  { type: 'splitter.recursive_character', label: 'Recursive Splitter', category: 'Text Splitters', provider: 'splitter', color: '#6366f1', description: 'Recursive character splitting (LangChain-style)', configFields: [
    { key: 'text', label: 'Text', type: 'textarea' },
    { key: 'chunk_size', label: 'Chunk Size', type: 'number', placeholder: '1000' },
    { key: 'chunk_overlap', label: 'Overlap', type: 'number', placeholder: '200' },
  ] },
  { type: 'splitter.character', label: 'Character Splitter', category: 'Text Splitters', provider: 'splitter', color: '#6366f1', description: 'Split on a fixed separator', configFields: [
    { key: 'text', label: 'Text', type: 'textarea' },
    { key: 'separator', label: 'Separator', type: 'text', placeholder: '\\n\\n' },
    { key: 'chunk_size', label: 'Chunk Size', type: 'number', placeholder: '1000' },
  ] },
  { type: 'splitter.token', label: 'Token Splitter', category: 'Text Splitters', provider: 'splitter', color: '#6366f1', description: 'Split by token count', configFields: [
    { key: 'text', label: 'Text', type: 'textarea' },
    { key: 'chunk_tokens', label: 'Tokens per Chunk', type: 'number', placeholder: '256' },
    { key: 'chunk_overlap_tokens', label: 'Overlap Tokens', type: 'number', placeholder: '50' },
  ] },
  { type: 'splitter.markdown', label: 'Markdown Splitter', category: 'Text Splitters', provider: 'splitter', color: '#6366f1', description: 'Split Markdown at headers', configFields: [
    { key: 'text', label: 'Markdown Text', type: 'textarea' },
    { key: 'header_levels', label: 'Header Levels (JSON)', type: 'json', placeholder: '[1,2,3]' },
  ] },
  { type: 'splitter.code', label: 'Code Splitter', category: 'Text Splitters', provider: 'splitter', color: '#6366f1', description: 'Split code at function/class boundaries', configFields: [
    { key: 'text', label: 'Source Code', type: 'textarea' },
    { key: 'language', label: 'Language', type: 'select', options: ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'c', 'cpp'] },
    { key: 'chunk_size', label: 'Chunk Size', type: 'number', placeholder: '1500' },
  ] },
  { type: 'splitter.sentence', label: 'Sentence Splitter', category: 'Text Splitters', provider: 'splitter', color: '#6366f1', description: 'Split at sentence boundaries', configFields: [
    { key: 'text', label: 'Text', type: 'textarea' },
    { key: 'chunk_size', label: 'Chunk Size', type: 'number', placeholder: '1000' },
  ] },

  // ── Agent Nodes ─────────────────────────────────────────────────────────────
  { type: 'agent.react', label: 'ReAct Agent', category: 'Agents', provider: 'agent', color: '#7c3aed', description: 'Reason + Act agent with tool use loop', configFields: [
    { key: 'input', label: 'Question / Input', type: 'textarea', required: true },
    { key: 'tools', label: 'Tools (JSON array of node IDs)', type: 'json', placeholder: '["tool.calculator","tool.wikipedia"]' },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'max_iterations', label: 'Max Iterations', type: 'number', placeholder: '5' },
    { key: 'provider', label: 'Provider', type: 'select', options: ['auto', 'anthropic', 'openai'] },
    { key: 'model', label: 'Model', type: 'text' },
  ] },
  { type: 'agent.openai_function', label: 'Function Calling Agent', category: 'Agents', provider: 'agent', color: '#7c3aed', description: 'OpenAI native tool/function calling', configFields: [
    { key: 'input', label: 'Question', type: 'textarea', required: true },
    { key: 'tools', label: 'Tools (JSON array)', type: 'json' },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'model', label: 'Model', type: 'select', options: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'] },
    { key: 'max_iterations', label: 'Max Iterations', type: 'number', placeholder: '5' },
  ] },
  { type: 'agent.conversational', label: 'Conversational Agent', category: 'Agents', provider: 'agent', color: '#7c3aed', description: 'Stateful conversation with memory', configFields: [
    { key: 'input', label: 'User Message', type: 'textarea', required: true },
    { key: 'conversation_id', label: 'Conversation ID', type: 'text', placeholder: '{{ body.user_id }}' },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'model', label: 'Model', type: 'text' },
    { key: 'provider', label: 'Provider', type: 'select', options: ['auto', 'anthropic', 'openai'] },
  ] },
  { type: 'agent.sql', label: 'SQL Agent', category: 'Agents', provider: 'agent', color: '#7c3aed', description: 'Natural language to SQL', configFields: [
    { key: 'question', label: 'Question', type: 'textarea', required: true },
    { key: 'connection_string', label: 'Connection String (optional)', type: 'text' },
    { key: 'tables', label: 'Tables to Include (JSON array)', type: 'json' },
    { key: 'max_rows', label: 'Max Rows', type: 'number', placeholder: '100' },
  ] },
  { type: 'agent.chain_of_thought', label: 'Chain of Thought', category: 'Agents', provider: 'agent', color: '#7c3aed', description: 'Force step-by-step reasoning', configFields: [
    { key: 'input', label: 'Question', type: 'textarea', required: true },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea' },
    { key: 'model', label: 'Model', type: 'text' },
    { key: 'provider', label: 'Provider', type: 'select', options: ['auto', 'anthropic', 'openai'] },
  ] },
  { type: 'agent.supervisor', label: 'Supervisor Agent', category: 'Agents', provider: 'agent', color: '#7c3aed', description: 'Routes tasks to specialized worker agents', configFields: [
    { key: 'input', label: 'Task', type: 'textarea', required: true },
    { key: 'workers', label: 'Workers (JSON)', type: 'json', placeholder: '[{"name":"Search","description":"web search tasks","node_id":"agent.react"}]' },
  ] },

  // ── Zendesk ─────────────────────────────────────────────────────────────────
  { type: 'zendesk.create_ticket', label: 'Create Ticket', category: 'Zendesk', provider: 'zendesk', color: '#03363d', description: 'Open a Zendesk ticket', configFields: [
    { key: 'subject', label: 'Subject', type: 'text', required: true },
    { key: 'body', label: 'Description', type: 'textarea', required: true },
    { key: 'requester_email', label: 'Requester Email', type: 'text' },
    { key: 'priority', label: 'Priority', type: 'select', options: ['low', 'normal', 'high', 'urgent'] },
  ] },
  { type: 'zendesk.update_ticket', label: 'Update Ticket', category: 'Zendesk', provider: 'zendesk', color: '#03363d', description: 'Update a Zendesk ticket', configFields: [
    { key: 'ticket_id', label: 'Ticket ID', type: 'text', required: true },
    { key: 'status', label: 'Status', type: 'select', options: ['new', 'open', 'pending', 'hold', 'solved', 'closed'] },
    { key: 'priority', label: 'Priority', type: 'select', options: ['low', 'normal', 'high', 'urgent'] },
  ] },
  { type: 'zendesk.get_ticket', label: 'Get Ticket', category: 'Zendesk', provider: 'zendesk', color: '#03363d', description: 'Retrieve a Zendesk ticket', configFields: [
    { key: 'ticket_id', label: 'Ticket ID', type: 'text', required: true },
  ] },
  { type: 'zendesk.search', label: 'Search Zendesk', category: 'Zendesk', provider: 'zendesk', color: '#03363d', description: 'Search Zendesk resources', configFields: [
    { key: 'query', label: 'Query', type: 'text', required: true },
  ] },
  { type: 'zendesk.add_comment', label: 'Add Comment', category: 'Zendesk', provider: 'zendesk', color: '#03363d', description: 'Add comment to a ticket', configFields: [
    { key: 'ticket_id', label: 'Ticket ID', type: 'text', required: true },
    { key: 'body', label: 'Comment', type: 'textarea', required: true },
    { key: 'public', label: 'Public?', type: 'boolean' },
  ] },

  // ── Linear ──────────────────────────────────────────────────────────────────
  { type: 'linear.create_issue', label: 'Create Issue', category: 'Linear', provider: 'linear', color: '#5e6ad2', description: 'Create a Linear issue', configFields: [
    { key: 'title', label: 'Title', type: 'text', required: true },
    { key: 'team_id', label: 'Team ID', type: 'text', required: true },
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'priority', label: 'Priority (0-4)', type: 'number', placeholder: '2' },
  ] },
  { type: 'linear.update_issue', label: 'Update Issue', category: 'Linear', provider: 'linear', color: '#5e6ad2', description: 'Update a Linear issue', configFields: [
    { key: 'issue_id', label: 'Issue ID', type: 'text', required: true },
    { key: 'title', label: 'Title', type: 'text' },
    { key: 'stateId', label: 'State ID', type: 'text' },
    { key: 'priority', label: 'Priority', type: 'number' },
  ] },
  { type: 'linear.search_issues', label: 'Search Issues', category: 'Linear', provider: 'linear', color: '#5e6ad2', description: 'Search Linear issues', configFields: [
    { key: 'query', label: 'Search Term', type: 'text', required: true },
  ] },
  { type: 'linear.create_comment', label: 'Add Comment', category: 'Linear', provider: 'linear', color: '#5e6ad2', description: 'Comment on a Linear issue', configFields: [
    { key: 'issue_id', label: 'Issue ID', type: 'text', required: true },
    { key: 'body', label: 'Comment (Markdown)', type: 'textarea', required: true },
  ] },

  // ── Salesforce ──────────────────────────────────────────────────────────────
  { type: 'salesforce.query', label: 'SOQL Query', category: 'Salesforce', provider: 'salesforce', color: '#00a1e0', description: 'Query Salesforce with SOQL', configFields: [
    { key: 'soql', label: 'SOQL', type: 'textarea', required: true, placeholder: 'SELECT Id, Name FROM Lead LIMIT 10' },
  ] },
  { type: 'salesforce.create_lead', label: 'Create Lead', category: 'Salesforce', provider: 'salesforce', color: '#00a1e0', description: 'Create a Salesforce Lead', configFields: [
    { key: 'LastName', label: 'Last Name', type: 'text', required: true },
    { key: 'Company', label: 'Company', type: 'text', required: true },
    { key: 'Email', label: 'Email', type: 'text' },
    { key: 'Phone', label: 'Phone', type: 'text' },
    { key: 'LeadSource', label: 'Lead Source', type: 'text' },
  ] },
  { type: 'salesforce.create_contact', label: 'Create Contact', category: 'Salesforce', provider: 'salesforce', color: '#00a1e0', description: 'Create a Salesforce Contact', configFields: [
    { key: 'LastName', label: 'Last Name', type: 'text', required: true },
    { key: 'Email', label: 'Email', type: 'text' },
    { key: 'AccountId', label: 'Account ID', type: 'text' },
  ] },
  { type: 'salesforce.create_opportunity', label: 'Create Opportunity', category: 'Salesforce', provider: 'salesforce', color: '#00a1e0', description: 'Create a Salesforce Opportunity', configFields: [
    { key: 'Name', label: 'Name', type: 'text', required: true },
    { key: 'CloseDate', label: 'Close Date (YYYY-MM-DD)', type: 'text', required: true },
    { key: 'StageName', label: 'Stage', type: 'text', required: true },
    { key: 'Amount', label: 'Amount', type: 'number' },
  ] },

  // ── Confluence ──────────────────────────────────────────────────────────────
  { type: 'confluence.get_page', label: 'Get Page', category: 'Confluence', provider: 'confluence', color: '#172b4d', description: 'Retrieve a Confluence page', configFields: [
    { key: 'page_id', label: 'Page ID', type: 'text', required: true },
  ] },
  { type: 'confluence.create_page', label: 'Create Page', category: 'Confluence', provider: 'confluence', color: '#172b4d', description: 'Create a Confluence page', configFields: [
    { key: 'space_key', label: 'Space Key', type: 'text', required: true },
    { key: 'title', label: 'Title', type: 'text', required: true },
    { key: 'body', label: 'Body (HTML/Storage format)', type: 'textarea' },
    { key: 'parent_id', label: 'Parent Page ID', type: 'text' },
  ] },
  { type: 'confluence.search', label: 'Search', category: 'Confluence', provider: 'confluence', color: '#172b4d', description: 'Search Confluence with CQL', configFields: [
    { key: 'query', label: 'Search Query', type: 'text', required: true },
    { key: 'limit', label: 'Max Results', type: 'number', placeholder: '25' },
  ] },

  // ── Zoom ─────────────────────────────────────────────────────────────────────
  { type: 'zoom.create_meeting', label: 'Create Meeting', category: 'Zoom', provider: 'zoom', color: '#2d8cff', description: 'Schedule a Zoom meeting', configFields: [
    { key: 'topic', label: 'Topic', type: 'text', required: true },
    { key: 'start_time', label: 'Start Time (ISO)', type: 'text' },
    { key: 'duration', label: 'Duration (minutes)', type: 'number', placeholder: '60' },
    { key: 'timezone', label: 'Timezone', type: 'text', placeholder: 'UTC' },
  ] },
  { type: 'zoom.list_meetings', label: 'List Meetings', category: 'Zoom', provider: 'zoom', color: '#2d8cff', description: 'List Zoom meetings', configFields: [
    { key: 'type', label: 'Type', type: 'select', options: ['scheduled', 'live', 'upcoming'] },
  ] },

  // ── Monday.com ──────────────────────────────────────────────────────────────
  { type: 'monday.get_boards', label: 'Get Boards', category: 'Monday.com', provider: 'monday', color: '#ff3d57', description: 'List Monday.com boards', configFields: [
    { key: 'limit', label: 'Limit', type: 'number', placeholder: '10' },
  ] },
  { type: 'monday.create_item', label: 'Create Item', category: 'Monday.com', provider: 'monday', color: '#ff3d57', description: 'Add item to a board', configFields: [
    { key: 'board_id', label: 'Board ID', type: 'text', required: true },
    { key: 'name', label: 'Item Name', type: 'text', required: true },
    { key: 'column_values', label: 'Column Values (JSON)', type: 'json' },
  ] },
  { type: 'monday.create_update', label: 'Post Update', category: 'Monday.com', provider: 'monday', color: '#ff3d57', description: 'Post an update on an item', configFields: [
    { key: 'item_id', label: 'Item ID', type: 'text', required: true },
    { key: 'body', label: 'Update Text', type: 'textarea', required: true },
  ] },

  // ── Mailchimp ───────────────────────────────────────────────────────────────
  { type: 'mailchimp.add_member', label: 'Add Subscriber', category: 'Mailchimp', provider: 'mailchimp', color: '#ffe01b', description: 'Subscribe to a Mailchimp list', configFields: [
    { key: 'list_id', label: 'List ID', type: 'text', required: true },
    { key: 'email', label: 'Email', type: 'text', required: true },
    { key: 'first_name', label: 'First Name', type: 'text' },
    { key: 'last_name', label: 'Last Name', type: 'text' },
    { key: 'status', label: 'Status', type: 'select', options: ['subscribed', 'pending', 'unsubscribed'] },
  ] },
  { type: 'mailchimp.remove_member', label: 'Unsubscribe', category: 'Mailchimp', provider: 'mailchimp', color: '#ffe01b', description: 'Remove/unsubscribe from list', configFields: [
    { key: 'list_id', label: 'List ID', type: 'text', required: true },
    { key: 'email', label: 'Email', type: 'text', required: true },
  ] },

  // ── Freshdesk ───────────────────────────────────────────────────────────────
  { type: 'freshdesk.create_ticket', label: 'Create Ticket', category: 'Freshdesk', provider: 'freshdesk', color: '#25c16f', description: 'Create a Freshdesk ticket', configFields: [
    { key: 'subject', label: 'Subject', type: 'text', required: true },
    { key: 'description', label: 'Description', type: 'textarea' },
    { key: 'email', label: 'Requester Email', type: 'text' },
    { key: 'priority', label: 'Priority (1-4)', type: 'number', placeholder: '1' },
  ] },
  { type: 'freshdesk.reply_ticket', label: 'Reply to Ticket', category: 'Freshdesk', provider: 'freshdesk', color: '#25c16f', description: 'Reply to a Freshdesk ticket', configFields: [
    { key: 'ticket_id', label: 'Ticket ID', type: 'text', required: true },
    { key: 'body', label: 'Reply Body', type: 'textarea', required: true },
  ] },

  // ── Intercom ────────────────────────────────────────────────────────────────
  { type: 'intercom.create_contact', label: 'Create Contact', category: 'Intercom', provider: 'intercom', color: '#1f8ded', description: 'Create an Intercom contact', configFields: [
    { key: 'email', label: 'Email', type: 'text' },
    { key: 'name', label: 'Name', type: 'text' },
    { key: 'role', label: 'Role', type: 'select', options: ['user', 'lead'] },
  ] },
  { type: 'intercom.send_message', label: 'Send Message', category: 'Intercom', provider: 'intercom', color: '#1f8ded', description: 'Send in-app message to contact', configFields: [
    { key: 'contact_id', label: 'Contact ID', type: 'text', required: true },
    { key: 'body', label: 'Message', type: 'textarea', required: true },
    { key: 'message_type', label: 'Type', type: 'select', options: ['inapp', 'email'] },
  ] },
  { type: 'intercom.track_event', label: 'Track Event', category: 'Intercom', provider: 'intercom', color: '#1f8ded', description: 'Track a user event', configFields: [
    { key: 'contact_id', label: 'Contact ID', type: 'text', required: true },
    { key: 'event_name', label: 'Event Name', type: 'text', required: true },
    { key: 'metadata', label: 'Metadata (JSON)', type: 'json' },
  ] },

  // ── Typeform ────────────────────────────────────────────────────────────────
  { type: 'typeform.get_responses', label: 'Get Responses', category: 'Typeform', provider: 'typeform', color: '#262627', description: 'Fetch Typeform responses', configFields: [
    { key: 'form_id', label: 'Form ID', type: 'text', required: true },
    { key: 'page_size', label: 'Page Size', type: 'number', placeholder: '25' },
  ] },
  { type: 'typeform.list_forms', label: 'List Forms', category: 'Typeform', provider: 'typeform', color: '#262627', description: 'List all Typeform forms', configFields: [] },

  // ── Box ──────────────────────────────────────────────────────────────────────
  { type: 'box.list_folder', label: 'List Folder', category: 'Box', provider: 'box', color: '#0061d5', description: 'List Box folder contents', configFields: [
    { key: 'folder_id', label: 'Folder ID (0=root)', type: 'text', placeholder: '0' },
  ] },
  { type: 'box.upload_file', label: 'Upload File', category: 'Box', provider: 'box', color: '#0061d5', description: 'Upload a file to Box', configFields: [
    { key: 'name', label: 'Filename', type: 'text', required: true },
    { key: 'content', label: 'Content (text)', type: 'textarea' },
    { key: 'parent_id', label: 'Parent Folder ID', type: 'text', placeholder: '0' },
  ] },
  { type: 'box.search', label: 'Search Box', category: 'Box', provider: 'box', color: '#0061d5', description: 'Search Box files/folders', configFields: [
    { key: 'query', label: 'Query', type: 'text', required: true },
  ] },
  { type: 'box.share_link', label: 'Create Share Link', category: 'Box', provider: 'box', color: '#0061d5', description: 'Generate a Box share link', configFields: [
    { key: 'file_id', label: 'File/Folder ID', type: 'text', required: true },
    { key: 'item_type', label: 'Type', type: 'select', options: ['file', 'folder'] },
    { key: 'access', label: 'Access Level', type: 'select', options: ['open', 'company', 'collaborators'] },
  ] },

  // ── Dropbox ──────────────────────────────────────────────────────────────────
  { type: 'dropbox.list_folder', label: 'List Folder', category: 'Dropbox', provider: 'dropbox', color: '#0061fe', description: 'List Dropbox folder', configFields: [
    { key: 'path', label: 'Path (empty=root)', type: 'text' },
    { key: 'recursive', label: 'Recursive?', type: 'boolean' },
  ] },
  { type: 'dropbox.search', label: 'Search Files', category: 'Dropbox', provider: 'dropbox', color: '#0061fe', description: 'Search Dropbox files', configFields: [
    { key: 'query', label: 'Query', type: 'text', required: true },
    { key: 'path', label: 'Search in Path', type: 'text' },
  ] },
  { type: 'dropbox.create_shared_link', label: 'Create Shared Link', category: 'Dropbox', provider: 'dropbox', color: '#0061fe', description: 'Create a Dropbox sharing link', configFields: [
    { key: 'path', label: 'File/Folder Path', type: 'text', required: true },
    { key: 'visibility', label: 'Visibility', type: 'select', options: ['public', 'team_only', 'password'] },
  ] },

  // ── WooCommerce ─────────────────────────────────────────────────────────────
  { type: 'woocommerce.list_orders', label: 'List Orders', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'List WooCommerce orders with optional filters', configFields: [
    { key: 'status', label: 'Status', type: 'select', options: ['any', 'pending', 'processing', 'on-hold', 'completed', 'cancelled', 'refunded', 'failed', 'trash'] },
    { key: 'per_page', label: 'Per Page (max 100)', type: 'number', placeholder: '10' },
    { key: 'page', label: 'Page', type: 'number', placeholder: '1' },
  ] },
  { type: 'woocommerce.get_order', label: 'Get Order', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'Fetch a single WooCommerce order', configFields: [
    { key: 'order_id', label: 'Order ID', type: 'text', required: true },
  ] },
  { type: 'woocommerce.update_order', label: 'Update Order', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'Update a WooCommerce order status or notes', configFields: [
    { key: 'order_id', label: 'Order ID', type: 'text', required: true },
    { key: 'status', label: 'Status', type: 'select', options: ['pending', 'processing', 'on-hold', 'completed', 'cancelled', 'refunded', 'failed'] },
    { key: 'customer_note', label: 'Customer Note', type: 'textarea' },
  ] },
  { type: 'woocommerce.create_order', label: 'Create Order', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'Create a new WooCommerce order', configFields: [
    { key: 'order', label: 'Order (JSON)', type: 'json', required: true },
  ] },
  { type: 'woocommerce.list_products', label: 'List Products', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'List WooCommerce products', configFields: [
    { key: 'status', label: 'Status', type: 'select', options: ['any', 'draft', 'pending', 'private', 'publish'] },
    { key: 'search', label: 'Search', type: 'text' },
    { key: 'per_page', label: 'Per Page (max 100)', type: 'number', placeholder: '10' },
  ] },
  { type: 'woocommerce.get_product', label: 'Get Product', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'Fetch a single WooCommerce product', configFields: [
    { key: 'product_id', label: 'Product ID', type: 'text', required: true },
  ] },
  { type: 'woocommerce.create_product', label: 'Create Product', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'Create a new product in WooCommerce', configFields: [
    { key: 'product', label: 'Product (JSON)', type: 'json', required: true },
  ] },
  { type: 'woocommerce.update_product', label: 'Update Product', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'Update a WooCommerce product', configFields: [
    { key: 'product_id', label: 'Product ID', type: 'text', required: true },
    { key: 'name', label: 'Name', type: 'text' },
    { key: 'regular_price', label: 'Regular Price', type: 'text' },
    { key: 'stock_quantity', label: 'Stock Quantity', type: 'number' },
    { key: 'status', label: 'Status', type: 'select', options: ['draft', 'pending', 'private', 'publish'] },
  ] },
  { type: 'woocommerce.list_customers', label: 'List Customers', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'List WooCommerce customers', configFields: [
    { key: 'search', label: 'Search', type: 'text' },
    { key: 'email', label: 'Filter by Email', type: 'text' },
    { key: 'per_page', label: 'Per Page', type: 'number', placeholder: '10' },
  ] },
  { type: 'woocommerce.create_customer', label: 'Create Customer', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'Create a new WooCommerce customer', configFields: [
    { key: 'email', label: 'Email', type: 'text', required: true },
    { key: 'first_name', label: 'First Name', type: 'text' },
    { key: 'last_name', label: 'Last Name', type: 'text' },
  ] },
  { type: 'woocommerce.get_sales_report', label: 'Get Sales Report', category: 'WooCommerce', provider: 'woocommerce', color: '#7f54b3', description: 'Retrieve WooCommerce sales totals', configFields: [
    { key: 'period', label: 'Period', type: 'select', options: ['week', 'month', 'last_month', 'year'] },
    { key: 'date_min', label: 'Date Min (YYYY-MM-DD)', type: 'text' },
    { key: 'date_max', label: 'Date Max (YYYY-MM-DD)', type: 'text' },
  ] },

  // ── Webex ────────────────────────────────────────────────────────────────────
  { type: 'webex.send_message', label: 'Send Message', category: 'Webex', provider: 'webex', color: '#00bceb', description: 'Send a Webex message to a room or person', configFields: [
    { key: 'roomId', label: 'Room ID (or toPersonEmail)', type: 'text' },
    { key: 'toPersonEmail', label: 'To Person Email', type: 'text' },
    { key: 'text', label: 'Text', type: 'textarea' },
    { key: 'markdown', label: 'Markdown', type: 'textarea' },
  ] },
  { type: 'webex.list_rooms', label: 'List Rooms', category: 'Webex', provider: 'webex', color: '#00bceb', description: 'List Webex rooms the user belongs to', configFields: [
    { key: 'max', label: 'Max Results', type: 'number', placeholder: '20' },
    { key: 'type', label: 'Type', type: 'select', options: ['direct', 'group'] },
  ] },
  { type: 'webex.create_room', label: 'Create Room', category: 'Webex', provider: 'webex', color: '#00bceb', description: 'Create a new Webex room/space', configFields: [
    { key: 'title', label: 'Title', type: 'text', required: true },
    { key: 'teamId', label: 'Team ID (optional)', type: 'text' },
  ] },
  { type: 'webex.list_messages', label: 'List Messages', category: 'Webex', provider: 'webex', color: '#00bceb', description: 'List messages in a Webex room', configFields: [
    { key: 'roomId', label: 'Room ID', type: 'text', required: true },
    { key: 'max', label: 'Max Results', type: 'number', placeholder: '50' },
  ] },
  { type: 'webex.get_me', label: 'Get My Profile', category: 'Webex', provider: 'webex', color: '#00bceb', description: 'Fetch the authenticated Webex user profile', configFields: [] },
  { type: 'webex.list_people', label: 'Search People', category: 'Webex', provider: 'webex', color: '#00bceb', description: 'Search Webex users by email or name', configFields: [
    { key: 'email', label: 'Email', type: 'text' },
    { key: 'displayName', label: 'Display Name', type: 'text' },
  ] },
  { type: 'webex.create_meeting', label: 'Create Meeting', category: 'Webex', provider: 'webex', color: '#00bceb', description: 'Schedule a Webex meeting', configFields: [
    { key: 'title', label: 'Title', type: 'text', required: true },
    { key: 'start', label: 'Start (ISO 8601)', type: 'text', required: true },
    { key: 'end', label: 'End (ISO 8601)', type: 'text', required: true },
    { key: 'timezone', label: 'Timezone', type: 'text', placeholder: 'UTC' },
  ] },

  // ── RingCentral ─────────────────────────────────────────────────────────────
  { type: 'ringcentral.send_sms', label: 'Send SMS', category: 'RingCentral', provider: 'ringcentral', color: '#f36f23', description: 'Send an SMS via RingCentral', configFields: [
    { key: 'from', label: 'From (E.164)', type: 'text', required: true, placeholder: '+14155552671' },
    { key: 'to', label: 'To (E.164)', type: 'text', required: true, placeholder: '+19999999999' },
    { key: 'text', label: 'Message Text', type: 'textarea', required: true },
  ] },
  { type: 'ringcentral.list_messages', label: 'List Messages', category: 'RingCentral', provider: 'ringcentral', color: '#f36f23', description: 'List RingCentral message store entries', configFields: [
    { key: 'messageType', label: 'Type', type: 'select', options: ['SMS', 'Fax', 'VoiceMail', 'Pager', 'Text'] },
    { key: 'direction', label: 'Direction', type: 'select', options: ['Inbound', 'Outbound'] },
    { key: 'perPage', label: 'Per Page', type: 'number', placeholder: '20' },
  ] },
  { type: 'ringcentral.get_call_log', label: 'Get Call Log', category: 'RingCentral', provider: 'ringcentral', color: '#f36f23', description: 'Retrieve RingCentral call log records', configFields: [
    { key: 'dateFrom', label: 'Date From (ISO 8601)', type: 'text' },
    { key: 'dateTo', label: 'Date To (ISO 8601)', type: 'text' },
    { key: 'direction', label: 'Direction', type: 'select', options: ['Inbound', 'Outbound'] },
    { key: 'perPage', label: 'Per Page', type: 'number', placeholder: '20' },
  ] },
  { type: 'ringcentral.make_call', label: 'Make Call (Ring Out)', category: 'RingCentral', provider: 'ringcentral', color: '#f36f23', description: 'Initiate a 2-leg RingCentral call', configFields: [
    { key: 'from', label: 'From (E.164)', type: 'text', required: true },
    { key: 'to', label: 'To (E.164)', type: 'text', required: true },
  ] },
  { type: 'ringcentral.list_extensions', label: 'List Extensions', category: 'RingCentral', provider: 'ringcentral', color: '#f36f23', description: 'List all extensions in the account', configFields: [
    { key: 'status', label: 'Status', type: 'select', options: ['Enabled', 'Disabled', 'Frozen', 'NotActivated', 'Unassigned'] },
    { key: 'perPage', label: 'Per Page', type: 'number', placeholder: '100' },
  ] },
  { type: 'ringcentral.get_account_info', label: 'Get Account Info', category: 'RingCentral', provider: 'ringcentral', color: '#f36f23', description: 'Retrieve RingCentral account details', configFields: [] },
]

import { AGENTFLOW_NODES } from '../catalog/agentflow_nodes'

// Merge advanced agentflow nodes into the catalog
NODE_CATALOG.push(...AGENTFLOW_NODES)

export const CATEGORIES = [...new Set(NODE_CATALOG.map(n => n.category))]

export function getNodeDef(type: string): NodeDef | undefined {
  return NODE_CATALOG.find(n => n.type === type)
}