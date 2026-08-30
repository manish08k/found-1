import type { NodeDef } from '../types/nodes'

const AGENTFLOW_COLOR = '#7c3aed'

export const AGENTFLOW_NODES: NodeDef[] = [
  {
    type: 'agentflow.planner',
    label: 'Task Planner',
    category: 'AgentFlow',
    provider: 'agent',
    color: AGENTFLOW_COLOR,
    description: 'LLM-based task planner that breaks goals into subtasks',
    configFields: [
      { key: 'provider', label: 'Provider', type: 'select', options: ['auto', 'anthropic', 'openai'] },
      { key: 'model', label: 'Model', type: 'text', placeholder: 'gpt-4o-mini' },
      { key: 'goal', label: 'Goal / Objective', type: 'textarea', required: true, placeholder: 'Build a landing page for...' },
      { key: 'context', label: 'Additional Context', type: 'textarea' },
      { key: 'max_subtasks', label: 'Max Subtasks', type: 'number' },
    ],
  },
  {
    type: 'agentflow.router',
    label: 'LLM Router',
    category: 'AgentFlow',
    provider: 'agent',
    color: AGENTFLOW_COLOR,
    description: 'Routes to different branches based on LLM decision',
    configFields: [
      { key: 'provider', label: 'Provider', type: 'select', options: ['auto', 'anthropic', 'openai'] },
      { key: 'model', label: 'Model', type: 'text' },
      { key: 'input', label: 'Input to Route', type: 'textarea', placeholder: '{{text}}' },
      { key: 'routes', label: 'Routes (JSON)', type: 'json', required: true, placeholder: '[{"name":"support","description":"Customer support queries"}]' },
    ],
  },
  {
    type: 'agentflow.memory_read',
    label: 'Memory Read',
    category: 'AgentFlow',
    provider: 'agent',
    color: AGENTFLOW_COLOR,
    description: 'Read agent conversation state from memory',
    configFields: [
      { key: 'conversation_id', label: 'Conversation ID', type: 'text', placeholder: '{{conversation_id}}' },
      { key: 'max_messages', label: 'Max Messages', type: 'number' },
      { key: 'role_filter', label: 'Role Filter', type: 'select', options: ['', 'user', 'assistant', 'system'] },
    ],
  },
  {
    type: 'agentflow.memory_write',
    label: 'Memory Write',
    category: 'AgentFlow',
    provider: 'agent',
    color: AGENTFLOW_COLOR,
    description: 'Write agent state to conversation memory',
    configFields: [
      { key: 'conversation_id', label: 'Conversation ID', type: 'text', placeholder: '{{conversation_id}}' },
      { key: 'role', label: 'Role', type: 'select', options: ['assistant', 'user', 'system'] },
      { key: 'content', label: 'Content', type: 'textarea', placeholder: '{{text}}' },
      { key: 'content_field', label: 'Or Content Field', type: 'text', placeholder: 'text' },
    ],
  },
  {
    type: 'agentflow.parallel_agents',
    label: 'Parallel Agents',
    category: 'AgentFlow',
    provider: 'agent',
    color: AGENTFLOW_COLOR,
    description: 'Run multiple agent nodes in parallel',
    configFields: [
      { key: 'agents', label: 'Agents (JSON)', type: 'json', required: true, placeholder: '[{"node_id":"ai.chat","name":"Researcher","config":{}}]' },
      { key: 'merge_strategy', label: 'Merge Strategy', type: 'select', options: ['merge', 'list'] },
      { key: 'timeout', label: 'Timeout (seconds)', type: 'number' },
    ],
  },
  {
    type: 'agentflow.sequential_agents',
    label: 'Sequential Agents',
    category: 'AgentFlow',
    provider: 'agent',
    color: AGENTFLOW_COLOR,
    description: 'Run agent nodes in sequence, chaining outputs',
    configFields: [
      { key: 'agents', label: 'Agents (JSON)', type: 'json', required: true, placeholder: '[{"node_id":"ai.chat","name":"Step 1","config":{}}]' },
      { key: 'stop_on_error', label: 'Stop on Error', type: 'boolean' },
    ],
  },
  {
    type: 'agentflow.tool_caller',
    label: 'Tool Caller',
    category: 'AgentFlow',
    provider: 'agent',
    color: AGENTFLOW_COLOR,
    description: 'Call a registered tool with LLM-generated arguments',
    configFields: [
      { key: 'provider', label: 'Provider', type: 'select', options: ['auto', 'anthropic', 'openai'] },
      { key: 'model', label: 'Model', type: 'text' },
      { key: 'tool_name', label: 'Tool Node ID', type: 'text', required: true, placeholder: 'tool.calculator' },
      { key: 'task', label: 'Task Description', type: 'textarea', required: true, placeholder: 'Calculate the total for {{items}}' },
      { key: 'tool_schema', label: 'Tool Input Schema (JSON)', type: 'json' },
    ],
  },
]
