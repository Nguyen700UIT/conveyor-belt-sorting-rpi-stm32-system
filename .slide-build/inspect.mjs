import fs from 'node:fs/promises';
import {PresentationFile,FileBlob} from 'file:///C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const p=await PresentationFile.importPptx(await FileBlob.load('D:/Download/KTMT_KLTN_Phu luc 6_Mau bao cao bao ve.pptx'));
await fs.writeFile('D:/UIT/ConveyorBelt/.slide-build/source.json',(await p.inspect({select:'$.slides[*]',include:['id','index','elements.id','elements.text','elements.position','elements.style']})).ndjson);
await fs.writeFile('D:/UIT/ConveyorBelt/.slide-build/template.webp',new Uint8Array(await (await p.export({format:'webp',montage:true,scale:0.3})).arrayBuffer()));
console.log('done',p.slides.items.length);
for(const i of [0,3,13]) await fs.writeFile(`D:/UIT/ConveyorBelt/.slide-build/source-${i}.png`,new Uint8Array(await (await p.slides.items[i].export({format:'png',scale:1})).arrayBuffer()));
console.log('methods',Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides)),Object.getOwnPropertyNames(Object.getPrototypeOf(p.slides.items[0])));
