import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {PresentationFile,FileBlob} from 'file:///C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
const dir='D:/UIT/ConveyorBelt/.slide-build';
const skill='C:/Users/nguye/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations';
const sourcePath='D:/Download/KTMT_KLTN_Phu luc 6_Mau bao cao bao ve.pptx';
const p=await PresentationFile.importPptx(await FileBlob.load(sourcePath));
const original=[...p.slides.items];
const slides=[original[0].duplicate(),...Array.from({length:8},()=>original[3].duplicate()),original[13].duplicate()];
for(const s of original)s.delete();
slides.forEach((s,i)=>s.moveTo(i));
function text(s,value,x,y,w,h,size=32,color='#000000',bold=false,font='Arial',align='left'){
 const z=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 z.text=value;z.text.style={fontFamily:font,fontSize:size,color,bold,alignment:align};return z;
}
function clean(s,i){
 const shapes=[...s.shapes.items];
 for(const z of shapes){
  const t=String(z.text??'');
  if(t.includes('Copyrights')){z.position={left:444.47,top:667.33,width:432,height:38.33};}
  else if(/^\d+$/.test(t.trim()) && z.position.width===288){z.text=String(i+1); z.position={left:1208,top:i===9?34.89:667.33,width:58,height:38.33};}
 }
}
function content(i,title,lines){
 const s=slides[i];clean(s,i);
 const a=[...s.shapes.items];a[0].text=title;
 a[0].text.style={fontFamily:'Times New Roman',fontSize:58.67,bold:true,color:'#00A65A'};
 a[1].text='';
 lines.forEach((v,j)=>text(s,v,76,228+j*88,1120,76,34));
 return s;
}
// Cover keeps the supplied logos, border, background, and title frame.
const cover=slides[0];
const c=cover.shapes.items;
c[0].text='HỆ THỐNG BĂNG TẢI\nPHÂN LOẠI QUẢ TẮC';
c[0].text.style={fontFamily:'Times New Roman',fontSize:55,bold:true,color:'#15C58B',alignment:'center'};
c[2].text='BÁO CÁO TIẾN ĐỘ CE224';c[2].position={left:391.63,top:127.83,width:410,height:40};
c[3].text='';
text(cover,'Thiết kế hệ thống nhúng – CE224',169,396,940,52,34,'#029676',true);
text(cover,'Giảng viên giảng dạy: Phạm Quốc Hùng',169,466,960,52,32);
text(cover,'Phân loại theo trạng thái: sống, chín và hư',169,540,960,52,30);
content(1,'1. Giới thiệu dự án',[
 'Băng tải đưa từng quả tắc qua camera.',
 'Mô hình nhận diện tắc sống, tắc chín và tắc hư.',
 'Servo gạt quả vào hộp theo kết quả phân loại.',
 'Mục tiêu: giảm phân loại thủ công, thống kê theo ngày.'
]);
content(2,'2. Các phần chính của hệ thống',[
 'Raspberry Pi 5: xử lý ảnh bằng mô hình YOLOv26.',
 'STM32: nhận kết quả từ Pi 5 qua UART và CP2102.',
 '2 cảm biến E3F-DS30C4 và 2 servo MG90S: gạt đúng vị trí.',
 'BTS7960 điều khiển động cơ băng tải JGB37 545.'
]);
content(3,'3. Cách hệ thống hoạt động',[
 '1. Camera ghi hình quả tắc trên băng tải.',
 '2. Pi 5 phân loại khi quả đi đến vùng gửi kết quả.',
 '3. STM32 nhận lệnh, chờ cảm biến báo quả đến vị trí gạt.',
 '4. Quả đạt chuẩn đi thẳng. Quả cần tách được servo gạt.'
]);
content(4,'4. Tiến độ hiện tại',[
 'Đang thực hiện: thu thập và bổ sung ảnh quả tắc.',
 'Đã hoàn thành: fine-tune mô hình từ YOLOv26.',
 'Đã có ảnh dự đoán thử với nhãn green và damaged.',
 'Bước tiếp theo: đánh giá mô hình và tích hợp hệ thống.'
]);
content(5,'5. Công việc với dữ liệu',[
 'Tiếp tục thu ảnh cho đủ 3 nhóm: sống, chín và hư.',
 'Bổ sung ảnh ở nhiều góc nhìn và điều kiện ánh sáng.',
 'Rà soát nhãn, tách ảnh huấn luyện và ảnh kiểm tra.',
 'Theo dõi trường hợp nhầm giữa tắc chín và tắc hư.'
]);
async function image(s,id,x,y,w,h){
 const file=`C:/Users/nguye/AppData/Local/Temp/codex-clipboard-${id}.png`;
 const b=await fs.readFile(file);s.images.add({blob:b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),contentType:'image/png',alt:'Ảnh dự đoán do nhóm cung cấp',fit:'contain',position:{left:x,top:y,width:w,height:h}});
}
const g=content(6,'6. Ví dụ nhận diện tắc sống',[]);
await image(g,'38ad6b88-76b0-45b6-88b8-db0003a6feb8',72,226,360,280);
await image(g,'9ad64324-a380-443b-b7a3-4011702b5d9b',460,226,360,280);
await image(g,'ba1ac018-f3a3-415d-a5fd-a6b64c4c1438',848,226,360,280);
['green 96%','green 98%','green 90%'].forEach((v,i)=>text(g,v,72+i*388,518,360,44,28,'#008357',true,'Arial','center'));
text(g,'Các ảnh thử cho thấy mô hình đã nhận diện được tắc sống.',76,582,1120,42,30);
const d=content(7,'7. Ví dụ nhận diện tắc hư',[]);
await image(d,'02a99a3d-068d-461c-9491-fd77c5dd6c56',76,220,535,328);
await image(d,'cb0b0859-ad93-47ca-a16b-50dc64dddf36',662,220,535,328);
text(d,'damaged 80%',76,552,535,42,28,'#B02A24',true,'Arial','center');
text(d,'damaged 94%',662,552,535,42,28,'#B02A24',true,'Arial','center');
text(d,'% trên ảnh là độ tin cậy từng dự đoán, chưa phải độ chính xác chung.',76,606,1128,42,27);
content(8,'8. Kế hoạch tiếp theo',[
 'Đánh giá đủ 3 nhóm trên bộ ảnh kiểm tra riêng.',
 'Chạy mô hình trên Pi 5, đo tốc độ và độ trễ nhận diện.',
 'Ghép UART, cảm biến và servo, thử phân loại trên băng tải.',
 'Làm dashboard đếm quả theo ngày, ưu tiên xử lý bằng ngắt.'
]);
const end=slides[9];clean(end,9);
for(const z of end.shapes.items){if(String(z.text??'')==='05')z.text='CE224';}
const e=end.shapes.items;
e[4].text='';
e[2].text='CẢM ƠN THẦY VÀ CÁC BẠN';
e[2].text.style={fontFamily:'Times New Roman',fontSize:57,bold:true,color:'#FFFFFF'};
e[3].text='Nhóm xin nhận góp ý và trả lời câu hỏi';
e[3].position={left:173.58,top:431.31,width:950,height:78};
e[3].text.style={fontFamily:'Arial',fontSize:32,color:'#FFFFFF'};
for(let i=0;i<slides.length;i++)slides[i].speakerNotes.text='Nguồn: mô tả dự án, tiến độ và ảnh do nhóm cung cấp. Cấu hình phần cứng là thiết kế dự kiến. Chưa có số đo đánh giá tổng thể hoặc kết quả vận hành toàn hệ thống. Nhóm chưa cung cấp tên thành viên và MSSV.';
slides[5].speakerNotes.text+=' Các mục bổ sung và kiểm tra dữ liệu là công việc đề xuất tiếp theo.';
slides[6].speakerNotes.text+=' Nguồn ảnh: ảnh số 1, 3 và 5 trong tin nhắn của người dùng. green tương ứng tắc sống. Bộ ảnh cung cấp chưa có ví dụ nhãn tắc chín. Độ tin cậy không thể dùng làm độ chính xác toàn mô hình.';
slides[7].speakerNotes.text+=' Nguồn ảnh: ảnh số 2 và 4 trong tin nhắn của người dùng. damaged tương ứng tắc hư.';
await (await PresentationFile.exportPptx(p)).save(`${dir}/candidate.pptx`);
for(let i=0;i<slides.length;i++)await fs.writeFile(`${dir}/slide-${i+1}.png`,new Uint8Array(await (await slides[i].export({format:'png',scale:1})).arrayBuffer()));
await fs.writeFile(`${dir}/montage.webp`,new Uint8Array(await (await p.export({format:'webp',montage:true,scale:0.4})).arrayBuffer()));
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
// The workspace permits ordinary file copies, but Windows hard links fail here.
const nativeLink=fs.link.bind(fs);
fs.link=async(a,b)=>{try{return await nativeLink(a,b);}catch(e){if(e.code!=='EPERM')throw e;return fs.copyFile(a,b,1);}};
const r=await finalizePresentation({workspaceDir:'D:/UIT/ConveyorBelt',candidatePath:`${dir}/candidate.pptx`,finalPath:'D:/UIT/ConveyorBelt/output/CE224_Bang_tai_phan_loai_qua_tac.pptx',pythonExecutable:'C:/Users/nguye/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],explicitTotalSlideCount:10,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],verifyArtifactToolImport:true,receiptPath:`${dir}/validation.json`});
console.log(JSON.stringify(r));

