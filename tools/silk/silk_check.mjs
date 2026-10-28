import { readFile, writeFile } from 'node:fs/promises'
import { decode } from 'silk-wasm'
const [, , silkPath, outPcm] = process.argv
const data = await readFile(silkPath)
const res = await decode(data, 24000)
await writeFile(outPcm, Buffer.from(res.data))
console.log('decoded bytes', res.data.length, 'duration', res.duration)
