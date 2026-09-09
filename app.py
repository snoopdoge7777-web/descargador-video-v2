{
  "errorMessage": "The service was not able to process your request",
  "errorDescription": "Error de proceso: ERROR: [youtube:tab] RD0mYBSayCsH0: Playlists that require authentication may not extract correctly without a successful webpage download. If you are not downloading private content, or your cookies are only for the first account and channel, pass \"--extractor-args youtubetab:skip=authcheck\" to skip this check",
  "errorDetails": {
    "rawErrorMessage": [
      "500 - \"{\\\"message\\\":\\\"Error de proceso: ERROR: [youtube:tab] RD0mYBSayCsH0: Playlists that require authentication may not extract correctly without a successful webpage download. If you are not downloading private content, or your cookies are only for the first account and channel, pass \\\\\\\"--extractor-args youtubetab:skip=authcheck\\\\\\\" to skip this check\\\",\\\"status\\\":\\\"error\\\"}\\n\""
    ],
    "httpCode": "500"
  },
  "n8nDetails": {
    "nodeName": "HTTP Request",
    "nodeType": "n8n-nodes-base.httpRequest",
    "nodeVersion": 4.5,
    "itemIndex": 0,
    "time": "9/9/2026, 22:47:38",
    "n8nVersion": "2.39.0 (Cloud)",
    "binaryDataMode": "filesystem",
    "stackTrace": [
      "NodeApiError: The service was not able to process your request",
      "    at ExecuteContext.execute (/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-nodes-base@file++++home+runner+_work+n8n+n8n+packages+nodes-base/node_modules/n8n-nodes-base/nodes/HttpRequest/V3/HttpRequestV3.node.ts:890:16)",
      "    at processTicksAndRejections (node:internal/process/task_queues:104:5)",
      "    at WorkflowExecute.executeNode (/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-core@file++++home+runner+_work+n8n+n8n+packages+core/node_modules/n8n-core/src/execution-engine/workflow-execute.ts:1125:8)",
      "    at WorkflowExecute.runNode (/usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-core@file++++home+runner+_work+n8n+n8n+packages+core/node_modules/n8n-core/src/execution-engine/workflow-execute.ts:1427:11)",
      "    at /usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-core@file++++home+runner+_work+n8n+n8n+packages+core/node_modules/n8n-core/src/execution-engine/workflow-execute.ts:2329:27",
      "    at /usr/local/lib/node_modules/n8n/node_modules/.pnpm/n8n-core@file++++home+runner+_work+n8n+n8n+packages+core/node_modules/n8n-core/src/execution-engine/workflow-execute.ts:2810:11"
    ]
  }
}
