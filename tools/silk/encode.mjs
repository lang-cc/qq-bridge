// 用法: node encode.mjs <input.pcm> <sampleRate> <output.silk>
import { readFile, writeFile } from 'node:fs/promises'
import { encode } from 'silk-wasm'

const [, , input, rate, output] = process.argv
if (!input || !rate || !output) {
  console.error('usage: node encode.mjs <input.pcm> <sampleRate> <output.silk>')
  process.exit(2)
}

const pcm = await readFile(input)
const result = await encode(pcm, Number(rate))
await writeFile(output, Buffer.from(result.data))
console.log(`ok bytes=${result.data.length} duration=${result.duration}`)
