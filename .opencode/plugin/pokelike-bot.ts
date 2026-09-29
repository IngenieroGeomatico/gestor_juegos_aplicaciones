import { tool as defineTool, type Plugin } from "@opencode-ai/plugin"
import * as path from "node:path"

const RAIZ = path.resolve(import.meta.dirname, "..", "..")
const SCRIPT = "juegos/pokelike/scripts/jugar_pokelike.py"

type Resumen = {
  resultado: string
  pasos: number
  insignias: number
  equipo: { n: string; lv: number; ps: number }[]
}

/**
 * Tool que delega el juego al bot autónomo de Python.
 *
 * El bot imprime un log paso a paso y termina con un JSON. Aquí solo se
 * devuelve ese JSON: el LLM no necesita ver cientos de líneas de progreso, y
 * así la run entera cuesta un único turno en vez de uno por clic.
 */
const PokelikeBot: Plugin = async ({ $ }) => ({
  tool: {
    pokelike_bot: defineTool({
      description:
        "Juega una run de Pokelike Story de forma autónoma con el bot de Python. " +
        "Devuelve el resultado (CAMPEON, GAME_OVER, ATASCADO o PRESUPUESTO_AGOTADO), " +
        "las insignias y el equipo final. No hace falta guiar la partida paso a paso: " +
        "las decisiones las toma el bot.",
      args: {
        region: defineTool.schema
          .string()
          .optional()
          .describe("Región, p. ej. 'Kanto'. Por defecto 'Kanto'."),
        max_pasos: defineTool.schema
          .number()
          .optional()
          .describe(
            "Presupuesto de pasos. 400 es una partida corta (~15-20 min). Por defecto 400.",
          ),
        reset: defineTool.schema
          .boolean()
          .optional()
          .describe(
            "true = partida nueva desde cero con perfil temporal. " +
              "false (por defecto) = continuar la run guardada.",
          ),
        headful: defineTool.schema
          .boolean()
          .optional()
          .describe("true = abrir el navegador visible para depurar."),
      },
      async execute(args) {
        const flags: string[] = [
          "--group",
          "dev",
          "run",
          "python",
          SCRIPT,
          "--region",
          args.region?.trim() || "Kanto",
          "--max-pasos",
          String(args.max_pasos ?? 400),
        ]
        if (args.reset) flags.push("--reset")
        if (args.headful) flags.push("--headful")

        let salida: string
        let codigo: number | null
        try {
          const proc = await $`cd ${RAIZ} && uv ${flags}`.nothrow()
          salida = proc.stdout.toString() + proc.stderr.toString()
          codigo = proc.exitCode
        } catch (error) {
          return {
            title: "Pokelike",
            output: `No se pudo lanzar el bot: ${(error as Error).message}`,
            metadata: { ok: false },
          }
        }

        // El bot escribe mucho log antes del resumen; se queda solo con el JSON.
        const desde = salida.lastIndexOf("\n{")
        const bruto = desde >= 0 ? salida.slice(desde + 1) : salida.trim()

        let d: Resumen
        try {
          d = JSON.parse(bruto) as Resumen
        } catch {
          const ultimas = salida.trim().split("\n").slice(-15).join("\n")
          return {
            title: "Pokelike",
            output:
              `No se pudo leer el resumen del bot (código ${codigo}).\n\n` +
              `Últimas líneas:\n${ultimas}`,
            metadata: { ok: false, exitCode: codigo },
          }
        }

        const equipo = d.equipo.map((m) => `${m.n} Lv${m.lv} ${m.ps}%`).join(", ")
        return {
          title: `Pokelike: ${d.resultado}`,
          output:
            `resultado: ${d.resultado}\n` +
            `pasos: ${d.pasos} | insignias: ${d.insignias}\n` +
            `equipo: ${equipo || "(vacío)"}`,
          metadata: { ok: d.resultado === "CAMPEON", resultado: d.resultado },
        }
      },
    }),
  },
})

export default PokelikeBot
