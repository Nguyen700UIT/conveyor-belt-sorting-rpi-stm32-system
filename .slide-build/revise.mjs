import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {PresentationFile,FileBlob} from 'file:///C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const dir='D:/UIT/ConveyorBelt/.slide-build';
const skill='C:/Users/nguye/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations';
const p=await PresentationFile.importPptx(await FileBlob.load('D:/UIT/ConveyorBelt/output/CE224_Bang_tai_phan_loai_qua_tac.pptx'));
const s=p.slides.items[4];
const edits=[
 ['Đã hoàn thành: fine-tune mô hình từ YOLOv26.','Đã fine-tune YOLOv26, nhưng nhận diện tắc chín còn hạn chế do chênh lệch dữ liệu.',316],
 ['Đã có ảnh dự đoán thử với nhãn green và damaged.','Khắc phục: bổ sung ảnh tắc chín, cân bằng dữ liệu và huấn luyện lại.',416],
 ['Bước tiếp theo: đánh giá mô hình và tích hợp hệ thống.','Bước tiếp theo: lập trình logic và firmware cho hệ thống.',524]
];
for(const [before,after,y] of edits){
 const shape=s.shapes.items.find(z=>String(z.text)===before);
 if(!shape)throw new Error('Không tìm thấy nội dung cần sửa: '+before);
 shape.text=after;
 shape.position={left:76,top:y,width:1120,height:94};
 shape.text.style={fontFamily:'Arial',fontSize:34,color:'#000000'};
}
s.speakerNotes.text+=' Cập nhật từ nhóm: mô hình chưa nhận diện tốt trái chín do chênh lệch dữ liệu giữa các loại. Hướng khắc phục đề xuất là thu thêm ảnh tắc chín, cân bằng dữ liệu và huấn luyện lại. Bước tiếp theo của nhóm là lập trình logic và firmware cho hệ thống.';
await fs.writeFile(`${dir}/revised-slide-5.png`,new Uint8Array(await(await s.export({format:'png',scale:1})).arrayBuffer()));
await(await PresentationFile.exportPptx(p)).save(`${dir}/revision-candidate.pptx`);
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const nativeLink=fs.link.bind(fs);
fs.link=async(a,b)=>{try{return await nativeLink(a,b);}catch(e){if(e.code!=='EPERM')throw e;return fs.copyFile(a,b,1);}};
console.log(await finalizePresentation({workspaceDir:'D:/UIT/ConveyorBelt',candidatePath:`${dir}/revision-candidate.pptx`,finalPath:'D:/UIT/ConveyorBelt/output/CE224_Bang_tai_phan_loai_qua_tac_v2.pptx',pythonExecutable:'C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],explicitTotalSlideCount:10,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],verifyArtifactToolImport:true,receiptPath:`${dir}/revision-validation.json`}));
