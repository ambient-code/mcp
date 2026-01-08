import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  type Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "child_process";

function getBaseUrl(): string {
  const url = process.env.ACP_BASE_URL;
  if (!url) {
    throw new Error("ACP_BASE_URL environment variable is required");
  }
  return url;
}

// Get token from oc whoami -t
async function getToken(): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn("oc", ["whoami", "-t"]);
    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`oc whoami -t failed: ${stderr || "unknown error"}`));
        return;
      }
      resolve(stdout.trim());
    });

    proc.on("error", (err) => {
      reject(new Error(`Failed to run oc: ${err.message}`));
    });
  });
}

// Make authenticated request to ACP
async function acpFetch(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const token = await getToken();
  const baseUrl = getBaseUrl();

  const headers = {
    Authorization: `Bearer ${token}`,
    "X-Forwarded-Access-Token": token,
    "Content-Type": "application/json",
    ...options.headers,
  };

  return fetch(`${baseUrl}${path}`, {
    ...options,
    headers,
  });
}

// Tool definitions
const tools: Tool[] = [
  {
    name: "acp_list_projects",
    description:
      "List all projects/namespaces available in the Ambient Code Platform",
    inputSchema: {
      type: "object",
      properties: {},
      required: [],
    },
  },
  {
    name: "acp_list_sessions",
    description: "List all agentic sessions in a project",
    inputSchema: {
      type: "object",
      properties: {
        project: {
          type: "string",
          description: "Project/namespace name (e.g., my-workspace)",
        },
      },
      required: ["project"],
    },
  },
  {
    name: "acp_get_session",
    description: "Get details of a specific agentic session",
    inputSchema: {
      type: "object",
      properties: {
        project: {
          type: "string",
          description: "Project/namespace name",
        },
        session: {
          type: "string",
          description: "Session name",
        },
      },
      required: ["project", "session"],
    },
  },
  {
    name: "acp_get_events",
    description:
      "Get recent events from an agentic session (non-streaming snapshot)",
    inputSchema: {
      type: "object",
      properties: {
        project: {
          type: "string",
          description: "Project/namespace name",
        },
        session: {
          type: "string",
          description: "Session name",
        },
        limit: {
          type: "number",
          description: "Maximum number of events to return (default: 50)",
        },
      },
      required: ["project", "session"],
    },
  },
  {
    name: "acp_whoami",
    description:
      "Check current OpenShift authentication status and cluster info",
    inputSchema: {
      type: "object",
      properties: {},
      required: [],
    },
  },
  {
    name: "acp_create_session",
    description: "Create a new agentic session in the Ambient Code Platform",
    inputSchema: {
      type: "object",
      properties: {
        project: {
          type: "string",
          description: "Project/namespace name (e.g., my-workspace)",
        },
        displayName: {
          type: "string",
          description: "Human-readable display name for the session",
        },
        prompt: {
          type: "string",
          description: "Initial prompt to send to the agent",
        },
        model: {
          type: "string",
          description: "LLM model to use (default: claude-sonnet-4-5)",
        },
        interactive: {
          type: "boolean",
          description: "Whether the session is interactive (default: true)",
        },
      },
      required: ["project", "displayName", "prompt"],
    },
  },
  {
    name: "acp_send_message",
    description: "Send a message to an existing agentic session",
    inputSchema: {
      type: "object",
      properties: {
        project: {
          type: "string",
          description: "Project/namespace name",
        },
        session: {
          type: "string",
          description: "Session name",
        },
        message: {
          type: "string",
          description: "Message to send to the agent",
        },
      },
      required: ["project", "session", "message"],
    },
  },
  {
    name: "acp_stop_session",
    description: "Stop a running agentic session",
    inputSchema: {
      type: "object",
      properties: {
        project: {
          type: "string",
          description: "Project/namespace name",
        },
        session: {
          type: "string",
          description: "Session name",
        },
      },
      required: ["project", "session"],
    },
  },
];

// Tool handlers
async function handleListProjects(): Promise<string> {
  const response = await acpFetch("/api/projects");

  if (!response.ok) {
    throw new Error(
      `Failed to list projects: ${response.status} ${response.statusText}`,
    );
  }

  const data = await response.json();
  return JSON.stringify(data, null, 2);
}

async function handleListSessions(project: string): Promise<string> {
  const response = await acpFetch(`/api/projects/${project}/agentic-sessions`);

  if (!response.ok) {
    throw new Error(
      `Failed to list sessions: ${response.status} ${response.statusText}`,
    );
  }

  const data = await response.json();
  return JSON.stringify(data, null, 2);
}

async function handleGetSession(
  project: string,
  session: string,
): Promise<string> {
  const response = await acpFetch(
    `/api/projects/${project}/agentic-sessions/${session}`,
  );

  if (!response.ok) {
    throw new Error(
      `Failed to get session: ${response.status} ${response.statusText}`,
    );
  }

  const data = await response.json();
  return JSON.stringify(data, null, 2);
}

async function handleGetEvents(
  project: string,
  session: string,
  _limit = 50,
): Promise<string> {
  // For non-streaming, we'll fetch the session status which includes recent activity
  // The SSE endpoint is for real-time streaming, not suitable for MCP tool response
  const response = await acpFetch(
    `/api/projects/${project}/agentic-sessions/${session}`,
  );

  if (!response.ok) {
    throw new Error(
      `Failed to get session events: ${response.status} ${response.statusText}`,
    );
  }

  const data = await response.json();

  // Return session state with conversation history if available
  const result = {
    session: data.metadata?.name,
    status: data.status,
    // Note: Full conversation history may be in S3 state, not directly accessible via API
    message:
      "For real-time events, use the SSE endpoint: GET /api/projects/{project}/agentic-sessions/{session}/agui/events",
  };

  return JSON.stringify(result, null, 2);
}

async function handleWhoami(): Promise<string> {
  return new Promise((resolve, reject) => {
    const proc = spawn("oc", ["whoami"]);
    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", async (code) => {
      if (code !== 0) {
        reject(new Error(`Not logged in: ${stderr || "unknown error"}`));
        return;
      }

      // Also get cluster info
      const clusterProc = spawn("oc", ["whoami", "--show-server"]);
      let clusterUrl = "";

      clusterProc.stdout.on("data", (data) => {
        clusterUrl += data.toString();
      });

      clusterProc.on("close", () => {
        const result = {
          user: stdout.trim(),
          cluster: clusterUrl.trim(),
          acpBaseUrl: getBaseUrl(),
        };
        resolve(JSON.stringify(result, null, 2));
      });

      clusterProc.on("error", () => {
        const result = {
          user: stdout.trim(),
          cluster: "unknown",
          acpBaseUrl: getBaseUrl(),
        };
        resolve(JSON.stringify(result, null, 2));
      });
    });

    proc.on("error", (err) => {
      reject(new Error(`Failed to run oc: ${err.message}`));
    });
  });
}

interface CreateSessionOptions {
  project: string;
  displayName: string;
  prompt: string;
  model?: string;
  interactive?: boolean;
}

async function handleCreateSession(
  options: CreateSessionOptions,
): Promise<string> {
  const {
    project,
    displayName,
    prompt,
    model = "claude-sonnet-4-5",
    interactive = true,
  } = options;

  const sessionName = `agentic-session-${Date.now()}`;

  const body = {
    displayName,
    initialPrompt: prompt,
    interactive,
    llmSettings: {
      model,
      temperature: 0.7,
      maxTokens: 0,
    },
  };

  const response = await acpFetch(`/api/projects/${project}/agentic-sessions`, {
    method: "POST",
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to create session: ${response.status} ${response.statusText} - ${errorText}`,
    );
  }

  const data = await response.json();

  return JSON.stringify(
    {
      success: true,
      session: data.metadata?.name || sessionName,
      displayName,
      project,
      status: data.status?.phase || "Creating",
      message: "Session created. Use acp_send_message to interact with it.",
    },
    null,
    2,
  );
}

async function handleSendMessage(
  project: string,
  session: string,
  message: string,
): Promise<string> {
  const body = {
    messages: [
      {
        role: "user",
        content: message,
      },
    ],
  };

  const response = await acpFetch(
    `/api/projects/${project}/agentic-sessions/${session}/agui/run`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to send message: ${response.status} ${response.statusText} - ${errorText}`,
    );
  }

  // The response may be SSE stream or JSON depending on endpoint
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("text/event-stream")) {
    // For SSE, we'll read a few events and return them
    const text = await response.text();
    const events = text
      .split("\n\n")
      .filter((e) => e.startsWith("data:"))
      .map((e) => {
        try {
          return JSON.parse(e.replace("data:", "").trim());
        } catch {
          return e;
        }
      });

    return JSON.stringify(
      {
        success: true,
        session,
        project,
        eventsReceived: events.length,
        events: events.slice(0, 10),
        message:
          "Message sent. Events are streaming. Use acp_get_session to check status.",
      },
      null,
      2,
    );
  }

  const data = await response.json();
  return JSON.stringify(
    {
      success: true,
      session,
      project,
      response: data,
    },
    null,
    2,
  );
}

async function handleStopSession(
  project: string,
  session: string,
): Promise<string> {
  const response = await acpFetch(
    `/api/projects/${project}/agentic-sessions/${session}/stop`,
    {
      method: "POST",
    },
  );

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Failed to stop session: ${response.status} ${response.statusText} - ${errorText}`,
    );
  }

  return JSON.stringify(
    {
      success: true,
      session,
      project,
      message: "Session stop requested. Use acp_get_session to verify status.",
    },
    null,
    2,
  );
}

// Main server setup
async function main() {
  const server = new Server(
    {
      name: "ambient-code-platform",
      version: "0.1.0",
    },
    {
      capabilities: {
        tools: {},
      },
    },
  );

  // List tools handler
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return { tools };
  });

  // Call tool handler
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    try {
      let result: string;

      switch (name) {
        case "acp_list_projects":
          result = await handleListProjects();
          break;

        case "acp_list_sessions":
          if (!args?.project) throw new Error("project is required");
          result = await handleListSessions(args.project as string);
          break;

        case "acp_get_session":
          if (!args?.project) throw new Error("project is required");
          if (!args?.session) throw new Error("session is required");
          result = await handleGetSession(
            args.project as string,
            args.session as string,
          );
          break;

        case "acp_get_events":
          if (!args?.project) throw new Error("project is required");
          if (!args?.session) throw new Error("session is required");
          result = await handleGetEvents(
            args.project as string,
            args.session as string,
            (args.limit as number) || 50,
          );
          break;

        case "acp_whoami":
          result = await handleWhoami();
          break;

        case "acp_create_session":
          if (!args?.project) throw new Error("project is required");
          if (!args?.displayName) throw new Error("displayName is required");
          if (!args?.prompt) throw new Error("prompt is required");
          result = await handleCreateSession({
            project: args.project as string,
            displayName: args.displayName as string,
            prompt: args.prompt as string,
            model: args.model as string | undefined,
            interactive: args.interactive as boolean | undefined,
          });
          break;

        case "acp_send_message":
          if (!args?.project) throw new Error("project is required");
          if (!args?.session) throw new Error("session is required");
          if (!args?.message) throw new Error("message is required");
          result = await handleSendMessage(
            args.project as string,
            args.session as string,
            args.message as string,
          );
          break;

        case "acp_stop_session":
          if (!args?.project) throw new Error("project is required");
          if (!args?.session) throw new Error("session is required");
          result = await handleStopSession(
            args.project as string,
            args.session as string,
          );
          break;

        default:
          throw new Error(`Unknown tool: ${name}`);
      }

      return {
        content: [{ type: "text", text: result }],
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text", text: `Error: ${message}` }],
        isError: true,
      };
    }
  });

  // Connect via stdio
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
