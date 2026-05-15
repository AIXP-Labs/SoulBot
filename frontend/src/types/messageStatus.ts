// Agent message status enum — single source of truth for the frontend.
//
// MUST be kept in sync with the Python constants in
//   src/soulbot/messaging/message_entry.py
//
// The cross-language consistency is enforced by the Python test:
//   tests/test_messaging/test_status_enum_sync.py
//
// To add or rename a status value, update BOTH this file AND
// message_entry.py, then re-run `pytest tests/test_messaging/`.

export const MESSAGE_STATUS = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  DELIVERED: 'delivered',
  FAILED: 'failed',
  CANCELLED: 'cancelled',
} as const

export type MessageStatus =
  (typeof MESSAGE_STATUS)[keyof typeof MESSAGE_STATUS]

export const ALL_MESSAGE_STATUSES: readonly MessageStatus[] = [
  MESSAGE_STATUS.PENDING,
  MESSAGE_STATUS.PROCESSING,
  MESSAGE_STATUS.DELIVERED,
  MESSAGE_STATUS.FAILED,
  MESSAGE_STATUS.CANCELLED,
]

export const MESSAGE_REPLY_MODE = {
  NONE: 'none',
  CALLBACK: 'callback',
} as const

export type MessageReplyMode =
  (typeof MESSAGE_REPLY_MODE)[keyof typeof MESSAGE_REPLY_MODE]
