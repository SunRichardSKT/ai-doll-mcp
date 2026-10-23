// Exercise the exact gzip bytes linked into the device image, without hardware.
const fs=require('node:fs'),path=require('node:path'),zlib=require('node:zlib');
const root=path.resolve(__dirname,'..');
function embedded(name){
 const header=fs.readFileSync(path.join(root,'firmware/src/'+name+'_asset.h'),'utf8');
 const data=Buffer.from([...header.matchAll(/0x([0-9a-f]{2})/g)].map(m=>parseInt(m[1],16)));
 return zlib.gunzipSync(data).toString('utf8');
}
function source(name){
 if(process.argv.includes('--firmware'))return embedded(name);
 if(name==='device_page')return fs.readFileSync(path.join(root,'firmware/src/device_page.h'),'utf8').split('R"HTML(')[1].split(')HTML"')[0];
 if(name==='pairing')return fs.readFileSync(path.join(root,'clients/operit/vendor/qrcodegen.js'),'utf8')+'\n'+fs.readFileSync(path.join(root,'tools/pairing_connection.js'),'utf8');
 return fs.readFileSync(path.join(root,'tools/'+name+'.js'),'utf8');
}
exports.source=source;
