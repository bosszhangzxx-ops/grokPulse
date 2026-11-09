// grokbot-kit opencode plugin for opencode 2
// Plugin do opencode 2.x instalado por `grokbot-kit install opencode`, que troca __GROKBOT_KIT_EXE__ pelo caminho
// absoluto do executável (door 6). O opencode 2.x só carrega `export default { id, setup }` (door 5 da
// needs-input-reply). Fora de uma task (sem GROKBOT_KIT_TASK_ID no ambiente) não registra nada. Dentro de uma task,
// cada permissão que o opencode deixaria em `ask` numa sessão raiz vai a `grokbot-kit emit --from opencode` como
// `{type: "permission.asked", properties, parentID}` (door 14), com GROKBOT_KIT_REPLY=1 (door 8); a decisão que o
// `emit` devolve (`{"effect", "message"}`, door 6) vira o `effect` do pedido. Sem decisão, o `opencode run` nega.
// Sem sintaxe só de TypeScript: os testes importam este arquivo no node.
import { spawn } from "node:child_process"
import { readFileSync } from "node:fs"
import { join } from "node:path"

const GROKBOT_KIT = "__GROKBOT_KIT_EXE__"
const GRACE_SECONDS = 60

function askWaitSeconds() {
  try {
    const meta = JSON.parse(readFileSync(join(process.env.GROKBOT_KIT_TASK_DIR ?? "", "meta.json"), "utf8"))
    return Number.isInteger(meta.ask_wait_seconds) && meta.ask_wait_seconds > 0 ? meta.ask_wait_seconds : 0
  } catch {
    return 0
  }
}

async function parentOf(ctx, sessionID) {
  try {
    const session = await ctx.session.get({ sessionID })
    return typeof session?.parentID === "string" && session.parentID ? session.parentID : null
  } catch {
    return null
  }
}

// o `emit` espera a resposta do bot: o processo do opencode não pode ficar bloqueado nesse tempo
function emit(input) {
  return new Promise((resolve) => {
    let out = ""
    let child
    try {
      child = spawn(GROKBOT_KIT, ["emit", "--from", "opencode"], {
        stdio: ["pipe", "pipe", "ignore"],
        env: { ...process.env, GROKBOT_KIT_REPLY: "1" },
        timeout: (askWaitSeconds() + GRACE_SECONDS) * 1000,
        killSignal: "SIGKILL",
      })
    } catch {
      resolve(null)
      return
    }
    child.stdout.on("data", (chunk) => {
      out += chunk
    })
    child.on("error", () => resolve(null))
    child.on("close", (code) => resolve(code === 0 ? out : null))
    child.stdin.on("error", () => {})
    child.stdin.end(JSON.stringify(input))
  })
}

function decision(out) {
  try {
    const parsed = JSON.parse(out ?? "")
    if (parsed?.effect === "allow" || parsed?.effect === "deny") return parsed
  } catch {}
  return null
}

export default {
  id: "grokbot-kit",
  setup: async (ctx) => {
    if (!process.env.GROKBOT_KIT_TASK_ID) return
    await ctx.permission.hook("evaluate", async (event) => {
      if (event.effect !== "ask") return
      const parentID = await parentOf(ctx, event.sessionID)
      if (parentID) return
      const properties = {
        ...(event.metadata ?? {}),
        sessionID: event.sessionID,
        permission: event.action,
        patterns: [...(event.resources ?? [])],
        id: event.source?.id ?? null,
      }
      const answer = decision(await emit({ type: "permission.asked", properties, parentID: null }))
      if (!answer) return
      event.effect = answer.effect
      if (answer.effect === "deny" && typeof answer.message === "string") event.message = answer.message
    })
  },
}
