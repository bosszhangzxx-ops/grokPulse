// grokbot-kit opencode plugin for opencode 1
// Plugin do opencode instalado por `grokbot-kit install opencode`, que troca __GROKBOT_KIT_EXE__ pelo caminho
// absoluto do executável (door 6). Fora de uma task (sem GROKBOT_KIT_TASK_ID no ambiente) não faz nada e não chama
// o grokbot-kit. Dentro de uma task, repassa `permission.asked` e `question.asked` a `grokbot-kit emit --from
// opencode` como `{type, properties, parentID}` (door 14); o `emit` descarta permissões de sessões filhas (AC 55).
import { spawnSync } from "node:child_process"

const GROKBOT_KIT = "__GROKBOT_KIT_EXE__"
const ASKED: Record<string, string> = {
  "permission.asked": "permission.asked",
  "permission.v2.asked": "permission.asked",
  "question.asked": "question.asked",
  "question.v2.asked": "question.asked",
}

async function parentOf(client: any, sessionID: unknown): Promise<string | null> {
  if (typeof sessionID !== "string" || !client?.session?.get) return null
  try {
    const found = await client.session.get({ path: { id: sessionID } })
    const session = found?.data ?? found
    return typeof session?.parentID === "string" && session.parentID ? session.parentID : null
  } catch {
    return null
  }
}

export const GrokbotKit = async ({ client }: { client: any }) => {
  if (!process.env.GROKBOT_KIT_TASK_ID) return {}
  return {
    event: async ({ event }: { event: { type: string; properties?: Record<string, unknown> } }) => {
      const type = ASKED[event.type]
      if (!type) return
      const properties: Record<string, unknown> = { ...(event.properties ?? {}) }
      if (event.type === "permission.v2.asked") {
        properties.permission ??= properties.action
        properties.patterns ??= properties.resources
      }
      const parentID = await parentOf(client, properties.sessionID)
      spawnSync(GROKBOT_KIT, ["emit", "--from", "opencode"], {
        input: JSON.stringify({ type, properties, parentID }),
        stdio: ["pipe", "ignore", "ignore"],
        timeout: 30000,
      })
    },
  }
}
