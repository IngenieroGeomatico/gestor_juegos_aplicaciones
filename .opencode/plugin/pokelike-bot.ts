import { Plugin } from "@opencode/plugin"
import * as path from "node:path"
import { execFile } from "node:child_process"

const RAIZ = path.resolve(import.meta.dirname, "..", "..")
const SCRIPT = path.join(RAIZ, "juegos/pokelike/scripts/jugar_pokelike.py")

type Resumen = {
  resultado: string
  pasos: number
  insignias: number
  equipo: { n: string; lv: number; ps: number }[]
}

type Entrada = {
  region?: string
  max_pasos?: number
  reset?: boolean
  headful?: boolean
}

/**
 * Lanza el bot de Python y devuelve todo lo que escriba.
 *
 * `execFile` en vez de una shell: no hay interpolación, y el `maxBuffer` alto
 * es obligatorio porque una run larga imprime miles de líneas antes del JSON.
 */
function lanzar(
  args: string[],
  signal?: AbortSignal,
): Promise<{ salida: string; codigo: number | null }> {
  return new Promise((resolve) => {
    execFile(
      "uv",
      args,
      { cwd: RAIZ, maxBuffer: 64 * 1024 * 1024, signal },
      (error, stdout, stderr) => {
        const codigo =
          error && typeof (error as NodeJS.ErrnoException).code === "number"
            ? ((error as NodeJS.ErrnoException).code as unknown as number)
            : error
              ? null
              : 0
        resolve({ salida: `${stdout}${stderr}`, codigo })
      },
    )
  })
}

/**
 * Tool que delega el juego al bot autónomo de Python.
 *
 * El bot imprime un log paso a paso y termina con un JSON. Aquí solo se
 * devuelve ese JSON: el LLM no necesita ver cientos de líneas de progreso, y
 * así la run entera cuesta un único turno en vez de uno por clic.
 */
export default Plugin.define({
  id: "pokelike-bot",
  async setup(ctx) {
    await ctx.tool.transform((editor) => {
      editor.add({
        name: "pokelike_bot",
        description:
          "Juega una run de Pokelike Story de forma autónoma con el bot de Python. " +
          "Devuelve el resultado (CAMPEON, GAME_OVER, ATASCADO o PRESUPUESTO_AGOTADO), " +
          "las insignias y el equipo final. No hace falta guiar la partida paso a paso: " +
          "las decisiones las toma el bot.",
        input: {
          type: "object",
          properties: {
            region: {
              type: "string",
              description: "Región, p. ej. 'Kanto'. Por defecto 'Kanto'.",
            },
            max_pasos: {
              type: "number",
              description:
                "Presupuesto de pasos. 400 es una partida corta (~15-20 min). " +
                "0 = sin límite. Por defecto 400.",
            },
            reset: {
              type: "boolean",
              description:
                "true = partida nueva desde cero con perfil temporal. " +
                "false (por defecto) = continuar la run guardada.",
            },
            headful: {
              type: "boolean",
              description: "true = abrir el navegador visible para depurar.",
            },
          },
          additionalProperties: false,
        },
        execute: async (bruto, context) => {
          const entrada = (bruto ?? {}) as Entrada
          const args = [
            "run",
            "--group",
            "dev",
            "python",
            SCRIPT,
            "--region",
            entrada.region?.trim() || "Kanto",
            "--max-pasos",
            String(entrada.max_pasos ?? 400),
          ]
          if (entrada.reset) args.push("--reset")
          if (entrada.headful) args.push("--headful")

          let salida: string
          let codigo: number | null
          try {
            ({ salida, codigo } = await lanzar(args, context.signal))
          } catch (error) {
            return {
              content: `No se pudo lanzar el bot: ${(error as Error).message}`,
            }
          }

          // El bot escribe mucho log antes del resumen; se queda solo con el JSON.
          const desde = salida.lastIndexOf("\n{")
          const trozo = desde >= 0 ? salida.slice(desde + 1) : salida.trim()

          let d: Resumen
          try {
            d = JSON.parse(trozo) as Resumen
          } catch {
            const ultimas = salida.trim().split("\n").slice(-15).join("\n")
            return {
              content:
                `No se pudo leer el resumen del bot (código ${codigo}).\n\n` +
                `Últimas líneas:\n${ultimas}`,
            }
          }

          const equipo = d.equipo.map((m) => `${m.n} Lv${m.lv} ${m.ps}%`).join(", ")
          return {
            content:
              `resultado: ${d.resultado}\n` +
              `pasos: ${d.pasos} | insignias: ${d.insignias}\n` +
              `equipo: ${equipo || "(vacío)"}`,
          }
        },
      })
    })
  },
})
