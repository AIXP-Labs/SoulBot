// SoulBot API types

export interface Session {
  id: string
  app_name: string
  user_id: string
  agent_name: string
  last_agent: string | null
  title: string | null
  created_at: number
  last_update_time: number
}

export interface SessionDetail extends Session {
  state: Record<string, unknown>
  events: AgentEvent[]
}

export interface AgentEvent {
  author: string
  timestamp?: number
  content?: {
    parts?: EventPart[]
  }
  actions?: {
    transfer_to_agent?: string
  }
  partial?: boolean
  error_code?: string
  error_message?: string
}

export interface EventPart {
  text?: string
  function_call?: {
    name: string
    args: Record<string, unknown>
  }
  function_response?: {
    name: string
    response: unknown
  }
}

export interface AgentInfo {
  name: string
  description: string
  sub_agents: string[]
}

export interface TemplateInfo {
  name: string
  description: string
}

export interface CreateAgentRequest {
  name: string
  template: string
}

export interface AisopInfo {
  path: string
  group: string | null
  name: string
  version: string
  summary: string
  protocol: string
  tools: string[]
}

// AISP skill (single-folder unit). Distinct from AisopInfo: no group/tools,
// carries risk_level + when_to_use from the aisp_contract (doc 06).
export interface AispInfo {
  id: string
  path: string
  name: string
  version: string
  summary: string
  protocol: string
  risk_level: string
  when_to_use: string[]
}

export interface StoreProgram {
  id: string      // directory name incl. _aiap — what download/install need
  name: string
  version: string
  pattern: string
  summary: string
  tools: string[]
  quality_grade: string
  quality_score: number
  trust_level: string
  module_count: number
  github_url: string
  local_version: string   // version already in local aiap_store ('' if none)
}

// AISP skill from a GitHub store's aisp_store/ (doc 07)
export interface StoreSkill {
  id: string
  name: string
  version: string
  summary: string
  protocol: string
  risk_level: string
  when_to_use: string[]
  github_url: string
  local_version: string   // version already in local aisp_store ('' if none)
}

export interface ScheduleEntry {
  id: string
  trigger_config: {
    type: string
    delay?: number
    interval?: number
    cron?: string
    hour?: number
    minute?: number
    run_at?: string
  }
  aisop?: Array<{ role: string; content: Record<string, unknown> }>
  task?: Record<string, unknown>
  status: string
  origin_channel?: string
  origin_user?: string
  from_agent: string
  to_agent: string
  created_at: string
  last_run: string | null
  run_count: number
  last_result: string | null
  last_error: string | null
}

// Agent-to-agent message (Doc 08)
import type { MessageReplyMode, MessageStatus } from './messageStatus'

export interface AgentMessageEntry {
  id: string
  from_agent: string
  to_agent: string
  aisop: unknown[]
  status: MessageStatus
  reply_mode: MessageReplyMode
  parent_id: string | null
  depth: number
  created_at: string
  delivered_at: string | null
  result: string | null
  error: string | null
}

export interface AgentMessageListResponse {
  entries: AgentMessageEntry[]
  count: number
}

export {
  ALL_MESSAGE_STATUSES,
  MESSAGE_REPLY_MODE,
  MESSAGE_STATUS,
} from './messageStatus'
export type { MessageReplyMode, MessageStatus } from './messageStatus'
